# ruff: noqa: E501
"""Baseline arms. RET-L = BM25 (identifier-aware tokenizer, rank-bm25, top 50) with the L-arm
anchors (trace frames, config keys named in the evidence). RET-G = RET-L plus the graph features
(<=2-hop proximity/expansion, config binding, test link, uncertainty; symptom anchors on the dev
split). Both call `traceforge.retrieval.retrieve.rank` (existing code, read-only); the same shared
packer is applied afterwards by the harness, not here."""

from __future__ import annotations

from traceforge.retrieval.anchors import build_query
from traceforge.retrieval.retrieve import G_WEIGHTS, L_WEIGHTS, TOP_K, rank
from traceforge.retrieval_bench.registry import register
from traceforge.retrieval_bench.repo_ctx import RepoContext, synth_evidence
from traceforge.retrieval_bench.types import QueryText


def _ranked_ids(ctx: RepoContext, q: QueryText, k: int, mode: str) -> list[str]:
    ev = q.evidence or synth_evidence(q.qid, str(q), q.service)
    ranked = rank(build_query(ev, ctx.graph, q.service), ctx.graph, mode)
    out: list[str] = []
    for r in ranked:  # chunk.hit_id: bare `cfg:KEY` (not the service-qualified ContextHit id)
        if r.chunk.hit_id not in out:
            out.append(r.chunk.hit_id)
    return out[:k]


@register("RET-L", settings={"bm25_top_k": TOP_K, "weights": vars(L_WEIGHTS), "mode": "L"})
def ret_l(ctx: RepoContext, query_text: QueryText, k: int) -> list[str]:
    return _ranked_ids(ctx, query_text, k, "L")


@register("RET-G", settings={"bm25_top_k": TOP_K, "weights": vars(G_WEIGHTS), "mode": "G"})
def ret_g(ctx: RepoContext, query_text: QueryText, k: int) -> list[str]:
    return _ranked_ids(ctx, query_text, k, "G")
