"""Repair attempt loop (P2-S04): propose, policy, worktree, visible suite, hidden gate once."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, Literal

from traceforge.contracts.test_run import TestRunRequest, TestRunResult
from traceforge.repair import policy
from traceforge.repair.edits import EditError, apply_edits, parse_blocks, to_unified_diff
from traceforge.repair.feedback import (
    FEEDBACK_CAP,
    FeedbackItem,
    build_feedback,
    build_feedback_legacy,
    compose,
    sha256_text,
    summarize_edit,
)
from traceforge.repair.scope import describe_reasons
from traceforge.repair.worktree import WorktreeError, read_base_file, worktree

Outcome = Literal["TEST_VERIFIED_IN_LAB", "REJECTED", "UNVERIFIED", "NO_PATCH"]
RunTests = Callable[[TestRunRequest], TestRunResult]
ProposeEdit = Callable[[Any, str | None], str]
MAX_ATTEMPTS = 3


@dataclass
class Attempt:
    n: int
    feedback: str | None
    reasons: list[str] = field(default_factory=list)
    diff: str | None = None
    visible_passed: bool | None = None
    counts: dict[str, int] | None = None  # audit only: reproducer/visible passed and failed
    visible_outcomes: dict[str, str] | None = (
        None  # audit: visible test id -> outcome (regressions)
    )
    reproducer_outcomes: dict[str, str] | None = None
    # F1 only: the exact items (visible reproducer / visible suite output of the previous
    # attempt) whose composed text is `feedback`; `feedback_sha256` = sha256 of that text.
    feedback_items: tuple[FeedbackItem, ...] = ()
    feedback_sha256: str | None = None
    edit_summary: str | None = None  # what THIS attempt changed (visible side; shown to the next)
    rejection_text: str | None = None  # readable reasons (audit; not sent to the model)
    sandbox_detail: str | None = None


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
    detail: str | None = None  # sandbox error message, for audit (reason stays a stable code)

    def freeze_patch(self) -> None:
        """Forbid reassigning the diff and hash (called before the hidden run)."""
        object.__setattr__(self, "_frozen", True)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in ("diff", "patch_sha256", "signature_changed") and self.__dict__.get("_frozen"):
            raise AttributeError(f"{name} is frozen: the patch was fixed before the hidden run")
        object.__setattr__(self, name, value)

    def patch_consistent(self) -> bool:
        """The stored diff and hash agree (the hash is the sha256 of the exact diff text)."""
        return (self.diff is None and self.patch_sha256 is None) or (
            self.diff is not None and self.patch_sha256 == sha256_text(self.diff)
        )

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
    scope_check: Callable[[dict[str, str], dict[str, str]], list[str]] | None = None,
    feedback_style: Literal["v5", "legacy"] = "v5",
) -> RepairResult:
    allow, sources = list(allowlist), list(visible_test_sources)

    def run(wt: Any, suite: Literal["visible", "hidden", "reproducer"]) -> TestRunResult:
        try:
            return run_tests(
                TestRunRequest(
                    case_id=case_id, worktree_path=str(wt), suite=suite, timeout_s=timeout_s
                )
            )
        except Exception as e:  # a runner crash is a sandbox error, never a test failure
            return TestRunResult(
                passed=0,
                failed=0,
                tests=[],
                stdout_tail="",
                duration_ms=0,
                timed_out=False,
                error=f"runner_exception: {type(e).__name__}: {str(e)[:300]}",
            )

    def sandbox_error(r: TestRunResult | None, where: str) -> None:
        res.outcome, res.reason = "UNVERIFIED", "sandbox_error"
        res.detail = f"{where}: " + (
            "timeout" if r is not None and r.timed_out else (r.error if r else None) or "failed"
        )

    res = RepairResult(outcome="REJECTED")

    # Baseline: the reproducer must fail on the unpatched base.
    try:
        with worktree(repo_path, base_sha, root=worktree_root) as wt:
            base = run(wt, "reproducer")
    except WorktreeError as e:
        res.outcome, res.reason, res.detail = (
            "UNVERIFIED",
            "sandbox_error",
            f"baseline worktree: {e}",
        )
        return res
    if not _clean(base):
        sandbox_error(base, "baseline reproducer")
        return res
    if _green(base) or base.failed == 0:
        res.outcome, res.reason = "UNVERIFIED", "fault_not_reproduced"
        return res
    res.repro_before = "failed"

    last_items: tuple[FeedbackItem, ...] = ()
    last_edit: str | None = None
    final_diff: str | None = None
    final_sig = False
    passed_visible = False
    for n in range(1, max_attempts + 1):
        att = Attempt(n=n, feedback=None)
        if condition == "F1" and last_items:  # F0 never receives anything
            att.feedback_items = last_items
            att.feedback = compose(last_items, last_edit)
            att.feedback_sha256 = sha256_text(att.feedback)
        res.attempts.append(att)
        raw = propose_edit(context, att.feedback)
        if not raw.strip() or raw.strip() == "NO_PATCH":
            res.outcome, res.reason = "NO_PATCH", "no_patch_proposed"
            return res
        try:
            blocks = parse_blocks(raw)
            att.reasons = policy.check_paths([b.path for b in blocks], allow)
            if att.reasons:
                att.rejection_text = describe_reasons(att.reasons)
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
            att.rejection_text = describe_reasons(att.reasons)
            continue
        diff = to_unified_diff(old, new)
        pol = policy.check_patch(diff, old, new, sources)
        if scope_check is not None and pol.ok and (out := scope_check(old, new)):
            pol.ok, pol.reasons = False, out  # v5: the edit goes beyond the diagnosed target
        att.reasons = pol.reasons
        if not diff or not pol.ok:
            att.reasons = att.reasons or ["empty_diff"]
            att.rejection_text = describe_reasons(att.reasons)
            continue
        try:
            with worktree(repo_path, base_sha, diff, root=worktree_root) as wt:
                repro, vis = run(wt, "reproducer"), run(wt, "visible")  # whole visible suite
        except WorktreeError:  # the diff does not apply to the base revision: a failed attempt
            att.reasons = ["patch_does_not_apply"]
            att.rejection_text = describe_reasons(att.reasons)
            continue
        att.diff = diff
        final_diff, final_sig = diff, pol.signature_changed
        if not (_clean(repro) and _clean(vis)):
            sandbox_error(repro if not _clean(repro) else vis, f"attempt {n}")
            att.sandbox_detail = res.detail
            res.diff, res.patch_sha256 = diff, sha256_text(diff)
            return res
        att.visible_passed = _green(repro) and vis.failed == 0
        att.counts = {
            "repro_passed": repro.passed,
            "repro_failed": repro.failed,
            "visible_passed": vis.passed,
            "visible_failed": vis.failed,
        }
        att.visible_outcomes = {t.id: t.outcome for t in vis.tests}
        att.reproducer_outcomes = {t.id: t.outcome for t in repro.tests}
        if feedback_style == "legacy":  # pipeline v4: the original text, no edit summary
            last_items, last_edit = build_feedback_legacy(repro, vis), None
        else:
            att.edit_summary = summarize_edit(diff)
            reserve = len(att.edit_summary) + 24 if att.edit_summary else 0
            last_items = build_feedback(repro, vis, FEEDBACK_CAP - reserve)  # visible runs only
            last_edit = att.edit_summary
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
    res.freeze_patch()
    try:
        with worktree(repo_path, base_sha, final_diff, root=worktree_root) as wt:
            hidden = run(wt, "hidden")
    except WorktreeError as e:
        res.outcome, res.reason, res.detail = "UNVERIFIED", "sandbox_error", f"hidden worktree: {e}"
        return res
    res.hidden_result = hidden
    if not _clean(hidden):
        sandbox_error(hidden, "hidden suite")
        return res
    res.hidden_passed = _green(hidden)
    if passed_visible and res.hidden_passed:
        res.outcome, res.repro_after = "TEST_VERIFIED_IN_LAB", "passed"
    else:
        res.outcome = "REJECTED"
        res.reason = "hidden_failed" if passed_visible else "visible_failed"
        res.repro_after = "passed" if passed_visible else "failed"
    return res
