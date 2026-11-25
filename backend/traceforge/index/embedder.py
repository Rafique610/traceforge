# ruff: noqa: E501
"""Embedder protocol and implementations.

Public contract (stable):
    Embedder.model_id / .revision / .dims / .preprocessing_version : identity of the vector space
    Embedder.embed(texts: list[str]) -> np.ndarray float32 [n, dims], rows L2-normalised
    embed_key(content_hash, embedder) -> str : sha256 of (content_hash, model_id, revision, dims,
        preprocessing_version); the primary key of the content-addressed vector cache.

OllamaEmbedder talks only to a local Ollama server (POST /api/embed). One request per batch, a
timeout, no retry loops: a failure raises EmbedError. FakeEmbedder is deterministic and offline.
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
from typing import Protocol, runtime_checkable

import numpy as np


class EmbedError(RuntimeError):
    pass


@runtime_checkable
class Embedder(Protocol):
    model_id: str
    revision: str
    dims: int
    preprocessing_version: str

    def embed(self, texts: list[str]) -> np.ndarray: ...


def embed_key(content_hash: str, e: Embedder) -> str:
    raw = "\0".join([content_hash, e.model_id, e.revision, str(e.dims), e.preprocessing_version])
    return hashlib.sha256(raw.encode()).hexdigest()


def l2_normalise(m: np.ndarray) -> np.ndarray:
    m = np.asarray(m, dtype=np.float32)
    n = np.linalg.norm(m, axis=1, keepdims=True)
    return (m / np.where(n == 0, 1.0, n)).astype(np.float32)


class FakeEmbedder:
    """Deterministic hash-based embedder for tests. Records every call in `.calls` (list of text
    lists); `.texts` is the flat list of every text embedded."""

    def __init__(self, model_id="fake", revision="1", dims=16, preprocessing_version="p1"):
        self.model_id, self.revision, self.dims = model_id, revision, dims
        self.preprocessing_version = preprocessing_version
        self.calls: list[list[str]] = []

    @property
    def texts(self) -> list[str]:
        return [t for c in self.calls for t in c]

    def embed(self, texts: list[str]) -> np.ndarray:
        self.calls.append(list(texts))
        rows = []
        for t in texts:
            digest = hashlib.sha256(f"{self.model_id}|{self.revision}|{t}".encode()).digest()
            rows.append(
                np.random.default_rng(int.from_bytes(digest[:8], "little")).standard_normal(
                    self.dims
                )
            )
        return l2_normalise(np.array(rows).reshape(len(texts), self.dims))


class OllamaEmbedder:
    """Local Ollama embedder (default model all-minilm:22m, 384-d). `dims` and `revision` are
    resolved lazily (a one-text probe and the /api/tags digest) unless given."""

    def __init__(self, model="all-minilm:22m", base_url="http://127.0.0.1:11434", batch_size=32,
                 timeout=120.0, preprocessing_version="p1", revision=None, dims=None):  # fmt: skip
        self.model_id, self.base_url = model, base_url.rstrip("/")
        self.batch_size, self.timeout = batch_size, timeout
        self.preprocessing_version = preprocessing_version
        self._revision, self._dims = revision, dims

    def _post(self, path: str, body: dict | None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            self.base_url + path, data=data, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read())
        except Exception as exc:  # no retry loops: surface immediately
            raise EmbedError(f"ollama {path} failed: {exc}") from exc

    @property
    def revision(self) -> str:
        if self._revision is None:
            try:
                tags = self._post("/api/tags", None).get("models", [])
                names = (self.model_id, self.model_id + ":latest")
                digest = next((m["digest"] for m in tags if m.get("name") in names), "")
            except EmbedError:
                digest = ""
            self._revision = digest[:12] or "unknown"
        return self._revision

    @property
    def dims(self) -> int:
        if self._dims is None:
            self._dims = int(self._embed_raw(["dimension probe"]).shape[1])
        return self._dims

    def _embed_raw(self, texts: list[str]) -> np.ndarray:
        out = self._post("/api/embed", {"model": self.model_id, "input": texts})
        vecs = out.get("embeddings")
        if not vecs or len(vecs) != len(texts):
            raise EmbedError("ollama returned a wrong number of embeddings")
        return l2_normalise(np.array(vecs, dtype=np.float32))

    def embed(self, texts: list[str]) -> np.ndarray:
        step = self.batch_size
        parts = [self._embed_raw(texts[i : i + step]) for i in range(0, len(texts), step)]
        return np.vstack(parts) if parts else np.zeros((0, self.dims), np.float32)
