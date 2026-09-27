"""Spec #005 Batch 3 -- per-session step functions for an already-open
STOP_MANAGED_INVALIDATION position (docs/spec005_exit_amendment_v1.0.md,
ACCEPTED, sections 5-6, 8, 10).

Each function is pure: it takes a `StopManagedPosition` and returns a NEW
one via `dataclasses.replace()`, never mutating the argument. Callers
sequence these per the amendment's Pas 0 / Pas 3' / Pas 5 order (section
5); this module does not own the surrounding multi-security session loop
(see `backtest.exits` package docstring for that scope boundary).
"""
from __future__ import annotations

import dataclasses
from datetime import date
from typing import Optional

from data_foundation.model.entities import ActionType
from data_foundation.pit.access import _is_action_known_for_adjustment

from backtest.data.pit_access import BoundedPITAccess
from backtest.exits.entities import (
    EXIT_REASON_INVALIDATION,
    EXIT_REASON_STOP,
    EXIT_REASON_TARGET,
    StopManagedPosition,
    Tranche,
)
from backtest.exits.protection import _find_bar, is_authorized_at_open


def _calendar_days(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def _current_split_factor(pit: BoundedPITAccess, security_id: str, entry_date: str, as_of: str) -> Optional[float]:
    """Amendment section 6: `current_factor` is the adjustment factor,
    recomputed TODAY, of the POSITION'S OWN entry date (never a generic
    security-wide "latest" factor) -- the same `compute_factors()`
    recipe #001 already applies, reached only via `split_adjusted_close`
    ratios (never re-derived here)."""
    bars = pit.get_price_series_as_of(security_id, as_of)
    bar = _find_bar(bars, entry_date)
    if bar is None or not bar.raw_close or bar.split_adjusted_close is None:
        return None
    return bar.split_adjusted_close / bar.raw_close


def reconcile_split_for_open_position(
    pit: BoundedPITAccess, position: StopManagedPosition, session_date: str,
    same_day_evidence: frozenset = frozenset(),
) -> StopManagedPosition:
    """Amendment section 6, Pas 0 -- runs BEFORE any scheduled exit for
    this session (section 5). Applies each new, not-yet-processed SPLIT/
    REVERSE_SPLIT action exactly once, idempotently (`processed_split_
    action_ids`), rescaling only the still-active remainder -- an
    already-closed tranche's own recorded values are never touched. A
    split that is date-effective but not authorized at THIS session's
    open (same-day, no evidence) is neither applied nor ignored: it
    marks `split_reconciliation_incomplete=True`, permanently."""
    if position.closed or position.remaining_quantity <= 0:
        return position

    actions = pit.get_corporate_actions_as_of(position.security_id, session_date)
    pos = position
    became_incomplete = False
    for pca in actions:
        a = pca.action
        if a.action_type not in (ActionType.SPLIT.value, ActionType.REVERSE_SPLIT.value):
            continue
        if a.action_id in pos.processed_split_action_ids:
            continue
        if not _is_action_known_for_adjustment(a, session_date):
            continue
        if not is_authorized_at_open(a.effective_date, session_date, a.action_id in same_day_evidence):
            became_incomplete = True
            continue

        current_factor = _current_split_factor(pit, pos.security_id, pos.entry_date, session_date)
        if current_factor is None:
            became_incomplete = True
            continue
        if current_factor == pos.applied_factor:
            pos = dataclasses.replace(pos, processed_split_action_ids=pos.processed_split_action_ids + (a.action_id,))
            continue

        ratio = current_factor / pos.applied_factor
        pos = dataclasses.replace(
            pos,
            active_stop=pos.active_stop * ratio,
            target_price=pos.target_price * ratio if pos.target_price is not None else None,
            initial_risk=pos.initial_risk * ratio,
            entry_fill_price=pos.entry_fill_price * ratio,
            remaining_quantity=pos.remaining_quantity / ratio,
            applied_factor=current_factor,
            processed_split_action_ids=pos.processed_split_action_ids + (a.action_id,),
        )

    if became_incomplete:
        pos = dataclasses.replace(pos, split_reconciliation_incomplete=True)
    return pos


def advance_intrabar(
    position: StopManagedPosition, session_date: str, open_price: float, high: float, low: float,
) -> tuple[StopManagedPosition, tuple[Tranche, ...]]:
    """Amendment section 5, Pas 3'. Returns (new_position, tranches
    executed THIS session, in chronological order)."""
    if position.closed or position.remaining_quantity <= 0:
        return position, ()

    long = position.direction == "LONG"
    holding_days = _calendar_days(position.entry_date, session_date)
    target = position.target_price if not position.target_consumed else None

    def _stop_breach(price: float, stop: float) -> bool:
        return price <= stop if long else price >= stop

    def _target_breach(price: float, tgt: float) -> bool:
        return price >= tgt if long else price <= tgt

    # (a) stop at open -- resolves the whole session for this position.
    if _stop_breach(open_price, position.active_stop):
        frac = (1.0 - position.fraction) if position.target_consumed else 1.0
        tranche = Tranche(
            kind="REMAINDER", exit_reason=EXIT_REASON_STOP, fraction_of_original=frac,
            exit_date=session_date, exit_fill_price=open_price, holding_days=holding_days,
        )
        new_pos = dataclasses.replace(position, closed=True, close_tranche=tranche, remaining_quantity=0.0)
        return new_pos, (tranche,)

    pos = position
    executed: list[Tranche] = []

    # (b) target at open (only if still to be verified).
    if target is not None and _target_breach(open_price, target):
        partial = Tranche(
            kind="PARTIAL_PROFIT", exit_reason=EXIT_REASON_TARGET, fraction_of_original=pos.fraction,
            exit_date=session_date, exit_fill_price=open_price, holding_days=holding_days,
        )
        pos = dataclasses.replace(
            pos, target_consumed=True, partial_tranche=partial,
            remaining_quantity=pos.remaining_quantity * (1.0 - pos.fraction),
        )
        executed.append(partial)
        target = None  # consumed -- (c) below checks only the stop, per section 5.

    # (c) the rest of the session, on whatever quantity is still active.
    stop_hit = _stop_breach(low if long else high, pos.active_stop)
    target_hit = target is not None and _target_breach(high if long else low, target)

    if stop_hit and target_hit:
        # Genuine same-bar ambiguity: (a)/(b) did not already resolve
        # chronology via the open's own position -- stop-first, counted.
        frac = (1.0 - pos.fraction) if pos.target_consumed else 1.0
        tranche = Tranche(
            kind="REMAINDER", exit_reason=EXIT_REASON_STOP, fraction_of_original=frac,
            exit_date=session_date, exit_fill_price=pos.active_stop, holding_days=holding_days,
        )
        pos = dataclasses.replace(
            pos, closed=True, close_tranche=tranche, remaining_quantity=0.0,
            ambiguous_intrabar_conflicts=pos.ambiguous_intrabar_conflicts + 1,
        )
        executed.append(tranche)
        return pos, tuple(executed)

    if stop_hit:
        frac = (1.0 - pos.fraction) if pos.target_consumed else 1.0
        tranche = Tranche(
            kind="REMAINDER", exit_reason=EXIT_REASON_STOP, fraction_of_original=frac,
            exit_date=session_date, exit_fill_price=pos.active_stop, holding_days=holding_days,
        )
        pos = dataclasses.replace(pos, closed=True, close_tranche=tranche, remaining_quantity=0.0)
        executed.append(tranche)
        return pos, tuple(executed)

    if target_hit:
        partial = Tranche(
            kind="PARTIAL_PROFIT", exit_reason=EXIT_REASON_TARGET, fraction_of_original=pos.fraction,
            exit_date=session_date, exit_fill_price=pos.target_price, holding_days=holding_days,
        )
        pos = dataclasses.replace(
            pos, target_consumed=True, partial_tranche=partial,
            remaining_quantity=pos.remaining_quantity * (1.0 - pos.fraction),
        )
        executed.append(partial)
        return pos, tuple(executed)

    return pos, tuple(executed)


def update_trailing_stop_at_close(position: StopManagedPosition, close_price: float, atr_today: Optional[float]) -> StopManagedPosition:
    """Amendment section 3: S_next computed at close(t), becomes S_activ
    only from session t+1 -- never applied retroactively to today's own
    low/high check (Pas 3' above always reads the STOP value as it stood
    BEFORE this update). `atr_today=None` (ATR invalid mid-position, e.g.
    insufficient history after a data gap) leaves the stop at its last
    valid value -- never relaxed, never a substitute value -- and marks
    `trailing_path_incomplete=True` permanently (section 10)."""
    if position.closed or position.remaining_quantity <= 0:
        return position
    if atr_today is None:
        return dataclasses.replace(position, trailing_path_incomplete=True)
    long = position.direction == "LONG"
    candidate = close_price - position.k * atr_today if long else close_price + position.k * atr_today
    new_stop = max(position.active_stop, candidate) if long else min(position.active_stop, candidate)
    return dataclasses.replace(position, active_stop=new_stop)


def check_trend_invalidation(position: StopManagedPosition, session_date: str, observation_status: str) -> StopManagedPosition:
    """Amendment section 8 / section 5 Pas 5: `observation_status` is one
    of "VALID_HOLD" | "INVALIDATED" | "UNKNOWN" for the tracked lane(s),
    evaluated at THIS session's close, for whatever quantity is still
    active after Pas 3'. A position fully closed at Pas 3' (remaining_
    quantity == 0) skips this entirely -- no INVALIDATION_PATH_INCOMPLETE
    from an inapplicable check (regression #11). "UNKNOWN" taints the
    position permanently, regardless of later resolution (section 5's
    mandatory persistent-incompleteness rule)."""
    if position.closed or position.remaining_quantity <= 0:
        return position
    if observation_status == "UNKNOWN":
        return dataclasses.replace(position, invalidation_path_incomplete=True)
    if observation_status == "INVALIDATED":
        return dataclasses.replace(position, pending_invalidation_detected_date=session_date)
    return position


def execute_scheduled_invalidation(
    position: StopManagedPosition, next_session_date: str, next_session_open_price: Optional[float],
    stage_end_date: str,
) -> StopManagedPosition:
    """Consumes a pending invalidation (detected at a previous close) at
    the scheduled NEXT_SESSION_OPEN fill. If `next_session_date` itself
    falls AFTER `stage_end_date`, the fill is not yet due within this
    stage -- the position stays open with `pending_exit_note` recorded,
    never CENSORED via a next-stage open this engine never reads
    (amendment section 10's central CENSORED_AT_HORIZON case, regression
    #9). If due within the stage but the open bar is missing
    (`next_session_open_price=None`), the position is EXIT_FAILED
    (execution was due in-stage and could not be realized)."""
    if position.closed or position.pending_invalidation_detected_date is None:
        return position
    if next_session_date > stage_end_date:
        return dataclasses.replace(
            position,
            pending_exit_note=(
                f"INVALIDATED at close of {position.pending_invalidation_detected_date}, fill scheduled "
                f"{next_session_date} falls in the next stage -- not read, position stays CENSORED_AT_HORIZON"
            ),
        )
    if next_session_open_price is None:
        return dataclasses.replace(position, exit_failed=True, exit_failed_reason="NO_EXIT_BAR")
    frac = (1.0 - position.fraction) if position.target_consumed else 1.0
    holding_days = _calendar_days(position.entry_date, next_session_date)
    tranche = Tranche(
        kind="REMAINDER", exit_reason=EXIT_REASON_INVALIDATION, fraction_of_original=frac,
        exit_date=next_session_date, exit_fill_price=next_session_open_price, holding_days=holding_days,
    )
    return dataclasses.replace(
        position, closed=True, close_tranche=tranche, remaining_quantity=0.0,
        pending_invalidation_detected_date=None,
    )
