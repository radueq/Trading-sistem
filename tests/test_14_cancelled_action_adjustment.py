"""TEST 14 -- Cancelled corporate action must never adjust prices after
cancellation is known (GPT Review #001, commit 8492ade -- PATCH A).

Bug found in review: `_is_action_known_for_adjustment()` checked
`effective_date` and `available_at` but not CANCELLED status, so an
action correctly reported CANCELLED by `derive_corporate_action_pit_status()`
could still enter `compute_factors()` and alter the adjusted price
series -- metadata says CANCELLED, but the price series pretends the
split/dividend happened anyway. Reproduces GPT's exact example:
available_at=2024-03-01, effective_date=2024-03-20,
source_status_date(CANCELLED)=2024-03-15, as_of=2024-03-25.
"""
from data_foundation.model import ingestion as ing, repository as repo
from data_foundation.model.entities import ActionType, CorporateAction, PriceBar, SecurityMaster
from data_foundation.pit import access as pit
from fixtures.market_data import make_bars


def _make_security(conn, seed: str, now: str) -> str:
    sid = ing.new_security_id(seed)
    repo.insert_security_master(conn, SecurityMaster(
        security_id=sid, security_type="EQUITY", primary_exchange=None, currency="USD",
        source_provider="manual", source_security_id=seed, ingestion_timestamp=now,
    ))
    return sid


def test_cancelled_split_does_not_adjust_prices_once_cancellation_is_known(conn, now):
    sid = _make_security(conn, "test14:cancelled_split", now)

    bars = make_bars("2024-02-20", "2024-03-25", base_price=200.0, daily_drift=0.1)
    repo.insert_price_bars(conn, [
        PriceBar(security_id=sid, date=b["date"], raw_open=b["open"], raw_high=b["high"],
                  raw_low=b["low"], raw_close=b["close"], raw_volume=b["volume"],
                  source_provider="manual", ingestion_timestamp=now)
        for b in bars
    ])

    action = CorporateAction(
        action_id="ca_cancelled_split", security_id=sid, action_type=ActionType.SPLIT.value,
        announcement_date="2024-03-01", effective_date="2024-03-20", value=2.0,
        source_provider="manual", source_status="CANCELLED", source_status_date="2024-03-15",
        available_at="2024-03-01", ingestion_timestamp=now,
    )
    repo.insert_corporate_actions(conn, [action])

    as_of = "2024-03-25"  # after available_at, effective_date, AND the cancellation

    # metadata correctly reports CANCELLED
    actions = pit.get_corporate_actions_as_of(conn, sid, as_of)
    assert len(actions) == 1
    assert actions[0].pit_status == "CANCELLED"

    # adjusted price series must NOT reflect the cancelled split anywhere,
    # including for dates before the (never-executed) effective_date
    series = pit.get_price_series_as_of(conn, sid, as_of)
    assert len(series) > 0
    for bar in series:
        assert bar.split_adjusted_close == bar.raw_close, (
            f"cancelled split leaked into the adjusted series on {bar.date}"
        )


def test_pending_action_still_adjusts_before_its_cancellation_is_knowable(conn, now):
    """Symmetry check: at an as_of BEFORE the cancellation becomes
    knowable, the action must behave exactly as if it were still
    pending/effective -- a PIT-simulated researcher at that earlier
    as_of has no way to know it will later be cancelled."""
    sid = _make_security(conn, "test14:not_yet_cancelled", now)

    bars = make_bars("2024-01-05", "2024-01-25", base_price=200.0, daily_drift=0.1)
    repo.insert_price_bars(conn, [
        PriceBar(security_id=sid, date=b["date"], raw_open=b["open"], raw_high=b["high"],
                  raw_low=b["low"], raw_close=b["close"], raw_volume=b["volume"],
                  source_provider="manual", ingestion_timestamp=now)
        for b in bars
    ])

    # effective_date is BEFORE the cancellation becomes knowable -- an
    # unusual but legitimate case (e.g. a later restatement/reversal)
    action = CorporateAction(
        action_id="ca_reversed_split", security_id=sid, action_type=ActionType.SPLIT.value,
        announcement_date="2024-01-01", effective_date="2024-01-10", value=2.0,
        source_provider="manual", source_status="CANCELLED", source_status_date="2024-01-20",
        available_at="2024-01-01", ingestion_timestamp=now,
    )
    repo.insert_corporate_actions(conn, [action])

    as_of = "2024-01-15"  # after effective_date, but before the cancellation is knowable
    status, _ = pit.derive_corporate_action_pit_status(action, as_of)
    assert status == "EFFECTIVE"

    series = pit.get_price_series_as_of(conn, sid, as_of)
    pre_split_bar = next(b for b in series if b.date == "2024-01-05")
    assert pre_split_bar.split_adjusted_close < pre_split_bar.raw_close * 0.6, (
        "before the cancellation is knowable, the split should still be reflected"
    )
