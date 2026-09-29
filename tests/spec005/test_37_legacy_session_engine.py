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

from discovery.models.entities import DescriptiveMetrics, DiscoveryObservation

from hypothesis.models.entities import InvalidationCondition
from hypothesis.registry.hypotheses import HypothesisRegistry

from backtest.exits.costs import apply_entry_slippage, apply_exit_slippage, tranche_net_return
from backtest.exits.discovery_integration import build_invalidation_observer
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


def test_advance_legacy_position_at_close_rejects_non_finite_or_non_positive_close_prices():
    """GPT review finding #4: `advance_legacy_position_at_close()` used to
    reject only `close_price is None` -- NaN, +/-inf, zero, and negative
    all passed straight through into a CLOSED/EVALUABLE tranche. Every
    one of those is exactly as unusable as a missing bar for the exit
    that was actually due."""
    base = LegacyPosition(
        security_id="S", strategy_variant_id="V", exit_family="TIME_EXIT", direction="LONG",
        signal_date=D1, entry_date=D2, entry_session_index=1, entry_fill_price=100.0, time_exit_bars=1,
    )
    for bad_price in (float("nan"), float("inf"), float("-inf"), 0.0, -1.0):
        new_pos = advance_legacy_position_at_close(base, D2, session_index=1, close_price=bad_price, invalidation_status=None)
        assert new_pos.exit_failed is True, f"price {bad_price!r} was wrongly accepted as a usable exit fill"
        assert new_pos.exit_failed_reason == REASON_NO_EXIT_BAR
        assert new_pos.closed is False


def test_entry_with_non_finite_or_non_positive_open_is_rejected_as_no_entry_bar(conn, now):
    sec = make_security(conn, "spec005:LEGACY_BAD_ENTRY_PRICE", now)
    _insert_bars(conn, sec, now, [
        (D1, 100.0, 101.0, 99.0, 100.0),
        (D2, float("nan"), 101.0, 99.0, 100.0),  # entry day's own open is NaN
        (D3, 100.0, 106.0, 99.0, 105.0),
    ])
    registry = HypothesisRegistry()
    hid, vid = build_registered_time_exit_hypothesis(registry, time_exit_bars=3, signature_id="SIG_LEGACY_BAD_ENTRY")
    signal = EntrySignal(security_id=sec, strategy_variant_id=vid)
    engine = LegacySessionEngine(
        pit=_UnboundedAccess(conn), session_dates=(D1, D2, D3), registry=registry,
        accepted_hypothesis_ids=frozenset({hid}), entry_signals={(sec, vid, D1): signal},
        invalidation_observer=_never_invalidated, cost_assumptions=_ZERO_COSTS,
    )
    result = engine.run()
    assert result.positions == ()
    assert result.entry_dispositions == (EntryDisposition(sec, vid, D1, D2, ENTRY_NO_ENTRY_BAR),)


def test_final_close_with_a_non_finite_price_is_never_used_as_the_censored_mark(conn, now):
    """The engine's own `_last_close_observation` recording must never
    accept a NaN/infinite/zero/negative close as a usable final mark --
    treated exactly like a missing bar, so `final_closes[security_id]`
    comes back `None` (never the corrupted value) and classification
    correctly reports CENSORED_MARK_UNAVAILABLE."""
    sec = make_security(conn, "spec005:LEGACY_BAD_FINAL_MARK", now)
    _insert_bars(conn, sec, now, [
        (D1, 100.0, 101.0, 99.0, 100.0),
        (D2, 100.0, 101.0, 99.0, 100.0),
        (D3, 100.0, 106.0, 99.0, float("nan")),  # stage's own last close is corrupted
    ])
    registry = HypothesisRegistry()
    hid, vid = build_registered_time_exit_hypothesis(registry, time_exit_bars=10, signature_id="SIG_LEGACY_BAD_FINALMARK")
    signal = EntrySignal(security_id=sec, strategy_variant_id=vid)
    engine = LegacySessionEngine(
        pit=_UnboundedAccess(conn), session_dates=(D1, D2, D3), registry=registry,
        accepted_hypothesis_ids=frozenset({hid}), entry_signals={(sec, vid, D1): signal},
        invalidation_observer=_never_invalidated, cost_assumptions=_ZERO_COSTS,
    )
    result = engine.run()
    pos = result.positions[0]
    assert pos.closed is False
    assert result.final_closes.get(sec) is None
    outcome = classify_legacy_position(pos, stage_end_reached=True, final_mark_available=result.final_closes.get(sec) is not None)
    assert outcome.lifecycle == LIFECYCLE_CENSORED_AT_HORIZON
    assert outcome.evaluability == EVALUABILITY_UNEVALUABLE


def test_evaluate_legacy_stage_results_rejects_a_non_usable_final_mark():
    pos = LegacyPosition(
        security_id="S", strategy_variant_id="V", exit_family="TIME_EXIT", direction="LONG",
        signal_date=D1, entry_date=D2, entry_session_index=1, entry_fill_price=100.0, time_exit_bars=10,
    )
    outcome = classify_legacy_position(pos, stage_end_reached=True, final_mark_available=True)
    for bad_mark in (float("nan"), float("inf"), 0.0, -5.0):
        try:
            evaluate_legacy_stage_results([pos], [outcome], _ZERO_COSTS, D3, {"S": bad_mark})
            assert False, f"expected ValueError for final mark {bad_mark!r}"
        except ValueError as e:
            assert "final_closes" in str(e)


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

def test_signal_invalidation_detected_at_close_executes_at_the_next_sessions_open(conn, now):
    """Closure verification fix (post-9feb4a5): `ExecutionSemanticsProfile`
    v1 (SS9) separates `invalidation_detection=COMPLETED_BAR_CLOSE` from
    `invalidation_fill=NEXT_SESSION_OPEN_AFTER_DETECTION` -- an EARLIER
    version of this engine wrongly closed at the SAME close the
    invalidation was detected. D4's own open (107.0) deliberately differs
    from D3's close (105.0) so this test cannot pass by accident under the
    old, buggy same-close behavior."""
    sec = make_security(conn, "spec005:LEGACY_SIGINV", now)
    _insert_bars(conn, sec, now, [
        (D1, 100.0, 101.0, 99.0, 100.0),
        (D2, 100.0, 101.0, 99.0, 100.0),  # entry day
        (D3, 100.0, 106.0, 99.0, 105.0),  # invalidated HERE (detection) -- does not exit yet
        (D4, 107.0, 111.0, 104.0, 110.0),  # scheduled fill: open(D4) = 107.0, not close(D3) = 105.0
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
    assert pos.close_tranche.exit_date == D4
    assert pos.close_tranche.exit_fill_price == 107.0
    assert pos.invalidation_path_incomplete is False
    assert pos.pending_invalidation_detected_date is None  # consumed, not left dangling


def test_signal_invalidation_execution_uses_the_real_overnight_gap_not_the_detection_close(conn, now):
    """The economically material case: a detection close that LOOKS
    profitable is never the executed fill if the next session's open gaps
    hard against it. Entry 100 -> detection close ~130 (+30% if wrongly
    executed there, the old bug) -> next open ~90 (-10% from entry,
    correctly executed there) -- the exact numbers this finding was
    reported with."""
    sec = make_security(conn, "spec005:LEGACY_SIGINV_GAP", now)
    _insert_bars(conn, sec, now, [
        (D1, 100.0, 101.0, 99.0, 100.0),
        (D2, 100.0, 101.0, 99.0, 100.0),  # entry day, F_e = 100.0
        (D3, 100.0, 132.0, 99.0, 130.0),  # invalidated HERE at close=130.0 (would be +30% if executed here)
        (D4, 90.0, 92.0, 88.0, 91.0),     # real overnight gap down: open(D4) = 90.0 (-10% from entry)
    ])
    registry = HypothesisRegistry()
    hid, vid = build_registered_signal_invalidation_hypothesis(registry, max_holding_bars=10, signature_id="SIG_LEGACY_INV_GAP")
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
    assert pos.close_tranche.exit_date == D4
    assert pos.close_tranche.exit_fill_price == 90.0  # NOT 130.0 -- the detection close is never the fill
    outcome = classify_legacy_position(pos, stage_end_reached=True)
    (net_return,) = evaluate_legacy_stage_results([pos], [outcome], _ZERO_COSTS, D4, result.final_closes)
    assert abs(net_return - (-0.10)) < 1e-9  # -10%, not the +30% the old same-close bug would have reported


def test_signal_invalidation_scheduled_fill_fails_when_the_next_open_is_missing(conn, now):
    """`execute_scheduled_legacy_invalidation()`'s own EXIT_FAILED path: a
    detected invalidation due today (there IS a next session in
    `session_dates`) with no usable open bar on it is a failed execution,
    never silently dropped or deferred further."""
    sec = make_security(conn, "spec005:LEGACY_SIGINV_NOBAR", now)
    _insert_bars(conn, sec, now, [
        (D1, 100.0, 101.0, 99.0, 100.0),
        (D2, 100.0, 101.0, 99.0, 100.0),  # entry day
        (D3, 100.0, 106.0, 99.0, 105.0),  # invalidated here
        # D4: no bar at all -- the scheduled fill session has nothing to read.
    ])
    registry = HypothesisRegistry()
    hid, vid = build_registered_signal_invalidation_hypothesis(registry, max_holding_bars=10, signature_id="SIG_LEGACY_INV_NOBAR")
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
    assert pos.closed is False
    assert pos.exit_failed is True
    assert pos.exit_failed_reason == REASON_NO_EXIT_BAR
    outcome = classify_legacy_position(pos, stage_end_reached=True)
    assert outcome.lifecycle == LIFECYCLE_EXIT_FAILED
    assert outcome.evaluability == EVALUABILITY_UNEVALUABLE


def test_signal_invalidation_detected_on_the_stages_last_session_stays_censored_at_horizon(conn, now):
    """Amendment section 10's CENSORED_AT_HORIZON central case (regression
    #9), reused for this family: an invalidation detected at the STAGE's
    own last close has no room left in `session_dates` for its scheduled
    NEXT_SESSION_OPEN_AFTER_DETECTION fill -- it must stay
    CENSORED_AT_HORIZON, EVALUABLE (using the last close as the mark),
    never EXIT_FAILED, with the pending order recorded as a diagnostic
    note only."""
    sec = make_security(conn, "spec005:LEGACY_SIGINV_LASTCLOSE", now)
    _insert_bars(conn, sec, now, [
        (D1, 100.0, 101.0, 99.0, 100.0),
        (D2, 100.0, 101.0, 99.0, 100.0),  # entry day
        (D3, 100.0, 106.0, 99.0, 105.0),  # invalidated on the STAGE's own last session
    ])
    registry = HypothesisRegistry()
    hid, vid = build_registered_signal_invalidation_hypothesis(registry, max_holding_bars=10, signature_id="SIG_LEGACY_INV_LASTCLOSE")
    signal = EntrySignal(security_id=sec, strategy_variant_id=vid)

    def observer(position, session_date):
        return "INVALIDATED" if session_date == D3 else "VALID_HOLD"

    engine = LegacySessionEngine(
        pit=_UnboundedAccess(conn), session_dates=(D1, D2, D3), registry=registry,
        accepted_hypothesis_ids=frozenset({hid}), entry_signals={(sec, vid, D1): signal},
        invalidation_observer=observer, cost_assumptions=_ZERO_COSTS,
    )
    result = engine.run()
    pos = result.positions[0]
    assert pos.closed is False
    assert pos.exit_failed is False
    assert pos.pending_invalidation_detected_date == D3
    assert pos.pending_exit_note is not None and "beyond this stage" in pos.pending_exit_note
    outcome = classify_legacy_position(pos, stage_end_reached=True, final_mark_available=result.final_closes.get(sec) is not None)
    assert outcome.lifecycle == LIFECYCLE_CENSORED_AT_HORIZON
    assert outcome.evaluability == EVALUABILITY_EVALUABLE  # last close (105.0) is a usable mark
    (net_return,) = evaluate_legacy_stage_results([pos], [outcome], _ZERO_COSTS, D3, result.final_closes)
    assert net_return == (105.0 - 100.0) / 100.0  # open_remainder_net_return off the last close, zero costs


def test_signal_invalidation_pending_fill_executes_before_the_next_sessions_own_cap_check(conn, now):
    """Interaction with the cap: an invalidation detected at close(t),
    scheduled for open(t+1), must be EXECUTED at that open (Pas 1) BEFORE
    session t+1's own close-based cap check ever runs -- the position is
    already retired by the time Pas 3'/5 would evaluate the cap for that
    session, so it closes via the SCHEDULED INVALIDATION, never the cap,
    even though the cap's own bar count would ALSO have been reached that
    same session had the position still been open."""
    sec = make_security(conn, "spec005:LEGACY_SIGINV_VS_CAP", now)
    _insert_bars(conn, sec, now, [
        (D1, 100.0, 101.0, 99.0, 100.0),
        (D2, 100.0, 101.0, 99.0, 100.0),  # entry day, holding bar 1
        (D3, 100.0, 106.0, 99.0, 105.0),  # holding bar 2 -- invalidated HERE
        (D4, 95.0, 96.0, 90.0, 91.0),     # holding bar 3 == max_holding_bars -- but the pending fill wins
    ])
    registry = HypothesisRegistry()
    hid, vid = build_registered_signal_invalidation_hypothesis(registry, max_holding_bars=3, signature_id="SIG_LEGACY_INV_VS_CAP")
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
    assert pos.close_tranche.exit_reason != EXIT_REASON_MAX_HOLDING_BARS_FORCED_EXIT
    assert pos.close_tranche.exit_date == D4
    assert pos.close_tranche.exit_fill_price == 95.0  # D4's OPEN, the scheduled fill -- not D4's close (91.0)


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


def test_signal_invalidation_and_time_cap_on_the_same_session_the_cap_wins_and_closes_now():
    """Closure verification fix (post-9feb4a5): the PREVIOUS version of
    this test asserted the opposite (invalidation wins) under the old,
    incorrect same-close-execution model, where both looked like competing
    IMMEDIATE fills. Under the corrected model the cap is a hard,
    immediate-close backstop (`CAP_IS_HARD_V1`) while invalidation is a
    SCHEDULED exit (SS9's `NEXT_SESSION_OPEN_AFTER_DETECTION`) -- so a
    genuine same-session coincidence is never a tie: the cap closes NOW,
    the invalidation detection this same session has nothing left to
    schedule a fill against (mirrors amendment regression #11's own
    principle: a position fully resolved by one mechanism this session
    skips any other evaluation `for that day`)."""
    position = LegacyPosition(
        security_id="SEC_TIE", strategy_variant_id="V1", exit_family="SIGNAL_INVALIDATION",
        direction="LONG", signal_date=D1, entry_date=D2, entry_session_index=1, entry_fill_price=100.0,
        max_holding_bars=3,
    )
    new_pos = advance_legacy_position_at_close(position, D4, session_index=3, close_price=110.0, invalidation_status="INVALIDATED")
    assert new_pos.closed is True
    assert new_pos.close_tranche.exit_reason == EXIT_REASON_MAX_HOLDING_BARS_FORCED_EXIT
    assert new_pos.close_tranche.exit_reason != EXIT_REASON_SIGNAL_INVALIDATION
    assert new_pos.close_tranche.exit_date == D4
    assert new_pos.close_tranche.exit_fill_price == 110.0
    assert new_pos.pending_invalidation_detected_date is None  # never scheduled -- the cap already closed it


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


def _obs(security_id: str, as_of: str, lane_states: dict) -> DiscoveryObservation:
    return DiscoveryObservation(
        security_id=security_id, ticker_as_of=security_id, as_of=as_of, timeframe="1D",
        feature_vector={}, normalized_feature_vector={}, state_signature=lane_states,
        transition_vector={}, active_lanes=list(lane_states.keys()),
        descriptive_metrics=DescriptiveMetrics(extremeness=0.0, persistence=1, state_frequency=None, sample_count=1, support_status="SUFFICIENT"),
        reason_codes=[], config_version="cfg_test", feature_engine_version="v1.0.0", discovery_engine_version="v1.0.0",
    )


def test_a_missing_lane_from_a_real_discovery_observer_taints_the_engine_permanently(conn, now):
    """GPT review finding #1, exercised end to end through the REAL
    `discovery_integration.build_invalidation_observer()` wired into
    `LegacySessionEngine` (not a hand-typed 'UNKNOWN' stub): a session
    whose observation exists but is simply missing the tracked lane
    entirely (a real Discovery data gap, not a hand-typed sentinel) must
    still taint `invalidation_path_incomplete` permanently -- surviving
    even a later, clean session where the lane reappears within
    `holds_labels`."""
    sec = make_security(conn, "spec005:LEGACY_REAL_UNKNOWN", now)
    _insert_bars(conn, sec, now, [
        (D1, 100.0, 101.0, 99.0, 100.0),
        (D2, 100.0, 101.0, 99.0, 100.0),  # entry, holding bar 1 -- momentum=HIGH
        (D3, 100.0, 106.0, 99.0, 105.0),  # holding bar 2 -- "momentum" absent entirely from the observation
        (D4, 105.0, 111.0, 104.0, 110.0),  # holding bar 3 = max_holding_bars -- momentum=HIGH again, forced exit
    ])
    registry = HypothesisRegistry()
    hid, vid = build_registered_signal_invalidation_hypothesis(
        registry, max_holding_bars=3, signature_id="SIG_LEGACY_REAL_UNKNOWN",
        invalidation_conditions=(InvalidationCondition(lane="momentum", holds_labels=("HIGH",)),),
    )
    signal = EntrySignal(security_id=sec, strategy_variant_id=vid)
    observations_by_session = {
        D2: {sec: _obs(sec, D2, {"momentum": "HIGH"})},
        D3: {sec: _obs(sec, D3, {})},  # "momentum" missing entirely -- a real data gap
        D4: {sec: _obs(sec, D4, {"momentum": "HIGH"})},
    }
    observer = build_invalidation_observer(observations_by_session, registry)
    engine = LegacySessionEngine(
        pit=_UnboundedAccess(conn), session_dates=(D1, D2, D3, D4), registry=registry,
        accepted_hypothesis_ids=frozenset({hid}), entry_signals={(sec, vid, D1): signal},
        invalidation_observer=observer, cost_assumptions=_ZERO_COSTS,
    )
    result = engine.run()
    pos = result.positions[0]
    assert pos.closed is True  # forced exit by the time cap, never a false INVALIDATED from the gap
    assert pos.close_tranche.exit_reason == EXIT_REASON_MAX_HOLDING_BARS_FORCED_EXIT
    assert pos.invalidation_path_incomplete is True
    outcome = classify_legacy_position(pos, stage_end_reached=True)
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
