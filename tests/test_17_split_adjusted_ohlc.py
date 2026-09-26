"""TEST 17 -- Split-adjusted OHLC completion (PATCH #001-D, GPT Review
#005 scaffold blocker A, 2026-09-26).

Before this patch, PITPriceBar exposed split_adjusted_close and
split_adjusted_volume but not split_adjusted_open/high/low -- a
Backtester needs the full adjusted OHLC bar (NEXT_BAR_OPEN executable
entry price, MAE/MFE from adjusted high/low). The fix reuses the exact
same PIT-safe split_adjustment_factor already used for
split_adjusted_close, applied identically to raw_open/raw_high/raw_low --
no new adjustment methodology, no schema change.

Four properties are verified:
1. Factor correctness: split_adjusted_open/high/low == raw_open/high/low
   * split_adjustment_factor, for both a forward split (AAPL, 4-for-1)
   and a reverse split (RVSQ, 1-for-5) -- mirrors TEST 2's close-only
   check, extended to the three new fields.
2. OHLC ordering preservation: split_adjusted_low <= split_adjusted_open,
   split_adjusted_close <= split_adjusted_high for every bar -- scaling
   by a positive factor must never invert the bar's own internal
   ordering.
3. Continuity across the split boundary, mirroring TEST 2's own
   continuity check but for open/high/low, not just close.
4. Knowledge-time/PIT immunity: mirrors TEST 9 exactly (get_data(as_of=X)
   must be byte-identical before and after the store learns about a
   split dated after X) -- but asserts specifically on the three NEW
   fields, since they are computed via a code path (the as_of-scoped
   `factors` dict) shared with split_adjusted_close, and this proves
   that sharing actually holds for OHLC too, not just close.
"""
import pytest

from data_foundation.adapters.yfinance_adapter import YFinanceAdapter
from data_foundation.model import ingestion as ing, repository as repo
from data_foundation.pit import access as pit
from fixtures.fake_yfinance import make_ticker_factory
from fixtures.market_data import AAPL_SPLIT_2020, REVERSE_SPLIT


def _ingest(conn, now, dataset, tag):
    ticker = dataset["ticker"]
    adapter = YFinanceAdapter(ticker_factory=make_ticker_factory({ticker: dataset}))
    sid = ing.new_security_id(f"{tag}:{ticker}")
    ing.ensure_security(conn, sid, adapter, ticker, now)
    start, end = dataset["bars"][0]["date"], dataset["bars"][-1]["date"]
    ing.ingest_prices(conn, adapter, sid, ticker, start, end, now)
    ing.ingest_corporate_actions(conn, adapter, sid, ticker, start, end, now)
    return sid, end


@pytest.mark.parametrize("dataset,expected_ratio", [
    (AAPL_SPLIT_2020, 4.0),
    (REVERSE_SPLIT, 0.2),
])
def test_split_adjusted_ohlc_factor_correctness(conn, now, dataset, expected_ratio):
    sid, end = _ingest(conn, now, dataset, "test17a")
    raw_by_date = {b.date: b for b in repo.get_price_history(conn, sid)}

    series = pit.get_price_series_as_of(conn, sid, end)
    assert len(series) > 0
    for bar in series:
        raw = raw_by_date[bar.date]
        if raw.raw_close is None:
            continue
        # Same split_factor implicitly recovered from close, then applied
        # identically to open/high/low -- proves all four fields share
        # ONE per-date factor, not four independent computations.
        factor = bar.split_adjusted_close / raw.raw_close
        assert bar.split_adjusted_open == pytest.approx(raw.raw_open * factor, rel=1e-9)
        assert bar.split_adjusted_high == pytest.approx(raw.raw_high * factor, rel=1e-9)
        assert bar.split_adjusted_low == pytest.approx(raw.raw_low * factor, rel=1e-9)
        # raw_* must never be modified by the adjustment
        assert bar.raw_open == raw.raw_open
        assert bar.raw_high == raw.raw_high
        assert bar.raw_low == raw.raw_low


@pytest.mark.parametrize("dataset", [AAPL_SPLIT_2020, REVERSE_SPLIT])
def test_split_adjusted_ohlc_ordering_preserved(conn, now, dataset):
    sid, end = _ingest(conn, now, dataset, "test17b")
    series = pit.get_price_series_as_of(conn, sid, end)
    assert len(series) > 0
    for bar in series:
        if bar.split_adjusted_low is None:
            continue
        assert bar.split_adjusted_low <= bar.split_adjusted_open <= bar.split_adjusted_high, (
            f"{bar.date}: adjusted_low={bar.split_adjusted_low} <= "
            f"adjusted_open={bar.split_adjusted_open} <= adjusted_high={bar.split_adjusted_high} violated"
        )
        assert bar.split_adjusted_low <= bar.split_adjusted_close <= bar.split_adjusted_high, (
            f"{bar.date}: adjusted_low={bar.split_adjusted_low} <= "
            f"adjusted_close={bar.split_adjusted_close} <= adjusted_high={bar.split_adjusted_high} violated"
        )


@pytest.mark.parametrize("dataset,expected_ratio", [
    (AAPL_SPLIT_2020, 4.0),
    (REVERSE_SPLIT, 0.2),
])
def test_split_adjusted_ohlc_continuous_across_split_boundary(conn, now, dataset, expected_ratio):
    sid, end = _ingest(conn, now, dataset, "test17c")
    actions = repo.get_corporate_actions(conn, sid)
    matching = [a for a in actions if a.value == expected_ratio]
    assert len(matching) == 1
    effective_date = matching[0].effective_date

    series = {b.date: b for b in pit.get_price_series_as_of(conn, sid, end)}
    dates_sorted = sorted(series)
    boundary_idx = dates_sorted.index(effective_date)
    for field in ("split_adjusted_open", "split_adjusted_high", "split_adjusted_low"):
        pre = getattr(series[dates_sorted[boundary_idx - 1]], field)
        post = getattr(series[dates_sorted[boundary_idx]], field)
        jump = abs(post - pre) / pre
        assert jump < 0.05, (
            f"{field} should be continuous across the split boundary, got {jump:.2%} jump"
        )


def test_split_adjusted_ohlc_pit_immune_before_split_knowable(conn, now):
    """Mirrors TEST 9 exactly, asserting on the new OHLC fields
    specifically -- proves the as_of-scoped `factors` computation that
    already protects split_adjusted_close also protects
    split_adjusted_open/high/low, with no separate code path to get PIT
    safety wrong in."""
    ticker = AAPL_SPLIT_2020["ticker"]
    adapter = YFinanceAdapter(ticker_factory=make_ticker_factory({ticker: AAPL_SPLIT_2020}))
    sid = ing.new_security_id(f"test17d:{ticker}")
    ing.ensure_security(conn, sid, adapter, ticker, now)

    as_of = "2020-08-26"  # strictly before the split's effective_date (2020-08-31)
    pre_bars = [b for b in AAPL_SPLIT_2020["bars"] if b["date"] <= as_of]
    ing.ingest_prices(conn, adapter, sid, ticker, pre_bars[0]["date"], as_of, now)

    series_before = pit.get_price_series_as_of(conn, sid, as_of)
    ohlc_before = [(b.date, b.split_adjusted_open, b.split_adjusted_high, b.split_adjusted_low) for b in series_before]

    all_dates = [b["date"] for b in AAPL_SPLIT_2020["bars"]]
    ing.ingest_prices(conn, adapter, sid, ticker, all_dates[0], all_dates[-1], now)
    ing.ingest_corporate_actions(conn, adapter, sid, ticker, all_dates[0], all_dates[-1], now)
    assert as_of < repo.get_corporate_actions(conn, sid)[0].effective_date

    series_after = pit.get_price_series_as_of(conn, sid, as_of)
    ohlc_after = [(b.date, b.split_adjusted_open, b.split_adjusted_high, b.split_adjusted_low) for b in series_after]

    assert ohlc_before == ohlc_after, (
        "split_adjusted_open/high/low changed after future-dated split data was ingested -- "
        "look-ahead leakage in the OHLC completion"
    )
