"""retrieve(evidence, graph, mode, token_budget) -> ContextBundle.

ONE candidate generator serves both arms: BM25 top-`TOP_K` over the chunk corpus, plus forced
anchors (innermost 2 project frames, config keys named in evidence) and the other project frames.
  L: score = 0.30*lex + 0.25*anchor
  G: score = 0.30*lex + 0.25*anchor + 0.20*graph_proximity + 0.10*test_link - 0.10*uncertain,
     and <=2-hop neighbours of the anchors join the candidate pool.
Both rank forced anchors first (in anchor order), then by (-score, hit_id), and are packed into
the same token budget by `context_budget.pack`. The code map is NOT part of the bundle: it is
offered identically in both arms through `RealContextSource` (D22). Initial weights are the
architecture-doc values, untouched (tune only on dev after the dataset freeze).
"""

from dataclasses import dataclass

from traceforge.codeintel import Graph
from traceforge.contracts.context import ContextBundle
from traceforge.contracts.evidence import EvidenceBundle
from traceforge.retrieval.anchors import Query, build_query
from traceforge.retrieval.context_budget import Ranked, pack
from traceforge.retrieval.corpus import get_corpus, qualified_id
from traceforge.retrieval.graph_ranker import GraphFeatures, GraphInfo, graph_scores
from traceforge.retrieval.lexical import index_for

TOP_K = 50


@dataclass(frozen=True)
class Weights:
    lex: float = 0.30
    anchor: float = 0.25
    graph: float = 0.0
    test_link: float = 0.0
    uncertain: float = 0.0


L_WEIGHTS = Weights()
G_WEIGHTS = Weights(graph=0.20, test_link=0.10, uncertain=0.10)


def rank(
    query: Query,
    graph: Graph,
    mode: str,
    features: GraphFeatures | None = None,
    weights: Weights | None = None,
    top_k: int = TOP_K,
) -> list[Ranked]:
    """Deterministic ranking of the shared candidate pool for `mode` ("L" or "G")."""
    if mode not in ("L", "G"):
        raise ValueError(f"mode must be 'L' or 'G', got {mode!r}")
    corpus = get_corpus(graph)
    norm = index_for(corpus).normalized(query.terms)
    cands = index_for(corpus).candidates(query.terms, top_k)
    pool: dict[str, float] = {c.node_id: lex for c, lex in cands}
    anchor_of: dict[str, tuple[float, str, int, bool, str]] = {}
    for a in query.anchors:
        c = corpus.by_node.get(a.node_id)
        if c is None:
            continue
        anchor_of.setdefault(a.node_id, (a.strength, a.source, a.rank, a.forced, a.evidence_id))
        pool.setdefault(a.node_id, norm.get(c.hit_id, 0.0))
    feats = (features or GraphFeatures()) if mode == "G" else None
    w = weights or (G_WEIGHTS if mode == "G" else L_WEIGHTS)
    info: dict[str, GraphInfo] = {}
    if feats is not None and feats.any:
        info = graph_scores(graph, query.anchors, feats)
        if feats.expansion:
            for nid in info:
                if nid in corpus.by_node and nid not in pool:
                    pool[nid] = norm.get(corpus.by_node[nid].hit_id, 0.0)
    in_top = {c2.node_id for c2, _ in cands}
    out: list[Ranked] = []
    for nid, lex in pool.items():
        c = corpus.by_node[nid]
        strength, src, arank, forced, eid = anchor_of.get(nid, (0.0, "", 0, False, ""))
        g = info.get(nid) or (info.get(c.parent) if c.parent else None)
        prox = g.prox if g and feats and feats.proximity else 0.0
        tl = g.test_link if g else 0.0
        unc = g.uncertain if g else 0.0
        score = (
            w.lex * lex
            + w.anchor * strength
            + w.graph * prox
            + w.test_link * tl
            - w.uncertain * unc
        )
        reasons = [f"bm25:{lex:.2f}"]
        if src == "config":
            reasons.append(f"anchor:config_key named in {eid}")
        elif src:
            reasons.append(f"anchor:{src} frame#{arank + 1} ({eid})")
        if g and feats:
            if nid not in in_top and feats.expansion:
                reasons.append(f"graph:expanded (not in BM25 top {top_k})")
            reasons.append(f"graph:hops={g.hops} prox={g.prox:.2f} via {g.path}")
            if tl:
                reasons.append("graph:test_link")
            if unc:
                reasons.append(f"graph:uncertain={unc:.2f}")
        out.append(
            Ranked(
                c,
                score + (1.0 if forced else 0.0),
                reasons,
                forced,
                arank,
                qualified_id(c, query.service),
            )
        )
    out.sort(
        key=lambda r: (not r.forced, r.forced_rank if r.forced else 0, -r.score, r.chunk.hit_id)
    )
    return out


def retrieve(
    evidence: EvidenceBundle,
    graph: Graph,
    mode: str,
    token_budget: int,
    *,
    service: str = "",
    features: GraphFeatures | None = None,
    weights: Weights | None = None,
) -> ContextBundle:
    ranked = rank(build_query(evidence, graph, service), graph, mode, features, weights)
    hits, used = pack(ranked, token_budget)
    return ContextBundle(
        incident_id=evidence.incident_id, mode=mode, token_budget=token_budget,  # type: ignore[arg-type]
        tokens_used=used, hits=hits,
    )  # fmt: skip
