"""TEST 34 -- the integrated Pas 0-6 session order (docs/
spec005_exit_amendment_v1.0.md, ACCEPTED, section 5), across a real
2-security PIT universe, through `SessionEngine` end to end, including
stage-boundary censoring and aggregate net_return (section 9, WITH the
exit-side slippage formula, section 9/"amendament §13").

This is deliberately NOT a hand-derivation of every number from scratch:
ATR-driven trailing-stop drift (sections 3/6) is already exhaustively
covered, numerically, by tests/spec005/test_21 through test_25. What this
test proves is that the SESSION LOOP wires those already-correct
mechanisms together in the right order and that `evaluate_stage_results()`
correctly reads EACH position's own recorded facts (not a stale/aliased
field) when computing its aggregate return. Where a value depends on
ATR drift (SEC_A's stop level), the expected return is computed in this
test from the tranche's OWN actual recorded fields via the same,
independently-tested cost primitives (`apply_exit_slippage`,
`tranche_net_return`) `evaluate_stage_results()` itself uses -- proving
the wiring, not re-deriving Wilder's ATR by hand. Where a value does NOT
depend on ATR at all (SEC_B's still-open remainder -- `open_remainder_
net_return()` needs no ATR/stop path whatsoever), the full number is
hand-verified directly, plainly, in the test.

Scenario:
  SEC_A: entry with partial_profit -- target hit at open (Pas 3'b),
         THEN a 2-for-1 split reconciled at Pas 0, THEN the remainder
         stopped out intraday (Pas 3'c) -- CLOSED, EVALUABLE.
  SEC_B: entry, Control variant (no partial_profit) -- trend invalidation
         detected at the STAGE'S OWN LAST close (Pas 5) -- its scheduled
         NEXT_SESSION_OPEN fill falls in the next stage, never read
         (section 10's central CENSORED_AT_HORIZON case, regression #9)
         -- CENSORED_AT_HORIZON, EVALUABLE, with `pending_exit_note` set.
"""
from __future__ import annotations

import pytest

from data_foundation.model import repository as repo
from data_foundation.model.entities import PriceBar
from data_foundation.pit import access as pit_module

from backtest.exits.costs import (
    aggregate_position_return,
    apply_exit_slippage,
    compute_w,
    open_remainder_net_return,
    tranche_net_return,
)
from backtest.exits.engine import ENTRY_EXECUTED, EntryDisposition, EntrySignal, SessionEngine, evaluate_stage_results
from backtest.exits.entities import (
    EVALUABILITY_EVALUABLE,
    EXIT_REASON_STOP,
    EXIT_REASON_TARGET,
    LIFECYCLE_CENSORED_AT_HORIZON,
    LIFECYCLE_CLOSED,
)
from backtest.exits.taxonomy import classify_position
from backtest.models.entities import CostAssumptions

from spec005.fixtures.pit_universe import insert_corporate_action, make_security

L1, L2, L3 = "2024-03-01", "2024-03-02", "2024-03-03"
D1, D2, D3, D4, D5, D6 = (
    "2024-03-04", "2024-03-05", "2024-03-06", "2024-03-07", "2024-03-08", "2024-03-09",
)
SESSION_DATES = (D1, D2, D3, D4, D5, D6)
STAGE_END_DATE = D6

_VOL_CFG = {"atr_window": 3, "bb_window": 3, "bb_num_std": 2.0, "realized_vol_window": 3}


class _UnboundedAccess:
    """Same stand-in every other Batch 3 test uses (test_22, test_25):
    exercises the session engine directly against a real conn, bypassing
    Batch 2's own StageAccessBoundary machinery (already covered by
    tests/spec005/test_14-15)."""
    def __init__(self, conn):
        self.conn = conn

    def get_price_series_as_of(self, security_id, as_of):
        return pit_module.get_price_series_as_of(self.conn, security_id, as_of)

    def get_corporate_actions_as_of(self, security_id, as_of):
        return pit_module.get_corporate_actions_as_of(self.conn, security_id, as_of)


def _insert_bars(conn, security_id, now, rows):
    """`rows`: iterable of (date, open, high, low, close)."""
    repo.insert_price_bars(conn, [
        PriceBar(
            security_id=security_id, date=d, raw_open=o, raw_high=h, raw_low=l, raw_close=c,
            raw_volume=1000, source_provider="manual", ingestion_timestamp=now,
        )
        for d, o, h, l, c in rows
    ])


def _never_invalidated_except(security_id_to_watch, date_to_invalidate):
    def observer(position, session_date):
        if position.security_id == security_id_to_watch and session_date == date_to_invalidate:
            return "INVALIDATED"
        return "VALID_HOLD"
    return observer


def test_integrated_pas0_through_6_two_securities_stage_limits_and_aggregate_costs(conn, now):
    sec_a = make_security(conn, "spec005:ENGINE_A", now)
    sec_b = make_security(conn, "spec005:ENGINE_B", now)

    # SEC_A: flat pre-split lead-in (ATR_14(s=D1)=8 -> S_initial=100-2*8=84,
    # risc_initial=16, target=100+2*16=132), then D2 entry, D3 target hit
    # at open (133 >= 132), D4 the split takes raw effect (post-split
    # raw levels, ~half), D5 the remainder stops out (low crashes well
    # below any plausible drifted stop).
    _insert_bars(conn, sec_a, now, [
        (L1, 100.0, 104.0, 96.0, 100.0),
        (L2, 100.0, 104.0, 96.0, 100.0),
        (L3, 100.0, 104.0, 96.0, 100.0),
        (D1, 100.0, 104.0, 96.0, 100.0),
        (D2, 100.0, 102.0, 98.0, 100.0),
        (D3, 133.0, 135.0, 130.0, 134.0),
        (D4, 67.0, 68.0, 66.0, 67.0),
        (D5, 67.0, 68.0, 20.0, 25.0),
        (D6, 25.0, 26.0, 24.0, 25.0),
    ])
    insert_corporate_action(
        conn, sec_a, "act_split_a", "SPLIT", effective_date=D4, value=2.0, now=now, available_at=D4,
    )

    # SEC_B: gentle uptrend throughout, ATR_14(s=D1)=4 -> S_initial=50-2*4=42
    # -- every low stays comfortably above that. Trend invalidation is
    # detected at D6's own close, the stage's LAST session.
    _insert_bars(conn, sec_b, now, [
        (L1, 50.0, 52.0, 48.0, 50.0),
        (L2, 50.0, 52.0, 48.0, 50.0),
        (L3, 50.0, 52.0, 48.0, 50.0),
        (D1, 50.0, 52.0, 48.0, 50.0),
        (D2, 50.0, 51.0, 49.0, 50.0),
        (D3, 50.0, 52.0, 49.0, 51.0),
        (D4, 51.0, 53.0, 50.0, 52.0),
        (D5, 52.0, 54.0, 51.0, 53.0),
        (D6, 53.0, 61.0, 52.0, 60.0),
    ])

    pit = _UnboundedAccess(conn)
    entry_signals = {
        (sec_a, D1): EntrySignal(security_id=sec_a, direction="LONG", k=2.0, r_multiple=2.0, fraction=0.5),
        (sec_b, D1): EntrySignal(security_id=sec_b, direction="LONG", k=2.0),  # Control: no partial_profit
    }

    def same_day_evidence(security_id, session_date):
        if security_id == sec_a and session_date == D4:
            return frozenset({"act_split_a"})
        return frozenset()

    engine = SessionEngine(
        pit=pit, session_dates=SESSION_DATES, entry_signals=entry_signals,
        invalidation_observer=_never_invalidated_except(sec_b, D6),
        same_day_split_evidence=same_day_evidence, volatility_config=_VOL_CFG, stage_end_date=STAGE_END_DATE,
    )
    result = engine.run()

    positions_by_id = {p.security_id: p for p in result.positions}
    assert set(positions_by_id) == {sec_a, sec_b}

    # -- Entry dispositions: both signals executed (Pas 2). --
    assert EntryDisposition(sec_a, D1, D2, ENTRY_EXECUTED) in result.entry_dispositions
    assert EntryDisposition(sec_b, D1, D2, ENTRY_EXECUTED) in result.entry_dispositions

    # -- SEC_A structural checks (Pas 2, Pas 3'b, Pas 0, Pas 3'c). --
    pos_a = positions_by_id[sec_a]
    assert pos_a.closed is True
    assert pos_a.split_reconciliation_incomplete is False
    assert pos_a.applied_factor == pytest.approx(0.5)  # 2-for-1 split -> price halves
    assert "act_split_a" in pos_a.processed_split_action_ids
    assert pos_a.partial_tranche is not None
    assert pos_a.partial_tranche.exit_reason == EXIT_REASON_TARGET
    assert pos_a.partial_tranche.exit_fill_price == pytest.approx(133.0)
    assert pos_a.partial_tranche.entry_fill_price_reference == pytest.approx(100.0)
    assert pos_a.partial_tranche.fraction_of_original == pytest.approx(0.5)
    assert pos_a.close_tranche is not None
    assert pos_a.close_tranche.exit_reason == EXIT_REASON_STOP
    assert pos_a.close_tranche.fraction_of_original == pytest.approx(0.5)
    # The remainder tranche's own frozen entry reference is the POST-split
    # basis (100 * 0.5 = 50) -- it was created AFTER Pas 0 reconciled the
    # split, unlike the partial tranche above (created BEFORE it, still
    # referencing the pre-split 100). GPT review round 2 finding #5's own
    # invariant, still holding through the full session loop.
    assert pos_a.close_tranche.entry_fill_price_reference == pytest.approx(50.0)
    assert pos_a.close_tranche.holding_days == 3  # D2 -> D5

    # -- SEC_B structural checks (Pas 5 at the stage's own last close). --
    pos_b = positions_by_id[sec_b]
    assert pos_b.closed is False
    assert pos_b.pending_invalidation_detected_date == D6
    assert pos_b.pending_exit_note is not None
    assert pos_b.entry_fill_price == pytest.approx(50.0)  # never touched by any split
    assert result.final_closes[sec_b] == pytest.approx(60.0)

    # -- Facet classification (section 10). --
    outcome_a = classify_position(pos_a, stage_end_reached=True)
    outcome_b = classify_position(pos_b, stage_end_reached=True, final_mark_available=result.final_closes[sec_b] is not None)
    assert outcome_a.lifecycle == LIFECYCLE_CLOSED
    assert outcome_a.evaluability == EVALUABILITY_EVALUABLE
    assert outcome_a.reason is None
    assert outcome_b.lifecycle == LIFECYCLE_CENSORED_AT_HORIZON
    assert outcome_b.evaluability == EVALUABILITY_EVALUABLE
    assert outcome_b.reason is None

    # -- Aggregate net_return (section 9), WITH exit-side slippage (section
    # 9 / amendament §13) applied only to the STOP/INVALIDATION legs. --
    costs = CostAssumptions(
        commission_entry_rate=0.001, commission_exit_rate=0.002,
        slippage_entry_bps=0.0, slippage_exit_bps=100.0,  # 1% exit slippage
        borrow_annual_rate=0.0365,
    )
    positions = [pos_a, pos_b]
    outcomes = [outcome_a, outcome_b]
    results = evaluate_stage_results(positions, outcomes, costs, STAGE_END_DATE, result.final_closes)
    result_a, result_b = results

    # SEC_A: partial (TARGET, no slippage) is fully hand-derivable; the
    # remainder (STOP) is derived from its OWN actually-recorded fill via
    # the same cost primitives `evaluate_stage_results()` itself uses.
    expected_partial = tranche_net_return(
        "LONG", 100.0, 133.0, commission_entry_rate=0.001, commission_exit_rate=0.002,
        borrow_annual_rate=0.0365, holding_days=1,
    )
    assert expected_partial == pytest.approx(0.32624)
    f_x_remainder = apply_exit_slippage("LONG", pos_a.close_tranche.exit_fill_price, EXIT_REASON_STOP, slippage_exit_rate=0.01)
    expected_rest_a = tranche_net_return(
        "LONG", pos_a.close_tranche.entry_fill_price_reference, f_x_remainder,
        commission_entry_rate=0.001, commission_exit_rate=0.002, borrow_annual_rate=0.0365,
        holding_days=pos_a.close_tranche.holding_days,
    )
    w_a = compute_w(pos_a)
    assert w_a == pytest.approx(0.5)
    expected_result_a = aggregate_position_return(w_a, expected_partial, expected_rest_a)
    assert result_a == pytest.approx(expected_result_a)

    # SEC_B: no ATR/stop path at all -- fully hand-verified.
    # d*(60-50)/50 - 0.001 - 0.0365*4/365 = 0.2 - 0.001 - 0.0004 = 0.1986
    expected_result_b = open_remainder_net_return(
        "LONG", 50.0, 60.0, commission_entry_rate=0.001, borrow_annual_rate=0.0365, holding_days=4,
    )
    assert expected_result_b == pytest.approx(0.1986)
    assert compute_w(pos_b) == 0.0
    assert result_b == pytest.approx(expected_result_b)
