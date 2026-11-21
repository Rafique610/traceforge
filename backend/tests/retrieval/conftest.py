"""Fixtures. Evidence bundles here are hand-written UNIT-TEST inputs (not real collector output)."""

import shutil
from pathlib import Path

import pytest
from retr_helpers import bundle, item

from traceforge.codeintel import build_graph
from traceforge.contracts.evidence import EvidenceBundle

LAB = Path(__file__).resolve().parents[3] / "lab"


@pytest.fixture(scope="session")
def lab_tree(tmp_path_factory) -> Path:
    """A copy of the real lab under `<root>/lab` (the layout manifests use)."""
    if not LAB.is_dir():
        pytest.skip("lab/ not present")
    root = tmp_path_factory.mktemp("tree")
    shutil.copytree(LAB, root / "lab", ignore=shutil.ignore_patterns("__pycache__", ".env"))
    return root


@pytest.fixture(scope="session")
def lab_graph(lab_tree):
    return build_graph(lab_tree, cache_dir=None)


@pytest.fixture
def crash_evidence() -> EvidenceBundle:
    """Worker crash in make_client; the message names neither the key nor the host."""
    return bundle(
        item(1, "log", "ERROR worker.queue connect failed: [Errno -2] Name or service not known"),
        item(2, "trace_frame", 'File "/app/main.py", line 37, in main\n    c = connect(s)',
             path="lab/worker/main.py", line=37),
        item(3, "trace_frame", 'File "/app/queue.py", line 23, in make_client',
             path="lab/worker/queue.py", line=23),
    )  # fmt: skip


@pytest.fixture
def tiny_repo(tmp_path) -> Path:
    """Three small modules with a distinctive word each, for deterministic BM25 checks."""
    (tmp_path / "app").mkdir()
    (tmp_path / "app/__init__.py").write_text("")
    (tmp_path / "app/orders.py").write_text(
        "def parse_quantity(raw):\n    return int(raw)\n\n\n"
        "def charge_card(card):\n    return card.charge()\n\n\n"
        "def ship_parcel(order):\n    return order.parcel\n"
    )
    (tmp_path / "app/inventory.py").write_text(
        "from app.orders import parse_quantity\n\n\n"
        "def reserve_stock(item, raw):\n    return parse_quantity(raw) <= item.stock\n"
    )
    return tmp_path
