# ruff: noqa: E501
"""Metrics against hand-computed values."""

import math

import pytest

from traceforge.retrieval_bench import metrics as m

RANKED = ["a", "b", "c", "d", "e"]
GOLD = frozenset({"b", "e", "z"})  # z is never retrieved


def test_recall_precision():
    assert m.recall_at_k(RANKED, GOLD, 1) == 0.0
    assert m.recall_at_k(RANKED, GOLD, 2) == pytest.approx(1 / 3)
    assert m.recall_at_k(RANKED, GOLD, 5) == pytest.approx(2 / 3)
    assert m.precision_at_k(RANKED, GOLD, 2) == pytest.approx(1 / 2)
    assert m.precision_at_k(RANKED, GOLD, 5) == pytest.approx(2 / 5)
    # K fixed: a list shorter than K is not rewarded
    assert m.precision_at_k(["b"], GOLD, 5) == pytest.approx(1 / 5)


def test_mrr():
    assert m.mrr(RANKED, GOLD) == pytest.approx(1 / 2)
    assert m.mrr(["x", "y"], GOLD) == 0.0
    assert m.mrr(["e", "b"], GOLD) == 1.0


def test_ndcg():
    # hits at ranks 2 and 5; gold size 3 -> ideal has 3 hits at ranks 1,2,3 (K=5)
    dcg = 1 / math.log2(3) + 1 / math.log2(6)
    idcg = 1 / math.log2(2) + 1 / math.log2(3) + 1 / math.log2(4)
    assert m.ndcg_at_k(RANKED, GOLD, 5) == pytest.approx(dcg / idcg)
    # K=2: only the rank-2 hit counts; ideal = 2 hits
    assert m.ndcg_at_k(RANKED, GOLD, 2) == pytest.approx(
        (1 / math.log2(3)) / (1 / math.log2(2) + 1 / math.log2(3))
    )
    assert m.ndcg_at_k(["b"], frozenset({"b"}), 10) == 1.0
    assert m.ndcg_at_k(["x"], frozenset({"b"}), 10) == 0.0


def test_file_hit_and_packed_scores(tiny_ctx):
    from traceforge.retrieval_bench.packing import Packed

    ids = [c.hit_id for c in tiny_ctx.corpus.chunks]
    tax = "sym:pkg/billing.py::compute_tax"
    disc = "sym:pkg/billing.py::apply_discount"
    assert tax in ids and disc in ids
    ranked = [disc, "sym:pkg/queue.py::JobQueue.pop", tax]
    assert m.file_hit_at_k(tiny_ctx, ranked, frozenset({tax}), 1) == 1.0  # same file as gold
    assert m.file_hit_at_k(tiny_ctx, ranked[1:], frozenset({tax}), 1) == 0.0
    sc = m.score_query(tiny_ctx, ranked, frozenset({tax}), Packed([disc, tax], 100, 3000, 2400))
    assert sc["gold_coverage_packed"] == 1.0
    assert sc["precision_packed"] == 0.5
    assert sc["mrr_packed"] == 0.5
    assert sc["mrr"] == pytest.approx(1 / 3)
    assert sc["symbol_hit@1"] == 0.0 and sc["file_hit@1"] == 1.0
