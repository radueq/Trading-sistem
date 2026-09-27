"""Spec #005 Batch 3 -- three-facet position taxonomy and selection
metric for STOP_MANAGED_INVALIDATION (docs/spec005_exit_amendment_v1.0.md,
ACCEPTED, sections 10-11).
"""
from __future__ import annotations

from typing import Optional

from backtest.exits.entities import (
    EVALUABILITY_EVALUABLE,
    EVALUABILITY_UNEVALUABLE,
    LIFECYCLE_CENSORED_AT_HORIZON,
    LIFECYCLE_CLOSED,
    LIFECYCLE_EXIT_FAILED,
    REASON_CENSORED_MARK_UNAVAILABLE,
    REASON_INVALIDATION_PATH_INCOMPLETE,
    REASON_NO_EXIT_BAR,
    REASON_SPLIT_RECONCILIATION_INCOMPLETE,
    REASON_TRAILING_PATH_INCOMPLETE,
    PositionOutcome,
    StopManagedPosition,
)


def _persistent_incompleteness_reason(position: StopManagedPosition) -> Optional[str]:
    """Fixed priority when more than one persistent-incompleteness flag
    is set (all such positions are UNEVALUABLE either way -- this order
    only decides which single reason is reported)."""
    if position.split_reconciliation_incomplete:
        return REASON_SPLIT_RECONCILIATION_INCOMPLETE
    if position.invalidation_path_incomplete:
        return REASON_INVALIDATION_PATH_INCOMPLETE
    if position.trailing_path_incomplete:
        return REASON_TRAILING_PATH_INCOMPLETE
    return None


def classify_position(
    position: StopManagedPosition, stage_end_reached: bool, final_mark_available: bool = True,
) -> PositionOutcome:
    """Amendment section 10's intersection rules. `net_return` is never
    populated here -- callers combine this with `costs.
    aggregate_position_return()` once evaluability is known (this
    function decides ONLY the three facets)."""
    if position.exit_failed:
        return PositionOutcome(LIFECYCLE_EXIT_FAILED, EVALUABILITY_UNEVALUABLE, REASON_NO_EXIT_BAR)

    if position.closed:
        reason = _persistent_incompleteness_reason(position)
        if reason is not None:
            return PositionOutcome(LIFECYCLE_CLOSED, EVALUABILITY_UNEVALUABLE, reason)
        return PositionOutcome(LIFECYCLE_CLOSED, EVALUABILITY_EVALUABLE, None)

    if not stage_end_reached:
        raise ValueError(
            "classify_position(): position is neither closed nor EXIT_FAILED, and stage_end_reached=False "
            "-- it is not yet classifiable (still actively simulating)"
        )

    reason = _persistent_incompleteness_reason(position)
    if reason is not None:
        return PositionOutcome(LIFECYCLE_CENSORED_AT_HORIZON, EVALUABILITY_UNEVALUABLE, reason)
    if not final_mark_available:
        return PositionOutcome(LIFECYCLE_CENSORED_AT_HORIZON, EVALUABILITY_UNEVALUABLE, REASON_CENSORED_MARK_UNAVAILABLE)
    return PositionOutcome(LIFECYCLE_CENSORED_AT_HORIZON, EVALUABILITY_EVALUABLE, None)


def executed_entries_count(outcomes: list[PositionOutcome]) -> int:
    """Section 11: the denominator for both ratios below is every
    position with an EXECUTED entry, regardless of facet -- never
    signals rejected before an entry ever happened (SUPPRESSED_STAGE_
    BOUNDARY, NO_ENTRY_BAR, NO_VALID_STOP_BASIS, INVALID_PROTECTIVE_
    LEVELS). Callers must only ever pass executed-entry outcomes here."""
    return len(outcomes)


def censored_ratio(outcomes: list[PositionOutcome]) -> Optional[float]:
    n = executed_entries_count(outcomes)
    if n == 0:
        return None
    censored = sum(1 for o in outcomes if o.lifecycle == LIFECYCLE_CENSORED_AT_HORIZON)
    return censored / n


def evaluable_ratio(outcomes: list[PositionOutcome]) -> Optional[float]:
    n = executed_entries_count(outcomes)
    if n == 0:
        return None
    evaluable = sum(1 for o in outcomes if o.evaluability == EVALUABILITY_EVALUABLE)
    return evaluable / n


def median_net_return_to_exit_or_stage_end(outcomes: list[PositionOutcome]) -> Optional[float]:
    """Amendment section 11's new, mandatory ranking metric for any
    cohort containing STOP_MANAGED_INVALIDATION variants: the median over
    the FULL EVALUABLE set (facet 2), regardless of facet 1 (CLOSED or
    CENSORED_AT_HORIZON -- never EXIT_FAILED, always excluded). Directly
    counters the exact selection bias identified in review: excluding
    still-open positions from ranking would let a variant win by hiding
    its worst trades as still-censored."""
    values = sorted(
        o.net_return for o in outcomes
        if o.evaluability == EVALUABILITY_EVALUABLE and o.net_return is not None
    )
    if not values:
        return None
    n = len(values)
    mid = n // 2
    if n % 2 == 1:
        return values[mid]
    return (values[mid - 1] + values[mid]) / 2.0
