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
    repo_path: str | Path, datasets: Path
) -> Callable[[TestRunRequest], TestRunResult]:
    """Real sandbox: hidden tests mounted read-only from datasets/hidden_tests, never copied in."""
    from traceforge.faultgen.validate import SANDBOX_CFG
    from traceforge.sandbox import make_run_tests

    return make_run_tests(
        repo_path,
        hidden_dir=Path(datasets) / "hidden_tests",
        reproducer_dir=Path(datasets) / "reproducers",
        cfg=SANDBOX_CFG,
    )


class HiddenLeakGuard:
    """Wraps a chat function: every message is checked for hidden-test names/paths/lines."""

    def __init__(self, hidden_root: Path, case_ids: list[str]) -> None:
        self.markers: set[str] = {"hidden_tests"}
        for cid in case_ids:
            for f in (
                (Path(hidden_root) / cid).glob("*.py") if (Path(hidden_root) / cid).is_dir() else []
            ):
                text = f.read_text("utf-8")
                if f.name != "conftest.py":  # generic name, also a legitimate visible file
                    self.markers.add(f.name)
                self.markers |= {a or b for a, b in TEST_NAME.findall(text)}
        self.markers.discard("")
        self.calls = 0

    def check(self, messages: list[dict]) -> None:
        blob = json.dumps(messages)
        for m in self.markers:
            assert m not in blob, f"hidden-test material {m!r} found in a model prompt"

    def wrap(self, chat_fn: Callable[..., Any]) -> Callable[..., Any]:
        def guarded(messages: list[dict], *a: Any, **kw: Any) -> Any:
            self.calls += 1
            self.check(messages)
            return chat_fn(messages, *a, **kw)

        return guarded
