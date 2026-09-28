"""TEST 33 -- the SessionEngine's own orchestration concerns that no
per-position unit test can exercise: the SUPPRESSED_STAGE_BOUNDARY
disposition (amendment section 2, item 1 -- entirely an engine-level
concern, since it fires before any per-position mechanism is ever
reached) and `run_stage()`'s mandatory plan-acceptance gate (Spec #005
Exit Amendment review, "Session Engine & Integration" round, obligation
#2 -- `accept_research_plan()` must sit at a real, non-test-only call
site). The full Pas 0-6 session order itself, across a real multi-security
PIT universe, is TEST 34's job -- this file is deliberately narrower.
"""
from __future__ import annotations

import pytest

from hypothesis.registry.hypotheses import HypothesisRegistry

from backtest.exits.engine import (
    EntryDisposition,
    EntrySignal,
    PlanNotAcceptedError,
    SessionEngine,
    run_stage,
)
from backtest.exits.entities import ENTRY_SUPPRESSED_STAGE_BOUNDARY
from backtest.models.entities import (
    RANKING_METRIC_STOP_MANAGED_V1,
    RANKING_METRIC_V1,
    CostAssumptions,
    ExposureManifest,
    ResearchPlan,
    SelectionFold,
    SelectionRule,
    build_execution_semantics_profile_v1,
    build_research_plan_id,
    research_plan_fingerprint,
)


class _EmptyAccess:
    """No position ever reaches Pas 0-5 in these tests -- the only PIT
    calls that could happen are the ones SUPPRESSED_STAGE_BOUNDARY must
    NEVER make. Raising loudly on any call makes that assertion
    self-enforcing rather than merely implied by the disposition."""
    def get_price_series_as_of(self, security_id, as_of):
        raise AssertionError(f"SUPPRESSED_STAGE_BOUNDARY must never read a price: get_price_series_as_of({security_id!r}, {as_of!r})")

    def get_corporate_actions_as_of(self, security_id, as_of):
        raise AssertionError(f"SUPPRESSED_STAGE_BOUNDARY must never read corporate actions: get_corporate_actions_as_of({security_id!r}, {as_of!r})")


def _never_invalidated(position, session_date):
    return "VALID_HOLD"


def test_signal_on_the_stage_last_session_is_suppressed_without_reading_any_price():
    """A signal recorded at the close of the STAGE'S OWN LAST session has
    no in-stage session left for its NEXT_SESSION_OPEN entry -- amendment
    section 2, item 1: rejected via SUPPRESSED_STAGE_BOUNDARY, with no
    price ever read for it at all (not merely 'entry not opened')."""
    session_dates = ("2024-05-01", "2024-05-02", "2024-05-03")
    last_session = session_dates[-1]
    signal = EntrySignal(security_id="SEC_ENG_SUPPRESSED", direction="LONG", k=2.0)
    engine = SessionEngine(
        pit=_EmptyAccess(), session_dates=session_dates,
        entry_signals={("SEC_ENG_SUPPRESSED", last_session): signal},
        invalidation_observer=_never_invalidated,
    )
    result = engine.run()
    assert result.positions == ()
    assert result.entry_dispositions == (
        EntryDisposition(
            security_id="SEC_ENG_SUPPRESSED", signal_date=last_session,
            entry_date="<beyond authorized stage>", disposition=ENTRY_SUPPRESSED_STAGE_BOUNDARY,
        ),
    )


def test_a_signal_on_any_earlier_session_is_not_suppressed_by_this_rule():
    """The SAME signal, one session earlier, DOES have an in-stage next
    session -- it must reach the real entry path (and, with no price data
    behind `_EmptyAccess`, fail on an actual PIT read instead of being
    silently suppressed) -- proving the suppression above is genuinely
    about the stage boundary, not a blanket behavior."""
    session_dates = ("2024-05-01", "2024-05-02", "2024-05-03")
    signal = EntrySignal(security_id="SEC_ENG_NOTSUPPRESSED", direction="LONG", k=2.0)
    engine = SessionEngine(
        pit=_EmptyAccess(), session_dates=session_dates,
        entry_signals={("SEC_ENG_NOTSUPPRESSED", session_dates[0]): signal},
        invalidation_observer=_never_invalidated,
    )
    with pytest.raises(AssertionError, match="get_price_series_as_of"):
        engine.run()


def _build_plan(hypothesis_cohort_ids, ranking_metric) -> ResearchPlan:
    """Trimmed down from test_32's own `_build_plan()` -- these tests only
    need `run_stage()`'s gate to fire correctly, never a real
    STOP_MANAGED_INVALIDATION cohort, so an empty `hypothesis_cohort_ids`
    with the matching old ranking_metric is the minimal ACCEPTED case."""
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
    """The core of obligation #2: an INVALID plan (here, an empty cohort
    opting into the new ranking metric it has no right to -- symmetric
    enforcement, GPT review round 3 finding #3) must never reach the
    session loop at all -- not even far enough to touch the PIT facade."""
    registry = HypothesisRegistry()  # empty -- no hypotheses registered
    plan = _build_plan([], RANKING_METRIC_STOP_MANAGED_V1)  # wrong: empty cohort must use the OLD metric
    signal = EntrySignal(security_id="SEC_ENG_GATE", direction="LONG", k=2.0)
    with pytest.raises(PlanNotAcceptedError):
        run_stage(
            plan, registry, pit=_EmptyAccess(), session_dates=("2024-05-01", "2024-05-02"),
            entry_signals={("SEC_ENG_GATE", "2024-05-01"): signal}, invalidation_observer=_never_invalidated,
        )


def test_run_stage_runs_the_engine_once_the_plan_is_accepted():
    """The mirror case: an ACCEPTED plan lets `run_stage()` proceed all
    the way into the real session loop -- proven here by it reaching (and
    failing on) an actual PIT read, exactly like calling `SessionEngine`
    directly would, rather than being silently swallowed by the gate."""
    registry = HypothesisRegistry()
    plan = _build_plan([], RANKING_METRIC_V1)  # correct: empty cohort, old metric -- accepted
    signal = EntrySignal(security_id="SEC_ENG_GATE_OK", direction="LONG", k=2.0)
    with pytest.raises(AssertionError, match="get_price_series_as_of"):
        run_stage(
            plan, registry, pit=_EmptyAccess(), session_dates=("2024-05-01", "2024-05-02"),
            entry_signals={("SEC_ENG_GATE_OK", "2024-05-01"): signal}, invalidation_observer=_never_invalidated,
        )
