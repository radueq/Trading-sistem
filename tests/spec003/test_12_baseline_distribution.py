"""TEST 12 -- Baseline distribution / TEMPORALLY_STRATIFIED_ELIGIBLE_BASELINE
(Spec #003 SS33-34, Radu's Sec.74C amendment/SS66).

Hand-verified: the baseline point estimate is a weighted average of
PER-BIN statistics, weighted by the SIGNATURE's own bin composition --
never the baseline's own raw bin sizes.
"""
import pytest

from evaluation.baseline.universe import (
    bin_composition, partition_temporal_bins, stratified_baseline_point_estimate,
)


def test_stratified_estimate_uses_signature_weights_not_raw_bin_sizes():
    bins = partition_temporal_bins("2024-01-01", "2024-12-30", 3)

    # Signature's own episodes: 2 in "early", 1 in "middle", 0 in "late"
    signature_dates = ["2024-02-01", "2024-02-15", "2024-06-01"]
    weights = bin_composition(signature_dates, bins)
    assert weights["early"] == pytest.approx(2 / 3)
    assert weights["middle"] == pytest.approx(1 / 3)
    assert weights["late"] == 0.0

    # Baseline pool: "early" mean=0.01, "middle" mean=0.11, "late" mean=100.0
    # (a huge, unrelated late-period value that must NOT leak in, since
    # the signature has zero weight there)
    baseline = [
        ("2024-02-01", 0.00), ("2024-02-05", 0.02),          # early: mean 0.01
        ("2024-06-01", 0.10), ("2024-06-02", 0.12),          # middle: mean 0.11
        ("2024-11-01", 100.0), ("2024-11-02", 100.0),        # late: mean 100.0 (must be excluded)
    ]
    estimate = stratified_baseline_point_estimate(baseline, weights, bins, lambda vs: sum(vs) / len(vs))
    expected = weights["early"] * 0.01 + weights["middle"] * 0.11
    assert estimate == pytest.approx(expected)
    assert estimate < 1.0, "the late-period outlier must not leak into a signature with zero weight there"
