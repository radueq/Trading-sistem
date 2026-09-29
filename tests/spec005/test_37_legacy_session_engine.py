"""TEST 37 -- Spec #005 Discovery Integration & Legacy Exits, obligation 3:
`backtest.exits.legacy.LegacySessionEngine`, the TIME_EXIT/SIGNAL_
INVALIDATION execution engine `docs/spec005_known_limitations.md` names as
missing ("`SessionEngine` only ever constructs/advances `StopManagedPosition`
objects... nothing to run for that cohort's old-family variants"). Mirrors
TEST 33's own structure/discipline (construction-time guards first, then
real-`conn` per-session mechanics), independently, since `LegacySessionEngine`
is a SEPARATE engine from `SessionEngine` (never an extension of it).
"""
from __future__ import annotations

from data_foundation.model import repository as repo
from data_foundation.model.entities import PriceBar

from hypothesis.registry.hypotheses import HypothesisRegistry

from backtest.exits.costs import apply_entry_slippage, apply_exit_slippage, tranche_net_return
from backtest.exits.engine import ENTRY_EXECUTED, EntryDisposition, EntrySignal
from backtest.exits.entities import (
    ENTRY_NO_ENTRY_BAR,
    ENTRY_SUPPRESSED_STAGE_BOUNDARY,
    ENTRY_UNSUPPORTED_EXIT_FAMILY,
    ENTRY_VARIANT_NOT_FOUND,
    ENTRY_VARIANT_NOT_IN_ACCEPTED_COHORT,
    EVALUABILITY_EVALUABLE,
    EVALUABILITY_UNEVALUABLE,
    EXIT_REASON_MAX_HOLDING_BARS_FORCED_EXIT,
    EXIT_REASON_SIGNAL_INVALIDATION,
    EXIT_REASON_TIME_EXIT,
    LIFECYCLE_CENSORED_AT_HORIZON,
    LIFECYCLE_CLOSED,
    LIFECYCLE_EXIT_FAILED,
    LegacyPosition,
    REASON_INVALIDATION_PATH_INCOMPLETE,
    REASON_NO_EXIT_BAR,
    REASON_SPLIT_RECONCILIATION_INCOMPLETE,
)
from backtest.exits.legacy import (
    LegacySessionEngine,
    advance_legacy_position_at_close,
    classify_legacy_position,
    evaluate_legacy_stage_results,
    reconcile_split_for_legacy_position,
)
from backtest.models.entities import CostAssumptions

from spec005.fixtures.legacy_variants import build_registered_signal_invalidation_hypothesis, build_registered_time_exit_hypothesis
from spec005.fixtures.pit_universe import insert_corporate_action, make_security
from spec005.fixtures.stop_managed_variants import build_registered_stop_managed_hypothesis

_ZERO_COSTS = CostAssumptions(
    commission_entry_rate=0.0, commission_exit_rate=0.0, slippage_entry_bps=0.0, slippage_exit_bps=0.0, borrow_annual_rate=0.0,
)


class _EmptyAccess:
    def get_price_series_as_of(self, security_id, as_of):
        raise AssertionError(f"must never read a price for a rejected signal: get_price_series_as_of({security_id!r}, {as_of!r})")

    def get_corporate_actions_as_of(self, security_id, as_of):
        raise AssertionError(f"must never read corporate actions for a rejected signal: get_corporate_actions_as_of({security_id!r}, {as_of!r})")


class _UnboundedAccess:
    def __init__(self, conn):
        self.conn = conn

    def get_price_series_as_of(self, security_id, as_of):
        from data_foundation.pit import access as pit
        return pit.get_price_series_as_of(self.conn, security_id, as_of)

    def get_corporate_actions_as_of(self, security_id, as_of):
        from data_foundation.pit import access as pit
        return pit.get_corporate_actions_as_of(self.conn, security_id, as_of)


def _never_invalidated(position, session_date):
    return "VALID_HOLD"


def _insert_bars(conn, security_id, now, rows):
    repo.insert_price_bars(conn, [
        PriceBar(
            security_id=security_id, date=d, raw_open=o, raw_high=h, raw_low=l, raw_close=c,
            raw_volume=1000, source_provider="manual", ingestion_timestamp=now,
        )
        for d, o, h, l, c in rows
    ])


D1, D2, D3, D4, D5, D6 = "2024-06-03", "2024-06-04", "2024-06-05", "2024-06-06", "2024-06-07", "2024-06-08"


# -- Construction-time guards (mirror SessionEngine's own, independently) --

def test_signal_on_the_stage_last_session_is_suppressed_without_reading_any_price():
    session_dates = (D1, D2, D3)
    last_session = session_dates[-1]
    signal = EntrySignal(security_id="SEC_LEGACY_SUPPRESSED", strategy_variant_id="var_never_looked_up")
    engine = LegacySessionEngine(
        pit=_EmptyAccess(), session_dates=session_dates, registry=HypothesisRegistry(),
        accepted_hypothesis_ids=frozenset(),
        entry_signals={("SEC_LEGACY_SUPPRESSED", "var_never_looked_up", last_session): signal},
        invalidation_observer=_never_invalidated, cost_assumptions=_ZERO_COSTS,
    )
    result = engine.run()
    assert result.positions == ()
    assert result.entry_dispositions == (
        EntryDisposition(
            security_id="SEC_LEGACY_SUPPRESSED", strategy_variant_id="var_never_looked_up", signal_date=last_session,
            entry_date="<beyond authorized stage>", disposition=ENTRY_SUPPRESSED_STAGE_BOUNDARY,
        ),
    )


def test_unresolvable_variant_is_rejected_before_any_price_read():
    registry = HypothesisRegistry()
    signal = EntrySignal(security_id="SEC_X", strategy_variant_id="NOT_REGISTERED")
    engine = LegacySessionEngine(
        pit=_EmptyAccess(), session_dates=(D1, D2), registry=registry, accepted_hypothesis_ids=frozenset(),
        entry_signals={("SEC_X", "NOT_REGISTERED", D1): signal}, invalidation_observer=_never_invalidated,
        cost_assumptions=_ZERO_COSTS,
    )
    result = engine.run()
    assert result.positions == ()
    assert result.entry_dispositions == (
        EntryDisposition("SEC_X", "NOT_REGISTERED", D1, D2, ENTRY_VARIANT_NOT_FOUND),
    )


def test_variant_outside_accepted_cohort_is_rejected():
    registry = HypothesisRegistry()
    hid, vid = build_registered_time_exit_hypothesis(registry, time_exit_bars=3, signature_id="SIG_LEGACY_OFFCOHORT")
    signal = EntrySignal(security_id="SEC_X", strategy_variant_id=vid)
    engine = LegacySessionEngine(
        pit=_EmptyAccess(), session_dates=(D1, D2), registry=registry, accepted_hypothesis_ids=frozenset(),  # empty cohort
        entry_signals={("SEC_X", vid, D1): signal}, invalidation_observer=_never_invalidated, cost_assumptions=_ZERO_COSTS,
    )
    result = engine.run()
    assert result.entry_dispositions == (EntryDisposition("SEC_X", vid, D1, D2, ENTRY_VARIANT_NOT_IN_ACCEPTED_COHORT),)


def test_stop_managed_variant_is_an_unsupported_family_for_the_legacy_engine():
    registry = HypothesisRegistry()
    hid, vid = build_registered_stop_managed_hypothesis(registry, signature_id="SIG_LEGACY_WRONGFAM")
    signal = EntrySignal(security_id="SEC_X", strategy_variant_id=vid)
    engine = LegacySessionEngine(
        pit=_EmptyAccess(), session_dates=(D1, D2), registry=registry, accepted_hypothesis_ids=frozenset({hid}),
        entry_signals={("SEC_X", vid, D1): signal}, invalidation_observer=_never_invalidated, cost_assumptions=_ZERO_COSTS,
    )
    result = engine.run()
    assert result.entry_dispositions == (EntryDisposition("SEC_X", vid, D1, D2, ENTRY_UNSUPPORTED_EXIT_FAMILY),)


def test_missing_entry_bar_is_rejected(conn, now):
    sec = make_security(conn, "spec005:LEGACY_NO_ENTRY_BAR", now)
    _insert_bars(conn, sec, now, [(D1, 100.0, 101.0, 99.0, 100.0)])  # no bar at all on D2, the entry date
    registry = HypothesisRegistry()
    hid, vid = build_registered_time_exit_hypothesis(registry, time_exit_bars=3, signature_id="SIG_LEGACY_NOENTRYBAR")
    signal = EntrySignal(security_id=sec, strategy_variant_id=vid)
    engine = LegacySessionEngine(
        pit=_UnboundedAccess(conn), session_dates=(D1, D2), registry=registry,
        accepted_hypothesis_ids=frozenset({hid}), entry_signals={(sec, vid, D1): signal},
        invalidation_observer=_never_invalidated, cost_assumptions=_ZERO_COSTS,
    )
    result = engine.run()
    assert result.positions == ()
    assert result.entry_dispositions == (EntryDisposition(sec, vid, D1, D2, ENTRY_NO_ENTRY_BAR),)


def test_entry_signals_identity_mismatch_is_rejected_at_construction():
    registry = HypothesisRegistry()
    hid_a, vid_a = build_registered_time_exit_hypothesis(registry, time_exit_bars=3, signature_id="SIG_LEGACY_MISMATCH_A")
    _hid_b, vid_b = build_registered_time_exit_hypothesis(registry, time_exit_bars=3, signature_id="SIG_LEGACY_MISMATCH_B")
    mismatched_signal = EntrySignal(security_id="SEC_MISMATCH", strategy_variant_id=vid_a)
    try:
        LegacySessionEngine(
            pit=_EmptyAccess(), session_dates=(D1, D2), registry=registry, accepted_hypothesis_ids=frozenset({hid_a}),
            entry_signals={("SEC_MISMATCH", vid_b, D1): mismatched_signal},
            invalidation_observer=_never_invalidated, cost_assumptions=_ZERO_COSTS,
        )
        assert False, "expected ValueError"
    except ValueError as e:
        assert "does not match its own EntrySignal's identity" in str(e)


def test_session_dates_out_of_order_is_refused_at_construction():
    try:
        LegacySessionEngine(
            pit=_EmptyAccess(), session_dates=(D2, D1), registry=HypothesisRegistry(),
            accepted_hypothesis_ids=frozenset(), entry_signals={}, invalidation_observer=_never_invalidated,
            cost_assumptions=_ZERO_COSTS,
        )
        assert False, "expected ValueError"
    except ValueError as e:
        assert "strictly increasing" in str(e)


def test_empty_session_dates_is_refused_at_construction():
    try:
        LegacySessionEngine(
            pit=_EmptyAccess(), session_dates=(), registry=HypothesisRegistry(), accepted_hypothesis_ids=frozenset(),
            entry_signals={}, invalidation_observer=_never_invalidated, cost_assumptions=_ZERO_COSTS,
        )
        assert False, "expected ValueError"
    except ValueError as e:
        assert "non-empty" in str(e)


# -- TIME_EXIT mechanics (real conn) ------------------------------------

def test_time_exit_closes_at_the_close_of_the_correct_holding_bar(conn, now):
    """Spec #004: holding bar 1 = entry bar itself (D2); holding bar N =
    entry bar index + (N-1). time_exit_bars=3 -> exit at D4's close
    (entry index 1 + 2 = 3, i.e. session_dates[3])."""
    sec = make_security(conn, "spec005:LEGACY_TIME_EXIT", now)
    _insert_bars(conn, sec, now, [
        (D1, 100.0, 101.0, 99.0, 100.0),
        (D2, 100.0, 101.0, 99.0, 100.0),  # entry day, open=100
        (D3, 100.0, 106.0, 99.0, 105.0),
        (D4, 105.0, 111.0, 104.0, 110.0),  # exit day, close=110
        (D5, 110.0, 111.0, 109.0, 110.0),
        (D6, 110.0, 111.0, 109.0, 110.0),
    ])
    registry = HypothesisRegistry()
    hid, vid = build_registered_time_exit_hypothesis(registry, time_exit_bars=3, signature_id="SIG_LEGACY_TE_1")
    signal = EntrySignal(security_id=sec, strategy_variant_id=vid)
    engine = LegacySessionEngine(
        pit=_UnboundedAccess(conn), session_dates=(D1, D2, D3, D4, D5, D6), registry=registry,
        accepted_hypothesis_ids=frozenset({hid}), entry_signals={(sec, vid, D1): signal},
        invalidation_observer=_never_invalidated, cost_assumptions=_ZERO_COSTS,
    )
    result = engine.run()
    assert len(result.positions) == 1
    pos = result.positions[0]
    assert pos.entry_date == D2
    assert pos.entry_fill_price == 100.0
    assert pos.closed is True
    assert pos.close_tranche.exit_reason == EXIT_REASON_TIME_EXIT
    assert pos.close_tranche.exit_date == D4
    assert pos.close_tranche.exit_fill_price == 110.0
    assert pos.close_tranche.holding_days == 2  # D2 -> D4
    assert result.entry_dispositions == (EntryDisposition(sec, vid, D1, D2, ENTRY_EXECUTED),)

    outcome = classify_legacy_position(pos, stage_end_reached=True)
    assert outcome.lifecycle == LIFECYCLE_CLOSED
    assert outcome.evaluability == EVALUABILITY_EVALUABLE
    (net_return,) = evaluate_legacy_stage_results([pos], [outcome], _ZERO_COSTS, D6, result.final_closes)
    assert net_return == tranche_net_return("LONG", 100.0, 110.0, 0.0, 0.0, 0.0, 2)
    assert net_return == 0.10


def test_time_exit_of_one_bar_closes_on_the_entry_days_own_close(conn, now):
    """Edge case at the formula's own boundary: "holding bar 1 = entry bar
    itself" -- time_exit_bars=1 must exit the SAME session it enters,
    never deferred by even one session."""
    sec = make_security(conn, "spec005:LEGACY_TE_ONE_BAR", now)
    _insert_bars(conn, sec, now, [
        (D1, 100.0, 101.0, 99.0, 100.0),
        (D2, 100.0, 106.0, 99.0, 103.0),  # entry AND exit, same session
        (D3, 103.0, 104.0, 102.0, 103.0),
    ])
    registry = HypothesisRegistry()
    hid, vid = build_registered_time_exit_hypothesis(registry, time_exit_bars=1, signature_id="SIG_LEGACY_TE_ONEBAR")
    signal = EntrySignal(security_id=sec, strategy_variant_id=vid)
    engine = LegacySessionEngine(
        pit=_UnboundedAccess(conn), session_dates=(D1, D2, D3), registry=registry,
        accepted_hypothesis_ids=frozenset({hid}), entry_signals={(sec, vid, D1): signal},
        invalidation_observer=_never_invalidated, cost_assumptions=_ZERO_COSTS,
    )
    result = engine.run()
    pos = result.positions[0]
    assert pos.entry_date == D2
    assert pos.close_tranche.exit_date == D2  # same session, never deferred
    assert pos.close_tranche.exit_fill_price == 103.0  # D2's own close
    assert pos.close_tranche.holding_days == 0


def test_time_exit_applies_entry_and_exit_slippage(conn, now):
    sec = make_security(conn, "spec005:LEGACY_TE_SLIP", now)
    _insert_bars(conn, sec, now, [
        (D1, 100.0, 101.0, 99.0, 100.0),
        (D2, 100.0, 101.0, 99.0, 100.0),
        (D3, 100.0, 106.0, 99.0, 105.0),
        (D4, 105.0, 111.0, 104.0, 110.0),
    ])
    costs = CostAssumptions(
        commission_entry_rate=0.001, commission_exit_rate=0.002,
        slippage_entry_bps=200.0, slippage_exit_bps=150.0, borrow_annual_rate=0.0,
    )
    registry = HypothesisRegistry()
    hid, vid = build_registered_time_exit_hypothesis(registry, time_exit_bars=3, signature_id="SIG_LEGACY_TE_SLIP")
    signal = EntrySignal(security_id=sec, strategy_variant_id=vid)
    engine = LegacySessionEngine(
        pit=_UnboundedAccess(conn), session_dates=(D1, D2, D3, D4), registry=registry,
        accepted_hypothesis_ids=frozenset({hid}), entry_signals={(sec, vid, D1): signal},
        invalidation_observer=_never_invalidated, cost_assumptions=costs,
    )
    result = engine.run()
    pos = result.positions[0]
    assert pos.entry_fill_price == apply_entry_slippage("LONG", 100.0, 0.02)
    assert pos.entry_fill_price == 102.0

    outcome = classify_legacy_position(pos, stage_end_reached=True)
    (net_return,) = evaluate_legacy_stage_results([pos], [outcome], costs, D4, result.final_closes)
    expected_f_x = apply_exit_slippage("LONG", 110.0, EXIT_REASON_TIME_EXIT, slippage_exit_rate=0.015)
    expected_return = tranche_net_return("LONG", 102.0, expected_f_x, 0.001, 0.002, 0.0, 2)
    assert net_return == expected_return


def test_time_exit_due_on_a_missing_bar_is_exit_failed(conn, now):
    sec = make_security(conn, "spec005:LEGACY_TE_NOEXITBAR", now)
    _insert_bars(conn, sec, now, [
        (D1, 100.0, 101.0, 99.0, 100.0),
        (D2, 100.0, 101.0, 99.0, 100.0),
        (D3, 100.0, 106.0, 99.0, 105.0),
        # D4 (the due exit day) has no bar at all.
        (D5, 110.0, 111.0, 109.0, 110.0),
    ])
    registry = HypothesisRegistry()
    hid, vid = build_registered_time_exit_hypothesis(registry, time_exit_bars=3, signature_id="SIG_LEGACY_TE_NOEXIT")
    signal = EntrySignal(security_id=sec, strategy_variant_id=vid)
    engine = LegacySessionEngine(
        pit=_UnboundedAccess(conn), session_dates=(D1, D2, D3, D4, D5), registry=registry,
        accepted_hypothesis_ids=frozenset({hid}), entry_signals={(sec, vid, D1): signal},
        invalidation_observer=_never_invalidated, cost_assumptions=_ZERO_COSTS,
    )
    result = engine.run()
    pos = result.positions[0]
    assert pos.exit_failed is True
    assert pos.exit_failed_reason == REASON_NO_EXIT_BAR
    outcome = classify_legacy_position(pos, stage_end_reached=True)
    assert outcome.lifecycle == LIFECYCLE_EXIT_FAILED
    assert outcome.evaluability == EVALUABILITY_UNEVALUABLE


def test_time_exit_still_short_of_its_bar_count_is_censored_at_horizon(conn, now):
    sec = make_security(conn, "spec005:LEGACY_TE_CENSORED", now)
    _insert_bars(conn, sec, now, [
        (D1, 100.0, 101.0, 99.0, 100.0),
        (D2, 100.0, 101.0, 99.0, 100.0),
        (D3, 100.0, 106.0, 99.0, 105.0),
    ])
    registry = HypothesisRegistry()
    hid, vid = build_registered_time_exit_hypothesis(registry, time_exit_bars=10, signature_id="SIG_LEGACY_TE_CENSORED")
    signal = EntrySignal(security_id=sec, strategy_variant_id=vid)
    engine = LegacySessionEngine(
        pit=_UnboundedAccess(conn), session_dates=(D1, D2, D3), registry=registry,
        accepted_hypothesis_ids=frozenset({hid}), entry_signals={(sec, vid, D1): signal},
        invalidation_observer=_never_invalidated, cost_assumptions=_ZERO_COSTS,
    )
    result = engine.run()
    pos = result.positions[0]
    assert pos.closed is False
    outcome = classify_legacy_position(pos, stage_end_reached=True, final_mark_available=result.final_closes.get(sec) is not None)
    assert outcome.lifecycle == LIFECYCLE_CENSORED_AT_HORIZON
    assert outcome.evaluability == EVALUABILITY_EVALUABLE
    (net_return,) = evaluate_legacy_stage_results([pos], [outcome], _ZERO_COSTS, D3, result.final_closes)
    assert net_return == (105.0 - 100.0) / 100.0  # open_remainder_net_return, zero costs


# -- SIGNAL_INVALIDATION mechanics (real conn) --------------------------

def test_signal_invalidation_closes_at_close_when_invalidated_before_the_time_cap(conn, now):
    sec = make_security(conn, "spec005:LEGACY_SIGINV", now)
    _insert_bars(conn, sec, now, [
        (D1, 100.0, 101.0, 99.0, 100.0),
        (D2, 100.0, 101.0, 99.0, 100.0),  # entry day
        (D3, 100.0, 106.0, 99.0, 105.0),  # invalidated here -- exits at THIS close
        (D4, 105.0, 111.0, 104.0, 110.0),
    ])
    registry = HypothesisRegistry()
    hid, vid = build_registered_signal_invalidation_hypothesis(registry, max_holding_bars=5, signature_id="SIG_LEGACY_INV_1")
    signal = EntrySignal(security_id=sec, strategy_variant_id=vid)

    def observer(position, session_date):
        return "INVALIDATED" if session_date == D3 else "VALID_HOLD"

    engine = LegacySessionEngine(
        pit=_UnboundedAccess(conn), session_dates=(D1, D2, D3, D4), registry=registry,
        accepted_hypothesis_ids=frozenset({hid}), entry_signals={(sec, vid, D1): signal},
        invalidation_observer=observer, cost_assumptions=_ZERO_COSTS,
    )
    result = engine.run()
    pos = result.positions[0]
    assert pos.closed is True
    assert pos.close_tranche.exit_reason == EXIT_REASON_SIGNAL_INVALIDATION
    assert pos.close_tranche.exit_date == D3
    assert pos.close_tranche.exit_fill_price == 105.0
    assert pos.invalidation_path_incomplete is False


def test_signal_invalidation_forces_exit_at_the_time_cap_when_never_invalidated(conn, now):
    sec = make_security(conn, "spec005:LEGACY_SIGINV_CAP", now)
    _insert_bars(conn, sec, now, [
        (D1, 100.0, 101.0, 99.0, 100.0),
        (D2, 100.0, 101.0, 99.0, 100.0),  # entry day (holding bar 1)
        (D3, 100.0, 106.0, 99.0, 105.0),  # holding bar 2
        (D4, 105.0, 111.0, 104.0, 110.0),  # holding bar 3 = max_holding_bars -- forced exit
    ])
    registry = HypothesisRegistry()
    hid, vid = build_registered_signal_invalidation_hypothesis(registry, max_holding_bars=3, signature_id="SIG_LEGACY_INV_CAP")
    signal = EntrySignal(security_id=sec, strategy_variant_id=vid)
    engine = LegacySessionEngine(
        pit=_UnboundedAccess(conn), session_dates=(D1, D2, D3, D4), registry=registry,
        accepted_hypothesis_ids=frozenset({hid}), entry_signals={(sec, vid, D1): signal},
        invalidation_observer=_never_invalidated, cost_assumptions=_ZERO_COSTS,
    )
    result = engine.run()
    pos = result.positions[0]
    assert pos.closed is True
    assert pos.close_tranche.exit_reason == EXIT_REASON_MAX_HOLDING_BARS_FORCED_EXIT
    assert pos.close_tranche.exit_date == D4
    assert pos.close_tranche.exit_fill_price == 110.0


def test_signal_invalidation_and_time_cap_on_the_same_session_prefers_invalidation():
    """Explicit, documented tie-break (never given verbatim by any spec
    text for this exact simultaneity): the protective/risk-side signal
    wins, mirroring `advance_intrabar()`'s own stop-over-target precedent."""
    position = LegacyPosition(
        security_id="SEC_TIE", strategy_variant_id="V1", exit_family="SIGNAL_INVALIDATION",
        direction="LONG", signal_date=D1, entry_date=D2, entry_session_index=1, entry_fill_price=100.0,
        max_holding_bars=3,
    )
    new_pos = advance_legacy_position_at_close(position, D4, session_index=3, close_price=110.0, invalidation_status="INVALIDATED")
    assert new_pos.closed is True
    assert new_pos.close_tranche.exit_reason == EXIT_REASON_SIGNAL_INVALIDATION
    assert new_pos.close_tranche.exit_reason != EXIT_REASON_MAX_HOLDING_BARS_FORCED_EXIT


def test_unknown_invalidation_status_taints_the_position_permanently(conn, now):
    sec = make_security(conn, "spec005:LEGACY_SIGINV_UNKNOWN", now)
    _insert_bars(conn, sec, now, [
        (D1, 100.0, 101.0, 99.0, 100.0),
        (D2, 100.0, 101.0, 99.0, 100.0),  # entry, holding bar 1
        (D3, 100.0, 106.0, 99.0, 105.0),  # UNKNOWN here -- permanent taint
        (D4, 105.0, 111.0, 104.0, 110.0),  # holding bar 3 -- back to VALID_HOLD, forced exit by cap
    ])
    registry = HypothesisRegistry()
    hid, vid = build_registered_signal_invalidation_hypothesis(registry, max_holding_bars=3, signature_id="SIG_LEGACY_INV_UNKNOWN")
    signal = EntrySignal(security_id=sec, strategy_variant_id=vid)

    def observer(position, session_date):
        return "UNKNOWN" if session_date == D3 else "VALID_HOLD"

    engine = LegacySessionEngine(
        pit=_UnboundedAccess(conn), session_dates=(D1, D2, D3, D4), registry=registry,
        accepted_hypothesis_ids=frozenset({hid}), entry_signals={(sec, vid, D1): signal},
        invalidation_observer=observer, cost_assumptions=_ZERO_COSTS,
    )
    result = engine.run()
    pos = result.positions[0]
    # Closed cleanly by the time cap at D4 -- but the D3 UNKNOWN must
    # still be visible: a real fill on file does not erase the fact that
    # the holding condition's own path was not fully demonstrated.
    assert pos.closed is True
    assert pos.invalidation_path_incomplete is True
    outcome = classify_legacy_position(pos, stage_end_reached=True)
    assert outcome.lifecycle == LIFECYCLE_CLOSED
    assert outcome.evaluability == EVALUABILITY_UNEVALUABLE
    assert outcome.reason == REASON_INVALIDATION_PATH_INCOMPLETE


# -- Pas 0 split reconciliation (independent reimplementation) ----------

def _insert_flat_bars(conn, security_id, now, dates, price=100.0):
    repo.insert_price_bars(conn, [
        PriceBar(
            security_id=security_id, date=d, raw_open=price, raw_high=price + 1, raw_low=price - 1,
            raw_close=price, raw_volume=1000, source_provider="manual", ingestion_timestamp=now,
        )
        for d in dates
    ])


def _legacy_position(entry_date="2024-01-11", **overrides) -> LegacyPosition:
    fields = dict(
        security_id="SEC_X", strategy_variant_id="V1", exit_family="TIME_EXIT", direction="LONG",
        signal_date="2024-01-10", entry_date=entry_date, entry_session_index=0, entry_fill_price=100.0,
        time_exit_bars=10,
    )
    fields.update(overrides)
    return LegacyPosition(**fields)


def test_ontime_split_reconciliation_rescales_entry_fill_price_and_is_not_flagged(conn, now):
    sec = make_security(conn, "spec005:LEGACY_SPLIT_ONTIME", now)
    _insert_flat_bars(conn, sec, now, ["2024-01-11", "2024-01-20"])
    insert_corporate_action(conn, sec, "act_ontime", "SPLIT", effective_date="2024-01-20", value=2.0, now=now, available_at="2024-01-20")
    pos = _legacy_position(security_id=sec)
    pit = _UnboundedAccess(conn)

    new_pos = reconcile_split_for_legacy_position(pit, pos, "2024-01-20", same_day_evidence=frozenset({"act_ontime"}))
    assert new_pos.split_reconciliation_incomplete is False
    assert new_pos.entry_fill_price == 50.0
    assert new_pos.applied_factor == 0.5
    assert "act_ontime" in new_pos.processed_split_action_ids


def test_late_split_reconciliation_still_rescales_but_is_flagged_incomplete(conn, now):
    sec = make_security(conn, "spec005:LEGACY_SPLIT_LATE", now)
    _insert_flat_bars(conn, sec, now, ["2024-01-11", "2024-01-25"])
    insert_corporate_action(conn, sec, "act_late", "SPLIT", effective_date="2024-01-15", value=2.0, now=now, available_at="2024-01-15")
    pos = _legacy_position(security_id=sec)
    pit = _UnboundedAccess(conn)

    new_pos = reconcile_split_for_legacy_position(pit, pos, "2024-01-25")
    assert new_pos.entry_fill_price == 50.0  # still correctly caught up
    assert new_pos.applied_factor == 0.5
    assert new_pos.split_reconciliation_incomplete is True


def test_split_effective_before_entry_is_never_pas0s_concern(conn, now):
    sec = make_security(conn, "spec005:LEGACY_SPLIT_PREENTRY", now)
    _insert_flat_bars(conn, sec, now, ["2024-01-11", "2024-01-15"])
    insert_corporate_action(conn, sec, "act_preentry", "SPLIT", effective_date="2024-01-09", value=2.0, now=now, available_at="2024-01-09")
    pos = _legacy_position(security_id=sec, entry_date="2024-01-11")
    pit = _UnboundedAccess(conn)

    new_pos = reconcile_split_for_legacy_position(pit, pos, "2024-01-15")
    assert new_pos == pos  # completely untouched -- already reflected at entry


def test_closed_position_is_never_touched_by_reconciliation(conn, now):
    sec = make_security(conn, "spec005:LEGACY_SPLIT_CLOSED", now)
    _insert_flat_bars(conn, sec, now, ["2024-01-11", "2024-01-20"])
    insert_corporate_action(conn, sec, "act_c", "SPLIT", effective_date="2024-01-15", value=2.0, now=now, available_at="2024-01-15")
    from backtest.exits.entities import Tranche
    closed_tranche = Tranche(
        kind="REMAINDER", exit_reason="TIME_EXIT", fraction_of_original=1.0,
        exit_date="2024-01-12", exit_fill_price=110.0, holding_days=1, entry_fill_price_reference=100.0,
    )
    pos = _legacy_position(security_id=sec, closed=True, close_tranche=closed_tranche)
    pit = _UnboundedAccess(conn)

    new_pos = reconcile_split_for_legacy_position(pit, pos, "2024-01-20")
    assert new_pos == pos


# -- Variant-keyed bookkeeping -------------------------------------------

def test_two_variants_on_the_same_security_same_day_both_open_independent_positions(conn, now):
    sec = make_security(conn, "spec005:LEGACY_TWO_VARIANTS", now)
    _insert_bars(conn, sec, now, [
        (D1, 100.0, 101.0, 99.0, 100.0),
        (D2, 100.0, 101.0, 99.0, 100.0),
        (D3, 100.0, 106.0, 99.0, 105.0),
        (D4, 105.0, 111.0, 104.0, 110.0),
    ])
    registry = HypothesisRegistry()
    hid_a, vid_a = build_registered_time_exit_hypothesis(registry, time_exit_bars=2, signature_id="SIG_LEGACY_TWOVAR_A")
    hid_b, vid_b = build_registered_time_exit_hypothesis(registry, time_exit_bars=3, signature_id="SIG_LEGACY_TWOVAR_B")
    entry_signals = {
        (sec, vid_a, D1): EntrySignal(security_id=sec, strategy_variant_id=vid_a),
        (sec, vid_b, D1): EntrySignal(security_id=sec, strategy_variant_id=vid_b),
    }
    engine = LegacySessionEngine(
        pit=_UnboundedAccess(conn), session_dates=(D1, D2, D3, D4), registry=registry,
        accepted_hypothesis_ids=frozenset({hid_a, hid_b}), entry_signals=entry_signals,
        invalidation_observer=_never_invalidated, cost_assumptions=_ZERO_COSTS,
    )
    result = engine.run()
    assert len(result.positions) == 2
    by_variant = {p.strategy_variant_id: p for p in result.positions}
    assert by_variant[vid_a].close_tranche.exit_date == D3  # time_exit_bars=2 -> holding bar 2 = D3
    assert by_variant[vid_b].close_tranche.exit_date == D4  # time_exit_bars=3 -> holding bar 3 = D4


# -- classify_legacy_position() priority ---------------------------------

def test_split_reconciliation_incomplete_outranks_invalidation_incomplete():
    pos = LegacyPosition(
        security_id="S", strategy_variant_id="V", exit_family="SIGNAL_INVALIDATION", direction="LONG",
        signal_date=D1, entry_date=D2, entry_session_index=1, entry_fill_price=100.0, max_holding_bars=5,
        closed=True, split_reconciliation_incomplete=True, invalidation_path_incomplete=True,
    )
    outcome = classify_legacy_position(pos, stage_end_reached=True)
    assert outcome.reason == REASON_SPLIT_RECONCILIATION_INCOMPLETE
