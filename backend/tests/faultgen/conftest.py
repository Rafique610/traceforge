from pathlib import Path

import pytest
from fg_paths import LAB

from traceforge.faultgen import lab_tree
from traceforge.faultgen.generate import write_case, write_manifest
from traceforge.faultgen.model import build_case
from traceforge.faultgen.seeds import seed_drafts


@pytest.fixture(scope="session")
def builts():
    return [build_case(d, LAB) for d in seed_drafts(LAB)]


@pytest.fixture
def datasets(tmp_path: Path, builts) -> Path:
    for b in builts:
        write_case(b, tmp_path)
    write_manifest(builts, tmp_path / "manifests" / "dev.json")
    return tmp_path


@pytest.fixture
def lab_copy(tmp_path: Path) -> Path:
    """A throwaway copy of the lab (root/lab) for drift tests."""
    root = tmp_path / "labroot"
    lab_tree.copy_lab(LAB, root)
    return root / "lab"
