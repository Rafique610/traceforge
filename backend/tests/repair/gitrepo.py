"""Shared helpers: build a tiny git repo and run real pytest per suite (sandbox stand-in)."""

import re
import subprocess
import sys
from pathlib import Path

from traceforge.contracts.test_run import TestOutcome, TestRunRequest, TestRunResult

SUITE_FILES = {
    "reproducer": "tests/test_repro.py",
    "visible": "tests/test_visible.py",
    "hidden": "tests/test_hidden.py",
}


def _git(cwd, *args):
    return subprocess.run(
        ["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def make_repo(root: Path, files: dict[str, str]) -> tuple[str, str]:
    root.mkdir(parents=True)
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, newline="\n")
    _git(root, "init", "-q")
    ident = ["-c", "user.name=t", "-c", "user.email=t@t"]
    _git(root, *ident, "add", "-A")
    _git(root, *ident, "commit", "-qm", "base")
    return str(root), _git(root, "rev-parse", "HEAD")


def _count(out: str, word: str) -> int:
    m = re.search(rf"(\d+) {word}", out)
    return int(m[1]) if m else 0


def pytest_runner(req: TestRunRequest) -> TestRunResult:
    p = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", SUITE_FILES[req.suite]],
        cwd=req.worktree_path,
        capture_output=True,
        text=True,
        timeout=req.timeout_s,
        env={"PYTHONPATH": req.worktree_path, "PATH": "", "SYSTEMROOT": "C:\\Windows"},
        check=False,
    )
    out = p.stdout[-4000:]
    outcome = "passed" if p.returncode == 0 else "failed"
    return TestRunResult(
        passed=_count(out, "passed"),
        failed=_count(out, "failed"),
        stdout_tail=out,
        duration_ms=1,
        timed_out=False,
        tests=[TestOutcome(id=SUITE_FILES[req.suite], outcome=outcome)],
    )
