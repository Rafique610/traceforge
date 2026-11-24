"""P5-S11: RetrievalAdapter protocol and registry (RET-L, RET-G now; RET-E/LE/LG/LGE when present).

RET-L / RET-G map to the current `retrieval.retrieve(mode="L"|"G")`. Dense / fused arms register
only if Rafique's modules exist (`retrieval/dense.py`, `retrieval/hybrid.py`, P5-S08); each must
expose `make_adapter(name) -> RetrievalAdapter`.

LIMITATION (RC2 follow-up): this registry selects an adapter for offline use and for experiment
specs. Actually swapping retrieval inside the pipeline needs a hook in the frozen
`retrieval/sources.py` (RealContextSource), which is not implemented here (new RC + fingerprint).
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

BASELINE_ARMS = ("RET-L", "RET-G")
OPTIONAL_ARMS = {  # arm -> module that must exist before it registers
    "RET-E": "traceforge.retrieval.dense",
    "RET-LE": "traceforge.retrieval.hybrid",
    "RET-LG": "traceforge.retrieval.retrieve",  # = current G, an alias that always exists
    "RET-LGE": "traceforge.retrieval.hybrid",
}


@runtime_checkable
class RetrievalAdapter(Protocol):
    name: str

    def retrieve(self, evidence: Any, graph: Any, token_budget: int, *, service: str = "") -> Any:
        """Return a ContextBundle (same contract as `retrieval.retrieve`)."""
        ...


class CurrentRetrievalAdapter:
    """RET-L / RET-G placeholders over the existing retrieve()."""

    def __init__(self, name: str, mode: str) -> None:
        self.name, self.mode = name, mode

    def retrieve(self, evidence: Any, graph: Any, token_budget: int, *, service: str = "") -> Any:
        from traceforge.retrieval.retrieve import retrieve

        return retrieve(evidence, graph, self.mode, token_budget, service=service)


_REGISTRY: dict[str, Callable[[], RetrievalAdapter]] = {}


def register_adapter(name: str, factory: Callable[[], RetrievalAdapter]) -> None:
    _REGISTRY[name] = factory


def _probe_optional() -> None:
    for arm, module in OPTIONAL_ARMS.items():
        if arm in _REGISTRY:
            continue
        if arm == "RET-LG":
            register_adapter(arm, lambda: CurrentRetrievalAdapter("RET-LG", "G"))
            continue
        try:
            mod = importlib.import_module(module)
        except ImportError:
            continue
        if hasattr(mod, "make_adapter"):
            register_adapter(arm, lambda m=mod, a=arm: m.make_adapter(a))


def available_arms() -> list[str]:
    _probe_optional()
    return sorted(_REGISTRY)


def get_adapter(name: str) -> RetrievalAdapter:
    _probe_optional()
    if name not in _REGISTRY:
        raise KeyError(f"retrieval arm {name!r} not registered; available: {sorted(_REGISTRY)}")
    return _REGISTRY[name]()


register_adapter("RET-L", lambda: CurrentRetrievalAdapter("RET-L", "L"))
register_adapter("RET-G", lambda: CurrentRetrievalAdapter("RET-G", "G"))
