"""Spec #003 v1.1 SS42-43 -- temporal stability bins.

Descriptive only -- explicitly NOT a "stability score" (SS43): an edge
must not look robust if every observation comes from one year/regime,
but this module reports the per-bin breakdown, never a single combined
number.
"""
from __future__ import annotations

import statistics as pystats
from typing import Optional

from evaluation.baseline.universe import TemporalBin, assign_bin
from evaluation.models.entities import StabilityBinResult


def stability_by_bin(
    episode_records: list[dict],  # {as_of, security_id, forward_return, relative_return}
    bins: tuple[TemporalBin, ...],
) -> tuple[StabilityBinResult, ...]:
    results = []
    for b in bins:
        in_bin = [r for r in episode_records if assign_bin(r["as_of"], (b,)) == b.label]
        n = len(in_bin)
        fwd = [r["forward_return"] for r in in_bin if r.get("forward_return") is not None]
        rel = [r["relative_return"] for r in in_bin if r.get("relative_return") is not None]
        results.append(StabilityBinResult(
            bin_label=b.label,
            episode_n=n,
            unique_securities=len({r["security_id"] for r in in_bin}),
            mean=pystats.fmean(fwd) if fwd else None,
            median=pystats.median(fwd) if fwd else None,
            mean_relative=pystats.fmean(rel) if rel else None,
            positive_rate=(sum(1 for v in fwd if v > 0) / len(fwd)) if fwd else None,
        ))
    return tuple(results)
