# ruff: noqa: E501
"""Incremental embedding index (P5-S07). Stable public API:

    Embedder, OllamaEmbedder, FakeEmbedder, embed_key      (embedder.py)
    EmbeddingIndex, SyncReport                              (sync.py)
    search, verify, SearchHit                               (search.py)
    NamespaceStore, DimensionMismatch, ManifestError        (store.py)
See the module docstrings for contracts. Inputs (corpus Chunk list, codeintel Graph) are read-only.
"""

from .embedder import Embedder, EmbedError, FakeEmbedder, OllamaEmbedder, embed_key
from .search import SearchHit, search, verify
from .store import DimensionMismatch, ManifestError, NamespaceStore
from .sync import EmbeddingIndex, SyncReport

__all__ = ["EmbedError", "Embedder", "FakeEmbedder", "OllamaEmbedder", "embed_key", "SearchHit",
           "search", "verify", "DimensionMismatch", "ManifestError", "NamespaceStore",
           "EmbeddingIndex", "SyncReport"]  # fmt: skip
