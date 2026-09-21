"""TEST 16 -- Split-adjusted volume (PATCH #001-C, Radu's correction, 2026-09-21).

split_adjusted_volume is the volume-side counterpart of split_adjusted_close:
same PIT-safe split_factor, opposite direction (raw_volume / split_factor,
not raw_close * split_factor), since a split changes price and share count
in opposite directions. Two properties are verified:

1. Mechanical continuity: when raw_volume itself reflects a genuine
   post-split share-count change proportional to the split ratio (the
   real-world case -- turnover in shares is roughly split-ratio-invariant),
   split_adjusted_volume is continuous across the split boundary, for both
   a forward split (4-for-1) and a reverse split (1-for-5, symmetric check
   using the same formula with no special-casing).
2. Round-trip invariant: split_adjusted_close * split_adjusted_volume ==
   raw_close * raw_volume for every bar (ignoring rounding) -- a cheap
   regression guard that fails immediately if the volume formula's
   direction is ever accidentally inverted (multiply instead of divide),
   independent of whether the split_factor value itself is correct (TEST 2
   covers that separately).

raw_volume is never modified -- still exposed unchanged alongside the new
field.
"""
import pytest

from data_foundation.adapters.yfinance_adapter import YFinanceAdapter
from data_foundation.model import ingestion as ing
from data_foundation.pit import access as pit
from fixtures.fake_yfinance import make_ticker_factory
from fixtures.market_data import AAPL_SPLIT_2020, REVERSE_SPLIT, make_bars


@pytest.mark.parametrize("dataset", [AAPL_SPLIT_2020, REVERSE_SPLIT])
def test_split_adjusted_volume_round_trip_invariant(conn, now, dataset):
    ticker = dataset["ticker"]
    adapter = YFinanceAdapter(ticker_factory=make_ticker_factory({ticker: dataset}))
    sid = ing.new_security_id(f"test16:{ticker}")
    ing.ensure_security(conn, sid, adapter, ticker, now)
    start, end = dataset["bars"][0]["date"], dataset["bars"][-1]["date"]
    ing.ingest_prices(conn, adapter, sid, ticker, start, end, now)
    ing.ingest_corporate_actions(conn, adapter, sid, ticker, start, end, now)

    series = pit.get_price_series_as_of(conn, sid, end)
    assert len(series) > 0
    raw_by_date = {b["date"]: b for b in dataset["bars"]}
    for bar in series:
        assert bar.raw_volume is not None and bar.split_adjusted_volume is not None
        raw_turnover = bar.raw_close * bar.raw_volume
        adjusted_turnover = bar.split_adjusted_close * bar.split_adjusted_volume
        assert adjusted_turnover == pytest.approx(raw_turnover, rel=1e-9), (
            f"{bar.date}: split_adjusted_close * split_adjusted_volume "
            f"({adjusted_turnover}) != raw_close * raw_volume ({raw_turnover}) -- "
            "the volume adjustment direction may have been inverted"
        )
        # raw_volume must never be modified by the adjustment
        assert bar.raw_volume == raw_by_date[bar.date]["volume"]


FORWARD_SPLIT_VOLUME = {
    "ticker": "VOL4X",
    "info": {"quoteType": "EQUITY", "exchange": "SYNTH", "currency": "USD"},
    "bars": (
        make_bars("2023-01-02", "2023-01-06", base_price=100.0, volume=100)
        + make_bars("2023-01-09", "2023-01-13", base_price=25.0, volume=400)
    ),
    "splits": {"2023-01-09": 4.0},
    "dividends": {},
}

REVERSE_SPLIT_VOLUME = {
    "ticker": "VOL5R",
    "info": {"quoteType": "EQUITY", "exchange": "SYNTH", "currency": "USD"},
    "bars": (
        make_bars("2023-02-01", "2023-02-03", base_price=2.0, volume=500)
        + make_bars("2023-02-06", "2023-02-08", base_price=10.0, volume=100)
    ),
    "splits": {"2023-02-06": 0.2},
    "dividends": {},
}


@pytest.mark.parametrize("dataset,expected_adjusted_volume", [
    (FORWARD_SPLIT_VOLUME, 400.0),
    (REVERSE_SPLIT_VOLUME, 100.0),
])
def test_split_adjusted_volume_continuous_across_split_boundary(conn, now, dataset, expected_adjusted_volume):
    """Mirrors TEST 2's price-continuity check, for volume: when raw_volume
    already reflects a genuine post-split share-count change proportional
    to the split ratio, split_adjusted_volume must be approximately
    CONSTANT across the boundary -- the split alone must not look like a
    change in trading activity."""
    ticker = dataset["ticker"]
    adapter = YFinanceAdapter(ticker_factory=make_ticker_factory({ticker: dataset}))
    sid = ing.new_security_id(f"test16:{ticker}")
    ing.ensure_security(conn, sid, adapter, ticker, now)
    start, end = dataset["bars"][0]["date"], dataset["bars"][-1]["date"]
    ing.ingest_prices(conn, adapter, sid, ticker, start, end, now)
    ing.ingest_corporate_actions(conn, adapter, sid, ticker, start, end, now)

    series = pit.get_price_series_as_of(conn, sid, end)
    assert len(series) > 0
    for bar in series:
        assert bar.split_adjusted_volume == pytest.approx(expected_adjusted_volume, rel=1e-9), (
            f"{bar.date}: split_adjusted_volume={bar.split_adjusted_volume}, "
            f"expected ~{expected_adjusted_volume} (constant across the split boundary)"
        )
