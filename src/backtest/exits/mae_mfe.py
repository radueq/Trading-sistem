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
fixed together (commit `3aae3ef`):

1. A whole missing session, or a non-finite OHLC value, inside a
   tranche's own window must never leave coverage reading FULL.
2. The open/intraday/close/censored fill conventions require genuinely
   different treatment of the resolution day's own high/low.
3. `EXIT_FAILED` must never be reported as an ordinary censored
   remainder.
4. `PositionMaeMfe` must carry a genuinely unique identity (`entry_date`).

Two follow-up corrections, both raised by Radu before independent
verification of that delta completed:

5. (commit `536bad7`) Labeling a genuine data gap
   `COVERAGE_MISSING_SESSION_DATA` was not enough on its own -- base
   section 17, verbatim, "Missing interior range makes excursion metrics
   unavailable even if endpoint return is measurable; report coverage
   separately." `mae`/`mfe` are `Optional[float]`, `None` whenever any
   required session/value inside the window is missing or non-finite --
   never a number computed from the incomplete remainder and merely
   tagged with a different coverage label. The routine, by-design
   exclusion of an open/intraday exit day's own high/low (`COVERAGE_
   PARTIAL_EXIT_DAY_EXCLUDED`) is NOT "missing data" in this sense --
   section 17 itself specifies exactly which fields to use there, so
   `mae`/`mfe` stay real numbers for that case.
6. The reference price MAE/MFE excursions are computed against was
   `Tranche.entry_fill_price_reference`/`StopManagedPosition.
   entry_fill_price` -- `F_e`, the entry fill WITH slippage baked in
   (`costs.apply_entry_slippage()` runs before either field is ever
   set). Base section 17's own formula is explicit: "MAE=min(0,min_price/
   P_e-1)... cost-free price excursions" -- `P_e`, the RAW, pre-slippage
   common-basis reference (base section 13), never `F_e`. `P_e` is now
   derived directly from the entry day's OWN bar inside the tranche's
   own `bars` window (already queried on the tranche's own as-of basis,
   so split-coherence is automatic -- no separately-tracked reference
   needed at all for this purpose). `F_e`/`entry_fill_price_reference`
   remain exactly as they were for `costs.py`'s own NET RETURN
   calculation, which stays entirely separate -- MAE/MFE and net return
   answer different questions (a hypothetical cost-free excursion vs. an
   actual realized, cost-bearing return) and must never share a
   reference price."""
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
    # `None` (unavailable) exactly when coverage == COVERAGE_MISSING_SESSION_DATA
    # -- base section 17: missing interior range (including a missing/
    # non-finite entry-day open, since that IS the P_e reference every
    # other excursion is computed against) makes the excursion metrics
    # unavailable, never a number computed from the incomplete remainder.
    # Real signed floats otherwise (adverse = negative, favorable =
    # positive, relative to P_e -- the raw, pre-slippage entry reference).
    mae: Optional[float]
    mfe: Optional[float]
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
    direction: str, bars: Sequence[DailyRange], entry_date: str, exit_date: str, exit_fill: float,
    fill_mode: str, expected_session_dates: Sequence[str],
) -> TrancheMaeMfe:
    """`bars` covers whatever this tranche's own holding window's `as_of`
    query actually returned (starting at `entry_date`); `expected_
    session_dates` is the trading calendar's own authorized session
    sequence for that SAME window -- the two are cross-referenced
    explicitly so a session the calendar expected but `bars` has nothing
    for is never silently treated as if it simply didn't exist. Both
    `entry_date` and `exit_date` must be one of `expected_session_dates`
    -- a real entry/exit always happens ON an authorized session.

    `P_e` (base section 13's "positive common-basis reference entry" --
    the RAW price before slippage) is derived from the entry day's OWN
    bar inside `bars`, never passed in separately: `bars` is already
    queried on the tranche's own as-of basis, so deriving `P_e` from it
    directly guarantees split coherence for free, and structurally
    prevents ever passing a slipped `F_e` by mistake (the exact defect
    this fixes -- see module docstring, point 6). A missing or non-finite
    entry-day open makes the WHOLE result unavailable, exactly like any
    other missing/non-finite value in the window (below): every other
    excursion is computed relative to `P_e`, so an unknown `P_e` poisons
    all of them, not just the entry day's own contribution.

    `fill_mode` picks the exit day's own treatment:
    - `FILL_MODE_OPEN`/`FILL_MODE_INTRADAY`: the exit day's high/low are
      excluded (their ordering against the fill is unknowable from daily
      OHLC alone) -- only that day's own open, if present, and the
      actual `exit_fill` (the RAW trigger/fill level -- `Tranche.
      exit_fill_price`'s own value, never re-slipped here; slippage is
      applied separately, downstream, only for the net-return
      calculation in `costs.py`) are usable.
    - `FILL_MODE_CLOSE`/`FILL_MODE_CENSORED`: the exit/mark day is
      treated like any OTHER day in the window -- the position held
      through its own full range (a scheduled close fill, or simply
      still open), so its high/low ARE genuine, fully-observable inputs.

    Every OTHER day in the window (including the entry day itself, when
    it differs from `exit_date` -- base section 17: "entry-day full
    range for open entries") uses its own full high/low unconditionally.

    Missing/non-finite data: any expected session absent from `bars`
    entirely, a high/low/open that is not finite, or `exit_fill` itself
    not finite/strictly positive, makes `mae`/`mfe` both `None`
    (`COVERAGE_MISSING_SESSION_DATA`) -- base section 17: "Missing
    interior range makes excursion metrics unavailable even if endpoint
    return is measurable." This is never conflated with the routine,
    by-design exclusion of an open/intraday exit day's own high/low
    (`COVERAGE_PARTIAL_EXIT_DAY_EXCLUDED`), which still returns real
    numbers -- section 17 itself specifies exactly which fields to use
    there."""
    if fill_mode not in _ALL_FILL_MODES:
        raise ValueError(f"fill_mode must be one of {sorted(_ALL_FILL_MODES)}, got {fill_mode!r}")
    if not _is_finite_positive(exit_fill):
        raise ValueError(f"exit_fill must be finite and strictly positive, got exit_fill={exit_fill!r}")
    if entry_date not in expected_session_dates:
        raise ValueError(f"entry_date {entry_date!r} must be one of expected_session_dates")
    if exit_date not in expected_session_dates:
        raise ValueError(f"exit_date {exit_date!r} must be one of expected_session_dates")

    bars_by_date = {b.date: b for b in bars}
    entry_bar = bars_by_date.get(entry_date)
    if entry_bar is None or not _is_finite_positive(entry_bar.open):
        # P_e itself is unknown -- every excursion depends on it, so the
        # whole tranche's MAE/MFE is unavailable, not just the entry day.
        return TrancheMaeMfe(mae=None, mfe=None, coverage=COVERAGE_MISSING_SESSION_DATA)
    entry_fill = entry_bar.open  # P_e

    d = _direction_sign(direction)
    excursions: list[float] = [0.0]  # the entry moment itself: always a known, zero excursion, relative to P_e.
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
        # Base section 17, verbatim: "Missing interior range makes
        # excursion metrics unavailable even if endpoint return is
        # measurable; report coverage separately." `excursions` is
        # discarded here, not reduced to min/max -- a partial view can
        # never certify the TRUE excursion, since the unobserved gap
        # could hide something more extreme than anything actually seen.
        return TrancheMaeMfe(mae=None, mfe=None, coverage=COVERAGE_MISSING_SESSION_DATA)

    coverage = COVERAGE_PARTIAL_EXIT_DAY_EXCLUDED if exclude_high_low_on_exit_day else COVERAGE_FULL
    return TrancheMaeMfe(mae=min(excursions), mfe=max(excursions), coverage=coverage)


@dataclass(frozen=True)
class PositionMaeMfe:
    """One tranche's MAE/MFE, unambiguously associated to the position and
    tranche it belongs to -- section 12's own "per tranche, never one
    combined position number" requirement, as a standalone reporting
    record rather than a field on `StopManagedPosition`/`LegacyPosition`
    themselves (neither is modified). `entry_date` makes the identity
    genuinely unique: `(security_id, strategy_variant_id, tranche_kind)`
    alone collides when the same variant re-trades the same security
    within one stage (e.g. a TIME_EXIT(1) reopening immediately after its
    own same-day exit)."""
    security_id: str
    strategy_variant_id: str
    entry_date: str
    tranche_kind: str  # "PARTIAL_PROFIT" | "REMAINDER"
    mae_mfe: TrancheMaeMfe


def _window_bars(pit: "BoundedPITAccess", security_id: str, as_of: str, start_date: str, end_date: str) -> list[DailyRange]:
    """Bars for `[start_date, end_date]`, queried `as_of` the SAME date
    the tranche itself resolved on (its own close date, or the stage's
    final mark date for a still-open remainder) -- every bar returned,
    INCLUDING the entry day's own (start_date is always `position.
    entry_date`), is therefore split-adjusted on that ONE basis. `P_e` is
    derived from this same list inside `compute_tranche_mae_mfe()` --
    coherence is automatic, never a separately-tracked reference that
    could drift onto a different basis."""
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
    window, never to be confused with `bars`, which is whatever the
    `as_of` price query actually returned.

    An `EXIT_FAILED` position produces NO records at all, checked FIRST,
    before any tranche/mark logic -- `final_closes` is keyed by security,
    not by position, so a failed position sharing a security with a
    genuinely censored one must never borrow that mark and be reported as
    an ordinary censored remainder. This mirrors `taxonomy.
    classify_position()`'s own EXIT_FAILED-poisons-the-whole-position
    precedent (a realized partial tranche is not reported either, exactly
    as `evaluate_stage_results()` already reports no return at all for
    such a position).

    `Tranche.exit_fill_price` is passed straight through as `exit_fill`
    -- it is already the RAW trigger/fill level (`session.py` constructs
    it from the stop/target/invalidation LEVEL itself, before
    `costs.apply_exit_slippage()` ever runs), so it never needs
    adjustment here. `entry_fill_price_reference`/`position.
    entry_fill_price` are NOT passed to `compute_tranche_mae_mfe()` at
    all -- `P_e` is derived internally from `bars`' own entry-day open
    (see that function's docstring, point 6 of the module docstring).
    Those two fields remain exactly what `costs.py` uses for the NET
    RETURN calculation, entirely separate from MAE/MFE."""
    if position.exit_failed:
        return ()

    records: list[PositionMaeMfe] = []

    if position.partial_tranche is not None:
        t = position.partial_tranche
        expected = _expected_dates_in_window(session_dates, position.entry_date, t.exit_date)
        bars = _window_bars(pit, position.security_id, t.exit_date, position.entry_date, t.exit_date)
        fill_mode = _STOP_MANAGED_FILL_MODE_BY_REASON[t.exit_reason]
        result = compute_tranche_mae_mfe(
            position.direction, bars, position.entry_date, t.exit_date, t.exit_fill_price,
            fill_mode, expected,
        )
        records.append(PositionMaeMfe(position.security_id, position.strategy_variant_id, position.entry_date, t.kind, result))

    if position.closed and position.close_tranche is not None:
        t = position.close_tranche
        expected = _expected_dates_in_window(session_dates, position.entry_date, t.exit_date)
        bars = _window_bars(pit, position.security_id, t.exit_date, position.entry_date, t.exit_date)
        fill_mode = _STOP_MANAGED_FILL_MODE_BY_REASON[t.exit_reason]
        result = compute_tranche_mae_mfe(
            position.direction, bars, position.entry_date, t.exit_date, t.exit_fill_price,
            fill_mode, expected,
        )
        records.append(PositionMaeMfe(position.security_id, position.strategy_variant_id, position.entry_date, t.kind, result))
    elif not position.closed and mark_final is not None:
        expected = _expected_dates_in_window(session_dates, position.entry_date, final_mark_date)
        bars = _window_bars(pit, position.security_id, final_mark_date, position.entry_date, final_mark_date)
        result = compute_tranche_mae_mfe(
            position.direction, bars, position.entry_date, final_mark_date, mark_final,
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
    DETECTION`). As with the STOP_MANAGED counterpart, `P_e` is derived
    from `bars`' own entry-day open, never from `entry_fill_price_
    reference`/`position.entry_fill_price` (both `F_e`, reserved for
    `costs.py`'s own net-return calculation)."""
    if position.exit_failed:
        return ()

    if position.closed and position.close_tranche is not None:
        t = position.close_tranche
        expected = _expected_dates_in_window(session_dates, position.entry_date, t.exit_date)
        bars = _window_bars(pit, position.security_id, t.exit_date, position.entry_date, t.exit_date)
        fill_mode = _LEGACY_FILL_MODE_BY_REASON[t.exit_reason]
        result = compute_tranche_mae_mfe(
            position.direction, bars, position.entry_date, t.exit_date, t.exit_fill_price,
            fill_mode, expected,
        )
        return (PositionMaeMfe(position.security_id, position.strategy_variant_id, position.entry_date, t.kind, result),)
    if not position.closed and mark_final is not None:
        expected = _expected_dates_in_window(session_dates, position.entry_date, final_mark_date)
        bars = _window_bars(pit, position.security_id, final_mark_date, position.entry_date, final_mark_date)
        result = compute_tranche_mae_mfe(
            position.direction, bars, position.entry_date, final_mark_date, mark_final,
            FILL_MODE_CENSORED, expected,
        )
        return (PositionMaeMfe(position.security_id, position.strategy_variant_id, position.entry_date, "REMAINDER", result),)
    return ()
