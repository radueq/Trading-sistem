"""TEST 32 -- STOP_MANAGED_INVALIDATION's mandatory ResearchPlan identity
and selection-metric requirements (docs/spec005_exit_amendment_v1.0.md,
ACCEPTED, sections 7 and 11; GPT review round 2, finding #7)."""
import dataclasses

import pytest

from backtest.exits.entities import build_stop_managed_execution_semantics_profile_v1
from backtest.exits.plan_integration import validate_stop_managed_plan_requirements
from backtest.models.entities import (
    RANKING_METRIC_STOP_MANAGED_V1,
    RANKING_METRIC_V1,
    SelectionRule,
    build_research_plan_id,
    research_plan_fingerprint,
    validate_selection_rule,
    verify_research_plan_identity,
)


def test_old_plan_unaffected_by_a_cohort_without_stop_managed_variants(pit_research_plan):
    ok, errors = validate_stop_managed_plan_requirements(pit_research_plan, cohort_includes_stop_managed_invalidation=False)
    assert ok, errors
    assert pit_research_plan.stop_managed_execution_semantics_profile_id is None


def test_stop_managed_cohort_requires_both_the_profile_id_and_the_new_ranking_metric(pit_research_plan):
    ok, errors = validate_stop_managed_plan_requirements(pit_research_plan, cohort_includes_stop_managed_invalidation=True)
    assert not ok
    assert any("stop_managed_execution_semantics_profile_id" in e for e in errors)
    assert any("ranking_metric" in e for e in errors)


def test_stop_managed_cohort_with_both_requirements_set_is_valid(pit_research_plan):
    profile = build_stop_managed_execution_semantics_profile_v1()
    new_rule = dataclasses.replace(pit_research_plan.selection_rule, ranking_metric=RANKING_METRIC_STOP_MANAGED_V1)
    plan = dataclasses.replace(
        pit_research_plan, selection_rule=new_rule,
        stop_managed_execution_semantics_profile_id=profile.profile_id,
    )
    ok, errors = validate_stop_managed_plan_requirements(plan, cohort_includes_stop_managed_invalidation=True)
    assert ok, errors


def test_old_plan_fingerprint_is_byte_identical_to_before_this_field_existed(pit_research_plan):
    """The new optional field must never change an existing plan's
    identity -- recomputing the fingerprint with the new parameter
    OMITTED (defaults to None) must reproduce the SAME research_plan_id/
    plan_hash the fixture (unaware of this field) already produced."""
    plan = pit_research_plan
    fp_without_new_param = research_plan_fingerprint(
        plan.formation_start, plan.formation_end, plan.validation_start, plan.validation_end,
        plan.locked_oos_start, plan.selection_folds, plan.hypothesis_cohort_ids,
        plan.trading_calendar_id, plan.benchmark_security_id, plan.execution_semantics_profile_id,
        plan.selection_rule, plan.cost_assumptions, plan.exposure_manifest,
    )
    expected_id, expected_hash = build_research_plan_id(fp_without_new_param)
    assert plan.research_plan_id == expected_id
    assert plan.plan_hash == expected_hash

    ok, errors = verify_research_plan_identity(plan)
    assert ok, errors


def test_setting_the_new_field_changes_the_plan_identity(pit_research_plan):
    """Once populated, the new field DOES participate in identity --
    never silently ignored (mirrors PATCH #004-C's own _exit_fp()
    discipline: family-conditioned, but load-bearing once present)."""
    profile = build_stop_managed_execution_semantics_profile_v1()
    fp_with = research_plan_fingerprint(
        pit_research_plan.formation_start, pit_research_plan.formation_end, pit_research_plan.validation_start,
        pit_research_plan.validation_end, pit_research_plan.locked_oos_start, pit_research_plan.selection_folds,
        pit_research_plan.hypothesis_cohort_ids, pit_research_plan.trading_calendar_id,
        pit_research_plan.benchmark_security_id, pit_research_plan.execution_semantics_profile_id,
        pit_research_plan.selection_rule, pit_research_plan.cost_assumptions, pit_research_plan.exposure_manifest,
        profile.profile_id,
    )
    assert fp_with != research_plan_fingerprint(
        pit_research_plan.formation_start, pit_research_plan.formation_end, pit_research_plan.validation_start,
        pit_research_plan.validation_end, pit_research_plan.locked_oos_start, pit_research_plan.selection_folds,
        pit_research_plan.hypothesis_cohort_ids, pit_research_plan.trading_calendar_id,
        pit_research_plan.benchmark_security_id, pit_research_plan.execution_semantics_profile_id,
        pit_research_plan.selection_rule, pit_research_plan.cost_assumptions, pit_research_plan.exposure_manifest,
    )


def test_validate_selection_rule_accepts_both_ranking_metrics_rejects_a_third():
    old_rule = SelectionRule(minimum_executed_trades=1, minimum_evaluable_trades=1, minimum_evaluable_ratio=0.5)
    assert old_rule.ranking_metric == RANKING_METRIC_V1
    ok, errors = validate_selection_rule(old_rule)
    assert ok, errors

    new_rule = dataclasses.replace(old_rule, ranking_metric=RANKING_METRIC_STOP_MANAGED_V1)
    ok, errors = validate_selection_rule(new_rule)
    assert ok, errors

    bogus_rule = dataclasses.replace(old_rule, ranking_metric="SHARPE_RATIO")
    ok, errors = validate_selection_rule(bogus_rule)
    assert not ok
    assert any("ranking_metric" in e for e in errors)
