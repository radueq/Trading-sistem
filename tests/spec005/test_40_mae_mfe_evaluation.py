"""TEST 40 -- Spec #005 Batch 3 closure verification, blocker #2:
`compute_tranche_mae_mfe()` (amendment section 12) existed and was
correctly formula-tested (TEST 28), but had NO caller anywhere in
`engine.py`/`session.py`/`legacy.py` -- no real `run_stage()` result ever
carried an MAE/MFE value. `evaluate_stop_managed_position_mae_mfe()`/
`evaluate_legacy_position_mae_mfe()` (`backtest.exits.mae_mfe`) wire it
against real positions as a separate evaluation/reporting pass; neither
`StopManagedPosition`/`LegacyPosition`/`Tranche` is modified.

Radu's verdict on `8287ebb` (his own point 2) found four further defects
in that first wiring pass, all fixed here together:

1. A whole missing session or a non-finite OHLC value must never leave
   coverage reading FULL.
2. Open/intraday/close/censored fill conventions need genuinely different
   exit-day treatment (TIME_EXIT/cap close-fills must get their FULL
   range, never excluded as if an intraday exit had occurred).
3. `EXIT_FAILED` must never be reported as an ordinary censored remainder,
   even when `mark_final` happens to be non-None for that security.
4. `PositionMaeMfe` needs a genuinely unique identity (`entry_date`) so
   two successive trades of the same variant/security don't collide.
"""
from __future__ import annotations

import pytest

from data_foundation.model import repository as repo
from data_foundation.model.entities import ActionType, PriceBar

from backtest.data.calendar import build_trading_calendar
from backtest.exits.engine import EntrySignal, run_stage
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
    COVERAGE_MISSING_SESSION_DATA,
    COVERAGE_PARTIAL_EXIT_DAY_EXCLUDED,
    evaluate_legacy_position_mae_mfe,
    evaluate_stop_managed_position_mae_mfe,
)
from backtest.models.entities import (
    FORMATION_SELECTION,
    CalendarSource,
    CostAssumptions,
    ExposureManifest,
    ResearchPlan,
    SelectionFold,
    SelectionRule,
    build_execution_semantics_profile_v1,
    build_research_plan_id,
    research_plan_fingerprint,
)

from spec005.fixtures.legacy_variants import build_registered_time_exit_hypothesis
from spec005.fixtures.pit_universe import insert_corporate_action, make_security

from hypothesis.models.entities import Direction
from hypothesis.registry.hypotheses import HypothesisRegistry

D1, D2, D3, D4, D5 = "2024-06-03", "2024-06-04", "2024-06-05", "2024-06-06", "2024-06-07"
VALIDATION_START, VALIDATION_END, LOCKED_OOS_START = "2024-07-01", "2024-07-31", "2024-08-01"

_ZERO_COSTS = CostAssumptions(
    commission_entry_rate=0.0, commission_exit_rate=0.0, slippage_entry_bps=0.0, slippage_exit_bps=0.0, borrow_annual_rate=0.0,
)


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
    session_dates = (D2, D3, D4, D5)

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

    records = evaluate_stop_managed_position_mae_mfe(_UnboundedAccess(conn), position, session_dates, final_mark_date=D5, mark_final=None)
    assert len(records) == 2
    by_kind = {r.tranche_kind: r for r in records}
    assert set(by_kind) == {"PARTIAL_PROFIT", "REMAINDER"}
    for r in records:
        assert r.security_id == sec
        assert r.strategy_variant_id == "V1"
        assert r.entry_date == D2

    # Partial tranche: window D2..D3, queried as_of=D3 -- split not yet
    # known/effective there, so D2/D3 stay on the PRE-split (~100) scale.
    # D3 is the real-execution exit day (TARGET, intraday): only its OPEN
    # (101.0) counts, high/low excluded.
    partial = by_kind["PARTIAL_PROFIT"].mae_mfe
    assert partial.coverage == COVERAGE_PARTIAL_EXIT_DAY_EXCLUDED
    expected_partial_excursions = [0.0, (102.0 - 100.0) / 100.0, (98.0 - 100.0) / 100.0, (101.0 - 100.0) / 100.0, (120.0 - 100.0) / 100.0]
    assert partial.mae == min(expected_partial_excursions)
    assert partial.mfe == max(expected_partial_excursions)

    # Remainder tranche: window D2..D5, queried as_of=D5 -- the split IS
    # known+effective there, so D2/D3's historical bars are re-expressed
    # on the POST-split (~50) scale -- proving the two tranches genuinely
    # used DIFFERENT, coherent bases. D5 is the real-execution exit day
    # (STOP, intraday): only its OPEN counts.
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
    assert d2_adj_high == 51.0 and d2_adj_high != 102.0  # the historical bar itself was genuinely re-expressed


def test_censored_remainder_includes_the_final_days_own_extremes_not_just_the_mark(conn, now):
    """A still-open remainder's own LAST held day is not an intraday-exit
    day at all -- its high/low are used normally, like any other day in
    the window. D5's own high (112.0) is deliberately more favorable than
    `mark_final` (105.0) -- the correct MFE must reflect the extreme
    actually traded, not just the mark. Coverage reaches FULL (every day,
    including the final one, fully observed)."""
    sec = make_security(conn, "spec005:MAEMFE_CENSORED", now)
    _insert_bars(conn, sec, now, [
        (D2, 100.0, 101.0, 99.0, 100.0),
        (D3, 100.0, 103.0, 98.0, 101.0),
        (D4, 101.0, 108.0, 100.0, 107.0),
        (D5, 107.0, 112.0, 106.0, 105.0),  # the stage's own last session -- fully held, no real exit
    ])
    session_dates = (D2, D3, D4, D5)
    position = StopManagedPosition(
        security_id=sec, direction="LONG", entry_date=D2, signal_date=D1,
        entry_fill_price=100.0, k=2.0, r_multiple=None, fraction=None,
        active_stop=90.0, initial_risk=10.0, target_price=None,
        remaining_quantity=1.0, closed=False, strategy_variant_id="V2",
    )

    records = evaluate_stop_managed_position_mae_mfe(_UnboundedAccess(conn), position, session_dates, final_mark_date=D5, mark_final=105.0)
    assert len(records) == 1
    r = records[0]
    assert r.tranche_kind == "REMAINDER"
    assert r.entry_date == D2
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


def test_censored_remainder_with_a_genuine_data_gap_is_missing_session_data(conn, now):
    """Same shape as the previous test, but D4's own low is missing from
    the recorded bar -- a genuine data gap, distinct from the routine
    exit-day exclusion, downgrades coverage to `COVERAGE_MISSING_SESSION_
    DATA` (closure-verdict fix, post-`8287ebb`: this used to collapse into
    the same `PARTIAL_EXIT_DAY_EXCLUDED` label as the by-design exclusion,
    hiding the difference between an expected omission and a real gap)."""
    sec = make_security(conn, "spec005:MAEMFE_CENSORED_GAP", now)
    repo.insert_price_bars(conn, [
        PriceBar(security_id=sec, date=D2, raw_open=100.0, raw_high=101.0, raw_low=99.0, raw_close=100.0, raw_volume=1000, source_provider="manual", ingestion_timestamp=now),
        PriceBar(security_id=sec, date=D3, raw_open=100.0, raw_high=103.0, raw_low=98.0, raw_close=101.0, raw_volume=1000, source_provider="manual", ingestion_timestamp=now),
        PriceBar(security_id=sec, date=D4, raw_open=101.0, raw_high=108.0, raw_low=None, raw_close=107.0, raw_volume=1000, source_provider="manual", ingestion_timestamp=now),
        PriceBar(security_id=sec, date=D5, raw_open=107.0, raw_high=112.0, raw_low=106.0, raw_close=105.0, raw_volume=1000, source_provider="manual", ingestion_timestamp=now),
    ])
    session_dates = (D2, D3, D4, D5)
    position = StopManagedPosition(
        security_id=sec, direction="LONG", entry_date=D2, signal_date=D1,
        entry_fill_price=100.0, k=2.0, r_multiple=None, fraction=None,
        active_stop=90.0, initial_risk=10.0, target_price=None,
        remaining_quantity=1.0, closed=False, strategy_variant_id="V3",
    )
    records = evaluate_stop_managed_position_mae_mfe(_UnboundedAccess(conn), position, session_dates, final_mark_date=D5, mark_final=105.0)
    assert len(records) == 1
    result = records[0].mae_mfe
    assert result.coverage == COVERAGE_MISSING_SESSION_DATA
    # Radu's own follow-up correction: the label alone is not enough --
    # base section 17 makes the metrics themselves UNAVAILABLE, never a
    # number computed from the incomplete remainder.
    assert result.mae is None
    assert result.mfe is None


def test_censored_remainder_with_a_whole_missing_session_is_missing_session_data(conn, now):
    """Defect #1: a session the CALENDAR expects inside the window, but
    for which the security has no price bar AT ALL (not just a null
    field), must also downgrade coverage -- never silently vanish from
    consideration and leave FULL unjustified."""
    sec = make_security(conn, "spec005:MAEMFE_MISSING_WHOLE_SESSION", now)
    _insert_bars(conn, sec, now, [
        (D2, 100.0, 101.0, 99.0, 100.0),
        # D3 entirely absent -- a real data gap, the calendar still expects it.
        (D4, 101.0, 108.0, 100.0, 107.0),
    ])
    session_dates = (D2, D3, D4)  # the calendar's own authorized sessions -- D3 IS expected
    position = StopManagedPosition(
        security_id=sec, direction="LONG", entry_date=D2, signal_date=D1,
        entry_fill_price=100.0, k=2.0, r_multiple=None, fraction=None,
        active_stop=90.0, initial_risk=10.0, target_price=None,
        remaining_quantity=1.0, closed=False, strategy_variant_id="V_GAP",
    )
    records = evaluate_stop_managed_position_mae_mfe(_UnboundedAccess(conn), position, session_dates, final_mark_date=D4, mark_final=107.0)
    assert len(records) == 1
    result = records[0].mae_mfe
    assert result.coverage == COVERAGE_MISSING_SESSION_DATA
    assert result.mae is None
    assert result.mfe is None


def test_time_exit_close_fill_day_gets_its_full_range_not_excluded(conn, now):
    """Defect #2, the core of Radu's finding: TIME_EXIT (and, identically,
    MAX_HOLDING_BARS_FORCED_EXIT) is a scheduled CLOSE fill -- the
    position held through that whole session up to and including the
    close that closed it, so base section 17 requires its full range
    INCLUDED, unlike SIGNAL_INVALIDATION's own open-fill exit. D3's own
    high (108.0) is deliberately more favorable than the close/exit_fill
    (103.0) -- a wiring that still excluded it would understate MFE."""
    sec = make_security(conn, "spec005:MAEMFE_TIMEEXIT_CLOSE", now)
    _insert_bars(conn, sec, now, [
        (D2, 100.0, 101.0, 99.0, 100.0),   # entry day
        (D3, 100.0, 108.0, 97.0, 103.0),   # TIME_EXIT closes HERE, at the close (103.0)
    ])
    session_dates = (D2, D3)
    close_tranche = Tranche(
        kind="REMAINDER", exit_reason=EXIT_REASON_TIME_EXIT, fraction_of_original=1.0,
        exit_date=D3, exit_fill_price=103.0, holding_days=1, entry_fill_price_reference=100.0,
    )
    position = LegacyPosition(
        security_id=sec, strategy_variant_id="V_TE", exit_family="TIME_EXIT", direction="LONG",
        signal_date=D1, entry_date=D2, entry_session_index=1, entry_fill_price=100.0,
        time_exit_bars=2, closed=True, close_tranche=close_tranche,
    )
    records = evaluate_legacy_position_mae_mfe(_UnboundedAccess(conn), position, session_dates, final_mark_date=D3, mark_final=None)
    assert len(records) == 1
    result = records[0].mae_mfe
    assert result.coverage == COVERAGE_FULL
    assert result.mfe == (108.0 - 100.0) / 100.0  # D3's own high -- NOT excluded
    assert result.mae == (97.0 - 100.0) / 100.0  # D3's own low -- NOT excluded either


def test_short_direction_flips_the_excursion_sign(conn, now):
    """`evaluate_legacy_position_mae_mfe()` -- SHORT, TIME_EXIT (a close
    fill, full range included): adverse excursion comes from a HIGH
    (price rising against the position), favorable from a LOW, the
    mirror image of the LONG cases above. D3's own low (85.0) is deliberately
    more favorable than the exit fill (90.0), proving the full-range
    inclusion actually matters here too."""
    sec = make_security(conn, "spec005:MAEMFE_SHORT", now)
    _insert_bars(conn, sec, now, [
        (D2, 100.0, 102.0, 97.0, 100.0),
        (D3, 95.0, 96.0, 85.0, 90.0),  # closes here (TIME_EXIT, close fill) -- full range now included
    ])
    session_dates = (D2, D3)
    close_tranche = Tranche(
        kind="REMAINDER", exit_reason=EXIT_REASON_TIME_EXIT, fraction_of_original=1.0,
        exit_date=D3, exit_fill_price=90.0, holding_days=1, entry_fill_price_reference=100.0,
    )
    position = LegacyPosition(
        security_id=sec, strategy_variant_id="V_SHORT", exit_family="TIME_EXIT", direction="SHORT",
        signal_date=D1, entry_date=D2, entry_session_index=1, entry_fill_price=100.0,
        time_exit_bars=2, closed=True, close_tranche=close_tranche,
    )
    records = evaluate_legacy_position_mae_mfe(_UnboundedAccess(conn), position, session_dates, final_mark_date=D3, mark_final=None)
    assert len(records) == 1
    result = records[0].mae_mfe
    assert result.coverage == COVERAGE_FULL
    # SHORT: D2 high=102 adverse (-0.02), D2 low=97 favorable (+0.03),
    # D3 high=96 favorable (+0.04), D3 low=85 favorable (+0.15, the
    # extreme), exit fill=90 favorable (+0.10).
    assert result.mae == -0.02
    assert result.mfe == 0.15


def test_exit_failed_position_never_borrows_the_securitys_own_final_mark(conn, now):
    """Defect #3: `final_closes` is keyed by SECURITY, not by position --
    an `EXIT_FAILED` position sharing a security with a genuinely censored
    one must never be reported as an ordinary censored remainder just
    because `mark_final` happens to be non-None for that security."""
    sec = make_security(conn, "spec005:MAEMFE_EXITFAILED", now)
    _insert_bars(conn, sec, now, [(D2, 100.0, 101.0, 99.0, 100.0)])
    session_dates = (D2, D3)

    legacy_position = LegacyPosition(
        security_id=sec, strategy_variant_id="V_FAIL", exit_family="TIME_EXIT", direction="LONG",
        signal_date=D1, entry_date=D2, entry_session_index=1, entry_fill_price=100.0,
        time_exit_bars=5, closed=False, exit_failed=True, exit_failed_reason="NO_EXIT_BAR",
    )
    # mark_final is deliberately NON-None here -- simulating the security's
    # own final_closes entry being legitimately populated by OTHER activity.
    records = evaluate_legacy_position_mae_mfe(_UnboundedAccess(conn), legacy_position, session_dates, final_mark_date=D3, mark_final=105.0)
    assert records == ()

    sm_position = StopManagedPosition(
        security_id=sec, direction="LONG", entry_date=D2, signal_date=D1,
        entry_fill_price=100.0, k=2.0, r_multiple=None, fraction=None,
        active_stop=90.0, initial_risk=10.0, target_price=None,
        remaining_quantity=1.0, closed=False, exit_failed=True, exit_failed_reason="NO_EXIT_BAR",
        strategy_variant_id="V_FAIL2",
    )
    records2 = evaluate_stop_managed_position_mae_mfe(_UnboundedAccess(conn), sm_position, session_dates, final_mark_date=D3, mark_final=105.0)
    assert records2 == ()


def test_a_position_with_nothing_to_report_returns_no_records(conn, now):
    """EXIT_FAILED with no mark at all has nothing coherent to compute --
    an empty result, never a fabricated record from missing inputs."""
    position = LegacyPosition(
        security_id="SEC_NOREPORT", strategy_variant_id="V4", exit_family="TIME_EXIT", direction="LONG",
        signal_date=D1, entry_date=D2, entry_session_index=1, entry_fill_price=100.0,
        time_exit_bars=5, closed=False, exit_failed=True, exit_failed_reason="NO_EXIT_BAR",
    )
    records = evaluate_legacy_position_mae_mfe(_UnboundedAccess(conn), position, (D2, D3), final_mark_date=D3, mark_final=None)
    assert records == ()


def _build_time_exit_only_plan(hid: str, calendar_id: str, benchmark_security_id: str, cost_assumptions: CostAssumptions = _ZERO_COSTS) -> ResearchPlan:
    profile = build_execution_semantics_profile_v1()
    rule = SelectionRule(minimum_executed_trades=1, minimum_evaluable_trades=1, minimum_evaluable_ratio=0.5)
    exposure = ExposureManifest(declared_unseen=True)
    folds = (SelectionFold("fold_1", D1, D4),)
    fields = dict(
        formation_start=D1, formation_end=D4, validation_start=VALIDATION_START, validation_end=VALIDATION_END,
        locked_oos_start=LOCKED_OOS_START, selection_folds=folds, hypothesis_cohort_ids=(hid,),
        trading_calendar_id=calendar_id, benchmark_security_id=benchmark_security_id,
        execution_semantics_profile_id=profile.profile_id, selection_rule=rule,
        cost_assumptions=cost_assumptions, exposure_manifest=exposure,
    )
    fp = research_plan_fingerprint(**fields)
    plan_id, plan_hash = build_research_plan_id(fp)
    return ResearchPlan(research_plan_id=plan_id, plan_hash=plan_hash, created_at="t", created_by="test", **fields)


def test_real_run_stage_traversal_disambiguates_successive_trades_of_the_same_variant(conn, now):
    """Defect #4, end to end through the real engine: a TIME_EXIT(1)
    variant that reopens on a SECOND signal (exactly the ordinary shape
    this engine already produces -- test_39's own D1/D2 case) must yield
    TWO distinct `PositionMaeMfe` records, not one overwriting the other.
    `(security_id, strategy_variant_id, tranche_kind)` alone is identical
    for both trades -- only `entry_date` tells them apart."""
    sec = make_security(conn, "spec005:MAEMFE_SUCCESSIVE", now)
    bench = make_security(conn, "spec005:MAEMFE_SUCCESSIVE_BENCH", now)
    _insert_bars(conn, sec, now, [
        (D1, 100.0, 101.0, 99.0, 100.0),
        (D2, 100.0, 103.0, 98.0, 102.0),   # trade 1: enters here, TIME_EXIT(1) exits at THIS close (102.0)
        (D3, 102.0, 104.0, 100.0, 103.0),
        (D4, 103.0, 106.0, 101.0, 105.0),  # trade 2: enters here, TIME_EXIT(1) exits at THIS close (105.0)
    ])
    _insert_bars(conn, bench, now, [(d, 200.0, 201.0, 199.0, 200.0) for d in (D1, D2, D3, D4)])
    session_dates = (D1, D2, D3, D4)

    calendar = build_trading_calendar(
        source=CalendarSource.SYNTHETIC_TEST_FIXTURE.value, calendar_identifier="SPEC005_MAEMFE_SUCCESSIVE_CALENDAR",
        calendar_version="v1", market="US_EQUITIES", timezone="America/New_York",
        coverage_start=D1, coverage_end=D4, session_dates=session_dates,
        session_open_time="09:30", session_close_time="16:00", verified_by="test", verified_at="2026-01-01T00:00:00Z",
    )
    registry = HypothesisRegistry()
    hid, vid = build_registered_time_exit_hypothesis(registry, time_exit_bars=1, signature_id="SIG_MAEMFE_SUCCESSIVE")
    plan = _build_time_exit_only_plan(hid, calendar.calendar_id, bench)

    entry_signals = {
        (sec, vid, D1): EntrySignal(security_id=sec, strategy_variant_id=vid),
        (sec, vid, D3): EntrySignal(security_id=sec, strategy_variant_id=vid),
    }
    result = run_stage(
        plan, registry, conn, FORMATION_SELECTION, calendar,
        entry_signals=entry_signals, invalidation_observer=lambda position, session_date: "VALID_HOLD",
        stop_managed_profile=None,
    )
    assert len(result.positions) == 2
    assert {p.entry_date for p in result.positions} == {D2, D4}

    pit = _UnboundedAccess(conn)
    records = []
    for position in result.positions:
        records.extend(evaluate_legacy_position_mae_mfe(pit, position, session_dates, final_mark_date=D4, mark_final=None))

    assert len(records) == 2
    by_entry_date = {r.entry_date: r for r in records}
    assert set(by_entry_date) == {D2, D4}
    for r in records:
        assert r.security_id == sec
        assert r.strategy_variant_id == vid
        assert r.tranche_kind == "REMAINDER"
        # (security_id, strategy_variant_id, tranche_kind) is IDENTICAL
        # across both records -- entry_date is the only disambiguator.
    trade1, trade2 = by_entry_date[D2], by_entry_date[D4]
    assert trade1.mae_mfe.coverage == COVERAGE_FULL  # TIME_EXIT close fill -- full range included
    assert trade1.mae_mfe.mfe == (103.0 - 100.0) / 100.0  # D2's own high
    assert trade2.mae_mfe.mfe == (106.0 - 103.0) / 103.0  # D4's own high


_SLIPPAGE_COSTS = CostAssumptions(
    commission_entry_rate=0.0, commission_exit_rate=0.0, slippage_entry_bps=100.0, slippage_exit_bps=0.0, borrow_annual_rate=0.0,
)


def test_real_run_stage_with_entry_slippage_long_mae_mfe_uses_the_raw_pre_slippage_reference(conn, now):
    """Radu's own finding on `3aae3ef`, reproduced through the REAL
    engine end to end (`run_stage()` -> `evaluate_legacy_position_mae_
    mfe()`), not just the isolated formula: 100bps entry slippage on a
    LONG position makes `position.entry_fill_price` 101.0 (`F_e`) even
    though the real market open (`P_e`) was 100.0. MAE/MFE must still
    read exactly -10%/+10% (base section 17's cost-free excursions,
    relative to `P_e`) -- the skewed -10.8911%/+8.9109% a slipped
    reference would produce is exactly the defect this fixes."""
    sec = make_security(conn, "spec005:MAEMFE_SLIPPAGE_LONG", now)
    bench = make_security(conn, "spec005:MAEMFE_SLIPPAGE_LONG_BENCH", now)
    _insert_bars(conn, sec, now, [
        (D1, 100.0, 101.0, 99.0, 100.0),
        (D2, 100.0, 110.0, 90.0, 105.0),  # entry day (P_e=100.0) AND exit day (TIME_EXIT(1), close fill)
        (D3, 105.0, 106.0, 104.0, 105.0),
        (D4, 105.0, 106.0, 104.0, 105.0),
    ])
    _insert_bars(conn, bench, now, [(d, 200.0, 201.0, 199.0, 200.0) for d in (D1, D2, D3, D4)])
    session_dates = (D1, D2, D3, D4)

    calendar = build_trading_calendar(
        source=CalendarSource.SYNTHETIC_TEST_FIXTURE.value, calendar_identifier="SPEC005_MAEMFE_SLIPPAGE_LONG_CALENDAR",
        calendar_version="v1", market="US_EQUITIES", timezone="America/New_York",
        coverage_start=D1, coverage_end=D4, session_dates=session_dates,
        session_open_time="09:30", session_close_time="16:00", verified_by="test", verified_at="2026-01-01T00:00:00Z",
    )
    registry = HypothesisRegistry()
    hid, vid = build_registered_time_exit_hypothesis(
        registry, direction=Direction.LONG.value, time_exit_bars=1, signature_id="SIG_MAEMFE_SLIPPAGE_LONG",
    )
    plan = _build_time_exit_only_plan(hid, calendar.calendar_id, bench, cost_assumptions=_SLIPPAGE_COSTS)

    entry_signals = {(sec, vid, D1): EntrySignal(security_id=sec, strategy_variant_id=vid)}
    result = run_stage(
        plan, registry, conn, FORMATION_SELECTION, calendar,
        entry_signals=entry_signals, invalidation_observer=lambda position, session_date: "VALID_HOLD",
        stop_managed_profile=None,
    )
    assert len(result.positions) == 1
    position = result.positions[0]
    assert position.entry_fill_price == pytest.approx(101.0)  # F_e -- the slipped fill, NOT the MAE/MFE reference

    records = evaluate_legacy_position_mae_mfe(_UnboundedAccess(conn), position, session_dates, final_mark_date=D4, mark_final=None)
    assert len(records) == 1
    result_mae_mfe = records[0].mae_mfe
    assert result_mae_mfe.coverage == COVERAGE_FULL
    assert result_mae_mfe.mae == pytest.approx(-0.10)
    assert result_mae_mfe.mfe == pytest.approx(0.10)


def test_real_run_stage_with_entry_slippage_short_mae_mfe_uses_the_raw_pre_slippage_reference(conn, now):
    """Mirror of the LONG case: SHORT with 100bps entry slippage makes
    `F_e` LOWER than the raw open (`P_e`) -- `apply_entry_slippage`'s own
    `d=-1` sign flip. MAE/MFE must still read exactly -10%/+10% relative
    to the raw 100.0, not whatever `F_e` came out to."""
    sec = make_security(conn, "spec005:MAEMFE_SLIPPAGE_SHORT", now)
    bench = make_security(conn, "spec005:MAEMFE_SLIPPAGE_SHORT_BENCH", now)
    _insert_bars(conn, sec, now, [
        (D1, 100.0, 101.0, 99.0, 100.0),
        (D2, 100.0, 110.0, 90.0, 95.0),  # entry day (P_e=100.0) AND exit day (TIME_EXIT(1), close fill)
        (D3, 95.0, 96.0, 94.0, 95.0),
        (D4, 95.0, 96.0, 94.0, 95.0),
    ])
    _insert_bars(conn, bench, now, [(d, 200.0, 201.0, 199.0, 200.0) for d in (D1, D2, D3, D4)])
    session_dates = (D1, D2, D3, D4)

    calendar = build_trading_calendar(
        source=CalendarSource.SYNTHETIC_TEST_FIXTURE.value, calendar_identifier="SPEC005_MAEMFE_SLIPPAGE_SHORT_CALENDAR",
        calendar_version="v1", market="US_EQUITIES", timezone="America/New_York",
        coverage_start=D1, coverage_end=D4, session_dates=session_dates,
        session_open_time="09:30", session_close_time="16:00", verified_by="test", verified_at="2026-01-01T00:00:00Z",
    )
    registry = HypothesisRegistry()
    hid, vid = build_registered_time_exit_hypothesis(
        registry, direction=Direction.SHORT.value, time_exit_bars=1, signature_id="SIG_MAEMFE_SLIPPAGE_SHORT",
    )
    plan = _build_time_exit_only_plan(hid, calendar.calendar_id, bench, cost_assumptions=_SLIPPAGE_COSTS)

    entry_signals = {(sec, vid, D1): EntrySignal(security_id=sec, strategy_variant_id=vid)}
    result = run_stage(
        plan, registry, conn, FORMATION_SELECTION, calendar,
        entry_signals=entry_signals, invalidation_observer=lambda position, session_date: "VALID_HOLD",
        stop_managed_profile=None,
    )
    assert len(result.positions) == 1
    position = result.positions[0]
    assert position.entry_fill_price == pytest.approx(99.0)  # F_e -- SHORT: d=-1, 100*(1+(-1)*0.01)=99.0

    records = evaluate_legacy_position_mae_mfe(_UnboundedAccess(conn), position, session_dates, final_mark_date=D4, mark_final=None)
    assert len(records) == 1
    result_mae_mfe = records[0].mae_mfe
    assert result_mae_mfe.coverage == COVERAGE_FULL
    # SHORT relative to P_e=100.0: high=110 adverse (-0.10), low=90 favorable (+0.10).
    assert result_mae_mfe.mae == pytest.approx(-0.10)
    assert result_mae_mfe.mfe == pytest.approx(0.10)


def test_slipped_entry_reference_across_a_split_still_derives_pe_from_each_tranches_own_bars(conn, now):
    """Combines the split-basis-coherence guarantee with the slippage
    fix: `entry_fill_price_reference` is deliberately set to a SLIPPED
    value (not matching the raw bar open at all) to prove the evaluator
    genuinely ignores it and derives `P_e` fresh from `bars`, for BOTH
    tranches, even with an intervening split."""
    sec = make_security(conn, "spec005:MAEMFE_SLIPPAGE_SPLIT", now)
    _insert_bars(conn, sec, now, [
        (D2, 100.0, 102.0, 98.0, 100.0),   # entry day, pre-split scale -- P_e=100.0 (raw), NOT the slipped 101.0 below
        (D3, 101.0, 125.0, 100.0, 120.0),  # partial tranche closes HERE (target=120), pre-split scale
        (D4, 61.0, 63.0, 59.0, 60.0),      # split effective HERE (2-for-1) -- already post-split raw scale
        (D5, 56.0, 58.0, 54.0, 55.0),      # remainder closes HERE (stop=55), post-split scale
    ])
    insert_corporate_action(conn, sec, "ACT_SPLIT_2", ActionType.SPLIT.value, effective_date=D4, value=2.0, now=now)
    session_dates = (D2, D3, D4, D5)

    partial_tranche = Tranche(
        kind="PARTIAL_PROFIT", exit_reason=EXIT_REASON_TARGET, fraction_of_original=0.5,
        exit_date=D3, exit_fill_price=120.0, holding_days=1,
        entry_fill_price_reference=101.0,  # deliberately SLIPPED (F_e), not the raw 100.0 -- must be ignored for MAE/MFE
    )
    close_tranche = Tranche(
        kind="REMAINDER", exit_reason=EXIT_REASON_STOP, fraction_of_original=0.5,
        exit_date=D5, exit_fill_price=55.0, holding_days=3,
        entry_fill_price_reference=50.5,  # deliberately SLIPPED post-split (F_e/2), not the raw 50.0 -- must be ignored
    )
    position = StopManagedPosition(
        security_id=sec, direction="LONG", entry_date=D2, signal_date=D1,
        entry_fill_price=50.5,  # also slipped -- must be ignored for the censored path too, not exercised here
        k=2.0, r_multiple=2.0, fraction=0.5,
        active_stop=55.0, initial_risk=25.0, target_price=None,
        remaining_quantity=0.0, applied_factor=2.0,
        target_consumed=True, partial_tranche=partial_tranche,
        closed=True, close_tranche=close_tranche, strategy_variant_id="V_SLIP_SPLIT",
    )

    records = evaluate_stop_managed_position_mae_mfe(_UnboundedAccess(conn), position, session_dates, final_mark_date=D5, mark_final=None)
    assert len(records) == 2
    by_kind = {r.tranche_kind: r for r in records}

    # Partial tranche: as_of=D3, pre-split -- P_e must be 100.0 (D2's raw
    # open), never 101.0 (the deliberately-wrong slipped reference).
    partial = by_kind["PARTIAL_PROFIT"].mae_mfe
    assert partial.coverage == COVERAGE_PARTIAL_EXIT_DAY_EXCLUDED
    expected_partial = [0.0, (102.0 - 100.0) / 100.0, (98.0 - 100.0) / 100.0, (101.0 - 100.0) / 100.0, (120.0 - 100.0) / 100.0]
    assert partial.mae == pytest.approx(min(expected_partial))
    assert partial.mfe == pytest.approx(max(expected_partial))

    # Remainder tranche: as_of=D5, post-split -- P_e must be 50.0 (D2's
    # raw open re-expressed on the post-split basis), never 50.5.
    remainder = by_kind["REMAINDER"].mae_mfe
    assert remainder.coverage == COVERAGE_PARTIAL_EXIT_DAY_EXCLUDED
    # D2 is the entry day but NOT the exit day here, so its own (post-split
    # adjusted) high/low are included in full -- entry never suppresses a
    # non-exit day's range, it only supplies P_e as the reference point.
    d2_adj_high, d2_adj_low = 102.0 / 2.0, 98.0 / 2.0
    d3_adj_high, d3_adj_low = 125.0 / 2.0, 100.0 / 2.0
    expected_remainder = [
        0.0,
        (d2_adj_high - 50.0) / 50.0, (d2_adj_low - 50.0) / 50.0,
        (d3_adj_high - 50.0) / 50.0, (d3_adj_low - 50.0) / 50.0,
        (63.0 - 50.0) / 50.0, (59.0 - 50.0) / 50.0,
        (56.0 - 50.0) / 50.0,  # D5 is the real-execution exit day -- only its OPEN counts
        (55.0 - 50.0) / 50.0,  # the exit fill itself
    ]
    assert remainder.mae == pytest.approx(min(expected_remainder))
    assert remainder.mfe == pytest.approx(max(expected_remainder))
