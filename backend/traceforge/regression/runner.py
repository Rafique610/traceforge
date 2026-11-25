"""RegressionAwareRunner: a drop-in `run_tests` for `repair.loop.run_repair` (loop unchanged).

Per attempt (the loop's `visible` call on the patched worktree): impact report -> selected visible
tests first (fast fail) -> full visible suite. `reproducer` and `hidden` calls pass straight
through, so the loop still runs the hidden gate exactly once, as before. Every attempt is stored
as a `PatchVersion`. The runner also enforces a hard attempt ceiling (no unlimited loops).
"""

from __future__ import annotations

import difflib
import hashlib
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from traceforge.contracts.test_run import TestRunRequest, TestRunResult
from traceforge.regression.feedback import LeakGuard, LeakRefused, build_regression_feedback
from traceforge.regression.history import PatchHistory, PatchVersion
from traceforge.regression.impact import ImpactProvider, ImpactReport
from traceforge.regression.selection import select_tests

MAX_ATTEMPTS_CEILING = 10
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".cache", ".mypy_cache", ".ruff_cache"}
RunTests = Callable[[TestRunRequest], TestRunResult]
RunSelected = Callable[[TestRunRequest, Sequence[str]], TestRunResult]


class RegressionGuardError(RuntimeError):
    """Attempt ceiling exceeded or a configuration that would allow an unlimited loop."""


def tree_diff(base: Path, patched: Path) -> str:
    """Canonical unified diff of the differing files (also used for the patch sha256)."""

    def files(root: Path) -> dict[str, bytes]:
        out = {}
        for p in sorted(root.rglob("*")):
            rel = p.relative_to(root)
            if p.is_file() and not (set(rel.parts) & SKIP_DIRS) and p.suffix != ".pyc":
                out[rel.as_posix()] = p.read_bytes()
        return out

    a, b = files(base), files(patched)
    chunks = []
    for rel in sorted(set(a) | set(b)):
        if a.get(rel) == b.get(rel):
            continue
        la = a.get(rel, b"").decode("utf-8", "replace").replace("\r\n", "\n").splitlines(True)
        lb = b.get(rel, b"").decode("utf-8", "replace").replace("\r\n", "\n").splitlines(True)
        chunks.append("".join(difflib.unified_diff(la, lb, f"a/{rel}", f"b/{rel}")))
    return "".join(chunks)


def _summary(r: TestRunResult) -> dict[str, Any]:
    return {
        "passed": r.passed,
        "failed": r.failed,
        "failing": sorted(t.id for t in r.tests if t.outcome in ("failed", "error")),
        "error": r.error,
        "timed_out": r.timed_out,
    }


def _clean(r: TestRunResult) -> bool:
    return r.error is None and not r.timed_out


class RegressionAwareRunner:
    def __init__(
        self,
        *,
        provider: ImpactProvider,
        base_root: str | Path,
        visible_tests: Sequence[str],
        run_tests: RunTests,
        run_selected: RunSelected,
        history: PatchHistory | None = None,
        hidden_paths: Sequence[str] = (),
        hidden_markers: Sequence[str] = (),
        max_attempts: int = 3,
        fast_fail: bool = True,
        seeds: Sequence[str] = (),
        extra_leak_check: Callable[[list[dict]], None] | None = None,
        feedback: bool = True,
    ) -> None:
        if not isinstance(max_attempts, int) or not 1 <= max_attempts <= MAX_ATTEMPTS_CEILING:
            raise RegressionGuardError(
                f"max_attempts must be an int in 1..{MAX_ATTEMPTS_CEILING}, got {max_attempts!r}"
            )
        self.provider, self.base_root = provider, Path(base_root)
        self.visible_tests, self.hidden_paths = list(visible_tests), list(hidden_paths)
        self.run_tests, self.run_selected = run_tests, run_selected
        self.history = history if history is not None else PatchHistory()
        self.max_attempts, self.fast_fail, self.seeds = max_attempts, fast_fail, list(seeds)
        self.guard = LeakGuard(hidden_markers, hidden_paths, extra_leak_check)
        self.feedback = feedback  # False (F0): the targeted result is returned unmodified
        self.attempts = 0
        self.hidden_calls = 0
        self.last_report: ImpactReport | None = None

    def __call__(self, req: TestRunRequest) -> TestRunResult:
        if req.suite == "hidden":
            self.hidden_calls += 1
            res = self.run_tests(req)  # untouched; counts only are recorded, never fed back
            self.history.append_event(
                "hidden_gate", passed=res.passed, failed=res.failed, error=res.error
            )
            return res
        if req.suite != "visible":
            return self.run_tests(req)
        return self._visible(req)

    def _visible(self, req: TestRunRequest) -> TestRunResult:
        self.attempts += 1
        if self.attempts > self.max_attempts:
            raise RegressionGuardError(
                f"attempt {self.attempts} exceeds max_attempts={self.max_attempts}"
            )
        wt = Path(req.worktree_path)
        patch_sha = hashlib.sha256(tree_diff(self.base_root, wt).encode("utf-8")).hexdigest()
        note = None
        try:
            report = self.provider.analyse(
                self.base_root, wt, visible_tests=self.visible_tests,
                hidden_paths=self.hidden_paths, seeds=self.seeds,
            )  # fmt: skip
            sel = select_tests(report, self.visible_tests)
        except Exception as e:  # analysis must never block validation: degrade to the full suite
            report, sel = None, select_tests(ImpactReport(), self.visible_tests)
            note = f"impact_analysis_failed: {type(e).__name__}: {str(e)[:200]}"
        self.last_report = report
        ver = PatchVersion(
            attempt=self.attempts, patch_sha256=patch_sha,
            impact_sha256=report.impact_sha256 if report else None,
            selected_tests=sel.ids, targeted_result=None, full_visible_result=None,
            outcome="visible_passed", selection_fallback=sel.fallback, note=note,
        )  # fmt: skip
        if sel.ids:
            targeted = self.run_selected(req, sel.ids)
            ver.targeted_result = _summary(targeted)
            if not _clean(targeted):
                ver.outcome = "sandbox_error"
                self.history.append(ver)
                return targeted
            if targeted.failed > 0:
                ver.outcome = "targeted_failed"
                if self.fast_fail:
                    self.history.append(ver)
                    if not self.feedback:
                        return targeted
                    return targeted.model_copy(
                        update={"stdout_tail": self._feedback(targeted, report)[:4096]}
                    )
        full = self.run_tests(req)
        ver.full_visible_result = _summary(full)
        if not _clean(full):
            ver.outcome = "sandbox_error"
        elif full.failed > 0 and ver.outcome != "targeted_failed":
            ver.outcome = "visible_failed"
        elif full.failed == 0 and ver.outcome != "targeted_failed":
            ver.outcome = "visible_passed"
        self.history.append(ver)
        return full

    def _feedback(self, targeted: TestRunResult, report: ImpactReport | None) -> str:
        rep = report or ImpactReport()
        for include in (True, False):  # drop the excerpt first if it trips the guard
            try:
                return build_regression_feedback(
                    targeted, rep, self.visible_tests, self.guard, include_excerpt=include
                )
            except LeakRefused:
                continue
        return "Your patch broke a selected visible test (details withheld by the leak guard)."


def run_repair_regression_aware(
    *,
    provider: ImpactProvider,
    run_selected: RunSelected,
    visible_tests: Sequence[str],
    history: PatchHistory | None = None,
    hidden_paths: Sequence[str] = (),
    hidden_markers: Sequence[str] = (),
    fast_fail: bool = True,
    seeds: Sequence[str] = (),
    max_attempts: int = 3,
    **run_repair_kwargs: Any,
):
    """Opt-in wrapper: `run_repair(...)` with `run_tests` replaced by a RegressionAwareRunner.

    `run_repair_kwargs` are the unchanged `run_repair` keyword arguments (repo_path, base_sha,
    run_tests, ...). `max_attempts` is passed through; returns (RepairResult, runner).
    """
    from traceforge.repair.loop import run_repair
    from traceforge.repair.worktree import worktree

    base_run = run_repair_kwargs.pop("run_tests")
    with worktree(run_repair_kwargs["repo_path"], run_repair_kwargs["base_sha"]) as base:
        runner = RegressionAwareRunner(
            provider=provider, base_root=base, visible_tests=visible_tests,
            run_tests=base_run, run_selected=run_selected, history=history,
            hidden_paths=hidden_paths, hidden_markers=hidden_markers, max_attempts=max_attempts,
            fast_fail=fast_fail, seeds=seeds,
        )  # fmt: skip
        result = run_repair(run_tests=runner, max_attempts=max_attempts, **run_repair_kwargs)
    return result, runner
