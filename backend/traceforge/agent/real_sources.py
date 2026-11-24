# ruff: noqa: E501
"""Real adapters behind the agent's source protocols (no samples, no stand-ins).

- `ManifestCaseSource`: CaseSource over a dataset manifest (e.g. datasets/manifests/dev.json).
- `LabEvidenceSource`: EvidenceSource returning the REAL EvidenceBundle collected from the live lab
  for a case (saved by `agent.lab_collect`), or collecting live through an `EvidenceCollector`.
- `real_sources(...)`: a `Sources` with `RealContextSource` (retrieval + code graph) over a repo tree.
- `make_sandbox_run_tests`: the real Docker sandbox (`make_run_tests` + `faultgen.validate.SANDBOX_CFG`).
- `HiddenLeakGuard`: asserts hidden-test material never appears in any model prompt.
"""

import hashlib
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from traceforge.agent.pipeline import Sources
from traceforge.contracts.case_manifest import CaseManifest
from traceforge.contracts.evidence import EvidenceBundle
from traceforge.contracts.test_run import TestRunRequest, TestRunResult
from traceforge.retrieval.sources import RealContextSource

TEST_NAME = re.compile(r"\bdef (test_\w+)|^(?:\s*)async def (test_\w+)", re.M)


class ManifestCaseSource:
    def __init__(self, manifest: Path) -> None:
        raw = Path(manifest).read_bytes()
        self.sha256 = hashlib.sha256(raw).hexdigest()
        self._cases = {c["case_id"]: CaseManifest.model_validate(c) for c in json.loads(raw)}

    def get(self, case_id: str) -> CaseManifest:
        try:
            return self._cases[case_id]
        except KeyError:
            raise KeyError(f"case {case_id!r} not in manifest") from None


class LabEvidenceSource:
    """Saved real bundle `<evidence_dir>/<case_id>.json`; falls back to a live collector if given."""

    def __init__(self, evidence_dir: Path, collector: Any = None) -> None:
        self.dir, self.collector = Path(evidence_dir), collector

    def collect(self, incident_id: str, service: str, case: CaseManifest | None) -> EvidenceBundle:
        p = self.dir / f"{case.case_id}.json" if case else None
        if p is not None and p.is_file():
            b = EvidenceBundle.model_validate_json(p.read_text("utf-8"))
            return b.model_copy(update={"incident_id": incident_id})
        if self.collector is None:
            raise FileNotFoundError(f"no saved evidence for {case and case.case_id} in {self.dir}")
        return self.collector.collect(incident_id, service, case)


def real_sources(
    manifest: Path, evidence_dir: Path, repo_path: Path, collector: Any = None
) -> Sources:
    return Sources(
        ManifestCaseSource(manifest),
        LabEvidenceSource(evidence_dir, collector),
        RealContextSource(repo_path),
    )


def make_sandbox_run_tests(
    repo_path: str | Path, datasets: Path, service: str | None = None
) -> Callable[[TestRunRequest], TestRunResult]:
    """Real sandbox: hidden tests mounted read-only from datasets/hidden_tests, never copied in."""
    from traceforge.faultgen.validate import SANDBOX_CFG, SANDBOX_CFGS
    from traceforge.sandbox import make_run_tests

    return make_run_tests(
        repo_path,
        hidden_dir=Path(datasets) / "hidden_tests",
        reproducer_dir=Path(datasets) / "reproducers",
        cfg=SANDBOX_CFGS.get(service or "", SANDBOX_CFG),  # worker cases run in lab/worker
    )


FEEDBACK_SPAN = re.compile(r"<visible_test_feedback>.*?</visible_test_feedback>", re.S)
# a symptom evidence item: from its SYMPTOM tag to the next evidence header ("[EV-...") or the end
SYMPTOM_SPAN = re.compile(r"(?:^|(?<=\n)|(?<=\] ))(?:SYMPTOM|FINDING).*?(?=\n\[EV-|\Z)", re.S)
# the diagnosis lines of the patch prompt: model output derived from the visible symptom
DIAGNOSIS_LINES = re.compile(r"^(?:Diagnosis|Rationale):.*$", re.M)
MIN_FRAGMENT = 12


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def assert_fragments(source: str) -> set[str]:
    """Normalised source text of every `assert` statement (>= MIN_FRAGMENT chars)."""
    import ast

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Assert):
            seg = ast.get_source_segment(source, n)
            if seg and len(_norm(seg)) >= MIN_FRAGMENT:
                out.add(_norm(seg))
    return out


class HiddenLeakGuard:
    """Wraps a chat function: every message is checked for hidden-test names/paths (guard v2).

    - hidden-only test names, hidden file names and the hidden path marker are blocked ANYWHERE;
    - a test name shared by hidden and visible tests (`shared_visible`) is allowed only inside a
      verified span: a `<visible_test_feedback>` block (built by the repair loop from a visible
      run) or a SYMPTOM evidence item; outside such a span it is blocked like a hidden name;
    - assert-statement fragments of the hidden tests that are not also in the visible tests are
      detected in `fragment_hits` (mode "report": recorded, not raised; "enforce": raised;
      "off": not computed). Default "report" only records, so it cannot change any run."""

    def __init__(
        self,
        hidden_root: Path,
        case_ids: list[str],
        visible_dirs: list[Path] | None = None,
        fragment_mode: str = "report",
    ) -> None:
        """`visible_dirs`: the case's own visible test directories (reproducer + visible suite)."""
        self.markers: set[str] = {"hidden_tests"}
        self.fragment_mode = fragment_mode
        hidden_frag: set[str] = set()
        for cid in case_ids:
            for f in (
                (Path(hidden_root) / cid).glob("*.py") if (Path(hidden_root) / cid).is_dir() else []
            ):
                text = f.read_text("utf-8")
                if f.name != "conftest.py":  # generic name, also a legitimate visible file
                    self.markers.add(f.name)
                self.markers |= {a or b for a, b in TEST_NAME.findall(text)}
                if fragment_mode != "off":
                    hidden_frag |= assert_fragments(text)
        self.markers.discard("")
        visible: set[str] = set()
        visible_frag: set[str] = set()
        for d in visible_dirs or []:
            for f in Path(d).glob("*.py") if Path(d).is_dir() else []:
                text = f.read_text("utf-8")
                visible |= {a or b for a, b in TEST_NAME.findall(text)}
                if fragment_mode != "off":
                    visible_frag |= assert_fragments(text)
        self.shared_visible = sorted(self.markers & visible)  # allowed only in verified spans
        self.markers -= set(self.shared_visible)
        self.fragments = sorted(hidden_frag - visible_frag)
        self.fragment_hits: list[str] = []
        self.calls = 0

    @staticmethod
    def _texts(messages: list[dict]) -> list[str]:
        return [
            m["content"] if isinstance(m.get("content"), str) else json.dumps(m.get("content"))
            for m in messages
        ]

    def check(self, messages: list[dict]) -> None:
        blob = json.dumps(messages)
        for m in self.markers:
            assert m not in blob, f"hidden-test material {m!r} found in a model prompt"
        texts = self._texts(messages)
        for msg, t in zip(messages, texts, strict=True):
            if msg.get("role") == "assistant":
                continue  # the model's own words: it only ever saw visible names (hidden-only
                # names, files and paths were checked above, in every message)
            outside = DIAGNOSIS_LINES.sub(" ", SYMPTOM_SPAN.sub(" ", FEEDBACK_SPAN.sub(" ", t)))
            for m in self.shared_visible:
                assert m not in outside, (
                    f"test name {m!r} is visible to the model only inside feedback or symptom text"
                )
        if self.fragments:
            flat = [_norm(t) for t in texts]
            for frag in self.fragments:
                if any(frag in t for t in flat):
                    self.fragment_hits.append(frag)
                    assert self.fragment_mode != "enforce", (
                        f"hidden assertion fragment {frag[:60]!r} found in a model prompt"
                    )

    def wrap(self, chat_fn: Callable[..., Any]) -> Callable[..., Any]:
        def guarded(messages: list[dict], *a: Any, **kw: Any) -> Any:
            self.calls += 1
            self.check(messages)
            return chat_fn(messages, *a, **kw)

        return guarded
