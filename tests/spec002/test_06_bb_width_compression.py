"""TEST 6 -- BB Width compression (Spec #002 SS38/SS11).

Construct a compressed price series -> BB Width falls appropriately.
"""
import numpy as np
import pandas as pd

from discovery.features import volatility


def test_bb_width_falls_during_compression():
    n = 100
    rng = np.random.default_rng(42)
    wide = 100 + np.cumsum(rng.normal(0, 1.0, n // 2))       # wide daily range
    tight = wide[-1] + np.cumsum(rng.normal(0, 0.02, n // 2))  # tightly compressed
    close = np.concatenate([wide, tight])
    high = close + 0.5
    low = close - 0.5

    df = pd.DataFrame({"high": high, "low": low, "close": close})
    config = {"atr_window": 14, "bb_window": 20, "bb_num_std": 2.0, "realized_vol_window": 20}
    out = volatility.compute(df, config)

    bb_width = out["BB_width_20"]
    wide_period_width = bb_width.iloc[n // 2 - 5]
    compressed_period_width = bb_width.iloc[-1]
    assert compressed_period_width < wide_period_width
