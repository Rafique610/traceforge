# ruff: noqa: E501
"""Graph overlay (P5-S12): a COPY of a codeintel Graph plus inheritance/override edges, name-resolved
call candidates, evidence classes on every edge and runtime ("observed") marks.

The original `Graph` is never mutated: `build_overlay` copies the networkx graph and works on the
copy. `codeintel/` is not edited. Evidence classes (design section 3):
  static   found by AST/compose/settings parsing with confidence >= 0.85
  observed only for edges between two supplied runtime facts (adjacent trace frames, failing test
           -> frame it covers); never created from the static graph alone
  inferred confidence < 0.85 (name-referenced tests, name-resolved calls, attribute guesses)
  unknown  edge to an `unknown:` node (dynamic dispatch, external base class, string-built names)
"""

from __future__ import annotations

import ast
import builtins
import re
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path

import networkx as nx

from traceforge.analysis import priors as P
from traceforge.codeintel.builder import ModuleIndex
from traceforge.codeintel.config import REVERSE_OF, UNKNOWN_PREFIX
from traceforge.codeintel.graph import Graph
from traceforge.codeintel.trace_map import symbol_at

OVERLAY_REVERSE = {
    "inherits": "subclassed_by",
    "overrides": "overridden_by",
}
ALL_REVERSE = {**REVERSE_OF, **OVERLAY_REVERSE}
_NAME_TAIL = re.compile(r"\.([A-Za-z_]\w*)$")
_ORDER = {"unknown": 0, "inferred": 1, "static": 2, "observed": 3}


@dataclass(frozen=True)
class Edge:
    src: str
    dst: str
    type: str
    reverse: bool
    confidence: float
    evidence: str
    provenance: str
    overlay: bool = False


@dataclass(frozen=True)
class RuntimeFacts:
    """Runtime artifacts supplied by the caller (never gold, never hidden tests)."""

    frames: Sequence[tuple[str, int]] = ()  # (repo-relative path, line), outermost first
    failing_tests: Sequence[str] = ()  # visible test ids, e.g. "tests/test_x.py::test_y"


@dataclass
class OverlayGraph:
    base: Graph
    nx: nx.MultiDiGraph
    observed: dict[str, list[str]] = field(default_factory=dict)
    stats: dict = field(default_factory=dict)

    def node(self, nid: str) -> dict:
        return self.nx.nodes[nid]

    def __contains__(self, nid: str) -> bool:
        return nid in self.nx

    def kind(self, nid: str) -> str:
        return self.nx.nodes[nid]["kind"]

    def path_of(self, nid: str) -> str | None:
        return self.nx.nodes[nid].get("path") if nid in self.nx else None

    def edges_from(self, nid: str, types: Iterable[str] | None = None) -> Iterator[Edge]:
        """Out-edges of `nid`, deterministic order (dst, type, provenance)."""
        want = set(types) if types is not None else None
        rows = []
        for _u, v, d in self.nx.out_edges(nid, data=True):
            if want is None or d["type"] in want:
                rows.append((v, d["type"], d["provenance"], d))
        for v, t, prov, d in sorted(rows, key=lambda r: r[:3]):
            yield Edge(nid, v, t, d["reverse"], d.get("confidence", 1.0), d["evidence"], prov,
                       bool(d.get("overlay")))  # fmt: skip

    def has_edge_type(self, nid: str, etype: str) -> bool:
        return any(d["type"] == etype for _u, _v, d in self.nx.out_edges(nid, data=True))


def classify_edge(g: nx.MultiDiGraph, u: str, v: str, data: dict) -> str:
    if (
        data.get("unknown")
        or g.nodes[u]["kind"] == "unknown"
        or g.nodes[v]["kind"] == "unknown"
        or u.startswith(UNKNOWN_PREFIX)
        or v.startswith(UNKNOWN_PREFIX)
    ):
        return "unknown"
    return "static" if data.get("confidence", 1.0) >= P.STATIC_MIN_CONFIDENCE else "inferred"


def path_evidence(classes: Sequence[str]) -> str:
    """Weakest link: unknown < inferred < static; all-observed (non-empty) stays observed."""
    if not classes:
        return "static"
    worst = min(classes, key=lambda c: _ORDER[c])
    if worst == "observed":
        return "observed"
    if worst == "static" and all(c in ("static", "observed") for c in classes):
        return "static"
    return worst


def _is_hidden(path: str | None, hidden: Sequence[str]) -> bool:
    if not path:
        return False
    p = path.replace("\\", "/").lstrip("./")
    for pat in hidden:
        pat = pat.replace("\\", "/").strip("/")
        if pat and (p == pat or p.startswith(pat + "/") or fnmatch(p, pat)):
            return True
    return False


# ---- inheritance ---------------------------------------------------------------------------
def _dotted(node: ast.AST) -> list[str] | None:
    """`a.b.C` -> ['a','b','C']; `Gen[T]` -> chain of the subscripted value; else None."""
    if isinstance(node, ast.Subscript):
        return _dotted(node.value)
    names: list[str] = []
    while isinstance(node, ast.Attribute):
        names.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        names.append(node.id)
        return names[::-1]
    return None


def _class_defs(tree: ast.Module) -> Iterator[tuple[ast.ClassDef, str]]:
    def walk(body, prefix):
        for n in body:
            if isinstance(n, ast.ClassDef):
                q = f"{prefix}.{n.name}" if prefix else n.name
                yield n, q
                yield from walk(n.body, q)
            elif isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef):
                q = f"{prefix}.{n.name}" if prefix else n.name
                yield from walk(n.body, q)

    yield from walk(tree.body, "")


@dataclass
class _FileInfo:
    tree: ast.Module
    from_imports: dict[str, tuple[int, str, str]]  # local -> (level, module, name)
    mod_imports: dict[str, str]  # local alias -> dotted module


def _file_info(src: str) -> _FileInfo | None:
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return None
    fi, mi = {}, {}
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom):
            for a in n.names:
                fi[a.asname or a.name] = (n.level, n.module or "", a.name)
        elif isinstance(n, ast.Import):
            for a in n.names:
                mi[a.asname or a.name.split(".")[0]] = a.name if a.asname else a.name.split(".")[0]
                if not a.asname and "." in a.name:
                    mi[a.name] = a.name
    return _FileInfo(tree, fi, mi)


def _add_edge(g: nx.MultiDiGraph, u: str, v: str, etype: str, prov: str, conf: float, **extra):
    base = {"source": "ast", "confidence": conf, "provenance": prov, "overlay": True,
            "weight": 0.6, **extra}  # fmt: skip
    g.add_edge(u, v, key=f"{etype}@{prov}", reverse=False, type=etype, **base)
    g.add_edge(v, u, key=f"{ALL_REVERSE[etype]}@{prov}", reverse=True,
               **{**base, "type": ALL_REVERSE[etype]})  # fmt: skip


def _add_unknown_node(g: nx.MultiDiGraph, uid: str, name: str) -> None:
    if uid not in g:
        g.add_node(uid, kind="unknown", name=name, degree=0, degree_all=0, hub_factor=1.0)


def _add_inheritance(g: nx.MultiDiGraph, repo: Path, stats: dict) -> None:
    py_files = sorted(
        d["path"]
        for _n, d in g.nodes(data=True)
        if d["kind"] == "file" and d["path"].endswith(".py")
    )
    idx = ModuleIndex(py_files, repo.name if (repo / "__init__.py").exists() else None)
    infos: dict[str, _FileInfo] = {}
    for rel in py_files:
        try:
            fi = _file_info((repo / rel).read_text(encoding="utf-8", errors="replace"))
        except OSError:
            fi = None
        if fi:
            infos[rel] = fi
    top_classes: dict[str, dict[str, str]] = {}  # rel -> {name: class node id}
    for rel, fi in infos.items():
        top_classes[rel] = {
            c.name: f"class:{rel}::{q}" for c, q in _class_defs(fi.tree) if "." not in q
        }

    def resolve_in_file(rel: str, name: str) -> str | None:
        return top_classes.get(rel, {}).get(name)

    def resolve(rel: str, dotted: list[str]) -> str | None:
        fi = infos[rel]
        head = dotted[0]
        if len(dotted) == 1:
            local = resolve_in_file(rel, head)
            if local:
                return local
            imp = fi.from_imports.get(head)
            if imp:
                lvl, mod, name = imp
                tgt = idx.relative(rel, lvl, mod) if lvl else idx.lookup(mod, rel)
                return resolve_in_file(tgt, name) if tgt else None  # one import hop
            return None
        # attribute form: module alias . Class
        mod_path: str | None = None
        imp = fi.from_imports.get(head)
        if imp:
            lvl, mod, name = imp
            dotted_mod = f"{mod}.{name}" if mod else name
            mod_path = idx.relative(rel, lvl, dotted_mod) if lvl else idx.lookup(dotted_mod, rel)
        elif head in fi.mod_imports:
            full = ".".join([fi.mod_imports[head], *dotted[1:-1]])
            mod_path = idx.lookup(full, rel)
        return resolve_in_file(mod_path, dotted[-1]) if mod_path else None

    n_inh = n_unknown = 0
    bases_of: dict[str, list[str]] = {}
    for rel in sorted(infos):
        for cdef, qual in _class_defs(infos[rel].tree):
            cid = f"class:{rel}::{qual}"
            if cid not in g:
                continue
            for b in cdef.bases:
                dotted = _dotted(b)
                prov = f"{rel}:{getattr(b, 'lineno', cdef.lineno)}"
                tgt = resolve(rel, dotted) if dotted else None
                if tgt and tgt in g and tgt != cid:
                    _add_edge(g, cid, tgt, "inherits", prov, 1.0)
                    bases_of.setdefault(cid, []).append(tgt)
                    n_inh += 1
                    continue
                text = ast.unparse(b)
                if dotted and len(dotted) == 1 and hasattr(builtins, dotted[0]):
                    continue  # object, Exception, ... : external but known stdlib builtin
                uid = f"{UNKNOWN_PREFIX}base:{text}"
                _add_unknown_node(g, uid, text)
                _add_edge(g, cid, uid, "inherits", prov, P.NAME_RESOLVE_CONF / 2, unknown=True)
                n_unknown += 1
    # overrides: a method overrides the nearest ancestor's method of the same name
    methods: dict[str, dict[str, str]] = {}
    for u, v, d in g.edges(data=True):
        if d["type"] == "defined_in" and not d["reverse"] and v.startswith("class:"):
            if g.nodes[u]["kind"] == "method":
                methods.setdefault(v, {})[g.nodes[u]["name"]] = u
    n_over = 0
    for cid in sorted(bases_of):
        seen, queue = {cid}, list(bases_of[cid])
        found: dict[str, str] = {}
        while queue:
            a = queue.pop(0)
            if a in seen:
                continue
            seen.add(a)
            for name, mid in sorted(methods.get(a, {}).items()):
                found.setdefault(name, mid)
            queue.extend(bases_of.get(a, []))
        for name, mid in sorted(methods.get(cid, {}).items()):
            if name in found:
                prov = f"{g.nodes[mid]['path']}:{g.nodes[mid]['start']}"
                _add_edge(g, mid, found[name], "overrides", prov, 1.0)
                n_over += 1
    stats.update(inherits=n_inh, unknown_bases=n_unknown, overrides=n_over)


def _add_name_resolution(g: nx.MultiDiGraph, stats: dict) -> None:
    """`unknown:x.name` call sites become inferred `calls` edges to the in-repo methods called
    `name` (<= NAME_RESOLVE_MAX candidates). The unknown edge stays; nothing is claimed static."""
    by_name: dict[str, list[str]] = {}
    for nid, d in g.nodes(data=True):
        if d["kind"] == "method":
            by_name.setdefault(d["name"], []).append(nid)
    todo = []
    for u, v, k, d in g.edges(keys=True, data=True):
        if (
            d["type"] == "calls"
            and not d["reverse"]
            and d.get("unknown")
            and v.startswith(UNKNOWN_PREFIX)
        ):
            todo.append((u, v, k, d))
    added = 0
    for u, v, _k, d in sorted(todo, key=lambda t: (t[0], t[1], t[3]["provenance"])):
        m = _NAME_TAIL.search(g.nodes[v].get("name", ""))
        cands = sorted(c for c in by_name.get(m.group(1), []) if c != u) if m else []
        if 0 < len(cands) <= P.NAME_RESOLVE_MAX:
            for c in cands:
                _add_edge(
                    g, u, c, "calls", d["provenance"], P.NAME_RESOLVE_CONF, name_resolved=True
                )
                added += 1
            d["name_resolved_n"] = len(cands)
    stats["name_resolved_edges"] = added


_DYNAMIC_NAMES = {"import_module", "__import__", "eval", "exec"}


def _func_defs(tree: ast.Module) -> Iterator[tuple[ast.AST, str]]:
    def walk(body, prefix):
        for n in body:
            if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                q = f"{prefix}.{n.name}" if prefix else n.name
                if not isinstance(n, ast.ClassDef):
                    yield n, q
                yield from walk(n.body, q)

    yield from walk(tree.body, "")


def _own_nodes(fn: ast.AST) -> Iterator[ast.AST]:
    stack = list(getattr(fn, "body", []))[::-1]
    while stack:
        n = stack.pop()
        yield n
        if not isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            stack.extend(reversed(list(ast.iter_child_nodes(n))))


def _dynamic_kind(n: ast.AST) -> str | None:
    """Reflection / string-built imports: `unknown` by design (design section 3)."""
    if isinstance(n, ast.Call):
        name = (
            n.func.id
            if isinstance(n.func, ast.Name)
            else (n.func.attr if isinstance(n.func, ast.Attribute) else None)
        )
        nonconst = bool(n.args) and not isinstance(n.args[0], ast.Constant)
        if name in ("import_module", "__import__") and nonconst:
            return "dynamic import"
        if name in ("eval", "exec"):
            return "eval/exec"
        if (
            name in ("getattr", "setattr")
            and len(n.args) > 1
            and not isinstance(n.args[1], ast.Constant)
        ):
            return "getattr with a computed name"
    if isinstance(n, ast.Subscript) and isinstance(n.value, ast.Call):
        f = n.value.func
        if isinstance(f, ast.Name) and f.id in ("globals", "locals"):
            return "globals()/locals() lookup"
    return None


def _add_dynamic_markers(g: nx.MultiDiGraph, repo: Path, stats: dict) -> None:
    n_dyn = 0
    for rel in sorted(
        {
            d["path"]
            for _n, d in g.nodes(data=True)
            if d["kind"] in ("function", "method") and d.get("path", "").endswith(".py")
        }
    ):
        try:
            tree = ast.parse((repo / rel).read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError, ValueError):
            continue
        for fn, qual in _func_defs(tree):
            nid = f"func:{rel}::{qual}"
            if nid not in g:
                continue
            for n in _own_nodes(fn):
                kind = _dynamic_kind(n)
                if kind:
                    text = ast.unparse(n)
                    text = text if len(text) <= 60 else text[:57] + "..."
                    uid = f"{UNKNOWN_PREFIX}dynamic:{text}"
                    _add_unknown_node(g, uid, text)
                    _add_edge(g, nid, uid, "calls", f"{rel}:{n.lineno}", 0.0, unknown=True,
                              dynamic=kind)  # fmt: skip
                    n_dyn += 1
    stats["dynamic_markers"] = n_dyn


# ---- observed marks ------------------------------------------------------------------------
def _match_tests(g: nx.MultiDiGraph, test_id: str) -> list[str]:
    """Test nodes named by a visible test id (exact, parametrised prefix, or whole file)."""
    tid = test_id[5:] if test_id.startswith("test:") else test_id
    out = []
    for nid, d in g.nodes(data=True):
        if d["kind"] != "test":
            continue
        s = nid[5:]
        if s == tid or s.startswith(tid + "::") or s.startswith(tid + "[") or d["path"] == tid:
            out.append(nid)
    return sorted(set(out))


def _mark_observed(og: OverlayGraph, runtime: RuntimeFacts) -> None:
    frames: list[str] = []
    for path, line in runtime.frames:
        nid = symbol_at(og.base, path, line)
        if nid and nid in og.nx:
            og.observed.setdefault(nid, []).append(f"trace frame {path}:{line}")
            if not frames or frames[-1] != nid:
                frames.append(nid)
    tests: list[str] = []
    for t in runtime.failing_tests:
        for nid in _match_tests(og.nx, t):
            og.observed.setdefault(nid, []).append(f"failing test {t}")
            tests.append(nid)
    g = og.nx
    obs = set(og.observed)
    for u, v, d in g.edges(data=True):
        if (
            u in obs
            and v in obs
            and d["type"] in ("calls", "called_by", "tests_covers", "covered_by")
        ):
            if d["evidence"] != "unknown":
                d["evidence"] = "observed"
    og.stats["observed_nodes"] = len(obs)


def build_overlay(
    graph: Graph,
    runtime: RuntimeFacts | None = None,
    *,
    hidden_paths: Sequence[str] = (),
) -> OverlayGraph:
    """Copy `graph`, add overlay edges, classify evidence. `graph` itself is never modified."""
    g = graph.nx.copy()  # per-node/edge attribute dicts are copied; values are scalars
    for nid in [n for n, d in g.nodes(data=True) if _is_hidden(d.get("path"), hidden_paths)]:
        g.remove_node(nid)
    stats: dict = {}
    _add_inheritance(g, graph.repo, stats)
    _add_name_resolution(g, stats)
    _add_dynamic_markers(g, graph.repo, stats)
    for u, v, d in g.edges(data=True):
        d["evidence"] = classify_edge(g, u, v, d)
    og = OverlayGraph(graph, g, {}, stats)
    if runtime:
        _mark_observed(og, runtime)
    return og
