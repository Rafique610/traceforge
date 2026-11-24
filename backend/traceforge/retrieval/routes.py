"""HTTP route resolution: which handler serves `METHOD /path`.

The code graph has no route nodes, so an HTTP request seen in a symptom could not be linked to
its handler. This module reads framework decorators (`@router.get("/x")`, `@app.post("/y")`,
`APIRouter(prefix="/orders")`) from the source of the graph's non-test files and maps a request
to the handler's graph node. It is general (decorator shape, not endpoint names), read-only, and
used only to create graph anchors from a symptom; it adds no nodes or edges to the graph.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass

from traceforge.codeintel import Graph, symbol_at
from traceforge.codeintel.tests_map import is_test_file

_HTTP = {"get", "post", "put", "patch", "delete", "head", "options"}
_PARAM = re.compile(r"^\{[^}]*\}$")


@dataclass(frozen=True)
class Route:
    method: str
    template: str  # full path template, e.g. /orders/{order_id}/quote
    node_id: str  # graph id of the handler


def _const_str(node: ast.AST | None) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _prefixes(tree: ast.Module) -> dict[str, str]:
    """Module-level `name = APIRouter(prefix="/x")` -> {name: "/x"}."""
    out: dict[str, str] = {}
    for n in tree.body:
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call):
            for kw in n.value.keywords:
                if kw.arg == "prefix" and (p := _const_str(kw.value)) is not None:
                    for t in n.targets:
                        if isinstance(t, ast.Name):
                            out[t.id] = p
    return out


def route_index(graph: Graph) -> list[Route]:
    """All routes declared in the repo's non-test Python files (cached on the graph object)."""
    cached = getattr(graph, "_route_index", None)
    if cached is not None:
        return cached
    routes: list[Route] = []
    files = sorted(
        d["path"]
        for _n, d in graph.nx.nodes(data=True)
        if d.get("kind") == "file" and d.get("path", "").endswith(".py")
    )
    for rel in files:
        if is_test_file(rel):
            continue
        try:
            tree = ast.parse((graph.repo / rel).read_text("utf-8", errors="replace"))
        except (OSError, SyntaxError):
            continue
        prefixes = _prefixes(tree)
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for dec in fn.decorator_list:
                if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)):
                    continue
                if dec.func.attr not in _HTTP or not isinstance(dec.func.value, ast.Name):
                    continue
                arg = _const_str(dec.args[0]) if dec.args else None
                if arg is None:
                    arg = next((_const_str(k.value) for k in dec.keywords if k.arg == "path"), None)
                if arg is None:
                    continue
                nid = symbol_at(graph, rel, fn.lineno)
                if nid:
                    full = prefixes.get(dec.func.value.id, "") + arg
                    routes.append(Route(dec.func.attr.upper(), full or "/", nid))
    graph._route_index = routes  # type: ignore[attr-defined]
    return routes


def _segments(path: str) -> list[str]:
    return [s for s in path.split("?", 1)[0].split("/") if s]


def match_routes(graph: Graph, method: str, path: str) -> list[Route]:
    """Routes whose method and template match the request path (most literal segments first)."""
    want = _segments(path)
    hits: list[tuple[int, Route]] = []
    for r in route_index(graph):
        have = _segments(r.template)
        if r.method != method.upper() or len(have) != len(want):
            continue
        if all(_PARAM.match(h) or h == w for h, w in zip(have, want, strict=True)):
            hits.append((sum(1 for h in have if not _PARAM.match(h)), r))
    return [r for _k, r in sorted(hits, key=lambda x: (-x[0], x[1].template))]
