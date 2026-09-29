"""TEST 39 -- Spec #005 Discovery Integration & Legacy Exits, review
finding #5: a test that actually traverses `StageReadContext` -> real
`discovery.engine.compute_discovery_observations()` (via Batch 2's own
`HistoricalObservationCache`) -> `discovery_integration`'s matching/
invalidation evaluation -> `engine.run_stage()`. `run_stage()` itself is
NOT changed to call Discovery internally (an explicit, separate-
orchestrator design Radu confirmed is acceptable) -- this test IS that
separate orchestrator, built once to prove the composition actually
works end to end, not just when fed hand-built `DiscoveryObservation`s
(test_38's own job, kept for exact, hand-verified numbers).

The price path is deliberately engineered (not random) so a REAL,
unmodified Discovery computation lands on a KNOWN, verified lane label at
each session -- read off empirically via the SAME production function
this test calls, the same discipline `test_35`/`test_38` already use for
cost primitives (cross-check against the real computation, never
re-derive Discovery's own percentile/state logic by hand): ~1.5 years of
smooth linear-drift daily bars puts `volatility` (BB-width percentile) at
`EXTREME_COMPRESSION` throughout, then a sharp, large price swing
introduced on the THIRD formation session flips it to `EXTREME_EXPANSION`
-- a real state transition Discovery itself detects (it also emits
`STATE_TRANSITION` in `reason_codes`, unused by this test but confirming
the same underlying mechanism).
"""
from __future__ import annotations

from data_foundation.model import repository as repo
from data_foundation.model.entities import PriceBar

from discovery.config.loader import load_config as load_discovery_config

from hypothesis.models.entities import EntryDefinition, InvalidationCondition, LaneStateCondition
from hypothesis.registry.hypotheses import HypothesisRegistry

from backtest.data.calendar import build_trading_calendar
from backtest.data.context import StageReadContext
from backtest.exits.costs import tranche_net_return
from backtest.exits.discovery_integration import (
    build_entry_signals_from_observations,
    build_invalidation_observer,
    observations_by_session_from_caches,
)
from backtest.exits.engine import run_stage
from backtest.exits.entities import EVALUABILITY_EVALUABLE, EXIT_REASON_SIGNAL_INVALIDATION, LIFECYCLE_CLOSED
from backtest.exits.legacy import classify_legacy_position, evaluate_legacy_stage_results
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

from fixtures.market_data import business_days

from spec005.fixtures.legacy_variants import build_registered_signal_invalidation_hypothesis
from spec005.fixtures.pit_universe import insert_price_history, make_security

_ZERO_COSTS = CostAssumptions(
    commission_entry_rate=0.0, commission_exit_rate=0.0, slippage_entry_bps=0.0, slippage_exit_bps=0.0, borrow_annual_rate=0.0,
)

WARMUP_START = "2023-01-02"
CALM_END = "2024-06-20"
D1, D2, D3, D4, D5, D6 = "2024-06-21", "2024-06-24", "2024-06-25", "2024-06-26", "2024-06-27", "2024-06-28"
VALIDATION_START, VALIDATION_END, LOCKED_OOS_START = "2024-07-01", "2024-07-31", "2024-08-01"

BASE_PRICE = 100.0
DAILY_DRIFT = 0.05


def _build_plan(hid: str, calendar_id: str, benchmark_security_id: str) -> ResearchPlan:
    """Mirrors `spec005.conftest.pit_research_plan`'s own construction
    (old-family-only cohort: default `SelectionRule.ranking_metric`, no
    STOP_MANAGED fields at all) -- inlined here rather than editing that
    fixture, since this test needs its own benchmark/zone dates."""
    profile = build_execution_semantics_profile_v1()
    rule = SelectionRule(minimum_executed_trades=1, minimum_evaluable_trades=1, minimum_evaluable_ratio=0.5)
    costs = _ZERO_COSTS
    exposure = ExposureManifest(declared_unseen=True)
    folds = (SelectionFold("fold_1", D1, D6),)
    fields = dict(
        formation_start=D1, formation_end=D6, validation_start=VALIDATION_START, validation_end=VALIDATION_END,
        locked_oos_start=LOCKED_OOS_START, selection_folds=folds, hypothesis_cohort_ids=(hid,),
        trading_calendar_id=calendar_id, benchmark_security_id=benchmark_security_id,
        execution_semantics_profile_id=profile.profile_id, selection_rule=rule,
        cost_assumptions=costs, exposure_manifest=exposure,
    )
    fp = research_plan_fingerprint(**fields)
    plan_id, plan_hash = build_research_plan_id(fp)
    return ResearchPlan(research_plan_id=plan_id, plan_hash=plan_hash, created_at="t", created_by="test", **fields)


def test_real_discovery_observations_drive_matching_invalidation_and_run_stage(conn, now):
    sec = make_security(conn, "spec005:REAL_PIPELINE_SEC", now)
    bench = make_security(conn, "spec005:REAL_PIPELINE_BENCH", now)

    all_dates = business_days(WARMUP_START, D6)
    calm_dates = business_days(WARMUP_START, CALM_END)
    insert_price_history(conn, sec, now, WARMUP_START, CALM_END, base_price=BASE_PRICE, daily_drift=DAILY_DRIFT)
    insert_price_history(conn, bench, now, WARMUP_START, D6, base_price=200.0, daily_drift=0.02)

    # Last calm close -- the entry-day (D2) open, per make_bars' own
    # `price = base_price; price += daily_drift` per business day.
    last_calm_price = BASE_PRICE + DAILY_DRIFT * (len(calm_dates) - 1)

    # D1/D2: flat continuation (no swing) -- volatility stays
    # EXTREME_COMPRESSION (empirically confirmed below by reading the
    # real observation back, never assumed). D3 onward: a sharp +/-30%
    # daily swing -- volatility flips to EXTREME_EXPANSION.
    extra_days = (D1, D2, D3, D4, D5, D6)
    rows = []
    p = last_calm_price
    for i, d in enumerate(extra_days):
        swing = 0.0 if i < 2 else 0.30
        o = p
        h = p * (1 + swing + 0.02)
        l = p * (1 - swing - 0.02)
        c = p * (1 + swing) if i % 2 == 0 else p * (1 - swing)
        rows.append((d, o, h, l, c))
        p = c
    repo.insert_price_bars(conn, [
        PriceBar(
            security_id=sec, date=d, raw_open=o, raw_high=h, raw_low=l, raw_close=c,
            raw_volume=1_000_000, source_provider="manual", ingestion_timestamp=now,
        )
        for d, o, h, l, c in rows
    ])
    entry_open = rows[1][1]  # D2's own open == last_calm_price (flat through D1/D2)
    d3_close = rows[2][4]
    assert entry_open == last_calm_price
    assert d3_close == last_calm_price * 1.30

    calendar = build_trading_calendar(
        source=CalendarSource.SYNTHETIC_TEST_FIXTURE.value, calendar_identifier="SPEC005_REAL_PIPELINE_CALENDAR",
        calendar_version="v1", market="US_EQUITIES", timezone="America/New_York",
        coverage_start=WARMUP_START, coverage_end=D6, session_dates=tuple(all_dates),
        session_open_time="09:30", session_close_time="16:00", verified_by="test", verified_at="2026-01-01T00:00:00Z",
    )

    registry = HypothesisRegistry()
    entry = EntryDefinition(core_conditions=(LaneStateCondition("volatility", "EXTREME_COMPRESSION"),))
    invalidation_conditions = (InvalidationCondition(lane="volatility", holds_labels=("EXTREME_COMPRESSION", "COMPRESSION")),)
    hid, sig_vid = build_registered_signal_invalidation_hypothesis(
        registry, max_holding_bars=5, invalidation_conditions=invalidation_conditions,
        signature_id="SIG_REAL_PIPELINE", entry=entry,
    )

    plan = _build_plan(hid, calendar.calendar_id, bench)
    discovery_config = load_discovery_config()

    with StageReadContext(conn, plan, FORMATION_SELECTION, (sec,), bench, calendar, WARMUP_START) as ctx:
        caches = {d: ctx.get_or_compute_observations((sec,), d, discovery_config) for d in (D1, D2, D3, D4, D5, D6)}
        observations_by_session = observations_by_session_from_caches(caches)

        # Empirical confirmation (not assumed) of the real, unmodified
        # Discovery computation's own output -- this IS the "read off
        # verified lane labels" step the module docstring describes.
        assert observations_by_session[D1][sec].state_signature["volatility"] == "EXTREME_COMPRESSION"
        assert observations_by_session[D2][sec].state_signature["volatility"] == "EXTREME_COMPRESSION"
        assert observations_by_session[D3][sec].state_signature["volatility"] == "EXTREME_EXPANSION"

        entry_signals = build_entry_signals_from_observations(observations_by_session, registry, frozenset({hid}))
        assert (sec, sig_vid, D1) in entry_signals
        invalidation_observer = build_invalidation_observer(observations_by_session, registry)

        result = run_stage(
            plan, registry, conn, FORMATION_SELECTION, calendar,
            entry_signals=entry_signals, invalidation_observer=invalidation_observer, stop_managed_profile=None,
        )

    # The hypothesis's own horizon_candidate_set also auto-materializes a
    # TIME_EXIT(1) sibling variant (build_registered_signal_invalidation_
    # hypothesis's documented default), sharing the same real entry match.
    # Since volatility is EXTREME_COMPRESSION on BOTH D1 and D2, the real
    # matching function correctly emits an entry signal for EACH day --
    # TIME_EXIT(1) closes on its own entry day (holding bar 1), which
    # frees its (security, variant) key immediately, so the D2 signal
    # opens a SECOND, independent TIME_EXIT(1) position entering/exiting
    # at D3. SIGNAL_INVALIDATION's own position (from the D1 signal)
    # is still open when the D2 signal is evaluated, so its own
    # "already open" check correctly suppresses a second entry for it --
    # exactly one `sig_vid` position ever exists. 3 positions total: two
    # TIME_EXIT(1) instances plus the one SIGNAL_INVALIDATION position
    # this test actually asserts on.
    assert len(result.positions) == 3
    assert sum(1 for p in result.positions if p.strategy_variant_id == sig_vid) == 1
    sig_pos = next(p for p in result.positions if p.strategy_variant_id == sig_vid)

    assert sig_pos.entry_date == D2
    assert sig_pos.entry_fill_price == entry_open
    assert sig_pos.closed is True
    assert sig_pos.close_tranche.exit_reason == EXIT_REASON_SIGNAL_INVALIDATION
    assert sig_pos.close_tranche.exit_date == D3
    assert sig_pos.close_tranche.exit_fill_price == d3_close
    assert sig_pos.invalidation_path_incomplete is False

    outcome = classify_legacy_position(sig_pos, stage_end_reached=True)
    assert outcome.lifecycle == LIFECYCLE_CLOSED and outcome.evaluability == EVALUABILITY_EVALUABLE
    (net_return,) = evaluate_legacy_stage_results([sig_pos], [outcome], _ZERO_COSTS, D6, result.final_closes)
    expected_return = tranche_net_return("LONG", entry_open, d3_close, 0.0, 0.0, 0.0, sig_pos.close_tranche.holding_days)
    assert net_return == expected_return
    # Zero costs, entry->exit +30% swing -- hand-verifiable directly,
    # without even needing the cost-formula cross-check above.
    assert abs(net_return - 0.30) < 1e-9
