# ruff: noqa: E501
"""Live check for runtime_dependency cases: stop the real dependency, observe the real symptom, restore.

Uses its OWN compose project (`tf-faultgen-live`) and a free host port, so a running lab stack is never
touched. Two observations per state (up / stopped): a raw RESP PING from the host to the published port,
and the lab's own `app.queue.OrderQueue` inside a throwaway container on the project network (non-root,
read-only, caps dropped, no Docker socket). Supported: `lab_redis` (raw PING + enqueue) and `lab_db`
(the lab engine runs `SELECT 1`; credentials reach the probe through a temporary env file, never argv).
"""

import socket
import subprocess
from pathlib import Path

PROJECT = "tf-faultgen-live"
IMAGE = "traceforge-lab/shop_api:dev"
PROBE = (
    "from decimal import Decimal\n"
    "from app.queue import OrderQueue\n"
    "try:\n"
    "    OrderQueue().enqueue_confirmation(1, Decimal('1.00')); print('ENQUEUE_OK')\n"
    "except Exception as e:\n"
    "    print('ENQUEUE_FAILED', type(e).__name__)\n"
)
PROBE_DB = (
    "from sqlalchemy import text\n"
    "from app.db import get_engine\n"
    "try:\n"
    "    with get_engine().connect() as c:\n"
    "        c.execute(text('SELECT 1'))\n"
    "    print('DB_OK')\n"
    "except Exception as e:\n"
    "    print('DB_FAILED', type(e).__name__)\n"
)
CHECKS = {
    "lab_redis": (PROBE, "ENQUEUE_OK", "ENQUEUE_FAILED"),
    "lab_db": (PROBE_DB, "DB_OK", "DB_FAILED"),
}


def _sh(
    args: list[str], env: dict | None = None, timeout: int = 180
) -> subprocess.CompletedProcess:
    import os

    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**os.environ, **(env or {})},
        check=False,
    )


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _ping(port: int) -> str:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=3) as s:
            s.sendall(b"*1\r\n$4\r\nPING\r\n")
            return s.recv(16).decode().strip()
    except ConnectionRefusedError:
        return "refused"
    except OSError as e:
        return f"error:{type(e).__name__}"


def _app_probe(code: str = PROBE, env_file: str | None = None) -> str:
    # -e would override --env-file, so the placeholder DB credentials are only set without one
    extra = (
        ["--env-file", env_file] if env_file else ["-e", "DB_USER=probe", "-e", "DB_PASSWORD=probe"]
    )
    p = _sh(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            f"{PROJECT}_default",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--user",
            "10001",
            "--memory",
            "128m",
            "-e",
            "REDIS_HOST=lab_redis",
            *extra,
            "--entrypoint",
            "python",
            IMAGE,
            "-c",
            code,
        ],
        timeout=60,
    )
    return p.stdout.strip() or p.stderr.strip()[-200:]


def _db_env_file(lab: Path, tmp: Path) -> str:
    """Map lab/.env LAB_DB_* to the DB_* names the app reads, in a private temp file."""
    lines = (lab / ".env").read_text("utf-8").splitlines()
    vals = dict(ln.split("=", 1) for ln in lines if "=" in ln and not ln.startswith("#"))
    body = "".join(
        f"DB_{k}={vals.get('LAB_DB_' + k, '').strip()}\n" for k in ("USER", "PASSWORD", "NAME")
    )
    path = tmp / "db.env"
    path.write_text(body + "DB_HOST=lab_db\n", encoding="utf-8")
    return str(path)


def live_runtime_check(stop: list[str], lab: Path) -> list[str]:
    """Return a list of problems (empty = symptom observed when stopped, healthy when restored)."""
    if len(stop) != 1 or stop[0] not in CHECKS:
        return [f"live check supports one of {sorted(CHECKS)}, got {stop}"]
    svc = stop[0]
    code, ok, failed = CHECKS[svc]
    if _sh(["docker", "image", "inspect", IMAGE]).returncode != 0:
        return [f"image {IMAGE} not built (task lab:build)"]
    import tempfile

    port = _free_port()
    dc = [
        "docker",
        "compose",
        "-p",
        PROJECT,
        "-f",
        str(lab / "compose.yaml"),
        "--env-file",
        str(lab / ".env"),
    ]
    env = {"LAB_REDIS_PORT": str(port)}
    problems: list[str] = []
    with tempfile.TemporaryDirectory(prefix="tf-live-") as tmp:
        env_file = _db_env_file(lab, Path(tmp)) if svc == "lab_db" else None
        try:
            up = _sh([*dc, "up", "-d", "--wait", svc], env)
            if up.returncode != 0:
                return [f"could not start {svc}: {up.stderr.strip()[-200:]}"]
            if svc == "lab_redis" and (r := _ping(port)) != "+PONG":
                problems.append(f"healthy broker did not answer PING: {r}")
            if (r := _app_probe(code, env_file)) != ok:
                problems.append(f"healthy: expected {ok}, got {r}")
            _sh([*dc, "stop", svc], env)
            if svc == "lab_redis" and (r := _ping(port)) != "refused":
                problems.append(f"stopped broker: expected connection refused, got {r}")
            if not (r := _app_probe(code, env_file)).startswith(failed):
                problems.append(f"stopped: expected {failed}, got {r}")
            _sh([*dc, "start", svc], env)
            _sh([*dc, "up", "-d", "--wait", svc], env)
            if (r := _app_probe(code, env_file)) != ok:
                problems.append(f"restored: expected {ok}, got {r}")
        finally:
            _sh([*dc, "down", "--remove-orphans"], env)  # no -v: never touches volumes
    return problems
