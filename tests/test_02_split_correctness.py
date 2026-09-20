"""TEST 2 -- Split correctness (Spec #001 SS23).

Verifies raw prices are preserved unchanged, the corporate action is
recorded with the correct ratio, and the split adjustment methodology
removes the scale discontinuity (continuity across the split boundary).
Covers a forward split (AAPL, real ratio+date anchor -- see
tests/fixtures/market_data.py for provenance) and a reverse split
(RVSQ, fully synthetic) so both directions of the formula are exercised.
"""
import pytest

from data_foundation.adapters.yfinance_adapter import YFinanceAdapter
from data_foundation.model import adjustment_engine as ae, ingestion as ing, repository as repo
from fixtures.fake_yfinance import make_ticker_factory
from fixtures.market_data import AAPL_SPLIT_2020, REVERSE_SPLIT


@pytest.mark.parametrize("dataset,expected_ratio", [
    (AAPL_SPLIT_2020, 4.0),
    (REVERSE_SPLIT, 0.2),
])
def test_split_correctness(conn, now, dataset, expected_ratio):
    ticker = dataset["ticker"]
    adapter = YFinanceAdapter(ticker_factory=make_ticker_factory({ticker: dataset}))
    sid = ing.new_security_id(f"yfinance:{ticker}")
    ing.ensure_security(conn, sid, adapter, ticker, now)
    start, end = dataset["bars"][0]["date"], dataset["bars"][-1]["date"]
    ing.ingest_prices(conn, adapter, sid, ticker, start, end, now)
    actions = ing.ingest_corporate_actions(conn, adapter, sid, ticker, start, end, now)

    # 1. Raw prices preserved exactly as ingested
    stored_bars = {b.date: b for b in repo.get_price_history(conn, sid)}
    for bar in dataset["bars"]:
        assert stored_bars[bar["date"]].raw_close == bar["close"]

    # 2. Corporate action recorded with the correct ratio
    matching = [a for a in actions if a.value == expected_ratio]
    assert len(matching) == 1
    effective_date = matching[0].effective_date

    # 3. Adjustment methodology + continuity across the split boundary
    factors = {f.date: f for f in ae.compute_and_store_adjustment_factors(conn, sid)}
    adjusted = {d: stored_bars[d].raw_close * f.split_adjustment_factor for d, f in factors.items()}

    dates_sorted = sorted(adjusted)
    boundary_idx = dates_sorted.index(effective_date)
    raw_pre = stored_bars[dates_sorted[boundary_idx - 1]].raw_close
    raw_post = stored_bars[dates_sorted[boundary_idx]].raw_close
    adj_pre = adjusted[dates_sorted[boundary_idx - 1]]
    adj_post = adjusted[dates_sorted[boundary_idx]]

    raw_jump = abs(raw_post - raw_pre) / raw_pre
    adjusted_jump = abs(adj_post - adj_pre) / adj_pre
    assert raw_jump > 0.5, "sanity: the raw series should show the large unadjusted jump"
    assert adjusted_jump < 0.05, (
        f"split-adjusted series should be continuous across the split, got {adjusted_jump:.2%} jump"
    )
