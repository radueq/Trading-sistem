"""Lane E -- Momentum/Change features (Spec #002 SS13).

ROC_n = close(t)/close(t-n) - 1 (same family as Lane A's returns, at
shorter horizons -- kept as its own lane per Spec #002's structure).
momentum_delta / momentum_acceleration represent X(t), delta X(t),
delta^2 X(t) on the config-selected driving ROC window (TEST_CONFIG) --
never turned into BUY/SELL signals (Spec #002 SS13).
"""
from __future__ import annotations

import pandas as pd


def compute(df: pd.DataFrame, config: dict) -> dict[str, pd.Series]:
    close = df["close"]
    out: dict[str, pd.Series] = {}

    for w in config["roc_windows"]:
        out[f"ROC_{w}"] = close / close.shift(w) - 1.0

    driving = out[f"ROC_{config['driving_roc_window']}"]
    momentum_delta = driving.diff(1)
    out["momentum_delta"] = momentum_delta
    out["momentum_acceleration"] = momentum_delta.diff(1)

    return out
