"""Lane A -- Trend features (Spec #002 SS9).

Inputs: a local, already-PIT-scoped OHLCV DataFrame (split-adjusted
close), ascending by date. Outputs the FULL time series of each raw
feature (needed downstream for time-series percentile normalization),
not just the as_of value.

No `trend_score` / composite alpha-flavored field is computed here --
Spec #002 SS9 explicitly forbids it. Individual measurements stay
observable.
"""
from __future__ import annotations

import pandas as pd


def compute(df: pd.DataFrame, config: dict) -> dict[str, pd.Series]:
    close = df["close"]
    out: dict[str, pd.Series] = {}

    for w in config["return_windows"]:
        out[f"return_{w}d"] = close / close.shift(w) - 1.0

    for w in config["sma_windows"]:
        sma = close.rolling(window=w, min_periods=w).mean()
        out[f"sma_{w}"] = sma
        out[f"distance_sma{w}"] = close / sma - 1.0

    slope_window = config["slope_window"]
    for w in config.get("slope_windows", []):
        if f"sma_{w}" not in out:
            continue  # only computed for windows that are also in sma_windows
        sma = out[f"sma_{w}"]
        # average per-period % change of the SMA over slope_window --
        # positive = rising SMA, negative = falling.
        out[f"slope_sma{w}"] = (sma / sma.shift(slope_window) - 1.0) / slope_window

    return out
