"""Evaluation metrics: pure functions over saved AgentRunRecords + CaseManifests (+ contexts)."""

from traceforge.evaluation.metrics.common import Pair, distance_bucket, group_by
from traceforge.evaluation.metrics.diagnosis import diagnosis_metrics
from traceforge.evaluation.metrics.repair import repair_metrics
from traceforge.evaluation.metrics.system import system_metrics

DIMENSIONS = {
    "cause_class": lambda p: p[1].cause_class,
    "distance": lambda p: distance_bucket(p[1].distance),
    "fault_family": lambda p: p[1].fault_family,
    "log_format": lambda p: p[1].log_format,
}


def section(pairs: list[Pair]) -> dict:
    """Diagnosis + repair + system metrics for one group of pairs (n_records, n_cases shown)."""
    return {
        "n_records": len(pairs),
        "n_cases": len({r.case_id for r, _ in pairs}),
        "diagnosis": diagnosis_metrics(pairs),
        "repair": repair_metrics(pairs),
        "system": system_metrics(pairs),
    }


def condition_section(pairs: list[Pair]) -> dict:
    """One condition: overall plus every metric broken down by each dimension."""
    return {
        "overall": section(pairs),
        "breakdowns": {
            dim: {k: section(v) for k, v in group_by(pairs, fn).items()}
            for dim, fn in DIMENSIONS.items()
        },
    }
