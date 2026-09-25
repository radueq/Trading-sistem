"""Spec #003 v1.1 SS37 -- opportunity density (frequency of occurrence).

Descriptive only -- NEVER part of any significance calculation. Two
different things kept separate throughout this module (SS9): statistical
evidence (does an effect exist) and opportunity density (how often does
the signature occur). `session_dates` is the shared trading-session
calendar for the evaluation run (the benchmark's own bar dates within
Development) -- gaps are measured in session/bar POSITIONS, matching the
bar-based contract used everywhere else (SS3-4).
"""
from __future__ import annotations

import statistics as pystats

from evaluation.models.entities import OpportunityDensity


def compute_opportunity_density(representative_as_ofs: list[str], session_dates: list[str]) -> OpportunityDensity:
    n = len(representative_as_ofs)
    total_sessions = len(session_dates)
    if n == 0 or total_sessions == 0:
        return OpportunityDensity(
            episode_count=n, episodes_per_20_sessions=None, episodes_per_60_sessions=None,
            median_sessions_between_episodes=None,
        )

    per_20 = (n / total_sessions) * 20
    per_60 = (n / total_sessions) * 60

    if n < 2:
        return OpportunityDensity(
            episode_count=n, episodes_per_20_sessions=per_20, episodes_per_60_sessions=per_60,
            median_sessions_between_episodes=None,
        )

    index_by_date = {d: i for i, d in enumerate(session_dates)}
    positions = sorted(index_by_date[d] for d in representative_as_ofs if d in index_by_date)
    gaps = [b - a for a, b in zip(positions, positions[1:])]
    median_gap = pystats.median(gaps) if gaps else None
    return OpportunityDensity(
        episode_count=n, episodes_per_20_sessions=per_20, episodes_per_60_sessions=per_60,
        median_sessions_between_episodes=median_gap,
    )
