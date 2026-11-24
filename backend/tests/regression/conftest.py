# ruff: noqa: E501
"""Shared helpers: tiny git repo with a dependant, real pytest per suite (sandbox stand-in)."""

import re
import subprocess
import sys
from pathlib import Path

import pytest

from traceforge.contracts.test_run import TestOutcome, TestRunRequest, TestRunResult

FILES = {
    "shop.py": "def discount(price, pct):\n    return price - price * pct\n\n\ndef ident(x):\n    return x\n",
    "checkout.py": "from shop import discount\n\n\ndef total(price):\n    return discount(price, 0.5)\n",
    "tests/test_repro.py": "from shop import discount\n\n\ndef test_ten_percent():\n    assert discount(200, 10) == 180\n",
    "tests/test_visible.py": "from shop import discount, ident\n\n\ndef test_zero():\n    assert discount(100, 0) == 100\n\n\ndef test_ident():\n    assert ident(7) == 7\n",
    "tests/test_checkout.py": "from checkout import total\n\n\ndef test_total_halves():\n    assert total(100) == 50\n",
    "tests/test_hidden.py": "from shop import discount\n\n\ndef test_hidden_half():\n    assert discount(50, 50) == 25\n",
}
VISIBLE_FILES = ["tests/test_visible.py", "tests/test_checkout.py"]
VISIBLE_IDS = [
    "tests/test_visible.py::test_zero",
    "tests/test_visible.py::test_ident",
    "tests/test_checkout.py::test_total_halves",
]
HIDDEN_PATHS = ["tests/test_hidden.py"]
ALLOW = ["shop.py", "checkout.py"]
DISC = "<<<<<<< SEARCH shop.py\n    return price - price * pct\n=======\n    return price - price * pct / 100\n>>>>>>> REPLACE"
CALL = "<<<<<<< SEARCH checkout.py\n    return discount(price, 0.5)\n=======\n    return discount(price, 50)\n>>>>>>> REPLACE"
ENV = {"PATH": "", "SYSTEMROOT": "C:\\Windows"}


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout.strip()


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


def _pytest(wt, targets):
    p = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-rA", "-p", "no:cacheprovider", *targets],
        cwd=wt, capture_output=True, text=True, timeout=120, env={**ENV, "PYTHONPATH": str(wt)},
    )  # fmt: skip
    out = p.stdout
    tests = [
        TestOutcome(id=m[2], outcome="passed" if m[1] == "PASSED" else "failed")
        for m in re.finditer(r"^(PASSED|FAILED) (\S+?)(?: - .*)?$", out, re.M)
    ]
    return TestRunResult(
        passed=sum(t.outcome == "passed" for t in tests),
        failed=sum(t.outcome == "failed" for t in tests),
        tests=tests, stdout_tail=out[-4000:], duration_ms=1, timed_out=False,
    )  # fmt: skip


def run_tests(req: TestRunRequest) -> TestRunResult:
    files = {"reproducer": ["tests/test_repro.py"], "visible": VISIBLE_FILES, "hidden": HIDDEN_PATHS}
    return _pytest(req.worktree_path, files[req.suite])


def run_selected(req: TestRunRequest, ids) -> TestRunResult:
    return _pytest(req.worktree_path, list(ids))
