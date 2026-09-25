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


def stratified_permutation_p_value(
    signature_values_by_bin: dict[str, list[float]],
    baseline_values_by_bin: dict[str, list[float]],
    weights_by_bin: dict[str, float],
    iterations: int,
    seed: int,
) -> tuple[Optional[float], Optional[float]]:
    """The stratified counterpart of `permutation_p_value`, consistent
    with `baseline.universe.stratified_baseline_point_estimate` and
    `statistics.bootstrap.stratified_baseline_bootstrap_replicates`: a
    bin contributes to `observed`/the null distribution only when BOTH
    its signature and baseline pools are non-empty and its weight > 0 --
    exactly the same inclusion rule the point estimate uses, so `raw_p`
    is testing the identical weighted quantity the reported effect size
    is measuring. Returns (observed_difference, raw_p); (None, None) if
    no bin qualifies."""
    pools: dict[str, tuple[list[float], list[float]]] = {}
    for label, weight in weights_by_bin.items():
        if weight <= 0:
            continue
        sig_vals = signature_values_by_bin.get(label, [])
        base_vals = baseline_values_by_bin.get(label, [])
        if not sig_vals or not base_vals:
            continue
        pools[label] = (sig_vals, base_vals)
    if not pools or iterations <= 0:
        return None, None

    total_weight = sum(weights_by_bin[label] for label in pools)
    observed = sum(
        weights_by_bin[label] * (sum(sig_vals) / len(sig_vals) - sum(base_vals) / len(base_vals))
        for label, (sig_vals, base_vals) in pools.items()
    ) / total_weight

    rng = random.Random(seed)
    at_least_as_extreme = 0
    for _ in range(iterations):
        combined = 0.0
        for label, (sig_vals, base_vals) in pools.items():
            n_sig = len(sig_vals)
            pooled = sig_vals + base_vals
            rng.shuffle(pooled)
            perm_diff = sum(pooled[:n_sig]) / n_sig - sum(pooled[n_sig:]) / len(base_vals)
            combined += weights_by_bin[label] * perm_diff
        combined /= total_weight
        if abs(combined) >= abs(observed):
            at_least_as_extreme += 1
    raw_p = (at_least_as_extreme + 1) / (iterations + 1)
    return observed, raw_p
