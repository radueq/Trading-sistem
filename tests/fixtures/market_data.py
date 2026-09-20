"""TEST_CONFIG fixture data for the Spec #001 Level 1 test suite.

TEST_CONFIG, not DEFAULT_TRADING_RULES (Spec #001 SS16): nothing here is a
trading rule, threshold, or universe-eligibility criterion. It exists
solely to exercise adapter/model/PIT/QA software correctness.

Live network access to Yahoo Finance is blocked in this execution sandbox
(see docs/known_limitations.md) -- these fixtures stand in for live
yfinance pulls. Provenance per case, so nobody downstream mistakes a
synthetic placeholder for a verified real quote:

- AAPL_SPLIT_2020 (ticker "AAPL"): REAL anchor. Apple Inc executed a
  well-documented 4-for-1 forward stock split with ex-date 2020-08-31.
  That ratio and date are real public facts. The OHLC values are
  synthetic placeholders (NOT verified real market prices), built to be
  internally consistent (exact 4x scale change across the split) so the
  adjustment math is exercised correctly.
- REVERSE_SPLIT (ticker "RVSQ", fictitious): fully synthetic. Reverse
  splits are a common real-world corporate action (e.g. post-crisis bank
  reverse splits); no specific real case is claimed here, only the 1-for-5
  (ratio 0.2) math direction is exercised.
- DIVIDEND (ticker "DIVQ", fictitious): fully synthetic, one dividend
  event, to exercise dividend identification vs split confusion.
- TICKER_CHANGE (tickers "FB" then "META", one security): REAL anchor.
  Facebook, Inc. changed its ticker to META effective 2022-06-09 (company
  rename to Meta Platforms). OHLC values are synthetic placeholders,
  continuity-consistent across the rename.
- TICKER_REUSE (ticker "ZZZQ", fictitious, deliberately not a real
  symbol): fully synthetic. Two unrelated fictitious companies use the
  same ticker in different eras.
- DELISTING (ticker "TDLC", fictitious): fully synthetic, shaped like a
  real-world abrupt delisting (e.g. bankruptcy) without claiming to
  reproduce any specific real case.
- MISSING_BAR (ticker "MISSQ", fictitious): fully synthetic, one
  otherwise-expected weekday bar is deliberately omitted.

All date ranges are chosen to avoid US market holidays so the Level 1 QA
missing-bar check (weekday calendar only, no holiday calendar -- see
Known Limitations) doesn't produce false positives outside the
deliberately injected gap.
"""
from __future__ import annotations

from datetime import date, timedelta


def business_days(start: str, end: str) -> list[str]:
    d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    out = []
    d = d0
    while d <= d1:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def make_bars(start: str, end: str, base_price: float, daily_drift: float = 0.0,
              volume: int = 1_000_000, skip_dates: set[str] | None = None) -> list[dict]:
    skip_dates = skip_dates or set()
    bars = []
    price = base_price
    for d in business_days(start, end):
        if d in skip_dates:
            price += daily_drift
            continue
        bars.append({
            "date": d,
            "open": round(price * 0.998, 4),
            "high": round(price * 1.01, 4),
            "low": round(price * 0.99, 4),
            "close": round(price, 4),
            "adj_close": round(price, 4),
            "volume": volume,
        })
        price += daily_drift
    return bars


# --- AAPL_SPLIT_2020 ---------------------------------------------------
_aapl_pre = make_bars("2020-08-24", "2020-08-28", base_price=500.0, daily_drift=-0.5)
_aapl_post = make_bars("2020-08-31", "2020-09-04", base_price=125.0, daily_drift=0.2)
AAPL_SPLIT_2020 = {
    "ticker": "AAPL",
    "info": {"quoteType": "EQUITY", "exchange": "NMS", "currency": "USD"},
    "bars": _aapl_pre + _aapl_post,
    "splits": {"2020-08-31": 4.0},
    "dividends": {},
}

# --- REVERSE_SPLIT (synthetic) -----------------------------------------
_rvsq_pre = make_bars("2019-01-02", "2019-01-04", base_price=2.0, daily_drift=0.0)
_rvsq_post = make_bars("2019-01-07", "2019-01-09", base_price=10.0, daily_drift=0.0)
REVERSE_SPLIT = {
    "ticker": "RVSQ",
    "info": {"quoteType": "EQUITY", "exchange": "SYNTH", "currency": "USD"},
    "bars": _rvsq_pre + _rvsq_post,
    "splits": {"2019-01-07": 0.2},
    "dividends": {},
}

# --- DIVIDEND (synthetic) ----------------------------------------------
DIVIDEND = {
    "ticker": "DIVQ",
    "info": {"quoteType": "EQUITY", "exchange": "SYNTH", "currency": "USD"},
    "bars": make_bars("2021-03-01", "2021-03-10", base_price=50.0, daily_drift=0.1),
    "splits": {},
    "dividends": {"2021-03-05": 0.50},
}

# --- TICKER_CHANGE: FB -> META (real event, synthetic prices) ----------
_fb_bars = make_bars("2022-06-01", "2022-06-08", base_price=190.0, daily_drift=0.3)
_meta_bars = make_bars("2022-06-09", "2022-06-15", base_price=192.4, daily_drift=0.3)
TICKER_CHANGE_FB = {
    "ticker": "FB",
    "info": {"quoteType": "EQUITY", "exchange": "NMS", "currency": "USD"},
    "bars": _fb_bars,
    "splits": {},
    "dividends": {},
}
TICKER_CHANGE_META = {
    "ticker": "META",
    "info": {"quoteType": "EQUITY", "exchange": "NMS", "currency": "USD"},
    "bars": _meta_bars,
    "splits": {},
    "dividends": {},
}
TICKER_CHANGE_RENAME_DATE = "2022-06-09"

# --- TICKER_REUSE (fully synthetic) -------------------------------------
TICKER_REUSE_COMPANY_A = {
    "ticker": "ZZZQ",
    "info": {"quoteType": "EQUITY", "exchange": "SYNTH", "currency": "USD"},
    "bars": make_bars("2015-01-02", "2015-01-09", base_price=8.0, daily_drift=-0.1),
    "splits": {},
    "dividends": {},
    "delisted_effective": "2015-01-12",
}
TICKER_REUSE_COMPANY_B = {
    "ticker": "ZZZQ",
    "info": {"quoteType": "EQUITY", "exchange": "SYNTH", "currency": "USD"},
    "bars": make_bars("2021-01-04", "2021-01-11", base_price=30.0, daily_drift=0.5),
    "splits": {},
    "dividends": {},
}

# --- DELISTING (fully synthetic) ----------------------------------------
DELISTING = {
    "ticker": "TDLC",
    "info": {"quoteType": "EQUITY", "exchange": "SYNTH", "currency": "USD"},
    "bars": make_bars("2019-01-02", "2019-01-15", base_price=12.0, daily_drift=-0.6),
    "splits": {},
    "dividends": {},
    "delisted_effective": "2019-01-16",
    "delisting_reason": "bankruptcy (synthetic test case)",
}

# --- OHLC_INVALID (fully synthetic, deliberately corrupted) -------------
_ohlcq_bars = make_bars("2022-05-02", "2022-05-06", base_price=20.0, daily_drift=0.1)
# Corrupt one bar: low > high (impossible) and negative close on another.
_ohlcq_bars[2] = {**_ohlcq_bars[2], "low": 25.0, "high": 19.0}
_ohlcq_bars[3] = {**_ohlcq_bars[3], "close": -5.0}
OHLC_INVALID = {
    "ticker": "OHLCQ",
    "info": {"quoteType": "EQUITY", "exchange": "SYNTH", "currency": "USD"},
    "bars": _ohlcq_bars,
    "splits": {},
    "dividends": {},
    "invalid_dates": {_ohlcq_bars[2]["date"]: "OHLC_INVALID", _ohlcq_bars[3]["date"]: "NEGATIVE_PRICE"},
}

# --- MISSING_BAR (fully synthetic) --------------------------------------
MISSING_BAR = {
    "ticker": "MISSQ",
    "info": {"quoteType": "EQUITY", "exchange": "SYNTH", "currency": "USD"},
    "bars": make_bars("2022-02-01", "2022-02-10", base_price=40.0, daily_drift=0.15,
                       skip_dates={"2022-02-04"}),
    "splits": {},
    "dividends": {},
    "missing_date": "2022-02-04",
}
