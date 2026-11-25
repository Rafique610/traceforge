# ruff: noqa: E501
"""P5-S08 arms: RRF by hand, forced anchors, ties, dimension mismatch, warm-resync reuse, fairness,
registration. Offline: a deterministic FakeEmbedder replaces Ollama."""

import numpy as np
import pytest

from traceforge.index import DimensionMismatch, FakeEmbedder, search
from traceforge.retrieval_bench import registry
from traceforge.retrieval_bench.packing import pack_ids
from traceforge.retrieval_bench.types import QueryText
from traceforge.retrieval_next import bench_plugin
from traceforge.retrieval_next.dense import DenseRetriever, ensure_index, group_of
from traceforge.retrieval_next.hybrid import HybridRetriever, base_ranking, rrf


def test_rrf_hand_computed():
    # k=60: a = 1/61 + 1/62 = b (tie) ; c = 1/63 ; d = 1/63
    out = rrf([["a", "b", "c"], ["b", "a", "d"]], k=60)
    # a, b tie on score -> best rank in list 0 (a=1 < b=2); c (list0 rank 3) before d (absent)
    assert out == ["a", "b", "c", "d"]
    assert rrf([["x", "y"], ["y"]], k=1)[:2] == ["y", "x"]  # y: 1/3+1/2 > x: 1/2
    assert rrf([["a"], ["b"]], k=60, limit=1) == ["a"]


def test_rrf_forced_first_and_dedup_and_ties():
    out = rrf([["a", "b", "c"], ["c", "b"]], k=60, forced=["z", "c"])
    assert out[:2] == ["z", "c"] and out[2:] == ["b", "a"]  # b: 1/62+1/62 beats a: 1/61
    assert rrf([["a", "a", "b"]], k=60) == ["a", "b"]  # duplicate counted once
    assert rrf([[], ["m", "k"], ["k", "m"]], k=60) == ["k", "m"]  # equal scores: id order
    with pytest.raises(ValueError):
        rrf([["a"]], k=0)


def _fake(dims=16):
    return FakeEmbedder("fake", "1", dims)


def test_dense_warm_resync_reuses_and_search_dims(tiny_ctx, tmp_path):
    emb = _fake()
    idx = ensure_index(tiny_ctx, emb, tmp_path / "ix", "k1")
    info = tiny_ctx.state["k1"]["info"]
    assert info["warm"]["texts_embedded"] == 0
    assert info["warm"]["reused"] == len(tiny_ctx.corpus.chunks)
    assert info["sync"]["texts_embedded"] > 0
    with pytest.raises(DimensionMismatch):
        search(idx, np.ones(7, np.float32), 3)
    assert (tmp_path / "ix" / "build_log.jsonl").is_file()


def test_dense_query_text_is_exactly_the_bm25_string(tiny_ctx, tmp_path):
    emb = _fake()
    d = DenseRetriever("k", lambda: emb, tmp_path / "ix")
    q = tiny_ctx.make_query("q1", "broker down when pushing a job", "")
    ids = d(tiny_ctx, q, 50)
    assert emb.calls[-1] == ["broker down when pushing a job"]
    assert ids == d(tiny_ctx, q, 50)
    assert len(ids) == len(set(ids)) <= 50
    assert all(i in tiny_ctx.corpus.by_hit for i in ids)


def test_dense_incremental_second_tree_embeds_only_changes(tiny_repo, tmp_path):
    from traceforge.retrieval_bench.repo_ctx import build_context

    emb = _fake()
    c1 = build_context("shop_api-001", tiny_repo)
    ensure_index(c1, emb, tmp_path / "ix", "k")
    n1 = len(emb.texts)
    (tiny_repo / "pkg" / "billing.py").write_text(
        "def compute_tax(amount, rate):\n    return amount * rate * 2\n\n\n"
        "def apply_discount(amount, pct):\n    return amount * (100 - pct) / 100\n",
        "utf-8",
    )
    c2 = build_context("shop_api-002", tiny_repo)  # same `dev` group root
    assert group_of(c1.name) == group_of(c2.name) == "dev"
    ensure_index(c2, emb, tmp_path / "ix", "k")
    assert 0 < len(emb.texts) - n1 <= 2  # only the modified function (and maybe its module)


class _NoDense:
    def prepare(self, ctx):
        return None

    def __call__(self, ctx, q, k):
        return []

    def storage_bytes(self, ctx):
        return 0


def test_hybrid_matches_base_when_dense_empty_and_forced_first(tiny_ctx, tmp_path):
    q = QueryText("compute_tax wrong rate", "q", None, "")
    import traceforge.retrieval_bench  # noqa: F401

    for mode, name in (("L", "RET-L"), ("G", "RET-G")):
        h = HybridRetriever(mode, _NoDense(), 60)
        assert h(tiny_ctx, q, 50) == registry.get(name)(tiny_ctx, q, 50)
        ids, forced = base_ranking(tiny_ctx, q, mode)
        assert ids[: len(forced)] == forced
    tb = (
        'Traceback (most recent call last):\n  File "pkg/queue.py", line 3, in push\n'
        "    raise ConnectionError('broker down')\nConnectionError: broker down"
    )
    qt = tiny_ctx.make_query("q2", tb, "")
    emb = _fake()
    d = DenseRetriever("k", lambda: emb, tmp_path / "ix")
    fused = HybridRetriever("L", d, 60)(tiny_ctx, qt, 50)
    ids, forced = base_ranking(tiny_ctx, qt, "L")
    assert forced and fused[: len(forced)] == forced
    assert fused == HybridRetriever("L", d, 60)(tiny_ctx, qt, 50)  # deterministic


def test_fused_arms_use_the_shared_packer(tiny_ctx, tmp_path):
    emb = _fake()
    d = DenseRetriever("k", lambda: emb, tmp_path / "ix")
    q = tiny_ctx.make_query("q", "apply discount percent", "")
    r = HybridRetriever("G", d, 30)(tiny_ctx, q, 50)
    p = pack_ids(tiny_ctx, r, 3000)
    assert p.tokens_used <= p.usable and p.budget == 3000


def test_plugin_registers_arms_and_alias(tiny_ctx, tmp_path):
    names = bench_plugin.register_arms(
        lambda tag: _fake(), tmp_path / "ix", tags=["jina"], prefix="T:"
    )
    try:
        assert {
            "T:RET-E@jina",
            "T:RET-LE@jina:k30",
            "T:RET-LGE@jina:k60",
            "T:RET-E",
            "T:RET-LE",
            "T:RET-LGE",
        } <= set(names)
        assert registry.meta("T:RET-LGE@jina:k30")["settings"]["rrf_k"] == 30
        q = tiny_ctx.make_query("q", "retry limit", "")
        r = registry.get("T:RET-LGE")
        r.prepare(tiny_ctx)
        assert r(tiny_ctx, q, 50)
    finally:
        for n in names:
            registry.unregister(n)


def test_ret_lg_is_g(tiny_ctx):
    import traceforge.retrieval_bench  # noqa: F401  (registers RET-G)

    assert "RET-LG" in registry.names()
    q = tiny_ctx.make_query("q", "compute_tax rate", "")
    assert registry.get("RET-LG")(tiny_ctx, q, 50) == registry.get("RET-G")(tiny_ctx, q, 50)


def test_modules_never_touch_gold():
    import traceforge.retrieval_next.dense as d
    import traceforge.retrieval_next.hybrid as h

    for m in (d, h):
        with open(m.__file__, encoding="utf-8") as f:
            src = f.read().lower()
        assert "gold_" not in src and "mutation.patch" not in src and "hidden_tests" not in src
