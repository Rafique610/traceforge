"""Chunk corpus built from the code graph and the source tree (one chunk per function/class header,
test function and config key). Cached per (repo, base_sha, content_hash).

Node-id convention of the metrics module is the contract for `hit_id`:
`sym:<path>::<qualname>` (functions, methods, classes), `test:<path>::<qualname>` and `cfg:<key>`.
Graph node ids (`func:`, `class:`, `test:`, `cfg:`, `field:`) are kept as `node_id`.

Two conventions come from the fault generator's gold labels and are followed here:
- gold config keys are service-qualified (`cfg:shop_api.REDIS_HOST`), while graph config nodes are
  shared (`cfg:REDIS_HOST`): `qualified_id(chunk, service)` produces the gold form for ContextHits;
- gold symbols may be class attributes / settings fields (`Settings.redis_host`), so every
  annotated or simple class-level assignment is its own `sym:` chunk (`field:` node id; its graph
  neighbourhood is that of the settings field when the graph has it, else of the owning class).
"""

import ast
from dataclasses import dataclass, field
from pathlib import Path

from traceforge.codeintel import Graph

SOURCE_TEXT_CAP = 6000  # chars of a chunk indexed by BM25 (excerpts are separate)
CLASS_HEADER_MAX_LINES = 12


@dataclass
class Chunk:
    node_id: str  # graph id
    hit_id: str  # metrics id
    kind: str  # symbol | config_key | test (ContextHit.kind)
    path: str
    start: int
    end: int
    name: str  # qualname, or config key
    text: str  # what BM25 indexes
    lines: list[tuple[int, str]] = field(default_factory=list)  # numbered source excerpt
    notes: list[str] = field(default_factory=list)  # extra excerpt lines (config read sites)
    parent: str | None = None  # owning class node for field chunks (graph fallback)
    services: list[str] = field(default_factory=list)  # services whose env declares a config key


@dataclass
class Corpus:
    chunks: list[Chunk]
    by_node: dict[str, Chunk]
    by_hit: dict[str, Chunk]
    _spans: dict[str, list[Chunk]]
    _owner: dict[tuple[str, int], Chunk]
    index: object = None  # lazily attached LexicalIndex

    def owner_at(self, path: str, line: int) -> Chunk | None:
        """The chunk a source line belongs to: config declaration/settings-field line, else the
        innermost function/test, else the class header."""
        if (path, line) in self._owner:  # config declaration line in compose/.env
            return self._owner[(path, line)]
        best = None
        for c in self._spans.get(path, ()):
            if c.start <= line <= c.end and (
                best is None or (c.start, -c.end) > (best.start, -best.end)
            ):
                best = c
        return best


def hit_id_of(node_id: str, graph: Graph) -> str | None:
    """Metrics-convention id of a graph node, or None if the node is not a retrievable chunk."""
    d = graph.nx.nodes.get(node_id)
    if d is None:
        return None
    k = d["kind"]
    if k in ("function", "method", "class"):
        return f"sym:{d['path']}::{d['qualname']}"
    if k == "test":
        return f"test:{d['path']}::{d['qualname']}"
    if k == "config_key":
        return f"cfg:{d['name']}"
    return None


def graph_id_of(hit_id: str, graph: Graph) -> str | None:
    """Inverse of hit_id_of (graph ids are accepted unchanged)."""
    if hit_id in graph:
        return hit_id
    prefix, _, rest = hit_id.partition(":")
    for gp in ("func", "class") if prefix == "sym" else ("test",) if prefix == "test" else ():
        if f"{gp}:{rest}" in graph:
            return f"{gp}:{rest}"
    return None


def _read_lines(repo: Path, rel: str, cache: dict[str, list[str]]) -> list[str]:
    if rel not in cache:
        try:
            cache[rel] = (repo / rel).read_text("utf-8", errors="replace").splitlines()
        except OSError:
            cache[rel] = []
    return cache[rel]


def _config_chunk(graph: Graph, nid: str, d: dict, src: dict[str, list[str]]) -> Chunk:
    key = d["name"]
    decl = _read_lines(graph.repo, d["path"], src)
    decl_line = decl[d["start"] - 1].strip() if 0 < d["start"] <= len(decl) else key
    notes, names, services = [], [], []
    edges = sorted(graph.nx.out_edges(nid, data=True), key=lambda x: (x[1], x[2]["provenance"]))
    for _u, v, e in edges:
        if e["type"] == "env_of" and v.startswith("svc:"):
            services.append(v[4:])
        if e["type"] != "read_by":
            continue
        vd = graph.node(v)
        label = vd.get("qualname") or vd.get("name") or v
        names.append(label)
        notes.append(f"# read by {vd['kind']} {label} @ {e['provenance']}")
    text = " ".join([key, key.lower(), d["path"], decl_line, *names])
    return Chunk(
        nid, f"cfg:{key}", "config_key", d["path"], d["start"], d["end"], key, text,
        [(d["start"], decl_line)], notes[:8], None, sorted(set(services)),
    )  # fmt: skip


def _field_chunks(graph: Graph, rel: str, src: dict[str, list[str]]) -> list[Chunk]:
    """One chunk per class-level simple/annotated assignment of every class in file `rel`."""
    try:
        tree = ast.parse("\n".join(_read_lines(graph.repo, rel, src)))
    except SyntaxError:
        return []
    out: list[Chunk] = []

    def visit(body: list[ast.stmt], prefix: str) -> None:
        for st in body:
            if isinstance(st, ast.ClassDef):
                qual = f"{prefix}{st.name}"
                for m in st.body:
                    tgt = m.target if isinstance(m, ast.AnnAssign) else (
                        m.targets[0] if isinstance(m, ast.Assign) and len(m.targets) == 1 else None
                    )  # fmt: skip
                    if isinstance(tgt, ast.Name) and not tgt.id.startswith("__"):
                        fq, end = f"{qual}.{tgt.id}", m.end_lineno or m.lineno
                        lines = [(i, src[rel][i - 1]) for i in range(m.lineno, end + 1)]
                        text = f"{rel} {fq}\n" + "\n".join(t for _, t in lines)
                        out.append(
                            Chunk(
                                f"field:{rel}::{fq}",
                                f"sym:{rel}::{fq}",
                                "symbol",
                                rel,
                                m.lineno,
                                end,
                                fq,
                                text,
                                lines,
                                [],
                                f"class:{rel}::{qual}",
                            )  # fmt: skip
                        )
                visit(st.body, f"{qual}.")

    visit(tree.body, "")
    return out


def build_corpus(graph: Graph) -> Corpus:
    src: dict[str, list[str]] = {}
    starts: dict[str, list[int]] = {}
    for _nid, d in graph.nx.nodes(data=True):
        if d["kind"] in ("function", "method"):
            starts.setdefault(d["path"], []).append(d["start"])
    chunks: list[Chunk] = []
    for nid in sorted(graph.nx.nodes):
        d = graph.node(nid)
        k = d["kind"]
        if k == "config_key":
            chunks.append(_config_chunk(graph, nid, d, src))
            continue
        if k not in ("function", "method", "class", "test"):
            continue
        start, end = d["start"], d["end"]
        if k == "class":  # header only; methods are their own chunks
            later = [s - 1 for s in starts.get(d["path"], ()) if start < s <= end]
            end = min([end, start + CLASS_HEADER_MAX_LINES - 1, *later])
        lines = _read_lines(graph.repo, d["path"], src)
        body = [(i, lines[i - 1]) for i in range(start, min(end, len(lines)) + 1)]
        text = f"{d['path']} {d['qualname']}\n" + "\n".join(t for _, t in body)
        kind = "test" if k == "test" else "symbol"
        chunks.append(
            Chunk(
                nid,
                hit_id_of(nid, graph),
                kind,
                d["path"],
                start,
                end,
                d["qualname"],
                text[:SOURCE_TEXT_CAP],
                body,
            )  # fmt: skip
        )
    for rel in sorted({d["path"] for _n, d in graph.nx.nodes(data=True) if d["kind"] == "class"}):
        chunks += [c for c in _field_chunks(graph, rel, src) if c.parent in graph]
    by_node = {c.node_id: c for c in chunks}
    spans: dict[str, list[Chunk]] = {}
    owner: dict[tuple[str, int], Chunk] = {}
    for c in chunks:
        if c.kind == "config_key":
            owner[(c.path, c.start)] = c
        else:
            spans.setdefault(c.path, []).append(c)
    return Corpus(chunks, by_node, {c.hit_id: c for c in chunks}, spans, owner)


_CACHE: dict[tuple[str, str, str], Corpus] = {}


def get_corpus(graph: Graph) -> Corpus:
    """Per-(repo, base_sha, content hash) cache: a rebuilt identical graph reuses the corpus."""
    key = (str(graph.repo), graph.base_sha, graph.content_hash)
    if key not in _CACHE:
        if len(_CACHE) > 16:
            _CACHE.clear()
        _CACHE[key] = build_corpus(graph)
    return _CACHE[key]


def qualified_id(chunk: Chunk, service: str) -> str:
    """ContextHit id: config keys become `cfg:<service>.<KEY>`, the manifests' gold form, using the
    incident's service (else the first service whose env declares the key, else the bare key)."""
    if chunk.kind != "config_key":
        return chunk.hit_id
    svc = service or (chunk.services[0] if chunk.services else "")
    return f"cfg:{svc}.{chunk.name}" if svc else chunk.hit_id
