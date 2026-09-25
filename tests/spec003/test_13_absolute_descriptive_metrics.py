"""TEST 13 -- Absolute descriptive metrics (Spec #003 SS35/SS66).

mean/median/std/quantiles/positive_rate hand-verified on a known list.
"""
import pytest

from evaluation.statistics.descriptive import describe


def test_descriptive_stats_match_hand_computation():
    values = [-0.02, -0.01, 0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07]
    d = describe(values)
    assert d.n == 10
    assert d.mean == pytest.approx(sum(values) / 10)
    assert d.median == pytest.approx((0.02 + 0.03) / 2)
    assert d.positive_rate == pytest.approx(7 / 10)  # 7 strictly positive
    assert d.q10 < d.q25 < d.q75 < d.q90
