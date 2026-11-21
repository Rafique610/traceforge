"""Code map (D22): file -> classes/functions with signatures, no bodies. Built from the graph."""

from collections import defaultdict
from pathlib import Path

from .graph import Graph


def approx_tokens(text: str) -> int:
    """chars/4 estimate (same approximation as the limits report); not a real tokenizer."""
    return (len(text) + 3) // 4


def code_map(
    graph: Graph,
    repo_path: str | Path | None = None,
    *,
    docstrings: bool = False,
    include_tests: bool = True,
) -> str:
    """Outline text. `repo_path` is accepted for API symmetry; paths come from the graph.

    Deterministic: files sorted, members in source order.
    """
    by_file: dict[str, list[tuple[int, int, str, dict]]] = defaultdict(list)
    cfg_by_file: dict[str, list[str]] = defaultdict(list)
    services, tests = [], defaultdict(list)
    for nid, d in graph.nx.nodes(data=True):
        k = d["kind"]
        if k in ("function", "method", "class"):
            by_file[d["path"]].append((d["start"], d["end"], nid, d))
        elif k == "test":
            tests[d["path"]].append(d["qualname"])
        elif k == "config_key":
            cfg_by_file[d["path"]].append(d["name"])
        elif k == "service":
            services.append(d["name"])
    lines = []
    for path in sorted(set(by_file) | set(tests)):
        if not include_tests and path in tests and path not in by_file:
            continue
        lines.append(path)
        for _s, _e, _nid, d in sorted(by_file.get(path, []), key=lambda x: (x[0], -x[1], x[2])):
            depth = d["qualname"].count(".")
            doc = f"  # {d['doc']}" if docstrings and d.get("doc") else ""
            lines.append("  " * (depth + 1) + d["signature"] + doc)
        if include_tests and tests.get(path):
            lines.append("  tests: " + ", ".join(tests[path]))
    for path in sorted(cfg_by_file):
        lines.append(f"{path}: " + ", ".join(sorted(set(cfg_by_file[path]))))
    if services:
        lines.append("services: " + ", ".join(sorted(services)))
    return "\n".join(lines)
