"""TEST 12 -- Baseline distribution / TEMPORALLY_STRATIFIED_ELIGIBLE_BASELINE
(Spec #003 SS33-34, Radu's Sec.74C amendment/SS66).

Hand-verified: the baseline point estimate is the weighted MEAN of ONE
pooled per-security-weighted distribution (joint remediation design
003+004, Stage 4; decision registry A3 -- replaces the old two-level
"per-bin plain stat, then bin-weighted-average" mechanism), weighted by
the SIGNATURE's own bin composition -- never the baseline's own raw bin
sizes. One row per security per bin here, so per-security weighting
reduces to a plain per-bin average (the F4+F5 weighting only matters
when a security has multiple rows in a bin -- see
test_49_pooled_weighted_baseline_distribution.py for that case) -- this
test is about bin-level weighting surviving the Stage 4 rewrite, not
about per-security weighting itself.
"""
import pytest

from evaluation.baseline.universe import (
    bin_composition, partition_temporal_bins, stratified_baseline_weighted_points, weighted_mean,
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
    # the signature has zero weight there). One row per DISTINCT
    # security per bin (SEC_1/SEC_2 in "early", SEC_3/SEC_4 in "middle",
    # SEC_5/SEC_6 in "late") -- F4+F5's per-security weighting has
    # nothing to equalize here (n_i,b=1 for every security), so this
    # reduces to the plain per-bin mean.
    baseline = [
        ("SEC_1", "2024-02-01", 0.00), ("SEC_2", "2024-02-05", 0.02),   # early: mean 0.01
        ("SEC_3", "2024-06-01", 0.10), ("SEC_4", "2024-06-02", 0.12),   # middle: mean 0.11
        ("SEC_5", "2024-11-01", 100.0), ("SEC_6", "2024-11-02", 100.0),  # late: mean 100.0 (must be excluded)
    ]
    points = stratified_baseline_weighted_points(baseline, weights, bins)
    estimate = weighted_mean(points)
    expected = weights["early"] * 0.01 + weights["middle"] * 0.11
    assert estimate == pytest.approx(expected)
    assert estimate < 1.0, "the late-period outlier must not leak into a signature with zero weight there"
