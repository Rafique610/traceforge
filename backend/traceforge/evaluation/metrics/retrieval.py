"""Retrieval metrics (binary relevance) from saved ContextBundles vs gold symbols/config keys.

Relevant node ids: `cfg:<key>` and `sym:<path>::<qualname>`. Hits are taken in saved rank order
and de-duplicated by node_id. Cases with no gold target (runtime_dependency, abstain) are
excluded and counted in `n_without_gold`.
"""

import math

from traceforge.contracts.case_manifest import CaseManifest
from traceforge.contracts.context import ContextBundle
from traceforge.evaluation.metrics.common import (
    distance_bucket,
    gold_node_ids,
    group_by,
    mean_of,
    ratio,
)

KS = (1, 5, 10)


def _ranked(bundle: ContextBundle) -> list[str]:
    seen: list[str] = []
    for h in bundle.hits:
        if h.node_id not in seen:
            seen.append(h.node_id)
    return seen


def case_retrieval(bundle: ContextBundle, gold: set[str]) -> dict:
    """Per-bundle found@k, reciprocal rank and nDCG@10 (gold must be non-empty)."""
    ranked = _ranked(bundle)
    out: dict = {f"found@{k}": len(gold & set(ranked[:k])) for k in KS}
    first = next((i for i, n in enumerate(ranked, 1) if n in gold), None)
    out["rr"] = 1 / first if first else 0.0
    dcg = sum(1 / math.log2(i + 1) for i, n in enumerate(ranked[:10], 1) if n in gold)
    ideal = sum(1 / math.log2(i + 1) for i in range(1, min(len(gold), 10) + 1))
    out["ndcg@10"] = dcg / ideal
    out["gold"] = len(gold)
    return out


def retrieval_metrics(items: list[tuple[ContextBundle, CaseManifest]]) -> dict:
    scored = [(case_retrieval(b, g), b) for b, m in items if (g := gold_node_ids(m))]
    n = len(scored)
    out: dict = {"n": n, "n_without_gold": len(items) - n}
    gold_total = sum(s["gold"] for s, _ in scored)
    for k in KS:
        out[f"recall@{k}"] = {
            **mean_of([s[f"found@{k}"] / s["gold"] for s, _ in scored]),
            "pooled": ratio(sum(s[f"found@{k}"] for s, _ in scored), gold_total),
        }
    out["mrr"] = mean_of([s["rr"] for s, _ in scored])
    out["ndcg@10"] = mean_of([s["ndcg@10"] for s, _ in scored])
    out["tokens_used"] = mean_of([float(b.tokens_used) for _, b in scored])
    return out


def retrieval_report(items: list[tuple[ContextBundle, CaseManifest]]) -> dict:
    """Per retrieval mode (L/G): overall plus breakdowns (case-level dimensions)."""
    dims = {
        "cause_class": lambda it: it[1].cause_class,
        "distance": lambda it: distance_bucket(it[1].distance),
        "fault_family": lambda it: it[1].fault_family,
        "log_format": lambda it: it[1].log_format,
    }
    result = {}
    for mode, grp in group_by(items, lambda it: it[0].mode).items():
        result[mode] = {
            "overall": retrieval_metrics(grp),
            "breakdowns": {
                d: {k: retrieval_metrics(v) for k, v in group_by(grp, f).items()}
                for d, f in dims.items()
            },
        }
    return result
