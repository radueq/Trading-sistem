"""TEST 35 -- Session Engine & Integration review, round 1, finding #6:
the integrated demonstration must go through the REAL, obligatory public
entry point (`engine.run_stage()`), against a REAL `BoundedPITAccess`
bounded by a REAL `StageAccessBoundary` (never the `_UnboundedAccess`
stand-in test_33/34 use to exercise the loop's own mechanics in
isolation), with a genuinely ACCEPTED STOP_MANAGED_INVALIDATION plan,
NONZERO costs (both entry and exit slippage), and a trend invalidation
detected and EXECUTED WITHIN the stage (not merely at the stage's last
close, which TEST 34 already covers) -- with explicit proof that Pas 1's
scheduled invalidation fill takes priority over a stop breach the SAME
session's own price action would otherwise have triggered.
"""
from __future__ import annotations

import pytest

from data_foundation.model import repository as repo
from data_foundation.model.entities import PriceBar
from data_foundation.pit import access as pit_module

from hypothesis.registry.hypotheses import HypothesisRegistry

from backtest.data.pit_access import BoundedPITAccess
from backtest.exits.costs import apply_entry_slippage, apply_exit_slippage, tranche_net_return
from backtest.exits.engine import EntrySignal, evaluate_stage_results, run_stage
from backtest.exits.entities import (
    EVALUABILITY_EVALUABLE,
    EXIT_REASON_INVALIDATION,
    EXIT_REASON_STOP,
    LIFECYCLE_CLOSED,
)
from backtest.exits.taxonomy import classify_position
from backtest.models.entities import FORMATION_SELECTION, CostAssumptions, StageAccessBoundary

from spec005.fixtures.pit_universe import make_security
from spec005.fixtures.stop_managed_variants import build_accepted_stop_managed_plan, build_registered_stop_managed_hypothesis

L1, L2, L3 = "2024-04-01", "2024-04-02", "2024-04-03"
D1, D2, D3, D4, D5 = "2024-04-04", "2024-04-05", "2024-04-06", "2024-04-07", "2024-04-08"
SESSION_DATES = (D1, D2, D3, D4, D5)
STAGE_END_DATE = D5

_COSTS = CostAssumptions(
    commission_entry_rate=0.001, commission_exit_rate=0.002,
    slippage_entry_bps=200.0,  # 2%
    slippage_exit_bps=150.0,   # 1.5%
    borrow_annual_rate=0.0,
)


def _insert_bars(conn, security_id, now, rows):
    repo.insert_price_bars(conn, [
        PriceBar(
            security_id=security_id, date=d, raw_open=o, raw_high=h, raw_low=l, raw_close=c,
            raw_volume=1000, source_provider="manual", ingestion_timestamp=now,
        )
        for d, o, h, l, c in rows
    ])


def test_run_stage_end_to_end_real_bounded_pit_invalidation_priority_over_stop(conn, now):
    sec = make_security(conn, "spec005:RUNSTAGE_PRIORITY", now)
    # Flat ATR_14(s=D1)=8 lead-in through D2/D3 (no trailing-stop drift):
    # S_initial = F_e(102, WITH 2% entry slippage) - 2*8 = 86.
    # D4: the scheduled invalidation fires AT OPEN (95) -- its own LOW (10)
    # crashes far below the stop (86), which would ALSO have triggered a
    # stop if Pas 3' had ever run this session. It must not: Pas 1 runs
    # first and retires the position before Pas 3' is ever reached.
    _insert_bars(conn, sec, now, [
        (L1, 100.0, 104.0, 96.0, 100.0),
        (L2, 100.0, 104.0, 96.0, 100.0),
        (L3, 100.0, 104.0, 96.0, 100.0),
        (D1, 100.0, 104.0, 96.0, 100.0),
        (D2, 100.0, 104.0, 96.0, 100.0),  # entry day, same TR=8 as lead-in
        (D3, 100.0, 104.0, 96.0, 100.0),  # invalidation detected at THIS close
        (D4, 95.0, 96.0, 10.0, 90.0),     # scheduled fill at open=95; low=10 would ALSO breach stop=86
        (D5, 90.0, 91.0, 89.0, 90.0),     # unreachable -- position already closed at D4
    ])

    registry = HypothesisRegistry()
    hid, vid = build_registered_stop_managed_hypothesis(registry, k=2.0)  # Control: no partial_profit
    plan, profile = build_accepted_stop_managed_plan([hid], cost_assumptions=_COSTS)

    boundary = StageAccessBoundary(zone=FORMATION_SELECTION, max_as_of=STAGE_END_DATE)
    pit = BoundedPITAccess(conn, boundary)

    def observer(position, session_date):
        return "INVALIDATED" if session_date == D3 else "VALID_HOLD"

    signal = EntrySignal(security_id=sec, strategy_variant_id=vid)
    result = run_stage(
        plan, registry, pit, session_dates=SESSION_DATES,
        entry_signals={(sec, D1): signal}, invalidation_observer=observer, stop_managed_profile=profile,
        volatility_config={"atr_window": 3, "bb_window": 3, "bb_num_std": 2.0, "realized_vol_window": 3},
    )

    assert len(result.positions) == 1
    pos = result.positions[0]

    # Entry slippage applied through the FULL run_stage() path.
    assert pos.entry_fill_price == pytest.approx(apply_entry_slippage("LONG", 100.0, 0.02))
    assert pos.entry_fill_price == pytest.approx(102.0)
    assert pos.active_stop == pytest.approx(86.0)  # 102 - 2*8, never unslipped 100-16=84

    # Priority: INVALIDATION closed it, not STOP -- even though D4's own
    # low (10) would have breached the stop (86) had Pas 3' ever run.
    assert pos.closed is True
    assert pos.close_tranche.exit_reason == EXIT_REASON_INVALIDATION
    assert pos.close_tranche.exit_reason != EXIT_REASON_STOP
    assert pos.close_tranche.exit_fill_price == pytest.approx(95.0)  # D4's OPEN, the scheduled fill -- raw, unslipped
    assert pos.close_tranche.holding_days == 2  # D2 -> D4
    assert pos.pending_invalidation_detected_date is None  # consumed

    outcome = classify_position(pos, stage_end_reached=True)
    assert outcome.lifecycle == LIFECYCLE_CLOSED
    assert outcome.evaluability == EVALUABILITY_EVALUABLE

    (net_return,) = evaluate_stage_results([pos], [outcome], _COSTS, STAGE_END_DATE, result.final_closes)
    expected_f_x = apply_exit_slippage("LONG", 95.0, EXIT_REASON_INVALIDATION, slippage_exit_rate=0.015)
    expected_return = tranche_net_return(
        "LONG", pos.entry_fill_price, expected_f_x,
        commission_entry_rate=0.001, commission_exit_rate=0.002, borrow_annual_rate=0.0, holding_days=2,
    )
    assert net_return == pytest.approx(expected_return)
