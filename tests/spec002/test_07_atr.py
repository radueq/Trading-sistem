"""TEST 7 -- ATR (Spec #002 SS38/SS11).

Known OHLC sequence -> ATR manually verifiable, via the public
volatility.compute() contract (classic Wilder recursive smoothing,
seeded by a plain mean of the first `window` true ranges). A small
window (5) is used here purely so the hand computation stays short; the
output feature key is still literally "ATR_14" (Spec #002's fixed
naming -- see volatility.py) regardless of the configured window.
"""
import pandas as pd

from discovery.features import volatility


def test_atr_matches_hand_computed_wilder_formula():
    high = [10, 11, 10.5, 12, 11.5, 13, 12.5, 14]
    low = [9, 9.5, 9.8, 10.5, 10.8, 11.5, 11.8, 12.5]
    close = [9.5, 10.5, 10.0, 11.5, 11.0, 12.5, 12.0, 13.5]
    window = 5

    prev_close = [None] + close[:-1]
    true_ranges = []
    for i in range(len(close)):
        if prev_close[i] is None:
            true_ranges.append(high[i] - low[i])
        else:
            true_ranges.append(max(
                high[i] - low[i], abs(high[i] - prev_close[i]), abs(low[i] - prev_close[i]),
            ))

    seed = sum(true_ranges[:window]) / window
    expected_atr = [None] * (window - 1) + [seed]
    for i in range(window, len(true_ranges)):
        expected_atr.append((expected_atr[-1] * (window - 1) + true_ranges[i]) / window)

    df = pd.DataFrame({"high": high, "low": low, "close": close})
    config = {"atr_window": window, "bb_window": 5, "bb_num_std": 2.0, "realized_vol_window": 5}
    out = volatility.compute(df, config)
    atr = out["ATR_14"]

    for i, expected in enumerate(expected_atr):
        if expected is None:
            assert pd.isna(atr.iloc[i])
        else:
            assert abs(atr.iloc[i] - expected) < 1e-9
