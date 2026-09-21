"""Spec #002 TEST_CONFIG fixtures -- synthetic securities with known-by-
construction properties.

All fully synthetic, deterministic (numpy `default_rng` with fixed
seeds), no claim of resembling real market data. Named securities are
constructed so a specific feature/reason-code is unambiguously present
by design (documented per dataset below); "filler" securities pad the
universe for cross-sectional/budget/diversity tests that need breadth
rather than a specific property.
"""
from __future__ import annotations

import numpy as np

from fixtures.market_data import business_days

N = 320  # > percentile_window (252) plus buffer for lookback windows
DATES = business_days("2024-01-02", "2025-06-30")[:N]


def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def _bars_from_close(dates, closes, volumes=None) -> list[dict]:
    volumes = volumes if volumes is not None else [500_000] * len(dates)
    bars = []
    for d, c, v in zip(dates, closes, volumes):
        bars.append({
            "date": d, "open": round(float(c) * 0.999, 4), "high": round(float(c) * 1.01, 4),
            "low": round(float(c) * 0.99, 4), "close": round(float(c), 4),
            "adj_close": round(float(c), 4), "volume": int(v),
        })
    return bars


def _dataset(ticker: str, dates, closes, volumes=None) -> dict:
    return {
        "ticker": ticker,
        "info": {"quoteType": "EQUITY", "exchange": "SYNTH", "currency": "USD"},
        "bars": _bars_from_close(dates, closes, volumes),
        "splits": {},
        "dividends": {},
    }


# BENCHMARK: steady moderate growth, low noise (Spec #002 SS10/SS32).
def _benchmark_closes():
    r = _rng(1)
    noise = r.normal(0, 0.004, N)
    return 100 * np.exp(np.cumsum(0.0003 + noise))


BENCHMARK = _dataset("BENCH", DATES, _benchmark_closes())

# TREND_UP: strong steady uptrend, low noise -- clearly above the
# benchmark (TEST 4 trend calculations, TREND_EXTREME).
def _trend_up_closes():
    r = _rng(2)
    noise = r.normal(0, 0.006, N)
    return 50 * np.exp(np.cumsum(0.0018 + noise))


TREND_UP = _dataset("TRNDUP", DATES, _trend_up_closes())

# TREND_FLAT: no drift, small noise -- neutral baseline for contrast.
def _trend_flat_closes():
    r = _rng(3)
    return 60 * np.exp(np.cumsum(r.normal(0, 0.004, N)))


TREND_FLAT = _dataset("TRNDFLAT", DATES, _trend_flat_closes())

# VOL_COMPRESSED: shrinking daily range for the first 70% (compression),
# then sharply expanding (TEST 6 BB Width, VOLATILITY_COMPRESSION/
# EXPANSION reason codes, transition acceleration).
def _vol_compressed_closes():
    r = _rng(4)
    n1 = int(N * 0.7)
    n2 = N - n1
    vol_path = np.concatenate([np.linspace(0.010, 0.001, n1), np.linspace(0.001, 0.020, n2)])
    noise = r.normal(0, 1, N) * vol_path
    return 80 * np.exp(np.cumsum(noise))


VOL_COMPRESSED = _dataset("VOLCOMP", DATES, _vol_compressed_closes())

# VOLUME_SPIKE: steady baseline volume, single sharp spike near the end
# (TEST 8 RVOL/volume percentile, VOLUME_ANOMALY).
def _volume_spike_closes_and_volumes():
    closes = 70 * np.exp(np.cumsum(_rng(5).normal(0, 0.005, N)))
    volumes = [500_000] * N
    volumes[-1] = 6_000_000  # spike lands exactly on the last (as_of) bar
    return closes, volumes


_vs_closes, _vs_volumes = _volume_spike_closes_and_volumes()
VOLUME_SPIKE = _dataset("VOLSPK", DATES, _vs_closes, _vs_volumes)

# MOMENTUM_ACCEL: flat/low drift for the first 80%, then linearly
# ramping drift -- ROC increasing at an increasing rate near as_of
# (TEST 9 momentum delta/acceleration, MOMENTUM_ACCELERATION).
def _momentum_accel_closes():
    r = _rng(6)
    flat = int(N * 0.8)
    accel = N - flat
    drift = np.concatenate([np.full(flat, 0.0002), np.linspace(0.0002, 0.0040, accel)])
    noise = r.normal(0, 0.004, N)
    return 40 * np.exp(np.cumsum(drift + noise))


MOMENTUM_ACCEL = _dataset("MOMACC", DATES, _momentum_accel_closes())

# RS_STRONG: clearly outperforms the benchmark (TEST 5 relative
# strength, RS_EXTREME).
def _rs_strong_closes():
    r = _rng(7)
    return 30 * np.exp(np.cumsum(0.0025 + r.normal(0, 0.005, N)))


RS_STRONG = _dataset("RSSTRONG", DATES, _rs_strong_closes())

# INSUFFICIENT_HISTORY: much shorter series than percentile_window
# (TEST 10 missing history -> explicit status, no silent calculation).
_SHORT_DATES = DATES[-30:]


def _insufficient_history_closes():
    r = _rng(8)
    return 20 * np.exp(np.cumsum(r.normal(0, 0.01, len(_SHORT_DATES))))


INSUFFICIENT_HISTORY = _dataset("SHORTHIST", _SHORT_DATES, _insufficient_history_closes())


def _filler_dataset(i: int) -> dict:
    r = _rng(100 + i)
    drift = r.uniform(-0.0010, 0.0010)
    noise = r.normal(0, r.uniform(0.004, 0.010), N)
    closes = (20 + i) * np.exp(np.cumsum(drift + noise))
    volumes = r.integers(300_000, 900_000, N)
    return _dataset(f"FILL{i:02d}", DATES, closes, volumes)


FILLERS = [_filler_dataset(i) for i in range(25)]

NAMED_SECURITIES = {
    "TREND_UP": TREND_UP,
    "TREND_FLAT": TREND_FLAT,
    "VOL_COMPRESSED": VOL_COMPRESSED,
    "VOLUME_SPIKE": VOLUME_SPIKE,
    "MOMENTUM_ACCEL": MOMENTUM_ACCEL,
    "RS_STRONG": RS_STRONG,
    "INSUFFICIENT_HISTORY": INSUFFICIENT_HISTORY,
}

ALL_DATASETS = list(NAMED_SECURITIES.values()) + FILLERS

AS_OF = BENCHMARK["bars"][-1]["date"]
