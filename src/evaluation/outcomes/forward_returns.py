"""Spec #003 v1.1 SS15/SS17/SS57 -- primary (absolute) forward outcome.

R_{i,t,h} = P(t+h)/P(t) - 1, P = split_adjusted_close (Spec #001 PATCH
#001-C baseline `aa56bb5` -- corporate-action-consistent price AND
volume). A research measurement (close(t) -> close(t+h)), never claimed
to be an executable trade P&L (SS17) -- the Backtester (a future,
out-of-scope spec) introduces executable entry.

Horizon is BARS: entry/exit are POSITIONS in the security's own PIT bar
series, never calendar-date arithmetic (SS3-4) -- the same function
serves 1D today and 4H later without a rewrite, as long as the caller
supplies that timeframe's own bar series.

One PIT fetch per security (SS62): callers pass the FULL bar list
already retrieved via a single pit.access.get_price_series_as_of(conn,
sid, as_of=<data_as_of>) call, never a per-observation query.
"""
from __future__ import annotations

import bisect
from dataclasses import replace
from typing import Optional

from evaluation.models.entities import ForwardOutcome, OutcomeStatus

OUTCOME_ENGINE_VERSION = "v1.0.0"


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
) -> ForwardOutcome:
    """`bars` must already cover at least up to `development_end` (if set)
    or the caller's own data_as_of bound. This function NEVER reads a
    bar's price/volume beyond `development_end`: when the exit bar's
    DATE alone (not its price) shows it would fall after
    `development_end`, status is CROSSES_LOCKED_OOS and the price field
    is never touched (Spec #003 SS12/SS14 -- Locked OOS is never used,
    not even for this classification)."""

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

    dates = [b.date for b in bars]
    entry_idx = _exact_entry_index(dates, observation_as_of)
    if entry_idx is None:
        return _invalid(OutcomeStatus.INVALID_INPUT)

    entry_bar = bars[entry_idx]
    if entry_bar.split_adjusted_close is None:
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


def with_status(outcome: ForwardOutcome, status: OutcomeStatus) -> ForwardOutcome:
    return replace(outcome, outcome_status=status.value)
