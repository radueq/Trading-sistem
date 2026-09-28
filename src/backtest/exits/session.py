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
import math
from datetime import date
from typing import Optional

from data_foundation.model.adjustment_engine import compute_factors
from data_foundation.model.entities import ActionType, CorporateAction
from data_foundation.pit.access import _is_action_known_for_adjustment

from backtest.data.pit_access import BoundedPITAccess
from backtest.exits.entities import (
    EXIT_REASON_INVALIDATION,
    EXIT_REASON_STOP,
    EXIT_REASON_TARGET,
    StopManagedPosition,
    Tranche,
)
from backtest.exits.protection import _find_bar, is_authorized_at_open, knowledge_date


def _calendar_days(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


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
    open (same-day, no evidence -- checked on its `knowledge_date()`,
    never `effective_date` directly, GPT review round 2 finding #1) is
    neither applied nor ignored: it marks `split_reconciliation_
    incomplete=True`, permanently.

    GPT review round 2, finding #4: the applied factor is built ONLY
    from actions THIS position has actually authorized (already-processed
    + newly-authorized this call) via `compute_factors()` directly --
    never delegated to `get_price_series_as_of()`'s own full known-action
    set, which could silently fold in a DIFFERENT same-day action this
    position has not (yet) authorized at open.

    GPT review round 2, finding #2: even when the ratio is successfully
    applied, if the action's own `effective_date` is STRICTLY BEFORE
    `session_date`, this reconciliation happened later than the split's
    own rightful session -- some number of intervening sessions were
    necessarily simulated on the stale, unreconciled basis (regardless of
    whether that was itself PIT-correct at the time). `split_
    reconciliation_incomplete` is set permanently in that case too, even
    though the ratio catch-up still corrects the position going forward.

    GPT review round 3, finding #1: a split with `effective_date <=
    position.entry_date` is NEVER Pas 0's concern, regardless of
    `session_date` -- it was already fully reflected in the position's
    OWN opening basis the moment it was created (section 5: "Pozițiile
    nou deschise azi pornesc DIRECT pe baza intrării... post orice split
    cunoscut"), and `compute_factors()`'s own condition (`effective_date
    > d`) structurally cannot rescale a date at or after the split's own
    effective date. Treating such a split as "newly encountered" on some
    later session wrongly marked the position `split_reconciliation_
    incomplete` even though nothing was ever stale -- the entry's own
    factor was already, correctly, 1.0. These actions are skipped here
    entirely: never authorization-checked, never recorded as processed,
    never counted toward lateness."""
    if position.closed or position.remaining_quantity <= 0:
        return position

    actions = pit.get_corporate_actions_as_of(position.security_id, session_date)
    pos = position
    became_incomplete = False
    known_split_actions: list[CorporateAction] = []
    newly_authorized: list[CorporateAction] = []

    for pca in actions:
        a = pca.action
        if a.action_type not in (ActionType.SPLIT.value, ActionType.REVERSE_SPLIT.value):
            continue
        if a.effective_date <= pos.entry_date:
            continue  # already fully reflected in the position's own opening basis -- not Pas 0's concern.
        if not _is_action_known_for_adjustment(a, session_date):
            continue
        known_split_actions.append(a)
        if a.action_id in pos.processed_split_action_ids:
            continue
        if not is_authorized_at_open(knowledge_date(a), session_date, a.action_id in same_day_evidence):
            became_incomplete = True
            continue
        newly_authorized.append(a)

    if not newly_authorized:
        if became_incomplete:
            pos = dataclasses.replace(pos, split_reconciliation_incomplete=True)
        return pos

    already_processed = {a.action_id for a in known_split_actions if a.action_id in pos.processed_split_action_ids}
    authorized_actions = [a for a in known_split_actions if a.action_id in already_processed] + newly_authorized

    bars = pit.get_price_series_as_of(pos.security_id, session_date)
    entry_bar = _find_bar(bars, pos.entry_date)
    if entry_bar is None or not entry_bar.raw_close:
        return dataclasses.replace(pos, split_reconciliation_incomplete=True)

    factors = compute_factors([pos.entry_date], {pos.entry_date: entry_bar.raw_close}, authorized_actions, [])
    current_factor, _total_return_factor = factors[pos.entry_date]

    newly_authorized_ids = tuple(a.action_id for a in newly_authorized)
    late = any(a.effective_date < session_date for a in newly_authorized)

    if current_factor != pos.applied_factor:
        ratio = current_factor / pos.applied_factor
        pos = dataclasses.replace(
            pos,
            active_stop=pos.active_stop * ratio,
            target_price=pos.target_price * ratio if pos.target_price is not None else None,
            initial_risk=pos.initial_risk * ratio,
            entry_fill_price=pos.entry_fill_price * ratio,
            remaining_quantity=pos.remaining_quantity / ratio,
            applied_factor=current_factor,
            processed_split_action_ids=pos.processed_split_action_ids + newly_authorized_ids,
        )
    else:
        pos = dataclasses.replace(pos, processed_split_action_ids=pos.processed_split_action_ids + newly_authorized_ids)

    if became_incomplete or late:
        pos = dataclasses.replace(pos, split_reconciliation_incomplete=True)
    return pos


def advance_intrabar(
    position: StopManagedPosition, session_date: str, open_price: float, high: float, low: float,
) -> tuple[StopManagedPosition, tuple[Tranche, ...]]:
    """Amendment section 5, Pas 3'. Returns (new_position, tranches
    executed THIS session, in chronological order). Every `Tranche`
    freezes `entry_fill_price_reference=position.entry_fill_price` at the
    moment of its OWN creation (GPT review round 2, finding #5) -- so a
    split reconciled on a LATER session can never retroactively corrupt
    an already-closed tranche's own return computation."""
    if position.closed or position.remaining_quantity <= 0:
        return position, ()

    long = position.direction == "LONG"
    holding_days = _calendar_days(position.entry_date, session_date)
    entry_ref = position.entry_fill_price
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
            entry_fill_price_reference=entry_ref,
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
            entry_fill_price_reference=entry_ref,
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
            entry_fill_price_reference=entry_ref,
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
            entry_fill_price_reference=entry_ref,
        )
        pos = dataclasses.replace(pos, closed=True, close_tranche=tranche, remaining_quantity=0.0)
        executed.append(tranche)
        return pos, tuple(executed)

    if target_hit:
        partial = Tranche(
            kind="PARTIAL_PROFIT", exit_reason=EXIT_REASON_TARGET, fraction_of_original=pos.fraction,
            exit_date=session_date, exit_fill_price=pos.target_price, holding_days=holding_days,
            entry_fill_price_reference=entry_ref,
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
    BEFORE this update). Any non-usable `atr_today` -- missing, non-finite
    (NaN/inf), zero, or negative (GPT review round 2, finding #6a: not
    just `None`) -- leaves the stop at its last valid value -- never
    relaxed, never a substitute value -- and marks `trailing_path_
    incomplete=True` permanently (section 10)."""
    if position.closed or position.remaining_quantity <= 0:
        return position
    if (
        atr_today is None or not math.isfinite(atr_today) or atr_today <= 0
        or close_price is None or not math.isfinite(close_price)
    ):
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
        entry_fill_price_reference=position.entry_fill_price,
    )
    return dataclasses.replace(
        position, closed=True, close_tranche=tranche, remaining_quantity=0.0,
        pending_invalidation_detected_date=None,
    )
