"""Sandbox limits and image settings (plain defaults; no env access here)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SandboxConfig:
    requirements: str = "pytest==8.3.4"  # space-separated pip specs baked into the image
    base_image: str = "python:3.12-slim"  # BugsInPy cases need their own Python (P5-S05)
    memory: str = "512m"
    cpus: str = "1"
    pids_limit: int = 128
    tmpfs_size: str = "64m"
    user: str = "10001:10001"
    image_repo: str = "traceforge-sandbox"
    workdir_rel: str = ""  # service dir inside the worktree, e.g. "lab/shop_api"
    stdout_cap: int = 4096


DEFAULT = SandboxConfig()
