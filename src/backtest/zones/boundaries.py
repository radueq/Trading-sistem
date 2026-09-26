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
from datetime import date as _date
from typing import Optional


def _is_valid_iso_date(value) -> bool:
    if not isinstance(value, str):
        return False
    try:
        _date.fromisoformat(value)
        return True
    except ValueError:
        return False


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
    errors: list[str] = []
    for name, value in (
        ("formation_start", formation_start), ("formation_end", formation_end),
        ("validation_start", validation_start), ("validation_end", validation_end),
        ("locked_oos_start", locked_oos_start),
    ):
        if not _is_valid_iso_date(value):
            errors.append(f"{name} is not a valid ISO date: {value!r}")
    if errors:
        return False, tuple(errors)
    if not (formation_start <= formation_end < validation_start <= validation_end < locked_oos_start):
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
    two upper-bound inequalities against `formation_end`/`validation_start`."""
    errors: list[str] = []
    for period in periods:
        label = f"evidence run {period.hypothesis_id!r}"
        if period.development_start is None:
            errors.append(f"{label}: development_start is None -- a non-null date is required (SS3)")
        elif not _is_valid_iso_date(period.development_start):
            errors.append(f"{label}: development_start is not a valid ISO date: {period.development_start!r}")

        if period.development_end is None:
            errors.append(f"{label}: development_end is None -- a non-null date is required (SS3)")
            continue
        if not _is_valid_iso_date(period.development_end):
            errors.append(f"{label}: development_end is not a valid ISO date: {period.development_end!r}")
            continue

        if (
            period.development_start is not None
            and _is_valid_iso_date(period.development_start)
            and period.development_start > period.development_end
        ):
            errors.append(
                f"{label}: development_start={period.development_start!r} is after "
                f"development_end={period.development_end!r}"
            )
        if period.development_end > formation_end:
            errors.append(
                f"{label}: development_end={period.development_end!r} exceeds formation_end={formation_end!r} "
                f"(require development_end <= formation_end, SS3)"
            )
        if period.development_end >= validation_start:
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
