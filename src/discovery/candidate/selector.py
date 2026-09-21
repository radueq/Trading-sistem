"""Candidate Budget selection -- deterministic and outcome-blind (Spec
#002 SS21/SS22/SS23).

Allowed reduction signals: feature extremeness, transition magnitude,
persistence, statistical unusualness, multi-lane activation,
deterministic budget, diversity sampling. Forbidden: anything derived
from historical/forward profitability, win rate, expectancy, or
backtest ranking -- none of those concepts appear anywhere below.

Ties are broken by security_id ascending (Spec #002 SS22's explicit
requirement), so selection is fully deterministic for identical input.
"""
from __future__ import annotations

from discovery.models.entities import DiscoveryCandidate


def _sort_key(c: DiscoveryCandidate) -> tuple:
    return (
        -c.descriptive_metrics.extremeness,
        -len(c.active_lanes),
        -c.descriptive_metrics.persistence,
        c.security_id,
    )


def select_candidates(candidates: list[DiscoveryCandidate], discovery_config: dict) -> list[DiscoveryCandidate]:
    budget_cfg = discovery_config["candidate_budget"]
    ranked = sorted(candidates, key=_sort_key)

    if not budget_cfg.get("enabled", True):
        return ranked

    max_candidates = budget_cfg["max_candidates"]
    if len(ranked) <= max_candidates:
        return ranked

    diversity_cfg = discovery_config.get("diversity", {})
    if not diversity_cfg.get("enabled", False):
        return ranked[:max_candidates]

    return _select_with_diversity(ranked, max_candidates)


def _select_with_diversity(ranked: list[DiscoveryCandidate], max_candidates: int) -> list[DiscoveryCandidate]:
    """Round-robin over buckets keyed by each candidate's sorted
    active_lanes tuple, preserving each bucket's internal deterministic
    (already-ranked) order, so the budget doesn't collapse into one
    repeated phenomenon when alternatives satisfying the policy exist."""
    buckets: dict[tuple, list[DiscoveryCandidate]] = {}
    for c in ranked:
        key = tuple(sorted(c.active_lanes))
        buckets.setdefault(key, []).append(c)

    bucket_order = sorted(buckets.keys())
    selected: list[DiscoveryCandidate] = []
    idx = 0
    while len(selected) < max_candidates:
        made_progress = False
        for key in bucket_order:
            if idx < len(buckets[key]):
                selected.append(buckets[key][idx])
                made_progress = True
                if len(selected) >= max_candidates:
                    break
        if not made_progress:
            break
        idx += 1

    return sorted(selected, key=_sort_key)
