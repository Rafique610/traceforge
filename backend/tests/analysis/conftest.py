# ruff: noqa: E501
"""Fixtures for tests/analysis."""

from pathlib import Path

import pytest
from rc_helpers import FILES, write_tree

from traceforge.codeintel import build_graph


@pytest.fixture
def tree(tmp_path: Path):
    return write_tree(tmp_path / "base", FILES)


@pytest.fixture
def graph(tree):
    return build_graph(tree, "t", cache_dir=None)
