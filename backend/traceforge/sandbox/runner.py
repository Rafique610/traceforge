"""run_tests(TestRunRequest) -> TestRunResult inside a locked-down, disposable container.

Uses the docker CLI via subprocess (no SDK): the SDK is not a project dependency, the CLI
gives a plain `docker kill` on timeout, and --mount avoids Windows `C:\\` colon parsing.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from traceforge.contracts.test_run import TestRunRequest, TestRunResult
from traceforge.sandbox.config import DEFAULT, SandboxConfig
from traceforge.sandbox.images import SandboxError, docker, ensure_image
from traceforge.sandbox.report import parse_junit, tail

_CASE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_KEEP = 65536
HIDDEN_WITHHELD = "[hidden suite output withheld]"


@dataclass(frozen=True)
class Timing:
    """Wall = whole `docker run`; pytest = time reported by pytest; start = wall - pytest."""

    wall_ms: int
    pytest_ms: int

    @property
    def start_ms(self) -> int:
        return max(self.wall_ms - self.pytest_ms, 0)


def resolve_dir(path: str, repo_path: str | Path | None, what: str) -> Path:
    """Repo-relative POSIX path (contract) or an absolute path from the trusted caller."""
    p = Path(path)
    if not p.is_absolute():
        if repo_path is None:
            raise SandboxError(f"{what}: relative path needs repo_path")
        root = Path(repo_path).resolve()
        p = (root / p).resolve()
        if not p.is_relative_to(root):
            raise SandboxError(f"{what}: path escapes the repo")
    p = p.resolve()
    if not p.is_dir():
        raise SandboxError(f"{what}: not a directory: {p}")
    if any(c in str(p) for c in ',"\n'):
        raise SandboxError(f"{what}: unsupported character in path")
    return p


def _mount(src: Path, dst: str, ro: bool = True) -> list[str]:
    return ["--mount", f"type=bind,source={src},target={dst}" + (",readonly" if ro else "")]


def _pytest_args(suite: str, wd: str, has_repro_dir: bool) -> list[str]:
    base = ["python", "-m", "pytest", "-p", "no:cacheprovider", "-o", "junit_family=xunit1"]
    base += ["--junitxml=/out/report.xml", "-q", "-rN", "--tb=short", "--disable-warnings"]
    if suite == "visible":
        return [
            *base,
            "--rootdir",
            wd,
            "--ignore=tests/integration",
            "-m",
            "not integration",
            "tests",
        ]
    if suite == "hidden":
        return [*base, "--rootdir", "/hidden", "/hidden"]
    if has_repro_dir:
        return [*base, "--rootdir", "/reproducer", "/reproducer"]
    return [*base, "--rootdir", wd, "reproducer"]


def docker_run_args(cfg: SandboxConfig, name: str) -> list[str]:
    """Every isolation flag lives here (asserted by a unit test). Image tag is appended later."""
    return [
        "run", "--name", name, "--network", "none", "--read-only",
        "--tmpfs", f"/tmp:rw,nosuid,nodev,size={cfg.tmpfs_size}",
        "--user", cfg.user, "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--memory", cfg.memory, "--memory-swap", cfg.memory, "--cpus", cfg.cpus,
        "--pids-limit", str(cfg.pids_limit), "--ulimit", "nofile=1024:1024",
        "-e", "HOME=/tmp", "-e", "PYTHONDONTWRITEBYTECODE=1", "-e", "PYTHONHASHSEED=0",
    ]  # fmt: skip


def _run_container(argv: list[str], name: str, timeout_s: int) -> tuple[int | None, str, bool]:
    """(exit code or None if killed, bounded output tail, timed_out). Kills on timeout."""
    buf = bytearray()
    proc = subprocess.Popen(
        ["docker", *argv],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
    )

    def pump() -> None:
        assert proc.stdout is not None
        while chunk := proc.stdout.read1(8192):
            buf.extend(chunk)
            del buf[:-_KEEP]

    reader = threading.Thread(target=pump, daemon=True)
    reader.start()
    timed_out = False
    try:
        code: int | None = proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out, code = True, None
        docker("kill", name, timeout=30)
        proc.kill()
        proc.wait(timeout=30)
    reader.join(timeout=5)
    return code, buf.decode("utf-8", "replace"), timed_out


def docker_cleanup(name: str) -> None:
    try:
        docker("rm", "-f", name, timeout=30)
    except SandboxError:
        pass


def _result(tests: list, wall: int, timed_out: bool, out: str, err: str | None) -> TestRunResult:
    return TestRunResult(
        passed=sum(t.outcome == "passed" for t in tests),
        failed=sum(t.outcome in ("failed", "error") for t in tests),
        tests=tests, stdout_tail=out, duration_ms=wall, timed_out=timed_out, error=err,
    )  # fmt: skip


def run_tests_timed(
    req: TestRunRequest,
    *,
    repo_path: str | Path | None = None,
    hidden_dir: str | Path | None = None,
    reproducer_dir: str | Path | None = None,
    cfg: SandboxConfig = DEFAULT,
) -> tuple[TestRunResult, Timing]:
    """hidden_dir / reproducer_dir are roots holding one `<case_id>/` folder per case."""
    t0 = time.monotonic()

    def fail(msg: str) -> tuple[TestRunResult, Timing]:
        ms = int((time.monotonic() - t0) * 1000)
        return _result([], ms, False, "", msg[:500]), Timing(ms, 0)

    name = f"tf-sbx-{uuid.uuid4().hex[:12]}"
    hidden = req.suite == "hidden"
    try:
        if not _CASE_ID.match(req.case_id):
            return fail("invalid case_id")
        wt = resolve_dir(req.worktree_path, repo_path, "worktree")
        wd_rel = cfg.workdir_rel.strip("/")
        wd_host = (wt / wd_rel).resolve()
        if not wd_host.is_relative_to(wt) or not wd_host.is_dir():
            return fail(f"workdir not found in worktree: {wd_rel!r}")
        wd = f"/work/{wd_rel}".rstrip("/")
        mounts = _mount(wt, "/work")
        suite_dir, dst = None, ""
        if hidden:
            if hidden_dir is None:
                return fail("hidden suite requested but no hidden_dir configured")
            suite_dir = resolve_dir(str(Path(hidden_dir) / req.case_id), None, "hidden")
            dst = "/hidden"
        elif req.suite == "reproducer" and reproducer_dir is not None:
            suite_dir = resolve_dir(str(Path(reproducer_dir) / req.case_id), None, "reproducer")
            dst = "/reproducer"
        if suite_dir is not None:
            if suite_dir.is_relative_to(wt) or wt.is_relative_to(suite_dir):
                return fail("suite dir overlaps the model-visible worktree")
            mounts += _mount(suite_dir, dst)
        tag = ensure_image(cfg)
        pyp = f"{wd}:{wd}/src"
        with tempfile.TemporaryDirectory(prefix="tf-out-") as out:
            outp = Path(out)
            outp.chmod(0o777)  # scratch: the only writable bind mount
            argv = [
                *docker_run_args(cfg, name),
                *mounts,
                *_mount(outp, "/out", ro=False),
                "--workdir", wd, "-e", f"PYTHONPATH={pyp}", tag,
                *_pytest_args(req.suite, wd, suite_dir is not None),
            ]  # fmt: skip
            t1 = time.monotonic()
            oom = False
            try:
                code, out_text, timed_out = _run_container(argv, name, req.timeout_s)
                wall = int((time.monotonic() - t1) * 1000)
                if code not in (0, 1):
                    oom = (
                        docker("inspect", "-f", "{{.State.OOMKilled}}", name).stdout.strip()
                        == "true"
                    )
            finally:
                docker_cleanup(name)
            report = outp / "report.xml"
            xml = report.read_text("utf-8", "replace") if report.is_file() else None
    except (SandboxError, OSError, subprocess.SubprocessError) as e:
        docker_cleanup(name)
        return fail(str(e))

    shown = HIDDEN_WITHHELD if hidden else tail(out_text, cfg.stdout_cap)
    if timed_out:
        return _result([], wall, True, shown, None), Timing(wall, 0)
    if xml is None or code not in (0, 1, 2):
        why = "out of memory (OOM killed)" if oom else f"no test report (exit {code})"
        return _result([], wall, False, shown, why), Timing(wall, 0)
    try:
        tests, secs = parse_junit(xml)
    except Exception as e:  # malformed XML is a sandbox failure, never success
        return _result([], wall, False, shown, f"unparseable report: {e}"), Timing(wall, 0)
    err = None if tests else "no tests collected"
    return _result(tests, wall, False, shown, err), Timing(wall, int(secs * 1000))


def run_tests(req: TestRunRequest, **kw) -> TestRunResult:
    return run_tests_timed(req, **kw)[0]
