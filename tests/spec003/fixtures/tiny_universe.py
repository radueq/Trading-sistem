"""Spec #003 TEST_CONFIG -- a small, fast, hand-verifiable universe for
Evaluation Engine integration tests. Kept deliberately tiny (3 securities
+ benchmark, ~70 sessions) so the full run_evaluation() pipeline (one
Discovery pass per session) stays fast in the test suite -- unlike Spec
#002's own 32-security/320-day universe, which is appropriate for
single-as_of Discovery queries but too slow to re-run per session across
an Evaluation window.

COMPQ: wide close-to-close noise for the first 20 sessions (warmup),
then genuinely tighter for the rest -- mirrors Spec #002's own
VOL_COMPRESSED fixture technique (a real volatility-regime change, not
cosmetic OHLC padding). With a small percentile_window (config override,
typically 10-15), BB_width_percentile drops toward the COMPRESSION
bucket for a stretch of sessions after the regime change.
FLAT_A/FLAT_B: unremarkable random-walk fillers, present so the universe
isn't a single security (eligibility/concentration diagnostics need
more than one).
"""
from __future__ import annotations

import numpy as np

from fixtures.market_data import business_days

N = 70
DATES = business_days("2024-01-02", "2024-06-30")[:N]


def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def _bars_from_close(dates, closes) -> list[dict]:
    bars = []
    for d, c in zip(dates, closes):
        bars.append({
            "date": d, "open": round(float(c) * 0.999, 4), "high": round(float(c) * 1.006, 4),
            "low": round(float(c) * 0.994, 4), "close": round(float(c), 4),
            "adj_close": round(float(c), 4), "volume": 500_000,
        })
    return bars


def _dataset(ticker: str, dates, closes) -> dict:
    return {
        "ticker": ticker,
        "info": {"quoteType": "EQUITY", "exchange": "SYNTH", "currency": "USD"},
        "bars": _bars_from_close(dates, closes),
        "splits": {}, "dividends": {},
    }


def _benchmark_closes():
    r = _rng(1)
    return 100 * np.exp(np.cumsum(0.0002 + r.normal(0, 0.004, N)))


def _compq_closes():
    # Genuine close-to-close volatility regime change (not cosmetic OHLC
    # padding) -- wide daily noise for the first `wide_days` sessions,
    # then sharply tighter for the rest, mirroring Spec #002's own
    # VOL_COMPRESSED fixture technique (tests/spec002/fixtures/synthetic_universe.py).
    r = _rng(2)
    wide_days = 20
    wide = r.normal(0, 0.02, wide_days)
    tight = r.normal(0, 0.0015, N - wide_days)
    noise = np.concatenate([wide, tight])
    return 40 * np.exp(np.cumsum(0.0001 + noise))


def _flat_closes(seed):
    r = _rng(seed)
    return 60 * np.exp(np.cumsum(r.normal(0, 0.005, N)))


BENCHMARK = _dataset("SBENCH", DATES, _benchmark_closes())
COMPQ = _dataset("COMPQ", DATES, _compq_closes())
FLAT_A = _dataset("FLATA", DATES, _flat_closes(3))
FLAT_B = _dataset("FLATB", DATES, _flat_closes(4))

NON_BENCHMARK = [COMPQ, FLAT_A, FLAT_B]
ALL_DATASETS = NON_BENCHMARK
