# ruff: noqa: E501
"""RET-E: dense retrieval over the corpus chunks (P5-S08).

The query is embedded exactly as the BM25 arm receives it (`str(query_text)`, no rewrite, no
anchors, no graph) and the top-k chunks by cosine come from `traceforge.index.EmbeddingIndex`
(flat numpy, content-addressed vectors). The index lives incrementally in a namespace directory:
each repo (and the whole dev split, whose cases are mutations of one lab) has one root, so a
second sync of the same tree embeds nothing and a mutated dev tree re-embeds only changed chunks.
`ensure_index` asserts that a warm resync reuses every vector.

Model-specific prefixes (e.g. nomic "search_query: ") are model preprocessing, recorded in
`preprocessing_version`, not a query rewrite.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from traceforge.index import EmbeddingIndex, OllamaEmbedder, search
from traceforge.index.embedder import l2_normalise


@dataclass(frozen=True)
class ModelSpec:
    tag: str
    model: str
    query_prefix: str = ""
    doc_prefix: str = ""
    batch_size: int = 32

    @property
    def preprocessing_version(self) -> str:
        return "p1" + ("+pfx" if (self.query_prefix or self.doc_prefix) else "")


MODELS: dict[str, ModelSpec] = {
    "minilm": ModelSpec("minilm", "all-minilm:22m"),
    "jina": ModelSpec("jina", "unclemusclez/jina-embeddings-v2-base-code"),
    "nomic": ModelSpec("nomic", "nomic-embed-text", "search_query: ", "search_document: "),
}


class PrefixedOllamaEmbedder(OllamaEmbedder):
    """OllamaEmbedder with optional document / query prefixes. `embed` = documents (used by the
    index); `embed_query` = the query side."""

    def __init__(self, spec: ModelSpec, **kw):
        super().__init__(model=spec.model, batch_size=spec.batch_size,
                         preprocessing_version=spec.preprocessing_version, **kw)  # fmt: skip
        self.spec = spec

    def embed(self, texts: list[str]) -> np.ndarray:
        return super().embed([self.spec.doc_prefix + t for t in texts])

    def embed_query(self, text: str) -> np.ndarray:
        return self._embed_raw([self.spec.query_prefix + text])[0]


def query_vector(embedder, text: str) -> np.ndarray:
    fn = getattr(embedder, "embed_query", None)
    return np.asarray(fn(text) if fn else embedder.embed([text])[0], dtype=np.float32)


def group_of(ctx_name: str) -> str:
    """One index root per repo; every dev case (named `<service>-<nnn>`) shares the `dev` root."""
    return "dev" if ctx_name.startswith("shop_api-") else ctx_name


def _rss_mb() -> float | None:
    from traceforge.retrieval_bench.repo_ctx import process_peak_rss_mb

    return process_peak_rss_mb()


def ensure_index(ctx, embedder, root: Path, key: str) -> EmbeddingIndex:
    """Sync the namespace to `ctx` once (cold or incremental), then assert a warm resync embeds
    nothing and reuses every vector. Cached in `ctx.state[key]`."""
    if key in ctx.state:
        return ctx.state[key]["index"]
    idx_root = Path(root) / group_of(ctx.name)
    idx = _INDEXES.setdefault(
        (str(idx_root), key),
        EmbeddingIndex(idx_root, embedder, getattr(embedder, "batch_size", 32)),
    )
    chunks = ctx.corpus.chunks
    t0 = time.perf_counter()
    rep = idx.sync(chunks, ctx.graph, ctx.name)
    sync_s = time.perf_counter() - t0
    warm = idx.sync(chunks, ctx.graph, ctx.name)
    ids, mat = idx.live()
    n_unique = len({c["embed_key"] for c in idx.manifest()["chunks"]})
    if warm.texts_embedded != 0 or warm.embed_calls != 0 or warm.reused != len(ids):
        raise AssertionError(f"warm resync did not reuse vectors: {warm.as_dict()}")
    if len(ids) != len(chunks):
        raise AssertionError(f"index has {len(ids)} ids for {len(chunks)} chunks")
    info = {
        "ctx": ctx.name, "model": embedder.model_id, "revision": embedder.revision,
        "dims": embedder.dims, "chunks": len(chunks), "unique_vectors": n_unique,
        "sync_s": round(sync_s, 4), "warm_resync_s": round(warm.seconds, 4),
        "sync": rep.as_dict(), "warm": warm.as_dict(), "live_matrix_bytes": int(mat.nbytes),
        "store_bytes": idx.store.storage_bytes(), "peak_rss_mb": _rss_mb(),
    }  # fmt: skip
    ctx.state[key] = {"index": idx, "info": info}
    log = Path(root) / "build_log.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"tag": key, **info}) + "\n")
    return idx


_INDEXES: dict[tuple[str, str], EmbeddingIndex] = {}


class DenseRetriever:
    """RET-E. `embedder_factory()` is called lazily (tests inject a fake)."""

    def __init__(self, key: str, embedder_factory, root: Path | str):
        self.key, self._factory, self.root = key, embedder_factory, Path(root)
        self._embedder = None
        self.query_embed_s: list[float] = []

    @property
    def embedder(self):
        if self._embedder is None:
            self._embedder = self._factory()
        return self._embedder

    def prepare(self, ctx) -> None:
        ensure_index(ctx, self.embedder, self.root, self.key)

    def scores(self, ctx, query_text, k: int):
        """-> list[SearchHit] (id, cosine) top-k, deterministic ties (see index.search)."""
        idx = ensure_index(ctx, self.embedder, self.root, self.key)
        t0 = time.perf_counter()
        qv = query_vector(self.embedder, str(query_text))
        self.query_embed_s.append(time.perf_counter() - t0)
        return search(idx, l2_normalise(qv.reshape(1, -1))[0], k)

    def __call__(self, ctx, query_text, k: int) -> list[str]:
        out: list[str] = []
        for h in self.scores(ctx, query_text, k):
            if h.id not in out:
                out.append(h.id)
        return out[:k]

    def storage_bytes(self, ctx) -> int:
        st = ctx.state.get(self.key)
        return int(st["info"]["store_bytes"]) if st else 0
