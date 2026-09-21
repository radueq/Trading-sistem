"""Lane B -- Relative Strength features (Spec #002 SS10).

relative_return_Nd = ticker's N-day return - benchmark's N-day return
(a simple difference, chosen for being easy to hand-verify -- Spec #002
TEST 5). `rs_percentile_cross_sectional` is NOT computed here -- it
needs the whole eligible universe at once, so it's computed in
discovery/engine.py's cross-sectional pass over relative_return_63d.

Benchmark handling is entirely data/config driven (Spec #002 SS10/SS32):
no specific benchmark ticker string is ever hardcoded in this module --
the caller supplies benchmark_df, fetched the same way as any other
security's PIT price series, so switching benchmarks is a config/data
change, never a code change (see TEST 20).
"""
from __future__ import annotations

import pandas as pd


def compute(df: pd.DataFrame, benchmark_df: pd.DataFrame, config: dict) -> dict[str, pd.Series]:
    merged = df[["date", "close"]].merge(
        benchmark_df[["date", "close"]], on="date", how="left", suffixes=("", "_benchmark"),
    )
    close = merged["close"]
    bench_close = merged["close_benchmark"]

    out: dict[str, pd.Series] = {}
    for w in config["return_windows"]:
        ticker_return = close / close.shift(w) - 1.0
        benchmark_return = bench_close / bench_close.shift(w) - 1.0
        out[f"relative_return_{w}d"] = ticker_return - benchmark_return
    return out
