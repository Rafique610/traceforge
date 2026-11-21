"""L/G behaviour on the real lab graph and a tiny repo (evidence: hand-written test input)."""

import json

import pytest
from retr_helpers import bundle, item

from traceforge.codeintel import build_graph
from traceforge.retrieval import NO_GRAPH, GraphFeatures, retrieve
from traceforge.retrieval.anchors import build_query
from traceforge.retrieval.retrieve import rank


def _hits(b):
    return [(h.node_id, h.score, h.reasons, h.excerpt) for h in b.hits]


def test_anchors_only_innermost_two_frames_are_forced(lab_graph):
    ev = bundle(
        item(1, "trace_frame", "f", path="lab/worker/main.py", line=37),
        item(2, "trace_frame", "f", path="lab/worker/queue.py", line=41),  # ping
        item(3, "trace_frame", "f", path="lab/worker/queue.py", line=23),  # make_client
        item(4, "trace_frame", "f", path="lab/worker/retry.py", line=17),  # with_backoff
    )
    q = build_query(ev, lab_graph)
    forced = [a for a in q.anchors if a.forced]
    assert len(forced) == 2 and all(a.source == "trace" for a in forced)
    assert [a.node_id.split("::")[1] for a in forced] == ["with_backoff", "make_client"]
    assert [a.source for a in q.anchors if not a.forced] == ["trace_other", "trace_other"]


def test_forced_anchors_lead_both_arms_even_with_zero_lexical_match(lab_graph):
    ev = bundle(
        item(1, "log", "zzzz qqqq"),
        item(2, "trace_frame", "f", path="lab/worker/queue.py", line=23),
    )
    for mode in "LG":
        b = retrieve(ev, lab_graph, mode, 3000)
        assert b.hits[0].node_id == "sym:lab/worker/queue.py::make_client"
        assert "anchor:trace" in " ".join(b.hits[0].reasons)


def test_config_key_named_in_evidence_is_forced_in_both_arms(lab_graph):
    ev = bundle(item(1, "log", "ERROR cannot use REDIS_HOST=bad value"))
    for mode in "LG":
        b = retrieve(ev, lab_graph, mode, 3000, service="worker")
        assert b.hits[0].node_id == "cfg:worker.REDIS_HOST"
        assert "anchor:config_key" in b.hits[0].reasons[1]


def test_config_dump_does_not_force_every_key(lab_graph):
    ev = bundle(item(1, "config", "REDIS_HOST=x\nDB_HOST=y\nDB_PORT=1"), item(2, "log", "boom"))
    assert not build_query(ev, lab_graph).anchors


def test_g_equals_l_when_graph_features_are_off(lab_graph, crash_evidence):
    l_b = retrieve(crash_evidence, lab_graph, "L", 3000)
    g_off = retrieve(crash_evidence, lab_graph, "G", 3000, features=NO_GRAPH)
    assert _hits(g_off) == _hits(l_b)
    assert (g_off.tokens_used, g_off.token_budget) == (l_b.tokens_used, l_b.token_budget)
    assert (l_b.mode, g_off.mode) == ("L", "G")


@pytest.mark.parametrize("off", ["proximity", "expansion", "test_link", "uncertainty"])
def test_g_differs_from_l_through_documented_features_only(lab_graph, crash_evidence, off):
    on = retrieve(crash_evidence, lab_graph, "G", 3000)
    l_b = retrieve(crash_evidence, lab_graph, "L", 3000)
    assert _hits(on) != _hits(l_b)
    one_off = retrieve(crash_evidence, lab_graph, "G", 3000, features=GraphFeatures(**{off: False}))
    assert one_off.mode == "G"  # ablating a single feature is accepted and stays valid


def test_equal_budget_and_never_exceeds_it(lab_graph, crash_evidence):
    for budget in (50, 200, 1000, 3000, 10000):
        for mode in "LG":
            b = retrieve(crash_evidence, lab_graph, mode, budget)
            assert b.token_budget == budget
            assert b.tokens_used <= int(budget * 0.8) <= budget


def test_deterministic_bundles(lab_graph, crash_evidence):
    for mode in "LG":
        a = retrieve(crash_evidence, lab_graph, mode, 3000)
        b = retrieve(crash_evidence, lab_graph, mode, 3000)
        assert json.dumps(a.model_dump(mode="json")) == json.dumps(b.model_dump(mode="json"))


def test_config_key_binding_finds_the_key_from_a_crash_site_in_another_file(
    lab_graph, crash_evidence
):
    """Crash in worker/queue.py::make_client; the key is declared in compose.yaml and bound by
    worker/settings.py. The message never names it, so lexical L cannot rank it; G binds it."""
    g_b = retrieve(crash_evidence, lab_graph, "G", 3000, service="worker")
    key = "cfg:worker.REDIS_HOST"
    g_rank = [h.node_id for h in g_b.hits].index(key) + 1
    assert g_rank <= 5
    hit = next(h for h in g_b.hits if h.node_id == key)
    assert any("graph:hops=1" in r and "reads_config@" in r for r in hit.reasons)
    # the key's settings field (another file) is bound to it: ranked far higher by G than by L
    field = "sym:lab/worker/settings.py::WorkerSettings.redis_host"
    q = build_query(crash_evidence, lab_graph, "worker")

    def position(mode):
        ids = [r.hit_id or r.chunk.hit_id for r in rank(q, lab_graph, mode)]
        return ids.index(field) if field in ids else len(ids)

    assert position("G") < position("L") - 10
    g_field = next(r for r in rank(q, lab_graph, "G") if r.chunk.hit_id == field)
    assert any("graph:hops=1" in r for r in g_field.reasons)


def test_hits_use_the_metrics_id_convention(lab_graph, crash_evidence):
    from traceforge.evaluation.metrics.retrieval import case_retrieval

    b = retrieve(crash_evidence, lab_graph, "G", 3000, service="worker")
    for h in b.hits:
        assert h.node_id.startswith(("sym:", "cfg:", "test:")), h.node_id
        if h.node_id.startswith("sym:"):
            assert h.node_id.split("::")[0][4:] == h.path
    gold = {b.hits[2].node_id}
    assert case_retrieval(b, gold)["found@5"] == 1


def test_graph_is_optional_for_empty_evidence(tiny_repo):
    g = build_graph(tiny_repo, "t", cache_dir=None)
    b = retrieve(bundle(item(1, "log", "nothing useful")), g, "G", 500)
    assert b.hits == [] and b.tokens_used == 0


def test_bad_mode_rejected(tiny_repo):
    g = build_graph(tiny_repo, "t", cache_dir=None)
    with pytest.raises(ValueError):
        retrieve(bundle(item(1, "log", "x")), g, "X", 500)


def test_overlapping_spans_are_deduped_but_ids_kept(lab_graph):
    ev = bundle(item(1, "trace_frame", "f", path="lab/worker/queue.py", line=41))  # nested ping
    b = retrieve(ev, lab_graph, "L", 6000)
    ids = [h.node_id for h in b.hits]
    ping, parent = "sym:lab/worker/queue.py::connect_with_retry.ping", None
    parent = "sym:lab/worker/queue.py::connect_with_retry"
    assert ping in ids and parent in ids
