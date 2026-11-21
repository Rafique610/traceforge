"""Adapter for the repair loop (P2-S04): `run_repair(run_tests=make_run_tests(...))`.

    run_tests = make_run_tests(repo_path, hidden_dir="datasets/hidden_tests",
                               reproducer_dir="datasets/reproducers")
    run_repair(..., repo_path=repo_path, run_tests=run_tests)

The loop passes `str(worktree)` (absolute, a git worktree of `repo_path`); the contract's
repo-relative POSIX form is also accepted and resolved under `repo_path` (no escaping it).
`hidden_dir/<case_id>/` is bind-mounted read-only at /hidden only for suite="hidden" and is
never copied into the worktree; hidden output is withheld, only test ids/outcomes return.
`reproducer_dir/<case_id>/` (optional) is mounted at /reproducer; otherwise the worktree's
`reproducer/` dir is used. `visible` = `tests/` minus `tests/integration`.
Use `SandboxConfig(workdir_rel="lab/shop_api")` when the service is a subdir of the repo.
"""

from collections.abc import Callable
from pathlib import Path

from traceforge.contracts.test_run import TestRunRequest, TestRunResult
from traceforge.sandbox.config import DEFAULT, SandboxConfig
from traceforge.sandbox.runner import run_tests_timed


def make_run_tests(
    repo_path: str | Path,
    hidden_dir: str | Path | None = None,
    reproducer_dir: str | Path | None = None,
    cfg: SandboxConfig = DEFAULT,
) -> Callable[[TestRunRequest], TestRunResult]:
    def run_tests(req: TestRunRequest) -> TestRunResult:
        return run_tests_timed(
            req, repo_path=repo_path, hidden_dir=hidden_dir, reproducer_dir=reproducer_dir, cfg=cfg
        )[0]

    return run_tests
