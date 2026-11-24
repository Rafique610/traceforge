"""Side-by-side retrieval record: lexical (L), graph (G) and their union, for one incident.

Written next to every v5 run so the graph's contribution is inspectable per case, independently of
the model. Relevance here is judged only from the symptom (term overlap with the hit text, and the
graph reasons that tie a hit to a symptom anchor); gold symbols are NOT used. Gold-based scoring
(`evaluate`) is evaluation-only and takes the gold labels as an argument.
"""

from __future__ import annotations

from typing import Any

from traceforge.agent.symptom import symptom_view
from traceforge.contracts.context import ContextBundle
from traceforge.contracts.evidence import EvidenceBundle
from traceforge.retrieval.anchors import symptom_terms
from traceforge.retrieval.lexical import tokenize


def _row(h: Any, terms: set[str]) -> dict:
    words = set(tokenize(f"{h.path} {h.excerpt}"))
    matched = sorted(terms & words)
    anchored = any(r.startswith("anchor:symptom") for r in h.reasons)
    graph = any(r.startswith("graph:") for r in h.reasons)
    return {
        "id": h.node_id,
        "path": h.path,
        "kind": h.kind,
        "score": round(h.score, 4),
        "symptom_terms_matched": matched[:12],
        "n_symptom_terms_matched": len(matched),
        "symptom_anchor": anchored,
        "graph_reason": graph,
        "reasons": h.reasons[:4],
        "relevant_to_symptom": bool(matched) or anchored,
    }


def compare(evidence: EvidenceBundle, retrieve: Any, token_budget: int) -> dict:
    """`retrieve(evidence, None, mode, budget) -> ContextBundle` (a ContextSource.retrieve)."""
    terms = set(tokenize(" ".join(symptom_terms(symptom_view(evidence)))))
    bundles: dict[str, ContextBundle] = {m: retrieve(evidence, None, m, token_budget) for m in "LG"}
    rows = {m: [_row(h, terms) for h in b.hits] for m, b in bundles.items()}
    ids = {m: {r["id"] for r in rows[m]} for m in "LG"}
    union = ids["L"] | ids["G"]
    only = {m: [r for r in rows[m] if r["id"] not in ids["L" if m == "G" else "G"]] for m in "LG"}
    return {
        "token_budget": token_budget,
        "symptom_terms": sorted(terms)[:40],
        "L": rows["L"],
        "G": rows["G"],
        "union_ids": sorted(union),
        "overlap": len(ids["L"] & ids["G"]),
        "only_L": [r["id"] for r in only["L"]],
        "only_G": [r["id"] for r in only["G"]],
        "relevant": {m: sum(1 for r in rows[m] if r["relevant_to_symptom"]) for m in ("L", "G")},
        "irrelevant": {
            m: sum(1 for r in rows[m] if not r["relevant_to_symptom"]) for m in ("L", "G")
        },
        "only_G_relevant": sum(1 for r in only["G"] if r["relevant_to_symptom"]),
        "only_L_relevant": sum(1 for r in only["L"] if r["relevant_to_symptom"]),
    }


def evaluate(record: dict, gold: set[str]) -> dict:
    """Evaluation only: where do the gold `path::qualname` symbols rank in L and G?"""

    def rank(rows: list[dict]) -> int | None:
        for i, r in enumerate(rows, 1):
            if f"{r['path']}::{r['id'].rsplit('::', 1)[-1]}" in gold:
                return i
        return None

    return {
        "gold_rank_L": rank(record["L"]),
        "gold_rank_G": rank(record["G"]),
        "gold_in_union": any(
            f"{i.split(':', 1)[-1]}" in gold or i.split(":", 1)[-1] in gold
            for i in record["union_ids"]
        ),
    }
