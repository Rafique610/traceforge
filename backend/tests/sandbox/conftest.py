import shutil
import subprocess
from pathlib import Path

import pytest

FIX = Path(__file__).parent / "fixtures"
collect_ignore = ["fixtures"]  # fixture projects/probes run in the sandbox, not here


def pytest_configure(config):
    config.addinivalue_line("markers", "docker: needs a running Docker daemon (real containers)")


def docker_up() -> bool:
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


@pytest.fixture
def worktree(tmp_path: Path) -> Path:
    """Throwaway copy of the fixture project (the 'disposable worktree')."""
    wt = tmp_path / "wt"
    shutil.copytree(FIX / "proj", wt)
    return wt


@pytest.fixture
def hidden_root() -> Path:
    return FIX / "hidden"


def add_probe(wt: Path, name: str) -> None:
    """Put a security probe where the 'reproducer' suite will run it."""
    shutil.copy(FIX / "probes" / name, wt / "reproducer" / name)
