"""Spec #005 v1.0 SS3 -- zone-boundary inequalities (Batch 1).

    formation_start <= formation_end < validation_start <= validation_end < locked_oos_start
    each_evidence_run.development_end <= formation_end
    each_evidence_run.development_end < validation_start

The second and third lines are why Spec #005 exists at all: #003/#004
already used the Formation/Selection period to form every hypothesis in
the cohort, so no sub-interval of it can later be called independent
validation (SS7 of the review conclusions). `development_end` is the
correct upper bound for "data actually used" -- not a per-signal
max(entry+horizon) computation -- because `evaluation.outcomes.
forward_returns.compute_forward_outcome()` already hard-walls every
forward-return read on DATE alone at that boundary (CROSSES_LOCKED_OOS),
never touching a price past it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from backtest.models.entities import (
    DEVELOPMENT_VALIDATION,
    FORMATION_SELECTION,
    ResearchPlan,
    StageAccessBoundary,
    StageBoundaryPlanMismatchError,
    parse_iso_date,
    verify_research_plan_identity,
)


@dataclass(frozen=True)
class EvidencePeriod:
    """One evidence run's actually-used data window (Spec #005 SS3/SS4).
    `hypothesis_id` is carried through purely for error-message
    attribution -- it plays no role in the inequalities themselves."""
    hypothesis_id: str
    development_start: Optional[str]
    development_end: Optional[str]


def verify_zone_ordering(
    formation_start: str, formation_end: str, validation_start: str, validation_end: str, locked_oos_start: str,
) -> tuple[bool, tuple[str, ...]]:
    """Every comparison is made on PARSED `date` objects, never on the
    raw strings. GPT Batch 1 patch review (P1 finding, second round):
    `datetime.date.fromisoformat()` alone accepts non-canonical forms
    like ISO week dates ("2024W011" == 2024-01-01) that do not sort
    lexically the same way their canonical `YYYY-MM-DD` equivalent
    would -- `parse_iso_date()` rejects anything but strict
    `YYYY-MM-DD` BEFORE any date ever reaches a comparison, closing the
    exact loophole that let a `validation_start` slip chronologically
    before `formation_end` while still passing this check as strings."""
    errors: list[str] = []
    parsed = {}
    for name, value in (
        ("formation_start", formation_start), ("formation_end", formation_end),
        ("validation_start", validation_start), ("validation_end", validation_end),
        ("locked_oos_start", locked_oos_start),
    ):
        d = parse_iso_date(value)
        if d is None:
            errors.append(f"{name} is not a valid ISO date: {value!r}")
        else:
            parsed[name] = d
    if errors:
        return False, tuple(errors)
    if not (
        parsed["formation_start"] <= parsed["formation_end"] < parsed["validation_start"]
        <= parsed["validation_end"] < parsed["locked_oos_start"]
    ):
        return False, (
            f"zone ordering violated: require formation_start({formation_start!r}) <= "
            f"formation_end({formation_end!r}) < validation_start({validation_start!r}) <= "
            f"validation_end({validation_end!r}) < locked_oos_start({locked_oos_start!r})",
        )
    return True, ()


def verify_evidence_periods(
    formation_end: str, validation_start: str, periods: tuple[EvidencePeriod, ...],
) -> tuple[bool, tuple[str, ...]]:
    """Checks BOTH ends of each evidence run's actually-used data window
    (SS3: "Require non-null dates and matching evidence lineage") --
    `development_start` not just `development_end`, so a missing/absent
    start date or a start-after-end ordering bug is caught, not just the
    two upper-bound inequalities against `formation_end`/`validation_start`.
    `formation_end`/`validation_start` themselves are validated and
    parsed here too -- all comparisons are on `date` objects, never raw
    strings (see `verify_zone_ordering()`'s docstring for why)."""
    errors: list[str] = []
    formation_end_date = parse_iso_date(formation_end)
    validation_start_date = parse_iso_date(validation_start)
    if formation_end_date is None:
        errors.append(f"formation_end is not a valid ISO date: {formation_end!r}")
    if validation_start_date is None:
        errors.append(f"validation_start is not a valid ISO date: {validation_start!r}")
    if errors:
        return False, tuple(errors)

    for period in periods:
        label = f"evidence run {period.hypothesis_id!r}"
        start_date = None
        if period.development_start is None:
            errors.append(f"{label}: development_start is None -- a non-null date is required (SS3)")
        else:
            start_date = parse_iso_date(period.development_start)
            if start_date is None:
                errors.append(f"{label}: development_start is not a valid ISO date: {period.development_start!r}")

        if period.development_end is None:
            errors.append(f"{label}: development_end is None -- a non-null date is required (SS3)")
            continue
        end_date = parse_iso_date(period.development_end)
        if end_date is None:
            errors.append(f"{label}: development_end is not a valid ISO date: {period.development_end!r}")
            continue

        if start_date is not None and start_date > end_date:
            errors.append(
                f"{label}: development_start={period.development_start!r} is after "
                f"development_end={period.development_end!r}"
            )
        if end_date > formation_end_date:
            errors.append(
                f"{label}: development_end={period.development_end!r} exceeds formation_end={formation_end!r} "
                f"(require development_end <= formation_end, SS3)"
            )
        if end_date >= validation_start_date:
            errors.append(
                f"{label}: development_end={period.development_end!r} does not precede validation_start="
                f"{validation_start!r} (require development_end < validation_start, SS3) -- this period was "
                f"already used to form the hypothesis and cannot also be independent validation"
            )
    return (not errors, tuple(errors))


def verify_zone_boundaries(
    formation_start: str, formation_end: str, validation_start: str, validation_end: str, locked_oos_start: str,
    evidence_periods: tuple[EvidencePeriod, ...],
) -> tuple[bool, tuple[str, ...]]:
    errors: list[str] = []
    ordering_ok, ordering_errors = verify_zone_ordering(formation_start, formation_end, validation_start, validation_end, locked_oos_start)
    errors.extend(ordering_errors)
    periods_ok, periods_errors = verify_evidence_periods(formation_end, validation_start, evidence_periods)
    errors.extend(periods_errors)
    return (not errors, tuple(errors))


def build_stage_access_boundary_from_plan(plan: ResearchPlan, zone: str) -> StageAccessBoundary:
    """Spec #005 SS3, Batch 2 patch (round 2, then round 3): a bare
    `StageAccessBoundary(FORMATION_SELECTION, "2099-12-31")` was
    accepted with no check against anything -- the LOCKED_OOS zone
    label was forbidden, but nothing stopped a FORMATION_SELECTION- or
    DEVELOPMENT_VALIDATION-labeled boundary from reaching straight into
    the Locked OOS date range under a different label. `max_as_of` must
    come from the frozen plan's OWN already-validated zone dates --
    `formation_end` for FORMATION_SELECTION, `validation_end` for
    DEVELOPMENT_VALIDATION -- never a caller-supplied string.

    Round-3 review (still-open gap): identity re-verification alone
    (`verify_research_plan_identity()`) only proves the plan's fields
    match its OWN claimed hash -- it says nothing about whether those
    fields are economically SANE. A plan can have a perfectly
    self-consistent hash over OVERLAPPING zone dates (e.g.
    validation_start before formation_end), which would let a boundary
    derived from it reach data it was never supposed to. `verify_
    zone_ordering()` is now called here too, on the plan's own 5 zone
    dates, closing that gap. This function lives here rather than in
    `backtest.models.entities` specifically so it CAN call
    `verify_zone_ordering()` -- `entities.py` cannot import this module
    without creating a cycle (this module already imports from
    `entities`)."""
    ok, errors = verify_research_plan_identity(plan)
    if not ok:
        raise StageBoundaryPlanMismatchError(
            f"cannot derive a StageAccessBoundary from a plan that fails identity verification: {errors}"
        )
    ordering_ok, ordering_errors = verify_zone_ordering(
        plan.formation_start, plan.formation_end, plan.validation_start, plan.validation_end, plan.locked_oos_start,
    )
    if not ordering_ok:
        raise StageBoundaryPlanMismatchError(
            f"cannot derive a StageAccessBoundary from a plan whose own zone dates fail "
            f"verify_zone_ordering(): {ordering_errors}"
        )
    if zone == FORMATION_SELECTION:
        max_as_of = plan.formation_end
    elif zone == DEVELOPMENT_VALIDATION:
        max_as_of = plan.validation_end
    else:
        raise StageBoundaryPlanMismatchError(
            f"build_stage_access_boundary_from_plan() only derives {FORMATION_SELECTION!r} or "
            f"{DEVELOPMENT_VALIDATION!r} boundaries, got zone={zone!r}"
        )
    return StageAccessBoundary(zone=zone, max_as_of=max_as_of)


def zone_start_date(plan: ResearchPlan, zone: str) -> str:
    """The zone's own START date on `plan` -- `formation_start` for
    FORMATION_SELECTION, `validation_start` for DEVELOPMENT_VALIDATION.
    Additive (Spec #005 -- Discovery Integration & Legacy Exits): factors
    out the exact zone-start mapping `engine.run_stage()` and
    `data.context.StageReadContext.__init__()` each already inline
    independently, for a THIRD caller (`exits.discovery_integration`)
    that needs the same zone_start without a fourth inline copy. Neither
    existing inline copy is touched -- this is a new function only."""
    if zone == FORMATION_SELECTION:
        return plan.formation_start
    if zone == DEVELOPMENT_VALIDATION:
        return plan.validation_start
    raise StageBoundaryPlanMismatchError(
        f"zone_start_date() only derives {FORMATION_SELECTION!r} or {DEVELOPMENT_VALIDATION!r} "
        f"start dates, got zone={zone!r}"
    )
