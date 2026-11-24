# ruff: noqa: E501
"""Configuration faults: a wrong computed value whose symptom names no setting.

The failing endpoint's handler reads settings through `quote`; the G arm offers those settings
(symptom_config anchors) and binds a config key to its settings field beyond the 2-hop limit.
L never sees these anchors. Pristine lab tree: no faulty line is needed.
"""

import pytest
from retr_helpers import bundle, item

from traceforge.agent import symptom
from traceforge.contracts.test_run import TestOutcome, TestRunResult
from traceforge.retrieval import GraphFeatures
from traceforge.retrieval.anchors import build_query, symptom_anchors
from traceforge.retrieval.retrieve import rank

OUT = (
    "F\n=== FAILURES ===\n___ test_price_1 ___\n"
    "/reproducer/test_symptom.py:7: in test_price_1\n"
    "    assert observe_price(client, session, [('7.45', 1)], 'staff50') == [200, '11.10']\n"
    "E   AssertionError: assert [200, '9.35'] == [200, '11.10']\n"
    "--- Captured stderr call ---\n"
    'INFO httpx HTTP Request: GET http://testserver/orders/1/quote?coupon=staff50 "HTTP/1.1 200 OK"\n'
)


@pytest.fixture
def ev():
    r = TestRunResult(
        passed=0,
        failed=1,
        tests=[TestOutcome(id="test_symptom.py::test_price_1", outcome="failed")],
        stdout_tail=OUT,
        duration_ms=1,
        timed_out=False,
    )
    base = bundle(item(1, "health", "container tf-1-shop_api-1: running (health: healthy)"))
    return symptom.with_symptom(base, symptom.build_symptom({"reproducer": r}))


def test_g_offers_the_settings_read_on_the_failing_path_l_does_not(lab_graph, ev):
    q = build_query(ev, lab_graph, "shop_api")
    cfg = [a for a in q.graph_anchors if a.source == "symptom_config"]
    fields = {a.node_id.rsplit("::", 1)[-1] for a in cfg}
    assert {"Settings.max_discount_pct", "Settings.tax_rate", "Settings.shipping_fee"} <= fields
    assert not [a for a in q.anchors if a.source == "symptom_config"]  # shared anchors: none
    assert len(cfg) <= 6
    # a setting whose words occur in the symptom (coupon, via the endpoint query) comes first
    assert {a.node_id.rsplit("::", 1)[-1] for a in cfg[:2]} == {
        "Settings.coupon_codes",
        "Settings.coupons_valid_until",
    }
    ids_l = [r.chunk.hit_id for r in rank(q, lab_graph, "L")]
    ids_g = [r.chunk.hit_id for r in rank(q, lab_graph, "G")]
    gold = "sym:lab/shop_api/app/settings.py::Settings.max_discount_pct"
    assert gold in ids_g and gold not in ids_l[:20]


def test_symptom_config_anchors_are_unforced_and_weaker_than_route_anchors(lab_graph, ev):
    view = symptom.symptom_view(ev)
    a = symptom_anchors(lab_graph, view, "EV-0002")
    route = next(x for x in a if x.source == "symptom_route")
    cfg = next(x for x in a if x.source == "symptom_config")
    assert not cfg.forced and cfg.strength < route.strength


def test_no_graph_features_means_no_symptom_config(lab_graph, ev):
    q = build_query(ev, lab_graph, "shop_api")
    off = GraphFeatures(False, False, False, False, False, False, False)
    assert [r.chunk.hit_id for r in rank(q, lab_graph, "G", off)] == [
        r.chunk.hit_id for r in rank(q, lab_graph, "L")
    ]


def test_config_key_binds_to_its_field_past_the_hop_limit(lab_graph, ev):
    """handler -> quote -> key is 2 hops; the settings field bound to the key is still reached."""
    from traceforge.retrieval.anchors import Anchor
    from traceforge.retrieval.graph_ranker import GraphFeatures as GF
    from traceforge.retrieval.graph_ranker import graph_scores

    route = next(
        n
        for n, d in lab_graph.nx.nodes(data=True)
        if n.endswith("routes/orders.py::get_order_quote")
    )
    info = graph_scores(lab_graph, [Anchor(route, "symptom_route", 0, "EV-0002", False)], GF())
    assert any(n.endswith("Settings.max_discount_pct") for n in info)
