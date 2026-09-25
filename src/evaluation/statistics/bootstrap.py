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
    session_dates: list[str],
    block_length_bars: int,
    iterations: int,
    seed: int,
    statistic: Callable[[list[float]], float] = _mean,
) -> list[float]:
    """A block is a run of `block_length_bars` CONSECUTIVE MARKET
    SESSIONS from `session_dates` (the run's REAL trading calendar --
    e.g. the benchmark's own bar dates within Development), not a run of
    `block_length_bars` (date, value) ROWS, and not a run of the dates
    merely PRESENT in `dated_values` (GPT Review #003 Round 2, mandatory
    finding: for a sparse/rare signature, the dates it happens to have
    values on can span months with large real-calendar gaps between
    them -- treating THOSE as "consecutive" would mean `block_length_bars
    =20` groups 20 scattered event dates instead of ~20 trading sessions,
    losing the actual local-time-window/regime structure TIME_BLOCK
    clustering exists to preserve). A session with zero values
    contributes nothing when its block is drawn -- expected and normal,
    not an error.

    All values sharing a date are grouped together first (GPT Review
    #003 Round 1, mandatory finding #2: same-day cross-security
    observations -- e.g. NVDA/AMD/AVGO/MRVL/CRDO all showing an episode
    the same week the market jumps -- must never be split across
    different blocks). Each replicate draws as many blocks (with
    replacement) as there are blocks in the real-calendar partition,
    concatenating ALL of each drawn block's values -- the replicate's
    total count is not forced to match the original count exactly, which
    is the standard behavior of a moving block bootstrap over
    unevenly-spaced panel data."""
    if not dated_values or not session_dates or block_length_bars <= 0 or iterations <= 0:
        return []
    values_by_date: dict[str, list[float]] = {}
    for d, v in dated_values:
        values_by_date.setdefault(d, []).append(v)

    ordered_sessions = sorted(set(session_dates))
    n_sessions = len(ordered_sessions)
    date_blocks = [ordered_sessions[i:i + block_length_bars] for i in range(0, n_sessions, block_length_bars)]
    n_blocks = len(date_blocks)
    if n_blocks == 0:
        return []

    rng = random.Random(seed)
    replicates: list[float] = []
    for _ in range(iterations):
        resampled: list[float] = []
        for _ in range(n_blocks):
            for d in date_blocks[rng.randrange(n_blocks)]:
                resampled.extend(values_by_date.get(d, []))
        if resampled:
            replicates.append(statistic(resampled))
    return replicates


def percentile_ci(replicates: list[float], alpha: float = 0.05) -> ConfidenceInterval:
    if not replicates:
        return ConfidenceInterval(lower=None, upper=None, method=METHOD_LABEL)
    arr = np.array(replicates, dtype=float)
    lower = float(np.quantile(arr, alpha / 2))
    upper = float(np.quantile(arr, 1 - alpha / 2))
    return ConfidenceInterval(lower=lower, upper=upper, method=METHOD_LABEL)


def bootstrap_ci_for_series(
    dated_values: list[tuple[str, float]], session_dates: list[str], block_length_bars: int, iterations: int, seed: int,
    statistic: Callable[[list[float]], float] = _mean, alpha: float = 0.05,
) -> ConfidenceInterval:
    replicates = time_block_bootstrap_replicates(dated_values, session_dates, block_length_bars, iterations, seed, statistic)
    return percentile_ci(replicates, alpha)


def _stable_bin_offset(label: str, sorted_labels: list[str]) -> int:
    """A deterministic, process-stable per-bin seed offset -- Python's
    built-in hash() is salted per-process for strings, which would break
    cross-run reproducibility (Spec #003 SS60); index-into-a-sorted-list
    is stable everywhere."""
    return sorted_labels.index(label)


def stratified_baseline_bootstrap_replicates(
    baseline_dated_values_by_bin: dict[str, list[tuple[str, float]]],
    session_dates_by_bin: dict[str, list[str]],
    weights_by_bin: dict[str, float],
    block_length_bars: int,
    iterations: int,
    seed: int,
    statistic: Callable[[list[float]], float] = _mean,
) -> list[float]:
    """The CI-producing counterpart of
    baseline.universe.stratified_baseline_point_estimate: one TIME_BLOCK
    bootstrap replicate per bin per iteration (each bin resampled
    independently over ITS OWN slice of the real session calendar --
    `session_dates_by_bin[label]`, GPT Review #003 Round 2 -- via a
    stable per-bin seed offset), combined using the signature's FIXED
    bin weights (never resampled themselves)."""
    sorted_labels = sorted(baseline_dated_values_by_bin.keys())
    per_bin_replicates: dict[str, list[float]] = {}
    for label in sorted_labels:
        dated_values = baseline_dated_values_by_bin[label]
        bin_sessions = session_dates_by_bin.get(label, [])
        bin_seed = seed + _stable_bin_offset(label, sorted_labels)
        per_bin_replicates[label] = time_block_bootstrap_replicates(
            dated_values, bin_sessions, block_length_bars, iterations, bin_seed, statistic,
        ) if dated_values and bin_sessions else []

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
