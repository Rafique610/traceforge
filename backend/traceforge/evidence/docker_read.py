"""Read-only Docker access through the socket proxy (TCP). Only GET calls are ever issued:
containers list/inspect/logs. The raw socket is never used and no write method is called here.
"""

from dataclasses import dataclass, field
from typing import Any

import docker
from docker.errors import DockerException

from traceforge.evidence.model import EvidenceConfig


@dataclass
class ContainerInfo:
    service: str
    name: str
    status: str  # running | exited | restarting | paused | created | dead
    health: str | None  # healthy | unhealthy | starting | None (no healthcheck)
    exit_code: int | None
    restart_count: int
    started_at: str | None
    env: dict[str, str] = field(default_factory=dict)  # RAW: must be redacted before use
    image: str = ""


def connect(cfg: EvidenceConfig) -> Any:
    return docker.DockerClient(base_url=cfg.docker_url, timeout=cfg.docker_timeout_s)


def _env(items: list[str] | None) -> dict[str, str]:
    out = {}
    for it in items or []:
        k, _, v = it.partition("=")
        out[k] = v
    return out


def inspect_service(client: Any, cfg: EvidenceConfig, service: str) -> ContainerInfo | None:
    """State of the compose service's container, or None when it is absent."""
    flt = {
        "label": [
            f"com.docker.compose.project={cfg.compose_project}",
            f"com.docker.compose.service={service}",
        ]
    }
    found = client.containers.list(all=True, filters=flt)
    if not found:
        return None
    a = found[0].attrs
    st = a.get("State", {})
    return ContainerInfo(
        service=service,
        name=found[0].name,
        status=st.get("Status", "unknown"),
        health=(st.get("Health") or {}).get("Status"),
        exit_code=st.get("ExitCode") if st.get("Status") != "running" else None,
        restart_count=a.get("RestartCount", 0),
        started_at=st.get("StartedAt"),
        env=_env(a.get("Config", {}).get("Env")),
        image=a.get("Config", {}).get("Image", ""),
    )


def read_logs(client: Any, cfg: EvidenceConfig, service: str) -> str:
    """Recent log text with Docker timestamps (bounded by tail and since)."""
    import time

    flt = {
        "label": [
            f"com.docker.compose.project={cfg.compose_project}",
            f"com.docker.compose.service={service}",
        ]
    }
    found = client.containers.list(all=True, filters=flt)
    if not found:
        return ""
    raw = found[0].logs(
        stdout=True,
        stderr=True,
        timestamps=True,
        tail=cfg.log_max_lines * 4,
        since=int(time.time()) - cfg.log_window_s,
    )
    return raw.decode("utf-8", "replace")


__all__ = ["ContainerInfo", "DockerException", "connect", "inspect_service", "read_logs"]
