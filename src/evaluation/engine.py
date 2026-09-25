"""Spec #003 v1.1 -- Outcome-Aware Evaluation Engine orchestration.

run_evaluation() is the single entry point. Pipeline (Spec #003 SS1):

  PIT-safe historical data + Historical Discovery observations
    -> Outcome Engine (outcomes/forward_returns.py, outcomes/benchmark.py)
    -> Episode Engine (observations/episodes.py)
    -> Statistical Evaluation (statistics/*)
    -> Evidence Profile (models/entities.py)

Evaluation is outcome-aware (SS11); Discovery (Spec #002) remains
permanently outcome-blind. This module reads discovery.engine's
PRE-BUDGET compute_discovery_observations() (PATCH #002-B), never
run_discovery()'s post-budget output -- Candidate Budget is a
downstream/LLM compute-budget knob, not a statistical sampling decision
(Spec #003 IMPLEMENTATION BLOCKER Sec.74A). discovery/ imports nothing
from evaluation/ anywhere (TEST 26).

Locked OOS is never read for anything beyond the exit bar's DATE (to
classify CROSSES_LOCKED_OOS) -- see outcomes/forward_returns.py's
docstring. Zero LLM calls anywhere in this path (SS61).

The only formally significance-tested outcome_type at Level 1 is
`relative_return` (OUTCOME_TYPE below) -- absolute forward_return is
still fully reported (descriptive stats + its own bootstrap CI) but not
separately BH-corrected, avoiding doubling the multiple-testing burden
for a metric that conflates market beta with idiosyncratic signal (see
docs/spec003_known_limitations.md).
"""
from __future__ import annotations

from dataclasses import replace
from typing import Optional

from data_foundation.pit import access as pit

from discovery.config.loader import DiscoveryConfig
from discovery.engine import DISCOVERY_ENGINE_VERSION, compute_discovery_observations

from evaluation.baseline.universe import (
    assign_bin, bin_composition, exclude_self, partition_temporal_bins,
    robust_iqr, stratified_baseline_point_estimate,
)
from evaluation.config.loader import EvaluationConfig
from evaluation.models.entities import (
    BaselineComparison, ConcentrationStats, ConfidenceInterval, DescriptiveStats,
    EvaluationRunRegistry, EvidenceProfile, MissingnessReport, OutcomeStatus,
    SignatureCreationMode, SignatureSet, SupportInfo, SupportStatus,
)
from evaluation.observations.episodes import build_episodes
from evaluation.observations.signatures import match_observations
from evaluation.outcomes.benchmark import attach_benchmark_return
from evaluation.outcomes.forward_returns import compute_forward_outcome
from evaluation.registry.runs import build_run_id, utc_now_iso
from evaluation.statistics.bootstrap import (
    bootstrap_ci_for_series, percentile_ci, stratified_baseline_bootstrap_replicates,
    time_block_bootstrap_replicates,
)
from evaluation.statistics.comparison import stratified_permutation_p_value
from evaluation.statistics.concentration import compute_concentration
from evaluation.statistics.descriptive import describe
from evaluation.statistics.multiple_testing import PValueRecord, benjamini_hochberg, record_key
from evaluation.statistics.opportunity import compute_opportunity_density
from evaluation.statistics.stability import stability_by_bin

EVALUATION_ENGINE_VERSION = "v1.0.0"
OUTCOME_TYPE = "relative_return"
_ZERO_SCALE_EPS = 1e-12


def _resolve_session_dates(conn, benchmark_security_id, development_start, development_end, data_as_of):
    bench_bars = pit.get_price_series_as_of(conn, benchmark_security_id, data_as_of)
    dates = [b.date for b in bench_bars if b.date >= development_start]
    if development_end is not None:
        dates = [d for d in dates if d <= development_end]
    return dates, bench_bars


def _collect_observations(conn, security_ids, observation_dates, benchmark_security_id, discovery_config):
    all_obs = []
    for as_of in observation_dates:
        all_obs.extend(compute_discovery_observations(conn, security_ids, as_of, benchmark_security_id, discovery_config))
    return all_obs


def _fetch_bars_by_security(conn, security_ids, data_as_of):
    return {sid: pit.get_price_series_as_of(conn, sid, data_as_of) for sid in security_ids}


def _build_baseline_pool(all_obs, bars_by_security, benchmark_bars, timeframe, horizons, development_end, config_version):
    """{horizon_bars: [(security_id, as_of, ForwardOutcome)]} for EVERY
    eligible observation, regardless of signature (Spec #003 SS33-34) --
    computed once, reused by every signature's baseline comparison."""
    pool: dict[int, list] = {h: [] for h in horizons}
    for obs in all_obs:
        bars = bars_by_security.get(obs.security_id, [])
        for h in horizons:
            outcome = compute_forward_outcome(
                obs.security_id, bars, obs.as_of, timeframe, h, development_end, config_version,
            )
            outcome = attach_benchmark_return(outcome, benchmark_bars)
            pool[h].append((obs.security_id, obs.as_of, outcome))
    return pool


def _missingness_from_outcomes(raw_n: int, outcomes: list) -> MissingnessReport:
    counts = {s: 0 for s in OutcomeStatus}
    for o in outcomes:
        counts[OutcomeStatus(o.outcome_status)] += 1
    return MissingnessReport(
        eligible_observations=raw_n, raw_observations=raw_n, episodes=len(outcomes),
        valid_outcomes=counts[OutcomeStatus.VALID],
        insufficient_future_data=counts[OutcomeStatus.INSUFFICIENT_FUTURE_DATA],
        crosses_locked_oos=counts[OutcomeStatus.CROSSES_LOCKED_OOS],
        missing_benchmark=counts[OutcomeStatus.MISSING_BENCHMARK],
        invalid_input=counts[OutcomeStatus.INVALID_INPUT],
    )


def _standardized_effect(median_difference: Optional[float], baseline_iqr: Optional[float]):
    if median_difference is None or baseline_iqr is None or abs(baseline_iqr) < _ZERO_SCALE_EPS:
        return None, "UNDEFINED_ZERO_SCALE"
    return median_difference / (baseline_iqr / 1.349), "OK"


def _evaluate_signature_horizon(
    *, signature, horizon_bars, timeframe, raw_matches_by_security, bars_by_security,
    benchmark_bars, development_end, config_version, baseline_pool_h, bins, session_dates,
    ev_config, run_id, mode,
) -> EvidenceProfile:
    episode_cfg = ev_config.data["episode"]
    episodes = []
    for sid, as_ofs in raw_matches_by_security.items():
        bar_dates = [b.date for b in bars_by_security.get(sid, [])]
        episodes.extend(build_episodes(
            sid, signature.signature_id, sorted(as_ofs), bar_dates,
            max_gap_bars=episode_cfg["max_gap_bars"], representative=episode_cfg["representative"],
        ))

    raw_n = sum(len(v) for v in raw_matches_by_security.values())

    episode_outcomes = []
    for ep in episodes:
        bars = bars_by_security.get(ep.security_id, [])
        outcome = compute_forward_outcome(
            ep.security_id, bars, ep.representative_as_of, timeframe, horizon_bars, development_end, config_version,
        )
        outcome = attach_benchmark_return(outcome, benchmark_bars)
        episode_outcomes.append((ep, outcome))

    valid = [(ep, o) for ep, o in episode_outcomes if o.outcome_status == OutcomeStatus.VALID.value]
    absolute_values = [o.forward_return for _, o in valid]
    relative_valid = [(ep, o) for ep, o in valid if o.relative_return is not None]
    relative_values = [o.relative_return for _, o in relative_valid]
    dated_absolute = [(ep.representative_as_of, o.forward_return) for ep, o in valid]
    dated_relative = [(ep.representative_as_of, o.relative_return) for ep, o in relative_valid]

    bootstrap_cfg = ev_config.data["bootstrap"]
    abs_ci = bootstrap_ci_for_series(
        dated_absolute, session_dates, bootstrap_cfg["block_length_bars"], bootstrap_cfg["iterations"], bootstrap_cfg["seed"],
    )
    rel_ci = bootstrap_ci_for_series(
        dated_relative, session_dates, bootstrap_cfg["block_length_bars"], bootstrap_cfg["iterations"], bootstrap_cfg["seed"] + 1,
    )
    absolute_outcome = describe(absolute_values, abs_ci)
    relative_outcome = describe(relative_values, rel_ci)

    # --- Baseline comparison (relative_return, the formally-tested metric) ---
    exclude_pairs = {(ep.security_id, ep.representative_as_of) for ep, _ in relative_valid}
    baseline_all = [
        (sid, as_of, o.relative_return)
        for sid, as_of, o in baseline_pool_h
        if o.outcome_status == OutcomeStatus.VALID.value and o.relative_return is not None
    ]
    baseline_dated = exclude_self(baseline_all, exclude_pairs)

    signature_dates = [ep.representative_as_of for ep, _ in relative_valid]
    weights = bin_composition(signature_dates, bins)

    baseline_mean = stratified_baseline_point_estimate(baseline_dated, weights, bins, lambda vs: sum(vs) / len(vs))
    import statistics as _pystats
    baseline_median = stratified_baseline_point_estimate(baseline_dated, weights, bins, _pystats.median)

    baseline_by_bin: dict[str, list] = {b.label: [] for b in bins}
    for d, v in baseline_dated:
        label = assign_bin(d, bins)
        if label is not None:
            baseline_by_bin[label].append((d, v))
    # Each bin's bootstrap resamples over ITS OWN slice of the real
    # session calendar (GPT Review #003 Round 2), never over the dates
    # merely present in that bin's baseline values.
    session_dates_by_bin: dict[str, list[str]] = {
        b.label: [d for d in session_dates if b.start_date <= d <= b.end_date] for b in bins
    }
    baseline_replicates = stratified_baseline_bootstrap_replicates(
        baseline_by_bin, session_dates_by_bin, weights,
        bootstrap_cfg["block_length_bars"], bootstrap_cfg["iterations"], bootstrap_cfg["seed"] + 2,
    )
    signature_replicates = time_block_bootstrap_replicates(
        dated_relative, session_dates, bootstrap_cfg["block_length_bars"], bootstrap_cfg["iterations"], bootstrap_cfg["seed"] + 3,
    )
    diff_replicates = [
        s - b for s, b in zip(signature_replicates, baseline_replicates)
    ] if signature_replicates and baseline_replicates else []
    mean_difference_ci = percentile_ci(diff_replicates) if diff_replicates else ConfidenceInterval(None, None, "TIME_BLOCK_BOOTSTRAP_PERCENTILE")

    signature_mean_relative = describe(relative_values).mean
    signature_median_relative = describe(relative_values).median
    mean_difference = (
        signature_mean_relative - baseline_mean if signature_mean_relative is not None and baseline_mean is not None else None
    )
    median_difference = (
        signature_median_relative - baseline_median if signature_median_relative is not None and baseline_median is not None else None
    )

    baseline_iqr = robust_iqr([v for _, v in baseline_dated])
    standardized_effect, standardized_effect_status = _standardized_effect(median_difference, baseline_iqr)

    # Stratified permutation test (GPT Review #003 Round 1, finding #4):
    # must compare against the SAME per-bin baseline pools and weights as
    # the point estimate/CI above -- never the raw unstratified pool.
    signature_values_by_bin: dict[str, list[float]] = {b.label: [] for b in bins}
    for ep, o in relative_valid:
        label = assign_bin(ep.representative_as_of, bins)
        if label is not None:
            signature_values_by_bin[label].append(o.relative_return)
    baseline_values_by_bin = {label: [v for _, v in dated] for label, dated in baseline_by_bin.items()}

    comparison_cfg = ev_config.data["comparison"]
    observed_diff, raw_p = stratified_permutation_p_value(
        signature_values_by_bin, baseline_values_by_bin, weights, comparison_cfg["iterations"], comparison_cfg["seed"],
    )

    family_id = f"{timeframe}|{horizon_bars}bars|{OUTCOME_TYPE}|{run_id}" if raw_p is not None else None
    mt_cfg = ev_config.data["multiple_testing"]

    baseline_comparison = BaselineComparison(
        baseline_mean=baseline_mean, baseline_median=baseline_median,
        mean_difference=mean_difference, median_difference=median_difference,
        mean_difference_ci=mean_difference_ci,
        standardized_effect=standardized_effect, standardized_effect_status=standardized_effect_status,
        raw_p=raw_p, adjusted_p=None, family_id=family_id,
        multiple_testing_method=mt_cfg["method"] if mode == "FORMAL_DEVELOPMENT" else None,
    )

    # Concentration and support are both computed over relative_valid --
    # the population the formal comparison/effect-size/p-value actually
    # runs on (GPT Review #003 Round 1, finding #5) -- not the broader
    # `valid` (absolute-only) or raw total episode count. A signature
    # with many total episodes but few usable relative outcomes must not
    # look better-supported than it actually is.
    concentration = compute_concentration([ep.security_id for ep, _ in relative_valid])

    stability_records = [
        {"as_of": ep.representative_as_of, "security_id": ep.security_id,
         "forward_return": o.forward_return, "relative_return": o.relative_return}
        for ep, o in valid
    ]
    stability = stability_by_bin(stability_records, bins)

    opportunity_density = compute_opportunity_density(
        [ep.representative_as_of for ep in episodes], session_dates,
    )

    missingness = _missingness_from_outcomes(raw_n, [o for _, o in episode_outcomes])

    support_cfg = ev_config.data["support"]
    valid_episode_n = len(relative_valid)
    unique_securities = concentration.unique_security_count
    support_status = (
        SupportStatus.SUFFICIENT.value
        if valid_episode_n >= support_cfg["minimum_episode_count"] and unique_securities >= support_cfg["minimum_unique_securities"]
        else SupportStatus.INSUFFICIENT.value
    )
    support = SupportInfo(
        raw_n=raw_n, episode_n=len(episodes), valid_episode_n=valid_episode_n,
        unique_security_count=unique_securities, support_status=support_status,
    )

    return EvidenceProfile(
        signature_id=signature.signature_id, timeframe=timeframe, horizon_bars=horizon_bars,
        evaluation_mode=mode, support=support, opportunity_density=opportunity_density,
        absolute_outcome=absolute_outcome, relative_outcome=relative_outcome,
        baseline_comparison=baseline_comparison, concentration=concentration,
        stability=stability, missingness=missingness, warnings=(),
    )


def run_evaluation(
    conn,
    security_ids: list[str],
    benchmark_security_id: str,
    development_start: str,
    development_end: Optional[str],
    signature_set: SignatureSet,
    discovery_config: DiscoveryConfig,
    evaluation_config: EvaluationConfig,
    data_as_of: Optional[str] = None,
) -> tuple[list[EvidenceProfile], EvaluationRunRegistry]:
    """THE single entry point. Returns every (signature x horizon)
    EvidenceProfile plus this run's reproducibility metadata (Spec #003
    SS59-60)."""
    ev_data = evaluation_config.data
    mode = ev_data["evaluation_mode"]
    timeframe = ev_data["timeframe"]
    horizons = list(ev_data["horizons"]["values"])
    if ev_data["horizons"]["unit"] != "BARS":
        raise ValueError("Spec #003 SS3-4: horizons.unit must be BARS")

    if mode == "FORMAL_DEVELOPMENT":
        # GPT Review #003 Round 1, mandatory finding #3: a frozen
        # Signature Set (SS26) is meaningless if a post-hoc signature can
        # still be run through a FORMAL_DEVELOPMENT evaluation -- this
        # must be a hard error, fast, before any PIT/Discovery work.
        for sig in signature_set.signatures:
            if sig.creation_mode != SignatureCreationMode.PRE_REGISTERED.value or not sig.created_before_outcome_evaluation:
                raise ValueError(
                    "FORMAL_DEVELOPMENT requires every signature to be PRE_REGISTERED "
                    "with created_before_outcome_evaluation=True (Spec #003 SS26/SS28) -- "
                    f"signature {sig.signature_id!r} has creation_mode={sig.creation_mode!r}, "
                    f"created_before_outcome_evaluation={sig.created_before_outcome_evaluation!r}"
                )
            # GPT Review #003 Round 2 guard: the fingerprint correctly
            # makes a provenance mismatch produce a DIFFERENT
            # signature_set_id, but nothing previously stopped a
            # signature pre-registered under one Discovery config/version
            # from actually being RUN against a different one -- the two
            # entities would be legitimately different, yet the engine
            # would silently accept the mismatched combination. Hard
            # error instead.
            if sig.timeframe != timeframe:
                raise ValueError(
                    f"FORMAL_DEVELOPMENT: signature {sig.signature_id!r} was pre-registered for "
                    f"timeframe={sig.timeframe!r}, but this run's timeframe is {timeframe!r}"
                )
            if sig.discovery_engine_version != DISCOVERY_ENGINE_VERSION:
                raise ValueError(
                    f"FORMAL_DEVELOPMENT: signature {sig.signature_id!r} was pre-registered against "
                    f"discovery_engine_version={sig.discovery_engine_version!r}, but the current one is "
                    f"{DISCOVERY_ENGINE_VERSION!r}"
                )
            if sig.discovery_config_version != discovery_config.config_version:
                raise ValueError(
                    f"FORMAL_DEVELOPMENT: signature {sig.signature_id!r} was pre-registered against "
                    f"discovery_config_version={sig.discovery_config_version!r}, but the discovery_config "
                    f"passed to this run is {discovery_config.config_version!r}"
                )

    data_as_of = data_as_of or development_end
    if data_as_of is None:
        raise ValueError("data_as_of is required when development_end is not set (SS13)")

    session_dates, benchmark_bars = _resolve_session_dates(
        conn, benchmark_security_id, development_start, development_end, data_as_of,
    )
    all_obs = _collect_observations(conn, security_ids, session_dates, benchmark_security_id, discovery_config)

    involved_security_ids = sorted({o.security_id for o in all_obs})
    bars_by_security = _fetch_bars_by_security(conn, involved_security_ids, data_as_of)

    baseline_pool = _build_baseline_pool(
        all_obs, bars_by_security, benchmark_bars, timeframe, horizons, development_end,
        evaluation_config.config_version,
    )

    bin_end = development_end or (session_dates[-1] if session_dates else development_start)
    stability_cfg = ev_data["stability"]
    bins = partition_temporal_bins(development_start, bin_end, stability_cfg["temporal_bins"])

    run_id = build_run_id(
        development_start=development_start, development_end=development_end,
        timeframe=timeframe, signature_set_id=signature_set.signature_set_id,
        discovery_config_version=discovery_config.config_version,
        evaluation_config_version=evaluation_config.config_version,
        bootstrap_seed=ev_data["bootstrap"]["seed"], comparison_seed=ev_data["comparison"]["seed"],
    )

    profiles: list[EvidenceProfile] = []
    for signature in signature_set.signatures:
        matched = match_observations(all_obs, signature)
        raw_matches_by_security: dict[str, list[str]] = {}
        for o in matched:
            raw_matches_by_security.setdefault(o.security_id, []).append(o.as_of)

        for h in horizons:
            profiles.append(_evaluate_signature_horizon(
                signature=signature, horizon_bars=h, timeframe=timeframe,
                raw_matches_by_security=raw_matches_by_security, bars_by_security=bars_by_security,
                benchmark_bars=benchmark_bars, development_end=development_end,
                config_version=evaluation_config.config_version, baseline_pool_h=baseline_pool[h],
                bins=bins, session_dates=session_dates, ev_config=evaluation_config,
                run_id=run_id, mode=mode,
            ))

    if mode == "FORMAL_DEVELOPMENT":
        records = [
            PValueRecord(p.signature_id, p.timeframe, p.horizon_bars, OUTCOME_TYPE, run_id, p.baseline_comparison.raw_p)
            for p in profiles if p.baseline_comparison.raw_p is not None
        ]
        adjusted = benjamini_hochberg(records)
        new_profiles = []
        for p in profiles:
            # Keyed by the FULL (signature_id, timeframe, horizon_bars,
            # outcome_type, run_id) tuple -- a plain signature_id lookup
            # would silently apply one horizon's adjusted_p/family_id to
            # every other horizon of the same signature (GPT Review #003
            # Round 1, mandatory finding #1).
            key = record_key(PValueRecord(p.signature_id, p.timeframe, p.horizon_bars, OUTCOME_TYPE, run_id, 0.0))
            if key in adjusted:
                adj_p, fam_id = adjusted[key]
                p = replace(p, baseline_comparison=replace(p.baseline_comparison, adjusted_p=adj_p, family_id=fam_id))
            new_profiles.append(p)
        profiles = new_profiles

    registry = EvaluationRunRegistry(
        evaluation_run_id=run_id, created_at=utc_now_iso(), mode=mode,
        development_start=development_start, development_end=development_end,
        timeframe=timeframe, horizons=tuple(horizons), benchmark_security_id=benchmark_security_id,
        discovery_engine_version=DISCOVERY_ENGINE_VERSION,
        discovery_config_version=discovery_config.config_version,
        evaluation_engine_version=EVALUATION_ENGINE_VERSION, evaluation_config_version=evaluation_config.config_version,
        signature_set_id=signature_set.signature_set_id,
        bootstrap_seed=ev_data["bootstrap"]["seed"], bootstrap_iterations=ev_data["bootstrap"]["iterations"],
        comparison_seed=ev_data["comparison"]["seed"], comparison_iterations=ev_data["comparison"]["iterations"],
        multiple_testing_method=ev_data["multiple_testing"]["method"],
    )
    return profiles, registry


def decay_curve(profiles: list[EvidenceProfile], signature_id: str) -> list[tuple[int, Optional[float], Optional[float]]]:
    """Spec #003 SS52-53 -- report the curve across horizons for ONE
    signature, never pick a winner horizon. (horizon_bars, mean_forward,
    mean_relative), sorted by horizon_bars."""
    matches = [p for p in profiles if p.signature_id == signature_id]
    matches.sort(key=lambda p: p.horizon_bars)
    return [(p.horizon_bars, p.absolute_outcome.mean, p.relative_outcome.mean) for p in matches]
