"""TEST 9 -- Momentum delta/acceleration (Spec #002 SS38/SS13).

Synthetic acceleration -> expected Delta/Delta^2 (X(t), DeltaX(t),
Delta^2 X(t)).
"""
import pandas as pd

from discovery.features import momentum


def test_momentum_acceleration_on_synthetic_series():
    n = 40
    # quadratic price path -> genuinely accelerating ROC near the end
    closes = [100.0 + 0.01 * i * i for i in range(n)]
    df = pd.DataFrame({"close": closes})
    config = {"roc_windows": [5, 10, 20], "driving_roc_window": 10}

    out = momentum.compute(df, config)
    roc10 = out["ROC_10"]
    delta = out["momentum_delta"]
    accel = out["momentum_acceleration"]
    last = n - 1

    expected_roc10 = closes[last] / closes[last - 10] - 1.0
    assert abs(roc10.iloc[last] - expected_roc10) < 1e-9

    expected_delta = roc10.iloc[last] - roc10.iloc[last - 1]
    assert abs(delta.iloc[last] - expected_delta) < 1e-9

    expected_accel = delta.iloc[last] - delta.iloc[last - 1]
    assert abs(accel.iloc[last] - expected_accel) < 1e-9

    assert delta.iloc[last] > 0
