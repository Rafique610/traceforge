# ruff: noqa: E501
import re
import subprocess
import sys
from pathlib import Path

import pytest

from traceforge.contracts.test_run import TestOutcome, TestRunRequest, TestRunResult

FILES = {
    "shop.py": "def discount(price, pct):\n    return price - price * pct\n\n\ndef ident(x):\n    return x\n",
    "tests/test_repro.py": "from shop import discount\n\n\ndef test_ten_percent():\n    assert discount(200, 10) == 180\n",
    "tests/test_visible.py": (
        "from shop import discount, ident\n\n\ndef test_zero():\n    assert discount(100, 0) == 100\n\n\n"
        "def test_ident():\n    assert ident(7) == 7\n"
    ),
    "tests/test_hidden.py": (
        "from shop import discount\n\n\ndef test_half():\n    assert discount(50, 50) == 25\n"
    ),
}
SUITE_FILES = {
    "reproducer": "tests/test_repro.py",
    "visible": "tests/test_visible.py",
    "hidden": "tests/test_hidden.py",
}
CORRECT = "<<<<<<< SEARCH shop.py\n    return price - price * pct\n=======\n    return price - price * pct / 100\n>>>>>>> REPLACE"
WRONG = "<<<<<<< SEARCH shop.py\n    return price - price * pct\n=======\n    return price - pct * 2\n>>>>>>> REPLACE"


def git(cwd, *args):
    return subprocess.run(
        ["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path):
    r = tmp_path / "repo"
    r.mkdir()
    for rel, text in FILES.items():
        (r / rel).parent.mkdir(parents=True, exist_ok=True)
        (r / rel).write_text(text, newline="\n")
    git(r, "init", "-q")
    git(r, "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
    git(r, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base")
    return str(r), git(r, "rev-parse", "HEAD")


def real_runner(req: TestRunRequest) -> TestRunResult:
    """Real pytest on the worktree (stand-in for the sandbox)."""
    p = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", SUITE_FILES[req.suite]],
        cwd=req.worktree_path,
        capture_output=True,
        text=True,
        timeout=req.timeout_s,
        env={"PYTHONPATH": req.worktree_path, "PATH": "", "SYSTEMROOT": "C:\\Windows"},
    )
    out = p.stdout[-4000:]
    passed = int((re.search(r"(\d+) passed", out) or [0, 0])[1])
    failed = int((re.search(r"(\d+) failed", out) or [0, 0])[1])
    return TestRunResult(
        passed=passed,
        failed=failed,
        stdout_tail=out,
        duration_ms=1,
        timed_out=False,
        tests=[
            TestOutcome(
                id=SUITE_FILES[req.suite], outcome="passed" if p.returncode == 0 else "failed"
            )
        ],
    )
