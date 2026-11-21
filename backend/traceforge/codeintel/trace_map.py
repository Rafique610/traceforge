"""Trace/log location -> graph symbol (used by retrieval anchors)."""

from .graph import Graph

_SPAN_KINDS = ("function", "method", "test", "class")


def symbol_at(graph: Graph, path: str, line: int) -> str | None:
    """Innermost function/method/test (else class) whose span contains `path:line`.

    `path` is repo-relative POSIX; an absolute path under the repo is accepted.
    """
    p = path.replace("\\", "/")
    root = graph.repo.as_posix().rstrip("/") + "/"
    if p.lower().startswith(root.lower()):
        p = p[len(root) :]
    best, best_key = None, None
    for nid, d in graph.nx.nodes(data=True):
        if d.get("path") != p or d["kind"] not in _SPAN_KINDS or not d["start"] <= line <= d["end"]:
            continue
        key = (d["kind"] != "class", d["start"], -d["end"])  # prefer callables, then innermost
        if best_key is None or key > best_key:
            best, best_key = nid, key
    return best
