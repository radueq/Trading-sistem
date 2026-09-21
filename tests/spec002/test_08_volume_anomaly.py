"""TEST 8 -- Volume anomaly (Spec #002 SS38/SS12).

Known volume spike -> RVOL/percentile behaves correctly.
"""
import pandas as pd
import pytest

from discovery.features import volume


def test_volume_spike_produces_high_rvol():
    n = 40
    volumes = [500_000] * n
    volumes[-1] = 5_000_000  # 10x spike on the last (as_of) bar

    df = pd.DataFrame({"volume": volumes})
    config = {"adv_window": 20}
    out = volume.compute(df, config)

    rvol = out["RVOL_20"].iloc[-1]
    assert rvol > 8.0  # ADV_20 excludes today, so still ~500k baseline -> ~10x
    assert out["volume_ratio_20"].iloc[-1] == rvol  # documented alias, see volume.py

    # a normal day elsewhere should NOT look anomalous
    assert out["RVOL_20"].iloc[25] == pytest.approx(1.0, abs=0.05)
