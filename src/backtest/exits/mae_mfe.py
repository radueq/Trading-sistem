"""Spec #005 Batch 3 -- per-tranche MAE/MFE for STOP_MANAGED_INVALIDATION
(docs/spec005_exit_amendment_v1.0.md, ACCEPTED, section 12).

Partial profit does not end the whole position's exposure -- the
remainder stays exposed after the sale, including the rest of that same
day -- so MAE/MFE is reported PER TRANCHE, never as one combined
"position" number when two tranches exist. The partial-observed-day
exclusion applies uniformly to BOTH an intraday stop and an intraday
target close (generalized here to any exit day at all, open-fill or
intraday: on the day a tranche's own exit is filled, only that day's
open and the exit fill itself are usable OHLC-derived inputs -- the
day's low/high cannot be ordered against the fill from daily OHLC alone,
whether the fill happened at the open or mid-session).

Closure verification finding (post-`9feb4a5`): `compute_tranche_mae_mfe()`
below was correct and unit-tested (`test_28`) but had NO caller anywhere
in `engine.py`/`session.py`/`legacy.py` -- no `Tranche`/`StopManagedPosition`/
`LegacyPosition` produced by a real `run_stage()` result ever carried an
MAE/MFE value, so section 12's REPORTING requirement was not actually met
despite the formula existing. `evaluate_stop_managed_position_mae_mfe()`/
`evaluate_legacy_position_mae_mfe()` (bottom of this module) now wire it
against real positions -- as a SEPARATE evaluation/reporting pass over an
already-produced `run_stage()` result, never by adding fields to
`StopManagedPosition`/`LegacyPosition`/`Tranche` themselves (both stay
byte-for-byte unchanged)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from backtest.data.pit_access import BoundedPITAccess
    from backtest.exits.entities import LegacyPosition, StopManagedPosition

# COVERAGE_FULL was previously unreachable (GPT review round 2, finding
# #6b) because every caller passed a REAL execution's own exit day, which
# is always ambiguous by construction (the fill's ordering against that
# day's own high/low is unknowable from daily OHLC alone) -- so coverage
# was always PARTIAL_EXIT_DAY_EXCLUDED whenever an exit day existed at
# all. It IS reachable now: `compute_tranche_mae_mfe(..., exit_is_real_
# execution=False)` (a still-open remainder marked-to-market at the stage
# boundary, closure verification fix post-9feb4a5) treats its own final
# day as a NORMAL, fully-held day -- no intraday exit happened on it, so
# excluding its high/low would misrepresent a fully-observed day as if an
# execution ambiguity existed there. FULL is reported when every day in
# that window, including the final one, has both a high and a low.
COVERAGE_FULL = "FULL"
COVERAGE_PARTIAL_EXIT_DAY_EXCLUDED = "PARTIAL_EXIT_DAY_EXCLUDED"


@dataclass(frozen=True)
class DailyRange:
    """Split-adjusted OHLC for one session, the minimal shape this module
    needs -- callers adapt from `PITPriceBar`/whatever their own bar type
    is."""
    date: str
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]


@dataclass(frozen=True)
class TrancheMaeMfe:
    mae: float  # most adverse excursion observed, signed (negative = adverse), relative to entry_fill
    mfe: float  # most favorable excursion observed, signed (positive = favorable)
    coverage: str  # COVERAGE_FULL | COVERAGE_PARTIAL_EXIT_DAY_EXCLUDED


def _direction_sign(direction: str) -> float:
    if direction == "LONG":
        return 1.0
    if direction == "SHORT":
        return -1.0
    raise ValueError(f"direction must be 'LONG' or 'SHORT', got {direction!r}")


def compute_tranche_mae_mfe(
    direction: str, entry_fill: float, bars: list[DailyRange], exit_date: str, exit_fill: float,
    exit_is_real_execution: bool = True,
) -> TrancheMaeMfe:
    """`bars` should cover the tranche's own holding window (entry date
    through `exit_date`, inclusive) -- but the exit fill itself is ALWAYS
    a valid observation on its own, so this never returns None: an empty
    (or exit-day-only) `bars` list still yields a degenerate result from
    the exit fill alone, correctly labeled PARTIAL_EXIT_DAY_EXCLUDED.

    `exit_is_real_execution` (default `True`, preserves every existing
    caller's behavior byte-for-byte -- closure verification fix, post-
    `9feb4a5`): `True` for a tranche that actually closed via a real fill
    (stop, target, invalidation, time exit, cap) -- `exit_date`'s own bar
    is genuinely ambiguous (the fill's ordering against that day's own
    high/low cannot be established from daily OHLC alone) and is excluded
    from the high/low sweep, same as always. `False` for a position/
    remainder still open at the stage boundary, marked-to-market for
    reporting (`CENSORED_AT_HORIZON`): no intraday execution happened on
    that final day at all, so it is treated like any OTHER day in the
    window -- its own high/low ARE genuine, fully-observable inputs.
    Excluding them in this case would report a fully-held day as if an
    intraday exit had occurred on it, which section 12 never asks for.
    `exit_fill` in that case is the mark-to-market price (the final
    authorized close) and is still added as an extra observed excursion.

    GPT review round 2, finding #6b: coverage must never read FULL when
    data is actually missing -- absence of data proves nothing about
    coverage, so it can never be presented as complete. This flags
    PARTIAL_EXIT_DAY_EXCLUDED whenever: (a) `exit_date`'s own bar is
    absent from `bars` entirely (its true range was never even supplied),
    (b) `exit_is_real_execution` is `True` (that day is ALWAYS ambiguous
    by construction, regardless of data completeness), or (c) ANY day in
    the window is missing a high or low value. The exit fill itself is
    ALWAYS included as an excursion, regardless of whether a bar for
    `exit_date` was present -- an exit day absent from `bars` would
    otherwise silently drop the exit fill from consideration entirely,
    understating the true MAE/MFE whenever the fill itself was the most
    extreme point.

    GPT review round 3, finding #4: the excursion AT ENTRY is always
    KNOWN -- by definition, price == entry_fill at that moment, so its
    excursion is exactly 0.0 -- and this is included UNCONDITIONALLY,
    regardless of `bars`. Without it, an empty-bars tranche with a
    favorable exit (e.g. entry 100, exit 110, no bars) wrongly reported
    MAE == MFE == +10% instead of the correct MAE=0%/MFE=+10% (the price
    never actually traded below entry -- 0% IS the true worst point
    observed); symmetrically, a pure-loss tranche must never report a
    positive MFE from this alone."""
    d = _direction_sign(direction)
    excursions: list[float] = [0.0]  # the entry moment itself: always a known, zero excursion.
    coverage = COVERAGE_FULL
    exit_day_bar_present = False

    for b in bars:
        if b.date == exit_date:
            exit_day_bar_present = True
            if exit_is_real_execution:
                coverage = COVERAGE_PARTIAL_EXIT_DAY_EXCLUDED
                if b.open is not None:
                    excursions.append(d * (b.open - entry_fill) / entry_fill)
                continue
            # else: fall through to the SAME high/low handling as any
            # other day below -- this day was fully held, no real
            # intraday exit occurred on it.
        if b.high is None or b.low is None:
            coverage = COVERAGE_PARTIAL_EXIT_DAY_EXCLUDED
            if b.high is not None:
                excursions.append(d * (b.high - entry_fill) / entry_fill)
            if b.low is not None:
                excursions.append(d * (b.low - entry_fill) / entry_fill)
            continue
        excursions.append(d * (b.high - entry_fill) / entry_fill)
        excursions.append(d * (b.low - entry_fill) / entry_fill)

    excursions.append(d * (exit_fill - entry_fill) / entry_fill)
    if not exit_day_bar_present:
        coverage = COVERAGE_PARTIAL_EXIT_DAY_EXCLUDED

    return TrancheMaeMfe(mae=min(excursions), mfe=max(excursions), coverage=coverage)


@dataclass(frozen=True)
class PositionMaeMfe:
    """One tranche's MAE/MFE, unambiguously associated to the position and
    tranche it belongs to -- section 12's own "per tranche, never one
    combined position number" requirement, as a standalone reporting
    record rather than a field on `StopManagedPosition`/`LegacyPosition`
    themselves (neither is modified)."""
    security_id: str
    strategy_variant_id: str
    tranche_kind: str  # "PARTIAL_PROFIT" | "REMAINDER"
    mae_mfe: TrancheMaeMfe


def _window_bars(pit: "BoundedPITAccess", security_id: str, as_of: str, start_date: str, end_date: str) -> list[DailyRange]:
    """Bars for `[start_date, end_date]`, queried `as_of` the SAME date
    the tranche itself resolved on (its own close date, or the stage's
    final mark date for a still-open remainder) -- every bar returned is
    therefore split-adjusted on that ONE basis, coherent with whichever
    entry price reference the caller pairs it with (see the two
    `evaluate_*_position_mae_mfe()` functions below)."""
    bars = pit.get_price_series_as_of(security_id, as_of)
    return [
        DailyRange(date=b.date, open=b.split_adjusted_open, high=b.split_adjusted_high, low=b.split_adjusted_low)
        for b in bars if start_date <= b.date <= end_date
    ]


def evaluate_stop_managed_position_mae_mfe(
    pit: "BoundedPITAccess", position: "StopManagedPosition", final_mark_date: str, mark_final: Optional[float],
) -> tuple[PositionMaeMfe, ...]:
    """Amendment section 12, wired against a real `run_stage()` result.
    Returns a SEPARATE record per tranche that actually exists on this
    position (0, 1, or 2 records) -- never merged into one "position"
    number. `position` itself is never modified.

    Price basis coherence (the requirement behind this whole function):
    each tranche's own bars are queried `as_of` THAT tranche's own
    resolution date and paired with the entry price reference frozen (or
    current) on that SAME basis -- `Tranche.entry_fill_price_reference`
    for a closed tranche (frozen exactly when IT closed, section 6),
    `position.entry_fill_price` (continuously reconciled) for a still-open
    remainder queried as of the stage's own final mark date. Mixing a
    frozen reference from one as-of basis with bars queried on a DIFFERENT
    one would silently reintroduce the exact split-ratio error `entry_
    fill_price_reference` exists to prevent (GPT review round 2, finding
    #5)."""
    records: list[PositionMaeMfe] = []

    if position.partial_tranche is not None:
        t = position.partial_tranche
        bars = _window_bars(pit, position.security_id, t.exit_date, position.entry_date, t.exit_date)
        result = compute_tranche_mae_mfe(
            position.direction, t.entry_fill_price_reference, bars, t.exit_date, t.exit_fill_price,
            exit_is_real_execution=True,
        )
        records.append(PositionMaeMfe(position.security_id, position.strategy_variant_id, t.kind, result))

    if position.closed and position.close_tranche is not None:
        t = position.close_tranche
        bars = _window_bars(pit, position.security_id, t.exit_date, position.entry_date, t.exit_date)
        result = compute_tranche_mae_mfe(
            position.direction, t.entry_fill_price_reference, bars, t.exit_date, t.exit_fill_price,
            exit_is_real_execution=True,
        )
        records.append(PositionMaeMfe(position.security_id, position.strategy_variant_id, t.kind, result))
    elif not position.closed and mark_final is not None:
        bars = _window_bars(pit, position.security_id, final_mark_date, position.entry_date, final_mark_date)
        result = compute_tranche_mae_mfe(
            position.direction, position.entry_fill_price, bars, final_mark_date, mark_final,
            exit_is_real_execution=False,
        )
        records.append(PositionMaeMfe(position.security_id, position.strategy_variant_id, "REMAINDER", result))

    return tuple(records)


def evaluate_legacy_position_mae_mfe(
    pit: "BoundedPITAccess", position: "LegacyPosition", final_mark_date: str, mark_final: Optional[float],
) -> tuple[PositionMaeMfe, ...]:
    """The `LegacyPosition` (TIME_EXIT/SIGNAL_INVALIDATION) counterpart of
    `evaluate_stop_managed_position_mae_mfe()` -- narrower, since neither
    older family ever has a partial-profit tranche (module docstring of
    `backtest.exits.legacy`): always exactly one tranche's worth of
    record, or none for a position with nothing to report (e.g.
    `EXIT_FAILED`)."""
    if position.closed and position.close_tranche is not None:
        t = position.close_tranche
        bars = _window_bars(pit, position.security_id, t.exit_date, position.entry_date, t.exit_date)
        result = compute_tranche_mae_mfe(
            position.direction, t.entry_fill_price_reference, bars, t.exit_date, t.exit_fill_price,
            exit_is_real_execution=True,
        )
        return (PositionMaeMfe(position.security_id, position.strategy_variant_id, t.kind, result),)
    if not position.closed and mark_final is not None:
        bars = _window_bars(pit, position.security_id, final_mark_date, position.entry_date, final_mark_date)
        result = compute_tranche_mae_mfe(
            position.direction, position.entry_fill_price, bars, final_mark_date, mark_final,
            exit_is_real_execution=False,
        )
        return (PositionMaeMfe(position.security_id, position.strategy_variant_id, "REMAINDER", result),)
    return ()
