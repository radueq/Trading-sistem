"""Spec #003 v1.1 SS15/SS17/SS57 -- primary (absolute) forward outcome.

R_{i,t,h} = P(t+h)/P(t) - 1, P = split_adjusted_close (Spec #001 PATCH
#001-C baseline `aa56bb5` -- corporate-action-consistent price AND
volume). A research measurement (close(t) -> close(t+h)), never claimed
to be an executable trade P&L (SS17) -- the Backtester (a future,
out-of-scope spec) introduces executable entry.

Horizon is BARS. By default (no `calendar=` argument) entry/exit are
POSITIONS in the security's own PIT bar series, never calendar-date
arithmetic (SS3-4) -- the same function serves 1D today and 4H later
without a rewrite, as long as the caller supplies that timeframe's own
bar series. Joint remediation design 003+004 section 1.3 (decision
registry B1-B2, revision 5-6; authorized 2026-10-06, Stage 2) adds an
OPTIONAL calendar-aware resolution instead: see `compute_forward_
outcome()`'s own docstring.

One PIT fetch per security (SS62): callers pass the FULL bar list
already retrieved via a single pit.access.get_price_series_as_of(conn,
sid, as_of=<data_as_of>) call, never a per-observation query.
"""
from __future__ import annotations

import bisect
import math
from dataclasses import replace
from typing import Optional

from data_foundation.calendar.entities import TradingCalendar
from evaluation.models.entities import ForwardOutcome, OutcomeStatus

OUTCOME_ENGINE_VERSION = "v1.0.0"


def _is_finite_positive(price: float) -> bool:
    """Spec #003 S1 (GPT review finding, Top Finding 16) -- a price
    that is present (not `None`) but zero, negative, `NaN`, or infinite
    must never reach the division below as if it were a real price."""
    return math.isfinite(price) and price > 0


def _exact_entry_index(dates: list[str], as_of: str) -> Optional[int]:
    """The bar dated EXACTLY `as_of` -- required, not "the latest bar at
    or before" (GPT Review #003 Round 1, mandatory finding #6). An
    at-or-before entry could silently predate `as_of` (e.g. a security
    with no bar on the observation date, halt or gap), while
    `outcomes/benchmark.py`'s alignment requires an EXACT-date benchmark
    bar for that same `as_of` -- mixing the two would compare a security
    return measured from one date against a benchmark return measured
    from another. No bar at exactly `as_of` -> INVALID_INPUT, never a
    silently-shifted entry."""
    i = bisect.bisect_left(dates, as_of)
    return i if i < len(dates) and dates[i] == as_of else None


def compute_forward_outcome(
    security_id: str,
    bars,  # list[PITPriceBar], ordered ascending by date, already fetched once
    observation_as_of: str,
    timeframe: str,
    horizon_bars: int,
    development_end: Optional[str],
    config_version: str,
    *,
    calendar: Optional[TradingCalendar] = None,
    data_as_of: Optional[str] = None,
) -> ForwardOutcome:
    """`bars` must already cover at least up to `development_end` (if set)
    or the caller's own data_as_of bound. This function NEVER reads a
    bar's price/volume beyond `development_end`: when the exit bar's
    DATE alone (not its price) shows it would fall after
    `development_end`, status is CROSSES_LOCKED_OOS and the price field
    is never touched (Spec #003 SS12/SS14 -- Locked OOS is never used,
    not even for this classification).

    `calendar` is NEW, OPTIONAL (joint remediation design 003+004,
    section 1.3; decision registry B1-B2, revision 5-6; authorized
    2026-10-06, Stage 2). Omitted (`None`, the default): the ORIGINAL
    bar-position-based resolution below runs completely unchanged --
    every existing caller and test keeps today's exact behavior.
    Supplied: the target session is resolved from the CALENDAR's own
    `session_dates` (never inferred from bar positions), via the
    four-way check in that order -- calendar-insufficient, Locked-OOS,
    not-yet-reached, data-gap/valid -- so that no price is ever read
    for a session later than `effective_as_of = min(data_as_of,
    development_end)`. `data_as_of` is only meaningful together with
    `calendar`; omitted, `effective_as_of` falls back to
    `development_end` alone (no additional vantage-point bound)."""

    def _invalid(status: OutcomeStatus, dev_end: Optional[str] = development_end) -> ForwardOutcome:
        return ForwardOutcome(
            security_id=security_id, observation_as_of=observation_as_of, timeframe=timeframe,
            horizon_bars=horizon_bars, entry_reference_price=None, exit_reference_price=None,
            exit_as_of=None, forward_return=None, benchmark_return=None, relative_return=None,
            outcome_status=status.value, development_end=dev_end,
            outcome_engine_version=OUTCOME_ENGINE_VERSION, config_version=config_version,
        )

    if horizon_bars <= 0 or not bars:
        return _invalid(OutcomeStatus.INVALID_INPUT)

    if calendar is not None:
        return _compute_forward_outcome_calendar_aware(
            security_id=security_id, bars=bars, observation_as_of=observation_as_of, timeframe=timeframe,
            horizon_bars=horizon_bars, development_end=development_end, config_version=config_version,
            calendar=calendar, data_as_of=data_as_of, invalid=_invalid,
        )

    dates = [b.date for b in bars]
    entry_idx = _exact_entry_index(dates, observation_as_of)
    if entry_idx is None:
        return _invalid(OutcomeStatus.INVALID_INPUT)

    entry_bar = bars[entry_idx]
    if entry_bar.split_adjusted_close is None:
        return _invalid(OutcomeStatus.INVALID_INPUT)
    if not _is_finite_positive(entry_bar.split_adjusted_close):
        return _invalid(OutcomeStatus.INVALID_INPUT)

    exit_idx = entry_idx + horizon_bars
    if exit_idx >= len(bars):
        return _invalid(OutcomeStatus.INSUFFICIENT_FUTURE_DATA)

    exit_bar = bars[exit_idx]
    # Date-only inspection for the Locked-OOS wall -- the price/volume
    # fields of exit_bar are never read on this branch.
    if development_end is not None and exit_bar.date > development_end:
        return _invalid(OutcomeStatus.CROSSES_LOCKED_OOS)

    if exit_bar.split_adjusted_close is None:
        return _invalid(OutcomeStatus.INSUFFICIENT_FUTURE_DATA)
    if not _is_finite_positive(exit_bar.split_adjusted_close):
        return _invalid(OutcomeStatus.INVALID_INPUT)

    forward_return = exit_bar.split_adjusted_close / entry_bar.split_adjusted_close - 1.0

    return ForwardOutcome(
        security_id=security_id, observation_as_of=observation_as_of, timeframe=timeframe,
        horizon_bars=horizon_bars,
        entry_reference_price=entry_bar.split_adjusted_close,
        exit_reference_price=exit_bar.split_adjusted_close,
        exit_as_of=exit_bar.date,
        forward_return=forward_return, benchmark_return=None, relative_return=None,
        outcome_status=OutcomeStatus.VALID.value, development_end=development_end,
        outcome_engine_version=OUTCOME_ENGINE_VERSION, config_version=config_version,
    )


def _compute_forward_outcome_calendar_aware(
    *, security_id: str, bars, observation_as_of: str, timeframe: str, horizon_bars: int,
    development_end: Optional[str], config_version: str, calendar: TradingCalendar,
    data_as_of: Optional[str], invalid,
) -> ForwardOutcome:
    """Joint remediation design 003+004, section 1.3's own four-way
    check, in its own stated order. Steps 1-3 are pure calendar-date
    arithmetic -- no price is read until step 4, and step 4 only reads a
    bar at a date already proven `<= effective_as_of`."""
    session_dates = calendar.session_dates

    # Step 1 -- calendar insufficient to determine the target: T_entry
    # itself not in the calendar, or the resolved target falls past the
    # end of the calendar's own session list. No price read yet.
    entry_index = _exact_entry_index(session_dates, observation_as_of)
    if entry_index is None:
        return invalid(OutcomeStatus.INVALID_INPUT)

    target_index = entry_index + horizon_bars
    if target_index >= len(session_dates):
        return invalid(OutcomeStatus.INVALID_INPUT)

    target_date = session_dates[target_index]

    # Step 2 -- Locked-OOS wall, from the calendar's own date alone.
    if development_end is not None and target_date > development_end:
        return invalid(OutcomeStatus.CROSSES_LOCKED_OOS)

    # Step 3 -- not-yet-reached, from the caller's own vantage point.
    if data_as_of is None:
        effective_as_of = development_end
    elif development_end is None:
        effective_as_of = data_as_of
    else:
        effective_as_of = min(data_as_of, development_end)
    if effective_as_of is not None and target_date > effective_as_of:
        return invalid(OutcomeStatus.INSUFFICIENT_FUTURE_DATA)

    # Step 4 -- NOW the security's own bars are read, bounded to dates
    # already proven <= effective_as_of.
    dates = [b.date for b in bars]
    entry_bar_idx = _exact_entry_index(dates, observation_as_of)
    if entry_bar_idx is None:
        return invalid(OutcomeStatus.INVALID_INPUT)
    entry_bar = bars[entry_bar_idx]
    if entry_bar.split_adjusted_close is None:
        return invalid(OutcomeStatus.INVALID_INPUT)
    if not _is_finite_positive(entry_bar.split_adjusted_close):
        return invalid(OutcomeStatus.INVALID_INPUT)

    target_bar_idx = _exact_entry_index(dates, target_date)
    if target_bar_idx is None:
        return invalid(OutcomeStatus.DATA_GAP)  # 4a -- no bar at T_target
    target_bar = bars[target_bar_idx]
    if target_bar.split_adjusted_close is None:
        return invalid(OutcomeStatus.DATA_GAP)  # 4b -- bar present, price None
    if not _is_finite_positive(target_bar.split_adjusted_close):
        return invalid(OutcomeStatus.INVALID_INPUT)

    forward_return = target_bar.split_adjusted_close / entry_bar.split_adjusted_close - 1.0

    return ForwardOutcome(
        security_id=security_id, observation_as_of=observation_as_of, timeframe=timeframe,
        horizon_bars=horizon_bars,
        entry_reference_price=entry_bar.split_adjusted_close,
        exit_reference_price=target_bar.split_adjusted_close,
        exit_as_of=target_bar.date,
        forward_return=forward_return, benchmark_return=None, relative_return=None,
        outcome_status=OutcomeStatus.VALID.value, development_end=development_end,
        outcome_engine_version=OUTCOME_ENGINE_VERSION, config_version=config_version,
    )


def with_status(outcome: ForwardOutcome, status: OutcomeStatus) -> ForwardOutcome:
    return replace(outcome, outcome_status=status.value)
