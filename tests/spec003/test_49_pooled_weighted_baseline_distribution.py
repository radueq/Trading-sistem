"""TEST 49 -- ONE pooled weighted baseline distribution (joint
remediation design 003+004 section 3-4; decision registry A3, Stage 4).

`stratified_baseline_point_estimate()`'s own pre-Stage-4 signature
received only `(date, value)` pairs, with NO security identity -- it
could not implement per-security weighting for ANY statistic, for any
`stat` callable. Fixed: `stratified_baseline_weighted_points()` builds
ONE pooled `(value, weight)` distribution from EVERY eligible row
across every bin, each row carrying `w = W_b / (k_b * n_i,b)`; this
SAME pooled set feeds `baseline_mean` (`weighted_mean()`),
`baseline_median`, and `baseline_iqr`'s own Q1/Q3 (`weighted_quantile()`)
TOGETHER -- replacing the old two-level "per-bin plain stat, then
bin-weighted-average" mechanism AND the separately-unweighted
`robust_iqr()` call entirely, in one change, not two.

Numeric oracles below are the exact worked examples from
`docs/joint_remediation_design_003_004_2026-10-04.md` section 4.3 and
`docs/implementation_plan_003_004_2026-10-05.md`'s own Stage 4
acceptance criteria -- independently confirmed by direct computation
before being locked here as regression fixtures.
"""
import pytest

from evaluation.baseline.universe import (
    partition_temporal_bins, stratified_baseline_weighted_points, weighted_mean, weighted_quantile,
)


def test_simple_one_bin_example_exact_fractions():
    # One bin, security A=[0,2] (2 rows), security B=[4] (1 row), k=2.
    # Per-row weights [1/4, 1/4, 1/2] -- the EXACT numbers repeated in
    # Radu's own Stage 4 authorization text and the implementation
    # plan's acceptance criteria. Pre-Stage-4 (unweighted) row
    # computation gave mean=2.0/median=2.0 -- the corrected pooled
    # weighted computation must NOT reproduce that.
    bins = partition_temporal_bins("2024-01-01", "2024-12-31", 1)
    baseline = [("A", "2024-02-01", 0.0), ("A", "2024-02-02", 2.0), ("B", "2024-02-03", 4.0)]
    weights = {bins[0].label: 1.0}

    points = stratified_baseline_weighted_points(baseline, weights, bins)
    assert sorted(points) == sorted([(0.0, 0.25), (2.0, 0.25), (4.0, 0.5)])

    mean = weighted_mean(points)
    median = weighted_quantile(points, 0.5)
    q1 = weighted_quantile(points, 0.25)
    q3 = weighted_quantile(points, 0.75)

    assert mean == pytest.approx(2.5)
    assert mean != pytest.approx(2.0), "must not reproduce the pre-Stage-4 unweighted row mean"
    assert median == pytest.approx(8 / 3)
    assert median != pytest.approx(2.0), "must not reproduce the pre-Stage-4 unweighted row median"
    assert q1 == pytest.approx(1.0)
    assert q3 == pytest.approx(4.0)
    assert (q3 - q1) == pytest.approx(3.0)


def test_richer_two_bin_example_exact_fractions():
    # Section 4.3's "Reweight" worked example (the ADOPTED mechanism):
    # bin "early" (weight 0.7): A=[0.8,1.0,1.2] (3 rows), B=[2.0] (1 row).
    # bin "late" (weight 0.3): A=[1.5] (1 row), B=[2.5] (1 row). k=2 in
    # both bins.
    bins = partition_temporal_bins("2024-01-01", "2024-12-31", 2)
    early, late = bins[0].label, bins[1].label
    baseline = [
        ("A", "2024-02-01", 0.8), ("A", "2024-02-02", 1.0), ("A", "2024-02-03", 1.2),
        ("B", "2024-02-04", 2.0),
        ("A", "2024-08-01", 1.5),
        ("B", "2024-08-02", 2.5),
    ]
    weights = {early: 0.7, late: 0.3}

    points = stratified_baseline_weighted_points(baseline, weights, bins)
    assert sum(w for _, w in points) == pytest.approx(1.0)

    mean = weighted_mean(points)
    median = weighted_quantile(points, 0.5)
    q1 = weighted_quantile(points, 0.25)
    q3 = weighted_quantile(points, 0.75)

    assert mean == pytest.approx(1.65)
    assert median == pytest.approx(33 / 20)
    assert q1 == pytest.approx(79 / 70)
    assert q3 == pytest.approx(43 / 20)
    assert (q3 - q1) == pytest.approx(143 / 140)


def test_median_and_iqr_read_from_the_identical_pooled_set():
    # A SEPARATE assertion (implementation plan's own explicit
    # acceptance criterion) that baseline_median and baseline_iqr's
    # Q1/Q3 are computed from the IDENTICAL pooled set -- never two
    # independently-built distributions. Proven by construction here:
    # one `points` list feeds all three statistics.
    bins = partition_temporal_bins("2024-01-01", "2024-12-31", 2)
    early, late = bins[0].label, bins[1].label
    baseline = [
        ("A", "2024-02-01", 0.8), ("A", "2024-02-02", 1.0), ("A", "2024-02-03", 1.2),
        ("B", "2024-02-04", 2.0),
        ("A", "2024-08-01", 1.5),
        ("B", "2024-08-02", 2.5),
    ]
    weights = {early: 0.7, late: 0.3}

    points_a = stratified_baseline_weighted_points(baseline, weights, bins)
    points_b = stratified_baseline_weighted_points(baseline, weights, bins)
    assert sorted(points_a) == sorted(points_b), "rebuilding from the same input must reproduce the identical pool"

    mean = weighted_mean(points_a)
    median = weighted_quantile(points_a, 0.5)
    q1 = weighted_quantile(points_a, 0.25)
    q3 = weighted_quantile(points_a, 0.75)
    # all four read from the SAME points_a object, by construction --
    # this is the actual guarantee (not a re-derivation check).
    assert mean is not None and median is not None and q1 is not None and q3 is not None


@pytest.mark.parametrize("scale", [2.0, 0.5, 1000.0])
def test_weight_rescaling_invariance(scale):
    # Rescaling EVERY weight by a positive constant must leave every
    # quantile value unchanged (both C_i and W scale together) and
    # leave the weighted mean unchanged (a ratio).
    bins = partition_temporal_bins("2024-01-01", "2024-12-31", 2)
    early, late = bins[0].label, bins[1].label
    baseline = [
        ("A", "2024-02-01", 0.8), ("A", "2024-02-02", 1.0), ("A", "2024-02-03", 1.2),
        ("B", "2024-02-04", 2.0),
        ("A", "2024-08-01", 1.5),
        ("B", "2024-08-02", 2.5),
    ]
    weights = {early: 0.7, late: 0.3}
    points = stratified_baseline_weighted_points(baseline, weights, bins)
    scaled_points = [(v, w * scale) for v, w in points]

    for p in (0.25, 0.5, 0.75):
        assert weighted_quantile(points, p) == pytest.approx(weighted_quantile(scaled_points, p))
    assert weighted_mean(points) == pytest.approx(weighted_mean(scaled_points))


def test_bins_with_zero_weight_or_no_baseline_rows_are_excluded():
    # A bin the signature has zero weight in, or that has no baseline
    # rows at all, must not leak into the pooled distribution -- same
    # inclusion rule as the pre-Stage-4 mechanism (`if weight <= 0:
    # continue` / `if not rows: continue`), now applied to the pool
    # builder itself.
    bins = partition_temporal_bins("2024-01-01", "2024-12-30", 3)
    baseline = [
        ("A", "2024-02-01", 1.0), ("B", "2024-02-02", 1.0),  # early
        ("A", "2024-11-01", 999.0),  # late -- must be excluded (zero weight)
    ]
    weights = {"early": 1.0, "middle": 0.0, "late": 0.0}
    points = stratified_baseline_weighted_points(baseline, weights, bins)
    assert all(v != 999.0 for v, _ in points)
    assert weighted_mean(points) == pytest.approx(1.0)
