"""TEST 7 -- Missing data (Spec #001 SS23).

An artificially injected missing bar must be detected and reported via
a reason code, with no silent forward-fill (SS17): no price_history row
may be synthesized for the gap.
"""
from data_foundation.adapters.yfinance_adapter import YFinanceAdapter
from data_foundation.model import ingestion as ing, repository as repo
from data_foundation.qa import engine as qa
from fixtures.fake_yfinance import make_ticker_factory
from fixtures.market_data import MISSING_BAR


def test_missing_bar_detected_without_silent_fill(conn, now):
    ticker = MISSING_BAR["ticker"]
    adapter = YFinanceAdapter(ticker_factory=make_ticker_factory({ticker: MISSING_BAR}))
    sid = ing.new_security_id(f"yfinance:{ticker}")
    ing.ensure_security(conn, sid, adapter, ticker, now)
    start, end = MISSING_BAR["bars"][0]["date"], MISSING_BAR["bars"][-1]["date"]
    ing.ingest_prices(conn, adapter, sid, ticker, start, end, now)

    missing_date = MISSING_BAR["missing_date"]

    stored_dates = {b.date for b in repo.get_price_history(conn, sid)}
    assert missing_date not in stored_dates, "no bar should be synthesized for the gap (no silent fill)"

    results = {r.date: r for r in qa.run_and_store_qa_checks(conn, sid)}
    assert "MISSING_BAR" in results[missing_date].reason_codes
