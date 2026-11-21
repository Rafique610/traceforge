import shutil
from pathlib import Path

import pytest

from traceforge.codeintel import build_graph

collect_ignore = ["fixture_repo"]
FIXTURE = Path(__file__).parent / "fixture_repo"


@pytest.fixture
def repo(tmp_path):
    """A writable copy of the fixture repo (tests may edit it)."""
    return _copy(tmp_path / "repo")


def _copy(dst: Path) -> Path:
    shutil.copytree(FIXTURE, dst)
    # written here so linters/pytest never see a deliberately invalid .py file
    (dst / "svc" / "broken.py").write_text("def broken(:\n    pass\n")
    return dst


@pytest.fixture(scope="module")
def graph(tmp_path_factory):
    return build_graph(_copy(tmp_path_factory.mktemp("fx") / "repo"), "fixture-sha", cache_dir=None)


def edges(g, etype, reverse=False):
    return [
        (u, v, d)
        for u, v, d in g.nx.edges(data=True)
        if d["type"] == etype and d["reverse"] == reverse
    ]


def has_edge(g, etype, u, v):
    return any(a == u and b == v for a, b, _ in edges(g, etype))
