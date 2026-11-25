# ruff: noqa: E501
"""Chunk identity, content hashing, edge digests and the manifest diff.

- id: the corpus `hit_id` (kind + path + qualname); changes on rename or file move.
- content_hash: sha256 of the normalised embedding text; distinct from the id. The embedding text
  is "{kind} {qualname}\\n{source lines}": the path and line numbers are excluded, so a pure
  file move or a reformat outside the body keeps the hash (vector reused) while a rename changes
  the qualname/def line and therefore re-embeds (names carry meaning for code retrieval).
- edge_digest: sha256 of a chunk's sorted outgoing forward graph edges (type, target); a change
  with an unchanged content_hash is an edge-only update (never re-embeds).
Diff classes: NEW / MODIFIED / DELETED / MOVED (same content_hash, different id) / UNCHANGED.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ChunkRecord:
    id: str
    content_hash: str
    path: str
    kind: str
    start: int
    end: int
    edge_digest: str
    text: str = field(default="", compare=False, repr=False)  # not persisted


def normalise_text(s: str) -> str:
    raw = s.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    lines = [ln.expandtabs(4).rstrip() for ln in raw]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def embedding_text(c) -> str:
    body = "\n".join(t for _n, t in c.lines)
    if c.notes:
        body += "\n" + "\n".join(c.notes)
    return normalise_text(f"{c.kind} {c.name}\n{body}")[:6000]


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def edge_digest(c, graph) -> str:
    nid = c.node_id if c.node_id in graph else (c.parent or c.node_id)
    if nid not in graph:
        return sha256_hex("")
    es = {
        f"{d['type']}>{v}"
        for _u, v, d in graph.nx.out_edges(nid, data=True)
        if not d.get("reverse")
    }
    return sha256_hex("\n".join(sorted(es)))


def graph_digest(graph) -> str:
    es = sorted(
        f"{u}|{d['type']}|{v}" for u, v, d in graph.nx.edges(data=True) if not d.get("reverse")
    )
    return sha256_hex("\n".join(es))


def make_records(chunks, graph) -> dict[str, ChunkRecord]:
    out: dict[str, ChunkRecord] = {}
    for c in chunks:
        if c.hit_id in out:
            raise ValueError(f"duplicate chunk id {c.hit_id}")
        text = embedding_text(c)
        out[c.hit_id] = ChunkRecord(
            c.hit_id, sha256_hex(text), c.path, c.kind, c.start, c.end, edge_digest(c, graph), text
        )
    return out


@dataclass
class Diff:
    new: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    moved: list[str] = field(default_factory=list)  # ids in the current manifest
    unchanged: list[str] = field(default_factory=list)
    edge_only: list[str] = field(default_factory=list)  # unchanged text, changed outgoing edges


def diff(prev: dict[str, ChunkRecord], cur: dict[str, ChunkRecord]) -> Diff:
    d = Diff()
    gone = {i: p for i, p in prev.items() if i not in cur}
    gone_by_hash: dict[str, list[str]] = {}
    for i in sorted(gone):
        gone_by_hash.setdefault(gone[i].content_hash, []).append(i)
    matched: set[str] = set()
    for i in sorted(cur):
        c, p = cur[i], prev.get(i)
        if p is None:
            twins = gone_by_hash.get(c.content_hash)
            if twins:
                matched.add(twins.pop(0))
                d.moved.append(i)
            else:
                d.new.append(i)
        elif p.content_hash != c.content_hash:
            d.modified.append(i)
        else:
            d.unchanged.append(i)
            if p.edge_digest != c.edge_digest:
                d.edge_only.append(i)
    d.deleted = sorted(i for i in gone if i not in matched)
    return d
