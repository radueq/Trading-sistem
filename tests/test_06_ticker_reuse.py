"""TEST 6 -- Ticker reuse (Spec #001 SS23).

If the same symbol is later used by an unrelated security, histories
must NOT be combined. Fully synthetic fixture (ticker "ZZZQ", not a real
symbol) -- see tests/fixtures/market_data.py.
"""
from data_foundation.adapters.yfinance_adapter import YFinanceAdapter
from data_foundation.model import ingestion as ing, repository as repo
from data_foundation.model.entities import SymbolHistoryEntry
from data_foundation.pit import access as pit
from data_foundation.qa import engine as qa
from fixtures.fake_yfinance import make_ticker_factory
from fixtures.market_data import TICKER_REUSE_COMPANY_A, TICKER_REUSE_COMPANY_B

TICKER = "ZZZQ"


def test_ticker_reuse_does_not_merge_histories(conn, now):
    # Two separate adapters/factories: in reality you'd have queried the
    # ticker at two different points in time and gotten two unrelated
    # companies' data -- yfinance itself only ever knows the CURRENT
    # mapping, which is exactly why identity assignment can't be
    # automatic here (see ingestion.py docstring).
    adapter_a = YFinanceAdapter(ticker_factory=make_ticker_factory({TICKER: TICKER_REUSE_COMPANY_A}))
    adapter_b = YFinanceAdapter(ticker_factory=make_ticker_factory({TICKER: TICKER_REUSE_COMPANY_B}))

    sid_a = ing.new_security_id("yfinance:ZZZQ:company_a")
    sid_b = ing.new_security_id("yfinance:ZZZQ:company_b")
    assert sid_a != sid_b

    a_start, a_end = TICKER_REUSE_COMPANY_A["bars"][0]["date"], TICKER_REUSE_COMPANY_A["bars"][-1]["date"]
    b_start, b_end = TICKER_REUSE_COMPANY_B["bars"][0]["date"], TICKER_REUSE_COMPANY_B["bars"][-1]["date"]

    ing.ensure_security(conn, sid_a, adapter_a, TICKER, now)
    ing.ensure_security(conn, sid_b, adapter_b, TICKER, now)
    ing.ensure_symbol_history(conn, sid_a, TICKER, a_start, TICKER_REUSE_COMPANY_A["delisted_effective"], "yfinance")
    ing.ensure_symbol_history(conn, sid_b, TICKER, b_start, None, "yfinance")

    ing.ingest_prices(conn, adapter_a, sid_a, TICKER, a_start, a_end, now)
    ing.ingest_prices(conn, adapter_b, sid_b, TICKER, b_start, b_end, now)

    assert pit.get_security_id_for_ticker_as_of(conn, TICKER, "2015-01-05") == sid_a
    assert pit.get_security_id_for_ticker_as_of(conn, TICKER, "2021-01-06") == sid_b

    bars_a = {b.date for b in repo.get_price_history(conn, sid_a)}
    bars_b = {b.date for b in repo.get_price_history(conn, sid_b)}
    assert bars_a == {b["date"] for b in TICKER_REUSE_COMPANY_A["bars"]}
    assert bars_b == {b["date"] for b in TICKER_REUSE_COMPANY_B["bars"]}
    assert bars_a.isdisjoint(bars_b)

    # legitimate, non-overlapping reuse must NOT trigger IDENTIFIER_CONFLICT
    for r in qa.run_qa_checks(conn, sid_a):
        assert "IDENTIFIER_CONFLICT" not in r.reason_codes
    for r in qa.run_qa_checks(conn, sid_b):
        assert "IDENTIFIER_CONFLICT" not in r.reason_codes


def test_genuinely_overlapping_ticker_windows_are_flagged(conn, now):
    # A deliberately corrupted scenario: two different security_ids claim
    # the SAME ticker for OVERLAPPING date windows -- a genuine data
    # error QA must catch, distinct from legitimate sequential reuse.
    sid_x = ing.new_security_id("yfinance:ZZZQ:conflict_x")
    sid_y = ing.new_security_id("yfinance:ZZZQ:conflict_y")
    adapter = YFinanceAdapter(ticker_factory=make_ticker_factory({TICKER: TICKER_REUSE_COMPANY_A}))
    ing.ensure_security(conn, sid_x, adapter, TICKER, now)
    ing.ensure_security(conn, sid_y, adapter, TICKER, now)

    repo.insert_symbol_history(conn, SymbolHistoryEntry(
        security_id=sid_x, ticker=TICKER, exchange=None,
        valid_from="2015-01-01", valid_to="2015-06-01", source_provider="yfinance",
    ))
    repo.insert_symbol_history(conn, SymbolHistoryEntry(
        security_id=sid_y, ticker=TICKER, exchange=None,
        valid_from="2015-03-01", valid_to=None, source_provider="yfinance",  # overlaps sid_x's window
    ))
    ing.ingest_prices(conn, adapter, sid_x, TICKER, "2015-01-02", "2015-01-09", now)

    results = qa.run_qa_checks(conn, sid_x)
    assert any("IDENTIFIER_CONFLICT" in r.reason_codes for r in results)
