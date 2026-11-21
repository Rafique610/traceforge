# ruff: noqa: E501
"""Live check for runtime_dependency cases: stop the real dependency, observe the real symptom, restore.

Uses its OWN compose project (`tf-faultgen-live`) and a free host port, so a running lab stack is never
touched. Two observations per state (up / stopped): a raw RESP PING from the host to the published port,
and the lab's own `app.queue.OrderQueue` inside a throwaway container on the project network (non-root,
read-only, caps dropped, no Docker socket). Only `lab_redis` is supported.
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


def _app_probe() -> str:
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
            "DB_USER=probe",
            "-e",
            "DB_PASSWORD=probe",
            "-e",
            "REDIS_HOST=lab_redis",
            "--entrypoint",
            "python",
            IMAGE,
            "-c",
            PROBE,
        ],
        timeout=60,
    )
    return p.stdout.strip() or p.stderr.strip()[-200:]


def live_runtime_check(stop: list[str], lab: Path) -> list[str]:
    """Return a list of problems (empty = symptom observed when stopped, healthy when restored)."""
    if stop != ["lab_redis"]:
        return [f"live check supports only ['lab_redis'], got {stop}"]
    if _sh(["docker", "image", "inspect", IMAGE]).returncode != 0:
        return [f"image {IMAGE} not built (task lab:build)"]
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
    try:
        up = _sh([*dc, "up", "-d", "--wait", "lab_redis"], env)
        if up.returncode != 0:
            return [f"could not start lab_redis: {up.stderr.strip()[-200:]}"]
        if (r := _ping(port)) != "+PONG":
            problems.append(f"healthy broker did not answer PING: {r}")
        if (r := _app_probe()) != "ENQUEUE_OK":
            problems.append(f"healthy: expected ENQUEUE_OK, got {r}")
        _sh([*dc, "stop", "lab_redis"], env)
        if (r := _ping(port)) != "refused":
            problems.append(f"stopped broker: expected connection refused, got {r}")
        if not (r := _app_probe()).startswith("ENQUEUE_FAILED"):
            problems.append(f"stopped: expected ENQUEUE_FAILED, got {r}")
        _sh([*dc, "start", "lab_redis"], env)
        _sh([*dc, "up", "-d", "--wait", "lab_redis"], env)
        if (r := _ping(port)) != "+PONG":
            problems.append(f"restored broker did not answer PING: {r}")
    finally:
        _sh([*dc, "down", "--remove-orphans"], env)  # no -v: never touches volumes
    return problems
