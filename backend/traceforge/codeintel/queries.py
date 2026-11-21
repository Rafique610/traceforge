"""Graph queries: distance, neighbors, impact sets (D23), signature changes, weights, stats."""

import math
from collections import Counter, deque
from dataclasses import dataclass, field
from heapq import heappop, heappush

from .config import UNKNOWN_PREFIX
from .graph import Graph


def _bfs(adj: dict[str, list[str]], start: str, limit: int | None, goal: str | None = None):
    dist = {start: 0}
    q = deque([start])
    while q:
        n = q.popleft()
        if n == goal or (limit is not None and dist[n] >= limit):
            continue
        for m in adj.get(n, ()):
            if m not in dist:
                dist[m] = dist[n] + 1
                q.append(m)
    return dist


def distance(graph: Graph, a: str, b: str, edge_types: tuple[str, ...] | None = None) -> int | None:
    """Shortest hop count over the undirected view, ignoring `unknown:` nodes; None if unreachable.

    Default edge types: graph.config.distance_edge_types (calls, config binding, compose).
    Pass edge_types=() to walk every forward edge type.
    """
    if (
        a not in graph
        or b not in graph
        or a.startswith(UNKNOWN_PREFIX)
        or b.startswith(UNKNOWN_PREFIX)
    ):
        return None
    if a == b:
        return 0
    types = graph.config.distance_edge_types if edge_types is None else (edge_types or None)
    return _bfs(graph.adjacency(types), a, None, b).get(b)


def neighbors(
    graph: Graph,
    node: str,
    hops: int | None = None,
    edge_types: tuple[str, ...] | None = None,
    expand_hubs: bool = True,
) -> list[tuple[str, int]]:
    """(node, hops) within `hops` (<=2), ordered by (hops, id). Default: all edge types."""
    hops = min(hops if hops is not None else graph.config.max_neighbor_hops, 2)
    if node not in graph:
        return []
    adj = graph.adjacency(tuple(edge_types) if edge_types else None)
    if not expand_hubs:
        thr = graph.config.hub_degree_threshold
        adj = {n: ([] if graph.node(n)["degree"] > thr else v) for n, v in adj.items()}
        adj[node] = graph.adjacency(tuple(edge_types) if edge_types else None).get(node, [])
    d = _bfs(adj, node, hops)
    return sorted(((n, h) for n, h in d.items() if n != node), key=lambda x: (x[1], x[0]))


def edge_cost(graph: Graph, data: dict) -> float:
    """Lower = closer. Stronger edge types (higher weight) and confident edges cost less."""
    return 1.0 / max(data["weight"] * data["confidence"], 1e-6)


def weighted_distances(graph: Graph, source: str, max_cost: float) -> dict[str, float]:
    """Dijkstra over forward edges (undirected), cost = edge_cost * hub penalty of the entered node.

    Hub down-weighting: entering a node of degree d > hub threshold costs 1/hub_factor more.
    """
    best = {source: 0.0}
    heap = [(0.0, source)]
    while heap:
        c, n = heappop(heap)
        if c > best.get(n, math.inf):
            continue
        for _u, v, d in list(graph.nx.out_edges(n, data=True)):
            if d["reverse"] or graph.node(v)["kind"] == "unknown":
                continue
            nc = c + edge_cost(graph, d) / graph.node(v)["hub_factor"]
            if nc <= max_cost and nc < best.get(v, math.inf):
                best[v] = nc
                heappush(heap, (nc, v))
        for u, _v, d in list(graph.nx.in_edges(n, data=True)):
            if not d["reverse"] or graph.node(u)["kind"] == "unknown":
                continue
            nc = c + edge_cost(graph, d) / graph.node(u)["hub_factor"]
            if nc <= max_cost and nc < best.get(u, math.inf):
                best[u] = nc
                heappush(heap, (nc, u))
    return best


@dataclass(frozen=True)
class ImpactEntry:
    node: str
    depth: int
    via: str  # reverse edge type that reached it
    provenance: str
    breaking: bool  # reached directly from a signature-changed symbol


@dataclass
class ImpactSet:
    changed: list[str]
    entries: list[ImpactEntry] = field(default_factory=list)

    @property
    def symbols(self) -> list[str]:
        return [e.node for e in self.entries]

    @property
    def tests(self) -> list[str]:
        return [e.node for e in self.entries if e.node.startswith("test:")]

    @property
    def files(self) -> list[str]:
        return sorted({e.node for e in self.entries if e.node.startswith("file:")})


_IMPACT_VIA = ("called_by", "read_by", "imported_by", "covered_by", "declared_by", "env_of")


def impact_set(
    graph: Graph,
    changed_symbols: list[str] | set[str],
    signature_changed: set[str] | frozenset[str] = frozenset(),
    max_depth: int | None = None,
) -> ImpactSet:
    """Everything that depends on the changed symbols, via reverse edges (cycle safe).

    Callers and config readers propagate transitively; tests and importing files are leaves.
    `breaking` marks depth-1 callers of a symbol in `signature_changed`.
    """
    max_depth = max_depth if max_depth is not None else graph.config.impact_max_depth
    changed = sorted(c for c in changed_symbols if c in graph)
    seen = set(changed)
    out = ImpactSet(changed)
    q = deque((c, 0) for c in changed)
    while q:
        n, d = q.popleft()
        if d >= max_depth:
            continue
        for _u, v, data in sorted(
            graph.nx.out_edges(n, data=True), key=lambda x: (x[1], x[2]["provenance"])
        ):
            if not data["reverse"] or data["type"] not in _IMPACT_VIA or v in seen:
                continue
            seen.add(v)
            brk = d == 0 and n in signature_changed and data["type"] == "called_by"
            out.entries.append(ImpactEntry(v, d + 1, data["type"], data["provenance"], brk))
            if graph.node(v)["kind"] not in ("test", "file"):
                q.append((v, d + 1))
    out.entries.sort(key=lambda e: (e.depth, e.node))
    return out


def impact(graph: Graph, symbol: str) -> list[str]:
    """P2-S02 `impact(symbol) -> list[symbol]`."""
    return impact_set(graph, [symbol]).symbols


def signature_changes(old: Graph, new: Graph) -> dict[str, tuple[str | None, str | None]]:
    """node id -> (old, new) signature for symbols whose signature differs, appeared or vanished."""
    out = {}
    for nid in sorted(set(old.nx.nodes) | set(new.nx.nodes)):
        a = old.nx.nodes[nid].get("signature") if nid in old else None
        b = new.nx.nodes[nid].get("signature") if nid in new else None
        if (a or b) and a != b:
            out[nid] = (a, b)
    return out


def changed_symbols(old: Graph, new: Graph) -> list[str]:
    """Function/class/test nodes whose source hash or signature differs (or are added/removed)."""
    out = []
    for nid in sorted(set(old.nx.nodes) | set(new.nx.nodes)):
        a, b = (g.nx.nodes[nid] if nid in g else {} for g in (old, new))
        if (a.get("hash"), a.get("signature")) != (b.get("hash"), b.get("signature")) and (
            a.get("signature") or b.get("signature")
        ):
            out.append(nid)
    return out


def stats(graph: Graph) -> dict:
    nodes = Counter(d["kind"] for _n, d in graph.nx.nodes(data=True))
    fwd = Counter(d["type"] for _u, _v, d in graph.nx.edges(data=True) if not d["reverse"])
    rev = sum(1 for _u, _v, d in graph.nx.edges(data=True) if d["reverse"])
    unknown = sum(
        1 for _u, _v, d in graph.nx.edges(data=True) if d.get("unknown") and not d["reverse"]
    )
    return {
        "nodes": graph.nx.number_of_nodes(),
        "nodes_by_kind": dict(sorted(nodes.items())),
        "forward_edges": sum(fwd.values()),
        "reverse_edges": rev,
        "edges_by_type": dict(sorted(fwd.items())),
        "unknown_call_edges": unknown,
        **graph.stats,
    }
