# ruff: noqa: E501
"""Paired bootstrap and exact sign test for method differences (stdlib only, seeded)."""

from __future__ import annotations

import math
import random

SEED = 20261125
ITERS = 10_000


def paired_bootstrap(
    a: list[float], b: list[float], iters: int = ITERS, seed: int | str = SEED
) -> dict:
    """Mean of (a - b) over paired queries with a percentile 95% CI from resampling the pairs.
    Deterministic for a fixed seed (random.Random). n < 2 -> CI is the point value."""
    if len(a) != len(b) or not a:
        raise ValueError("paired samples must be equal-length and non-empty")
    d = [x - y for x, y in zip(a, b, strict=True)]
    n = len(d)
    mean = sum(d) / n
    rng = random.Random(seed)
    means = sorted(sum(d[rng.randrange(n)] for _ in range(n)) / n for _ in range(iters))
    lo, hi = means[int(0.025 * iters)], means[min(int(0.975 * iters), iters - 1)]
    return {"n": n, "mean_diff": mean, "ci_lo": lo, "ci_hi": hi, "iters": iters, "seed": str(seed)}


def sign_test(a: list[float], b: list[float], eps: float = 1e-12) -> dict:
    """Exact two-sided sign test on non-tied pairs."""
    wins = sum(x - y > eps for x, y in zip(a, b, strict=True))
    losses = sum(y - x > eps for x, y in zip(a, b, strict=True))
    n = wins + losses
    if n == 0:
        return {"a_better": 0, "b_better": 0, "ties": len(a), "p": 1.0}
    k = min(wins, losses)
    p = min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2**n)
    return {"a_better": wins, "b_better": losses, "ties": len(a) - n, "p": p}
