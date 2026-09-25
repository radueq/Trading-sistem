"""Spec #003 v1.1 SS18-19 -- benchmark-relative outcome.

AR_{i,t,h} = R_{i,t,h} - R_benchmark,t,h. Benchmark alignment is by
ACTUAL entry/exit DATE, never DataFrame position (SS19) -- the
benchmark's own bar series can have different dates present than a
given security's (halts, gaps). No benchmark bar at the needed date ->
MISSING_BENCHMARK, no silent fallback to a nearby date.
"""
from __future__ import annotations

import bisect
from dataclasses import replace
from typing import Optional

from evaluation.models.entities import ForwardOutcome, OutcomeStatus


def _exact_date_index(dates: list[str], date: Optional[str]) -> Optional[int]:
    if date is None:
        return None
    i = bisect.bisect_left(dates, date)
    if i < len(dates) and dates[i] == date:
        return i
    return None


def attach_benchmark_return(outcome: ForwardOutcome, benchmark_bars) -> ForwardOutcome:
    """benchmark_bars: one bar list per evaluation run (SS62 -- a single
    PIT fetch, reused across every security/observation), aligned here by
    date to THIS outcome's own entry/exit dates. A non-VALID outcome is
    returned unchanged -- its status/reason is already final."""
    if outcome.outcome_status != OutcomeStatus.VALID.value:
        return outcome

    dates = [b.date for b in benchmark_bars]
    entry_idx = _exact_date_index(dates, outcome.observation_as_of)
    exit_idx = _exact_date_index(dates, outcome.exit_as_of)
    if entry_idx is None or exit_idx is None:
        return replace(outcome, outcome_status=OutcomeStatus.MISSING_BENCHMARK.value)

    entry_close = benchmark_bars[entry_idx].split_adjusted_close
    exit_close = benchmark_bars[exit_idx].split_adjusted_close
    if entry_close is None or exit_close is None:
        return replace(outcome, outcome_status=OutcomeStatus.MISSING_BENCHMARK.value)

    benchmark_return = exit_close / entry_close - 1.0
    relative_return = outcome.forward_return - benchmark_return
    return replace(outcome, benchmark_return=benchmark_return, relative_return=relative_return)
