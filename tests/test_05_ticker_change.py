"""TEST 5 -- Ticker change (Spec #001 SS23).

OLD_TICKER -> same security_id -> NEW_TICKER. History must remain
continuous under one internal identity across the rename. Uses the real
FB -> META rename (effective 2022-06-09) as the event anchor -- see
tests/fixtures/market_data.py for provenance of the (synthetic) prices.
"""
from data_foundation.adapters.yfinance_adapter import YFinanceAdapter
from data_foundation.model import ingestion as ing, repository as repo
from data_foundation.pit import access as pit
from fixtures.fake_yfinance import make_ticker_factory
from fixtures.market_data import TICKER_CHANGE_FB, TICKER_CHANGE_META, TICKER_CHANGE_RENAME_DATE


def test_ticker_change_preserves_continuous_history(conn, now):
    factory = make_ticker_factory({"FB": TICKER_CHANGE_FB, "META": TICKER_CHANGE_META})
    adapter = YFinanceAdapter(ticker_factory=factory)
    sid = ing.new_security_id("yfinance:FB_META:2022_rename")

    ing.ensure_security(conn, sid, adapter, "FB", now)

    fb_start, fb_end = TICKER_CHANGE_FB["bars"][0]["date"], TICKER_CHANGE_FB["bars"][-1]["date"]
    meta_start, meta_end = TICKER_CHANGE_META["bars"][0]["date"], TICKER_CHANGE_META["bars"][-1]["date"]

    ing.ensure_symbol_history(conn, sid, "FB", fb_start, TICKER_CHANGE_RENAME_DATE, "yfinance")
    ing.ensure_symbol_history(conn, sid, "META", TICKER_CHANGE_RENAME_DATE, None, "yfinance")

    ing.ingest_prices(conn, adapter, sid, "FB", fb_start, fb_end, now)
    ing.ingest_prices(conn, adapter, sid, "META", meta_start, meta_end, now)

    assert pit.get_ticker_as_of(conn, sid, "2022-06-05") == "FB"
    assert pit.get_ticker_as_of(conn, sid, TICKER_CHANGE_RENAME_DATE) == "META"
    assert pit.get_security_id_for_ticker_as_of(conn, "FB", "2022-06-05") == sid
    assert pit.get_security_id_for_ticker_as_of(conn, "META", "2022-06-12") == sid

    all_dates = {b.date for b in repo.get_price_history(conn, sid)}
    expected = {b["date"] for b in TICKER_CHANGE_FB["bars"]} | {b["date"] for b in TICKER_CHANGE_META["bars"]}
    assert all_dates == expected, "history must be continuous across the rename under one security_id"
