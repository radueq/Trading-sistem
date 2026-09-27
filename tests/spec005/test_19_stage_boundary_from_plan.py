"""TEST 19 -- StageAccessBoundary derived and verified from a
ResearchPlan (Spec #005 v1.0 SS3, Batch 2 patch round 2).

Batch 2 patch round-2 review (P1 finding #4): a bare
`StageAccessBoundary(FORMATION_SELECTION, "2099-12-31")` was accepted
with no check against anything -- forbidding the LOCKED_OOS zone LABEL
never stopped a FORMATION_SELECTION-labeled boundary from reaching into
the Locked OOS date range under a different label. `max_as_of` must
come from the plan's own already-validated zone dates, never a
caller-supplied string.
"""
import dataclasses

import pytest

from backtest.models.entities import (
    DEVELOPMENT_VALIDATION,
    FORMATION_SELECTION,
    LOCKED_OOS,
    OutOfScopeAccessError,
    StageBoundaryPlanMismatchError,
    build_stage_access_boundary_from_plan,
)


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
