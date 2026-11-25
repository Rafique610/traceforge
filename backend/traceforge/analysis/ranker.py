# ruff: noqa: E501
"""Root-cause candidate ranker (P5-S12). Ranked hypotheses with reason chains; not a verdict.

Inputs are supplied by the caller and are symptom-side only: trace frames, failing visible test
ids, symptom text, optional retrieval hits. Gold, hidden tests and `.env` values are never inputs.
Score of a candidate = noisy-or over seeds of
  seed relevance x direction prior x kind prior x path weight (edge prior x confidence x hub x decay)
Deterministic: ties are broken by node id.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from traceforge.analysis import priors as P
from traceforge.analysis.overlay import OverlayGraph
from traceforge.analysis.traversal import (
    Reached,
    Step,
    TraversalConfig,
    traverse,
    unknown_sites,
)
from traceforge.codeintel.trace_map import symbol_at

_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_SPLIT = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")
STOPWORDS = frozenset(
    "self cls none true false return import from with assert error raise exception test tests "
    "line file module the and for not def class value".split()
)
CANDIDATE_KINDS = ("function", "method", "class", "config_key")


@dataclass(frozen=True)
class Seed:
    node: str
    kind: str  # frame | failing_test | symptom | retrieval
    relevance: float
    observed: bool = False
    note: str = ""


@dataclass(frozen=True)
class Candidate:
    node: str
    kind: str
    path: str | None
    start: int | None
    score: float
    rank: int
    evidence: str  # evidence class of the best reason chain
    reasons: tuple[str, ...]  # human-readable chain: seed -> ... -> candidate
    steps: tuple[Step, ...]  # (edge type, evidence class, file:line) per hop
    via_seed: str
    direction: str


@dataclass(frozen=True)
class RankResult:
    candidates: tuple[Candidate, ...]
    seeds: tuple[Seed, ...]
    abstain: bool = False
    unresolved: tuple[str, ...] = ()  # unknown call sites next to the seeds
    notes: tuple[str, ...] = ()

    def ids(self, k: int | None = None) -> list[str]:
        return [c.node for c in self.candidates[:k]]


@dataclass(frozen=True)
class RankerConfig:
    traversal: TraversalConfig = field(default_factory=TraversalConfig)
    top_k: int = 20
    undeclared_boost: float = P.UNDECLARED_KEY_BOOST


# ---- seeds ---------------------------------------------------------------------------------
def _tokens(text: str) -> set[str]:
    out: set[str] = set()
    for w in _WORD.findall(text):
        for part in w.split("_"):
            out.update(p.lower() for p in _SPLIT.findall(part) if len(p) >= 4)
    return out - STOPWORDS


def seeds_from_runtime(
    og: OverlayGraph,
    frames: Sequence[tuple[str, int]] = (),
    failing_tests: Sequence[str] = (),
    symptom: str = "",
) -> list[Seed]:
    """Seeds from trace frames (outermost first), failing test ids and symptom text."""
    seeds: dict[tuple[str, str], Seed] = {}

    def add(s: Seed) -> None:
        k = (s.node, s.kind)
        if k not in seeds or seeds[k].relevance < s.relevance:
            seeds[k] = s

    src_frames = []
    for path, line in frames:
        nid = symbol_at(og.base, path, line)
        if nid and nid in og:
            src_frames.append((nid, f"{path}:{line}"))
    non_test = [f for f in src_frames if og.kind(f[0]) != "test"]
    inner = non_test[-1][0] if non_test else None
    for nid, loc in src_frames:
        if og.kind(nid) == "test":
            add(Seed(nid, "failing_test", P.SEED_PRIOR["failing_test"], True, f"frame {loc}"))
        else:
            rel = P.SEED_PRIOR["frame"] * (P.INNER_FRAME_BOOST if nid == inner else P.OUTER_FRAME)
            add(Seed(nid, "frame", rel, True, f"trace frame {loc}"))
    for t in failing_tests:
        tid = t[5:] if t.startswith("test:") else t
        for nid, d in og.nx.nodes(data=True):
            if d["kind"] == "test" and (nid[5:] == tid or nid[5:].startswith(tid + "[")):
                add(Seed(nid, "failing_test", P.SEED_PRIOR["failing_test"], True, f"failing {t}"))
    if symptom:
        add_symptom_seeds(og, symptom, add)
    return sorted(seeds.values(), key=lambda s: (-s.relevance, s.node, s.kind))


def add_symptom_seeds(og: OverlayGraph, text: str, add) -> None:
    words = set(_WORD.findall(text))
    toks = _tokens(text)
    by_name: dict[str, list[str]] = {}
    for nid, d in og.nx.nodes(data=True):
        if d["kind"] in ("function", "method", "class") and d.get("name") in words:
            by_name.setdefault(d["name"], []).append(nid)
    for name, nodes in sorted(by_name.items()):
        for nid in sorted(nodes):  # a name shared by n nodes splits its relevance (collision)
            add(Seed(nid, "symptom", P.SEED_PRIOR["symptom"] / len(nodes), False,
                     f"symptom names `{name}`"))  # fmt: skip
    for nid, d in sorted(og.nx.nodes(data=True)):
        if d["kind"] != "config_key":
            continue
        name = d["name"]
        if name in words:
            add(Seed(nid, "symptom", 0.9, False, f"symptom names key {name}"))
            continue
        kt = _tokens(name)
        hit = kt & toks
        if hit:
            frac = len(hit) / len(kt)
            add(Seed(nid, "symptom", P.NAME_TOKEN_MATCH * frac, False,
                     f"symptom shares word(s) {sorted(hit)} with key {name}"))  # fmt: skip


def seeds_from_retrieval(og: OverlayGraph, hits: Iterable[tuple[str, float]]) -> list[Seed]:
    """Retrieval hits as (node id, score in 0..1); unknown ids are skipped."""
    return [
        Seed(n, "retrieval", P.SEED_PRIOR["retrieval"] * max(0.0, min(1.0, s)), False, "retrieval")
        for n, s in hits
        if n in og
    ]


# ---- ranking -------------------------------------------------------------------------------
def _expand_test_seeds(og: OverlayGraph, seeds: Sequence[Seed]) -> list[Seed]:
    """A failing test points at what it covers: covered functions become seeds (hop 0)."""
    out: list[Seed] = []
    for s in seeds:
        if og.kind(s.node) != "test":
            out.append(s)
            continue
        for e in og.edges_from(s.node, ("tests_covers",)):
            if og.kind(e.dst) in ("function", "method", "class") and e.evidence != "unknown":
                out.append(Seed(e.dst, s.kind, s.relevance * e.confidence, s.observed,
                                f"covered by {s.node[5:]}"))  # fmt: skip
    return out


def _kind_of(og: OverlayGraph, nid: str) -> str:
    return og.kind(nid)


def _undeclared(og: OverlayGraph, key: str, any_compose: bool) -> bool:
    """Key read by code, set by no compose service, while the repo does declare service env."""
    return any_compose and og.has_edge_type(key, "read_by") and not og.has_edge_type(key, "env_of")


def rank_root_causes(
    og: OverlayGraph, seeds: Sequence[Seed], cfg: RankerConfig | None = None
) -> RankResult:
    cfg = cfg or RankerConfig()
    seeds = _expand_test_seeds(og, [s for s in seeds if s.node in og])
    any_compose = any(d["kind"] == "service" for _n, d in og.nx.nodes(data=True))
    contrib: dict[str, list[tuple[float, Seed, str, Reached | None]]] = {}

    def put(node: str, score: float, seed: Seed, direction: str, r: Reached | None) -> None:
        if og.kind(node) in CANDIDATE_KINDS and score > 0:
            contrib.setdefault(node, []).append((score, seed, direction, r))

    named = frozenset(s.node for s in seeds)
    tcfg = TraversalConfig(
        depth=cfg.traversal.depth, top_n=cfg.traversal.top_n, node_cap=cfg.traversal.node_cap,
        edge_budget=cfg.traversal.edge_budget, decay=cfg.traversal.decay,
        hub_stop=cfg.traversal.hub_stop, named=cfg.traversal.named | named,
    )  # fmt: skip
    for s in seeds:
        put(s.node, s.relevance * P.KIND_PRIOR.get(og.kind(s.node), 0.5), s, "seed", None)
        for direction in ("forward", "config", "reverse", "tests"):
            if direction == "tests":
                continue  # tests are evidence, not root-cause candidates
            for r in traverse(og, [s.node], direction, tcfg):
                score = (s.relevance * P.DIRECTION_PRIOR[direction]
                         * P.KIND_PRIOR.get(og.kind(r.node), 0.0) * r.weight)  # fmt: skip
                if og.kind(r.node) == "config_key" and _undeclared(og, r.node, any_compose):
                    score *= cfg.undeclared_boost
                put(r.node, score, s, direction, r)
    ranked: list[tuple[float, str]] = []
    for node, rows in contrib.items():
        prod = 1.0
        for sc, *_ in rows:
            prod *= 1.0 - min(sc, 0.999)
        ranked.append((1.0 - prod, node))
    ranked.sort(key=lambda t: (-round(t[0], 9), t[1]))
    cands: list[Candidate] = []
    for i, (score, node) in enumerate(ranked[: cfg.top_k], 1):
        sc, seed, direction, r = max(
            contrib[node], key=lambda row: (round(row[0], 9), row[1].node, row[2])
        )
        steps = r.steps if r else ()
        reasons = [f"seed {seed.node} ({seed.kind}: {seed.note})"]
        reasons += [s.text() for s in steps] or ["is the seed itself"]
        ev = r.evidence if r else ("observed" if seed.observed else "static")
        d = og.node(node)
        cands.append(Candidate(node, d["kind"], d.get("path"), d.get("start"), score, i, ev,
                               tuple(reasons), steps, seed.node, direction))  # fmt: skip
    unresolved = sorted(
        {f"{s.node} -> {u}" for s in seeds if og.kind(s.node) != "test"
         for u in _unresolved_sites(og, s.node)}
    )  # fmt: skip
    notes = []
    if unresolved:
        notes.append(
            "unresolved call sites next to the seeds: the true dependency may be invisible"
        )
    return RankResult(tuple(cands), tuple(seeds), bool(unresolved), tuple(unresolved), tuple(notes))


def _unresolved_sites(og: OverlayGraph, node: str) -> list[str]:
    """Unknown call sites with no name-based candidate (those are inferred edges, not blind)."""
    out = []
    for e in og.edges_from(node, ("calls",)):
        if e.evidence == "unknown" and e.dst.startswith("unknown:") and not e.reverse:
            n = 0
            for _u, _v, d in og.nx.out_edges(node, data=True):
                if (
                    d["type"] == "calls"
                    and d.get("name_resolved")
                    and d["provenance"] == e.provenance
                ):
                    n += 1
            if n == 0:
                out.append(f"{e.dst} @ {e.provenance}")
    return out


__all__ = [
    "Candidate", "RankResult", "RankerConfig", "Seed", "rank_root_causes", "seeds_from_retrieval",
    "seeds_from_runtime", "unknown_sites",
]  # fmt: skip
