"""TEST 13 -- Knowledge-time policy (Radu's correction, 2026-09-21).

Not part of the original Spec #001 SS23 numbered list, but mandated by
the 2026-09-21 patch instructions as required coverage for the new
available_at (knowledge-time) field. Covers, in order:

  A. available_at > effective_date (a retroactively-disclosed action):
     status derivation and price-adjustment gating both wait for
     available_at, not just effective_date.
  B. available_at = NULL preserves the pre-patch Level 1 behavior
     (effective_date-only gating, no ANNOUNCED phase, tagged UNKNOWN).
  C. ingestion_timestamp never acts as a knowledge-time proxy: two rows
     for "the same" historical event, ingested at wildly different
     wall-clock times, must produce identical PIT results.
"""
from data_foundation.adapters.yfinance_adapter import YFinanceAdapter
from data_foundation.model import ingestion as ing, repository as repo
from data_foundation.model.entities import ActionType, CorporateAction, PriceBar, SecurityMaster
from data_foundation.pit import access as pit
from fixtures.fake_yfinance import make_ticker_factory
from fixtures.market_data import AAPL_SPLIT_2020, make_bars


def _make_security(conn, seed: str, now: str) -> str:
    sid = ing.new_security_id(seed)
    repo.insert_security_master(conn, SecurityMaster(
        security_id=sid, security_type="EQUITY", primary_exchange=None, currency="USD",
        source_provider="manual", source_security_id=seed, ingestion_timestamp=now,
    ))
    return sid


def test_available_at_after_effective_date_is_respected(conn, now):
    """A. Retroactive disclosure: effective_date=2024-03-01,
    available_at=2024-03-15 -- the event really happened March 1st, but
    nobody (including our system) could have known about it before
    March 15th."""
    sid = _make_security(conn, "test13:retroactive_split", now)

    bars = make_bars("2024-02-26", "2024-02-29", base_price=400.0, daily_drift=-1.0) + \
           make_bars("2024-03-01", "2024-03-20", base_price=100.0, daily_drift=0.3)
    repo.insert_price_bars(conn, [
        PriceBar(security_id=sid, date=b["date"], raw_open=b["open"], raw_high=b["high"],
                  raw_low=b["low"], raw_close=b["close"], raw_volume=b["volume"],
                  source_provider="manual", ingestion_timestamp=now)
        for b in bars
    ])

    action = CorporateAction(
        action_id="ca_retro_split", security_id=sid, action_type=ActionType.SPLIT.value,
        announcement_date=None, effective_date="2024-03-01", value=4.0,
        source_provider="manual", source_status=None, source_status_date=None,
        available_at="2024-03-15", ingestion_timestamp=now, last_updated_timestamp=now,
    )
    repo.upsert_corporate_actions(conn, [action])

    # status derivation waits for available_at, not just effective_date
    assert pit.derive_corporate_action_pit_status(action, "2024-03-10") == ("NOT_KNOWN", "KNOWN")
    assert pit.derive_corporate_action_pit_status(action, "2024-03-15") == ("EFFECTIVE", "KNOWN")
    assert pit.derive_corporate_action_pit_status(action, "2024-03-20") == ("EFFECTIVE", "KNOWN")

    # info does not appear before available_at, even though effective_date has passed
    assert pit.get_corporate_actions_as_of(conn, sid, "2024-03-10") == []
    after = pit.get_corporate_actions_as_of(conn, sid, "2024-03-15")
    assert len(after) == 1 and after[0].pit_status == "EFFECTIVE"

    # price-adjustment gating: split not reflected before available_at ...
    series_before = pit.get_price_series_as_of(conn, sid, "2024-03-10")
    bar_before = next(b for b in series_before if b.date == "2024-02-26")
    assert bar_before.split_adjusted_close == bar_before.raw_close

    # ... but IS reflected for historical (pre-split) dates once available_at is reached
    series_after = pit.get_price_series_as_of(conn, sid, "2024-03-15")
    bar_after = next(b for b in series_after if b.date == "2024-02-26")
    assert bar_after.split_adjusted_close < bar_after.raw_close * 0.3


def test_available_at_null_preserves_level1_effective_date_fallback(conn, now):
    """B. yfinance never supplies announcement_date, so available_at is
    always NULL for its actions -- the pre-patch Level 1 behavior
    (effective_date-only gating, no ANNOUNCED phase) must still hold,
    explicitly tagged UNKNOWN."""
    ticker = AAPL_SPLIT_2020["ticker"]
    adapter = YFinanceAdapter(ticker_factory=make_ticker_factory({ticker: AAPL_SPLIT_2020}))
    sid = ing.new_security_id(f"yfinance:{ticker}:test13b")
    ing.ensure_security(conn, sid, adapter, ticker, now)
    start, end = AAPL_SPLIT_2020["bars"][0]["date"], AAPL_SPLIT_2020["bars"][-1]["date"]
    ing.ingest_prices(conn, adapter, sid, ticker, start, end, now)
    actions = ing.ingest_corporate_actions(conn, adapter, sid, ticker, start, end, now)
    action = actions[0]
    assert action.available_at is None

    for as_of in ["2020-08-24", "2020-08-25", "2020-08-26", "2020-08-27", "2020-08-28"]:
        assert pit.derive_corporate_action_pit_status(action, as_of) == ("NOT_KNOWN", "UNKNOWN"), (
            f"no ANNOUNCED phase should ever appear without a validated available_at signal ({as_of})"
        )
    assert pit.derive_corporate_action_pit_status(action, "2020-08-31") == ("EFFECTIVE", "UNKNOWN")


def test_ingestion_timestamp_never_used_as_knowledge_time(conn, now):
    """C. Two rows for the same historical split, differing only in
    ingestion_timestamp (one "ingested" in 2020, one "ingested" today),
    must produce IDENTICAL PIT results at every as_of -- ingestion time
    must have zero influence on historical knowledge-time. This is
    exactly Radu's own example: downloading a 2020 split today must not
    make it "unknown" in 2020."""
    sid = _make_security(conn, "test13:ingestion_time_independence", now)
    common = dict(
        security_id=sid, action_type=ActionType.SPLIT.value,
        announcement_date=None, effective_date="2020-08-31", value=4.0,
        source_provider="manual", source_status=None, source_status_date=None,
        available_at=None,
    )
    action_ingested_in_2020 = CorporateAction(
        action_id="ca_ingested_2020", ingestion_timestamp="2020-09-01T00:00:00+00:00",
        last_updated_timestamp="2020-09-01T00:00:00+00:00", **common,
    )
    action_ingested_today = CorporateAction(
        action_id="ca_ingested_today", ingestion_timestamp="2026-09-21T00:00:00+00:00",
        last_updated_timestamp="2026-09-21T00:00:00+00:00", **common,
    )

    for as_of in ["2020-08-25", "2020-08-30", "2020-08-31", "2020-09-05"]:
        assert pit.derive_corporate_action_pit_status(action_ingested_in_2020, as_of) == \
            pit.derive_corporate_action_pit_status(action_ingested_today, as_of), (
                f"ingestion_timestamp changed the PIT result at as_of={as_of}"
            )

    # concretely: knowable as of 2020-08-31 even though "today" is 2026
    assert pit.derive_corporate_action_pit_status(action_ingested_today, "2020-08-31") == ("EFFECTIVE", "UNKNOWN")
