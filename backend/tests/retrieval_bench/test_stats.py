# ruff: noqa: E501
import pytest

from traceforge.retrieval_bench.stats import SEED, paired_bootstrap, sign_test


def test_bootstrap_seeded_and_reproducible():
    a = [1.0, 0.5, 0.0, 1.0, 0.25, 0.75]
    b = [0.5, 0.5, 0.0, 0.0, 0.25, 0.25]
    r1 = paired_bootstrap(a, b, iters=2000, seed=SEED)
    r2 = paired_bootstrap(a, b, iters=2000, seed=SEED)
    assert r1 == r2
    # few resamples + varied differences: a different seed must move the interval ends
    c = [0.1, 0.9, 0.3, 0.7, 0.2, 0.8, 0.45, 0.05]
    d = [0.0] * 8
    ends = {
        (r["ci_lo"], r["ci_hi"])
        for r in (paired_bootstrap(c, d, iters=20, seed=s) for s in range(SEED, SEED + 6))
    }
    assert len(ends) > 1
    assert r1["mean_diff"] == pytest.approx(sum(x - y for x, y in zip(a, b, strict=True)) / 6)
    assert r1["ci_lo"] <= r1["mean_diff"] <= r1["ci_hi"]


def test_bootstrap_constant_difference_has_degenerate_ci():
    r = paired_bootstrap([1, 1, 1, 1], [0, 0, 0, 0], iters=500, seed=1)
    assert r["mean_diff"] == r["ci_lo"] == r["ci_hi"] == 1.0


def test_bootstrap_validates_input():
    with pytest.raises(ValueError):
        paired_bootstrap([1.0], [1.0, 2.0])


def test_sign_test_hand_computed():
    # 5 wins, 0 losses, 1 tie: p = 2 * (1/32) = 0.0625
    r = sign_test([1, 1, 1, 1, 1, 0], [0, 0, 0, 0, 0, 0])
    assert (r["a_better"], r["b_better"], r["ties"]) == (5, 0, 1)
    assert r["p"] == pytest.approx(0.0625)
    # 3 vs 3: p = 1
    assert sign_test([1, 1, 1, 0, 0, 0], [0, 0, 0, 1, 1, 1])["p"] == 1.0
    assert sign_test([1, 1], [1, 1])["p"] == 1.0
