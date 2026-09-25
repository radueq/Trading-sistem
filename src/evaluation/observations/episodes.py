"""Spec #003 v1.1 SS30-31 -- Episode Engine.

Consecutive DiscoveryObservation dates for the same (security_id,
signature_id) collapse into ONE Episode -- the statistical unit for the
default EPISODE_DEDUPLICATED view (SS31); RAW_OBSERVATIONS (every
matching date, undeduplicated) is reported separately (SS31) but is
never the default statistical view.

`max_gap_bars` (config `episode.max_gap_bars`, default 1) is the number
of INTERVENING non-matching bars tolerated before starting a new
episode -- a documented Level 1 convention, not the only valid reading:
two matches exactly 1 bar apart (immediately consecutive, e.g. Monday
then Tuesday) have 0 bars between them and always join the same episode
regardless of this setting; `max_gap_bars: 1` additionally tolerates
exactly one skipped bar (e.g. Monday then Wednesday, Tuesday didn't
match) before splitting into a new episode. Gap is measured in the
security's own bar-INDEX positions (never calendar days), matching the
bar-based contract used throughout this module (SS3-4).

`representative` (default FIRST) is the only value Level 1 implements --
the episode's FIRST matching date is the one whose ForwardOutcome
episode-level statistics use (SS30).
"""
from __future__ import annotations

import bisect

from evaluation.models.entities import Episode

SUPPORTED_REPRESENTATIVES = ("FIRST",)


def _date_index(bar_dates: list[str]) -> dict:
    return {d: i for i, d in enumerate(bar_dates)}


def build_episodes(
    security_id: str,
    signature_id: str,
    matched_as_ofs: list[str],
    bar_dates: list[str],
    max_gap_bars: int,
    representative: str = "FIRST",
) -> list[Episode]:
    """`matched_as_ofs`: dates this (security, signature) matched,
    already sorted ascending. `bar_dates`: THIS security's own bar-date
    series (ascending), used only to measure the bar-index gap between
    consecutive matches -- never for the outcome computation itself."""
    if representative not in SUPPORTED_REPRESENTATIVES:
        raise ValueError(f"unsupported episode.representative: {representative!r}")
    if not matched_as_ofs:
        return []

    idx_by_date = _date_index(bar_dates)
    episodes: list[Episode] = []
    current: list[str] = [matched_as_ofs[0]]

    for prev_date, date in zip(matched_as_ofs, matched_as_ofs[1:]):
        prev_idx = idx_by_date.get(prev_date, bisect.bisect_right(bar_dates, prev_date) - 1)
        idx = idx_by_date.get(date, bisect.bisect_right(bar_dates, date) - 1)
        gap = idx - prev_idx - 1
        if gap <= max_gap_bars:
            current.append(date)
        else:
            episodes.append(_finish(security_id, signature_id, current))
            current = [date]
    episodes.append(_finish(security_id, signature_id, current))
    return episodes


def _finish(security_id: str, signature_id: str, members: list[str]) -> Episode:
    return Episode(
        episode_id=f"{security_id}:{signature_id}:{members[0]}",
        security_id=security_id, signature_id=signature_id,
        member_as_ofs=tuple(members), representative_as_of=members[0],
    )
