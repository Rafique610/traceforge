# ruff: noqa: E501
"""Pipeline v5 retrieval: symptom-aware lexical query, symptom-derived graph anchors, routes.

Uses the real lab graph (conftest) and hand-written symptom evidence in the shape the pipeline
creates. No model is involved. The lab source here is the pristine tree: retrieval must not need
the faulty line, only the symptom and the graph.
"""

import pytest
from retr_helpers import bundle, item

from traceforge.agent import symptom
from traceforge.contracts.test_run import TestOutcome, TestRunResult
from traceforge.retrieval import NO_GRAPH, GraphFeatures, retrieve
from traceforge.retrieval.anchors import build_query, symptom_anchors, symptom_terms
from traceforge.retrieval.compare import compare, evaluate
from traceforge.retrieval.retrieve import rank
from traceforge.retrieval.routes import match_routes, route_index

TEST = (
    "shop_api/tests/test_pricing_rules.py::test_coupon_is_capped_and_unknown_or_expired_is_refused"
)
REPRO_OUT = (
    "F\n=== FAILURES ===\n___ test_price_1 ___\n"
    "/reproducer/test_symptom.py:7: in test_price_1\n"
    "    assert observe_price(client, session, [('7.45', 1)], 'staff50') == [200, '11.10']\n"
    "E   AssertionError: assert [200, '9.35'] == [200, '11.10']\n"
    "--- Captured stderr call ---\n"
    'INFO httpx HTTP Request: GET http://testserver/orders/1/quote?coupon=staff50 "HTTP/1.1 200 OK"\n'
)


def _run(out, ids, passed=0):
    return TestRunResult(
        passed=passed,
        failed=len(ids),
        tests=[TestOutcome(id=i, outcome="failed") for i in ids],
        stdout_tail=out,
        duration_ms=1,
        timed_out=False,
    )


@pytest.fixture
def base():
    return bundle(
        item(1, "health", "container tf-1-shop_api-1: running (health: healthy)", "shop_api")
    )


@pytest.fixture
def with_sym(base):
    sym = symptom.build_symptom(
        {
            "reproducer": _run(REPRO_OUT, ["test_symptom.py::test_price_1"]),
            "visible": _run("", [TEST], passed=34),
        }
    )
    return symptom.with_symptom(base, sym)


def _view(ev):
    return symptom.symptom_view(ev)


# --- lexical ----------------------------------------------------------------------------------


def test_symptom_terms_carry_endpoint_inputs_and_test_names_without_boilerplate(with_sym):
    terms = {t.lower() for t in symptom_terms(_view(with_sym))}
    assert {"orders", "quote", "coupon", "staff50", "observe_price"} <= terms
    assert not terms & {"symptom", "visible", "reproducer", "failing", "compared"}
    assert not any(t.isdigit() for t in terms)


def test_query_is_no_longer_only_the_service_name(lab_graph, base, with_sym):
    plain = build_query(base, lab_graph, "shop_api")
    rich = build_query(with_sym, lab_graph, "shop_api")
    assert set(plain.terms) <= {"shop", "api", "shop_api"}  # the confirmed v4 behaviour
    assert {"coupon", "quote", "staff50"} <= set(rich.terms)


def test_without_a_symptom_the_query_and_anchors_are_unchanged(lab_graph, base):
    q = build_query(base, lab_graph, "shop_api")
    assert q.graph_anchors == [] and q.anchors == []


# --- graph anchors ----------------------------------------------------------------------------


def test_failing_visible_test_anchors_the_code_it_covers(lab_graph, with_sym):
    anchors = symptom_anchors(lab_graph, _view(with_sym), "EV-0002")
    covered = {a.node_id.rsplit("::", 1)[-1] for a in anchors if a.source == "symptom_test"}
    assert "discount_pct" in covered and all(a.source.startswith("symptom") for a in anchors)
    assert all(not a.forced and a.weight > 0 for a in anchors)


def test_request_is_resolved_to_its_handler_by_route(lab_graph, with_sym):
    anchors = symptom_anchors(lab_graph, _view(with_sym), "EV-0002")
    routes = [a for a in anchors if a.source == "symptom_route"]
    assert [a.node_id.rsplit("::", 1)[-1] for a in routes] == ["get_order_quote"]


def test_route_matching_is_by_method_and_template_not_by_name(lab_graph):
    assert (
        match_routes(lab_graph, "GET", "/orders/7/quote?x=1")[0].template
        == "/orders/{order_id}/quote"
    )
    assert match_routes(lab_graph, "POST", "/orders/7/quote") == []  # wrong method
    assert match_routes(lab_graph, "GET", "/nothing/here") == []
    # a literal segment beats a parameter of the same arity
    assert (
        match_routes(lab_graph, "GET", "/products/low-stock")[0].template == "/products/low-stock"
    )
    assert any(r.template == "/health" for r in route_index(lab_graph))


def test_anchor_count_is_bounded(lab_graph):
    many = bundle(item(1, "health", "ok", "shop_api"))
    sym = symptom.build_symptom(
        {
            "visible": _run(
                "", [f"shop_api/tests/test_pricing_rules.py::test_x{i}" for i in range(6)], passed=1
            )
        }
    )
    ev = symptom.with_symptom(many, sym)
    assert len(symptom_anchors(lab_graph, _view(ev), "EV-0002")) <= 12


# --- L vs G stay separable --------------------------------------------------------------------


def test_lexical_arm_ignores_the_graph_only_anchors(lab_graph, with_sym):
    q = build_query(with_sym, lab_graph, "shop_api")
    assert q.graph_anchors  # present for G
    stripped = type(q)(q.service, q.terms, q.grep_terms, q.anchors, q.trace_nodes, [])
    L1 = [(r.chunk.hit_id, round(r.score, 6)) for r in rank(q, lab_graph, "L")]
    L2 = [(r.chunk.hit_id, round(r.score, 6)) for r in rank(stripped, lab_graph, "L")]
    assert L1 == L2


def test_no_graph_features_makes_g_equal_l_even_with_a_symptom(lab_graph, with_sym):
    q = build_query(with_sym, lab_graph, "shop_api")
    g = [(r.chunk.hit_id, round(r.score, 6)) for r in rank(q, lab_graph, "G", NO_GRAPH)]
    lex = [(r.chunk.hit_id, round(r.score, 6)) for r in rank(q, lab_graph, "L")]
    assert g == lex
    off = GraphFeatures(symptom_anchors=False)
    assert rank(q, lab_graph, "G", off) != [] and NO_GRAPH.any is False


def test_g_adds_graph_evidence_that_l_does_not_have(lab_graph, with_sym):
    rec = compare(
        with_sym, lambda e, g, m, b: retrieve(e, lab_graph, m, b, service="shop_api"), 3000
    )
    assert rec["only_G"] or rec["only_L"]  # the arms really differ
    assert any(r["graph_reason"] or r["symptom_anchor"] for r in rec["G"])
    assert not any(r["symptom_anchor"] for r in rec["L"])  # L never uses symptom anchors
    assert rec["overlap"] + len(rec["only_L"]) == len(rec["L"])
    assert set(rec["union_ids"]) == {r["id"] for r in rec["L"]} | {r["id"] for r in rec["G"]}


def test_g_does_not_wander_into_unrelated_services(lab_graph, with_sym):
    hits = retrieve(with_sym, lab_graph, "G", 3000, service="shop_api").hits[:10]
    assert hits and not any(h.path.startswith("lab/worker/") for h in hits)


def test_both_arms_find_the_faulty_function_only_with_the_symptom(lab_graph, base, with_sym):
    gold = {"lab/shop_api/app/coupons.py::discount_pct"}
    for mode in "LG":
        plain = retrieve(base, lab_graph, mode, 3000, service="shop_api")
        rich = retrieve(with_sym, lab_graph, mode, 3000, service="shop_api")
        ids = lambda b: {f"{h.path}::{h.node_id.rsplit('::', 1)[-1]}" for h in b.hits}  # noqa: E731
        assert not gold & ids(plain), mode  # v4 query: service name only
        assert gold & ids(rich), mode


def test_comparison_record_has_no_gold_and_evaluate_scores_it_offline(lab_graph, with_sym):
    rec = compare(
        with_sym, lambda e, g, m, b: retrieve(e, lab_graph, m, b, service="shop_api"), 3000
    )
    assert "gold" not in str(rec).lower()
    scored = evaluate(rec, {"lab/shop_api/app/coupons.py::discount_pct"})
    assert scored["gold_rank_L"] and scored["gold_rank_G"]
    assert {"relevant", "irrelevant", "only_G_relevant"} <= set(rec)
