"""Spec #005 Batch 3 -- entry-time validation and initial protective-stop/
target formulas for STOP_MANAGED_INVALIDATION (docs/spec005_exit_
amendment_v1.0.md, ACCEPTED, sections 2-3).

ATR reuses #002's existing ATR_14 (Wilder method, window and seeding,
`discovery.features.volatility.compute()`) VERBATIM -- no new indicator,
no different smoothing. The INPUT SERIES fed to it must be internally
coherent, though: #002's own `discovery.engine._price_series_to_df()`
mixes raw high/low with split-adjusted close, which would inject an
artificial true-range spike at any split inside the ATR window -- the
accepted amendment requires the same METHOD, not a silent carry-over of
that inconsistency (GPT review, round 2). This module uses
`split_adjusted_high`/`split_adjusted_low`/`split_adjusted_close`
together (all three under the SAME as-of query, PATCH #001-D) for a
coherent basis; #002's own mixed convention is left untouched (out of
scope to fix here) and is only noted, separately, in
docs/spec005_known_limitations.md.

Split-basis reconciliation reuses #001's own `split_adjusted_close`
(itself `compute_factors()`'s existing recipe) via a RATIO between two
as-of queries of the SAME PIT facade -- never a re-derivation of that
methodology. All PIT reads go through `backtest.data.pit_access.
BoundedPITAccess`, the one sanctioned gateway (Spec #005 SS3/SS6).
"""
from __future__ import annotations

import math
from typing import Optional

import pandas as pd

from data_foundation.model.entities import ActionType, CorporateAction
from data_foundation.pit.access import PITPriceBar, _is_action_known_for_adjustment
from discovery.features import volatility

from backtest.data.pit_access import BoundedPITAccess
from backtest.exits.entities import (
    ENTRY_INVALID_PROTECTIVE_LEVELS,
    ENTRY_NO_ENTRY_BAR,
    ENTRY_NO_VALID_STOP_BASIS,
    StopManagedPosition,
)

# Falls back to #002's own default if the caller doesn't supply a config
# explicitly (mirrors the fixed window Discovery itself uses in V1,
# discovery/config/features.yaml) -- never a silently different window.
_DEFAULT_VOLATILITY_CONFIG = {
    "atr_window": 14, "bb_window": 20, "bb_num_std": 2.0, "realized_vol_window": 20,
}


def is_authorized_at_open(availability_date: str, session_date: str, known_before_open_same_day: bool = False) -> bool:
    """Amendment section 3's explicit temporal-access-at-open rule,
    applied to the KNOWLEDGE/availability date (see `knowledge_date()`
    below) -- NEVER to `effective_date` directly (GPT review, round 2,
    finding #1): effectiveness and knowability are separate axes, and a
    split effective today that was ANNOUNCED yesterday needs no evidence
    at all, while a split effective days ago but only disclosed TODAY
    needs exactly the same same-day scrutiny a same-day-effective split
    would. `known_before_open_same_day` must be genuine temporal evidence
    beyond the bare date (e.g. a verified pre-market disclosure
    timestamp) -- NEVER inferred from `available_at`'s date-only value,
    which cannot by itself distinguish morning from afternoon. Absent
    such evidence, the default is False (not authorized)."""
    if availability_date < session_date:
        return True
    if availability_date == session_date:
        return known_before_open_same_day
    return False


def knowledge_date(action: CorporateAction) -> str:
    """The date this action's EXISTENCE became knowable -- `available_at`
    when a validated knowledge-time signal exists, else the Level 1
    fallback to `effective_date` (mirrors `derive_corporate_action_pit_
    status()`'s own two-path policy in `data_foundation.pit.access`
    exactly, never a third, independent knowledge-time model)."""
    return action.available_at if action.available_at is not None else action.effective_date


def _find_bar(bars: list[PITPriceBar], date: str) -> Optional[PITPriceBar]:
    for b in bars:
        if b.date == date:
            return b
    return None


def _split_adjusted_ohlc_df(bars: list[PITPriceBar]) -> pd.DataFrame:
    """High/low/close all under the SAME as-of query's split-adjustment
    (PATCH #001-D fields) -- internally coherent, so a split anywhere
    inside the window never produces an artificial true-range spike.
    Deliberately NOT `discovery.engine._price_series_to_df()`'s own
    raw-high/low + split-adjusted-close mix (see module docstring)."""
    return pd.DataFrame({
        "high": [b.split_adjusted_high for b in bars],
        "low": [b.split_adjusted_low for b in bars],
        "close": [b.split_adjusted_close for b in bars],
    })


def compute_atr_from_bars(bars: list[PITPriceBar], volatility_config: Optional[dict] = None) -> Optional[float]:
    """ATR_14 at the LAST bar in `bars` (caller passes exactly the window
    ending at the session of interest, inclusive, per section 3: "Bara
    zilei intrării NU participă la calcul"). None if the series is too
    short or the value is NaN/non-finite."""
    if not bars:
        return None
    cfg = volatility_config or _DEFAULT_VOLATILITY_CONFIG
    df = _split_adjusted_ohlc_df(bars)
    result = volatility.compute(df, cfg)
    value = result["ATR_14"].iloc[-1]
    if pd.isna(value) or not math.isfinite(float(value)):
        return None
    return float(value)


def check_new_splits_authorized_at_open(
    pit: BoundedPITAccess, security_id: str, entry_date: str,
    same_day_evidence: frozenset = frozenset(),
) -> tuple[bool, tuple[str, ...]]:
    """For every SPLIT/REVERSE_SPLIT action known (per #001's own,
    unmodified `_is_action_known_for_adjustment` gate) as of `entry_date`:
    apply `is_authorized_at_open()` to its `knowledge_date()`, not its
    `effective_date`. Returns (authorized, blocking_action_ids) --
    non-empty blocking ids means the basis reconciliation below must not
    proceed (NO_VALID_STOP_BASIS).

    GPT review round 3, finding #2: there is no `effective_date` cutoff
    (e.g. "only after signal_date") that safely excludes a split from
    this check -- a split effective AT OR BEFORE signal_date can still
    need same-day-at-entry authorization if its own KNOWLEDGE only
    arrived between signal_date and entry_date (a retroactive disclosure
    affecting the ATR window's own internal coherence, not merely the
    signal-to-entry re-expression the earlier, narrower filter was
    written for). A split whose knowledge_date is safely in the past
    (the overwhelming majority) trivially auto-authorizes here regardless
    -- removing the filter only changes behavior for genuinely recent/
    same-day disclosures, which is exactly what needs checking."""
    actions = pit.get_corporate_actions_as_of(security_id, entry_date)
    blocking = []
    for pca in actions:
        a = pca.action
        if a.action_type not in (ActionType.SPLIT.value, ActionType.REVERSE_SPLIT.value):
            continue
        if not _is_action_known_for_adjustment(a, entry_date):
            continue
        if not is_authorized_at_open(knowledge_date(a), entry_date, a.action_id in same_day_evidence):
            blocking.append(a.action_id)
    return (not blocking, tuple(sorted(blocking)))


def compute_atr_basis_reconciliation(
    pit: BoundedPITAccess, security_id: str, signal_date: str, entry_date: str,
    same_day_evidence: frozenset = frozenset(), volatility_config: Optional[dict] = None,
) -> tuple[Optional[float], tuple[str, ...]]:
    """Amendment section 3: ATR_14(s), the window of bars up to and
    including the signal session, expressed on the entry price's basis
    "folosind NUMAI ajustările efective ȘI CUNOSCUTE LA MOMENTUL
    DESCHIDERII" (using only adjustments effective AND KNOWN AT THE
    MOMENT OF OPENING). Returns (atr_reexpressed_on_entry_basis,
    diagnostics) -- `None` on the first element means the entry must be
    rejected via NO_VALID_STOP_BASIS; `diagnostics` names why.

    GPT review round 3, finding #2: the window is fetched via a SINGLE
    `get_price_series_as_of(as_of=entry_date)` query and computed
    directly on THOSE (already correctly, per-date, split-adjusted)
    bars -- never the previous two-step "freeze the window as of
    signal_date, then multiply the whole ATR by one ratio" shortcut. That
    shortcut silently missed a split effective AT OR BEFORE signal_date
    (inside or before the window) whose knowledge only arrives between
    signal_date and entry_date: frozen-as-of-signal_date bars could never
    reflect it, and the ratio (computed from signal_date's own bar, which
    a split effective AT OR BEFORE it structurally never rescales) was
    always 1.0 regardless, so the distortion passed through undetected.
    Fetching directly at `as_of=entry_date` uses #001's own `compute_
    factors()` recipe per-date, which handles any number of splits,
    anywhere in the window, correctly and uniformly per split (it reacts
    only to SPLIT/REVERSE_SPLIT actions, each a well-defined, clean
    multiplicative constant before its own effective_date) -- there is no
    separate "uniformity" precondition left to verify, because this IS
    the bar-by-bar reconciliation the amendment's non-uniform-case text
    calls for, not the single-ratio shortcut it warns cannot substitute
    for it. PIT-safety: this uses ONLY facts known as of `entry_date` (our
    actual "now" when computing the trade's initial protection) to
    correctly re-express HISTORICAL bars -- never anything known only
    after entry_date.

    GPT review round 3 follow-up: the single-query rewrite above dropped
    the explicit check that a bar dated EXACTLY `signal_date` exists.
    ATR_14(s) is defined at the signal session itself (section 3) -- not
    at whatever session happens to be the latest one on or before it.
    Filtering `bars_as_of_entry` to `date <= signal_date` and checking
    only the resulting COUNT silently accepts a window whose last bar is
    an earlier session (e.g. a data gap or a non-trading day misalignment
    leaves no bar dated `signal_date`), producing an ATR computed as of
    that earlier session while it is reported and used as ATR_14(s). The
    explicit `_find_bar(..., signal_date)` check below closes this:
    missing signal-session bar is SIGNAL_BAR_MISSING, propagated by
    `open_stop_managed_position` into ENTRY_NO_VALID_STOP_BASIS exactly
    like every other basis-rejection reason here."""
    authorized, blocking = check_new_splits_authorized_at_open(pit, security_id, entry_date, same_day_evidence)
    if not authorized:
        return None, blocking

    bars_as_of_entry = pit.get_price_series_as_of(security_id, entry_date)
    if _find_bar(bars_as_of_entry, signal_date) is None:
        return None, ("SIGNAL_BAR_MISSING",)

    bars_window = [b for b in bars_as_of_entry if b.date <= signal_date]
    cfg = volatility_config or _DEFAULT_VOLATILITY_CONFIG
    if len(bars_window) < cfg["atr_window"]:
        return None, ("INSUFFICIENT_HISTORY_FOR_ATR_WINDOW",)

    atr = compute_atr_from_bars(bars_window, cfg)
    if atr is None or not math.isfinite(atr) or not (atr > 0):
        return None, ("ATR_NOT_STRICTLY_POSITIVE",)
    return atr, ()


def compute_initial_protection(
    direction: str, entry_fill_price: float, atr_reexpressed: float, k: float, r_multiple: Optional[float],
) -> tuple[Optional[float], Optional[float], Optional[float], Optional[str]]:
    """Amendment section 3's long/short formulas. Returns
    (active_stop, initial_risk, target_price, rejection_reason) -- exactly
    one of (the first three) / (the last) is populated. INVALID_
    PROTECTIVE_LEVELS per section 2 rule #4 -- covers both the economic
    ordering AND the finiteness of every computed level (a non-finite
    result, e.g. from a corrupted upstream ratio, is exactly as invalid
    as a backwards one)."""
    if direction == "LONG":
        active_stop = entry_fill_price - k * atr_reexpressed
        initial_risk = entry_fill_price - active_stop
        if not (math.isfinite(active_stop) and math.isfinite(initial_risk) and 0 < active_stop < entry_fill_price):
            return None, None, None, ENTRY_INVALID_PROTECTIVE_LEVELS
        target_price = None
        if r_multiple is not None:
            target_price = entry_fill_price + r_multiple * initial_risk
            if not (math.isfinite(target_price) and target_price > entry_fill_price):
                return None, None, None, ENTRY_INVALID_PROTECTIVE_LEVELS
    elif direction == "SHORT":
        active_stop = entry_fill_price + k * atr_reexpressed
        initial_risk = active_stop - entry_fill_price
        if not (math.isfinite(active_stop) and math.isfinite(initial_risk) and active_stop > entry_fill_price > 0):
            return None, None, None, ENTRY_INVALID_PROTECTIVE_LEVELS
        target_price = None
        if r_multiple is not None:
            target_price = entry_fill_price - r_multiple * initial_risk
            if not (math.isfinite(target_price) and 0 < target_price < entry_fill_price):
                return None, None, None, ENTRY_INVALID_PROTECTIVE_LEVELS
    else:
        raise ValueError(f"direction must be 'LONG' or 'SHORT', got {direction!r}")
    return active_stop, initial_risk, target_price, None


def open_stop_managed_position(
    pit: BoundedPITAccess, security_id: str, direction: str, signal_date: str, entry_date: str,
    entry_fill_price: Optional[float], k: float, r_multiple: Optional[float], fraction: Optional[float],
    same_day_split_evidence: frozenset = frozenset(), volatility_config: Optional[dict] = None,
) -> tuple[Optional[StopManagedPosition], Optional[str]]:
    """Orchestrates amendment sections 1-4's entry sequence, minus the two
    dispositions this function deliberately never touches: SUPPRESSED_
    STAGE_BOUNDARY (calendar-only, no price read -- the caller's own
    zone/calendar check, before this is ever invoked) and NO_ENTRY_BAR,
    signaled here by `entry_fill_price=None` (the caller determines
    whether the entry bar itself exists; this function only reads price
    history for the ATR/split-basis reconciliation, never for the entry
    fill). Returns (position, rejection_reason) -- exactly one is None."""
    if entry_fill_price is None:
        return None, ENTRY_NO_ENTRY_BAR

    atr_reexpressed, _diagnostics = compute_atr_basis_reconciliation(
        pit, security_id, signal_date, entry_date, same_day_split_evidence, volatility_config,
    )
    if atr_reexpressed is None:
        return None, ENTRY_NO_VALID_STOP_BASIS

    active_stop, initial_risk, target_price, rejection = compute_initial_protection(
        direction, entry_fill_price, atr_reexpressed, k, r_multiple,
    )
    if rejection is not None:
        return None, rejection

    position = StopManagedPosition(
        security_id=security_id, direction=direction, entry_date=entry_date, signal_date=signal_date,
        entry_fill_price=entry_fill_price, k=k, r_multiple=r_multiple, fraction=fraction,
        active_stop=active_stop, initial_risk=initial_risk, target_price=target_price,
    )
    return position, None
