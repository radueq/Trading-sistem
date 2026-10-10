"""TEST 50 -- `weighted_quantile()`'s own boundary/contract and the
tie/order-independence matrix (joint remediation design 003+004 section
4; decision registry A3, Stage 4).

Midpoint (Hazen-type) convention WITH MANDATORY TIE-AGGREGATION -- the
adopted convention (the alternative rescaled/`R_i` convention was
explored in the design doc but NOT adopted, since its
inclusive-reproduction property breaks once tie-aggregation collapses
tied values; this module does not implement it at all)."""
import pytest

from evaluation.baseline.universe import weighted_quantile


def test_tie_aggregation_removes_order_dependence():
    # The SAME multiset of (value, weight) pairs, in a DIFFERENT input
    # order, must give the IDENTICAL answer. p=0.7 on [(0,1),(0,3),(10,1)]
    # vs [(0,3),(0,1),(10,1)] -- both aggregate to {0: 4, 10: 1} first.
    order_a = [(0.0, 1.0), (0.0, 3.0), (10.0, 1.0)]
    order_b = [(0.0, 3.0), (0.0, 1.0), (10.0, 1.0)]
    q_a = weighted_quantile(order_a, 0.7)
    q_b = weighted_quantile(order_b, 0.7)
    assert q_a == q_b
    # Hand-verified: aggregated points (0, 4), (10, 1), W=5.
    # P_1 = (4 - 0.5*4)/5 = 0.4; P_2 = (5 - 0.5*1)/5 = 0.9.
    # p=0.7 interpolates between them: frac=(0.7-0.4)/(0.9-0.4)=0.6,
    # value = 0 + 0.6*(10-0) = 6.0.
    assert q_a == pytest.approx(6.0)


def test_splitting_one_rows_weight_vs_one_merged_row_agree():
    # A single row (10.0, weight=4.0) split into several rows at the
    # IDENTICAL value must agree with the merged form, by construction
    # once tie-aggregation applies.
    merged = [(10.0, 4.0), (20.0, 1.0)]
    split = [(10.0, 1.0), (10.0, 1.0), (10.0, 1.0), (10.0, 1.0), (20.0, 1.0)]
    for p in (0.1, 0.25, 0.5, 0.75, 0.9):
        assert weighted_quantile(merged, p) == weighted_quantile(split, p)


def test_midpoint_disagrees_with_statistics_inclusive_even_tie_free():
    # Deliberate, documented difference -- NOT a bug. [0,10,20] at equal
    # weight: midpoint gives Q1=2.5/median=10/Q3=17.5, vs "inclusive"'s
    # 5/10/15. Locked here so this property is never "fixed" by mistake.
    points = [(0.0, 1.0), (10.0, 1.0), (20.0, 1.0)]
    assert weighted_quantile(points, 0.25) == pytest.approx(2.5)
    assert weighted_quantile(points, 0.5) == pytest.approx(10.0)
    assert weighted_quantile(points, 0.75) == pytest.approx(17.5)

    import statistics as pystats
    inclusive = pystats.quantiles([0.0, 10.0, 20.0], n=4, method="inclusive")
    assert inclusive == [5.0, 10.0, 15.0]
    assert weighted_quantile(points, 0.25) != inclusive[0]


def test_tie_aggregation_locks_its_own_post_aggregation_behavior():
    # [0,0,10] all weight 1 -- aggregates to {0: 2, 10: 1}, W=3.
    # P_1 = (2 - 1)/3 = 1/3; P_2 = (3 - 0.5)/3 = 5/6.
    # median (p=0.5) interpolates: frac=(0.5-1/3)/(5/6-1/3)=0.333.., value=0+0.333..*10=10/3.
    points = [(0.0, 1.0), (0.0, 1.0), (10.0, 1.0)]
    assert weighted_quantile(points, 0.5) == pytest.approx(10 / 3)


def test_non_finite_value_hard_fails():
    with pytest.raises(ValueError):
        weighted_quantile([(float("nan"), 1.0), (1.0, 1.0)], 0.5)
    with pytest.raises(ValueError):
        weighted_quantile([(float("inf"), 1.0), (1.0, 1.0)], 0.5)


def test_non_finite_weight_hard_fails():
    with pytest.raises(ValueError):
        weighted_quantile([(1.0, float("nan")), (2.0, 1.0)], 0.5)
    with pytest.raises(ValueError):
        weighted_quantile([(1.0, float("inf")), (2.0, 1.0)], 0.5)


def test_negative_weight_hard_fails_never_silently_clamped_or_dropped():
    # Verification discipline: confirm this specifically does NOT
    # silently skip (the existing `if weight <= 0: continue` pattern
    # elsewhere in this module would -- this function must not reuse
    # that pattern verbatim).
    with pytest.raises(ValueError):
        weighted_quantile([(1.0, -0.5), (2.0, 1.0)], 0.5)


def test_zero_weight_is_silently_excluded_not_an_error():
    points = [(1.0, 0.0), (2.0, 1.0), (3.0, 1.0)]
    # must not raise, and the zero-weight row must not affect the result.
    result = weighted_quantile(points, 0.5)
    assert result == weighted_quantile([(2.0, 1.0), (3.0, 1.0)], 0.5)


def test_empty_input_returns_none():
    assert weighted_quantile([], 0.5) is None
    assert weighted_quantile([(1.0, 0.0)], 0.5) is None  # only a zero-weight row survives filtering -- still empty


def test_single_distinct_value_returns_it_for_every_p():
    points = [(7.0, 1.0), (7.0, 2.0), (7.0, 0.5)]
    for p in (0.0, 0.1, 0.5, 0.9, 1.0):
        assert weighted_quantile(points, p) == 7.0


def test_p_outside_bracket_clamps_to_first_or_last_point():
    points = [(1.0, 1.0), (2.0, 1.0), (3.0, 1.0)]
    assert weighted_quantile(points, 0.0) == 1.0
    assert weighted_quantile(points, 1.0) == 3.0
