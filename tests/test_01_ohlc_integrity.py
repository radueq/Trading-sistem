"""TEST 1 -- OHLC integrity (Spec #001 SS23).

low <= open <= high and low <= close <= high must hold for every bar;
violations (and negative prices) must be detected by Data QA, not
silently accepted.
"""
from data_foundation.adapters.yfinance_adapter import YFinanceAdapter
from data_foundation.model import ingestion as ing
from data_foundation.qa import engine as qa
from fixtures.fake_yfinance import make_ticker_factory
from fixtures.market_data import OHLC_INVALID


def test_ohlc_integrity_detects_invalid_bars(conn, now):
    ticker = OHLC_INVALID["ticker"]
    adapter = YFinanceAdapter(ticker_factory=make_ticker_factory({ticker: OHLC_INVALID}))
    sid = ing.new_security_id(f"yfinance:{ticker}")
    ing.ensure_security(conn, sid, adapter, ticker, now)
    start, end = OHLC_INVALID["bars"][0]["date"], OHLC_INVALID["bars"][-1]["date"]
    ing.ingest_prices(conn, adapter, sid, ticker, start, end, now)

    results = qa.run_and_store_qa_checks(conn, sid)
    by_date = {r.date: r for r in results}

    for date, expected_code in OHLC_INVALID["invalid_dates"].items():
        assert expected_code in by_date[date].reason_codes, (
            f"expected {expected_code} on {date}, got {by_date[date].reason_codes}"
        )
        assert by_date[date].qa_pass is False, f"{date} should fail QA (ERROR severity)"

    clean_date = OHLC_INVALID["bars"][0]["date"]
    assert by_date[clean_date].reason_codes == []
    assert by_date[clean_date].qa_pass is True
