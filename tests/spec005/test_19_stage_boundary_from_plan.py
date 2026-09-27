"""TEST 19 -- StageAccessBoundary derived and verified from a
ResearchPlan (Spec #005 v1.0 SS3, Batch 2 patch rounds 2 and 3).

Batch 2 patch round-2 review (P1 finding #4): a bare
`StageAccessBoundary(FORMATION_SELECTION, "2099-12-31")` was accepted
with no check against anything -- forbidding the LOCKED_OOS zone LABEL
never stopped a FORMATION_SELECTION-labeled boundary from reaching into
the Locked OOS date range under a different label. `max_as_of` must
come from the plan's own already-validated zone dates, never a
caller-supplied string.

Batch 2 patch round-3 review (P1 finding #1): identity re-verification
alone only proves a plan's fields match its OWN claimed hash -- a plan
can have a perfectly self-consistent hash over OVERLAPPING zone dates
(e.g. validation_start before formation_end), which would let a
boundary derived from it reach data it was never supposed to. See
`test_a_plan_with_a_genuinely_computed_hash_but_invalid_zone_ordering_is_rejected`
below.
"""
import dataclasses

import pytest

from backtest.models.entities import (
    DEVELOPMENT_VALIDATION,
    FORMATION_SELECTION,
    LOCKED_OOS,
    OutOfScopeAccessError,
    StageBoundaryPlanMismatchError,
    build_research_plan_id,
    research_plan_fingerprint,
    verify_research_plan_identity,
)
from backtest.zones.boundaries import build_stage_access_boundary_from_plan


def test_formation_selection_boundary_is_derived_from_the_plans_formation_end(pit_research_plan):
    boundary = build_stage_access_boundary_from_plan(pit_research_plan, FORMATION_SELECTION)
    assert boundary.zone == FORMATION_SELECTION
    assert boundary.max_as_of == pit_research_plan.formation_end


def test_development_validation_boundary_is_derived_from_the_plans_validation_end(pit_research_plan):
    boundary = build_stage_access_boundary_from_plan(pit_research_plan, DEVELOPMENT_VALIDATION)
    assert boundary.zone == DEVELOPMENT_VALIDATION
    assert boundary.max_as_of == pit_research_plan.validation_end


def test_locked_oos_zone_is_rejected_by_the_plan_derived_factory(pit_research_plan):
    with pytest.raises(StageBoundaryPlanMismatchError):
        build_stage_access_boundary_from_plan(pit_research_plan, LOCKED_OOS)


def test_an_unknown_zone_is_rejected(pit_research_plan):
    with pytest.raises(StageBoundaryPlanMismatchError):
        build_stage_access_boundary_from_plan(pit_research_plan, "SOME_OTHER_ZONE")


def test_a_tampered_plan_is_rejected_before_any_boundary_is_derived(pit_research_plan):
    """The exact case the finding named: a plan whose formation_end has
    been swapped after freezing (e.g. to "2099-12-31") must never anchor
    a boundary -- catching that requires re-verifying the PLAN's own
    identity, not trusting whatever field value it happens to carry."""
    tampered = dataclasses.replace(pit_research_plan, formation_end="2099-12-31")
    with pytest.raises(StageBoundaryPlanMismatchError, match="identity verification"):
        build_stage_access_boundary_from_plan(tampered, FORMATION_SELECTION)


def test_the_derived_formation_boundary_cannot_reach_the_locked_oos_range(pit_research_plan):
    boundary = build_stage_access_boundary_from_plan(pit_research_plan, FORMATION_SELECTION)
    with pytest.raises(OutOfScopeAccessError):
        boundary.require_as_of_in_scope(pit_research_plan.locked_oos_start)


def test_the_derived_validation_boundary_cannot_reach_the_locked_oos_range(pit_research_plan):
    boundary = build_stage_access_boundary_from_plan(pit_research_plan, DEVELOPMENT_VALIDATION)
    with pytest.raises(OutOfScopeAccessError):
        boundary.require_as_of_in_scope(pit_research_plan.locked_oos_start)


def test_a_plan_with_a_genuinely_computed_hash_but_invalid_zone_ordering_is_rejected(pit_research_plan):
    """Round-3 finding #1: identity re-verification alone only proves a
    plan's fields match its OWN claimed hash -- it says nothing about
    whether those fields are economically sane. This plan's
    `validation_start` is set to (not after) `formation_end`, but its
    `research_plan_id`/`plan_hash` are recomputed from exactly those
    overlapping fields, so `verify_research_plan_identity()` alone would
    happily pass it."""
    fields = dict(
        formation_start=pit_research_plan.formation_start, formation_end=pit_research_plan.formation_end,
        validation_start=pit_research_plan.formation_start, validation_end=pit_research_plan.validation_end,
        locked_oos_start=pit_research_plan.locked_oos_start, selection_folds=pit_research_plan.selection_folds,
        hypothesis_cohort_ids=pit_research_plan.hypothesis_cohort_ids,
        trading_calendar_id=pit_research_plan.trading_calendar_id,
        benchmark_security_id=pit_research_plan.benchmark_security_id,
        execution_semantics_profile_id=pit_research_plan.execution_semantics_profile_id,
        selection_rule=pit_research_plan.selection_rule, cost_assumptions=pit_research_plan.cost_assumptions,
        exposure_manifest=pit_research_plan.exposure_manifest,
    )
    fp = research_plan_fingerprint(**fields)
    plan_id, plan_hash = build_research_plan_id(fp)
    invalid_plan = dataclasses.replace(pit_research_plan, research_plan_id=plan_id, plan_hash=plan_hash, **fields)

    ok, _ = verify_research_plan_identity(invalid_plan)
    assert ok, "the plan must be self-consistent (a genuinely computed hash) for this to be the right regression test"

    with pytest.raises(StageBoundaryPlanMismatchError, match="own zone dates fail"):
        build_stage_access_boundary_from_plan(invalid_plan, FORMATION_SELECTION)
