"""TEST 33 -- the SessionEngine's own orchestration concerns that no
per-position unit test can exercise: SUPPRESSED_STAGE_BOUNDARY (amendment
section 2, item 1), `run_stage()`'s mandatory plan-acceptance gate, tying
every entry signal to a REAL, registry-resolved `StrategyVariant` (rejecting
an unresolvable variant, an off-cohort variant, or an unsupported exit
family BEFORE any price is read), `run_stage()` scoping execution to the
PLAN's own declared zone/calendar (never an independently supplied period),
strict `session_dates` ordering, and variant-keyed position bookkeeping (two
variants trading the same security concurrently, never suppressing each
other). The full Pas 0-6 session order itself, across a real multi-security
PIT universe, is TEST 34/35's job -- this file is deliberately narrower.
"""
from __future__ import annotations

import pytest

from data_foundation.model import repository as repo
from data_foundation.model.entities import PriceBar
from data_foundation.pit import access as pit_module

from hypothesis.registry.hypotheses import HypothesisRegistry

from backtest.exits.engine import (
    ENTRY_EXECUTED,
    EntryDisposition,
    EntrySignal,
    PlanNotAcceptedError,
    SessionEngine,
    evaluate_stage_results,
    run_stage,
)
from backtest.exits.entities import (
    ENTRY_NO_ENTRY_BAR,
    ENTRY_SUPPRESSED_STAGE_BOUNDARY,
    ENTRY_UNSUPPORTED_EXIT_FAMILY,
    ENTRY_VARIANT_NOT_FOUND,
    ENTRY_VARIANT_NOT_IN_ACCEPTED_COHORT,
    EVALUABILITY_EVALUABLE,
)
from backtest.exits.taxonomy import classify_position

from spec005.fixtures.pit_universe import make_security
from backtest.models.entities import (
    FORMATION_SELECTION,
    RANKING_METRIC_STOP_MANAGED_V1,
    CostAssumptions,
    ExposureManifest,
    ResearchPlan,
    SelectionFold,
    SelectionRule,
    build_execution_semantics_profile_v1,
    build_research_plan_id,
    research_plan_fingerprint,
)

from spec005.fixtures.stop_managed_variants import build_accepted_stop_managed_plan, build_registered_stop_managed_hypothesis

_ZERO_COSTS = CostAssumptions(
    commission_entry_rate=0.0, commission_exit_rate=0.0, slippage_entry_bps=0.0, slippage_exit_bps=0.0, borrow_annual_rate=0.0,
)


class _EmptyAccess:
    """No position ever reaches Pas 0-5 in these tests -- the only PIT
    calls that could happen are the ones a correctly-rejected signal must
    NEVER make. Raising loudly on any call makes that assertion
    self-enforcing rather than merely implied by the disposition."""
    def get_price_series_as_of(self, security_id, as_of):
        raise AssertionError(f"must never read a price for a rejected signal: get_price_series_as_of({security_id!r}, {as_of!r})")

    def get_corporate_actions_as_of(self, security_id, as_of):
        raise AssertionError(f"must never read corporate actions for a rejected signal: get_corporate_actions_as_of({security_id!r}, {as_of!r})")


def _never_invalidated(position, session_date):
    return "VALID_HOLD"


def test_signal_on_the_stage_last_session_is_suppressed_without_reading_any_price():
    """A signal recorded at the close of the STAGE'S OWN LAST session has
    no in-stage session left for its NEXT_SESSION_OPEN entry -- amendment
    section 2, item 1: rejected via SUPPRESSED_STAGE_BOUNDARY, with no
    price ever read for it at all. This check runs independently of
    variant resolution -- `strategy_variant_id` here is never even
    looked up."""
    session_dates = ("2024-05-01", "2024-05-02", "2024-05-03")
    last_session = session_dates[-1]
    signal = EntrySignal(security_id="SEC_ENG_SUPPRESSED", strategy_variant_id="var_never_looked_up")
    engine = SessionEngine(
        pit=_EmptyAccess(), session_dates=session_dates, registry=HypothesisRegistry(),
        accepted_hypothesis_ids=frozenset(),
        entry_signals={("SEC_ENG_SUPPRESSED", "var_never_looked_up", last_session): signal},
        invalidation_observer=_never_invalidated, cost_assumptions=_ZERO_COSTS,
    )
    result = engine.run()
    assert result.positions == ()
    assert result.entry_dispositions == (
        EntryDisposition(
            security_id="SEC_ENG_SUPPRESSED", strategy_variant_id="var_never_looked_up", signal_date=last_session,
            entry_date="<beyond authorized stage>", disposition=ENTRY_SUPPRESSED_STAGE_BOUNDARY,
        ),
    )


def test_a_signal_on_any_earlier_session_reaches_the_real_entry_path():
    """The SAME signal, one session earlier, DOES have an in-stage next
    session -- with a REAL, registered, in-cohort variant, it must reach
    all the way to an actual PIT read (proving the suppression above is
    genuinely about the stage boundary, not a blanket behavior)."""
    registry = HypothesisRegistry()
    hid, vid = build_registered_stop_managed_hypothesis(registry)
    session_dates = ("2024-05-01", "2024-05-02", "2024-05-03")
    signal = EntrySignal(security_id="SEC_ENG_NOTSUPPRESSED", strategy_variant_id=vid)
    engine = SessionEngine(
        pit=_EmptyAccess(), session_dates=session_dates, registry=registry,
        accepted_hypothesis_ids=frozenset({hid}),
        entry_signals={("SEC_ENG_NOTSUPPRESSED", vid, session_dates[0]): signal},
        invalidation_observer=_never_invalidated, cost_assumptions=_ZERO_COSTS,
    )
    with pytest.raises(AssertionError, match="get_price_series_as_of"):
        engine.run()


def test_unresolvable_variant_id_is_rejected_before_any_price_read():
    registry = HypothesisRegistry()
    session_dates = ("2024-05-01", "2024-05-02")
    signal = EntrySignal(security_id="SEC_ENG_NOVARIANT", strategy_variant_id="var_does_not_exist")
    engine = SessionEngine(
        pit=_EmptyAccess(), session_dates=session_dates, registry=registry,
        accepted_hypothesis_ids=frozenset(),
        entry_signals={("SEC_ENG_NOVARIANT", "var_does_not_exist", session_dates[0]): signal},
        invalidation_observer=_never_invalidated, cost_assumptions=_ZERO_COSTS,
    )
    result = engine.run()
    assert result.entry_dispositions[0].disposition == ENTRY_VARIANT_NOT_FOUND


def test_variant_outside_the_accepted_cohort_is_rejected_before_any_price_read():
    """A REAL, resolvable variant -- but its parent hypothesis is NOT in
    `accepted_hypothesis_ids` (the plan's own accepted cohort). Rejected,
    never silently run as if it belonged."""
    registry = HypothesisRegistry()
    hid, vid = build_registered_stop_managed_hypothesis(registry)
    session_dates = ("2024-05-01", "2024-05-02")
    signal = EntrySignal(security_id="SEC_ENG_OFFCOHORT", strategy_variant_id=vid)
    engine = SessionEngine(
        pit=_EmptyAccess(), session_dates=session_dates, registry=registry,
        accepted_hypothesis_ids=frozenset(),  # hid is NOT here
        entry_signals={("SEC_ENG_OFFCOHORT", vid, session_dates[0]): signal},
        invalidation_observer=_never_invalidated, cost_assumptions=_ZERO_COSTS,
    )
    result = engine.run()
    assert result.entry_dispositions[0].disposition == ENTRY_VARIANT_NOT_IN_ACCEPTED_COHORT


def test_unsupported_exit_family_is_rejected_before_any_price_read():
    """A variant whose OWN exit_family this engine has no mechanics for
    (TIME_EXIT here) must never be silently run through the
    STOP_MANAGED_INVALIDATION machinery."""
    from hypothesis.models.entities import Direction, EntryDefinition, HorizonCandidateSet, LaneStateCondition, ParameterSource
    from hypothesis.registry.hypotheses import build_hypothesis_id, hypothesis_fingerprint, materialize_variants
    import dataclasses as dc
    from hypothesis.models.entities import EvidenceProvenance, HypothesisComplexitySnapshot, HypothesisProvenance, HypothesisResearchMode, HypothesisStatus, StrategyHypothesis

    registry = HypothesisRegistry()
    entry = EntryDefinition(core_conditions=(LaneStateCondition("volatility", "COMPRESSION"),))
    horizons = HorizonCandidateSet(unit="BARS", values=(3,), selection_basis="x", parameter_source=ParameterSource.PRE_SPECIFIED.value)
    ev = EvidenceProvenance(
        evaluation_run_id="run_x", evaluation_engine_version="v1.0.0", evaluation_config_version="cfg_eval",
        signature_id="SIG_TIMEEXIT", signature_set_id="sigset_x", discovery_engine_version="v1.0.0",
        discovery_config_version="cfg_disc", timeframe="1D",
    )
    fp = hypothesis_fingerprint("SIG_TIMEEXIT", Direction.LONG.value, entry, "NEXT_BAR_OPEN", horizons, ev, "cfg_hyp_x")
    hid, dh = build_hypothesis_id(fp)
    hyp = StrategyHypothesis(
        hypothesis_id=hid, hypothesis_version=1, definition_hash=dh, status=HypothesisStatus.PREREGISTERED.value,
        research_mode=HypothesisResearchMode.PREREGISTERED_STRATEGY.value, parent_signature_id="SIG_TIMEEXIT",
        signature_set_id="sigset_x", direction=Direction.LONG.value, direction_basis="EVIDENCE_SIGN",
        entry_definition=entry, entry_execution_policy="NEXT_BAR_OPEN", horizon_candidate_set=horizons,
        variant_ids=(), evidence_provenance=ev, hypothesis_provenance=HypothesisProvenance("HUMAN:radu", None, None, "radu", "t"),
        constraints=HypothesisComplexitySnapshot(3, 1, "cfg_hyp_x"), created_at="t", created_by="radu", strategy_config_version="cfg_hyp_x",
    )
    variants = materialize_variants(hyp, created_at="t")  # default TIME_EXIT/SIGNAL_INVALIDATION variants only
    hyp = dc.replace(hyp, variant_ids=tuple(v.strategy_variant_id for v in variants))
    registry._force_register(hyp)
    for v in variants:
        registry.register_variant(v)
    time_exit_variant = next(v for v in variants if v.exit_hypothesis.exit_family != "STOP_MANAGED_INVALIDATION")

    session_dates = ("2024-05-01", "2024-05-02")
    signal = EntrySignal(security_id="SEC_ENG_WRONGFAMILY", strategy_variant_id=time_exit_variant.strategy_variant_id)
    engine = SessionEngine(
        pit=_EmptyAccess(), session_dates=session_dates, registry=registry,
        accepted_hypothesis_ids=frozenset({hid}),
        entry_signals={("SEC_ENG_WRONGFAMILY", time_exit_variant.strategy_variant_id, session_dates[0]): signal},
        invalidation_observer=_never_invalidated, cost_assumptions=_ZERO_COSTS,
    )
    result = engine.run()
    assert result.entry_dispositions[0].disposition == ENTRY_UNSUPPORTED_EXIT_FAMILY


def _build_old_family_plan(hypothesis_cohort_ids, ranking_metric) -> ResearchPlan:
    """Trimmed down, old-family-only plan builder (mirrors test_32's own
    `_build_plan()`), used ONLY for the run_stage()-gate-rejects test below
    -- that test never reaches calendar/variant resolution at all."""
    rule = SelectionRule(minimum_executed_trades=1, minimum_evaluable_trades=1, minimum_evaluable_ratio=0.5, ranking_metric=ranking_metric)
    profile = build_execution_semantics_profile_v1()
    costs = CostAssumptions(commission_entry_rate=0.0005, commission_exit_rate=0.0005, slippage_entry_bps=5.0, slippage_exit_bps=5.0, borrow_annual_rate=0.0)
    exposure = ExposureManifest(declared_unseen=True)
    fields = dict(
        formation_start="2024-01-01", formation_end="2024-01-31", validation_start="2024-02-01",
        validation_end="2024-02-29", locked_oos_start="2024-03-01",
        selection_folds=(SelectionFold("fold_1", "2024-01-01", "2024-01-31"),),
        hypothesis_cohort_ids=tuple(hypothesis_cohort_ids), trading_calendar_id="cal_x",
        benchmark_security_id="SBENCH", execution_semantics_profile_id=profile.profile_id,
        selection_rule=rule, cost_assumptions=costs, exposure_manifest=exposure,
    )
    fp = research_plan_fingerprint(**fields)
    plan_id, plan_hash = build_research_plan_id(fp)
    return ResearchPlan(research_plan_id=plan_id, plan_hash=plan_hash, created_at="t", created_by="radu", **fields)


def test_run_stage_refuses_to_run_a_single_session_for_a_rejected_plan():
    """An INVALID plan (empty cohort opting into the new ranking metric it
    has no right to -- symmetric enforcement, GPT review round 3 finding
    #3) must never reach the session loop at all -- not even far enough
    to touch the calendar, the registry, or the PIT facade (accepted here
    as `conn=None`/`trading_calendar=None`, since neither is ever
    dereferenced before the plan-acceptance check fails)."""
    registry = HypothesisRegistry()
    plan = _build_old_family_plan([], RANKING_METRIC_STOP_MANAGED_V1)  # wrong: empty cohort must use the OLD metric
    signal = EntrySignal(security_id="SEC_ENG_GATE", strategy_variant_id="unused")
    with pytest.raises(PlanNotAcceptedError):
        run_stage(
            plan, registry, conn=None, zone=FORMATION_SELECTION, trading_calendar=None,
            entry_signals={("SEC_ENG_GATE", "unused", "2024-01-01"): signal},
            invalidation_observer=_never_invalidated,
        )


def test_run_stage_runs_the_engine_and_ties_signals_to_the_accepted_cohort(conn, now):
    """The mirror case: an ACCEPTED plan with a REAL STOP_MANAGED_
    INVALIDATION cohort, run against ITS OWN real calendar, lets
    `run_stage()` proceed all the way into the real session loop for a
    signal naming a variant FROM that cohort -- proven by it reaching an
    actual PIT read (no price data exists for this security at all, so the
    real entry path concludes in NO_ENTRY_BAR -- a genuine per-position
    rejection, never a gate-level one). Acceptance of the PLAN is not, by
    itself, authorization to run an ARBITRARY signal -- this variant is
    the one the accepted plan's own cohort actually names."""
    registry = HypothesisRegistry()
    hid, vid = build_registered_stop_managed_hypothesis(registry)
    plan, profile, calendar = build_accepted_stop_managed_plan([hid])
    sec = make_security(conn, "spec005:ENGINE_GATE_OK", now)  # registered, but NO price bars at all
    signal = EntrySignal(security_id=sec, strategy_variant_id=vid)
    result = run_stage(
        plan, registry, conn, FORMATION_SELECTION, calendar,
        entry_signals={(sec, vid, "2024-01-29"): signal}, invalidation_observer=_never_invalidated,
        stop_managed_profile=profile,
    )
    assert len(result.entry_dispositions) == 1
    assert result.entry_dispositions[0].disposition == ENTRY_NO_ENTRY_BAR


def test_run_stage_rejects_a_signal_for_a_variant_outside_the_accepted_plan_even_though_the_plan_itself_is_valid(conn, now):
    """The plan is genuinely ACCEPTED (its OWN cohort is a DIFFERENT
    hypothesis), but the signal points at a variant that was never part of
    it. `run_stage()` must not treat "the plan was accepted" as "any
    signal may run" -- this one is rejected, no PIT ever read for it."""
    registry = HypothesisRegistry()
    hid_in_cohort, _vid_in_cohort = build_registered_stop_managed_hypothesis(registry, signature_id="SIG_IN_COHORT")
    _hid_outside, vid_outside = build_registered_stop_managed_hypothesis(registry, signature_id="SIG_OUTSIDE")
    plan, profile, calendar = build_accepted_stop_managed_plan([hid_in_cohort])  # does NOT include hid_outside
    signal = EntrySignal(security_id="SEC_ENG_OFFPLAN", strategy_variant_id=vid_outside)
    result = run_stage(
        plan, registry, conn, FORMATION_SELECTION, calendar,
        entry_signals={("SEC_ENG_OFFPLAN", vid_outside, "2024-01-29"): signal}, invalidation_observer=_never_invalidated,
        stop_managed_profile=profile,
    )
    assert result.entry_dispositions[0].disposition == ENTRY_VARIANT_NOT_IN_ACCEPTED_COHORT


# --------------------------------------------------------------------------
# Session Engine & Integration review, round 2, finding #1: the executed
# stage must be tied to the PLAN'S OWN declared zone periods -- never an
# independently constructed boundary/calendar/session list that disagrees
# with them (e.g. treating April as this plan's FORMATION_SELECTION when
# the plan's own formation_start/formation_end say January).
# --------------------------------------------------------------------------

def test_run_stage_rejects_a_trading_calendar_that_does_not_belong_to_the_plan(conn, now):
    registry = HypothesisRegistry()
    hid, vid = build_registered_stop_managed_hypothesis(registry)
    plan, profile, _matching_calendar = build_accepted_stop_managed_plan([hid])
    _other_hid, _other_vid = build_registered_stop_managed_hypothesis(registry, signature_id="SIG_UNRELATED")
    _other_plan, _other_profile, unrelated_calendar = build_accepted_stop_managed_plan(
        [hid], formation_start="2025-06-01", formation_end="2025-06-30",
        validation_start="2025-07-01", validation_end="2025-07-31", locked_oos_start="2025-08-01",
    )
    signal = EntrySignal(security_id="SEC_X", strategy_variant_id=vid)
    with pytest.raises(ValueError, match="does not match"):
        run_stage(
            plan, registry, conn, FORMATION_SELECTION, unrelated_calendar,
            entry_signals={("SEC_X", vid, "2024-01-01"): signal}, invalidation_observer=_never_invalidated,
            stop_managed_profile=profile,
        )


def test_run_stage_never_executes_sessions_outside_the_plans_own_formation_zone(conn, now):
    """The plan's own Formation zone is January (the fixture default).
    The calendar handed to `run_stage()` is intentionally WIDER, covering
    through April -- a REAL trading session exists in April. A signal
    dated in April must NEVER be evaluated when run against
    FORMATION_SELECTION (no disposition at all -- it was never part of
    the executed stage); a signal dated within January (the true
    Formation zone) DOES reach the real entry path."""
    registry = HypothesisRegistry()
    hid, vid = build_registered_stop_managed_hypothesis(registry)
    plan, profile, calendar = build_accepted_stop_managed_plan([hid], coverage_end="2024-04-30")
    april_signal_date = "2024-04-01"
    assert april_signal_date in calendar.session_dates  # a real session -- just outside the plan's Formation zone
    january_signal_date = "2024-01-29"

    sec_april = make_security(conn, "spec005:ENGINE_ZONE_APRIL", now)
    sec_jan = make_security(conn, "spec005:ENGINE_ZONE_JAN", now)  # no price bars -- proves the real path was reached

    entry_signals = {
        (sec_april, vid, april_signal_date): EntrySignal(security_id=sec_april, strategy_variant_id=vid),
        (sec_jan, vid, january_signal_date): EntrySignal(security_id=sec_jan, strategy_variant_id=vid),
    }
    result = run_stage(
        plan, registry, conn, FORMATION_SELECTION, calendar,
        entry_signals=entry_signals, invalidation_observer=_never_invalidated, stop_managed_profile=profile,
    )
    dispositions_by_sec = {d.security_id: d for d in result.entry_dispositions}
    assert sec_april not in dispositions_by_sec  # April was never part of the executed FORMATION_SELECTION stage
    assert sec_jan in dispositions_by_sec  # January correctly was
    assert dispositions_by_sec[sec_jan].disposition == ENTRY_NO_ENTRY_BAR


# --------------------------------------------------------------------------
# Session Engine & Integration review, round 2, finding #2: session_dates
# must be strictly increasing with no duplicates -- checked at
# SessionEngine construction, regardless of caller.
# --------------------------------------------------------------------------

def test_session_dates_out_of_order_is_refused_at_construction():
    with pytest.raises(ValueError, match="strictly increasing"):
        SessionEngine(
            pit=_EmptyAccess(), session_dates=("2024-05-02", "2024-05-01"), registry=HypothesisRegistry(),
            accepted_hypothesis_ids=frozenset(), entry_signals={}, invalidation_observer=_never_invalidated,
            cost_assumptions=_ZERO_COSTS,
        )


def test_duplicate_session_dates_is_refused_at_construction():
    with pytest.raises(ValueError, match="strictly increasing"):
        SessionEngine(
            pit=_EmptyAccess(), session_dates=("2024-05-01", "2024-05-01", "2024-05-02"), registry=HypothesisRegistry(),
            accepted_hypothesis_ids=frozenset(), entry_signals={}, invalidation_observer=_never_invalidated,
            cost_assumptions=_ZERO_COSTS,
        )


# --------------------------------------------------------------------------
# Session Engine & Integration review, round 1, findings #2 and #3: a
# session whose own bar is missing or incomplete must be recorded as a
# persistent gap (never silently skipped), and the stage's final mark must
# come from the LAST session actually run, with its own date checked --
# never a stale close carried forward from an earlier session.
# --------------------------------------------------------------------------

class _UnboundedAccess:
    """Same stand-in every other Batch 3 test uses (test_22/25/34):
    exercises the session engine directly against a real conn, bypassing
    Batch 2's own StageAccessBoundary machinery."""
    def __init__(self, conn):
        self.conn = conn

    def get_price_series_as_of(self, security_id, as_of):
        return pit_module.get_price_series_as_of(self.conn, security_id, as_of)

    def get_corporate_actions_as_of(self, security_id, as_of):
        return pit_module.get_corporate_actions_as_of(self.conn, security_id, as_of)


def _insert_bars(conn, security_id, now, rows):
    """`rows`: iterable of (date, open, high, low, close), any of which
    may be `None` to simulate incomplete OHLC for that session."""
    repo.insert_price_bars(conn, [
        PriceBar(
            security_id=security_id, date=d, raw_open=o, raw_high=h, raw_low=l, raw_close=c,
            raw_volume=1000, source_provider="manual", ingestion_timestamp=now,
        )
        for d, o, h, l, c in rows
    ])


_VOL_CFG_3 = {"atr_window": 3, "bb_window": 3, "bb_num_std": 2.0, "realized_vol_window": 3}


def _flat_signal_and_engine(conn, now, seed, rows, session_dates, direction="LONG", cost_assumptions=None):
    """Common scaffolding: one Control-variant STOP_MANAGED position
    entered at the first session, held with no exit trigger (stop far
    below/above every inserted low/high) for the rest of the run. Returns
    (sec, result) -- `sec` is the REAL security_id `make_security()`
    assigns (never the raw `seed` string itself)."""
    registry = HypothesisRegistry()
    hid, vid = build_registered_stop_managed_hypothesis(registry, direction=direction, k=2.0)
    sec = make_security(conn, seed, now)
    _insert_bars(conn, sec, now, rows)
    signal = EntrySignal(security_id=sec, strategy_variant_id=vid)
    engine = SessionEngine(
        pit=_UnboundedAccess(conn), session_dates=session_dates, registry=registry,
        accepted_hypothesis_ids=frozenset({hid}), entry_signals={(sec, vid, session_dates[0]): signal},
        invalidation_observer=_never_invalidated, cost_assumptions=cost_assumptions or _ZERO_COSTS,
        volatility_config=_VOL_CFG_3,
    )
    return sec, engine.run()


def test_missing_bar_marks_trailing_path_incomplete_permanently(conn, now):
    """D1..D4 flat (entry D0->D1), D2 has NO bar at all, D3/D4 recover with
    full, ordinary bars. Pas 3' (and the close(t) trailing update) could
    not run for D2 -- a real stop/target breach could have gone unnoticed
    -- so the position must carry `trailing_path_incomplete=True`
    PERMANENTLY, even though D3/D4's own data is perfectly fine (recovery
    does not repair the gap retroactively)."""
    seed = "spec005:ENGINE_MISSING_BAR"
    rows = [
        ("2024-06-01", 100.0, 104.0, 96.0, 100.0),  # D0 (signal day, needs an ATR window)
        ("2024-05-31", 100.0, 104.0, 96.0, 100.0),
        ("2024-05-30", 100.0, 104.0, 96.0, 100.0),
        ("2024-06-02", 100.0, 102.0, 98.0, 100.0),  # D1: entry
        # D2 ("2024-06-03"): NO bar at all.
        ("2024-06-04", 100.0, 102.0, 98.0, 100.0),  # D3: recovers
        ("2024-06-05", 100.0, 102.0, 98.0, 100.0),  # D4
    ]
    session_dates = ("2024-06-01", "2024-06-02", "2024-06-03", "2024-06-04", "2024-06-05")
    sec, result = _flat_signal_and_engine(conn, now, seed, rows, session_dates)
    assert len(result.positions) == 1
    pos = result.positions[0]
    assert pos.closed is False
    assert pos.trailing_path_incomplete is True


def test_incomplete_ohlc_marks_trailing_path_incomplete_permanently(conn, now):
    """Same shape, but D2 HAS a bar -- with `low=None` (incomplete OHLC,
    not an absent session). Must be treated identically to a missing bar:
    Pas 3' cannot check the stop/target without a low, so the gap is
    exactly as real."""
    seed = "spec005:ENGINE_INCOMPLETE_OHLC"
    rows = [
        ("2024-06-01", 100.0, 104.0, 96.0, 100.0),
        ("2024-05-31", 100.0, 104.0, 96.0, 100.0),
        ("2024-05-30", 100.0, 104.0, 96.0, 100.0),
        ("2024-06-02", 100.0, 102.0, 98.0, 100.0),  # D1: entry
        ("2024-06-03", 100.0, 102.0, None, 100.0),  # D2: low missing
        ("2024-06-04", 100.0, 102.0, 98.0, 100.0),
        ("2024-06-05", 100.0, 102.0, 98.0, 100.0),
    ]
    session_dates = ("2024-06-01", "2024-06-02", "2024-06-03", "2024-06-04", "2024-06-05")
    sec, result = _flat_signal_and_engine(conn, now, seed, rows, session_dates)
    assert len(result.positions) == 1
    pos = result.positions[0]
    assert pos.closed is False
    assert pos.trailing_path_incomplete is True


def test_final_close_from_a_stale_earlier_session_is_never_used_as_the_mark(conn, now):
    """The stage's declared last session (D3) has NO bar at all -- the
    security's last AVAILABLE close is from D2. `final_closes` must be
    `None` for this security, never D2's stale value silently reused as
    if it were D3's own close."""
    seed = "spec005:ENGINE_STALE_MARK"
    rows = [
        ("2024-06-01", 100.0, 104.0, 96.0, 100.0),
        ("2024-05-31", 100.0, 104.0, 96.0, 100.0),
        ("2024-05-30", 100.0, 104.0, 96.0, 100.0),
        ("2024-06-02", 100.0, 102.0, 98.0, 100.0),  # D1: entry
        ("2024-06-03", 100.0, 102.0, 98.0, 101.0),  # D2: last AVAILABLE close = 101
        # D3 ("2024-06-04"): NO bar at all -- the stage's own declared last session.
    ]
    session_dates = ("2024-06-01", "2024-06-02", "2024-06-03", "2024-06-04")
    sec, result = _flat_signal_and_engine(conn, now, seed, rows, session_dates)
    assert result.final_closes[sec] is None


# --------------------------------------------------------------------------
# Session Engine & Integration review, round 1, finding #1: entry slippage
# (CostAssumptions.slippage_entry_bps) was never applied -- entry_fill_price
# was the raw open, unconditionally. `apply_entry_slippage()` (costs.py)
# must run BEFORE the position is built, so F_e itself (and everything
# derived from it: S_initial, and the aggregate return) reflects it.
# --------------------------------------------------------------------------

def test_entry_slippage_long_shifts_fill_protection_and_aggregate_return(conn, now):
    """LONG, 1% entry slippage: F_e = 100*(1+0.01) = 101 (a WORSE, higher,
    buy price) -- S_initial = 101 - 2*8 = 85 (not 100-16=84). Two sessions
    only (signal + entry/close, same day) so no further ATR drift muddies
    the numbers. Still-open remainder at D1's own close (100) gives a
    fully hand-verifiable aggregate return."""
    seed = "spec005:ENGINE_ENTRY_SLIPPAGE_LONG"
    rows = [
        ("2024-07-01", 100.0, 104.0, 96.0, 100.0),  # D0 signal day
        ("2024-06-29", 100.0, 104.0, 96.0, 100.0),
        ("2024-06-28", 100.0, 104.0, 96.0, 100.0),
        ("2024-07-02", 100.0, 104.0, 96.0, 100.0),  # D1: entry + close, same TR=8 as lead-in -- no ATR drift
    ]
    session_dates = ("2024-07-01", "2024-07-02")
    costs = CostAssumptions(commission_entry_rate=0.0, commission_exit_rate=0.0, slippage_entry_bps=100.0, slippage_exit_bps=0.0, borrow_annual_rate=0.0)
    sec, result = _flat_signal_and_engine(conn, now, seed, rows, session_dates, direction="LONG", cost_assumptions=costs)
    assert len(result.positions) == 1
    pos = result.positions[0]
    assert pos.entry_fill_price == pytest.approx(101.0)
    assert pos.active_stop == pytest.approx(85.0)  # 101 - 2*8, never the unslipped 100-2*8=84
    assert result.final_closes[sec] == pytest.approx(100.0)

    outcome = classify_position(pos, stage_end_reached=True, final_mark_available=True)
    assert outcome.evaluability == EVALUABILITY_EVALUABLE
    (net_return,) = evaluate_stage_results([pos], [outcome], costs, session_dates[-1], result.final_closes)
    assert net_return == pytest.approx(-1.0 / 101.0)


def test_entry_slippage_short_shifts_fill_protection_and_aggregate_return(conn, now):
    """SHORT, 1% entry slippage: F_e = 100*(1-0.01) = 99 (a WORSE, lower,
    sell-to-open price) -- S_initial(short) = 99 + 2*8 = 115 (not
    100+16=116... note the sign: worse for a short is a LOWER fill, which
    makes S_initial LOWER too, tighter than the unslipped 116)."""
    seed = "spec005:ENGINE_ENTRY_SLIPPAGE_SHORT"
    rows = [
        ("2024-07-01", 100.0, 104.0, 96.0, 100.0),
        ("2024-06-29", 100.0, 104.0, 96.0, 100.0),
        ("2024-06-28", 100.0, 104.0, 96.0, 100.0),
        ("2024-07-02", 100.0, 104.0, 96.0, 100.0),  # same TR=8 as lead-in -- no ATR drift
    ]
    session_dates = ("2024-07-01", "2024-07-02")
    costs = CostAssumptions(commission_entry_rate=0.0, commission_exit_rate=0.0, slippage_entry_bps=100.0, slippage_exit_bps=0.0, borrow_annual_rate=0.0)
    sec, result = _flat_signal_and_engine(conn, now, seed, rows, session_dates, direction="SHORT", cost_assumptions=costs)
    assert len(result.positions) == 1
    pos = result.positions[0]
    assert pos.entry_fill_price == pytest.approx(99.0)
    assert pos.active_stop == pytest.approx(115.0)
    assert result.final_closes[sec] == pytest.approx(100.0)

    outcome = classify_position(pos, stage_end_reached=True, final_mark_available=True)
    (net_return,) = evaluate_stage_results([pos], [outcome], costs, session_dates[-1], result.final_closes)
    assert net_return == pytest.approx(-1.0 / 99.0)


# --------------------------------------------------------------------------
# Session Engine & Integration review, round 1, finding #4: stage_end_date
# must actually bound the loop -- construction must refuse a session_dates
# list reaching past it, and must refuse a stage_end_date reaching past the
# PIT facade's OWN authorized boundary, BEFORE a single session runs.
# --------------------------------------------------------------------------

class _BoundaryStub:
    def __init__(self, max_as_of):
        self.max_as_of = max_as_of


class _AccessWithBoundary(_EmptyAccess):
    """Same PIT-call-forbidding stand-in as `_EmptyAccess`, but exposing a
    `.boundary.max_as_of` -- exactly the shape a real `BoundedPITAccess`
    has -- so the engine's own boundary-concordance check has something to
    compare against."""
    def __init__(self, max_as_of):
        self.boundary = _BoundaryStub(max_as_of)


def test_session_dates_beyond_stage_end_date_is_refused_at_construction():
    """Repro from review round 1: stage_end_date=2024-05-02, but
    session_dates reaches 2024-05-03 -- must be refused immediately, no
    session ever run, no PIT read ever attempted."""
    signal = EntrySignal(security_id="SEC_ENG_BOUND", strategy_variant_id="unused")
    with pytest.raises(ValueError, match="beyond stage_end_date"):
        SessionEngine(
            pit=_EmptyAccess(), session_dates=("2024-05-01", "2024-05-02", "2024-05-03"),
            registry=HypothesisRegistry(), accepted_hypothesis_ids=frozenset(),
            entry_signals={("SEC_ENG_BOUND", "unused", "2024-05-01"): signal}, invalidation_observer=_never_invalidated,
            cost_assumptions=_ZERO_COSTS, stage_end_date="2024-05-02",
        )


def test_stage_end_date_beyond_the_pit_facades_own_boundary_is_refused_at_construction():
    """Even with `session_dates` itself staying within `stage_end_date`,
    a `stage_end_date` that reaches past the REAL PIT facade's own
    authorized `boundary.max_as_of` must also be refused -- the engine and
    the facade it reads through must agree on the stage limit."""
    signal = EntrySignal(security_id="SEC_ENG_BOUND2", strategy_variant_id="unused")
    with pytest.raises(ValueError, match="exceeds this pit's own authorized boundary"):
        SessionEngine(
            pit=_AccessWithBoundary(max_as_of="2024-05-01"), session_dates=("2024-05-01", "2024-05-02"),
            registry=HypothesisRegistry(), accepted_hypothesis_ids=frozenset(),
            entry_signals={("SEC_ENG_BOUND2", "unused", "2024-05-01"): signal}, invalidation_observer=_never_invalidated,
            cost_assumptions=_ZERO_COSTS, stage_end_date="2024-05-02",
        )


# --------------------------------------------------------------------------
# Session Engine & Integration review, round 2, finding #3: position
# bookkeeping must be keyed by (security_id, strategy_variant_id), never
# bare security_id -- two DIFFERENT variants trading the SAME security must
# both open independent positions, neither suppressing the other.
# --------------------------------------------------------------------------

def test_two_variants_on_the_same_security_same_day_both_open_independent_positions(conn, now):
    registry = HypothesisRegistry()
    hid_a, vid_a = build_registered_stop_managed_hypothesis(registry, k=2.0, signature_id="SIG_VARA")
    hid_b, vid_b = build_registered_stop_managed_hypothesis(registry, k=3.0, signature_id="SIG_VARB")
    sec = make_security(conn, "spec005:ENGINE_TWO_VARIANTS", now)
    rows = [
        ("2024-08-01", 100.0, 104.0, 96.0, 100.0),  # D0 signal day
        ("2024-07-30", 100.0, 104.0, 96.0, 100.0),
        ("2024-07-29", 100.0, 104.0, 96.0, 100.0),
        ("2024-08-02", 100.0, 104.0, 96.0, 100.0),  # D1: entry, same TR=8 -- no ATR drift
    ]
    _insert_bars(conn, sec, now, rows)
    session_dates = ("2024-08-01", "2024-08-02")
    entry_signals = {
        (sec, vid_a, session_dates[0]): EntrySignal(security_id=sec, strategy_variant_id=vid_a),
        (sec, vid_b, session_dates[0]): EntrySignal(security_id=sec, strategy_variant_id=vid_b),
    }
    engine = SessionEngine(
        pit=_UnboundedAccess(conn), session_dates=session_dates, registry=registry,
        accepted_hypothesis_ids=frozenset({hid_a, hid_b}), entry_signals=entry_signals,
        invalidation_observer=_never_invalidated, cost_assumptions=_ZERO_COSTS, volatility_config=_VOL_CFG_3,
    )
    result = engine.run()

    executed = [d for d in result.entry_dispositions if d.disposition == ENTRY_EXECUTED]
    assert len(executed) == 2
    assert {d.strategy_variant_id for d in executed} == {vid_a, vid_b}

    assert len(result.positions) == 2
    pos_by_variant = {p.strategy_variant_id: p for p in result.positions}
    assert set(pos_by_variant) == {vid_a, vid_b}
    assert all(p.security_id == sec for p in result.positions)
    # k=2 vs k=3 on the identical ATR=8 basis -> different active_stop --
    # proof these are two REALLY independent positions, not one shared/
    # overwritten object.
    assert pos_by_variant[vid_a].active_stop == pytest.approx(100.0 - 2 * 8)
    assert pos_by_variant[vid_b].active_stop == pytest.approx(100.0 - 3 * 8)
    assert pos_by_variant[vid_a].active_stop != pos_by_variant[vid_b].active_stop
