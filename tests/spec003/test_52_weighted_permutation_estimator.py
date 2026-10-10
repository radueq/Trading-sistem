"""TEST 52 -- weighted permutation estimator (joint remediation design
003+004 section 5; decision registry A4, Stage 4).

Pre-Stage-4 bug: `stratified_permutation_p_value()` compared against a
PLAIN baseline mean while the reported effect size already used a
per-security-weighted one -- testing significance of a DIFFERENT
quantity than the one actually reported. Fixed: within each bin, a
FIXED per-row weight (`1/(k_b*n_i,b)`, position-bound to that bin's
baseline slots) is precomputed ONCE from the TRUE baseline composition;
only VALUES are shuffled, never which weight a slot carries.

The exhaustive-enumeration regression below is the EXACT fixture named
in Radu's own Stage 4 authorization text: signature `[8]`, baseline
`A=[0,2]`/`B=[4]`, observed `5.5`, exact `p=8/24=1/3` -- kept distinct
from a Monte Carlo estimate using the add-one continuity correction.
"""
import itertools

import pytest

from evaluation.statistics.comparison import stratified_permutation_p_value


def test_exhaustive_enumeration_exact_fixture():
    sig_by_bin = {"x": [8.0]}
    base_rows_by_bin = {"x": [("A", 0.0), ("A", 2.0), ("B", 4.0)]}
    weights = {"x": 1.0}

    observed, raw_p_monte_carlo = stratified_permutation_p_value(
        sig_by_bin, base_rows_by_bin, weights, iterations=2000, seed=42,
    )
    assert observed == pytest.approx(5.5)

    # Exact enumeration by hand, mirroring the function's own fixed-
    # weight-per-slot mechanics: all 4! = 24 orderings of the four
    # pooled values [8, 0, 2, 4] across the four FIXED positions
    # (position 0 = signature slot; positions 1-3 = baseline slots with
    # FIXED weights [1/4, 1/4, 1/2], aligned to the ORIGINAL (A,0),
    # (A,2), (B,4) order, never to whichever value lands there).
    pooled = [8.0, 0.0, 2.0, 4.0]
    fixed_weights = [0.25, 0.25, 0.5]
    extreme = 0
    total = 0
    for perm in itertools.permutations(pooled):
        total += 1
        sig_val = perm[0]
        base_vals = perm[1:]
        base_mean = sum(v * w for v, w in zip(base_vals, fixed_weights))
        diff = sig_val - base_mean
        if abs(diff) >= abs(5.5):
            extreme += 1
    assert total == 24
    assert extreme == 8
    exact_p = extreme / total
    assert exact_p == pytest.approx(1 / 3)
    # The Monte Carlo estimate (add-one continuity correction) is
    # DIFFERENT from the exact fraction by construction -- never equal
    # on the nose, even though both approximate the same thing.
    assert raw_p_monte_carlo != exact_p


def test_equal_weight_reduces_byte_identical_to_plain_mean_mechanics():
    # Power-of-2 case (2 securities, 1 row each per bin -> uniform
    # weight 0.5 each) -- floating point summation order is exact here
    # (0.5 is exactly representable), so this reproduces the pre-
    # Stage-4 plain-mean mechanics bit-for-bit: same observed value,
    # same p-value, same RNG sequence (same shuffle calls, same order).
    sig_by_bin = {"early": [1.0, 2.0], "late": [4.0, 5.0]}
    base_rows_new = {"early": [("S1", 0.5), ("S2", 1.5)], "late": [("S4", 3.5), ("S5", 4.5)]}
    base_vals_plain = {"early": [0.5, 1.5], "late": [3.5, 4.5]}
    weights = {"early": 0.6, "late": 0.4}

    obs_new, p_new = stratified_permutation_p_value(sig_by_bin, base_rows_new, weights, iterations=500, seed=99)
    obs_old, p_old = _old_stratified_permutation_p_value(sig_by_bin, base_vals_plain, weights, iterations=500, seed=99)

    assert obs_new == obs_old
    assert p_new == p_old


def test_non_equal_security_weighting_changes_the_observed_statistic():
    # Sanity: when a security contributes MULTIPLE rows in a bin, the
    # weighted baseline mean must differ from the plain mean of the
    # SAME raw values (otherwise the fix has no effect).
    sig_by_bin = {"x": [10.0]}
    base_rows = {"x": [("A", 0.0), ("A", 1.0), ("A", 2.0), ("B", 100.0)]}  # A dominates by row count
    weights = {"x": 1.0}
    observed, _ = stratified_permutation_p_value(sig_by_bin, base_rows, weights, iterations=10, seed=1)
    # weighted: A's 3 rows share weight 1/2 total (1/6 each), B alone
    # gets 1/2 -- weighted baseline mean = (0+1+2)/3*0.5 + 100*0.5 = 0.5+50 = 50.5
    plain_mean = sum(v for _, v in base_rows["x"]) / len(base_rows["x"])  # (0+1+2+100)/4 = 25.75
    weighted_mean_expected = ((0.0 + 1.0 + 2.0) / 3) * 0.5 + 100.0 * 0.5  # A's own group mean * 0.5 + B * 0.5 = 50.5
    assert observed == pytest.approx(10.0 - weighted_mean_expected)
    assert observed != pytest.approx(10.0 - plain_mean)


def test_no_qualifying_bin_returns_none():
    observed, p = stratified_permutation_p_value({}, {}, {}, iterations=100, seed=1)
    assert observed is None and p is None


def _old_stratified_permutation_p_value(sig_by_bin, base_by_bin, weights_by_bin, iterations, seed):
    """The pre-Stage-4 plain-mean mechanics, reimplemented inline as the
    regression oracle for the equal-weight byte-identical check above --
    deliberately NOT imported from production code, since the whole
    point is to compare against what the OLD code used to do."""
    import random as _random

    pools = {}
    for label, weight in weights_by_bin.items():
        if weight <= 0:
            continue
        sig_vals = sig_by_bin.get(label, [])
        base_vals = base_by_bin.get(label, [])
        if not sig_vals or not base_vals:
            continue
        pools[label] = (sig_vals, base_vals)
    if not pools or iterations <= 0:
        return None, None
    total_weight = sum(weights_by_bin[label] for label in pools)
    observed = sum(
        weights_by_bin[label] * (sum(sig_vals) / len(sig_vals) - sum(base_vals) / len(base_vals))
        for label, (sig_vals, base_vals) in pools.items()
    ) / total_weight
    rng = _random.Random(seed)
    at_least_as_extreme = 0
    for _ in range(iterations):
        combined = 0.0
        for label, (sig_vals, base_vals) in pools.items():
            n_sig = len(sig_vals)
            pooled = sig_vals + base_vals
            rng.shuffle(pooled)
            perm_diff = sum(pooled[:n_sig]) / n_sig - sum(pooled[n_sig:]) / len(base_vals)
            combined += weights_by_bin[label] * perm_diff
        combined /= total_weight
        if abs(combined) >= abs(observed):
            at_least_as_extreme += 1
    raw_p = (at_least_as_extreme + 1) / (iterations + 1)
    return observed, raw_p
