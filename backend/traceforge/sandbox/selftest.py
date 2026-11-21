"""Real-Docker selftest + timing: python -m traceforge.sandbox.selftest [--runs N]."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import tempfile
from pathlib import Path

from traceforge.contracts.test_run import TestRunRequest
from traceforge.sandbox.config import SandboxConfig
from traceforge.sandbox.images import docker, image_tag
from traceforge.sandbox.runner import run_tests_timed

FILES = {
    "tests/test_pass.py": "def test_ok():\n    assert 1 + 1 == 2\n",
    "reproducer/test_fail.py": "def test_bad():\n    assert 1 == 2\n",
    "reproducer/test_net.py": (
        "import socket, pytest\n\n\ndef test_no_network():\n"
        "    with pytest.raises(OSError):\n"
        '        socket.create_connection(("1.1.1.1", 53), timeout=3)\n'
    ),
}
SLEEP = {"reproducer/test_sleep.py": "import time\n\n\ndef test_sleep():\n    time.sleep(60)\n"}


def _run(wt: Path, suite: str, t: int = 60):
    return run_tests_timed(
        TestRunRequest(case_id="selftest", worktree_path=str(wt), suite=suite, timeout_s=t)
    )


def _write(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, newline="\n")


def selftest(runs: int = 10) -> dict:
    checks: dict[str, bool] = {}
    with tempfile.TemporaryDirectory(prefix="tf-selftest-") as d:
        wt = Path(d) / "wt"
        _write(wt, FILES)
        _run(wt, "visible")  # warm: builds the image once if absent, primes caches
        vis, _ = _run(wt, "visible")
        checks["pass"] = vis.error is None and (vis.passed, vis.failed) == (1, 0)
        # reproducer dir holds a failing test and a no-network test together
        rep, _ = _run(wt, "reproducer")
        out = {t.id.split("::")[-1]: t.outcome for t in rep.tests}
        checks["fail"] = rep.error is None and out.get("test_bad") == "failed"
        checks["no_network"] = out.get("test_no_network") == "passed"
        _write(wt, SLEEP)
        slow, _ = _run(wt, "reproducer", t=5)
        checks["timeout"] = slow.timed_out and slow.passed == 0
        (wt / "reproducer/test_sleep.py").unlink()
        samples = [_run(wt, "visible")[1] for _ in range(runs)]
    left = docker("ps", "-a", "-q", "--filter", "name=tf-sbx-").stdout.strip()
    checks["no_container_left"] = left == ""
    med = statistics.median
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "runs": runs,
        "median_wall_ms": int(med(s.wall_ms for s in samples)),
        "median_container_start_ms": int(med(s.start_ms for s in samples)),
        "median_pytest_ms": int(med(s.pytest_ms for s in samples)),
        "all_wall_ms": [s.wall_ms for s in samples],
        "image": image_tag(SandboxConfig()),
        "docker_server": docker("version", "--format", "{{.Server.Version}}").stdout.strip(),
        "platform": platform.platform(),
        "command": "backend\\.venv\\Scripts\\python.exe -m traceforge.sandbox.selftest --runs 10",
        "note": "visible suite of a 1-test project; wall = docker run incl. start; "
        "start = wall - pytest time; one container at a time",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument("--out", type=Path, default=Path(__file__).with_name("timings.json"))
    a = ap.parse_args()
    res = selftest(a.runs)
    a.out.write_text(json.dumps(res, indent=2) + "\n", "utf-8")
    print(json.dumps(res, indent=2))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
