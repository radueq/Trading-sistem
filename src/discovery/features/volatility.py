"""Lane C -- Volatility features (Spec #002 SS11).

ATR and Bollinger Band Width are deliberately NOT interchangeable (Spec
#002 SS11): ATR captures absolute/relative volatility, BB Width
captures compression. Both computed explicitly, plus realized
volatility (rolling stdev of log returns).

ATR uses the classic Wilder recursive smoothing (seeded by a plain mean
of the first `atr_window` true ranges, then recursively smoothed),
chosen over an exponential-weighted approximation specifically so a
small synthetic OHLC sequence stays hand-verifiable (Spec #002 TEST 7).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _wilders_atr(true_range: pd.Series, window: int) -> pd.Series:
    atr = pd.Series([float("nan")] * len(true_range), index=true_range.index)
    if len(true_range) < window or true_range.iloc[:window].isna().any():
        return atr
    atr.iloc[window - 1] = true_range.iloc[:window].mean()
    for i in range(window, len(true_range)):
        prev = atr.iloc[i - 1]
        tr_i = true_range.iloc[i]
        if pd.isna(prev) or pd.isna(tr_i):
            continue
        atr.iloc[i] = (prev * (window - 1) + tr_i) / window
    return atr


def compute(df: pd.DataFrame, config: dict) -> dict[str, pd.Series]:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)

    true_range = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)

    atr_window = config["atr_window"]
    atr = _wilders_atr(true_range, atr_window)

    bb_window = config["bb_window"]
    num_std = config["bb_num_std"]
    bb_sma = close.rolling(window=bb_window, min_periods=bb_window).mean()
    bb_std = close.rolling(window=bb_window, min_periods=bb_window).std(ddof=0)
    bb_width = ((bb_sma + num_std * bb_std) - (bb_sma - num_std * bb_std)) / bb_sma

    rv_window = config["realized_vol_window"]
    log_return = np.log(close / close.shift(1))
    realized_vol = log_return.rolling(window=rv_window, min_periods=rv_window).std(ddof=0)

    # Feature names are fixed literal labels matching Spec #002's exact
    # naming (ATR_14, BB_width_20), independent of the configured
    # atr_window/bb_window value -- the same convention Spec #002 uses
    # for these two (a single named feature, not a list like the return
    # windows). Default config uses window=14/20 to match the labels;
    # tests may override the window (e.g. for a small hand-verifiable
    # series) without the output key changing.
    return {
        "ATR_14": atr,
        "ATR_pct": atr / close,
        "BB_width_20": bb_width,
        "realized_volatility_20": realized_vol,
    }
