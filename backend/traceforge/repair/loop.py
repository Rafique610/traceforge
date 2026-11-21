"""Repair attempt loop (P2-S04): propose, policy, worktree, visible suite, hidden gate once."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, Literal

from traceforge.contracts.test_run import TestRunRequest, TestRunResult
from traceforge.repair import policy
from traceforge.repair.edits import EditError, apply_edits, parse_blocks, to_unified_diff
from traceforge.repair.worktree import read_base_file, worktree

Outcome = Literal["TEST_VERIFIED_IN_LAB", "REJECTED", "UNVERIFIED", "NO_PATCH"]
RunTests = Callable[[TestRunRequest], TestRunResult]
ProposeEdit = Callable[[Any, str | None], str]
MAX_ATTEMPTS = 3
FEEDBACK_CAP = 2000


@dataclass
class Attempt:
    n: int
    feedback: str | None
    reasons: list[str] = field(default_factory=list)
    diff: str | None = None
    visible_passed: bool | None = None


@dataclass
class RepairResult:
    outcome: Outcome
    reason: str | None = None
    attempts: list[Attempt] = field(default_factory=list)
    diff: str | None = None
    patch_sha256: str | None = None
    hidden_passed: bool | None = None
    hidden_result: TestRunResult | None = None  # stored in the run record/DB, never in a prompt
    signature_changed: bool = False
    repro_before: str | None = None
    repro_after: str | None = None

    def transition_payload(self) -> dict[str, Any]:
        """Payload for PATCH_PROPOSED/VALIDATING -> VERIFIED|UNVERIFIED (P1-S04 guard)."""
        return {
            "repro_before": self.repro_before,
            "repro_after": self.repro_after,
            "patch_sha256": self.patch_sha256,
            "outcome": self.outcome,
            "reason": self.reason,
        }


def _clean(r: TestRunResult) -> bool:
    return r.error is None and not r.timed_out


def _green(r: TestRunResult) -> bool:
    return _clean(r) and r.failed == 0 and r.passed > 0


def _feedback(repro: TestRunResult, visible: TestRunResult) -> str:
    """Visible-suite output only (F1), capped."""
    bad = [t.id for t in visible.tests if t.outcome in ("failed", "error")]
    text = (
        f"reproducer:\n{repro.stdout_tail}\nvisible suite:\n{visible.stdout_tail}\nfailing: {bad}"
    )
    return text[:FEEDBACK_CAP]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_repair(
    *,
    case_id: str,
    repo_path: str,
    base_sha: str,
    condition: Literal["F0", "F1"],
    context: Any,
    propose_edit: ProposeEdit,
    run_tests: RunTests,
    allowlist: Iterable[str],
    visible_test_sources: Iterable[str] = (),
    max_attempts: int = MAX_ATTEMPTS,
    timeout_s: int = 120,
    worktree_root: str | None = None,
) -> RepairResult:
    allow, sources = list(allowlist), list(visible_test_sources)

    def run(wt: Any, suite: Literal["visible", "hidden", "reproducer"]) -> TestRunResult:
        return run_tests(
            TestRunRequest(case_id=case_id, worktree_path=str(wt), suite=suite, timeout_s=timeout_s)
        )

    res = RepairResult(outcome="REJECTED")

    # Baseline: the reproducer must fail on the unpatched base.
    with worktree(repo_path, base_sha, root=worktree_root) as wt:
        base = run(wt, "reproducer")
    if not _clean(base):
        res.outcome, res.reason = "UNVERIFIED", "sandbox_error"
        return res
    if _green(base) or base.failed == 0:
        res.outcome, res.reason = "UNVERIFIED", "fault_not_reproduced"
        return res
    res.repro_before = "failed"

    last_visible: str | None = None
    final_diff: str | None = None
    final_sig = False
    passed_visible = False
    for n in range(1, max_attempts + 1):
        att = Attempt(n=n, feedback=last_visible if condition == "F1" else None)
        res.attempts.append(att)
        raw = propose_edit(context, att.feedback)
        if not raw.strip() or raw.strip() == "NO_PATCH":
            res.outcome, res.reason = "NO_PATCH", "no_patch_proposed"
            return res
        try:
            blocks = parse_blocks(raw)
            att.reasons = policy.check_paths([b.path for b in blocks], allow)
            if att.reasons:
                continue
            old: dict[str, str] = {}
            for p in dict.fromkeys(b.path for b in blocks):
                text, link = read_base_file(repo_path, base_sha, p)
                if link:
                    raise EditError("symlink", p)
                if text is None:
                    raise EditError("file_missing_or_binary", p)
                old[p] = text
            new = apply_edits(old, blocks)
        except EditError as e:
            att.reasons = att.reasons or [e.reason]
            continue
        diff = to_unified_diff(old, new)
        pol = policy.check_patch(diff, old, new, sources)
        att.reasons = pol.reasons
        if not diff or not pol.ok:
            att.reasons = att.reasons or ["empty_diff"]
            continue
        att.diff = diff
        final_diff, final_sig = diff, pol.signature_changed
        with worktree(repo_path, base_sha, diff, root=worktree_root) as wt:
            repro, vis = run(wt, "reproducer"), run(wt, "visible")  # whole visible suite
        if not (_clean(repro) and _clean(vis)):
            res.outcome, res.reason = "UNVERIFIED", "sandbox_error"
            res.diff, res.patch_sha256 = diff, sha256_text(diff)
            return res
        att.visible_passed = _green(repro) and vis.failed == 0
        last_visible = _feedback(repro, vis)
        if att.visible_passed:
            passed_visible = True
            break

    if final_diff is None:
        res.reason = "; ".join(res.attempts[-1].reasons)
        return res

    # Freeze, then run the hidden suite once on the frozen patch. Never fed back to any prompt.
    res.diff, res.patch_sha256, res.signature_changed = (
        final_diff,
        sha256_text(final_diff),
        final_sig,
    )
    with worktree(repo_path, base_sha, final_diff, root=worktree_root) as wt:
        hidden = run(wt, "hidden")
    res.hidden_result = hidden
    if not _clean(hidden):
        res.outcome, res.reason = "UNVERIFIED", "sandbox_error"
        return res
    res.hidden_passed = _green(hidden)
    if passed_visible and res.hidden_passed:
        res.outcome, res.repro_after = "TEST_VERIFIED_IN_LAB", "passed"
    else:
        res.outcome = "REJECTED"
        res.reason = "hidden_failed" if passed_visible else "visible_failed"
        res.repro_after = "passed" if passed_visible else "failed"
    return res
