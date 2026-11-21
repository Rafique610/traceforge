"""Collector configuration and small shared types. No env access here (Settings owns env)."""

from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

# Non-secret env keys whose values config diagnosis needs. fnmatch globs, case-insensitive.
DEFAULT_ENV_ALLOWLIST = (
    "*_HOST", "*_PORT", "*_NAME", "*_QUEUE", "*_POOL_SIZE", "MAX_RETRIES", "BACKOFF_BASE_S",
    "CONNECT_ATTEMPTS", "LOG_LEVEL", "APP_ENV",
)  # fmt: skip


@dataclass(frozen=True)
class EvidenceConfig:
    repo_root: Path = REPO_ROOT
    docker_url: str = "tcp://127.0.0.1:2375"  # read-only socket proxy, never the raw socket
    compose_project: str = "traceforge-lab"
    compose_file: str = "lab/compose.yaml"
    # service -> (container path prefix, repo path prefix)
    path_map: dict[str, tuple[str, str]] = field(
        default_factory=lambda: {
            "shop_api": ("/app/", "lab/shop_api/"),
            "worker": ("/app/worker/", "lab/worker/"),
        }
    )
    # service -> health probe URL (HTTP GET, read-only)
    probes: dict[str, str] = field(
        default_factory=lambda: {"shop_api": "http://127.0.0.1:8100/health"}
    )
    env_allowlist: tuple[str, ...] = DEFAULT_ENV_ALLOWLIST
    log_max_lines: int = 400
    log_max_bytes: int = 32 * 1024
    dependency_log_lines: int = 40  # tail for non-target services that are down/unhealthy
    log_window_s: int = 900
    block_max_lines: int = 25
    max_external_frames: int = 2  # per traceback, nearest the raise site
    probe_timeout_s: float = 3.0
    docker_timeout_s: int = 10
