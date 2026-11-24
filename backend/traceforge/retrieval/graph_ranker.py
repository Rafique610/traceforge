"""Graph features (G arm only): proximity to anchors, <=2-hop expansion, config-key binding,
test link and an uncertainty penalty. L never imports this module's outputs.

Proximity = 1/(1+cost) where cost sums `1/(edge weight * confidence)` along the best path of at
most `MAX_HOPS` hops (stronger edge types are cheaper: config binding > call), and entering a hub
node costs `1/hub_factor` more (down-weights hubs such as a `settings()` factory).
`uncertain` = 1 - the lowest edge confidence on that path (unknown-call edges carry low confidence).
"""

import heapq
from dataclasses import dataclass

from traceforge.codeintel import Graph
from traceforge.codeintel.config import REVERSE_OF, UNKNOWN_PREFIX
from traceforge.retrieval.anchors import Anchor

MAX_HOPS = 2
_FORWARD = {v: k for k, v in REVERSE_OF.items()}
BINDING_TYPES = ("reads_config", "declares_config", "service_env")
WALK_TYPES = ("calls", "reads_config", "declares_config", "service_env", "service_runs",
              "depends_on", "tests_covers")  # fmt: skip


@dataclass(frozen=True)
class GraphFeatures:
    """Each flag switches one documented G feature; all off => G == L (fairness test)."""

    proximity: bool = True  # graph proximity term for BM25 candidates
    expansion: bool = True  # add <=2-hop neighbours that are not in the BM25 top-k
    binding: bool = True  # walk config-binding edges; key <-> settings field costs no hop
    test_link: bool = True  # tests covering an anchor
    uncertainty: bool = True  # penalty for low-confidence paths
    hubs: bool = True  # hub down-weighting
    symptom_anchors: bool = True  # anchors from the symptom (failing tests -> covered code, routes)

    @property
    def any(self) -> bool:
        return (
            self.proximity
            or self.expansion
            or self.test_link
            or self.uncertainty
            or self.symptom_anchors
        )


NO_GRAPH = GraphFeatures(False, False, False, False, False, False, False)


@dataclass(frozen=True)
class GraphInfo:
    node_id: str
    prox: float
    hops: int
    cost: float
    path: str  # human-readable provenance, e.g. "a.py::f -calls@a.py:12-> b.py::g"
    uncertain: float
    test_link: float


def _label(graph: Graph, nid: str) -> str:
    """Short node label for provenance strings: `file.py::qualname`, or the config key."""
    d = graph.node(nid)
    if d["kind"] == "config_key":
        return d["name"]
    if "qualname" in d:
        return f"{d['path'].rsplit('/', 1)[-1]}::{d['qualname']}"
    return nid


def _is_binding(a: dict, b: dict) -> bool:
    """A config key and the settings field that reads it are one unit (binding link, no hop)."""
    return {a["kind"], b["kind"]} == {"config_key", "settings_field"}


def _fwd(t: str) -> str:
    return _FORWARD.get(t, t)


def _walk(graph: Graph, anchor: Anchor, feats: GraphFeatures) -> dict[str, tuple]:
    """Best (cost, hops, min_conf, path) per node within MAX_HOPS hops of `anchor`."""
    types = tuple(t for t in WALK_TYPES if feats.binding or t not in BINDING_TYPES)
    best: dict[tuple[str, int], float] = {(anchor.node_id, 0): 0.0}
    found: dict[str, tuple] = {}
    heap = [(0.0, 0, anchor.node_id, 1.0, _label(graph, anchor.node_id))]
    while heap:
        cost, hops, n, conf, path = heapq.heappop(heap)
        if cost > best.get((n, hops), float("inf")):
            continue
        at_limit = hops >= MAX_HOPS  # only a key <-> settings-field binding (no hop) goes further
        edges = sorted(
            graph.nx.out_edges(n, data=True), key=lambda x: (x[1], x[2]["type"], x[2]["provenance"])
        )
        for _u, v, d in edges:
            if _fwd(d["type"]) not in types or v.startswith(UNKNOWN_PREFIX):
                continue
            vd = graph.node(v)
            if vd["kind"] == "unknown":
                continue
            if at_limit and not (feats.binding and _is_binding(graph.node(n), vd)):
                continue
            c = d["confidence"]
            if d.get("unknown"):
                c = min(c, graph.config.unknown_confidence)
            step, dh = 1.0 / max(d["weight"] * c, 1e-6), 1
            if feats.hubs:
                step /= vd["hub_factor"]
            if feats.binding and _is_binding(graph.node(n), vd):  # key and its settings field
                step, dh = 0.0, 0
            nc, nh = cost + step, hops + dh
            if nc >= best.get((v, nh), float("inf")):
                continue
            best[(v, nh)] = nc
            npath = f"{path} -{d['type']}@{d['provenance']}-> {_label(graph, v)}"
            nconf = min(conf, c)
            heapq.heappush(heap, (nc, nh, v, nconf, npath))
            if v != anchor.node_id and (v not in found or nc < found[v][0]):
                found[v] = (nc, nh, nconf, npath, _fwd(d["type"]))
    return found


def graph_scores(graph: Graph, anchors: list[Anchor], feats: GraphFeatures) -> dict[str, GraphInfo]:
    """Best GraphInfo per node over all anchors (anchor strength scales proximity)."""
    out: dict[str, GraphInfo] = {}
    for a in anchors:
        for nid, (cost, hops, conf, path, last) in sorted(_walk(graph, a, feats).items()):
            prox = a.strength / (1.0 + cost)
            tl = 1.0 if feats.test_link and last == "tests_covers" and hops == 1 else 0.0
            cur = out.get(nid)
            if cur is None or prox > cur.prox:
                out[nid] = GraphInfo(
                    nid, prox, hops, cost, path, (1.0 - conf) if feats.uncertainty else 0.0, tl
                )
            elif tl and not cur.test_link:
                out[nid] = GraphInfo(nid, cur.prox, cur.hops, cur.cost, cur.path, cur.uncertain, tl)
    return out
