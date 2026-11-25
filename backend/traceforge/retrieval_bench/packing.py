# ruff: noqa: E501
"""Equal-token-budget packing, identical for every method: the existing
`retrieval.context_budget.pack` (3000 tokens, 20% reserved => 2400 usable, tokens = chars/4,
<= 80 lines per excerpt, already-shown lines skipped), applied to a method's ranked chunk ids with
NEUTRAL reasons (so no method pays a different header cost)."""

from __future__ import annotations

from dataclasses import dataclass

from traceforge.retrieval.context_budget import RESERVE_FRACTION, Ranked, pack
from traceforge.retrieval_bench.repo_ctx import RepoContext

DEFAULT_BUDGET = 3000


@dataclass(frozen=True)
class Packed:
    ids: list[str]  # packed hits in rank order
    tokens_used: int
    budget: int
    usable: int


def pack_ids(ctx: RepoContext, ranked_ids: list[str], budget: int = DEFAULT_BUDGET) -> Packed:
    seen: list[str] = []
    for i in ranked_ids:
        if i in ctx.corpus.by_hit and i not in seen:
            seen.append(i)
    items = [
        Ranked(ctx.corpus.by_hit[i], score=float(-n), reasons=[], hit_id=i)
        for n, i in enumerate(seen)
    ]
    hits, used = pack(items, budget)
    return Packed([h.node_id for h in hits], used, budget, int(budget * (1 - RESERVE_FRACTION)))
