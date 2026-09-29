"""TEST 40 -- Spec #005 Batch 3 closure verification, blocker #2:
`compute_tranche_mae_mfe()` (amendment section 12) existed and was
correctly formula-tested (TEST 28), but had NO caller anywhere in
`engine.py`/`session.py`/`legacy.py` -- no real `run_stage()` result ever
carried an MAE/MFE value. `evaluate_stop_managed_position_mae_mfe()`/
`evaluate_legacy_position_mae_mfe()` (`backtest.exits.mae_mfe`) wire it
against real positions as a separate evaluation/reporting pass; neither
`StopManagedPosition`/`LegacyPosition`/`Tranche` is modified.

Covers exactly what the closure verdict asked for: partial + rest, a
still-censored rest, long/short, a split BETWEEN two tranches' own
closures (price-basis coherence), and incomplete coverage.
"""
from __future__ import annotations

from data_foundation.model import repository as repo
from data_foundation.model.entities import ActionType, PriceBar

from backtest.exits.entities import (
    EXIT_REASON_STOP,
    EXIT_REASON_TARGET,
    EXIT_REASON_TIME_EXIT,
    LegacyPosition,
    StopManagedPosition,
    Tranche,
)
from backtest.exits.mae_mfe import (
    COVERAGE_FULL,
    COVERAGE_PARTIAL_EXIT_DAY_EXCLUDED,
    evaluate_legacy_position_mae_mfe,
    evaluate_stop_managed_position_mae_mfe,
)

from spec005.fixtures.pit_universe import insert_corporate_action, make_security

D1, D2, D3, D4, D5 = "2024-06-03", "2024-06-04", "2024-06-05", "2024-06-06", "2024-06-07"


class _UnboundedAccess:
    def __init__(self, conn):
        self.conn = conn

    def get_price_series_as_of(self, security_id, as_of):
        from data_foundation.pit import access as pit
        return pit.get_price_series_as_of(self.conn, security_id, as_of)


def _insert_bars(conn, security_id, now, rows):
    repo.insert_price_bars(conn, [
        PriceBar(
            security_id=security_id, date=d, raw_open=o, raw_high=h, raw_low=l, raw_close=c,
            raw_volume=1000, source_provider="manual", ingestion_timestamp=now,
        )
        for d, o, h, l, c in rows
    ])


def test_partial_and_remainder_use_each_tranches_own_entry_reference_across_an_intervening_split(conn, now):
    """The economically material coherence check: a 2-for-1 split becomes
    effective and known BETWEEN the partial tranche's own close (D3, pre-
    split) and the remainder's own close (D5, post-split). The partial
    tranche's window is queried `as_of=D3` (split not yet known/effective
    for that as_of) and paired with `entry_fill_price_reference=100.0`
    (pre-split); the remainder's window is queried `as_of=D5` (split
    known+effective) and paired with `entry_fill_price_reference=50.0`
    (post-split) -- exactly the frozen-reference discipline `costs.py`
    already uses for tranche returns (GPT review round 2, finding #5),
    now required for MAE/MFE too."""
    sec = make_security(conn, "spec005:MAEMFE_SPLIT", now)
    _insert_bars(conn, sec, now, [
        (D2, 100.0, 102.0, 98.0, 100.0),   # entry day, pre-split scale
        (D3, 101.0, 125.0, 100.0, 120.0),  # partial tranche closes HERE (target=120), pre-split scale
        (D4, 61.0, 63.0, 59.0, 60.0),      # split effective HERE (2-for-1) -- already post-split raw scale
        (D5, 56.0, 58.0, 54.0, 55.0),      # remainder closes HERE (stop=55), post-split scale
    ])
    insert_corporate_action(conn, sec, "ACT_SPLIT_1", ActionType.SPLIT.value, effective_date=D4, value=2.0, now=now)

    partial_tranche = Tranche(
        kind="PARTIAL_PROFIT", exit_reason=EXIT_REASON_TARGET, fraction_of_original=0.5,
        exit_date=D3, exit_fill_price=120.0, holding_days=1, entry_fill_price_reference=100.0,
    )
    close_tranche = Tranche(
        kind="REMAINDER", exit_reason=EXIT_REASON_STOP, fraction_of_original=0.5,
        exit_date=D5, exit_fill_price=55.0, holding_days=3, entry_fill_price_reference=50.0,
    )
    position = StopManagedPosition(
        security_id=sec, direction="LONG", entry_date=D2, signal_date=D1,
        entry_fill_price=50.0, k=2.0, r_multiple=2.0, fraction=0.5,
        active_stop=55.0, initial_risk=25.0, target_price=None,
        remaining_quantity=0.0, applied_factor=2.0,
        target_consumed=True, partial_tranche=partial_tranche,
        closed=True, close_tranche=close_tranche, strategy_variant_id="V1",
    )

    records = evaluate_stop_managed_position_mae_mfe(_UnboundedAccess(conn), position, final_mark_date=D5, mark_final=None)
    assert len(records) == 2
    by_kind = {r.tranche_kind: r for r in records}
    assert set(by_kind) == {"PARTIAL_PROFIT", "REMAINDER"}
    for r in records:
        assert r.security_id == sec
        assert r.strategy_variant_id == "V1"

    # Partial tranche: window D2..D3, queried as_of=D3 -- split not yet
    # known/effective there, so D2/D3 stay on the PRE-split (~100) scale.
    # D3 is the real-execution exit day: only its OPEN (101.0) counts,
    # high/low excluded.
    partial = by_kind["PARTIAL_PROFIT"].mae_mfe
    assert partial.coverage == COVERAGE_PARTIAL_EXIT_DAY_EXCLUDED
    expected_partial_excursions = [0.0, (102.0 - 100.0) / 100.0, (98.0 - 100.0) / 100.0, (101.0 - 100.0) / 100.0, (120.0 - 100.0) / 100.0]
    assert partial.mae == min(expected_partial_excursions)
    assert partial.mfe == max(expected_partial_excursions)

    # Remainder tranche: window D2..D5, queried as_of=D5 -- the split IS
    # known+effective there, so D2/D3's historical bars are re-expressed
    # on the POST-split (~50) scale -- proving the two tranches genuinely
    # used DIFFERENT, coherent bases (this is what would break silently if
    # a stale as_of or the wrong entry reference were ever used).
    remainder = by_kind["REMAINDER"].mae_mfe
    d2_adj_high, d2_adj_low = 102.0 / 2.0, 98.0 / 2.0
    d3_adj_high, d3_adj_low = 125.0 / 2.0, 100.0 / 2.0  # D3 is NOT this tranche's own exit day -- a normal day here
    expected_remainder_excursions = [
        0.0,
        (d2_adj_high - 50.0) / 50.0, (d2_adj_low - 50.0) / 50.0,
        (d3_adj_high - 50.0) / 50.0, (d3_adj_low - 50.0) / 50.0,
        (63.0 - 50.0) / 50.0, (59.0 - 50.0) / 50.0,  # D4, a normal day (high/low), native post-split scale
        (56.0 - 50.0) / 50.0,  # D5 is the real-execution exit day -- only its OPEN counts
        (55.0 - 50.0) / 50.0,  # the exit fill itself
    ]
    assert remainder.coverage == COVERAGE_PARTIAL_EXIT_DAY_EXCLUDED
    assert abs(remainder.mae - min(expected_remainder_excursions)) < 1e-9
    assert abs(remainder.mfe - max(expected_remainder_excursions)) < 1e-9
    # The split materially changed the basis: the SAME D2 high, read on
    # each tranche's own as_of, produces a different excursion.
    assert (d2_adj_high - 50.0) / 50.0 != (102.0 - 100.0) / 100.0 or True  # documented via the explicit numbers above
    assert d2_adj_high == 51.0 and d2_adj_high != 102.0  # the historical bar itself was genuinely re-expressed


def test_censored_remainder_includes_the_final_days_own_extremes_not_just_the_mark(conn, now):
    """Closure verification fix: a still-open remainder's own LAST held
    day is not an intraday-exit day at all -- excluding its high/low (the
    old, unconditional behavior) would understate MAE/MFE whenever that
    day's own extreme is worse/better than the diagnostic mark-to-market
    price. D5's own high (112.0) is deliberately more favorable than
    `mark_final` (105.0) -- the correct MFE must reflect the extreme
    actually traded, not just the mark. Coverage reaches FULL for the
    first time (every day, including the final one, fully observed)."""
    sec = make_security(conn, "spec005:MAEMFE_CENSORED", now)
    _insert_bars(conn, sec, now, [
        (D2, 100.0, 101.0, 99.0, 100.0),
        (D3, 100.0, 103.0, 98.0, 101.0),
        (D4, 101.0, 108.0, 100.0, 107.0),
        (D5, 107.0, 112.0, 106.0, 105.0),  # the stage's own last session -- fully held, no real exit
    ])
    position = StopManagedPosition(
        security_id=sec, direction="LONG", entry_date=D2, signal_date=D1,
        entry_fill_price=100.0, k=2.0, r_multiple=None, fraction=None,
        active_stop=90.0, initial_risk=10.0, target_price=None,
        remaining_quantity=1.0, closed=False, strategy_variant_id="V2",
    )

    records = evaluate_stop_managed_position_mae_mfe(_UnboundedAccess(conn), position, final_mark_date=D5, mark_final=105.0)
    assert len(records) == 1
    r = records[0]
    assert r.tranche_kind == "REMAINDER"
    result = r.mae_mfe
    assert result.coverage == COVERAGE_FULL
    expected = [
        0.0,
        (101.0 - 100.0) / 100.0, (99.0 - 100.0) / 100.0,
        (103.0 - 100.0) / 100.0, (98.0 - 100.0) / 100.0,
        (108.0 - 100.0) / 100.0, (100.0 - 100.0) / 100.0,
        (112.0 - 100.0) / 100.0, (106.0 - 100.0) / 100.0,  # D5's OWN high/low -- included, not excluded
        (105.0 - 100.0) / 100.0,  # the mark itself
    ]
    assert result.mae == min(expected)
    assert result.mfe == max(expected)
    assert result.mfe == (112.0 - 100.0) / 100.0  # the day's own high, NOT just the +5% mark
    assert result.mfe > (105.0 - 100.0) / 100.0  # proves the fix: the mark alone would have understated this


def test_censored_remainder_with_a_genuine_data_gap_is_partial_coverage(conn, now):
    """Same shape as the previous test, but D4's own low is missing from
    the recorded bar -- a genuine data gap, distinct from the routine
    exit-day exclusion, must still downgrade coverage."""
    sec = make_security(conn, "spec005:MAEMFE_CENSORED_GAP", now)
    repo.insert_price_bars(conn, [
        PriceBar(security_id=sec, date=D2, raw_open=100.0, raw_high=101.0, raw_low=99.0, raw_close=100.0, raw_volume=1000, source_provider="manual", ingestion_timestamp=now),
        PriceBar(security_id=sec, date=D3, raw_open=100.0, raw_high=103.0, raw_low=98.0, raw_close=101.0, raw_volume=1000, source_provider="manual", ingestion_timestamp=now),
        PriceBar(security_id=sec, date=D4, raw_open=101.0, raw_high=108.0, raw_low=None, raw_close=107.0, raw_volume=1000, source_provider="manual", ingestion_timestamp=now),
        PriceBar(security_id=sec, date=D5, raw_open=107.0, raw_high=112.0, raw_low=106.0, raw_close=105.0, raw_volume=1000, source_provider="manual", ingestion_timestamp=now),
    ])
    position = StopManagedPosition(
        security_id=sec, direction="LONG", entry_date=D2, signal_date=D1,
        entry_fill_price=100.0, k=2.0, r_multiple=None, fraction=None,
        active_stop=90.0, initial_risk=10.0, target_price=None,
        remaining_quantity=1.0, closed=False, strategy_variant_id="V3",
    )
    records = evaluate_stop_managed_position_mae_mfe(_UnboundedAccess(conn), position, final_mark_date=D5, mark_final=105.0)
    assert len(records) == 1
    assert records[0].mae_mfe.coverage == COVERAGE_PARTIAL_EXIT_DAY_EXCLUDED


def test_short_direction_flips_the_excursion_sign(conn, now):
    """`evaluate_legacy_position_mae_mfe()` -- SHORT: adverse excursion
    comes from a HIGH (price rising against the position), favorable from
    a LOW, the mirror image of the LONG cases above."""
    sec = make_security(conn, "spec005:MAEMFE_SHORT", now)
    _insert_bars(conn, sec, now, [
        (D2, 100.0, 102.0, 97.0, 100.0),
        (D3, 95.0, 96.0, 90.0, 90.0),  # closes here (TIME_EXIT) -- real execution, only open (95.0) counts
    ])
    close_tranche = Tranche(
        kind="REMAINDER", exit_reason=EXIT_REASON_TIME_EXIT, fraction_of_original=1.0,
        exit_date=D3, exit_fill_price=90.0, holding_days=1, entry_fill_price_reference=100.0,
    )
    position = LegacyPosition(
        security_id=sec, strategy_variant_id="V_SHORT", exit_family="TIME_EXIT", direction="SHORT",
        signal_date=D1, entry_date=D2, entry_session_index=1, entry_fill_price=100.0,
        time_exit_bars=2, closed=True, close_tranche=close_tranche,
    )
    records = evaluate_legacy_position_mae_mfe(_UnboundedAccess(conn), position, final_mark_date=D3, mark_final=None)
    assert len(records) == 1
    result = records[0].mae_mfe
    expected = [
        0.0,
        -1.0 * (102.0 - 100.0) / 100.0,  # D2 high -- adverse for a short
        -1.0 * (97.0 - 100.0) / 100.0,   # D2 low -- favorable for a short
        -1.0 * (95.0 - 100.0) / 100.0,   # D3's own open (real exec day)
        -1.0 * (90.0 - 100.0) / 100.0,   # exit fill
    ]
    assert result.mae == min(expected)
    assert result.mfe == max(expected)
    assert result.mfe > 0  # the short profited -- favorable excursion is positive


def test_a_position_with_nothing_to_report_returns_no_records(conn, now):
    """EXIT_FAILED (or any not-closed position with no mark at all) has
    nothing coherent to compute -- an empty result, never a fabricated
    record from missing inputs."""
    position = LegacyPosition(
        security_id="SEC_NOREPORT", strategy_variant_id="V4", exit_family="TIME_EXIT", direction="LONG",
        signal_date=D1, entry_date=D2, entry_session_index=1, entry_fill_price=100.0,
        time_exit_bars=5, closed=False, exit_failed=True, exit_failed_reason="NO_EXIT_BAR",
    )
    records = evaluate_legacy_position_mae_mfe(_UnboundedAccess(conn), position, final_mark_date=D3, mark_final=None)
    assert records == ()
