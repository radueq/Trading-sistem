"""TEST 12 -- Universe sanity (Spec #001 SS23).

A plausibility check, not exact equality: the ingested Level 1 test
universe's size and per-security bar counts should be in the right
ballpark given what was fed into it.
"""
from data_foundation.adapters.yfinance_adapter import YFinanceAdapter
from data_foundation.model import ingestion as ing, repository as repo
from fixtures import market_data as md
from fixtures.fake_yfinance import make_ticker_factory

UNIVERSE = [
    ("yfinance:AAPL", "AAPL", md.AAPL_SPLIT_2020),
    ("yfinance:RVSQ", "RVSQ", md.REVERSE_SPLIT),
    ("yfinance:DIVQ", "DIVQ", md.DIVIDEND),
    ("yfinance:OHLCQ", "OHLCQ", md.OHLC_INVALID),
    ("yfinance:MISSQ", "MISSQ", md.MISSING_BAR),
    ("yfinance:TDLC", "TDLC", md.DELISTING),
]


def test_universe_sanity(conn, now):
    for seed, ticker, dataset in UNIVERSE:
        adapter = YFinanceAdapter(ticker_factory=make_ticker_factory({ticker: dataset}))
        sid = ing.new_security_id(seed)
        ing.ensure_security(conn, sid, adapter, ticker, now)
        start, end = dataset["bars"][0]["date"], dataset["bars"][-1]["date"]
        ing.ingest_prices(conn, adapter, sid, ticker, start, end, now)

    count = conn.execute("SELECT COUNT(*) AS n FROM security_master").fetchone()["n"]
    assert count == len(UNIVERSE), f"expected {len(UNIVERSE)} securities, got {count}"

    for seed, ticker, dataset in UNIVERSE:
        sid = ing.new_security_id(seed)
        bars = repo.get_price_history(conn, sid)
        expected_weekdays = len(md.business_days(dataset["bars"][0]["date"], dataset["bars"][-1]["date"]))
        # plausibility, not exact equality: allow one weekday short for
        # MISSING_BAR's deliberately injected gap
        assert expected_weekdays - 1 <= len(bars) <= expected_weekdays, (
            f"{ticker}: ingested bar count implausible ({len(bars)} vs ~{expected_weekdays} expected)"
        )
