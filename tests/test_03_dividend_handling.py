"""TEST 3 -- Dividend handling (Spec #001 SS23).

A dividend must be identified as DIVIDEND (never confused with a split)
and must never modify raw price bars.
"""
from data_foundation.adapters.yfinance_adapter import YFinanceAdapter
from data_foundation.model import ingestion as ing, repository as repo
from data_foundation.model.entities import ActionType
from fixtures.fake_yfinance import make_ticker_factory
from fixtures.market_data import DIVIDEND


def test_dividend_identified_and_does_not_alter_raw_prices(conn, now):
    ticker = DIVIDEND["ticker"]
    adapter = YFinanceAdapter(ticker_factory=make_ticker_factory({ticker: DIVIDEND}))
    sid = ing.new_security_id(f"yfinance:{ticker}")
    ing.ensure_security(conn, sid, adapter, ticker, now)
    start, end = DIVIDEND["bars"][0]["date"], DIVIDEND["bars"][-1]["date"]
    ing.ingest_prices(conn, adapter, sid, ticker, start, end, now)
    actions = ing.ingest_corporate_actions(conn, adapter, sid, ticker, start, end, now)

    assert len(actions) == 1
    assert actions[0].action_type == ActionType.DIVIDEND.value
    assert actions[0].action_type != ActionType.SPLIT.value
    assert actions[0].value == list(DIVIDEND["dividends"].values())[0]

    stored_bars = {b.date: b for b in repo.get_price_history(conn, sid)}
    for bar in DIVIDEND["bars"]:
        assert stored_bars[bar["date"]].raw_close == bar["close"], (
            "dividend must never modify raw price bars"
        )
