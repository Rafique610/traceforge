"""Subgraph export (JSON / Mermaid) for the reviewer UI, straight from the real graph."""

import json

from .graph import Graph
from .queries import neighbors


def subgraph_nodes(
    graph: Graph,
    centers: list[str],
    hops: int = 1,
    edge_types: tuple[str, ...] | None = None,
    max_nodes: int = 60,
) -> list[str]:
    """Centers plus neighbours within `hops`, nearest first, capped at max_nodes."""
    keep = [c for c in dict.fromkeys(centers) if c in graph]
    for c in list(keep):
        for n, _h in neighbors(graph, c, hops, edge_types):
            if n not in keep:
                keep.append(n)
    return keep[:max_nodes]


def export_subgraph(
    graph: Graph,
    centers: list[str],
    hops: int = 1,
    fmt: str = "json",
    edge_types: tuple[str, ...] | None = None,
    max_nodes: int = 60,
    include_unknown: bool = True,
) -> str:
    """fmt="json" -> {"nodes","edges"}; fmt="mermaid" -> flowchart text.

    Edges are forward edges between kept nodes (plus `unknown:` call targets of kept nodes),
    each carrying type, source, confidence, provenance (file:line).
    """
    keep = subgraph_nodes(graph, centers, hops, edge_types, max_nodes)
    kept = set(keep)
    edges = []
    for u, v, d in graph.nx.edges(data=True):
        if d["reverse"] or u not in kept or (edge_types and d["type"] not in edge_types):
            continue
        is_unk = graph.node(v)["kind"] == "unknown"
        if v in kept or (include_unknown and is_unk):
            edges.append((u, v, d))
            kept.add(v)
    edges.sort(key=lambda e: (e[0], e[1], e[2]["type"], e[2]["provenance"]))
    node_ids = [n for n in keep] + sorted(n for n in kept if n not in set(keep))
    nodes = []
    for n in node_ids:
        d = graph.node(n)
        nodes.append(
            {
                "id": n,
                "kind": d["kind"],
                "label": d.get("qualname") or d.get("name") or d.get("path") or n,
                "path": d.get("path"),
                "start": d.get("start"),
                "end": d.get("end"),
                "center": n in centers,
            }
        )
    ed = [
        {
            "source": u,
            "target": v,
            "type": d["type"],
            "source_kind": d["source"],
            "confidence": d["confidence"],
            "provenance": d["provenance"],
        }
        for u, v, d in edges
    ]
    if fmt == "json":
        return json.dumps({"nodes": nodes, "edges": ed}, indent=2)
    if fmt != "mermaid":
        raise ValueError("fmt must be 'json' or 'mermaid'")
    ids = {n["id"]: f"n{i}" for i, n in enumerate(nodes)}
    out = ["flowchart LR"]
    for n in nodes:
        label = f"{n['kind']}: {n['label']}".replace('"', "'")
        out.append(f'  {ids[n["id"]]}["{label}"]')
    for e in ed:
        arrow = "-.->" if e["confidence"] < 0.5 else "-->"
        lab = f"{e['type']} @ {e['provenance']}".replace('"', "'")
        out.append(f'  {ids[e["source"]]} {arrow}|"{lab}"| {ids[e["target"]]}')
    return "\n".join(out)
