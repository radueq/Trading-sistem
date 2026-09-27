"""Spec #005 Batch 3 -- cost/return formulas for STOP_MANAGED_INVALIDATION
(docs/spec005_exit_amendment_v1.0.md, ACCEPTED, section 9).

Applies the base spec's own SS13 per-tranche formula IDENTICALLY to each
tranche (no new symbol, no pre-normalized cost) plus one NEW, separate
formula for a still-open/censored remainder (no imputed exit cost -- no
sale occurred). `F_x` (a tranche's own exit fill) is an INPUT here,
already reflecting whichever fill convention produced it (the target's
own level for a partial-profit tranche, per section 4; a stop/
invalidation level for a closing tranche, per section 5/7) -- this module
computes the RETURN from a given fill, it does not itself decide the
fill.
"""
from __future__ import annotations

from typing import Optional

from backtest.exits.entities import StopManagedPosition


def _direction_sign(direction: str) -> float:
    if direction == "LONG":
        return 1.0
    if direction == "SHORT":
        return -1.0
    raise ValueError(f"direction must be 'LONG' or 'SHORT', got {direction!r}")


def tranche_net_return(
    direction: str, entry_fill: float, exit_fill: float,
    commission_entry_rate: float, commission_exit_rate: float,
    borrow_annual_rate: float, holding_days: int,
) -> float:
    """Section 9's CLOSED-tranche formula, applied identically whether
    this is the partial-profit tranche or a fully-closed remainder:
    d*(F_x-F_e)/F_e - c_e - c_x*(F_x/F_e) - borrow_drag_tranșă. Borrow
    drag uses THIS tranche's own holding_days, fully unweighted here --
    weighting (w/1-w) is applied once, only at `aggregate_position_return`."""
    d = _direction_sign(direction)
    borrow_drag = borrow_annual_rate * holding_days / 365.0
    return d * (exit_fill - entry_fill) / entry_fill - commission_entry_rate - commission_exit_rate * (exit_fill / entry_fill) - borrow_drag


def open_remainder_net_return(
    direction: str, entry_fill: float, mark_final: float,
    commission_entry_rate: float, borrow_annual_rate: float, holding_days: int,
) -> float:
    """Section 9's SEPARATE formula for a still-open/censored remainder --
    no `c_x` term at all (no sale occurred, no exit cost to impute):
    d*(mark_final-F_e)/F_e - c_e - borrow_drag_până_la_limită."""
    d = _direction_sign(direction)
    borrow_drag = borrow_annual_rate * holding_days / 365.0
    return d * (mark_final - entry_fill) / entry_fill - commission_entry_rate - borrow_drag


def compute_w(position: StopManagedPosition) -> float:
    """Section 9: w = the configured fraction IFF partial profit was
    actually executed for this position; 0 otherwise (Control variant,
    or Parțial where the stop/invalidation closed the position before
    the target was ever reached). Never the raw remaining_quantity --
    a uniform split preserves the fraction : (1-fraction) proportion of
    the ORIGINAL position regardless of its rescaled share count."""
    if position.target_consumed and position.fraction is not None:
        return position.fraction
    return 0.0


def aggregate_position_return(w: float, partial_return: Optional[float], rest_return: float) -> float:
    """Section 9: rezultat_poziție = w*rezultat_tranșă_parțială +
    (1-w)*rezultat_rest. When w == 0, `partial_return` is never read --
    the term is ABSENT, not "0 times an undefined value" (never pass a
    contrived partial_return when w == 0; this function does not
    silently tolerate one either, to keep that absence visible)."""
    if w == 0.0:
        return rest_return
    if partial_return is None:
        raise ValueError("partial_return must be provided when w != 0 (partial profit was executed)")
    return w * partial_return + (1.0 - w) * rest_return
