"""TEST 22 -- Cross-sectional RS eligibility isolation (GPT Review #002
Round 1, PATCH #002-A -- mandatory finding).

rs_percentile_cross_sectional must be computed ONLY against the
ELIGIBLE universe (Spec #002 SS15/SS29). Before this patch,
run_discovery() computed the cross-sectional pass over every security
in locals_by_security BEFORE eligibility filtering -- so a security that
will never become a candidate (e.g. failing minimum_price) could still
skew the RS percentile of securities that ARE eligible. Not a
theoretical risk: at real-data scale, thousands of ineligible penny
stocks/illiquid names entering the cross-sectional distribution would
silently distort which eligible securities look "notable."
"""
from data_foundation.adapters.yfinance_adapter import YFinanceAdapter
from data_foundation.model import ingestion as ing
from fixtures.fake_yfinance import make_ticker_factory
from fixtures.market_data import make_bars

from discovery.config.loader import load_config
from discovery.engine import run_discovery
from spec002.fixtures.synthetic_universe import AS_OF, DATES


def test_ineligible_extreme_rs_security_does_not_shift_eligible_percentiles(conn, now, universe):
    # A penny stock: stays well under eligibility.yaml's minimum_price
    # (1.0) for its entire history, but moves up dramatically (+0.2%/day
    # compounding-ish via linear drift) -- an extreme relative_return_63d
    # if it were ever allowed into the cross-sectional distribution.
    ticker = "PENNYX"
    bars = make_bars(DATES[0], DATES[-1], base_price=0.10, daily_drift=0.002)
    dataset = {
        "ticker": ticker, "info": {"quoteType": "EQUITY", "exchange": "SYNTH", "currency": "USD"},
        "bars": bars, "splits": {}, "dividends": {},
    }
    assert bars[-1]["close"] < 1.0, "sanity: fixture must actually fail minimum_price at as_of"

    adapter = YFinanceAdapter(ticker_factory=make_ticker_factory({ticker: dataset}))
    extra_sid = ing.new_security_id(f"test22:{ticker}")
    ing.ensure_security(conn, extra_sid, adapter, ticker, now)
    ing.ensure_symbol_history(conn, extra_sid, ticker, bars[0]["date"], None, "yfinance")
    ing.ingest_prices(conn, adapter, extra_sid, ticker, bars[0]["date"], bars[-1]["date"], now)

    config = load_config()
    baseline = run_discovery(conn, universe["non_benchmark_ids"], AS_OF, universe["benchmark_security_id"], config)
    with_penny = run_discovery(
        conn, universe["non_benchmark_ids"] + [extra_sid], AS_OF, universe["benchmark_security_id"], config,
    )

    baseline_rs = {c.security_id: c.normalized_feature_vector.get("rs_percentile_cross_sectional") for c in baseline}
    with_penny_rs = {
        c.security_id: c.normalized_feature_vector.get("rs_percentile_cross_sectional") for c in with_penny
    }

    shared_ids = set(baseline_rs) & set(with_penny_rs)
    assert len(shared_ids) > 5, "sanity: most eligible securities should be common to both runs"
    for sid in shared_ids:
        assert baseline_rs[sid] == with_penny_rs[sid], (
            f"ineligible extreme-RS security changed eligible security {sid}'s "
            f"rs_percentile_cross_sectional: {baseline_rs[sid]} -> {with_penny_rs[sid]}"
        )

    # sanity: the penny stock is genuinely excluded (failed eligibility), not just coincidentally absent
    assert extra_sid not in {c.security_id for c in with_penny}
