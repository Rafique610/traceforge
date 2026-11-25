# ruff: noqa: E501
"""Retriever registry.

A retriever is any callable `(ctx: RepoContext, query_text: QueryText, k: int) -> list[str]`
returning the top-`k` chunk ids (`Chunk.hit_id`, i.e. `sym:path::qualname`, `test:path::qualname`,
`cfg:KEY`), best first, no duplicates. `query_text` is a `str`; `.evidence` / `.service` are
optional extras for the evidence-based L/G arms. Retrievers NEVER see gold.

Optional members (looked up with getattr, all have defaults):
    prepare(ctx)          build a per-repo index; timed as `index_build_s`; stash it in
                          `ctx.state[name]` (the harness calls it once per repo, outside query timing)
    storage_bytes(ctx)    bytes persisted on disk for that index (default 0: nothing persisted)
    model_id              string recorded in provenance (default "none")
    settings              dict recorded in provenance

Add a method (the complete API):

    from traceforge.retrieval_bench.registry import register

    @register("RET-E", model_id="<model id@revision>", settings={"dims": 768})
    class DenseRetriever:
        def prepare(self, ctx):                      # optional
            ctx.state["RET-E"] = embed_all(ctx.corpus.chunks)
        def __call__(self, ctx, query_text, k):
            return top_k_ids(ctx.state["RET-E"], str(query_text), k)
        def storage_bytes(self, ctx):                # optional
            return ctx.state["RET-E"].nbytes

A plain function also works (`@register("RET-X")` on a def). Fused arms can reuse the other arms:
`get("RET-L")(ctx, q, 50)` and `get("RET-G")(ctx, q, 50)` give the ranked lists to fuse (RRF).
Importing the module that holds the decorator is enough; `load_plugins(["pkg.mod"])` does it by name
(CLI `--plugin pkg.mod`). Names must be unique. Equal-budget packing and scoring are done by the
harness for every registered method, so a method only returns ranked ids.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from traceforge.retrieval_bench.repo_ctx import RepoContext
    from traceforge.retrieval_bench.types import QueryText


@runtime_checkable
class Retriever(Protocol):
    def __call__(self, ctx: RepoContext, query_text: QueryText, k: int) -> list[str]: ...


_REGISTRY: dict[str, Any] = {}
_META: dict[str, dict] = {}


def register(name: str, *, model_id: str = "none", settings: dict | None = None) -> Callable:
    def deco(obj: Any) -> Any:
        if name in _REGISTRY:
            raise ValueError(f"retriever {name!r} already registered")
        _REGISTRY[name] = obj() if isinstance(obj, type) else obj
        _META[name] = {"model_id": model_id, "settings": settings or {}}
        return obj

    return deco


def get(name: str) -> Retriever:
    try:
        return _REGISTRY[name]
    except KeyError:
        raise KeyError(f"unknown retriever {name!r}; registered: {sorted(_REGISTRY)}") from None


def meta(name: str) -> dict:
    return _META[name]


def names() -> list[str]:
    return sorted(_REGISTRY)


def unregister(name: str) -> None:  # tests
    _REGISTRY.pop(name, None)
    _META.pop(name, None)


def load_plugins(modules: list[str]) -> None:
    for m in modules:
        importlib.import_module(m)
