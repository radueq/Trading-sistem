"""Spec #003 v1.1 SS40, amended by Radu's explicit correction (2026-09-25)
-- raw significance via a SEPARATE permutation test, never informally
derived from whether a bootstrap CI crosses zero. CI and p-value are
related but distinct objects (Radu's own words).

Classic two-sample label-permutation test on
D = mean(signature_values) - mean(baseline_values): the combined pool is
reshuffled into two groups of the observed sizes, without replacement,
`iterations` times, building an empirical null distribution for D under
the exchangeability hypothesis. Two-sided p-value with the standard
add-one continuity correction (avoids a p=0 claim from a finite number
of iterations).

Known limitation (documented, not fixed here): like the bootstrap CI,
this does not fully account for temporal/cross-sectional dependence
between the pooled values -- a block-permutation variant is a natural v2
refinement if the diagnostics (concentration/stability) ever show it's
needed. Not built speculatively now (Spec #003 SS47).
"""
from __future__ import annotations

import random
from typing import Optional


def permutation_p_value(
    signature_values: list[float], baseline_values: list[float], iterations: int, seed: int,
) -> tuple[Optional[float], Optional[float]]:
    """Returns (observed_difference, raw_p); (None, None) if either group
    is empty or iterations <= 0."""
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
