"""Spec #005 Batch 3 -- entry-time validation and initial protective-stop/
target formulas for STOP_MANAGED_INVALIDATION (docs/spec005_exit_
amendment_v1.0.md, ACCEPTED, sections 2-3).

ATR reuses #002's existing ATR_14 (Wilder method,
`discovery.features.volatility.compute()`) VERBATIM, on the SAME mixed
raw-high/low + split-adjusted-close basis `discovery.engine.
_price_series_to_df()` already builds it from -- no new indicator, no
"improved" fully-split-adjusted variant invented here. Split-basis
reconciliation reuses #001's own `split_adjusted_close` (itself
`compute_factors()`'s existing recipe) via a RATIO between two as-of
queries of the SAME PIT facade -- never a re-derivation of that
methodology. All PIT reads go through `backtest.data.pit_access.
BoundedPITAccess`, the one sanctioned gateway (Spec #005 SS3/SS6).
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from data_foundation.model.entities import ActionType
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


def is_authorized_at_open(effective_date: str, session_date: str, known_before_open_same_day: bool = False) -> bool:
    """Amendment section 3's explicit temporal-access-at-open rule.
    `known_before_open_same_day` must be genuine temporal evidence beyond
    the bare date (e.g. a verified pre-market disclosure timestamp) --
    NEVER inferred from `available_at`'s date-only value, which cannot by
    itself distinguish morning from afternoon. Absent such evidence, the
    default is False (not authorized)."""
    if effective_date < session_date:
        return True
    if effective_date == session_date:
        return known_before_open_same_day
    return False


def _find_bar(bars: list[PITPriceBar], date: str) -> Optional[PITPriceBar]:
    for b in bars:
        if b.date == date:
            return b
    return None


def _raw_high_low_split_adjusted_close_df(bars: list[PITPriceBar]) -> pd.DataFrame:
    """Same per-field basis as `discovery.engine._price_series_to_df()`
    (raw high/low, split-adjusted close) -- deliberately NOT re-derived
    from a different, "more correct" fully-adjusted basis; the amendment
    requires byte-identical reuse of #002's existing ATR_14, warts (the
    raw-high/low convention) included."""
    return pd.DataFrame({
        "high": [b.raw_high for b in bars],
        "low": [b.raw_low for b in bars],
        "close": [b.split_adjusted_close for b in bars],
    })


def compute_atr_from_bars(bars: list[PITPriceBar], volatility_config: Optional[dict] = None) -> Optional[float]:
    """ATR_14 at the LAST bar in `bars` (caller passes exactly the window
    ending at the session of interest, inclusive, per section 3: "Bara
    zilei intrării NU participă la calcul"). None if the series is too
    short or the value is NaN."""
    if not bars:
        return None
    cfg = volatility_config or _DEFAULT_VOLATILITY_CONFIG
    df = _raw_high_low_split_adjusted_close_df(bars)
    result = volatility.compute(df, cfg)
    value = result["ATR_14"].iloc[-1]
    if pd.isna(value):
        return None
    return float(value)


def check_new_splits_authorized_at_open(
    pit: BoundedPITAccess, security_id: str, signal_date: str, entry_date: str,
    same_day_evidence: frozenset = frozenset(),
) -> tuple[bool, tuple[str, ...]]:
    """For every SPLIT/REVERSE_SPLIT action strictly after `signal_date`
    (a pre-signal split is already baked into both bases and needs no
    check) and known (per #001's own, unmodified
    `_is_action_known_for_adjustment` gate) as of `entry_date`: apply
    `is_authorized_at_open()`. Returns (authorized, blocking_action_ids)
    -- non-empty blocking ids means the basis reconciliation below must
    not proceed (NO_VALID_STOP_BASIS)."""
    actions = pit.get_corporate_actions_as_of(security_id, entry_date)
    blocking = []
    for pca in actions:
        a = pca.action
        if a.action_type not in (ActionType.SPLIT.value, ActionType.REVERSE_SPLIT.value):
            continue
        if a.effective_date <= signal_date:
            continue
        if not _is_action_known_for_adjustment(a, entry_date):
            continue
        if not is_authorized_at_open(a.effective_date, entry_date, a.action_id in same_day_evidence):
            blocking.append(a.action_id)
    return (not blocking, tuple(sorted(blocking)))


def compute_atr_basis_reconciliation(
    pit: BoundedPITAccess, security_id: str, signal_date: str, entry_date: str,
    same_day_evidence: frozenset = frozenset(), volatility_config: Optional[dict] = None,
) -> tuple[Optional[float], tuple[str, ...]]:
    """Amendment section 3: ATR_14(s) re-expressed on the entry price's
    basis via the ratio factor(s, as_of=entry_date)/factor(s, as_of=s),
    both obtained from #001's own `split_adjusted_close` (never a
    re-derivation of `compute_factors()`). Returns
    (atr_reexpressed_on_entry_basis, diagnostics) -- `None` on the first
    element means the entry must be rejected via NO_VALID_STOP_BASIS;
    `diagnostics` names why."""
    authorized, blocking = check_new_splits_authorized_at_open(pit, security_id, signal_date, entry_date, same_day_evidence)
    if not authorized:
        return None, blocking

    bars_as_of_signal = pit.get_price_series_as_of(security_id, signal_date)
    bars_window = [b for b in bars_as_of_signal if b.date <= signal_date]
    cfg = volatility_config or _DEFAULT_VOLATILITY_CONFIG
    if len(bars_window) < cfg["atr_window"]:
        return None, ("INSUFFICIENT_HISTORY_FOR_ATR_WINDOW",)

    atr_s = compute_atr_from_bars(bars_window, cfg)
    if atr_s is None or not (atr_s > 0):
        return None, ("ATR_NOT_STRICTLY_POSITIVE",)

    bar_signal_as_of_signal = _find_bar(bars_as_of_signal, signal_date)
    bars_as_of_entry = pit.get_price_series_as_of(security_id, entry_date)
    bar_signal_as_of_entry = _find_bar(bars_as_of_entry, signal_date)
    if bar_signal_as_of_signal is None or bar_signal_as_of_entry is None:
        return None, ("SIGNAL_BAR_MISSING",)

    close_asof_signal = bar_signal_as_of_signal.split_adjusted_close
    close_asof_entry = bar_signal_as_of_entry.split_adjusted_close
    if not close_asof_signal or close_asof_entry is None:
        return None, ("BASIS_RATIO_UNCOMPUTABLE",)

    ratio = close_asof_entry / close_asof_signal
    return atr_s * ratio, ()


def compute_initial_protection(
    direction: str, entry_fill_price: float, atr_reexpressed: float, k: float, r_multiple: Optional[float],
) -> tuple[Optional[float], Optional[float], Optional[float], Optional[str]]:
    """Amendment section 3's long/short formulas. Returns
    (active_stop, initial_risk, target_price, rejection_reason) -- exactly
    one of (the first three) / (the last) is populated. INVALID_
    PROTECTIVE_LEVELS per section 2 rule #4."""
    if direction == "LONG":
        active_stop = entry_fill_price - k * atr_reexpressed
        initial_risk = entry_fill_price - active_stop
        if not (0 < active_stop < entry_fill_price):
            return None, None, None, ENTRY_INVALID_PROTECTIVE_LEVELS
        target_price = None
        if r_multiple is not None:
            target_price = entry_fill_price + r_multiple * initial_risk
            if not (target_price > entry_fill_price):
                return None, None, None, ENTRY_INVALID_PROTECTIVE_LEVELS
    elif direction == "SHORT":
        active_stop = entry_fill_price + k * atr_reexpressed
        initial_risk = active_stop - entry_fill_price
        if not (active_stop > entry_fill_price > 0):
            return None, None, None, ENTRY_INVALID_PROTECTIVE_LEVELS
        target_price = None
        if r_multiple is not None:
            target_price = entry_fill_price - r_multiple * initial_risk
            if not (0 < target_price < entry_fill_price):
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
