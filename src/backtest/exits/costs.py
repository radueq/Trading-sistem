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

from backtest.exits.entities import EXIT_REASON_TARGET, StopManagedPosition, Tranche


def _direction_sign(direction: str) -> float:
    if direction == "LONG":
        return 1.0
    if direction == "SHORT":
        return -1.0
    raise ValueError(f"direction must be 'LONG' or 'SHORT', got {direction!r}")


def slippage_rate_from_bps(slippage_bps: float) -> float:
    """`CostAssumptions.slippage_exit_bps` is stored in basis points
    (`validate_cost_assumptions()` requires it `< 10000`, i.e. `< 100%`) --
    this is the one, single conversion to a plain rate, reused everywhere
    a slippage rate is needed so `/10000.0` never gets re-typed (and
    potentially mistyped) at each call site."""
    return slippage_bps / 10000.0


def apply_exit_slippage(direction: str, level_fill: float, exit_reason: str, slippage_exit_rate: float) -> float:
    """Amendment section 9 (base spec SS13's original formula, restated in
    full there): `F_x = nivel_fill` for the partial-profit tranche --
    "fara slippage advers" (section 4) -- and `F_x = nivel_fill*(1-d*s_x)`
    for ANY tranche closed via stop or trend invalidation. `level_fill` is
    the RAW level a `Tranche.exit_fill_price` already stores (the order's
    own trigger/fill level, e.g. the active stop, the target price, or a
    NEXT_SESSION_OPEN price) -- this function is the one place that turns
    that raw level into the ACTUAL fill `F_x` a cost/return computation
    must use; `Tranche.exit_fill_price` itself is never overwritten with
    the slipped value (MAE/MFE, `backtest.exits.mae_mfe`, deliberately
    tracks the raw market level the price actually reached, not this
    engine's own execution slippage)."""
    if exit_reason == EXIT_REASON_TARGET:
        return level_fill
    d = _direction_sign(direction)
    return level_fill * (1.0 - d * slippage_exit_rate)


def tranche_net_return(
    direction: str, entry_fill: float, exit_fill: float,
    commission_entry_rate: float, commission_exit_rate: float,
    borrow_annual_rate: float, holding_days: int,
) -> float:
    """Section 9's CLOSED-tranche formula, applied identically whether
    this is the partial-profit tranche or a fully-closed remainder:
    d*(F_x-F_e)/F_e - c_e - c_x*(F_x/F_e) - borrow_drag_tranșă. Borrow
    drag uses THIS tranche's own holding_days, fully unweighted here --
    weighting (w/1-w) is applied once, only at `aggregate_position_return`.

    `entry_fill` MUST be the tranche's OWN `entry_fill_price_reference`
    (see `Tranche`'s docstring) -- NEVER `position.entry_fill_price`
    directly, which a split reconciled AFTER this tranche closed may have
    since rescaled (GPT review round 2, finding #5). Prefer
    `net_return_for_tranche()` below, which enforces this by construction."""
    d = _direction_sign(direction)
    borrow_drag = borrow_annual_rate * holding_days / 365.0
    return d * (exit_fill - entry_fill) / entry_fill - commission_entry_rate - commission_exit_rate * (exit_fill / entry_fill) - borrow_drag


def net_return_for_tranche(
    tranche: Tranche, direction: str,
    commission_entry_rate: float, commission_exit_rate: float, borrow_annual_rate: float,
) -> float:
    """Convenience wrapper that always reads F_e from `tranche.
    entry_fill_price_reference` -- never from a position's possibly
    later-rescaled `entry_fill_price` -- so a caller cannot accidentally
    reproduce the exact bug GPT review round 2 finding #5 identified
    (entry 100, partial profit at 120 fixed historically, THEN a 2:1
    split rescales the live position's entry to 50 -- combining that 50
    with the historical 120 fill would report +140% instead of the
    correct +20%)."""
    return tranche_net_return(
        direction, tranche.entry_fill_price_reference, tranche.exit_fill_price,
        commission_entry_rate, commission_exit_rate, borrow_annual_rate, tranche.holding_days,
    )


def net_return_for_tranche_with_slippage(
    tranche: Tranche, direction: str,
    commission_entry_rate: float, commission_exit_rate: float, borrow_annual_rate: float,
    slippage_exit_rate: float,
) -> float:
    """The actual section-9 entry point for a CLOSED tranche's return:
    unlike `net_return_for_tranche()` above (which takes `tranche.
    exit_fill_price` as an already-final `F_x`, by design -- see this
    module's own docstring, "this module computes the RETURN from a given
    fill, it does not itself decide the fill"), this ALSO decides F_x from
    the tranche's raw level via `apply_exit_slippage()` first. Additive:
    `net_return_for_tranche()` itself is untouched, so every existing
    caller (and test) that already supplies its own pre-decided F_x keeps
    working byte-for-byte."""
    f_x = apply_exit_slippage(direction, tranche.exit_fill_price, tranche.exit_reason, slippage_exit_rate)
    return tranche_net_return(
        direction, tranche.entry_fill_price_reference, f_x,
        commission_entry_rate, commission_exit_rate, borrow_annual_rate, tranche.holding_days,
    )


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
