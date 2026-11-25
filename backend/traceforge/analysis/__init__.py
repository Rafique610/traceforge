# ruff: noqa: E501
"""Root-cause, dependency and change-impact analysis (P5-S12, P5-S15, reduced S16 evaluation).

Offline, static analysis only, zero provider calls. Works on a COPY of a codeintel graph; nothing in
`codeintel/` or any RC1-fingerprinted file is edited, and no frozen file imports this package.
Design: docs/research/root-cause-impact-regression-design.md. Evaluation:
docs/research/rootcause-impact-evaluation.md.
"""

from traceforge.analysis.impact_report import OverlayImpactProvider, make_provider
from traceforge.analysis.overlay import OverlayGraph, RuntimeFacts, build_overlay
from traceforge.analysis.ranker import (
    RankerConfig,
    RankResult,
    Seed,
    rank_root_causes,
    seeds_from_retrieval,
    seeds_from_runtime,
)
from traceforge.analysis.traversal import (
    TraversalConfig,
    config_affecting,
    depended_on_by,
    depends_on,
    tests_exercising,
    traverse,
    what_else_could_change,
)

__all__ = [
    "OverlayGraph", "OverlayImpactProvider", "RankResult", "RankerConfig", "RuntimeFacts", "Seed",
    "TraversalConfig", "build_overlay", "config_affecting", "depended_on_by", "depends_on",
    "make_provider", "rank_root_causes", "seeds_from_retrieval", "seeds_from_runtime",
    "tests_exercising", "traverse", "what_else_could_change",
]  # fmt: skip
