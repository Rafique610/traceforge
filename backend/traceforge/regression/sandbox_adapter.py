# ruff: noqa: E501
"""Selected-visible-test execution over the real sandbox, plus the opt-in wiring (P5-S17).

Sandbox limitation (documented, verified in `sandbox/runner.py::_pytest_args`): the pytest argv of
the `visible` suite is fixed (`tests`, minus `tests/integration`), so `TestRunRequest` cannot carry
node ids. `SelectedTestRunner.run_selected` therefore runs the FULL visible suite once and filters
the outcomes down to the selected ids (`mode = "full_suite_filter"`). That run is memoised per
worktree and reused by the full-suite stage, so a targeted-then-full attempt costs ONE container
run, not two. Selection then buys feedback precision (a dependant regression is reported by id as
soon as it is seen), not wall-clock time; a true node-id run needs a sandbox API change.

Isolation: the adapter only ever forwards `suite="visible"`; its underlying runner is built with no
`hidden_dir` and no `reproducer_dir`, so the hidden tests are NEVER mounted for this suite (the
hidden gate keeps using the untouched original runner, called once by the repair loop).

Nothing here edits or imports-into a fingerprinted RC1 file.
"""

from __future__ import annotations

import ast
from collections.abc import Callable, Sequence
from contextlib import ExitStack
from pathlib import Path
from typing import Any

from traceforge.contracts.test_run import TestOutcome, TestRunRequest, TestRunResult
from traceforge.regression.history import PatchHistory
from traceforge.regression.impact import ImpactProvider, ImpactReport, get_impact_provider
from traceforge.regression.runner import RegressionAwareRunner

RunTests = Callable[[TestRunRequest], TestRunResult]
MODE = "full_suite_filter"
IMPACT_FAILED = "impact_analysis_failed"
LAYERS = ("off", "graph", "s15")


class SelectedSuiteError(RuntimeError):
    """The adapter was asked for something other than the visible suite."""


def _match(result_id: str, selected: Sequence[str], workdir_rel: str) -> bool:
    """A result id (workdir-relative, as pytest reports it) is selected if it equals a selected id
    (also with the workdir prefix stripped) or lies in a selected file-level / class-level id."""
    wd = workdir_rel.strip("/")
    for s in selected:
        s2 = s[len(wd) + 1 :] if wd and s.startswith(wd + "/") else s
        if result_id == s2 or result_id.startswith(s2 + "::") or result_id.startswith(s2 + "["):
            return True
    return False


def _to_vocab(result_id: str, selected: Sequence[str], workdir_rel: str) -> str:
    """Re-express a sandbox id in the selected-id vocabulary (repo-root-relative when the selected
    ids carry the workdir prefix) so downstream feedback recognises it as a known visible test."""
    wd = workdir_rel.strip("/")
    if wd and any(s.startswith(wd + "/") for s in selected):
        return f"{wd}/{result_id}"
    return result_id


class SelectedTestRunner:
    """`run_selected(req, ids)` and `run_visible(req)` over one underlying visible-suite runner."""

    mode = MODE

    def __init__(self, run_visible_suite: RunTests, *, workdir_rel: str = "") -> None:
        self._run, self.workdir_rel = run_visible_suite, workdir_rel
        self._memo: tuple[tuple[str, int], TestRunResult] | None = None
        self.container_runs = 0

    @staticmethod
    def _check(req: TestRunRequest) -> None:
        if req.suite != "visible":
            raise SelectedSuiteError(f"selected-test runner only runs 'visible', not {req.suite!r}")

    def _full(self, req: TestRunRequest) -> TestRunResult:
        key = (req.worktree_path, req.timeout_s)
        if self._memo is not None and self._memo[0] == key:
            return self._memo[1]
        res = self._run(req)
        self.container_runs += 1
        self._memo = (key, res)
        return res

    def run_selected(self, req: TestRunRequest, ids: Sequence[str]) -> TestRunResult:
        self._check(req)
        res = self._full(req)
        if res.error is not None or res.timed_out:
            return res
        tests = [
            TestOutcome(id=_to_vocab(t.id, ids, self.workdir_rel), outcome=t.outcome)
            for t in res.tests
            if _match(t.id, ids, self.workdir_rel)
        ]
        return res.model_copy(
            update={
                "tests": tests,
                "passed": sum(t.outcome == "passed" for t in tests),
                "failed": sum(t.outcome in ("failed", "error") for t in tests),
            }
        )

    def run_visible(self, req: TestRunRequest) -> TestRunResult:
        """Full visible suite; consumes the memo left by a targeted stage of the same worktree."""
        self._check(req)
        res = self._full(req)
        self._memo = None
        return res


def dispatching_run_tests(base: RunTests, selected: SelectedTestRunner) -> RunTests:
    """`base` for reproducer/hidden (untouched, called as before); visible goes through the memo."""

    def run_tests(req: TestRunRequest) -> TestRunResult:
        return selected.run_visible(req) if req.suite == "visible" else base(req)

    return run_tests


def make_sandbox_selected(repo_path: str | Path, service: str | None = None) -> SelectedTestRunner:
    """Real sandbox visible-only runner: no hidden_dir, no reproducer_dir (nothing can be mounted)."""
    from traceforge.faultgen.validate import SANDBOX_CFG, SANDBOX_CFGS
    from traceforge.sandbox import make_run_tests

    cfg = SANDBOX_CFGS.get(service or "", SANDBOX_CFG)
    return SelectedTestRunner(
        make_run_tests(repo_path, hidden_dir=None, reproducer_dir=None, cfg=cfg),
        workdir_rel=cfg.workdir_rel,
    )


def discover_visible_ids(root: str | Path, workdir_rel: str = "") -> list[str]:
    """Static visible test ids under `<root>/<workdir_rel>/tests` (not tests/integration), as
    repo-relative `path::test` ids plus file-level ids. No execution, no hidden dir involved."""
    root = Path(root)
    tdir = root / workdir_rel.strip("/") / "tests"
    ids: list[str] = []
    for f in sorted(tdir.rglob("test_*.py")) if tdir.is_dir() else []:
        rel = f.relative_to(root).as_posix()
        if "/tests/integration/" in rel:
            continue
        ids.append(rel)
        try:
            tree = ast.parse(f.read_text("utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for n in tree.body:
            if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name.startswith("test"):
                ids.append(f"{rel}::{n.name}")
            elif isinstance(n, ast.ClassDef) and n.name.startswith("Test"):
                ids += [
                    f"{rel}::{n.name}::{m.name}"
                    for m in n.body
                    if isinstance(m, ast.FunctionDef | ast.AsyncFunctionDef)
                    and m.name.startswith("test")
                ]
    return ids


class _UnavailableProvider:
    """Stands in for a provider that cannot be constructed: every analyse() fails, so the runner
    records `impact_analysis_failed` and validates with the full suite (never crash, never skip)."""

    def __init__(self, name: str, error: Exception) -> None:
        self.name, self.error = name, error

    def analyse(self, *a: Any, **k: Any) -> ImpactReport:
        raise RuntimeError(
            f"provider {self.name!r} unavailable: {type(self.error).__name__}: {self.error}"
        )


def resolve_provider(layer: str) -> ImpactProvider:
    try:
        return get_impact_provider(layer)
    except Exception as e:  # missing module, bad factory
        return _UnavailableProvider(layer, e)  # type: ignore[return-value]


def feedback_enabled(condition: str) -> bool:
    """F1 conditions only (L1/G1): the repair loop forwards visible output to the next attempt only
    for F1, and F0 never receives anything."""
    return condition.endswith("1")


def wire_regression(
    base_run: RunTests,
    *,
    layer: str,
    repo_path: str | Path,
    base_sha: str,
    selected: SelectedTestRunner,
    condition: str,
    history_path: str | Path | None = None,
    hidden_paths: Sequence[str] = ("hidden_tests",),
    hidden_markers: Sequence[str] = (),
    extra_leak_check: Callable[[list[dict]], None] | None = None,
    max_attempts: int = 3,
    stack: ExitStack,
    provider: ImpactProvider | None = None,
) -> Any:
    """Build the runner that replaces `run_tests` for one run. `stack` owns the base worktree
    (close it after the run). The original `base_run` still serves reproducer and hidden calls."""
    from traceforge.regression.impact import is_hidden_path
    from traceforge.repair.worktree import worktree

    if layer == "off":
        return base_run  # identity: the original runner object, nothing wrapped
    if layer not in LAYERS[1:]:
        raise ValueError(f"regression layer must be one of {LAYERS[1:]}, got {layer!r}")
    base = stack.enter_context(worktree(str(repo_path), base_sha))
    return RegressionAwareRunner(
        provider=provider or resolve_provider(layer),
        base_root=base,
        visible_tests=[
            i
            for i in discover_visible_ids(base, selected.workdir_rel)
            if not is_hidden_path(i.split("::")[0], hidden_paths)
        ],
        run_tests=dispatching_run_tests(base_run, selected),
        run_selected=selected.run_selected,
        history=PatchHistory(history_path),
        hidden_paths=hidden_paths, hidden_markers=hidden_markers, max_attempts=max_attempts,
        extra_leak_check=extra_leak_check,
        feedback=feedback_enabled(condition),
    )  # fmt: skip


def regression_meta(
    layer: str, runner: RegressionAwareRunner | None, history_path: str | None
) -> dict:
    """The meta.json block: provider, impact_sha256 per attempt, selected tests, targeted vs full."""
    if runner is None:
        return {"regression_layer": layer}
    return {
        "regression_layer": layer,
        "impact_provider": getattr(runner.provider, "name", type(runner.provider).__name__),
        "regression_mode": MODE,
        "patch_history": history_path,
        "hidden_calls": runner.hidden_calls,
        "regression_attempts": [
            {
                "attempt": v.attempt,
                "impact_sha256": v.impact_sha256,
                "selected_tests": v.selected_tests,
                "selection_fallback": v.selection_fallback,
                "targeted": v.targeted_result,
                "full_visible": v.full_visible_result,
                "outcome": v.outcome,
                "note": v.note,
            }
            for v in runner.history.versions
        ],
        "impact_analysis_failed": any((v.note or "").startswith(IMPACT_FAILED) for v in runner.history.versions),
    }  # fmt: skip
