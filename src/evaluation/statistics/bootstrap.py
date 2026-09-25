"""Spec #003 v1.1 SS39, amended by Radu's Sec.74B/D review (2026-09-25) --
TIME_BLOCK clustered bootstrap for confidence intervals ONLY. Raw
significance is a SEPARATE permutation test (statistics/comparison.py) --
never informally derived from whether a bootstrap CI crosses zero
(Radu's explicit correction).

Primary V1 inference mechanism: resample CONTIGUOUS TIME BLOCKS (not
individual episodes, not individual securities), so a common market/
regime shock that hits many securities' episodes in the same week stays
together in every resample -- the failure mode an episode-only or
security-only bootstrap would understate (Radu's own example: NVDA/AMD/
AVGO/CRDO/MRVL all showing an episode the same week Nasdaq jumps +8%).
`block_length_bars` is configurable and must never be tuned against
observed results.
"""
from __future__ import annotations

import random
from typing import Callable, Optional

import numpy as np

from evaluation.models.entities import ConfidenceInterval

METHOD_LABEL = "TIME_BLOCK_BOOTSTRAP_PERCENTILE"


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def time_block_bootstrap_replicates(
    dated_values: list[tuple[str, float]],
    block_length_bars: int,
    iterations: int,
    seed: int,
    statistic: Callable[[list[float]], float] = _mean,
) -> list[float]:
    """`dated_values` sorted by date, split into contiguous blocks of
    `block_length_bars` positions (bar-based, not calendar-day-based --
    the input is already a sequence of observed bars, gaps and all).
    Each replicate resamples whole blocks with replacement until the
    original length is reconstructed (last block truncated to fit), then
    applies `statistic`."""
    if not dated_values or block_length_bars <= 0 or iterations <= 0:
        return []
    ordered = [v for _, v in sorted(dated_values, key=lambda dv: dv[0])]
    n = len(ordered)
    blocks = [ordered[i:i + block_length_bars] for i in range(0, n, block_length_bars)]
    rng = random.Random(seed)
    replicates: list[float] = []
    for _ in range(iterations):
        resampled: list[float] = []
        while len(resampled) < n:
            resampled.extend(blocks[rng.randrange(len(blocks))])
        replicates.append(statistic(resampled[:n]))
    return replicates


def percentile_ci(replicates: list[float], alpha: float = 0.05) -> ConfidenceInterval:
    if not replicates:
        return ConfidenceInterval(lower=None, upper=None, method=METHOD_LABEL)
    arr = np.array(replicates, dtype=float)
    lower = float(np.quantile(arr, alpha / 2))
    upper = float(np.quantile(arr, 1 - alpha / 2))
    return ConfidenceInterval(lower=lower, upper=upper, method=METHOD_LABEL)


def bootstrap_ci_for_series(
    dated_values: list[tuple[str, float]], block_length_bars: int, iterations: int, seed: int,
    statistic: Callable[[list[float]], float] = _mean, alpha: float = 0.05,
) -> ConfidenceInterval:
    replicates = time_block_bootstrap_replicates(dated_values, block_length_bars, iterations, seed, statistic)
    return percentile_ci(replicates, alpha)


def _stable_bin_offset(label: str, sorted_labels: list[str]) -> int:
    """A deterministic, process-stable per-bin seed offset -- Python's
    built-in hash() is salted per-process for strings, which would break
    cross-run reproducibility (Spec #003 SS60); index-into-a-sorted-list
    is stable everywhere."""
    return sorted_labels.index(label)


def stratified_baseline_bootstrap_replicates(
    baseline_dated_values_by_bin: dict[str, list[tuple[str, float]]],
    weights_by_bin: dict[str, float],
    block_length_bars: int,
    iterations: int,
    seed: int,
    statistic: Callable[[list[float]], float] = _mean,
) -> list[float]:
    """The CI-producing counterpart of
    baseline.universe.stratified_baseline_point_estimate: one TIME_BLOCK
    bootstrap replicate per bin per iteration (each bin resampled
    independently, via a stable per-bin seed offset), combined using the
    signature's FIXED bin weights (never resampled themselves)."""
    sorted_labels = sorted(baseline_dated_values_by_bin.keys())
    per_bin_replicates: dict[str, list[float]] = {}
    for label in sorted_labels:
        dated_values = baseline_dated_values_by_bin[label]
        bin_seed = seed + _stable_bin_offset(label, sorted_labels)
        per_bin_replicates[label] = time_block_bootstrap_replicates(
            dated_values, block_length_bars, iterations, bin_seed, statistic,
        ) if dated_values else []

    combined: list[float] = []
    for r in range(iterations):
        total_weight = 0.0
        weighted_sum = 0.0
        for label, weight in weights_by_bin.items():
            if weight <= 0:
                continue
            reps = per_bin_replicates.get(label, [])
            if r >= len(reps):
                continue
            weighted_sum += weight * reps[r]
            total_weight += weight
        if total_weight > 0:
            combined.append(weighted_sum / total_weight)
    return combined
