"""TEST 3 -- Rolling percentile (Spec #002 SS38/SS14).

Known synthetic series -> expected percentile manually verifiable
(mean-rank formula, see normalization/rolling_percentile.py docstring).
"""
from discovery.normalization.rolling_percentile import rolling_percentile


def test_rolling_percentile_known_series():
    values = [1, 2, 3, 4, 5]
    out = rolling_percentile(values, window=5, min_periods=5)

    for point in out[:4]:
        assert point.value is None
        assert point.status == "INSUFFICIENT_HISTORY"

    # window=[1,2,3,4,5], current=5: count_less=4, count_equal=1
    # -> (4 + 0.5*1) / 5 = 0.9
    assert out[4].value == 0.9
    assert out[4].status == "VALID"


def test_rolling_percentile_tie_uses_mean_rank():
    values = [1, 2, 2, 2, 2]
    out = rolling_percentile(values, window=5, min_periods=5)
    # window=[1,2,2,2,2], current=2 (last element): count_less=1, count_equal=4
    # -> (1 + 0.5*4) / 5 = 0.6
    assert out[4].value == 0.6


def test_rolling_percentile_min_periods_override():
    values = [1, 2, 3, 4, 5]
    out = rolling_percentile(values, window=5, min_periods=3)
    assert out[1].status == "INSUFFICIENT_HISTORY"
    # window=[1,2,3], current=3: (2 + 0.5) / 3
    assert abs(out[2].value - (2.5 / 3)) < 1e-9
    assert out[2].status == "VALID"


def test_rolling_percentile_missing_input():
    values = [1, 2, None, 4, 5]
    out = rolling_percentile(values, window=5, min_periods=3)
    assert out[2].value is None
    assert out[2].status == "MISSING_INPUT"


def test_min_periods_cannot_exceed_window():
    import pytest
    with pytest.raises(ValueError):
        rolling_percentile([1, 2, 3], window=5, min_periods=10)
