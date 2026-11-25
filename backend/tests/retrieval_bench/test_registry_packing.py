# ruff: noqa: E501
"""Registry API and the equal-budget packer."""

import pytest

from traceforge.retrieval_bench import registry
from traceforge.retrieval_bench.packing import DEFAULT_BUDGET, pack_ids


def test_baselines_registered():
    import traceforge.retrieval_bench  # noqa: F401

    assert {"RET-L", "RET-G"} <= set(registry.names())
    assert registry.meta("RET-L")["settings"]["mode"] == "L"
    assert registry.meta("RET-G")["settings"]["mode"] == "G"


def test_register_function_class_and_duplicates():
    @registry.register("RET-TEST-FN", model_id="m@1", settings={"x": 1})
    def fn(ctx, query_text, k):
        return []

    @registry.register("RET-TEST-CLS")
    class Cls:
        def prepare(self, ctx):
            ctx.state["RET-TEST-CLS"] = 1

        def __call__(self, ctx, query_text, k):
            return [c.hit_id for c in ctx.corpus.chunks][:k]

    try:
        assert registry.get("RET-TEST-FN") is fn
        assert registry.meta("RET-TEST-FN") == {"model_id": "m@1", "settings": {"x": 1}}
        assert hasattr(registry.get("RET-TEST-CLS"), "prepare")
        with pytest.raises(ValueError):
            registry.register("RET-TEST-FN")(fn)
        with pytest.raises(KeyError):
            registry.get("RET-NOPE")
    finally:
        registry.unregister("RET-TEST-FN")
        registry.unregister("RET-TEST-CLS")


def test_equal_budget_packing_is_method_independent(tiny_ctx):
    ids = [c.hit_id for c in tiny_ctx.corpus.chunks]
    a = pack_ids(tiny_ctx, ids)
    b = pack_ids(tiny_ctx, list(ids))  # same ranking from a "different method"
    assert a == b
    assert a.budget == DEFAULT_BUDGET == 3000 and a.usable == 2400
    assert a.tokens_used <= a.usable


def test_packing_respects_budget_and_rank_order(tiny_ctx):
    ids = [c.hit_id for c in tiny_ctx.corpus.chunks]
    tight = pack_ids(tiny_ctx, ids, budget=40)  # 32 usable tokens: not everything fits
    assert tight.tokens_used <= tight.usable == 32
    assert len(tight.ids) < len(ids)
    full = pack_ids(tiny_ctx, ids)
    assert full.ids == [i for i in ids if i in full.ids]  # rank order preserved


def test_packing_ignores_unknown_ids_and_duplicates(tiny_ctx):
    one = tiny_ctx.corpus.chunks[0].hit_id
    p = pack_ids(tiny_ctx, ["sym:nope.py::x", one, one])
    assert p.ids == [one]


def test_every_registered_method_gets_the_same_packer(tiny_ctx):
    """Two methods returning the same ids are packed identically regardless of their name."""
    ids = [c.hit_id for c in tiny_ctx.corpus.chunks]

    @registry.register("RET-TEST-A")
    def a(ctx, q, k):
        return ids[:k]

    @registry.register("RET-TEST-B")
    def b(ctx, q, k):
        return ids[:k]

    try:
        from traceforge.retrieval_bench.runner import run
        from traceforge.retrieval_bench.suite import Workload
        from traceforge.retrieval_bench.types import BenchQuery

        q = BenchQuery("q", "t", tiny_ctx.make_query("q", "tax"), frozenset({ids[0]}))
        r = run([Workload("s", tiny_ctx, [q])], ["RET-TEST-A", "RET-TEST-B"], repeats=1,
                measure_memory=False)  # fmt: skip
        rows = {x["method"]: x for x in r["rows"]}
        assert rows["RET-TEST-A"]["tokens_used"] == rows["RET-TEST-B"]["tokens_used"]
        assert (
            r["rankings"]["RET-TEST-A"].popitem()[1]["packed"]
            == (r["rankings"]["RET-TEST-B"].popitem()[1]["packed"])
        )
    finally:
        registry.unregister("RET-TEST-A")
        registry.unregister("RET-TEST-B")
