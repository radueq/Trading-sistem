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
) -> Optional[TrancheMaeMfe]:
    """`bars` must cover the tranche's own holding window (entry date
    through `exit_date`, inclusive). Returns None only if no usable
    observation exists at all (e.g. an empty `bars` list)."""
    d = _direction_sign(direction)
    excursions: list[float] = []
    coverage = COVERAGE_FULL

    for b in bars:
        if b.date == exit_date:
            coverage = COVERAGE_PARTIAL_EXIT_DAY_EXCLUDED
            if b.open is not None:
                excursions.append(d * (b.open - entry_fill) / entry_fill)
            excursions.append(d * (exit_fill - entry_fill) / entry_fill)
            continue
        if b.high is not None:
            excursions.append(d * (b.high - entry_fill) / entry_fill)
        if b.low is not None:
            excursions.append(d * (b.low - entry_fill) / entry_fill)

    if not excursions:
        return None
    return TrancheMaeMfe(mae=min(excursions), mfe=max(excursions), coverage=coverage)
