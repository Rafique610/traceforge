"""Index a small Python project: function and config-key nodes, graph edges, a code map.

Spike code (P0-S06). Not imported by backend/.
"""

import ast
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

WORD = re.compile(r"[A-Za-z][a-z]+|[A-Z]+(?![a-z])|\d+")
STOP = {"the", "a", "of", "to", "in", "and", "or", "is", "if", "for", "return", "self", "def"}


def tokens(text: str) -> list[str]:
    out = []
    for part in re.split(r"[^A-Za-z0-9]+", text):
        out += [w.lower() for w in WORD.findall(part)]
    return [t for t in out if len(t) > 1 and t not in STOP]


@dataclass
class Node:
    id: str  # "fn:orders.py::order_total" or "cfg:REDIS_HOST"
    path: str
    start: int
    end: int
    text: str
    kind: str  # "function" | "config_key"


@dataclass
class Index:
    root: Path
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))  # undirected
    code_map: str = ""

    def link(self, a: str, b: str) -> None:
        if a in self.nodes and b in self.nodes and a != b:
            self.edges[a].add(b)
            self.edges[b].add(a)

    def node_at(self, path: str, line: int) -> str | None:
        best = None
        for n in self.nodes.values():
            if n.path == path and n.start <= line <= n.end:
                if best is None or n.start >= self.nodes[best].start:
                    best = n.id
        return best

    def hops(self, sources: set[str], max_hops: int = 3) -> dict[str, int]:
        dist = {s: 0 for s in sources if s in self.nodes}
        frontier = list(dist)
        for d in range(1, max_hops + 1):
            nxt = []
            for n in frontier:
                for m in self.edges[n]:
                    if m not in dist:
                        dist[m] = d
                        nxt.append(m)
            frontier = nxt
        return dist


def build(root: Path) -> Index:
    idx = Index(root=root)
    field_to_key: dict[str, str] = {}
    trees = {}
    for py in sorted(root.glob("*.py")):
        rel = py.name
        src = py.read_text(encoding="utf-8")
        tree = ast.parse(src)
        trees[rel] = (tree, src)
        for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
            nid = f"fn:{rel}::{fn.name}"
            idx.nodes[nid] = Node(
                nid, rel, fn.lineno, fn.end_lineno, ast.get_source_segment(src, fn), "function"
            )
            for kw in [k for c in ast.walk(fn) if isinstance(c, ast.Call) for k in c.keywords]:
                keys = [
                    a.value
                    for a in ast.walk(kw.value)
                    if isinstance(a, ast.Constant) and isinstance(a.value, str) and a.value.isupper()
                ]
                if kw.arg and keys:
                    field_to_key[kw.arg] = keys[0]
    for i, line in enumerate((root / "compose.yaml").read_text(encoding="utf-8").splitlines(), 1):
        m = re.match(r"\s+([A-Z_]+):\s*\$\{", line)
        if m:
            nid = f"cfg:{m.group(1)}"
            idx.nodes[nid] = Node(nid, "compose.yaml", i, i, line.strip(), "config_key")
    names = {n.id.split("::")[1]: n.id for n in idx.nodes.values() if n.kind == "function"}
    for rel, (tree, _src) in trees.items():
        for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
            nid = f"fn:{rel}::{fn.name}"
            for node in ast.walk(fn):
                if isinstance(node, ast.Call):  # calls: name() or module.name()
                    f = node.func
                    callee = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
                    if callee in names:
                        idx.link(nid, names[callee])
                    for a in node.args:  # env("KEY", ...) reads a config key
                        if (
                            isinstance(a, ast.Constant)
                            and isinstance(a.value, str)
                            and f"cfg:{a.value}" in idx.nodes
                        ):
                            idx.link(nid, f"cfg:{a.value}")
                if isinstance(node, ast.Attribute) and node.attr in field_to_key:  # cfg.redis_host
                    idx.link(nid, f"cfg:{field_to_key[node.attr]}")
    lines = []
    for rel, (tree, _src) in trees.items():
        lines.append(rel)
        for fn in [n for n in tree.body if isinstance(n, ast.FunctionDef)]:
            lines.append(f"  def {fn.name}({', '.join(a.arg for a in fn.args.args)})")
    lines.append("compose.yaml: " + ", ".join(n.id[4:] for n in idx.nodes.values() if n.kind == "config_key"))
    idx.code_map = "\n".join(lines)
    return idx
