"""Symptom pipeline (pipeline v5): what actually failed, taken from the permitted visible tests.

Source: the output of the visible reproducer and the visible suite, run on the BASE commit before
diagnosis (the same suites the repair loop already runs; nothing hidden). From each failing test we
keep: its id and location, the endpoint it called (from the captured HTTP log), the assertion
source line (inputs and the check), the compared values and the first detail lines.

Provenance: every `SymptomItem` records its suite and a sha256 of the raw output it was parsed
from. Items become evidence items (kind `issue`, text starting with `SYMPTOM`) appended after the
collected evidence, so existing evidence ids never change; retrieval reads the same items.

Nothing here reads gold symbols, mutation patches, hidden tests or expected answers. `validate`
fails closed on hidden-test markers and secrets before a symptom may enter a prompt. (The
offline gold-term audit lives in `traceforge.evaluation.symptom_audit`, evaluation only.)
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass, field

from traceforge.agent.evidence_view import SYMPTOM_TAG
from traceforge.contracts.evidence import EvidenceBundle, EvidenceItem
from traceforge.contracts.test_run import TestRunRequest, TestRunResult

MAX_FAILURES = 6  # failing tests turned into items per suite
MAX_ITEM_CHARS = 700
MAX_TOTAL_CHARS = 3500
_BLOCK = re.compile(r"^_{3,} (.+?) _{3,}$", re.M)
_FRAME = re.compile(r"^(\S+?\.py):(\d+): in (\S+)")
_ELINE = re.compile(r"^E\s{2,3}(.*)$")
_REQUEST = re.compile(r'\b(GET|POST|PUT|PATCH|DELETE)\s+https?://[^/\s"]+(/[^\s"]*)')
_COMPARE = re.compile(r"assert (.+?) == (.+)$")
_SECRET = re.compile(r"(?i)\b(password|passwd|secret|api[_-]?key|token)\b\s*[=:]\s*\S{4,}")


@dataclass(frozen=True)
class SymptomItem:
    suite: str  # "reproducer" | "visible"
    test_id: str  # path::name
    name: str
    location: str | None  # "path:line" of the failing frame in the test
    request: list[str]  # ["GET /orders/1/quote?coupon=staff50"]
    check: str | None  # the assertion source line
    left: str | None  # left operand of `assert LEFT == RIGHT` (value the code under test produced)
    right: str | None  # right operand (value the test requires, by operand order)
    detail: list[str]
    source_sha256: str  # sha256 of the raw suite output this was parsed from

    def text(self) -> str:
        who = "visible reproducer" if self.suite == "reproducer" else "visible suite"
        lines = [f"{SYMPTOM_TAG} failing test in the {who}: {self.test_id}"]
        if self.request:
            lines.append("request made by the test: " + "; ".join(self.request))
        if self.check:
            lines.append(f"check: {self.check}")
        if self.left is not None and self.right is not None:
            lines.append(
                f"compared: left={self.left} right={self.right} "
                "(left = produced by the code under test, right = required by the test)"
            )
        lines += [f"detail: {d}" for d in self.detail]
        return "\n".join(lines)[:MAX_ITEM_CHARS]


@dataclass
class Symptom:
    status: str = "ok"  # ok | sandbox_error | no_failure | blocked:<reason>
    items: list[SymptomItem] = field(default_factory=list)
    counts: dict[str, dict[str, int]] = field(default_factory=dict)  # suite -> passed/failed
    sources: dict[str, str] = field(default_factory=dict)  # suite -> sha256 of raw output
    truncated: bool = False

    def entries(self) -> list[tuple[str, str | None]]:
        """(text, location "path:line" or None) per evidence item to create, summary first."""
        head = "; ".join(
            f"{s}: {c['failed']} failed, {c['passed']} passed" for s, c in self.counts.items()
        )
        out: list[tuple[str, str | None]] = []
        if head:
            out.append(
                (f"{SYMPTOM_TAG} summary of the base commit's visible test runs: {head}", None)
            )
        return out + [(i.text(), i.location) for i in self.items]

    def texts(self) -> list[str]:
        return [t for t, _ in self.entries()]

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "counts": self.counts,
            "sources_sha256": self.sources,
            "truncated": self.truncated,
            "items": [i.__dict__ for i in self.items],
        }


_ADDR = re.compile(r"0x[0-9a-fA-F]{6,}")


def _stable(text: str) -> str:
    """Drop run-to-run noise (memory addresses of objects in assertion output) so the same
    failure always produces byte-identical symptom text, whatever the run or arm."""
    return _ADDR.sub("0x...", text)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_failures(result: TestRunResult, suite: str) -> list[SymptomItem]:
    """Failing tests of one suite run, with the details pytest printed for each (best effort)."""
    out_text = result.stdout_tail or ""
    sha = _sha(out_text)
    blocks = list(_BLOCK.finditer(out_text))
    details: dict[str, str] = {}
    for n, m in enumerate(blocks):
        end = blocks[n + 1].start() if n + 1 < len(blocks) else len(out_text)
        details[m.group(1).strip().split("[")[0]] = out_text[m.end() : end]
    items: list[SymptomItem] = []
    failed = [t for t in result.tests if t.outcome in ("failed", "error")]
    for t in failed[:MAX_FAILURES]:
        tid = t.id.replace("\\", "/")
        name = tid.rpartition("::")[2].split("[")[0]
        body = details.get(name, "")
        loc = check = left = right = None
        lines = body.splitlines()
        for n, ln in enumerate(lines):
            fm = _FRAME.match(ln.strip())
            if fm and (fm.group(3) == name or loc is None):
                loc = f"{fm.group(1)}:{fm.group(2)}".replace("\\", "/")
                nxt = lines[n + 1].strip() if n + 1 < len(lines) else ""
                check = nxt[:240] or None
                if fm.group(3) == name:
                    break
        e_lines = [m.group(1).strip() for ln in lines if (m := _ELINE.match(ln)) and m.group(1)]
        if e_lines and (cm := _COMPARE.search(e_lines[0])):
            left, right = _stable(cm.group(1)[:160]), _stable(cm.group(2)[:160])
        requests = list(dict.fromkeys(f"{m[1]} {m[2]}" for m in _REQUEST.finditer(body)))[:3]
        detail = [_stable(d[:200]) for d in (e_lines[1:] if left else e_lines)[:3] if d]
        items.append(SymptomItem(suite, tid, name, loc, requests, check, left, right, detail, sha))
    return items


def build_symptom(runs: dict[str, TestRunResult]) -> Symptom:
    """Symptom from base-commit runs: {"reproducer": result, "visible": result}."""
    sym = Symptom()
    for suite, r in runs.items():
        if r.error or r.timed_out:
            sym.status = "sandbox_error"
            return sym
        sym.counts[suite] = {"passed": r.passed, "failed": r.failed}
        sym.sources[suite] = _sha(r.stdout_tail or "")
        sym.truncated = sym.truncated or len(r.stdout_tail or "") >= 4000
        sym.items += parse_failures(r, suite)
    if not sym.items:
        sym.status = "no_failure"
    total = 0
    kept = []
    for it in sym.items:  # reproducer items first, then visible; bounded in total
        total += len(it.text())
        if total <= MAX_TOTAL_CHARS:
            kept.append(it)
    sym.items = kept
    return sym


def validate(sym: Symptom, hidden_check: Callable[[list[dict]], None] | None = None) -> list[str]:
    """Reasons the symptom may NOT enter a prompt (empty list = clean). Fails closed.

    `hidden_check` is `HiddenLeakGuard.check`: it raises AssertionError on hidden-only test names,
    hidden file names or paths. Names shared with the visible tests are exempt there by design.
    """
    reasons: list[str] = []
    for text in sym.texts():
        if _SECRET.search(text):
            reasons.append("secret_pattern")
        if hidden_check is not None:
            try:
                hidden_check([{"role": "user", "content": text}])
            except AssertionError as e:
                reasons.append(f"hidden_marker: {str(e)[:120]}")
    return sorted(set(reasons))


def collect_symptom(
    run_tests: Callable[[TestRunRequest], TestRunResult],
    worktree_path: str,
    case_id: str,
    timeout_s: int = 120,
) -> Symptom:
    """Run the visible reproducer and the visible suite on a base-commit worktree (the caller owns
    the worktree). The hidden suite is never requested."""
    runs = {}
    for suite in ("reproducer", "visible"):
        runs[suite] = run_tests(
            TestRunRequest(
                case_id=case_id, worktree_path=worktree_path, suite=suite, timeout_s=timeout_s
            )
        )
    return build_symptom(runs)


def with_symptom(evidence: EvidenceBundle, sym: Symptom, findings: bool = True) -> EvidenceBundle:
    """Evidence + symptom items appended (existing ids unchanged), then the deterministic
    diagnostics findings (`traceforge.diagnostics`, kind `issue`, text starting `FINDING`) when
    `findings` is true. The caller decides about blocked/failed symptoms; a `no_failure` symptom
    adds its summary line (and so can trigger the abstention hint)."""
    items = list(evidence.items)
    service = items[0].service if items else ""
    for text, loc in sym.entries():
        n = len(items) + 1
        path, _, line = (loc or "").rpartition(":")
        items.append(
            EvidenceItem(
                id=f"EV-{n:04d}",
                kind="issue",
                service=service,
                content=text,
                sha256=_sha(text),
                path=path or None,
                line=int(line) if line.isdigit() else None,
                scope="runtime",
                basis="observed",
                origin="visible test run on the base commit (sandbox)",
            )
        )
    out = evidence.model_copy(update={"items": items})
    if findings:
        from traceforge.diagnostics import findings_as_items, run_rules

        out = out.model_copy(update={"items": [*items, *findings_as_items(out, run_rules(out))]})
    return out


@dataclass
class SymptomView:
    """What retrieval needs from the symptom items of an evidence bundle."""

    tests: list[tuple[str, str]] = field(default_factory=list)  # (suite, test_id)
    requests: list[tuple[str, str]] = field(default_factory=list)  # (METHOD, "/path?query")
    texts: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)


_TEST_LINE = re.compile(
    rf"^{SYMPTOM_TAG} failing test in the (visible reproducer|visible suite): (.+)$", re.M
)
_REQ_LINE = re.compile(r"^request made by the test: (.+)$", re.M)


def symptom_view(evidence: EvidenceBundle) -> SymptomView:
    v = SymptomView()
    for i in evidence.items:
        if not (i.kind == "issue" and i.content.startswith(SYMPTOM_TAG)):
            continue
        v.evidence_ids.append(i.id)
        v.texts.append(i.content)
        if m := _TEST_LINE.search(i.content):
            suite = "reproducer" if m.group(1) == "visible reproducer" else "visible"
            v.tests.append((suite, m.group(2).strip()))
        if m := _REQ_LINE.search(i.content):
            for r in m.group(1).split("; "):
                meth, _, path = r.partition(" ")
                if path.startswith("/"):
                    v.requests.append((meth, path))
    return v
