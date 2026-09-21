"""Lane D -- Volume features (Spec #002 SS12).

ADV_20 is the trailing 20-day average volume EXCLUDING the current day
(a reference baseline that doesn't include the day being measured,
avoiding self-referential inflation) -- a documented Level 1 choice,
not claimed to be the only valid convention.

RVOL_20 and volume_ratio_20 are intentionally the SAME ratio
(volume / ADV_20): Spec #002 SS12 lists both names in its minimum
feature list without distinguishing them, and inventing an arbitrary
difference the spec doesn't specify would be worse than being explicit
that they're aliases of one computation.

No unusual-options-activity detection -- out of scope (Spec #002 SS12).
"""
from __future__ import annotations

import pandas as pd


def compute(df: pd.DataFrame, config: dict) -> dict[str, pd.Series]:
    volume = df["volume"].astype(float)
    window = config["adv_window"]

    adv_20 = volume.shift(1).rolling(window=window, min_periods=window).mean()
    rvol_20 = volume / adv_20

    return {
        "volume": volume,
        "ADV_20": adv_20,
        "RVOL_20": rvol_20,
        "volume_ratio_20": rvol_20,
    }
