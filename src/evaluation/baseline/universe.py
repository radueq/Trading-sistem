"""Spec #003 v1.1 SS33-34, amended by Radu's §74C review (2026-09-25) --
TEMPORALLY_STRATIFIED_ELIGIBLE_BASELINE.

The naive "unconditional eligible-universe baseline" (raw-row pooling
across all of Development) lets a signature that clusters in one regime
(e.g. almost all episodes in a 2024-2025 bull run) look like it beats a
baseline dominated by a totally different regime -- the apparent "edge"
could just be the regime, not the signature. Fixed per Radu's decision:
baseline strata are drawn from the SAME temporal bins as the signature's
own episodes, then combined using the SIGNATURE's own bin composition
(weights), never the baseline's own raw bin sizes. Also excludes the
identical `security_id x observation_as_of` pair from its own control
pool where present (Radu's amendment). Sector/volatility/beta/market-cap
matched controls remain explicitly out of scope (Radu's own words).
"""
from __future__ import annotations

import statistics as pystats
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class TemporalBin:
    label: str
    start_date: str
    end_date: str  # inclusive


def partition_temporal_bins(development_start: str, development_end: str, n_bins: int) -> tuple[TemporalBin, ...]:
    """Equal calendar-span bins over [development_start, development_end]
    (Spec #003 SS43's own "early/middle/late" framing for n_bins=3).
    Calendar-span, not equal-count-of-observations, so a signature that
    is simply more active doesn't distort the bin boundaries themselves."""
    from datetime import date, timedelta

    start = date.fromisoformat(development_start)
    end = date.fromisoformat(development_end)
    total_days = (end - start).days + 1
    if total_days <= 0 or n_bins <= 0:
        return ()

    labels = _bin_labels(n_bins)
    span = total_days / n_bins
    bins = []
    for i, label in enumerate(labels):
        bin_start = start + timedelta(days=round(i * span))
        bin_end_exclusive = start + timedelta(days=round((i + 1) * span))
        bin_end = bin_end_exclusive - timedelta(days=1) if i < n_bins - 1 else end
        bins.append(TemporalBin(label=label, start_date=bin_start.isoformat(), end_date=bin_end.isoformat()))
    return tuple(bins)


def _bin_labels(n_bins: int) -> list[str]:
    if n_bins == 1:
        return ["all"]
    if n_bins == 2:
        return ["early", "late"]
    if n_bins == 3:
        return ["early", "middle", "late"]
    return [f"bin_{i+1}" for i in range(n_bins)]


def assign_bin(as_of: str, bins: tuple[TemporalBin, ...]) -> Optional[str]:
    for b in bins:
        if b.start_date <= as_of <= b.end_date:
            return b.label
    return None


def bin_composition(dates: list[str], bins: tuple[TemporalBin, ...]) -> dict[str, float]:
    """`{bin_label: weight}` -- the fraction of `dates` (e.g. a
    signature's episode representative dates) falling in each bin.
    Dates outside every bin are dropped from the denominator."""
    counts: dict[str, int] = {b.label: 0 for b in bins}
    matched = 0
    for d in dates:
        label = assign_bin(d, bins)
        if label is not None:
            counts[label] += 1
            matched += 1
    if matched == 0:
        return {b.label: 0.0 for b in bins}
    return {label: count / matched for label, count in counts.items()}


def stratified_baseline_point_estimate(
    baseline_dated_values: list[tuple[str, float]],
    weights_by_bin: dict[str, float],
    bins: tuple[TemporalBin, ...],
    stat: Callable[[list[float]], float],
) -> Optional[float]:
    """Per-bin statistic (e.g. mean or median) computed directly on the
    baseline pool within that bin, then combined using the SIGNATURE's
    own bin weights (`weights_by_bin`) -- a weighted average of per-bin
    statistics, per Radu's own description ("compare against eligible-
    universe observations in same T... apoi agregam strata"). A
    documented Level 1 simplification, not a true weighted-quantile pool
    (see docs/spec003_known_limitations.md)."""
    values_by_bin: dict[str, list[float]] = {b.label: [] for b in bins}
    for d, v in baseline_dated_values:
        label = assign_bin(d, bins)
        if label is not None:
            values_by_bin[label].append(v)

    total_weight = 0.0
    weighted_sum = 0.0
    for label, weight in weights_by_bin.items():
        if weight <= 0:
            continue
        bin_values = values_by_bin.get(label, [])
        if not bin_values:
            continue
        weighted_sum += weight * stat(bin_values)
        total_weight += weight

    if total_weight == 0:
        return None
    return weighted_sum / total_weight


def exclude_self(
    baseline_dated_values: list[tuple[str, str, float]],  # (security_id, as_of, value)
    exclude: set[tuple[str, str]],
) -> list[tuple[str, float]]:
    """Drops `(security_id, observation_as_of)` pairs present in
    `exclude` (Radu's amendment: a signature episode's own observation
    never appears in its own control pool). Returns (date, value)."""
    return [(as_of, v) for sid, as_of, v in baseline_dated_values if (sid, as_of) not in exclude]


def robust_iqr(values: list[float]) -> Optional[float]:
    if len(values) < 2:
        return None
    q1 = pystats.quantiles(values, n=4, method="inclusive")[0]
    q3 = pystats.quantiles(values, n=4, method="inclusive")[2]
    return q3 - q1
