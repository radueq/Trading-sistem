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
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# COVERAGE_FULL is retained for API completeness (e.g. a future
# sub-day-precision data source that removes the exit-day ambiguity
# entirely) but is NOT reachable from `compute_tranche_mae_mfe()` today:
# every tranche has some exit day, and that day's own high/low is always
# either deliberately excluded (its ordering vs. the fill is unknowable
# from daily OHLC) or altogether absent from `bars` -- both cases are
# PARTIAL_EXIT_DAY_EXCLUDED, never FULL (GPT review round 2, finding #6b).
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
) -> TrancheMaeMfe:
    """`bars` should cover the tranche's own holding window (entry date
    through `exit_date`, inclusive) -- but the exit fill itself is ALWAYS
    a valid observation on its own, so this never returns None: an empty
    (or exit-day-only) `bars` list still yields a degenerate result from
    the exit fill alone, correctly labeled PARTIAL_EXIT_DAY_EXCLUDED.

    GPT review round 2, finding #6b: coverage must never read FULL when
    data is actually missing -- absence of data proves nothing about
    coverage, so it can never be presented as complete. This now flags
    PARTIAL_EXIT_DAY_EXCLUDED whenever: (a) `exit_date`'s own bar is
    absent from `bars` entirely (its true range was never even supplied,
    not just excluded on purpose), or (b) ANY other day in the window is
    missing a high or low value. The exit fill itself is now ALWAYS
    included as an excursion, regardless of whether a bar for `exit_date`
    was present -- previously, an exit day absent from `bars` silently
    dropped the exit fill from consideration entirely, understating the
    true MAE/MFE whenever the fill itself was the most extreme point."""
    d = _direction_sign(direction)
    excursions: list[float] = []
    coverage = COVERAGE_FULL
    exit_day_bar_present = False

    for b in bars:
        if b.date == exit_date:
            exit_day_bar_present = True
            coverage = COVERAGE_PARTIAL_EXIT_DAY_EXCLUDED
            if b.open is not None:
                excursions.append(d * (b.open - entry_fill) / entry_fill)
            continue
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
