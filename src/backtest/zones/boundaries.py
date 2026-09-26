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

from typing import Optional


def verify_zone_ordering(
    formation_start: str, formation_end: str, validation_start: str, validation_end: str, locked_oos_start: str,
) -> tuple[bool, tuple[str, ...]]:
    if not (formation_start <= formation_end < validation_start <= validation_end < locked_oos_start):
        return False, (
            f"zone ordering violated: require formation_start({formation_start!r}) <= "
            f"formation_end({formation_end!r}) < validation_start({validation_start!r}) <= "
            f"validation_end({validation_end!r}) < locked_oos_start({locked_oos_start!r})",
        )
    return True, ()


def verify_evidence_development_ends(
    formation_end: str, validation_start: str, development_ends: tuple[Optional[str], ...],
) -> tuple[bool, tuple[str, ...]]:
    """`development_ends` must already be resolved (one per evidence run
    in the cohort, via `backtest.provenance.evaluation_run`) -- this
    function only checks the two required inequalities against them.
    SS3: "Require non-null dates and matching evidence lineage." """
    errors: list[str] = []
    for i, dev_end in enumerate(development_ends):
        if dev_end is None:
            errors.append(f"evidence run #{i}: development_end is None -- a non-null date is required (SS3)")
            continue
        if dev_end > formation_end:
            errors.append(
                f"evidence run #{i}: development_end={dev_end!r} exceeds formation_end={formation_end!r} "
                f"(require development_end <= formation_end, SS3)"
            )
        if dev_end >= validation_start:
            errors.append(
                f"evidence run #{i}: development_end={dev_end!r} does not precede validation_start="
                f"{validation_start!r} (require development_end < validation_start, SS3) -- this period was "
                f"already used to form the hypothesis and cannot also be independent validation"
            )
    return (not errors, tuple(errors))


def verify_zone_boundaries(
    formation_start: str, formation_end: str, validation_start: str, validation_end: str, locked_oos_start: str,
    evidence_development_ends: tuple[Optional[str], ...],
) -> tuple[bool, tuple[str, ...]]:
    errors: list[str] = []
    ordering_ok, ordering_errors = verify_zone_ordering(formation_start, formation_end, validation_start, validation_end, locked_oos_start)
    errors.extend(ordering_errors)
    dates_ok, dates_errors = verify_evidence_development_ends(formation_end, validation_start, evidence_development_ends)
    errors.extend(dates_errors)
    return (not errors, tuple(errors))
