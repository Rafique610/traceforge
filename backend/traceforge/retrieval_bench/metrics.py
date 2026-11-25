# ruff: noqa: E501
"""Retrieval metrics on a ranked id list and a gold id set (binary relevance).

Definitions (K-truncated lists; `gold` is the set of relevant chunk ids):
  recall@K    = |top-K intersect gold| / |gold|
  precision@K = |top-K intersect gold| / K          (K fixed: a shorter list is not rewarded)
  MRR         = 1 / rank of the first gold id in the full list (0 if none)
  nDCG@K      = DCG / IDCG, DCG = sum rel_i / log2(i + 1), IDCG = ideal list of min(|gold|, K) hits
  file_hit@K  = 1 if any of the top-K ids lies in a gold file (source localisation)
Packed-context variants use the ids the shared packer actually kept within the token budget:
  gold_coverage = |packed intersect gold| / |gold|;  packed_precision = relevant / packed hits.
"""

from __future__ import annotations

import math

from traceforge.retrieval_bench.packing import Packed
from traceforge.retrieval_bench.repo_ctx import RepoContext

KS = (1, 5, 10)


def recall_at_k(ranked: list[str], gold: set[str] | frozenset[str], k: int) -> float:
    return len(set(ranked[:k]) & gold) / len(gold)


def precision_at_k(ranked: list[str], gold: set[str] | frozenset[str], k: int) -> float:
    return len(set(ranked[:k]) & gold) / k


def mrr(ranked: list[str], gold: set[str] | frozenset[str]) -> float:
    for n, i in enumerate(ranked, 1):
        if i in gold:
            return 1.0 / n
    return 0.0


def ndcg_at_k(ranked: list[str], gold: set[str] | frozenset[str], k: int) -> float:
    dcg = sum(1.0 / math.log2(n + 1) for n, i in enumerate(ranked[:k], 1) if i in gold)
    idcg = sum(1.0 / math.log2(n + 1) for n in range(1, min(len(gold), k) + 1))
    return dcg / idcg if idcg else 0.0


def _file(ctx: RepoContext, i: str) -> str | None:
    c = ctx.corpus.by_hit.get(i)
    return c.path if c else None


def file_hit_at_k(ctx: RepoContext, ranked: list[str], gold: set[str] | frozenset[str], k: int):
    gold_files = {f for g in gold if (f := _file(ctx, g))}
    return float(any(_file(ctx, i) in gold_files for i in ranked[:k]))


def score_query(
    ctx: RepoContext, ranked: list[str], gold: frozenset[str], packed: Packed
) -> dict[str, float]:
    m: dict[str, float] = {}
    for k in KS:
        m[f"recall@{k}"] = recall_at_k(ranked, gold, k)
        m[f"precision@{k}"] = precision_at_k(ranked, gold, k)
    m["mrr"] = mrr(ranked, gold)
    m["ndcg@10"] = ndcg_at_k(ranked, gold, 10)
    m["file_hit@1"] = file_hit_at_k(ctx, ranked, gold, 1)
    m["file_hit@5"] = file_hit_at_k(ctx, ranked, gold, 5)
    m["symbol_hit@1"] = float(bool(ranked) and ranked[0] in gold)
    hit = [i for i in packed.ids if i in gold]
    m["gold_coverage_packed"] = len(set(hit)) / len(gold)
    m["precision_packed"] = len(hit) / len(packed.ids) if packed.ids else 0.0
    m["mrr_packed"] = mrr(packed.ids, gold)
    m["tokens_used"] = float(packed.tokens_used)
    m["packed_hits"] = float(len(packed.ids))
    return m
