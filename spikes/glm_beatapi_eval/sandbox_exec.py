"""Run pytest on a worktree inside the locked-down TraceForge sandbox container.

Reuses traceforge.sandbox (docker_run_args: network none, read-only fs, tmpfs /tmp, cap-drop ALL,
non-root, memory/pids limits; image built once). The tree is mounted READ-ONLY at /work; the only
writable bind mount is a scratch dir for the junit report. No model-edited code runs on the host.
"""

from __future__ import annotations

import re
import tempfile
import time
import uuid
from pathlib import Path

from traceforge.sandbox.config import SandboxConfig
from traceforge.sandbox.images import SandboxError, ensure_image
from traceforge.sandbox.report import parse_junit, tail
from traceforge.sandbox.runner import _mount, _run_container, docker_cleanup, docker_run_args

REQS = (
    "pytest==9.2.0 fastapi==0.165.0 sqlalchemy==2.1.9 pydantic==2.14.4 pydantic-settings==2.16.3 "
    "httpx==0.28.1 psycopg[binary]==3.3.9 alembic==1.20.1 openai==3.57.0 networkx==3.7 "
    "rank-bm25==0.2.2 pyyaml==6.0.3 docker==7.2.0"
)
CFG = SandboxConfig(requirements=REQS, workdir_rel="backend", memory="768m", pids_limit=128)
_PATH_OK = re.compile(r"^tests(/[A-Za-z0-9_.\-]+)*(::[A-Za-z0-9_\[\]\-.]+)*$")
_NOISE = re.compile(r"\bin \d+(\.\d+)?s\b|/tmp/\S+|\(\d+:\d+:\d+\)")


def normalise_test_path(p: str) -> str:
    p = p.strip().replace("\\", "/").removeprefix("backend/").removeprefix("./") or "tests"
    if ".." in p.split("/") or not _PATH_OK.match(p):
        raise ValueError(f"test path must be under tests/ (got {p!r})")
    return p


def run_pytest(tree: Path, paths: list[str], timeout_s: int = 240, cap: int = 3000) -> dict:
    """Never raises: sandbox problems come back as `error`."""
    t0 = time.monotonic()
    name = f"tf-eval-{uuid.uuid4().hex[:10]}"
    res = {"paths": paths, "passed": 0, "failed": 0, "tests": [], "tail": "", "error": None,
           "timed_out": False, "exit_code": None}
    try:
        paths = [normalise_test_path(p) for p in paths] or ["tests"]
        tag = ensure_image(CFG)
        with tempfile.TemporaryDirectory(prefix="tf-evalout-") as out:
            outp = Path(out)
            outp.chmod(0o777)
            argv = [
                *docker_run_args(CFG, name),
                *_mount(tree.resolve(), "/work"),
                *_mount(outp, "/out", ro=False),
                "--workdir", "/work/backend", "-e", "PYTHONPATH=/work/backend", tag,
                "python", "-m", "pytest", "-p", "no:cacheprovider", "-o", "junit_family=xunit1",
                "--junitxml=/out/report.xml", "-q", "-rN", "--tb=short", "--disable-warnings",
                "--rootdir", "/work/backend", *paths,
            ]  # fmt: skip
            try:
                code, text, timed_out = _run_container(argv, name, timeout_s)
            finally:
                docker_cleanup(name)
            res.update(exit_code=code, timed_out=timed_out)
            report = outp / "report.xml"
            xml = report.read_text("utf-8", "replace") if report.is_file() else None
        res["tail"] = _NOISE.sub("", tail(text, cap))
        if xml:
            tests, _ = parse_junit(xml)
            res["tests"] = [(t.id.split("::")[-1], t.outcome) for t in tests]
            res["passed"] = sum(t.outcome == "passed" for t in tests)
            res["failed"] = sum(t.outcome in ("failed", "error") for t in tests)
        elif not timed_out:
            res["error"] = f"no test report (exit {code})"
    except (SandboxError, OSError, ValueError) as e:
        res["error"] = str(e)[:300]
    res["wall_s"] = round(time.monotonic() - t0, 1)
    return res


def summarise(r: dict) -> str:
    """Compact text for the model: counts, failing names, output tail."""
    if r["error"]:
        return f"SANDBOX ERROR: {r['error']}\n{r['tail']}"
    bad = [n for n, o in r["tests"] if o in ("failed", "error")]
    head = f"passed={r['passed']} failed={r['failed']} timed_out={r['timed_out']}"
    if bad:
        head += "\nFAILING: " + ", ".join(bad[:25])
    return head + "\n--- output tail ---\n" + r["tail"]
