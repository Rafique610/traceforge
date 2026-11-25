# ruff: noqa: E501
"""Retrieval benchmark harness (P5-S06): Retriever protocol + registry, shared equal-budget packing,
metrics, seeded paired bootstrap, repo and dev-split loaders. Offline, zero tokens, no gold in
retrievers. Importing the package registers the baselines RET-L and RET-G."""

from traceforge.retrieval_bench import methods as _methods  # noqa: F401
from traceforge.retrieval_bench.registry import get, names, register

__all__ = ["get", "names", "register"]
