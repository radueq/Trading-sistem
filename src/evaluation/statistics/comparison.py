"""Spec #003 v1.1 SS40, amended by Radu's explicit correction (2026-09-25)
-- raw significance via a SEPARATE permutation test, never informally
derived from whether a bootstrap CI crosses zero. CI and p-value are
related but distinct objects (Radu's own words).

`stratified_permutation_p_value` is the one `engine.py` actually calls
(GPT Review #003 Round 1, mandatory finding #4): the point estimate and
CI compare against TEMPORALLY_STRATIFIED_ELIGIBLE_BASELINE (weighted by
the signature's own temporal-bin composition, baseline/universe.py), so
the significance test must answer the SAME question -- comparing against
a raw, unstratified baseline pool would test a different, inconsistent
hypothesis (the earlier version's bug). Permutation happens WITHIN each
temporal bin (never across bins, which would re-introduce the exact
regime-mixing problem the stratified baseline exists to avoid), and the
per-bin permuted differences are combined using the signature's SAME
fixed bin weights as the point estimate, mirroring
`statistics/bootstrap.py`'s `stratified_baseline_bootstrap_replicates`.

`permutation_p_value` (plain, unstratified) is kept as a general-purpose
primitive -- used directly where there is no temporal-stratification
concern (e.g. Example D's multiple-testing-trap demonstration, which
compares two flat synthetic pools with no bin structure at all).

Known limitation (documented, not fixed here): within a single bin, this
still does not model finer-grained dependence (e.g. two securities in
the same bin moving together for unrelated-to-the-signature reasons) --
a full two-way clustered permutation is a natural v2 refinement if the
concentration/stability diagnostics ever show it's needed, not built
speculatively now (Spec #003 SS47).
"""
from __future__ import annotations

import random
from typing import Optional


def permutation_p_value(
    signature_values: list[float], baseline_values: list[float], iterations: int, seed: int,
) -> tuple[Optional[float], Optional[float]]:
    """Returns (observed_difference, raw_p); (None, None) if either group
    is empty or iterations <= 0. Classic two-sample label-permutation:
    the combined pool is reshuffled into two groups of the observed
    sizes, `iterations` times, building an empirical null distribution
    for D = mean(signature) - mean(baseline). Two-sided p-value with the
    standard add-one continuity correction (avoids a p=0 claim from a
    finite number of iterations)."""
    n_sig, n_base = len(signature_values), len(baseline_values)
    if n_sig == 0 or n_base == 0 or iterations <= 0:
        return None, None

    observed = sum(signature_values) / n_sig - sum(baseline_values) / n_base
    pooled = list(signature_values) + list(baseline_values)
    rng = random.Random(seed)
    at_least_as_extreme = 0
    for _ in range(iterations):
        shuffled = pooled[:]
        rng.shuffle(shuffled)
        perm_diff = sum(shuffled[:n_sig]) / n_sig - sum(shuffled[n_sig:]) / n_base
        if abs(perm_diff) >= abs(observed):
            at_least_as_extreme += 1
    raw_p = (at_least_as_extreme + 1) / (iterations + 1)
    return observed, raw_p


def _bin_row_weights(baseline_rows: list[tuple[str, float]]) -> list[float]:
    """Per-security-equalized LOCAL weight `1/(k_b*n_i,b)` for each row,
    position-aligned to `baseline_rows`' own order (joint remediation
    design 003+004 section 5; decision registry A4). The bin-level `W_b`
    factor from the point estimate's own `w = W_b/(k_b*n_i,b)` formula
    is omitted here on purpose -- it is a constant multiplicative factor
    across every row of ONE bin, so it cancels exactly in the weighted
    mean this function's weights feed into; only the RELATIVE,
    per-security weighting matters within a single bin's own permutation
    pool."""
    counts: dict[str, int] = {}
    for sid, _ in baseline_rows:
        counts[sid] = counts.get(sid, 0) + 1
    k_b = len(counts)
    return [1.0 / (k_b * counts[sid]) for sid, _ in baseline_rows]


def _weighted_mean(values: list[float], weights: list[float]) -> float:
    total_w = sum(weights)
    return sum(v * w for v, w in zip(values, weights)) / total_w


def stratified_permutation_p_value(
    signature_values_by_bin: dict[str, list[float]],
    baseline_rows_by_bin: dict[str, list[tuple[str, float]]],  # (security_id, value) per row
    weights_by_bin: dict[str, float],
    iterations: int,
    seed: int,
) -> tuple[Optional[float], Optional[float]]:
    """The stratified counterpart of `permutation_p_value`, consistent
    with `baseline.universe.stratified_baseline_weighted_points` and
    `statistics.bootstrap.stratified_baseline_bootstrap_replicates`
    (joint remediation design 003+004 section 5; decision registry A4,
    correcting the pre-Stage-4 mismatch where this test compared against
    a PLAIN baseline mean while the reported effect size already used a
    per-security-weighted one): a bin contributes to `observed`/the null
    distribution only when BOTH its signature and baseline pools are
    non-empty and its weight > 0 -- exactly the same inclusion rule the
    point estimate uses.

    WITHIN each bin, the fixed per-row weight (`_bin_row_weights()`,
    `1/(k_b*n_i,b)`) is precomputed ONCE from the TRUE baseline
    composition and stays bound to its POSITION in that bin's pooled
    array (signature values ++ baseline values, exactly as before) --
    never to whichever value a shuffle later places there. For
    `observed` and every permuted replicate, only the VALUES are
    shuffled: the signature-side statistic is the plain mean of
    whichever values land in the fixed signature slots, and the
    baseline-side statistic is the WEIGHTED mean of whichever values
    land in the baseline slots, using each slot's own fixed weight.

    At equal per-security weight (one row per security, `k_b ==
    len(baseline_rows)`), the fixed weights are uniform and this
    reduces BYTE-IDENTICAL to the pre-Stage-4 plain test (same observed
    value, p-value, RNG sequence) -- the per-bin pooling/shuffle
    mechanics and iteration order are otherwise unchanged.

    Returns (observed_difference, raw_p); (None, None) if no bin
    qualifies."""
    pools: dict[str, tuple[list[float], list[tuple[str, float]]]] = {}
    for label, weight in weights_by_bin.items():
        if weight <= 0:
            continue
        sig_vals = signature_values_by_bin.get(label, [])
        base_rows = baseline_rows_by_bin.get(label, [])
        if not sig_vals or not base_rows:
            continue
        pools[label] = (sig_vals, base_rows)
    if not pools or iterations <= 0:
        return None, None

    bin_weights: dict[str, list[float]] = {
        label: _bin_row_weights(base_rows) for label, (_, base_rows) in pools.items()
    }

    total_weight = sum(weights_by_bin[label] for label in pools)
    observed = sum(
        weights_by_bin[label] * (
            sum(sig_vals) / len(sig_vals) - _weighted_mean([v for _, v in base_rows], bin_weights[label])
        )
        for label, (sig_vals, base_rows) in pools.items()
    ) / total_weight

    rng = random.Random(seed)
    at_least_as_extreme = 0
    for _ in range(iterations):
        combined = 0.0
        for label, (sig_vals, base_rows) in pools.items():
            n_sig = len(sig_vals)
            base_values = [v for _, v in base_rows]
            pooled = sig_vals + base_values
            rng.shuffle(pooled)
            shuffled_base = pooled[n_sig:]
            perm_diff = sum(pooled[:n_sig]) / n_sig - _weighted_mean(shuffled_base, bin_weights[label])
            combined += weights_by_bin[label] * perm_diff
        combined /= total_weight
        if abs(combined) >= abs(observed):
            at_least_as_extreme += 1
    raw_p = (at_least_as_extreme + 1) / (iterations + 1)
    return observed, raw_p
