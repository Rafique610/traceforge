"""Identifier-aware tokenizer and BM25 candidate generation (rank-bm25, Okapi, k1=1.5, b=0.75)."""

import re

from rank_bm25 import BM25Okapi

from traceforge.retrieval.corpus import Chunk, Corpus

_CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")
STOP = frozenset("self cls the and for not none true false def return import from with".split())


def tokenize(text: str) -> list[str]:
    """Split identifiers on `_`, camelCase and digits; when an identifier was split also keep it
    whole (lowercased) so exact names still match. Deterministic."""
    out: list[str] = []
    for ident in re.findall(r"[A-Za-z0-9_]+", text):
        parts = [p.lower() for piece in ident.split("_") if piece for p in _CAMEL.findall(piece)]
        parts = [p for p in parts if len(p) > 1 and p not in STOP]
        out += parts
        if len(parts) > 1:
            out.append(ident.lower())
    return out


class LexicalIndex:
    def __init__(self, corpus: Corpus) -> None:
        self.chunks: list[Chunk] = corpus.chunks
        docs = [tokenize(c.text) or ["_"] for c in self.chunks]
        self.bm25 = BM25Okapi(docs) if docs else None

    def scores(self, terms: list[str]) -> list[float]:
        if not self.bm25 or not terms:
            return [0.0] * len(self.chunks)
        return [float(s) for s in self.bm25.get_scores(list(dict.fromkeys(terms)))]

    def normalized(self, terms: list[str]) -> dict[str, float]:
        """hit_id -> BM25 score divided by the best score (0 when nothing matches)."""
        raw = self.scores(terms)
        top = max(raw, default=0.0)
        return {
            c.hit_id: (max(s, 0.0) / top if top > 0 else 0.0)
            for c, s in zip(self.chunks, raw, strict=True)
        }

    def candidates(self, terms: list[str], k: int = 50) -> list[tuple[Chunk, float]]:
        """Top-k chunks with positive BM25 score as (chunk, normalised score), sorted by
        (-score, hit_id) so ties are deterministic."""
        norm = self.normalized(terms)
        scored = sorted(
            ((c, norm[c.hit_id]) for c in self.chunks if norm[c.hit_id] > 0),
            key=lambda x: (-x[1], x[0].hit_id),
        )
        return scored[:k]


def index_for(corpus: Corpus) -> LexicalIndex:
    if corpus.index is None:
        corpus.index = LexicalIndex(corpus)
    return corpus.index  # type: ignore[return-value]
