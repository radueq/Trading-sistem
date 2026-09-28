"""Spec #005 Batch 3 -- the ResearchPlan acceptance gate for STOP_MANAGED_
INVALIDATION's mandatory identity/selection-metric requirements (docs/
spec005_exit_amendment_v1.0.md, ACCEPTED, sections 7 and 11).

GPT review round 3, finding #3: no ResearchPlan-acceptance gate of any
kind exists elsewhere in Batch 1/2 (only `backtest.models.entities.
verify_research_plan_identity()`, a self-consistency check, not a full
acceptance workflow). `accept_research_plan()` below IS that gate -- not
a helper meant to be called only from tests. It resolves the plan's
ACTUAL cohort from the hypothesis registry itself (never a caller-
asserted boolean or family-string list) and verifies the referenced
STOP_MANAGED profile against a real, independently-verified
`StopManagedExecutionSemanticsProfile` object, never a bare, unverified
id string accepted on faith. Enforcement is symmetric: an old-family-only
cohort is REQUIRED to keep the old ranking metric, exactly as a
STOP_MANAGED-including cohort is required to use the new one -- neither
side is a free choice.

This module imports `hypothesis.models.entities`/`hypothesis.registry.
hypotheses` directly -- `backtest.provenance.evaluation_run` already
establishes the precedent that a clearly-labeled, narrowly-scoped
`backtest` module may reuse `hypothesis` package internals (that
module's own docstring names its two approved reuses); this is the
Batch 3 equivalent; `backtest.models.entities` itself stays
family-agnostic and does not import either.
"""
from __future__ import annotations

from typing import Optional

from hypothesis.models.entities import ExitFamily
from hypothesis.registry.hypotheses import HypothesisRegistry

from backtest.exits.entities import (
    StopManagedExecutionSemanticsProfile,
    verify_stop_managed_execution_semantics_profile_v1,
)
from backtest.models.entities import (
    RANKING_METRIC_STOP_MANAGED_V1,
    RANKING_METRIC_V1,
    ResearchPlan,
    verify_research_plan_identity,
)


def accept_research_plan(
    plan: ResearchPlan, registry: HypothesisRegistry,
    stop_managed_profile: Optional[StopManagedExecutionSemanticsProfile] = None,
) -> tuple[bool, tuple[str, ...]]:
    """The obligatory acceptance gate for a ResearchPlan. Verifies
    self-consistency (`verify_research_plan_identity`) AND, resolving
    every `hypothesis_cohort_ids` entry to its REAL `StrategyVariant`s via
    `registry` itself:

    - section 11: a cohort that includes >=1 STOP_MANAGED_INVALIDATION
      variant MUST use `ranking_metric=MEDIAN_NET_RETURN_TO_EXIT_OR_
      STAGE_END`; a cohort that does NOT MUST keep the old
      `MEDIAN_NET_RETURN` -- symmetric, neither side is optional.
    - section 7: a cohort that includes such variants MUST carry a
      `stop_managed_execution_semantics_profile_id` that matches an
      ACTUAL, independently-verified `stop_managed_profile` object
      supplied to THIS call -- never a bare id string trusted on its own.

    A `hypothesis_cohort_ids` entry absent from `registry` is itself a
    rejection (an unresolvable cohort can never be accepted)."""
    errors: list[str] = []
    identity_ok, identity_errors = verify_research_plan_identity(plan)
    errors.extend(identity_errors)

    cohort_variants = []
    for hypothesis_id in plan.hypothesis_cohort_ids:
        hyp = registry.get(hypothesis_id)
        if hyp is None:
            errors.append(
                f"hypothesis_cohort_ids contains {hypothesis_id!r}, not found in the supplied registry "
                f"-- an unresolvable cohort can never be accepted"
            )
            continue
        cohort_variants.extend(registry.variants_for(hypothesis_id))

    cohort_includes_stop_managed = any(
        v.exit_hypothesis.exit_family == ExitFamily.STOP_MANAGED_INVALIDATION.value for v in cohort_variants
    )

    if cohort_includes_stop_managed:
        if plan.selection_rule.ranking_metric != RANKING_METRIC_STOP_MANAGED_V1:
            errors.append(
                f"selection_rule.ranking_metric must be {RANKING_METRIC_STOP_MANAGED_V1!r} -- the resolved "
                f"cohort includes STOP_MANAGED_INVALIDATION variants (amendment section 11), got "
                f"{plan.selection_rule.ranking_metric!r}"
            )
        if plan.stop_managed_execution_semantics_profile_id is None:
            errors.append(
                "plan.stop_managed_execution_semantics_profile_id is required -- the resolved cohort "
                "includes STOP_MANAGED_INVALIDATION variants (amendment section 7 -- not optional)"
            )
        elif stop_managed_profile is None or stop_managed_profile.profile_id != plan.stop_managed_execution_semantics_profile_id:
            errors.append(
                f"plan.stop_managed_execution_semantics_profile_id="
                f"{plan.stop_managed_execution_semantics_profile_id!r} does not match a verified profile "
                f"actually supplied to this gate (stop_managed_profile)"
            )
        elif not verify_stop_managed_execution_semantics_profile_v1(stop_managed_profile)[0]:
            errors.append("the supplied stop_managed_profile itself fails v1 content-address/structural verification")
    else:
        if plan.selection_rule.ranking_metric != RANKING_METRIC_V1:
            errors.append(
                f"selection_rule.ranking_metric must be {RANKING_METRIC_V1!r} -- the resolved cohort has no "
                f"STOP_MANAGED_INVALIDATION variants, got {plan.selection_rule.ranking_metric!r} (symmetric "
                f"enforcement: an old-family-only cohort is not free to opt into the new metric either)"
            )

    return (not errors, tuple(errors))
