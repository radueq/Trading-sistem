"""TEST 23 -- A stock split alone must not create a false VOLUME_ANOMALY
(PATCH #001-C, Radu's correction, 2026-09-21).

Before PATCH #001-C, discovery.engine._price_series_to_df() fed
raw_volume (unadjusted) into the Volume Lane alongside split_adjusted_close
(adjusted) -- a mechanical share-count discontinuity at a split boundary
could then look like a real volume spike, producing a spurious
volume_percentile reading and a false VOLUME_ANOMALY reason code near
that date (documented as a BLOCKER in docs/spec002_known_limitations.md
before this patch).

Fixture: raw_volume is constructed to already reflect a genuine
post-split share-count change proportional to the split ratio (real-
world turnover in shares is roughly split-ratio-invariant) -- 100 pre /
400 post for a 4-for-1 forward split, 500 pre / 100 post for a 1-for-5
reverse split (Radu's example). With the fix, split_adjusted_volume is
~constant across the boundary for BOTH directions using the SAME
formula (no special-casing for forward vs reverse), so the rolling
percentile a few days after the split should sit near the NEUTRAL
midpoint (0.5), not drift to an artificial extreme.

Not testing "RVOL == 1 exactly after a split" (real volume varies
naturally) -- isolating the split's own mechanical contribution by
holding everything else constant, per Radu's fixture design.
"""
from dataclasses import replace

import pytest

from data_foundation.adapters.yfinance_adapter import YFinanceAdapter
from data_foundation.model import ingestion as ing
from fixtures.fake_yfinance import make_ticker_factory
from fixtures.market_data import make_bars

from discovery.config.loader import load_config
from discovery.engine import run_discovery
from spec002.fixtures.synthetic_universe import DATES

# 30 pre-split bars + 6 post-split bars; as_of sits 6 trading days after
# the split so the volume lane's rolling window (reduced to 20 for a
# small, hand-verifiable fixture) straddles the boundary: 14 pre-split
# + 6 post-split observations.
_SPLIT_EFFECTIVE_DATE = DATES[30]
_TEST_AS_OF = DATES[35]

FORWARD_SPLIT_VOLUME = {
    "ticker": "SPLITVOL4",
    "info": {"quoteType": "EQUITY", "exchange": "SYNTH", "currency": "USD"},
    "bars": (
        make_bars(DATES[0], DATES[29], base_price=100.0, volume=100)
        + make_bars(DATES[30], DATES[35], base_price=25.0, volume=400)
    ),
    "splits": {_SPLIT_EFFECTIVE_DATE: 4.0},
    "dividends": {},
}

REVERSE_SPLIT_VOLUME = {
    "ticker": "SPLITVOL5R",
    "info": {"quoteType": "EQUITY", "exchange": "SYNTH", "currency": "USD"},
    "bars": (
        make_bars(DATES[0], DATES[29], base_price=20.0, volume=500)
        + make_bars(DATES[30], DATES[35], base_price=100.0, volume=100)
    ),
    "splits": {_SPLIT_EFFECTIVE_DATE: 0.2},
    "dividends": {},
}


@pytest.mark.parametrize("dataset", [FORWARD_SPLIT_VOLUME, REVERSE_SPLIT_VOLUME])
def test_split_alone_does_not_move_volume_percentile_off_neutral(conn, now, universe, dataset):
    ticker = dataset["ticker"]
    adapter = YFinanceAdapter(ticker_factory=make_ticker_factory({ticker: dataset}))
    sid = ing.new_security_id(f"test23:{ticker}")
    ing.ensure_security(conn, sid, adapter, ticker, now)
    start, end = dataset["bars"][0]["date"], dataset["bars"][-1]["date"]
    ing.ingest_prices(conn, adapter, sid, ticker, start, end, now)
    ing.ingest_corporate_actions(conn, adapter, sid, ticker, start, end, now)

    base_config = load_config()
    config = replace(
        base_config,
        features={**base_config.features, "percentile_window": 20, "percentile_min_periods": 20},
        eligibility={**base_config.eligibility, "minimum_history_days": 20, "minimum_adv_20": 50},
    )

    candidates = run_discovery(conn, [sid], _TEST_AS_OF, universe["benchmark_security_id"], config)
    assert len(candidates) == 1, "sanity: the fixture must pass eligibility to be assessable at all"
    candidate = candidates[0]

    volume_percentile = candidate.normalized_feature_vector.get("volume_percentile")
    assert volume_percentile is not None
    assert volume_percentile == pytest.approx(0.5, abs=0.05), (
        f"{ticker}: volume_percentile={volume_percentile} a few days after a split alone "
        "-- should sit at the NEUTRAL midpoint (raw_volume was constructed to already be "
        "split-ratio-proportional); a value pulled toward an extreme means unadjusted "
        "volume leaked into the percentile calculation"
    )
    assert "VOLUME_ANOMALY" not in candidate.reason_codes
