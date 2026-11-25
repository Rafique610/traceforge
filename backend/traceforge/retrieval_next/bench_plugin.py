# ruff: noqa: E501
"""Registers the P5-S08 arms in the retrieval_bench registry.

    python -m traceforge.retrieval_bench --plugin traceforge.retrieval_next.bench_plugin \
        --methods RET-L RET-G RET-E@jina RET-LE@jina:k60 RET-LGE@jina:k60 ...

Names: RET-E@<tag>, RET-LE@<tag>:k30|k60, RET-LGE@<tag>:k30|k60 for tag in minilm, jina, nomic, and
the canonical RET-E / RET-LE / RET-LGE (primary model jina, k = 60) plus RET-LG (= RET-G).
The incremental index root is $TF_RETNEXT_INDEX_ROOT (default <repo>/runs/bench_repos/embed_index).
"""

from __future__ import annotations

import os
from pathlib import Path

from traceforge.retrieval_bench.registry import get, register
from traceforge.retrieval_next.dense import MODELS, DenseRetriever, PrefixedOllamaEmbedder
from traceforge.retrieval_next.hybrid import HybridRetriever

PRIMARY = os.environ.get("TF_RETNEXT_PRIMARY", "jina")
KS = (30, 60)
INDEX_ROOT = Path(os.environ.get("TF_RETNEXT_INDEX_ROOT") or
                  Path(__file__).resolve().parents[3] / "runs" / "bench_repos" / "embed_index")  # fmt: skip


def _meta(tag: str, **extra) -> dict:
    s = MODELS[tag]
    return {"model_id": f"{s.model}", "settings": {"tag": tag, "prefixes": bool(s.query_prefix),
            "preprocessing": s.preprocessing_version, "index": "traceforge.index flat cosine",
            "top_k_dense": 50, **extra}}  # fmt: skip


def register_arms(
    embedder_factory=None, root: Path | None = None, tags=None, prefix: str = ""
) -> list[str]:
    """Register every arm. `embedder_factory(tag) -> Embedder` is injectable (tests use a fake).
    Returns the registered names."""
    names: list[str] = []
    for tag in tags or MODELS:
        fac = (lambda t=tag: embedder_factory(t)) if embedder_factory else \
              (lambda t=tag: PrefixedOllamaEmbedder(MODELS[t]))  # fmt: skip
        dense = DenseRetriever(f"{prefix}{tag}", fac, root or INDEX_ROOT)
        variants = [(f"{prefix}RET-E@{tag}", dense, {})]
        for k in KS:
            variants.append(
                (f"{prefix}RET-LE@{tag}:k{k}", HybridRetriever("L", dense, k), {"rrf_k": k})
            )
            variants.append(
                (f"{prefix}RET-LGE@{tag}:k{k}", HybridRetriever("G", dense, k), {"rrf_k": k})
            )
        if tag == PRIMARY:
            variants += [(f"{prefix}RET-E", dense, {}),
                         (f"{prefix}RET-LE", HybridRetriever("L", dense, 60), {"rrf_k": 60}),
                         (f"{prefix}RET-LGE", HybridRetriever("G", dense, 60), {"rrf_k": 60})]  # fmt: skip
        for name, obj, extra in variants:
            m = _meta(tag, **extra)
            register(name, model_id=m["model_id"], settings=m["settings"])(obj)
            names.append(name)
    return names


@register("RET-LG", settings={"alias_of": "RET-G"})
def ret_lg(ctx, query_text, k):
    return get("RET-G")(ctx, query_text, k)


if not os.environ.get("TF_RETNEXT_NO_AUTOREGISTER"):
    register_arms()
