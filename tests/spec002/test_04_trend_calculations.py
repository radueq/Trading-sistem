"""TEST 4 -- Trend calculations (Spec #002 SS38/SS9).

Synthetic monotonic series -> expected returns/slopes/distances,
manually verifiable.
"""
import pandas as pd

from discovery.features import trend


def test_trend_calculations_on_monotonic_series():
    n = 250
    closes = [100.0 + i for i in range(n)]  # +1.0/day, perfectly linear
    df = pd.DataFrame({"close": closes})
    config = {
        "return_windows": [20, 63, 126], "sma_windows": [20, 50, 200],
        "slope_windows": [20, 50], "slope_window": 10,
    }

    out = trend.compute(df, config)
    last = n - 1

    expected_return_20d = closes[last] / closes[last - 20] - 1.0
    assert abs(out["return_20d"].iloc[last] - expected_return_20d) < 1e-9

    expected_return_63d = closes[last] / closes[last - 63] - 1.0
    assert abs(out["return_63d"].iloc[last] - expected_return_63d) < 1e-9

    expected_sma20 = sum(closes[last - 19: last + 1]) / 20
    assert abs(out["sma_20"].iloc[last] - expected_sma20) < 1e-9

    expected_distance_sma20 = closes[last] / expected_sma20 - 1.0
    assert abs(out["distance_sma20"].iloc[last] - expected_distance_sma20) < 1e-9

    # slope_sma20 is a percentage-based slope ((sma[t]/sma[t-w] - 1) / w),
    # so on a linear ABSOLUTE price path (+1.0/day) it stays positive but
    # gradually shrinks as the price base grows -- a fixed absolute
    # increment is a smaller percentage at a higher price level.
    assert out["slope_sma20"].iloc[150] > 0
    assert out["slope_sma20"].iloc[200] > 0
    assert out["slope_sma20"].iloc[200] < out["slope_sma20"].iloc[150]


def test_trend_features_nan_before_window_is_full():
    n = 30
    df = pd.DataFrame({"close": [100.0 + i for i in range(n)]})
    config = {"return_windows": [20], "sma_windows": [20], "slope_window": 5}
    out = trend.compute(df, config)
    assert pd.isna(out["return_20d"].iloc[10])
    assert pd.isna(out["sma_20"].iloc[10])
