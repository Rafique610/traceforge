# ruff: noqa: E501
"""Budgeted bidirectional multi-hop traversal over an OverlayGraph (P5-S12).

Directions (design section 3 table):
  forward  calls, imports, reads_config, inherits, overrides      -> "what does X depend on"
  reverse  called_by, imported_by, read_by, subclassed_by,
           overridden_by                                          -> "what depends on X"
  config   reads_config, then env_of / declared_by / defined_in   -> "which config affects X"
  tests    covered_by                                             -> "which tests exercise X"

Frontier control: level-synchronous; at each hop arrivals are scored by path weight
  weight = parent weight x edge prior x edge confidence x hub factor x decay (once per hop)
and only the top N per hop survive, subject to a per-edge-type budget and a node cap. Test, file,
unknown and service nodes are leaves. Nodes with degree_all > hub_stop are reported but not
expanded unless they are seeds or explicitly named. Everything is deterministic (ties by id).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace

from traceforge.analysis import priors as P
from traceforge.analysis.overlay import Edge, OverlayGraph, path_evidence

LEAF_KINDS = frozenset({"test", "file", "unknown", "service"})
DIRECTION_TYPES = {
    "forward": P.FORWARD_TYPES,
    "reverse": P.REVERSE_TYPES,
    "config": P.CONFIG_TYPES,
    "tests": P.TEST_TYPES,
}


@dataclass(frozen=True)
class Step:
    src: str
    dst: str
    type: str
    evidence: str
    provenance: str  # file:line
    confidence: float

    def text(self) -> str:
        return f"{self.src} -{self.type}[{self.evidence}]-> {self.dst} @ {self.provenance}"


@dataclass(frozen=True)
class Reached:
    node: str
    depth: int
    weight: float
    direction: str
    steps: tuple[Step, ...]
    evidence: str
    hub: bool = False

    @property
    def direct(self) -> bool:
        """One hop, found statically (or observed). Everything else is transitive or inferred."""
        return self.depth == 1 and self.evidence in ("static", "observed")

    @property
    def kind(self) -> str:
        if self.evidence in ("inferred", "unknown"):
            return "inferred"
        return "direct" if self.depth == 1 else "transitive"

    def explanation(self) -> list[str]:
        return [s.text() for s in self.steps]


@dataclass(frozen=True)
class TraversalConfig:
    depth: dict[str, int] = field(default_factory=lambda: dict(P.DEPTH))
    top_n: int = P.TOP_N_PER_HOP
    node_cap: int = P.NODE_CAP
    edge_budget: int = P.EDGE_TYPE_BUDGET
    decay: float = P.DECAY
    hub_stop: float = P.HUB_STOP_DEGREE
    named: frozenset[str] = frozenset()  # nodes the symptom names: hubs are expanded anyway
    overrides_in_reverse: bool = False  # callers of the overridden base method (inferred)
    last_level_kinds: tuple[str, ...] = ()  # kinds accepted one hop beyond `depth` (tests)

    def with_depth(self, **kw: int) -> TraversalConfig:
        return replace(self, depth={**self.depth, **kw})


IMPACT_CONFIG = TraversalConfig(
    depth={"reverse": P.IMPACT_DEPTH, "forward": P.IMPACT_DEPTH, "config": 2, "tests": 1},
    top_n=10_000, node_cap=2_000, edge_budget=10_000, hub_stop=float("inf"),
    overrides_in_reverse=True, last_level_kinds=("test",),
)  # fmt: skip


def _types(direction: str, cfg: TraversalConfig) -> tuple[str, ...]:
    t = DIRECTION_TYPES[direction]
    if direction == "reverse" and cfg.overrides_in_reverse:
        t = (*t, "overrides")
    return t


def _step(e: Edge, force_inferred: bool) -> Step:
    ev = "inferred" if force_inferred and e.evidence in ("static", "observed") else e.evidence
    return Step(e.src, e.dst, e.type, ev, e.provenance, e.confidence)


def traverse(
    og: OverlayGraph,
    seeds: Iterable[str],
    direction: str,
    cfg: TraversalConfig | None = None,
    *,
    types: Sequence[str] | None = None,
) -> list[Reached]:
    """Reached nodes (seeds excluded) ordered by (depth, -weight, id)."""
    cfg = cfg or TraversalConfig()
    seeds = sorted({s for s in seeds if s in og})
    allowed = tuple(types) if types is not None else _types(direction, cfg)
    maxd = cfg.depth.get(direction, 0)
    visited = set(seeds)
    frontier: dict[str, tuple[float, tuple[Step, ...]]] = {s: (1.0, ()) for s in seeds}
    out: list[Reached] = []
    spent: Counter[str] = Counter()
    top = maxd + (1 if cfg.last_level_kinds else 0)
    for hop in range(1, top + 1):
        arrivals: dict[str, tuple[float, tuple[Step, ...], str]] = {}
        for node, (w, steps) in sorted(frontier.items()):
            for e in og.edges_from(node, allowed):
                if e.dst in visited or e.dst not in og:
                    continue
                if e.type == "defined_in" and og.kind(node) != "config_key":
                    continue  # structural containment is only followed from config keys
                dkind = og.kind(e.dst)
                if hop > maxd and dkind not in cfg.last_level_kinds:
                    continue
                nw = (
                    w
                    * P.EDGE_PRIOR.get(e.type, 0.3)
                    * e.confidence
                    * og.node(e.dst).get("hub_factor", 1.0)
                    * cfg.decay**hop
                )
                st = _step(e, e.type == "overrides" and direction == "reverse")
                cur = arrivals.get(e.dst)
                if cur is None or nw > cur[0] or (nw == cur[0] and e.type < cur[2]):
                    arrivals[e.dst] = (nw, (*steps, st), e.type)
        accepted: dict[str, tuple[float, tuple[Step, ...]]] = {}
        for dst, (nw, steps, etype) in sorted(arrivals.items(), key=lambda kv: (-kv[1][0], kv[0])):
            if len(accepted) >= cfg.top_n or len(out) + len(accepted) >= cfg.node_cap:
                break
            if spent[etype] >= cfg.edge_budget:
                continue
            spent[etype] += 1
            accepted[dst] = (nw, steps)
        frontier = {}
        for dst, (nw, steps) in sorted(accepted.items()):
            visited.add(dst)
            hub = og.node(dst).get("degree_all", 0) > cfg.hub_stop
            out.append(
                Reached(
                    dst, hop, nw, direction, steps, path_evidence([s.evidence for s in steps]), hub
                )  # fmt: skip
            )
            if og.kind(dst) not in LEAF_KINDS and hop < top and (not hub or dst in cfg.named):
                frontier[dst] = (nw, steps)
        if not frontier:
            break
    return sorted(out, key=lambda r: (r.depth, -r.weight, r.node))


# ---- the five questions --------------------------------------------------------------------
@dataclass(frozen=True)
class Answer:
    question: str
    subject: str
    direct: tuple[Reached, ...] = ()
    transitive: tuple[Reached, ...] = ()
    inferred: tuple[Reached, ...] = ()  # reached only through inferred/unknown links
    unknown_sites: tuple[str, ...] = ()  # unresolved call sites on the subject: not analysable
    note: str = ""

    @property
    def all(self) -> tuple[Reached, ...]:
        return (*self.direct, *self.transitive, *self.inferred)


def _split(question: str, subject: str, reached: Sequence[Reached], og: OverlayGraph,
           note: str = "") -> Answer:  # fmt: skip
    direct = [r for r in reached if r.kind == "direct" and r.evidence != "unknown"]
    trans = [r for r in reached if r.kind == "transitive"]
    inferred = [r for r in reached if r.kind == "inferred"]
    return Answer(question, subject, tuple(direct), tuple(trans), tuple(inferred),
                  tuple(unknown_sites(og, subject)), note)  # fmt: skip


def unknown_sites(og: OverlayGraph, node: str) -> list[str]:
    """Unresolved call sites / bases directly on `node` (evidence `unknown`), as text."""
    if node not in og:
        return []
    return sorted(
        {f"{e.dst} @ {e.provenance}" for e in og.edges_from(node)
         if not e.reverse and e.evidence == "unknown" and e.dst.startswith("unknown:")}
    )  # fmt: skip


def depends_on(og: OverlayGraph, node: str, cfg: TraversalConfig | None = None) -> Answer:
    """What does `node` depend on (callees, imports, config reads, base classes)."""
    cfg = cfg or TraversalConfig()
    return _split("depends_on", node, traverse(og, [node], "forward", cfg), og)


def depended_on_by(og: OverlayGraph, node: str, cfg: TraversalConfig | None = None) -> Answer:
    """What depends on `node` (callers, importers, config readers, subclasses, overriders)."""
    cfg = cfg or TraversalConfig()
    return _split("depended_on_by", node, traverse(og, [node], "reverse", cfg), og)


def config_affecting(og: OverlayGraph, node: str, cfg: TraversalConfig | None = None) -> Answer:
    """Config keys `node` reads (directly or through callees) and the services/classes that set
    them. Keys and sources only: values are not stored (value flow is P5-S13, not built)."""
    cfg = cfg or TraversalConfig()
    keys = [r for r in traverse(og, [node], "forward", cfg) if og.kind(r.node) == "config_key"]
    reached = list(keys)
    seen = {r.node for r in reached}
    for r in traverse(og, [node], "config", cfg):
        if r.node not in seen:
            reached.append(r)
    # keys read by callees: expand the config direction from each callee-read key
    for k in keys:
        for r in traverse(og, [k.node], "config", cfg.with_depth(config=1)):
            if r.node not in seen:
                seen.add(r.node)
                reached.append(replace(r, depth=k.depth + r.depth, steps=(*k.steps, *r.steps),
                                       evidence=path_evidence([s.evidence for s in (*k.steps, *r.steps)])))  # fmt: skip
    reached.sort(key=lambda r: (r.depth, -r.weight, r.node))
    return _split("config_affecting", node, reached, og,
                  "values are not stored; keys and their declaring sources only")  # fmt: skip


def tests_exercising(og: OverlayGraph, node: str, cfg: TraversalConfig | None = None,
                     via_dependants: bool = True) -> Answer:  # fmt: skip
    """Tests that cover `node` directly, plus (optionally) tests covering its callers."""
    cfg = cfg or TraversalConfig()
    tests = [r for r in traverse(og, [node], "tests", cfg) if og.kind(r.node) == "test"]
    if via_dependants:
        have = {r.node for r in tests}
        for dep in traverse(og, [node], "reverse", cfg.with_depth(reverse=2)):
            if og.kind(dep.node) in LEAF_KINDS:
                continue
            for t in traverse(og, [dep.node], "tests", cfg):
                if t.node not in have and og.kind(t.node) == "test":
                    have.add(t.node)
                    steps = (*dep.steps, *t.steps)
                    tests.append(Reached(t.node, dep.depth + t.depth, dep.weight * t.weight,
                                         "tests", steps,
                                         path_evidence([s.evidence for s in steps])))  # fmt: skip
    tests.sort(key=lambda r: (r.depth, -r.weight, r.node))
    return _split("tests_exercising", node, tests, og)


def what_else_could_change(og: OverlayGraph, node: str,
                           cfg: TraversalConfig | None = None) -> Answer:  # fmt: skip
    """Impact view: dependants to IMPACT depth, plus subclasses/overriders, config sharers."""
    cfg = cfg or IMPACT_CONFIG
    reached = [r for r in traverse(og, [node], "reverse", cfg) if og.kind(r.node) != "test"]
    return _split("what_else_could_change", node, reached, og)
