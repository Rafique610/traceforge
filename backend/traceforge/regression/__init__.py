"""Opt-in regression-aware repair validation (P5-S17) and hybrid-experiment support (P5-S11).

Composes the injected `run_tests` of `repair.loop.run_repair`; nothing in `repair/`, `agent/` or any
RC1-fingerprinted file is edited or imports this package.
Contract: docs/research/regression-validation-contract.md
"""

from traceforge.regression.feedback import LeakRefused, build_regression_feedback
from traceforge.regression.history import PatchHistory, PatchVersion
from traceforge.regression.impact import (
    LIMITATION,
    GraphImpactProvider,
    ImpactProvider,
    ImpactReport,
    get_impact_provider,
    register_impact_provider,
)
from traceforge.regression.runner import (
    MAX_ATTEMPTS_CEILING,
    RegressionAwareRunner,
    RegressionGuardError,
    run_repair_regression_aware,
)
from traceforge.regression.selection import Selection, select_tests

__all__ = [
    "LIMITATION", "MAX_ATTEMPTS_CEILING", "GraphImpactProvider", "ImpactProvider", "ImpactReport",
    "LeakRefused", "PatchHistory", "PatchVersion", "RegressionAwareRunner", "RegressionGuardError",
    "Selection", "build_regression_feedback", "get_impact_provider", "register_impact_provider",
    "run_repair_regression_aware", "select_tests",
]  # fmt: skip
