"""TEST 2 -- No future candle leakage (Spec #002 SS38/SS2).

Discovery output for an earlier as_of must be identical whether or not
later-dated candles have since been ingested into the store -- the
Discovery-level counterpart to Spec #001's PIT look-ahead test.
"""
from data_foundation.adapters.yfinance_adapter import YFinanceAdapter
from data_foundation.model import ingestion as ing
from fixtures.fake_yfinance import make_ticker_factory

from discovery.config.loader import load_config
from discovery.engine import run_discovery
from spec002.fixtures.synthetic_universe import BENCHMARK, TREND_UP


def test_no_future_candle_leakage(conn, now):
    adapter = YFinanceAdapter(ticker_factory=make_ticker_factory(
        {BENCHMARK["ticker"]: BENCHMARK, TREND_UP["ticker"]: TREND_UP}
    ))

    bench_sid = ing.new_security_id("spec002_test2:BENCH")
    trnd_sid = ing.new_security_id("spec002_test2:TRNDUP")
    for ticker, sid in [(BENCHMARK["ticker"], bench_sid), (TREND_UP["ticker"], trnd_sid)]:
        ing.ensure_security(conn, sid, adapter, ticker, now)
        ing.ensure_symbol_history(conn, sid, ticker, BENCHMARK["bars"][0]["date"], None, "yfinance")

    all_dates = [b["date"] for b in BENCHMARK["bars"]]
    as_of = all_dates[280]  # well past the 252-day percentile window, leaving a "future" tail uningested

    ing.ingest_prices(conn, adapter, bench_sid, BENCHMARK["ticker"], all_dates[0], as_of, now)
    ing.ingest_prices(conn, adapter, trnd_sid, TREND_UP["ticker"], all_dates[0], as_of, now)

    config = load_config()
    before = run_discovery(conn, [trnd_sid], as_of, bench_sid, config)

    # ingest the remaining, LATER-dated candles for both securities
    ing.ingest_prices(conn, adapter, bench_sid, BENCHMARK["ticker"], all_dates[0], all_dates[-1], now)
    ing.ingest_prices(conn, adapter, trnd_sid, TREND_UP["ticker"], all_dates[0], all_dates[-1], now)

    after = run_discovery(conn, [trnd_sid], as_of, bench_sid, config)

    assert before == after, "Discovery output at an earlier as_of changed after later candles were ingested"
