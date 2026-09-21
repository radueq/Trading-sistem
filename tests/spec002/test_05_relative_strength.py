"""TEST 5 -- Relative Strength (Spec #002 SS38/SS10).

Ticker vs benchmark synthetic series -> manually verifiable RS
(relative_return_Nd = ticker's N-day return - benchmark's N-day return).
"""
import pandas as pd

from discovery.features import relative_strength


def test_relative_strength_manual():
    n = 200
    dates = [str(i) for i in range(n)]
    ticker_closes = [100.0 * (1.001 ** i) for i in range(n)]
    bench_closes = [100.0 * (1.0005 ** i) for i in range(n)]

    df = pd.DataFrame({"date": dates, "close": ticker_closes})
    bench_df = pd.DataFrame({"date": dates, "close": bench_closes})
    config = {"return_windows": [20, 63, 126]}

    out = relative_strength.compute(df, bench_df, config)
    last = n - 1

    ticker_ret_63 = ticker_closes[last] / ticker_closes[last - 63] - 1.0
    bench_ret_63 = bench_closes[last] / bench_closes[last - 63] - 1.0
    expected = ticker_ret_63 - bench_ret_63

    assert abs(out["relative_return_63d"].iloc[last] - expected) < 1e-9
    assert out["relative_return_63d"].iloc[last] > 0  # ticker clearly outperforms


def test_relative_strength_zero_against_self():
    n = 100
    dates = [str(i) for i in range(n)]
    closes = [50.0 * (1.0008 ** i) for i in range(n)]
    df = pd.DataFrame({"date": dates, "close": closes})
    config = {"return_windows": [20, 63]}

    out = relative_strength.compute(df, df, config)
    assert abs(out["relative_return_63d"].iloc[-1]) < 1e-9
