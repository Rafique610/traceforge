"""Warm test image: built once per dependency hash, reused for every run (D30)."""

import hashlib
import subprocess
import threading
from pathlib import Path

from traceforge.sandbox.config import DEFAULT, SandboxConfig

DOCKERFILE = Path(__file__).with_name("Dockerfile")
_lock = threading.Lock()
_ready: set[str] = set()


class SandboxError(RuntimeError):
    pass


def docker(*args: str, timeout: int = 60, stdin: str | None = None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["docker", *args],
            input=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise SandboxError(f"docker {args[0]} failed: {e}") from e


def image_tag(cfg: SandboxConfig) -> str:
    h = hashlib.sha256((DOCKERFILE.read_text("utf-8") + "\0" + cfg.requirements).encode())
    return f"{cfg.image_repo}:{h.hexdigest()[:12]}"


def ensure_image(cfg: SandboxConfig = DEFAULT, build_timeout: int = 600) -> str:
    """Return the image tag, building it only if absent. Build has network; runs never do."""
    tag = image_tag(cfg)
    with _lock:
        if tag in _ready:
            return tag
        if docker("image", "inspect", tag).returncode != 0:
            p = docker(
                "build", "-t", tag, "--build-arg", f"REQS={cfg.requirements}", "-",
                timeout=build_timeout, stdin=DOCKERFILE.read_text("utf-8"),
            )  # fmt: skip
            if p.returncode != 0:
                raise SandboxError(f"image build failed: {p.stderr[-500:]}")
        _ready.add(tag)
    return tag
