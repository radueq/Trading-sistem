"""Spec #005 Batch 3 -- per-tranche MAE/MFE for STOP_MANAGED_INVALIDATION
(docs/spec005_exit_amendment_v1.0.md, ACCEPTED, section 12), reconciled
against the base contract (docs/Spec_005_Backtesting_Exit_Evaluation_v1.0.md,
section 17/23) once it was recovered.

Partial profit does not end the whole position's exposure -- the
remainder stays exposed after the sale, including the rest of that same
day -- so MAE/MFE is reported PER TRANCHE, never as one combined
"position" number when two tranches exist.

Base spec section 17, verbatim: "MAE/MFE includes entry-day full range
for open entries and exit-day full range only for close exits. For open
exits include the exit open and prior held sessions, NEVER that exit
day's subsequent high/low." Section 23's own required test: "Open-exit
day later high/low excluded; close-exit day included." This means the
exit day's own treatment depends on WHICH fill convention closed the
tranche -- `FILL_MODE_*` below names the four cases this module
distinguishes. Amendment section 12 extends the OPEN/INTRADAY exclusion
explicitly to STOP_MANAGED_INVALIDATION's own two intraday-level fills
(stop, target); base section 17 governs everything else.

Radu's verdict on `8287ebb` (his own point 2, now confirmed against the
recovered base contract) found four defects in the first wiring pass,
fixed together here:

1. A whole missing session, or a non-finite OHLC value, inside a
   tranche's own window must never leave coverage reading FULL -- FULL
   is a positive claim of completeness, never a default for absent data.
2. The open/intraday/close/censored fill conventions require genuinely
   different treatment of the resolution day's own high/low, not one
   boolean collapsing all four into "exclude" vs "include" -- the
   earlier `exit_is_real_execution: bool` wrongly excluded TIME_EXIT/
   MAX_HOLDING_BARS_FORCED_EXIT's own close-fill day, which base section
   17 requires to be FULLY included (the position held through that
   whole day, up to and including the close that closed it).
3. `EXIT_FAILED` must never be reported as an ordinary censored
   remainder -- `final_closes`/`mark_final` is keyed by SECURITY, not by
   position, so a failed position sharing a security with a genuinely
   censored one must not silently borrow that mark.
4. `PositionMaeMfe` must carry a genuinely unique identity. Keying only
   on (security_id, strategy_variant_id, tranche_kind) collides when the
   same variant/security trades more than once within one stage (a
   TIME_EXIT(1) reopening after its own same-day exit is the ordinary
   case this engine already produces) -- `entry_date` is added so two
   successive trades of the same variant never produce indistinguishable
   records.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Sequence

from backtest.exits.entities import (
    EXIT_REASON_INVALIDATION,
    EXIT_REASON_MAX_HOLDING_BARS_FORCED_EXIT,
    EXIT_REASON_SIGNAL_INVALIDATION,
    EXIT_REASON_STOP,
    EXIT_REASON_TARGET,
    EXIT_REASON_TIME_EXIT,
)

if TYPE_CHECKING:
    from backtest.data.pit_access import BoundedPITAccess
    from backtest.exits.entities import LegacyPosition, StopManagedPosition

# Base section 17: exit day treatment depends on the fill convention that
# closed the tranche, not on a single "was this a real execution" bit.
FILL_MODE_OPEN = "OPEN_FILL"                    # NEXT_SESSION_OPEN_AFTER_DETECTION -- invalidation, either family
FILL_MODE_INTRADAY = "INTRADAY_LEVEL_FILL"      # amendment sec 12 -- STOP_MANAGED's own stop/target
FILL_MODE_CLOSE = "CLOSE_FILL"                  # SCHEDULED_..._BAR_CLOSE -- TIME_EXIT/cap (legacy family)
FILL_MODE_CENSORED = "CENSORED_MARK_TO_MARKET"  # still open, marked at the stage's own final authorized close

_ALL_FILL_MODES = frozenset({FILL_MODE_OPEN, FILL_MODE_INTRADAY, FILL_MODE_CLOSE, FILL_MODE_CENSORED})
# OPEN and INTRADAY are mechanically identical (exclude high/low, use only
# the day's open) -- kept as separate named constants because they are
# contractually distinct cases (base sec 17 vs amendment sec 12), even
# though the resulting computation does not need to tell them apart.
_EXCLUDE_HIGH_LOW_MODES = frozenset({FILL_MODE_OPEN, FILL_MODE_INTRADAY})

COVERAGE_FULL = "FULL"
COVERAGE_PARTIAL_EXIT_DAY_EXCLUDED = "PARTIAL_EXIT_DAY_EXCLUDED"
# Distinct from the above: this is a genuine DATA gap (a session the
# calendar expected has no bar at all, or a recorded value is not finite)
# -- never conflated with the routine, contractually-required exclusion
# of an open/intraday exit day's own high/low. Takes priority when both
# would otherwise apply, since it reflects an actual problem with the
# data rather than an expected, by-design omission.
COVERAGE_MISSING_SESSION_DATA = "MISSING_SESSION_DATA"


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
    coverage: str  # COVERAGE_FULL | COVERAGE_PARTIAL_EXIT_DAY_EXCLUDED | COVERAGE_MISSING_SESSION_DATA


def _direction_sign(direction: str) -> float:
    if direction == "LONG":
        return 1.0
    if direction == "SHORT":
        return -1.0
    raise ValueError(f"direction must be 'LONG' or 'SHORT', got {direction!r}")


def _is_finite(value: Optional[float]) -> bool:
    return value is not None and math.isfinite(value)


def _is_finite_positive(value: Optional[float]) -> bool:
    return _is_finite(value) and value > 0


def compute_tranche_mae_mfe(
    direction: str, entry_fill: float, bars: Sequence[DailyRange], exit_date: str, exit_fill: float,
    fill_mode: str, expected_session_dates: Sequence[str],
) -> TrancheMaeMfe:
    """`bars` covers whatever this tranche's own holding window's `as_of`
    query actually returned; `expected_session_dates` is the trading
    calendar's own authorized session sequence for that SAME window
    (`entry_date` through `exit_date`, inclusive) -- the two are cross-
    referenced explicitly so a session the calendar expected but `bars`
    has nothing for is never silently treated as if it simply didn't
    exist (defect #1: a whole missing session must downgrade coverage,
    not vanish unnoticed). `exit_date` must be one of
    `expected_session_dates` -- a real exit always happens ON an
    authorized session.

    `fill_mode` (defect #2) picks the exit day's own treatment:
    - `FILL_MODE_OPEN`/`FILL_MODE_INTRADAY`: the exit day's high/low are
      excluded (their ordering against the fill is unknowable from daily
      OHLC alone) -- only that day's own open, if present, and the
      actual `exit_fill` are usable.
    - `FILL_MODE_CLOSE`/`FILL_MODE_CENSORED`: the exit/mark day is
      treated like any OTHER day in the window -- the position held
      through its own full range (a scheduled close fill, or simply
      still open), so its high/low ARE genuine, fully-observable inputs.

    Every OTHER day in the window (including the entry day, always --
    base section 17: "entry-day full range for open entries") uses its
    own full high/low unconditionally.

    Non-finite/missing values (defect #1): any expected session absent
    from `bars` entirely, or a high/low that is not finite, downgrades
    coverage to `COVERAGE_MISSING_SESSION_DATA` -- checked independently
    of, and reported with priority over, the routine `PARTIAL_EXIT_DAY_
    EXCLUDED` label for an open/intraday exit day's own by-design
    exclusion. `entry_fill`/`exit_fill` themselves must be finite and
    strictly positive -- there is nothing meaningful to compute otherwise.

    The excursion AT ENTRY is always KNOWN -- by definition, price ==
    entry_fill at that moment, so its excursion is exactly 0.0 -- and is
    included UNCONDITIONALLY, regardless of `bars` (GPT review round 3,
    finding #4): without it, an empty-bars tranche with a favorable exit
    (e.g. entry 100, exit 110, no bars) would wrongly report MAE == MFE
    == +10% instead of the correct MAE=0%/MFE=+10%."""
    if fill_mode not in _ALL_FILL_MODES:
        raise ValueError(f"fill_mode must be one of {sorted(_ALL_FILL_MODES)}, got {fill_mode!r}")
    if not _is_finite_positive(entry_fill) or not _is_finite_positive(exit_fill):
        raise ValueError(
            f"entry_fill/exit_fill must be finite and strictly positive, got entry_fill={entry_fill!r} "
            f"exit_fill={exit_fill!r}"
        )
    if exit_date not in expected_session_dates:
        raise ValueError(f"exit_date {exit_date!r} must be one of expected_session_dates")

    d = _direction_sign(direction)
    excursions: list[float] = [0.0]
    bars_by_date = {b.date: b for b in bars}
    exclude_high_low_on_exit_day = fill_mode in _EXCLUDE_HIGH_LOW_MODES
    saw_missing_data = False

    for session_date in expected_session_dates:
        bar = bars_by_date.get(session_date)
        if bar is None:
            saw_missing_data = True
            continue
        if session_date == exit_date and exclude_high_low_on_exit_day:
            if _is_finite(bar.open):
                excursions.append(d * (bar.open - entry_fill) / entry_fill)
            else:
                saw_missing_data = True
            continue
        high_ok, low_ok = _is_finite(bar.high), _is_finite(bar.low)
        if not high_ok or not low_ok:
            saw_missing_data = True
        if high_ok:
            excursions.append(d * (bar.high - entry_fill) / entry_fill)
        if low_ok:
            excursions.append(d * (bar.low - entry_fill) / entry_fill)

    excursions.append(d * (exit_fill - entry_fill) / entry_fill)

    if saw_missing_data:
        coverage = COVERAGE_MISSING_SESSION_DATA
    elif exclude_high_low_on_exit_day:
        coverage = COVERAGE_PARTIAL_EXIT_DAY_EXCLUDED
    else:
        coverage = COVERAGE_FULL

    return TrancheMaeMfe(mae=min(excursions), mfe=max(excursions), coverage=coverage)


@dataclass(frozen=True)
class PositionMaeMfe:
    """One tranche's MAE/MFE, unambiguously associated to the position and
    tranche it belongs to -- section 12's own "per tranche, never one
    combined position number" requirement, as a standalone reporting
    record rather than a field on `StopManagedPosition`/`LegacyPosition`
    themselves (neither is modified). `entry_date` (defect #4) makes the
    identity genuinely unique: `(security_id, strategy_variant_id,
    tranche_kind)` alone collides when the same variant re-trades the
    same security within one stage (e.g. a TIME_EXIT(1) reopening
    immediately after its own same-day exit)."""
    security_id: str
    strategy_variant_id: str
    entry_date: str
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


def _expected_dates_in_window(session_dates: Sequence[str], start_date: str, end_date: str) -> tuple[str, ...]:
    return tuple(d for d in session_dates if start_date <= d <= end_date)


_STOP_MANAGED_FILL_MODE_BY_REASON = {
    EXIT_REASON_TARGET: FILL_MODE_INTRADAY,
    EXIT_REASON_STOP: FILL_MODE_INTRADAY,
    EXIT_REASON_INVALIDATION: FILL_MODE_OPEN,
}
_LEGACY_FILL_MODE_BY_REASON = {
    EXIT_REASON_TIME_EXIT: FILL_MODE_CLOSE,
    EXIT_REASON_MAX_HOLDING_BARS_FORCED_EXIT: FILL_MODE_CLOSE,
    EXIT_REASON_SIGNAL_INVALIDATION: FILL_MODE_OPEN,
}


def evaluate_stop_managed_position_mae_mfe(
    pit: "BoundedPITAccess", position: "StopManagedPosition", session_dates: Sequence[str],
    final_mark_date: str, mark_final: Optional[float],
) -> tuple[PositionMaeMfe, ...]:
    """Amendment section 12, wired against a real `run_stage()` result.
    Returns a SEPARATE record per tranche that actually exists on this
    position (0, 1, or 2 records) -- never merged into one "position"
    number. `position` itself is never modified.

    `session_dates` is the stage's own full, calendar-authorized session
    sequence (the same one `SessionEngine` was constructed with) --
    needed to detect a whole missing session inside a tranche's own
    window (defect #1), never to be confused with `bars`, which is
    whatever the `as_of` price query actually returned.

    Defect #3: an `EXIT_FAILED` position produces NO records at all,
    checked FIRST, before any tranche/mark logic -- `final_closes` is
    keyed by security, not by position, so a failed position sharing a
    security with a genuinely censored one must never borrow that mark
    and be reported as an ordinary censored remainder. This mirrors
    `taxonomy.classify_position()`'s own EXIT_FAILED-poisons-the-whole-
    position precedent (a realized partial tranche is not reported
    either, exactly as `evaluate_stage_results()` already reports no
    return at all for such a position).

    Price basis coherence: each tranche's own bars are queried `as_of`
    THAT tranche's own resolution date and paired with the entry price
    reference frozen (or current) on that SAME basis -- `Tranche.
    entry_fill_price_reference` for a closed tranche (frozen exactly when
    IT closed, section 6), `position.entry_fill_price` (continuously
    reconciled) for a still-open remainder queried as of the stage's own
    final mark date. Mixing a frozen reference from one as-of basis with
    bars queried on a DIFFERENT one would silently reintroduce the exact
    split-ratio error `entry_fill_price_reference` exists to prevent
    (GPT review round 2, finding #5)."""
    if position.exit_failed:
        return ()

    records: list[PositionMaeMfe] = []

    if position.partial_tranche is not None:
        t = position.partial_tranche
        expected = _expected_dates_in_window(session_dates, position.entry_date, t.exit_date)
        bars = _window_bars(pit, position.security_id, t.exit_date, position.entry_date, t.exit_date)
        fill_mode = _STOP_MANAGED_FILL_MODE_BY_REASON[t.exit_reason]
        result = compute_tranche_mae_mfe(
            position.direction, t.entry_fill_price_reference, bars, t.exit_date, t.exit_fill_price,
            fill_mode, expected,
        )
        records.append(PositionMaeMfe(position.security_id, position.strategy_variant_id, position.entry_date, t.kind, result))

    if position.closed and position.close_tranche is not None:
        t = position.close_tranche
        expected = _expected_dates_in_window(session_dates, position.entry_date, t.exit_date)
        bars = _window_bars(pit, position.security_id, t.exit_date, position.entry_date, t.exit_date)
        fill_mode = _STOP_MANAGED_FILL_MODE_BY_REASON[t.exit_reason]
        result = compute_tranche_mae_mfe(
            position.direction, t.entry_fill_price_reference, bars, t.exit_date, t.exit_fill_price,
            fill_mode, expected,
        )
        records.append(PositionMaeMfe(position.security_id, position.strategy_variant_id, position.entry_date, t.kind, result))
    elif not position.closed and mark_final is not None:
        expected = _expected_dates_in_window(session_dates, position.entry_date, final_mark_date)
        bars = _window_bars(pit, position.security_id, final_mark_date, position.entry_date, final_mark_date)
        result = compute_tranche_mae_mfe(
            position.direction, position.entry_fill_price, bars, final_mark_date, mark_final,
            FILL_MODE_CENSORED, expected,
        )
        records.append(PositionMaeMfe(position.security_id, position.strategy_variant_id, position.entry_date, "REMAINDER", result))

    return tuple(records)


def evaluate_legacy_position_mae_mfe(
    pit: "BoundedPITAccess", position: "LegacyPosition", session_dates: Sequence[str],
    final_mark_date: str, mark_final: Optional[float],
) -> tuple[PositionMaeMfe, ...]:
    """The `LegacyPosition` (TIME_EXIT/SIGNAL_INVALIDATION) counterpart of
    `evaluate_stop_managed_position_mae_mfe()` -- narrower, since neither
    older family ever has a partial-profit tranche (module docstring of
    `backtest.exits.legacy`): always exactly one tranche's worth of
    record, or none for a position with nothing to report (`EXIT_FAILED`,
    checked first, same precedent as the STOP_MANAGED counterpart above).

    `TIME_EXIT`/`MAX_HOLDING_BARS_FORCED_EXIT` are `FILL_MODE_CLOSE`
    (`SCHEDULED_..._BAR_CLOSE`, base section 9) -- the position held
    through that whole session up to and including the close that closed
    it, so base section 17 requires its FULL range included, never
    excluded as though an intraday ambiguity existed. `SIGNAL_
    INVALIDATION` is `FILL_MODE_OPEN` (`NEXT_SESSION_OPEN_AFTER_
    DETECTION`)."""
    if position.exit_failed:
        return ()

    if position.closed and position.close_tranche is not None:
        t = position.close_tranche
        expected = _expected_dates_in_window(session_dates, position.entry_date, t.exit_date)
        bars = _window_bars(pit, position.security_id, t.exit_date, position.entry_date, t.exit_date)
        fill_mode = _LEGACY_FILL_MODE_BY_REASON[t.exit_reason]
        result = compute_tranche_mae_mfe(
            position.direction, t.entry_fill_price_reference, bars, t.exit_date, t.exit_fill_price,
            fill_mode, expected,
        )
        return (PositionMaeMfe(position.security_id, position.strategy_variant_id, position.entry_date, t.kind, result),)
    if not position.closed and mark_final is not None:
        expected = _expected_dates_in_window(session_dates, position.entry_date, final_mark_date)
        bars = _window_bars(pit, position.security_id, final_mark_date, position.entry_date, final_mark_date)
        result = compute_tranche_mae_mfe(
            position.direction, position.entry_fill_price, bars, final_mark_date, mark_final,
            FILL_MODE_CENSORED, expected,
        )
        return (PositionMaeMfe(position.security_id, position.strategy_variant_id, position.entry_date, "REMAINDER", result),)
    return ()
