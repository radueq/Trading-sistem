"""TEST 9 -- PIT look-ahead test (Spec #001 SS23).

The single most critical test in the suite: get_data(as_of=X) must
return byte-identical results before and after the Data Store learns
about events/dates *after* X. Any change caused solely by later-ingested
future information is FAIL CRITICAL.
"""
from data_foundation.adapters.yfinance_adapter import YFinanceAdapter
from data_foundation.model import ingestion as ing, repository as repo
from data_foundation.pit import access as pit
from fixtures.fake_yfinance import make_ticker_factory
from fixtures.market_data import AAPL_SPLIT_2020

AS_OF = "2020-08-26"  # strictly before the split's effective_date (2020-08-31)


def test_pit_look_ahead_immunity(conn, now):
    ticker = AAPL_SPLIT_2020["ticker"]
    adapter = YFinanceAdapter(ticker_factory=make_ticker_factory({ticker: AAPL_SPLIT_2020}))
    sid = ing.new_security_id(f"yfinance:{ticker}")
    ing.ensure_security(conn, sid, adapter, ticker, now)

    # Phase 1: the store only knows about data up to AS_OF.
    pre_bars = [b for b in AAPL_SPLIT_2020["bars"] if b["date"] <= AS_OF]
    ing.ingest_prices(conn, adapter, sid, ticker, pre_bars[0]["date"], AS_OF, now)

    snapshot_before = pit.get_data(conn, sid, as_of=AS_OF)

    # Phase 2: ingest data dated AFTER AS_OF -- post-split bars and the
    # split corporate action itself (effective_date 2020-08-31 > AS_OF).
    all_dates = [b["date"] for b in AAPL_SPLIT_2020["bars"]]
    ing.ingest_prices(conn, adapter, sid, ticker, all_dates[0], all_dates[-1], now)
    ing.ingest_corporate_actions(conn, adapter, sid, ticker, all_dates[0], all_dates[-1], now)

    # sanity: the future data really is in the store now
    assert len(repo.get_price_history(conn, sid)) > len(pre_bars)
    assert len(repo.get_corporate_actions(conn, sid)) == 1
    assert AS_OF < repo.get_corporate_actions(conn, sid)[0].effective_date

    snapshot_after = pit.get_data(conn, sid, as_of=AS_OF)

    assert snapshot_before == snapshot_after, (
        "get_data(as_of=X) changed after future-dated data was ingested -- look-ahead leakage"
    )
