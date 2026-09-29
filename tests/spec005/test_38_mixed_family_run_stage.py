"""TEST 38 -- Spec #005 Discovery Integration & Legacy Exits, obligation 4:
an INTEGRATED test through the real, obligatory `engine.run_stage()` entry
point, with a cohort mixing all THREE exit families (TIME_EXIT,
SIGNAL_INVALIDATION, STOP_MANAGED_INVALIDATION) under ONE shared entry
decision, driven by REAL `backtest.exits.discovery_integration` entry-
matching/invalidation-evaluation against hand-built `DiscoveryObservation`s
(never a caller-typed EntrySignal dict or a stub `invalidation_observer`
closure) -- closing exactly the gap `docs/spec005_known_limitations.md`
names: "`SessionEngine` itself has nothing to run for that cohort's
old-family variants." Also proves stage limits (SUPPRESSED_STAGE_BOUNDARY
never spuriously fires for a signal recorded well before the stage's own
last session) and aggregate cost evaluation (entry AND exit slippage,
commissions) across the full mixed cohort.
"""
from __future__ import annotations

from datetime import date

from data_foundation.model import repository as repo
from data_foundation.model.entities import PriceBar

from discovery.models.entities import DescriptiveMetrics, DiscoveryObservation

from hypothesis.registry.hypotheses import HypothesisRegistry

from backtest.exits.costs import apply_entry_slippage, apply_exit_slippage, open_remainder_net_return, tranche_net_return
from backtest.exits.discovery_integration import build_entry_signals_from_observations, build_invalidation_observer
from backtest.exits.engine import evaluate_stage_results, run_stage
from backtest.exits.entities import (
    EVALUABILITY_EVALUABLE,
    EXIT_REASON_SIGNAL_INVALIDATION,
    EXIT_REASON_TIME_EXIT,
    LIFECYCLE_CENSORED_AT_HORIZON,
    LIFECYCLE_CLOSED,
)
from backtest.exits.legacy import classify_legacy_position, evaluate_legacy_stage_results
from backtest.exits.taxonomy import classify_position
from backtest.models.entities import FORMATION_SELECTION, CostAssumptions

from spec005.fixtures.mixed_family_variants import build_registered_mixed_family_hypothesis
from spec005.fixtures.pit_universe import make_security
from spec005.fixtures.stop_managed_variants import build_accepted_stop_managed_plan

L1, L2, L3 = "2024-03-29", "2024-03-30", "2024-03-31"
D1, D2, D3, D4, D5, D6 = "2024-04-01", "2024-04-02", "2024-04-03", "2024-04-04", "2024-04-05", "2024-04-06"
STAGE_END_DATE = D6

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


def _obs(security_id: str, as_of: str, lane_states: dict) -> DiscoveryObservation:
    return DiscoveryObservation(
        security_id=security_id, ticker_as_of=security_id, as_of=as_of, timeframe="1D",
        feature_vector={}, normalized_feature_vector={}, state_signature=lane_states,
        transition_vector={}, active_lanes=list(lane_states.keys()),
        descriptive_metrics=DescriptiveMetrics(extremeness=0.0, persistence=1, state_frequency=None, sample_count=1, support_status="SUFFICIENT"),
        reason_codes=[], config_version="cfg_test", feature_engine_version="v1.0.0", discovery_engine_version="v1.0.0",
    )


def test_mixed_cohort_run_stage_executes_all_three_families_with_correct_costs(conn, now):
    sec = make_security(conn, "spec005:MIXED_FAMILY_RUNSTAGE", now)
    # Flat TR=8 throughout (lead-in L1-L3 through D6) -- keeps STOP_MANAGED's
    # ATR_14 exactly flat (matches TEST 35's own established derivation
    # discipline), so its stop (102 - 2*8 = 86) is never at risk from the
    # deliberately flat OHLC path (low=96 always stays well above it).
    flat_row = (100.0, 104.0, 96.0, 100.0)
    _insert_bars(conn, sec, now, [(d, *flat_row) for d in (L1, L2, L3, D1, D2, D3, D4, D5, D6)])

    registry = HypothesisRegistry()
    ids = build_registered_mixed_family_hypothesis(
        registry, signature_id="SIG_MIXED_RUNSTAGE", time_exit_bars=3,
        stop_managed_k=2.0, signal_invalidation_max_holding_bars=5,
    )
    hid = ids["hypothesis_id"]

    # D1: volatility=COMPRESSION matches the shared EntryDefinition -- one
    # signal per variant is recorded at D1's close, entering all three at
    # D2's open. "momentum" stays HIGH throughout (STOP_MANAGED's own
    # invalidation lane never breaks); "relative_strength" flips to LOW
    # starting D3 (SIGNAL_INVALIDATION's own lane -- invalidates it at D3,
    # well before its max_holding_bars=5 cap).
    observations_by_session = {
        D1: {sec: _obs(sec, D1, {"volatility": "COMPRESSION", "momentum": "HIGH", "relative_strength": "HIGH"})},
        D2: {sec: _obs(sec, D2, {"momentum": "HIGH", "relative_strength": "HIGH"})},
        D3: {sec: _obs(sec, D3, {"momentum": "HIGH", "relative_strength": "LOW"})},
        D4: {sec: _obs(sec, D4, {"momentum": "HIGH", "relative_strength": "LOW"})},
        D5: {sec: _obs(sec, D5, {"momentum": "HIGH", "relative_strength": "LOW"})},
        D6: {sec: _obs(sec, D6, {"momentum": "HIGH", "relative_strength": "LOW"})},
    }
    entry_signals = build_entry_signals_from_observations(observations_by_session, registry, frozenset({hid}))
    assert set(entry_signals.keys()) == {
        (sec, ids["time_exit"], D1), (sec, ids["stop_managed"], D1), (sec, ids["signal_invalidation"], D1),
    }
    invalidation_observer = build_invalidation_observer(observations_by_session, registry)

    plan, profile, calendar = build_accepted_stop_managed_plan(
        [hid], cost_assumptions=_COSTS,
        formation_start=D1, formation_end=D6, validation_start="2024-05-01", validation_end="2024-05-31",
        locked_oos_start="2024-06-01", coverage_start=L1, coverage_end=D6,
        calendar_session_dates=(D1, D2, D3, D4, D5, D6),
    )

    result = run_stage(
        plan, registry, conn, FORMATION_SELECTION, calendar,
        entry_signals=entry_signals, invalidation_observer=invalidation_observer, stop_managed_profile=profile,
        volatility_config={"atr_window": 3, "bb_window": 3, "bb_num_std": 2.0, "realized_vol_window": 3},
    )

    assert len(result.positions) == 3
    # No SUPPRESSED_STAGE_BOUNDARY -- the shared signal was recorded at D1,
    # nowhere near the stage's own last session (D6).
    assert all(d.disposition == "EXECUTED" for d in result.entry_dispositions)
    by_variant = {p.strategy_variant_id: p for p in result.positions}

    expected_entry_fill = apply_entry_slippage("LONG", 100.0, 0.02)
    assert expected_entry_fill == 102.0

    # -- TIME_EXIT: time_exit_bars=3 -> holding bar 3 = D4 (entry D2 = bar 1).
    time_exit_pos = by_variant[ids["time_exit"]]
    assert time_exit_pos.entry_fill_price == expected_entry_fill
    assert time_exit_pos.closed is True
    assert time_exit_pos.close_tranche.exit_reason == EXIT_REASON_TIME_EXIT
    assert time_exit_pos.close_tranche.exit_date == D4
    te_outcome = classify_legacy_position(time_exit_pos, stage_end_reached=True)
    assert te_outcome.lifecycle == LIFECYCLE_CLOSED and te_outcome.evaluability == EVALUABILITY_EVALUABLE
    (te_return,) = evaluate_legacy_stage_results([time_exit_pos], [te_outcome], _COSTS, STAGE_END_DATE, result.final_closes)
    te_expected_fx = apply_exit_slippage("LONG", 100.0, EXIT_REASON_TIME_EXIT, slippage_exit_rate=0.015)
    te_expected = tranche_net_return("LONG", expected_entry_fill, te_expected_fx, 0.001, 0.002, 0.0, time_exit_pos.close_tranche.holding_days)
    assert te_return == te_expected

    # -- SIGNAL_INVALIDATION: invalidated at D3 (relative_strength -> LOW),
    # well before its own max_holding_bars=5 cap -- closes at D3's own close.
    sig_pos = by_variant[ids["signal_invalidation"]]
    assert sig_pos.entry_fill_price == expected_entry_fill
    assert sig_pos.closed is True
    assert sig_pos.close_tranche.exit_reason == EXIT_REASON_SIGNAL_INVALIDATION
    assert sig_pos.close_tranche.exit_date == D3
    assert sig_pos.invalidation_path_incomplete is False
    sig_outcome = classify_legacy_position(sig_pos, stage_end_reached=True)
    assert sig_outcome.lifecycle == LIFECYCLE_CLOSED and sig_outcome.evaluability == EVALUABILITY_EVALUABLE
    (sig_return,) = evaluate_legacy_stage_results([sig_pos], [sig_outcome], _COSTS, STAGE_END_DATE, result.final_closes)
    sig_expected_fx = apply_exit_slippage("LONG", 100.0, EXIT_REASON_SIGNAL_INVALIDATION, slippage_exit_rate=0.015)
    sig_expected = tranche_net_return("LONG", expected_entry_fill, sig_expected_fx, 0.001, 0.002, 0.0, sig_pos.close_tranche.holding_days)
    assert sig_return == sig_expected

    # -- STOP_MANAGED_INVALIDATION: "momentum" (its own invalidation lane)
    # never breaks, and the flat OHLC path never comes close to the stop
    # (86) -- stays open, CENSORED_AT_HORIZON at the stage's own last close.
    sm_pos = by_variant[ids["stop_managed"]]
    assert sm_pos.entry_fill_price == expected_entry_fill
    assert sm_pos.active_stop == 86.0  # 102 - 2*8, never breached
    assert sm_pos.closed is False
    sm_outcome = classify_position(sm_pos, stage_end_reached=True, final_mark_available=result.final_closes.get(sec) is not None)
    assert sm_outcome.lifecycle == LIFECYCLE_CENSORED_AT_HORIZON and sm_outcome.evaluability == EVALUABILITY_EVALUABLE
    assert result.final_closes[sec] == 100.0  # D6's own close
    (sm_return,) = evaluate_stage_results([sm_pos], [sm_outcome], _COSTS, STAGE_END_DATE, result.final_closes)
    holding_days = (date.fromisoformat(STAGE_END_DATE) - date.fromisoformat(sm_pos.entry_date)).days
    sm_expected = open_remainder_net_return("LONG", expected_entry_fill, 100.0, 0.001, 0.0, holding_days)
    assert sm_return == sm_expected
