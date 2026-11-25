# ruff: noqa: E501
"""EmbeddingIndex: incremental, resumable, namespaced embedding index (the stable entry point).

    idx = EmbeddingIndex(namespace_root, embedder, batch_size=32)
    report = idx.sync(chunks, graph, commit_id)   # chunks: Corpus.chunks (read-only input)
    idx.manifest()      -> live manifest dict (or None): {"commit","dims","chunks":[{id,content_hash,
                           embed_key,path,kind,start,end,edge_digest}], "graph_digest", ...}
    idx.live()          -> (ids sorted, float32 [n,dims] matrix) of the live view
    idx.search(q, k)    -> list[SearchHit]  (see search.py);  verify(idx, chunks) -> list[str]
    idx.gc("all"|"active") -> vectors removed (cache entries of deleted chunks live until gc)

Rules: only chunks whose embed_key is absent from the namespace are embedded (NEW/MODIFIED, or
everything for a new model namespace); MOVED and edge-only changes never embed. Embedding runs in
fixed-size batches in sorted-id order, each batch persisted before the next (resumable); the
live view changes only when ACTIVE.json is atomically swapped. A different model_id/revision/
dims is a different on-disk namespace, so an old index stays intact and queryable.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from .embedder import Embedder, embed_key
from .identity import ChunkRecord, diff, graph_digest, make_records
from .store import SCHEMA, DimensionMismatch, NamespaceStore


@dataclass
class SyncReport:
    commit: str
    new: int = 0
    modified: int = 0
    deleted: int = 0
    moved: int = 0
    unchanged: int = 0
    embed_calls: int = 0
    texts_embedded: int = 0
    reused: int = 0  # live chunks whose vector came from the cache
    edge_only_updates: int = 0
    seconds: float = 0.0
    ids: dict[str, list[str]] = field(default_factory=dict)  # per-class ids (audit)

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if k != "ids"}


class EmbeddingIndex:
    def __init__(self, root, embedder: Embedder, batch_size: int = 32):
        self.embedder, self.batch_size = embedder, batch_size
        self.store = NamespaceStore(root, embedder.model_id, embedder.revision, embedder.dims)
        self._live = None

    def manifest(self) -> dict | None:
        act = self.store.read_active()
        return act[1] if act else None

    def prev_records(self) -> dict[str, ChunkRecord]:
        m = self.manifest()
        if not m:
            return {}
        return {c["id"]: ChunkRecord(c["id"], c["content_hash"], c["path"], c["kind"], c["start"],
                                     c["end"], c["edge_digest"]) for c in m["chunks"]}  # fmt: skip

    def sync(self, chunks, graph, commit_id: str) -> SyncReport:
        t0 = time.perf_counter()
        e, st = self.embedder, self.store
        cur = make_records(chunks, graph)
        d = diff(self.prev_records(), cur)
        keys = {i: embed_key(r.content_hash, e) for i, r in cur.items()}
        todo: dict[str, str] = {}  # embed_key -> text, first id in sorted order
        for i in sorted(cur):
            if not st.has(keys[i]) and keys[i] not in todo:
                todo[keys[i]] = cur[i].text
        rep = SyncReport(commit_id, len(d.new), len(d.modified), len(d.deleted), len(d.moved),
                         len(d.unchanged), edge_only_updates=len(d.edge_only))  # fmt: skip
        rep.ids = {
            k: list(getattr(d, k))
            for k in ("new", "modified", "deleted", "moved", "unchanged", "edge_only")
        }
        order = list(todo)
        for s in range(0, len(order), self.batch_size):
            ks = order[s : s + self.batch_size]
            vecs = np.asarray(e.embed([todo[k] for k in ks]), dtype=np.float32)
            if vecs.ndim != 2 or vecs.shape != (len(ks), e.dims):
                raise DimensionMismatch(
                    f"embedder returned {vecs.shape}, expected ({len(ks)}, {e.dims})"
                )
            st.put_many(ks, vecs)  # persisted per batch: a crash resumes from here
            rep.embed_calls += 1
            rep.texts_embedded += len(ks)
        embedded = set(order)
        rep.reused = sum(1 for i in cur if keys[i] not in embedded)
        manifest = {
            "schema": SCHEMA, "commit": commit_id, "model_id": e.model_id, "revision": e.revision,
            "dims": e.dims, "preprocessing_version": e.preprocessing_version,
            "graph_digest": graph_digest(graph),
            "chunks": [{"id": i, "content_hash": r.content_hash, "embed_key": keys[i], "path": r.path,
                        "kind": r.kind, "start": r.start, "end": r.end, "edge_digest": r.edge_digest}
                       for i, r in sorted(cur.items())],
        }  # fmt: skip
        name, digest = st.write_manifest(manifest)
        st.set_active(commit_id, name, digest)  # the only visible switch
        self._live = None
        rep.seconds = time.perf_counter() - t0
        return rep

    def live(self) -> tuple[list[str], np.ndarray]:
        if self._live is None:
            m = self.manifest()
            ids = [c["id"] for c in m["chunks"]] if m else []
            mat = (np.stack([self.store.get(c["embed_key"]) for c in m["chunks"]])
                   if ids else np.zeros((0, self.embedder.dims), np.float32))  # fmt: skip
            self._live = (ids, mat.astype(np.float32))
        return self._live

    def search(self, query_vec, k: int = 10):
        from .search import search

        return search(self, query_vec, k)

    def gc(self, retain: str = "all") -> int:
        return self.store.gc(retain)
