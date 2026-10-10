"""TEST 51 -- `session_mass` diagnostic (joint remediation design
003+004 section 3; decision registry A2, Stage 4).

WEIGHTED per-session mass within the baseline pool, NEVER a raw
row-count `Counter` -- purely descriptive, never consumed by
`stratified_baseline_weighted_points()` or any weight/significance
formula. Radu's own worked example: security A present in 2 sessions
(S1, S2) against 9 OTHER securities sharing session S2 is a TRUE
`5%`/`95%` weighted split; a raw row count would misreport it as
`~9%`/`~91%` -- regression-locked here as the WRONG answer.
"""
from collections import Counter

import pytest

from evaluation.baseline.universe import (
    compute_session_mass, partition_temporal_bins, stratified_baseline_weighted_points, weighted_mean,
)


def _one_bin():
    return partition_temporal_bins("2024-01-01", "2024-12-31", 1)


def test_weighted_session_mass_reproduces_the_true_5_95_split():
    bins = _one_bin()
    baseline = [("A", "2024-02-01", 0.0), ("A", "2024-02-02", 0.0)]
    baseline += [(f"S{i}", "2024-02-02", 0.0) for i in range(9)]
    weights = {bins[0].label: 1.0}

    result = compute_session_mass(baseline, weights, bins)
    assert len(result) == 1
    mass = result[0].session_mass
    assert mass["2024-02-01"] == pytest.approx(0.05)
    assert mass["2024-02-02"] == pytest.approx(0.95)
    assert sum(mass.values()) == pytest.approx(1.0)


def test_raw_counter_would_misreport_the_skew_locked_as_wrong():
    baseline = [("A", "2024-02-01", 0.0), ("A", "2024-02-02", 0.0)]
    baseline += [(f"S{i}", "2024-02-02", 0.0) for i in range(9)]
    raw_counts = Counter(d for _, d, _ in baseline)
    total = sum(raw_counts.values())
    raw_fractions = {d: c / total for d, c in raw_counts.items()}
    assert raw_fractions["2024-02-01"] == pytest.approx(1 / 11)
    assert raw_fractions["2024-02-02"] == pytest.approx(10 / 11)
    # ~9%/~91% -- visibly different from, and misreporting, the true 5%/95%.
    assert abs(raw_fractions["2024-02-01"] - 0.05) > 0.03


def test_session_mass_is_purely_descriptive_point_estimate_unaffected():
    # stratified_baseline_weighted_points()'s own output must be
    # byte-identical whether or not compute_session_mass() is also
    # called -- the diagnostic consumes the SAME inputs but is a
    # read-only measurement, never a side-channel into the point
    # estimate.
    bins = partition_temporal_bins("2024-01-01", "2024-12-30", 3)
    baseline = [
        ("A", "2024-02-01", 1.0), ("B", "2024-02-02", 2.0),
        ("A", "2024-06-01", 3.0), ("C", "2024-06-02", 4.0),
    ]
    weights = {"early": 0.5, "middle": 0.5, "late": 0.0}

    points_before = stratified_baseline_weighted_points(baseline, weights, bins)
    mean_before = weighted_mean(points_before)
    _ = compute_session_mass(baseline, weights, bins)
    points_after = stratified_baseline_weighted_points(baseline, weights, bins)
    mean_after = weighted_mean(points_after)

    assert points_before == points_after
    assert mean_before == mean_after


def test_session_mass_excludes_zero_weight_bins_same_inclusion_rule():
    bins = partition_temporal_bins("2024-01-01", "2024-12-30", 3)
    baseline = [
        ("A", "2024-02-01", 1.0),
        ("A", "2024-11-01", 999.0),  # late -- must not appear (zero weight)
    ]
    weights = {"early": 1.0, "middle": 0.0, "late": 0.0}
    result = compute_session_mass(baseline, weights, bins)
    labels = {r.bin_label for r in result}
    assert labels == {"early"}
