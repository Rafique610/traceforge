"""Paired per-case comparison between two conditions (no best-of-N).

Per case and condition the value is the mean over that condition's replicates; only cases present
in BOTH conditions are compared. The CI is a seeded percentile bootstrap over cases and is
withheld (None) below MIN_CI_CASES paired cases.
"""

import random
from collections import defaultdict

from traceforge.contracts.case_manifest import REPAIRABLE
from traceforge.evaluation.metrics.common import Pair, gold_targets, group_by

MIN_CI_CASES = 10
PAIRED_METRICS = ("verified_repair", "cause_correct", "exact_target")


def _value(metric: str, r, m) -> float | None:
    """Per-record 0/1 outcome, or None when the case is outside the metric's denominator."""
    if metric == "verified_repair":
        return float(r.outcome == "TEST_VERIFIED_IN_LAB") if m.cause_class in REPAIRABLE else None
    if metric == "cause_correct":
        return float(r.diagnosis.cause_class == m.cause_class)
    if metric == "exact_target":
        if not gold_targets(m):
            return None
        d = r.diagnosis
        return float(not d.abstained and d.target in gold_targets(m))
    raise ValueError(f"unknown paired metric {metric!r}")


def per_case_values(pairs: list[Pair], condition: str, metric: str) -> dict[str, float]:
    acc: dict[str, list[float]] = defaultdict(list)
    for r, m in pairs:
        if r.condition == condition and (v := _value(metric, r, m)) is not None:
            acc[r.case_id].append(v)
    return {c: sum(v) / len(v) for c, v in acc.items()}


def bootstrap_ci(
    diffs: list[float], iterations: int = 10_000, seed: int = 0, level: float = 0.95
) -> tuple[float, float] | None:
    """Percentile bootstrap CI of the mean over cases; None when fewer than MIN_CI_CASES."""
    n = len(diffs)
    if n < MIN_CI_CASES:
        return None
    rng = random.Random(seed)
    means = sorted(sum(diffs[rng.randrange(n)] for _ in range(n)) / n for _ in range(iterations))
    lo = means[int((1 - level) / 2 * iterations)]
    hi = means[min(int((1 + level) / 2 * iterations), iterations - 1)]
    return lo, hi


def paired_comparison(
    pairs: list[Pair], a: str, b: str, metric: str, iterations: int = 10_000, seed: int = 0
) -> dict:
    """Difference `b - a` per case. wins/losses count cases where b is better/worse than a."""
    va, vb = per_case_values(pairs, a, metric), per_case_values(pairs, b, metric)
    cases = sorted(va.keys() & vb.keys())
    diffs = [vb[c] - va[c] for c in cases]
    n = len(cases)
    ci = bootstrap_ci(diffs, iterations, seed)
    return {
        "a": a,
        "b": b,
        "metric": metric,
        "n_paired": n,
        "n_only_a": len(va.keys() - vb.keys()),
        "n_only_b": len(vb.keys() - va.keys()),
        "mean_a": (sum(va[c] for c in cases) / n) if n else None,
        "mean_b": (sum(vb[c] for c in cases) / n) if n else None,
        "mean_diff": (sum(diffs) / n) if n else None,
        "b_better": sum(d > 0 for d in diffs),
        "b_worse": sum(d < 0 for d in diffs),
        "tied": sum(d == 0 for d in diffs),
        "ci95": list(ci) if ci else None,
        "ci_note": None if ci else f"n_paired < {MIN_CI_CASES}: no CI claimed",
        "bootstrap": {"iterations": iterations, "seed": seed},
    }


def all_paired(pairs: list[Pair], iterations: int = 10_000, seed: int = 0) -> list[dict]:
    conds = sorted(group_by(pairs, lambda p: p[0].condition))
    return [
        paired_comparison(pairs, a, b, metric, iterations, seed)
        for i, a in enumerate(conds)
        for b in conds[i + 1 :]
        for metric in PAIRED_METRICS
    ]
