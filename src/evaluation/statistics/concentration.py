"""Spec #003 v1.1 SS41 -- security concentration diagnostic.

Example the spec itself gives: N episodes = 80 but 52 from the same
security -- must be visible, not buried. Purely descriptive; feeds no
significance calculation."""
from __future__ import annotations

from collections import Counter

from evaluation.models.entities import ConcentrationStats


def compute_concentration(security_ids: list[str]) -> ConcentrationStats:
    n = len(security_ids)
    if n == 0:
        return ConcentrationStats(unique_security_count=0, largest_security_share_of_episodes=None)
    counts = Counter(security_ids)
    largest = max(counts.values())
    return ConcentrationStats(unique_security_count=len(counts), largest_security_share_of_episodes=largest / n)
