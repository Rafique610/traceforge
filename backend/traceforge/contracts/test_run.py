"""TestRunRequest -> TestRunResult: run one suite on a worktree in the sandbox (Track A runner)."""

from typing import Literal

from pydantic import BaseModel, Field


class TestRunRequest(BaseModel):
    __test__ = False  # not a pytest class

    case_id: str
    worktree_path: str = Field(description="Repo-relative POSIX path of the disposable worktree")
    suite: Literal["visible", "hidden", "reproducer"]
    timeout_s: int = Field(default=120, gt=0, le=900)


class TestOutcome(BaseModel):
    __test__ = False

    id: str
    outcome: Literal["passed", "failed", "error", "skipped"]


class TestRunResult(BaseModel):
    __test__ = False

    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    tests: list[TestOutcome]
    stdout_tail: str = Field(max_length=4096)
    duration_ms: int = Field(ge=0)
    timed_out: bool
    error: str | None = None
