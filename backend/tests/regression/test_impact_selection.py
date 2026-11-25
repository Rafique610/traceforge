# ruff: noqa: E501
import json
import shutil
from pathlib import Path

import pytest

from traceforge.codeintel import build_graph
from traceforge.regression import (
    LIMITATION,
    GraphImpactProvider,
    ImpactProvider,
    get_impact_provider,
    register_impact_provider,
    select_tests,
)
from traceforge.regression.impact import ImpactReport

LAB = Path(__file__).resolve().parents[3] / "lab"
HIDDEN = "shop_api/tests/test_pricing_rules.py"


@pytest.fixture(scope="module")
def lab_tests():
    g = build_graph(LAB, "lab", cache_dir=None)
    return [n[5:] for n, d in g.nx.nodes(data=True) if d["kind"] == "test"]


@pytest.fixture(scope="module")
def lab_report(lab_tests):
    vis = [t for t in lab_tests if not t.startswith(HIDDEN)]
    return GraphImpactProvider().analyse(
        LAB, LAB, visible_tests=vis, hidden_paths=[HIDDEN], seeds=["cfg:REDIS_HOST"]
    ), vis


def test_protocol_and_registry():
    p = get_impact_provider("graph")
    assert isinstance(p, ImpactProvider) and p.name == "graph"
    s15 = get_impact_provider("s15")  # the P5-S15 provider now exists (traceforge.analysis)
    assert isinstance(s15, ImpactProvider)
    with pytest.raises(KeyError):
        get_impact_provider("no-such-provider")
    register_impact_provider("dummy", GraphImpactProvider)
    assert get_impact_provider("dummy").name == "graph"


def test_lab_config_consumers(lab_report):
    r, _ = lab_report
    assert r.limitation == LIMITATION and r.verify()
    consumers = {c.consumer for c in r.config_consumers}
    assert "func:shop_api/app/queue.py::get_client" in consumers
    assert "func:worker/main.py::main" in consumers
    assert all(c.config_key == "cfg:REDIS_HOST" for c in r.config_consumers)
    assert any(f.code == "config_key_read_elsewhere" for f in r.risk_flags)
    assert {d.evidence_class for d in r.direct_dependants + r.transitive_dependants} <= {
        "static",
        "inferred",
        "unknown",
        "observed",
    }
    assert all(
        d.depth <= 3 and d.path[0] == "cfg:REDIS_HOST"
        for d in r.direct_dependants + r.transitive_dependants
    )
    assert r.transitive_dependants and r.related_tests
    assert r.related_tests[0].rank == 1 and r.related_tests[0].direct


def test_deterministic_hash_and_json(lab_tests):
    vis = [t for t in lab_tests if not t.startswith(HIDDEN)]
    a = GraphImpactProvider().analyse(
        LAB, LAB, visible_tests=vis, hidden_paths=[HIDDEN], seeds=["cfg:REDIS_HOST"]
    )
    b = GraphImpactProvider().analyse(
        LAB, LAB, visible_tests=vis, hidden_paths=[HIDDEN], seeds=["cfg:REDIS_HOST"]
    )
    assert a.canonical_json() == b.canonical_json() and a.impact_sha256 == b.impact_sha256
    assert select_tests(a, vis).ids == select_tests(b, vis).ids
    tampered = a.model_copy(update={"limitation": "x"})
    assert not tampered.verify()


def test_selection_order_and_reason(lab_report):
    r, vis = lab_report
    sel = select_tests(r, vis)
    assert sel.ids and len(set(sel.ids)) == len(sel.ids)
    depths = [next(t.depth for t in r.related_tests if t.test_id == i) for i in sel.ids]
    assert depths == sorted(depths)
    assert all(t.reason.startswith(("direct", "transitive")) for t in sel.tests)
    assert select_tests(r, vis, limit=2).ids == sel.ids[:2]
    assert select_tests(ImpactReport(), vis).fallback == "full_suite"


def test_hidden_paths_never_selected(lab_tests):
    """Hidden file is listed as hidden: it is absent from report, selection and JSON, even when the
    caller wrongly includes its ids among the visible list."""
    hidden_ids = [t for t in lab_tests if t.startswith(HIDDEN)]
    assert hidden_ids
    r = GraphImpactProvider().analyse(
        LAB, LAB, visible_tests=lab_tests, hidden_paths=[HIDDEN],
        seeds=["cfg:REDIS_HOST", "func:shop_api/app/coupons.py::apply_discount"],
    )  # fmt: skip
    blob = r.canonical_json()
    assert HIDDEN not in blob and "test_pricing_rules" not in blob
    sel = select_tests(r, lab_tests)
    assert not any(i.startswith(HIDDEN) for i in sel.ids)
    # without the hidden marker the same ids WOULD be reachable: proves the filter does the work
    r2 = GraphImpactProvider().analyse(
        LAB, LAB, visible_tests=lab_tests, hidden_paths=[],
        seeds=["func:shop_api/app/coupons.py::apply_discount"],
    )  # fmt: skip
    assert "test_pricing_rules" in r2.canonical_json()


def test_hidden_dir_pattern_and_only_visible_selectable(lab_tests, tmp_path):
    vis_only = ["shop_api/tests/test_settings.py::test_defaults"]
    r = GraphImpactProvider().analyse(
        LAB, LAB, visible_tests=vis_only, hidden_paths=["worker/tests"], seeds=["cfg:REDIS_HOST"]
    )
    assert {t.test_id for t in r.related_tests} <= set(vis_only)
    assert not any("worker/tests" in json.dumps(x.model_dump()) for x in r.related_tests)


def test_changed_symbol_flags_on_small_repo(tmp_path):
    base = tmp_path / "b"
    (base / "tests").mkdir(parents=True)
    (base / "m.py").write_text(
        "def f(a):\n    return a\n\n\ndef g(x):\n    return f(x)\n\n\ndef h():\n    return g(1)\n"
    )
    (base / "tests" / "test_m.py").write_text(
        "from m import h\n\n\ndef test_h():\n    assert h() == 1\n"
    )
    new = tmp_path / "n"
    shutil.copytree(base, new)
    (new / "m.py").write_text(
        "def f(a, b):\n    return a\n\n\ndef g(x):\n    return f(x, 1)\n\n\ndef h():\n    return g(1)\n"
    )
    r = GraphImpactProvider().analyse(base, new, visible_tests=["tests/test_m.py::test_h"])
    assert [m.change for m in r.modified_symbols if m.id.endswith("::f")] == ["signature"]
    assert (
        any(d.id.endswith("::g") and d.breaking for d in r.direct_dependants) or r.direct_dependants
    )
    assert any(n.reason.startswith("contract changes") for n in r.not_analysable)
    assert r.related_tests and r.related_tests[0].test_id == "tests/test_m.py::test_h"
