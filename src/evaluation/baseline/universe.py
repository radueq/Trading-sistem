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

import math
from dataclasses import dataclass
from typing import Optional

from evaluation.models.entities import SessionMassBin


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


def exclude_self(
    baseline_dated_values: list[tuple[str, str, float]],  # (security_id, as_of, value)
    exclude: set[tuple[str, str]],
) -> list[tuple[str, str, float]]:
    """Drops `(security_id, observation_as_of)` pairs present in
    `exclude` (Radu's amendment: a signature episode's own observation
    never appears in its own control pool). Returns `(security_id,
    as_of, value)` -- security identity is preserved (joint remediation
    design 003+004 section 3-4; decision registry A3): F4+F5's
    per-security weighting needs it downstream, and the old `(date,
    value)`-only return silently discarded it, which is exactly why the
    pre-Stage-4 point estimate could never implement per-security
    weighting for any statistic."""
    return [(sid, as_of, v) for sid, as_of, v in baseline_dated_values if (sid, as_of) not in exclude]


def stratified_baseline_weighted_points(
    baseline_dated_values: list[tuple[str, str, float]],  # (security_id, as_of, value)
    weights_by_bin: dict[str, float],
    bins: tuple[TemporalBin, ...],
) -> list[tuple[float, float]]:
    """ONE pooled weighted baseline distribution (joint remediation
    design 003+004 section 3-4; decision registry A3 -- replaces the old
    two-level "per-bin plain stat, then bin-weighted-average" mechanism
    entirely, not merely a `baseline_iqr`-only patch beside it). Every
    eligible row across every bin with `weights_by_bin[label] > 0`
    carries its own per-security weight `w = W_b / (k_b * n_i,b)` --
    `W_b`=this row's own bin weight (the signature's bin composition,
    `bin_composition()`), `k_b`=distinct securities within that bin,
    `n_i,b`=this security's own row count within that bin -- which
    equalizes each security's TOTAL weight within its bin (F4+F5),
    never a raw per-row weight that lets a security with more rows
    dominate. Summing one bin's own rows' weights reproduces `W_b`
    exactly, so the returned pool needs no separate cross-bin
    combination step: a single weighted mean/quantile computed directly
    over the FULL returned pool already combines bins correctly.

    Returns `(value, weight)` pairs feeding `baseline_mean` (via
    `weighted_mean()`), `baseline_median`, and `baseline_iqr`'s own
    Q1/Q3 (via `weighted_quantile()`) TOGETHER from this IDENTICAL
    pooled set -- never three independently-built distributions."""
    rows_by_bin: dict[str, list[tuple[str, float]]] = {b.label: [] for b in bins}
    for sid, as_of, v in baseline_dated_values:
        label = assign_bin(as_of, bins)
        if label is not None:
            rows_by_bin[label].append((sid, v))

    points: list[tuple[float, float]] = []
    for label, weight in weights_by_bin.items():
        if weight <= 0:
            continue
        rows = rows_by_bin.get(label, [])
        if not rows:
            continue
        counts: dict[str, int] = {}
        for sid, _ in rows:
            counts[sid] = counts.get(sid, 0) + 1
        k_b = len(counts)
        for sid, v in rows:
            n_i_b = counts[sid]
            points.append((v, weight / (k_b * n_i_b)))
    return points


def weighted_mean(points: list[tuple[float, float]]) -> Optional[float]:
    """Plain weighted mean of `(value, weight)` pairs (a zero weight is
    silently excluded, mirroring this module's established `if weight
    <= 0: continue` convention elsewhere -- unlike `weighted_quantile()`,
    this function has no interpolation step for which a negative/
    non-finite weight would silently corrupt a position, so it is not
    separately hard-failed here). `None` if no positive-weight point
    survives."""
    total_weight = 0.0
    total = 0.0
    for v, w in points:
        if w <= 0:
            continue
        total += w * v
        total_weight += w
    if total_weight == 0:
        return None
    return total / total_weight


def weighted_quantile(points: list[tuple[float, float]], p: float) -> Optional[float]:
    """Midpoint (Hazen-type) weighted quantile, WITH MANDATORY
    TIE-AGGREGATION (joint remediation design 003+004 section 4;
    decision registry A3 -- the adopted convention; the alternative
    rescaled/`R_i` convention explored in the design doc was NOT
    adopted, since its inclusive-reproduction property breaks once
    tie-aggregation collapses tied values).

    Algorithm: (1) aggregate (sum) the weights of every row sharing an
    IDENTICAL value into ONE point, BEFORE any cumulative-position
    computation -- required to remove order-dependence (the same
    multiset of `(value, weight)` pairs in a different input order
    would otherwise give different answers); (2) sort the aggregated
    points ascending by value; (3) `C_i` = cumulative weight through
    point i (inclusive); (4) `P_i = (C_i - 0.5*w_i) / W` (`W`=total
    weight); (5) linearly interpolate between the two `P_i` bracketing
    `p`, clamping to the first/last point's value when `p` falls
    outside `[P_1, P_n]`. Does NOT reproduce
    `statistics.quantiles(method="inclusive")`, even on tie-free
    equal-weight input -- a deliberate, documented difference (e.g.
    `[0,10,20]` at equal weight gives `Q1=2.5`/`median=10`/`Q3=17.5`
    here, vs `[5,10,15]` under "inclusive").

    Contract: a non-finite value or weight, OR a negative weight, is a
    hard-fail (`ValueError`) -- filtering ineligible rows is the
    CALLER's responsibility, done before calling, with the exclusion
    recorded explicitly (e.g. in `warnings`); a quantile function that
    silently reinterpreted malformed input would mask an upstream bug.
    A zero-weight row is excluded silently (not an error -- the one
    intentional exception, mirroring this module's established
    convention elsewhere). Empty input (no positive-weight point
    survives) returns `None`. A single distinct value with positive
    weight returns that value for every `p`, trivially."""
    cleaned: list[tuple[float, float]] = []
    for v, w in points:
        if not math.isfinite(v) or not math.isfinite(w):
            raise ValueError(f"weighted_quantile() received a non-finite value/weight: ({v!r}, {w!r})")
        if w < 0:
            raise ValueError(f"weighted_quantile() received a negative weight: {w!r} for value {v!r}")
        if w == 0:
            continue
        cleaned.append((v, w))
    if not cleaned:
        return None

    aggregated: dict[float, float] = {}
    for v, w in cleaned:
        aggregated[v] = aggregated.get(v, 0.0) + w
    sorted_points = sorted(aggregated.items())

    if len(sorted_points) == 1:
        return sorted_points[0][0]

    total_weight = sum(w for _, w in sorted_points)
    positions: list[float] = []
    values: list[float] = []
    cumulative = 0.0
    for v, w in sorted_points:
        cumulative += w
        positions.append((cumulative - 0.5 * w) / total_weight)
        values.append(v)

    if p <= positions[0]:
        return values[0]
    if p >= positions[-1]:
        return values[-1]
    for i in range(len(positions) - 1):
        if positions[i] <= p <= positions[i + 1]:
            span = positions[i + 1] - positions[i]
            if span == 0:
                return values[i]
            frac = (p - positions[i]) / span
            return values[i] + frac * (values[i + 1] - values[i])
    return values[-1]  # unreachable -- the boundary checks above cover [positions[0], positions[-1]]


def compute_session_mass(
    baseline_dated_values: list[tuple[str, str, float]],  # (security_id, as_of, value)
    weights_by_bin: dict[str, float],
    bins: tuple[TemporalBin, ...],
) -> tuple[SessionMassBin, ...]:
    """A2 diagnostic -- WEIGHTED per-session mass within the baseline
    pool (joint remediation design 003+004 section 3; decision registry
    A2): `session_mass[t] = sum(w_row for every row dated t)`, using the
    SAME per-security `w_row` formula `stratified_baseline_weighted_
    points()` uses, normalized within each bin (dividing by that bin's
    own total mass, which equals `W_b` by construction) so it sums to
    `1.0` there. NEVER a raw row-count `Counter`, which misreports the
    true influence skew -- e.g. one security present in 2 sessions
    against 9 other securities sharing a 3rd session is a true
    `5%`/`95%` weighted split, which a plain row count would instead
    read as roughly `~9%`/`~91%`.

    Purely descriptive: never consumed by
    `stratified_baseline_weighted_points()`, `weighted_mean()`,
    `weighted_quantile()`, or any weight/significance formula -- same
    category as `compute_concentration()`'s own established pattern."""
    rows_by_bin: dict[str, list[tuple[str, str]]] = {b.label: [] for b in bins}
    for sid, as_of, _ in baseline_dated_values:
        label = assign_bin(as_of, bins)
        if label is not None:
            rows_by_bin[label].append((sid, as_of))

    results: list[SessionMassBin] = []
    for label, weight in weights_by_bin.items():
        if weight <= 0:
            continue
        rows = rows_by_bin.get(label, [])
        if not rows:
            continue
        counts: dict[str, int] = {}
        for sid, _ in rows:
            counts[sid] = counts.get(sid, 0) + 1
        k_b = len(counts)
        mass_by_session: dict[str, float] = {}
        for sid, as_of in rows:
            n_i_b = counts[sid]
            w_row = weight / (k_b * n_i_b)
            mass_by_session[as_of] = mass_by_session.get(as_of, 0.0) + w_row
        bin_total = sum(mass_by_session.values())
        if bin_total <= 0:
            continue
        normalized = {d: m / bin_total for d, m in mass_by_session.items()}
        results.append(SessionMassBin(bin_label=label, session_mass=normalized))
    return tuple(results)
