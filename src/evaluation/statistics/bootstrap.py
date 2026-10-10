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
    *,
    keep_empty_as_none: bool = False,
) -> list:
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
    unevenly-spaced panel data.

    `keep_empty_as_none` (Stage 4 round-2 correction, GPT review on
    commit `74dc218`; decision registry A1/A4): default `False`
    preserves the ORIGINAL behavior byte-for-byte -- an iteration whose
    resampled composition is empty contributes NO entry, so the
    returned list can be SHORTER than `iterations`. Pass `True` only
    when the caller is going to combine this list with ANOTHER
    independently-built per-bin list by shared iteration INDEX (e.g.
    `stratified_baseline_replicates_by_bin()`/
    `signature_bootstrap_replicates_by_bin()` below) -- there, silently
    compacting away empty iterations breaks index alignment across
    bins (an empty iteration in one bin's list shifts every
    SUBSEQUENT iteration's position, silently pairing the WRONG
    iterations together once combined). With `True`, the returned list
    is ALWAYS exactly `iterations` long, `None` at any empty
    iteration, so index `r` always identifies the SAME iteration no
    matter which bin's list it came from."""
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
    replicates: list = []
    for _ in range(iterations):
        resampled: list[float] = []
        for _ in range(n_blocks):
            for d in date_blocks[rng.randrange(n_blocks)]:
                resampled.extend(values_by_date.get(d, []))
        if resampled:
            replicates.append(statistic(resampled))
        elif keep_empty_as_none:
            replicates.append(None)
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


def weighted_mean_by_security(rows: list[tuple[str, float]]) -> Optional[float]:
    """Per-security-equalized mean of `(security_id, value)` rows --
    local weight `1/(k*n_i)` per row (`k`=distinct securities present,
    `n_i`=this security's own row count among `rows`); the bin-level
    `W_b` factor from `baseline.universe.stratified_baseline_weighted_
    points()`'s own `w = W_b/(k*n_i)` formula is omitted here on
    purpose -- it is a constant multiplicative factor across every row
    of ONE bin, so it cancels exactly in the ratio this function
    computes. Used as the per-replicate statistic for the bootstrap
    (joint remediation design 003+004 section 6; decision registry A4):
    `k`/`n_i` are recomputed from WHATEVER composition is passed in --
    the caller is responsible for passing the real sample's rows for
    the point estimate's own CI, or one replicate's own resampled rows
    for the per-replicate bootstrap statistic, never the original
    sample's fixed weights reused across replicates. `None` if `rows`
    is empty."""
    if not rows:
        return None
    counts: dict[str, int] = {}
    for sid, _ in rows:
        counts[sid] = counts.get(sid, 0) + 1
    k = len(counts)
    total_weight = 0.0
    total = 0.0
    for sid, v in rows:
        w = 1.0 / (k * counts[sid])
        total += w * v
        total_weight += w
    return total / total_weight if total_weight > 0 else None


def _stable_bin_offset(label: str, sorted_labels: list[str]) -> int:
    """A deterministic, process-stable per-bin seed offset -- Python's
    built-in hash() is salted per-process for strings, which would break
    cross-run reproducibility (Spec #003 SS60); index-into-a-sorted-list
    is stable everywhere."""
    return sorted_labels.index(label)


def _replicates_by_bin(
    rows_by_bin: dict[str, list],  # label -> (as_of, payload) rows, payload shaped for `statistic`
    session_dates_by_bin: dict[str, list[str]],
    block_length_bars: int,
    iterations: int,
    seed: int,
    statistic: Callable,
) -> dict[str, list]:
    """Shared builder for the per-bin, per-ITERATION-INDEXED (`None`-
    preserving) replicate lists both
    `stratified_baseline_replicates_by_bin()` and
    `signature_bootstrap_replicates_by_bin()` need (Stage 4 round-2
    correction; GPT review on commit `74dc218`): each bin resampled
    independently over ITS OWN slice of the real session calendar via
    a stable per-bin seed offset, `keep_empty_as_none=True` so every
    returned list is exactly `iterations` long and index `r` always
    identifies the SAME iteration across bins -- the caller (never
    this function) decides how to combine bins, and must check for
    `None` at the SAME index on every side it combines, never relying
    on list length alone."""
    sorted_labels = sorted(rows_by_bin.keys())
    result: dict[str, list] = {}
    for label in sorted_labels:
        rows = rows_by_bin[label]
        bin_sessions = session_dates_by_bin.get(label, [])
        bin_seed = seed + _stable_bin_offset(label, sorted_labels)
        result[label] = time_block_bootstrap_replicates(
            rows, bin_sessions, block_length_bars, iterations, bin_seed,
            statistic=statistic, keep_empty_as_none=True,
        ) if rows and bin_sessions else [None] * iterations
    return result


def stratified_baseline_replicates_by_bin(
    baseline_dated_values_by_bin: dict[str, list[tuple[str, str, float]]],  # (security_id, as_of, value)
    session_dates_by_bin: dict[str, list[str]],
    block_length_bars: int,
    iterations: int,
    seed: int,
) -> dict[str, list]:
    """The CI-producing counterpart of
    `baseline.universe.stratified_baseline_weighted_points` (joint
    remediation design 003+004 section 6; decision registry A4): per
    bin, per ITERATION, the per-security-weighted mean
    (`weighted_mean_by_security`) of THAT replicate's own resampled
    composition -- `k`/`n_i` recomputed fresh each replicate, never
    the original sample's fixed weights.

    Returns `{bin_label: [iterations values, None where empty]}` --
    NOT combined across bins (Stage 4 round-2 correction: combining
    here, by list position after silently dropping empty replicates,
    is exactly the bug GPT's review caught -- a bin empty at iteration
    3 would shift every later iteration's position, silently pairing
    iteration 4's OTHER bins with iteration 3's position). Combining
    is the caller's job, done by `common_support_difference_
    replicates()` below, which also needs the SIGNATURE side's own
    per-bin replicates to apply common support to BOTH sides at once."""
    rows_by_bin = {label: [(as_of, (sid, v)) for sid, as_of, v in rows] for label, rows in baseline_dated_values_by_bin.items()}
    return _replicates_by_bin(rows_by_bin, session_dates_by_bin, block_length_bars, iterations, seed, weighted_mean_by_security)


def signature_bootstrap_replicates_by_bin(
    dated_values_by_bin: dict[str, list[tuple[str, float]]],  # (as_of, value), already grouped by bin
    session_dates_by_bin: dict[str, list[str]],
    block_length_bars: int,
    iterations: int,
    seed: int,
) -> dict[str, list]:
    """The signature side's own per-bin, per-iteration replicates --
    plain mean (the signature side is never per-security weighted;
    F4+F5 is a baseline-only concept). Added this round (Stage 4
    round-2 correction; GPT review on commit `74dc218`, section 6):
    before this, the signature's own bootstrap was ONE flat resample
    over the whole series, with no bin structure at all -- making it
    impossible to know, per replicate, which bins the signature side
    actually had data in, so `common_support_difference_replicates()`
    below could not apply common support to the signature side."""
    return _replicates_by_bin(dated_values_by_bin, session_dates_by_bin, block_length_bars, iterations, seed, _mean)


def common_support_difference_replicates(
    signature_replicates_by_bin: dict[str, list],
    baseline_replicates_by_bin: dict[str, list],
    weights_by_bin: dict[str, float],
    iterations: int,
) -> list[float]:
    """Per-ITERATION (signature - baseline) difference, applying
    common support WITHIN EACH REPLICATE to BOTH sides together (joint
    remediation design 003+004 section 6; decision registry A1/A4,
    Stage 4 round-2 correction -- GPT review on commit `74dc218`: A1's
    own blackout on the ORIGINAL, unresampled population does not
    cover this case, since support can be complete initially and
    incomplete in a given bootstrap replica). A bin contributes to
    iteration `r`'s difference only when BOTH its signature replicate
    AND its baseline replicate are available (not `None`) at that SAME
    index `r` -- a bin missing on EITHER side at that iteration is
    excluded from BOTH sides for that iteration, never left to bias
    the comparison toward whichever side still has it. Weights are
    renormalized over whichever bins qualify at that iteration (the
    existing `weighted_sum/total_weight` pattern). If NO bin qualifies
    for iteration `r`, that iteration contributes NO entry -- the
    difference is UNAVAILABLE, never a partial or substituted
    comparison."""
    diffs: list[float] = []
    for r in range(iterations):
        total_weight = 0.0
        sig_weighted = 0.0
        base_weighted = 0.0
        for label, weight in weights_by_bin.items():
            if weight <= 0:
                continue
            sig_list = signature_replicates_by_bin.get(label)
            base_list = baseline_replicates_by_bin.get(label)
            if sig_list is None or base_list is None or r >= len(sig_list) or r >= len(base_list):
                continue
            sig_val, base_val = sig_list[r], base_list[r]
            if sig_val is None or base_val is None:
                continue
            sig_weighted += weight * sig_val
            base_weighted += weight * base_val
            total_weight += weight
        if total_weight > 0:
            diffs.append(sig_weighted / total_weight - base_weighted / total_weight)
    return diffs
