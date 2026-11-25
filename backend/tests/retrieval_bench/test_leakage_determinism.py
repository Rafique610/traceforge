# ruff: noqa: E501
"""Gold never reaches a retriever; rankings are deterministic; seeds fixed."""

import json
from pathlib import Path

import pytest

from traceforge.retrieval_bench import registry
from traceforge.retrieval_bench.dev_loader import load_dev
from traceforge.retrieval_bench.repo_ctx import build_context
from traceforge.retrieval_bench.runner import _check_clean, compare, run, summarize
from traceforge.retrieval_bench.suite import Workload, assert_no_forbidden_paths
from traceforge.retrieval_bench.types import BenchQuery, QueryText

GOLD = "sym:pkg/billing.py::compute_tax"


def _workload(ctx) -> Workload:
    qs = [
        BenchQuery("q1", "exact_identifier", ctx.make_query("q1", "compute_tax rate amount"),
                   frozenset({GOLD})),
        BenchQuery("q2", "symptom_no_identifier", ctx.make_query("q2", "broker down connection error"),
                   frozenset({"sym:pkg/queue.py::JobQueue.push"})),
    ]  # fmt: skip
    return Workload("tiny", ctx, qs)


def test_retrievers_only_see_query_text_without_gold(tiny_ctx):
    seen = []

    @registry.register("RET-SPY")
    def spy(ctx, query_text, k):
        seen.append(query_text)
        return [c.hit_id for c in ctx.corpus.chunks][:k]

    try:
        w = _workload(tiny_ctx)
        run([w], ["RET-SPY"], repeats=1, measure_memory=False)
        assert seen and all(type(q) is QueryText for q in seen)
        gold_ids = {g for q in w.queries for g in q.gold}
        for q in seen:
            assert not (set(vars(q)) & {"gold", "qtype", "labels", "relevant"})
            assert all(g not in str(q) and g not in repr(vars(q)) for g in gold_ids)
    finally:
        registry.unregister("RET-SPY")


def test_gold_in_query_text_is_rejected(tiny_ctx):
    bad = BenchQuery("q", "t", tiny_ctx.make_query("q", f"look at {GOLD}"), frozenset({GOLD}))
    with pytest.raises(AssertionError):
        _check_clean(bad)


def test_forbidden_paths_are_detected(tmp_path: Path):
    (tmp_path / "hidden_tests").mkdir()
    (tmp_path / "hidden_tests" / "test_x.py").write_text("def test_x():\n    assert True\n")
    with pytest.raises(AssertionError):
        assert_no_forbidden_paths(build_context("bad", tmp_path))


def test_clean_tree_passes_guard(tiny_ctx):
    assert_no_forbidden_paths(tiny_ctx)


def test_dev_loader_refuses_test_split(tmp_path: Path):
    m = tmp_path / "datasets" / "manifests"
    m.mkdir(parents=True)
    (m / "test.json").write_text("[]")
    with pytest.raises(ValueError):
        load_dev(m / "test.json")


def test_baseline_rankings_are_deterministic(tiny_ctx):
    w = _workload(tiny_ctx)
    r1 = run([w], ["RET-L", "RET-G"], repeats=2, measure_memory=False)
    r2 = run([w], ["RET-L", "RET-G"], repeats=1, measure_memory=False)
    assert json.dumps(r1["rankings"], sort_keys=True) == json.dumps(r2["rankings"], sort_keys=True)
    ids = r1["rankings"]["RET-L"]["tiny/tiny/q1"]["ranked"]
    assert ids and ids[0] == GOLD  # the exact identifier is found first by BM25


def test_summary_and_comparison_seeded(tiny_ctx):
    w = _workload(tiny_ctx)
    r = run([w], ["RET-L", "RET-G"], repeats=1, measure_memory=False)
    s = summarize(r["rows"], ["RET-L", "RET-G"])
    assert {x["qtype"] for x in s} >= {"ALL", "exact_identifier"}
    c1 = compare(r["rows"], ["RET-L", "RET-G"], iters=200)
    c2 = compare(r["rows"], ["RET-L", "RET-G"], iters=200)
    assert c1 == c2 and c1
