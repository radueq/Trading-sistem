"""Spec #005 Batch 3 -- wires STOP_MANAGED_INVALIDATION's mandatory
identity/selection-metric requirements into `ResearchPlan` (docs/
spec005_exit_amendment_v1.0.md, ACCEPTED, sections 7 and 11).

GPT review round 2, finding #7: these two obligations do not depend on
the not-yet-built multi-security session engine -- `ResearchPlan`/
`SelectionRule` already exist (Batch 1/2), so leaving them disconnected
was a real gap in the delivery, not a consequence of missing
infrastructure. This module is the cross-check; `backtest.models.entities`
itself stays family-agnostic (it accepts, but never requires, the new
optional field/ranking_metric value -- see that module's own comments).
"""
from __future__ import annotations

from backtest.models.entities import RANKING_METRIC_STOP_MANAGED_V1, ResearchPlan


def validate_stop_managed_plan_requirements(
    plan: ResearchPlan, cohort_includes_stop_managed_invalidation: bool,
) -> tuple[bool, tuple[str, ...]]:
    """Section 7: "Obligatoriu pentru identitate: orice ResearchPlan/
    rulare cu variante STOP_MANAGED_INVALIDATION include AMBELE profiluri
    ... în identitatea semantică. Nu opțional." Section 11: "ranking_metric
    = MEDIAN_NET_RETURN_TO_EXIT_OR_STAGE_END -- obligatoriu pentru orice
    ResearchPlan a cărui cohortă include variante STOP_MANAGED_
    INVALIDATION... Planurile compuse exclusiv din familii vechi păstrează
    MEDIAN_NET_RETURN neschimbat."

    `cohort_includes_stop_managed_invalidation` is the caller's own
    determination from the plan's actual hypothesis cohort (this module
    never inspects `StrategyVariant`/hypothesis internals itself --
    `backtest.exits` deliberately never imports the `hypothesis` package,
    same isolation discipline as `backtest.models.entities`'s own module
    docstring). A plan whose cohort does NOT include such variants is
    never REQUIRED to carry the new field/metric -- old-family-only plans
    are untouched, byte-for-byte, per section 7/11 both."""
    if not cohort_includes_stop_managed_invalidation:
        return True, ()
    errors: list[str] = []
    if plan.stop_managed_execution_semantics_profile_id is None:
        errors.append(
            "plan.stop_managed_execution_semantics_profile_id is required whenever the hypothesis "
            "cohort includes STOP_MANAGED_INVALIDATION variants (amendment section 7 -- not optional)"
        )
    if plan.selection_rule.ranking_metric != RANKING_METRIC_STOP_MANAGED_V1:
        errors.append(
            f"selection_rule.ranking_metric must be {RANKING_METRIC_STOP_MANAGED_V1!r} whenever the "
            f"hypothesis cohort includes STOP_MANAGED_INVALIDATION variants (amendment section 11), "
            f"got {plan.selection_rule.ranking_metric!r}"
        )
    return (not errors, tuple(errors))
