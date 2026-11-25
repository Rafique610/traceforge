# ruff: noqa: E501
"""Fusion arms (P5-S08): Reciprocal Rank Fusion of a lexical / graph ranking with the dense one.

    RET-LE  = forced anchors first (as in L), then RRF(k) of the L ranking and the dense top-50
    RET-LG  = the current G arm (alias, identical ranking)
    RET-LGE = forced anchors first (as in G), then RRF(k) of the G ranking and the dense top-50

RRF score = sum_lists 1 / (k + rank), rank from 1. Ties are broken by the best rank in the base
(L or G) list, then by chunk id, so the order is fully deterministic. The base ranking comes from
`traceforge.retrieval.retrieve.rank` (read-only library call, same as RET-L / RET-G); the harness
applies the same equal-budget `pack()` afterwards. Forced anchors are the `Ranked.forced` entries
of that ranking, kept first in their anchor order exactly as the L / G arms put them.
"""

from __future__ import annotations

from traceforge.retrieval.anchors import build_query
from traceforge.retrieval.retrieve import rank
from traceforge.retrieval_bench.repo_ctx import synth_evidence

POOL = 50  # candidates taken from each list, as TOP_K in retrieval.retrieve


def rrf(lists: list[list[str]], k: int = 60, forced: list[str] | None = None,
        limit: int | None = None) -> list[str]:  # fmt: skip
    """Fuse ranked id lists. `forced` ids come first (given order); the rest by (-score,
    best rank in lists[0], id). Duplicates inside a list count once (first occurrence)."""
    if k <= 0:
        raise ValueError("rrf k must be positive")
    score: dict[str, float] = {}
    first: dict[str, int] = {}
    for li, lst in enumerate(lists):
        seen: set[str] = set()
        r = 0
        for i in lst:
            if i in seen:
                continue
            seen.add(i)
            r += 1
            score[i] = score.get(i, 0.0) + 1.0 / (k + r)
            if li == 0:
                first[i] = r
    head: list[str] = []
    for i in forced or []:
        if i not in head:
            head.append(i)
    tail = sorted((i for i in score if i not in head),
                  key=lambda i: (-round(score[i], 12), first.get(i, 10**9), i))  # fmt: skip
    out = head + tail
    return out[:limit] if limit is not None else out


def base_ranking(ctx, query_text, mode: str) -> tuple[list[str], list[str]]:
    """-> (ids best first, forced ids in anchor order) for the L or G arm; same call as
    `retrieval_bench.methods`, but keeping the forced flags."""
    ev = getattr(query_text, "evidence", None) or synth_evidence(
        getattr(query_text, "qid", ""), str(query_text), getattr(query_text, "service", "")
    )
    ranked = rank(build_query(ev, ctx.graph, getattr(query_text, "service", "")), ctx.graph, mode)
    ids: list[str] = []
    forced: list[str] = []
    for r in ranked:
        h = r.chunk.hit_id
        if h not in ids:
            ids.append(h)
            if r.forced:
                forced.append(h)
    return ids, forced


class HybridRetriever:
    def __init__(self, mode: str, dense, k_rrf: int = 60):
        if mode not in ("L", "G"):
            raise ValueError("mode must be L or G")
        self.mode, self.dense, self.k_rrf = mode, dense, k_rrf

    def prepare(self, ctx) -> None:
        self.dense.prepare(ctx)

    def __call__(self, ctx, query_text, k: int) -> list[str]:
        base, forced = base_ranking(ctx, query_text, self.mode)
        dense = self.dense(ctx, query_text, POOL)
        return rrf([base[:POOL], dense], self.k_rrf, forced=forced, limit=k)

    def storage_bytes(self, ctx) -> int:
        return self.dense.storage_bytes(ctx)
