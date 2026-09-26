"""Spec #004 SS38-40 -- building the compact EvidencePacket handed to a
human or AI agent for hypothesis proposal.

Pure transformation from three already-materialized #003 artifacts
(`EvaluationSignatureDefinition` + a list of `EvidenceProfile` -- one per
horizon, for the SAME signature -- + `EvaluationRunRegistry`). Imports
ONLY `evaluation.models.entities` (plain frozen dataclasses, zero PIT/DB
access, per Radu's SS110-F confirmation) -- never `evaluation.engine`,
`discovery.engine`, or anything under `data_foundation/`. TEST 36 in
tests/spec004 is an AST import scan that enforces this for the whole
`src/hypothesis/` package, not just this module.

PATCH #004-A finding #3 (GPT Review #004 Round 1): the original version
only checked that every profile's `signature_id` matched the supplied
signature -- it silently accepted a signature/profiles/run_registry
combination that "looked compatible" without actually verifying
provenance agreement (timeframe, Discovery engine/config versions,
which horizons were tested, whether every profile came from the SAME
evaluation_mode). `build_evidence_packet()` now hard-fails on any
mismatch, matching the same discipline Spec #003 uses for its own
provenance guards, instead of quietly building an internally
contradictory packet.

PATCH #004-A finding #4: `primary_horizon_bars` is no longer a free
parameter a caller passes per call -- it is READ from `hypothesis_config`
(`evidence_reference.reference_horizon_bars`), a policy value fixed
before any evidence exists and applied identically to every signature.
"""
from __future__ import annotations

from evaluation.models.entities import EvaluationRunRegistry, EvaluationSignatureDefinition, EvidenceProfile

from hypothesis.config.loader import HypothesisConfig
from hypothesis.models.entities import DecayPoint, EvidencePacket, EvidenceProvenance


def _entry_conditions_summary(sig: EvaluationSignatureDefinition) -> tuple[str, ...]:
    lane_part = tuple(f"{c.lane}={c.label}" for c in sig.lane_conditions)
    reason_part = tuple(f"reason_code={c.reason_code}" for c in sig.reason_code_conditions)
    return lane_part + reason_part


def _missingness_ratio(profile: EvidenceProfile) -> float | None:
    m = profile.missingness
    if not m.episodes:
        return None
    non_valid = m.insufficient_future_data + m.crosses_locked_oos + m.missing_benchmark + m.invalid_input
    return non_valid / m.episodes


def build_evidence_packet(
    signature: EvaluationSignatureDefinition,
    profiles: list[EvidenceProfile],
    run_registry: EvaluationRunRegistry,
    hypothesis_config: HypothesisConfig,
) -> EvidencePacket:
    """`profiles` must be every EvidenceProfile for THIS signature across
    every horizon `run_registry` actually tested (so the decay curve is
    complete, SS39, and matches the run's own accounting exactly -- TEST
    57) -- never a single horizon in isolation, and never a set that
    silently drops or duplicates a horizon."""
    if not profiles:
        raise ValueError("build_evidence_packet() requires at least one EvidenceProfile")

    signature_ids = {p.signature_id for p in profiles}
    if signature_ids != {signature.signature_id}:
        raise ValueError(
            f"all profiles must belong to signature_id={signature.signature_id!r}, got {signature_ids!r}"
        )

    if signature.timeframe != run_registry.timeframe:
        raise ValueError(
            f"signature.timeframe={signature.timeframe!r} does not match run_registry.timeframe="
            f"{run_registry.timeframe!r} -- cross-artifact provenance mismatch (PATCH #004-A finding #3)"
        )
    mismatched_profile_timeframes = {p.timeframe for p in profiles} - {run_registry.timeframe}
    if mismatched_profile_timeframes:
        raise ValueError(
            f"profile(s) with timeframe(s) {sorted(mismatched_profile_timeframes)!r} do not match "
            f"run_registry.timeframe={run_registry.timeframe!r}"
        )

    if signature.discovery_engine_version != run_registry.discovery_engine_version:
        raise ValueError(
            f"signature.discovery_engine_version={signature.discovery_engine_version!r} does not match "
            f"run_registry.discovery_engine_version={run_registry.discovery_engine_version!r}"
        )
    if signature.discovery_config_version != run_registry.discovery_config_version:
        raise ValueError(
            f"signature.discovery_config_version={signature.discovery_config_version!r} does not match "
            f"run_registry.discovery_config_version={run_registry.discovery_config_version!r}"
        )

    horizon_list = [p.horizon_bars for p in profiles]
    if len(horizon_list) != len(set(horizon_list)):
        raise ValueError(f"duplicate horizon_bars among profiles: {horizon_list!r}")
    profile_horizons = set(horizon_list)
    run_horizons = set(run_registry.horizons)
    if profile_horizons != run_horizons:
        raise ValueError(
            f"profiles cover horizons {sorted(profile_horizons)!r}, but run_registry.horizons="
            f"{sorted(run_horizons)!r} -- every horizon the run actually tested must be present, "
            f"and none extra (PATCH #004-A finding #3)"
        )

    evaluation_modes = {p.evaluation_mode for p in profiles}
    if len(evaluation_modes) != 1:
        raise ValueError(f"profiles mix evaluation_mode values {sorted(evaluation_modes)!r} -- must all agree")
    if next(iter(evaluation_modes)) != run_registry.mode:
        raise ValueError(
            f"profiles' evaluation_mode={next(iter(evaluation_modes))!r} does not match "
            f"run_registry.mode={run_registry.mode!r}"
        )

    reference_horizon_bars = hypothesis_config.data["evidence_reference"]["reference_horizon_bars"]
    primary = next((p for p in profiles if p.horizon_bars == reference_horizon_bars), None)
    if primary is None:
        raise ValueError(
            f"the configured evidence_reference.reference_horizon_bars={reference_horizon_bars!r} "
            f"has no matching EvidenceProfile among horizons {sorted(profile_horizons)!r} for signature "
            f"{signature.signature_id!r} -- the reference horizon is a fixed policy value and is never "
            f"substituted for a different one"
        )

    decay_curve = tuple(
        DecayPoint(
            evidence_horizon_bars=p.horizon_bars,
            mean_relative_return=p.relative_outcome.mean,
            median_relative_return=p.relative_outcome.median,
            valid_episode_n=p.support.valid_episode_n,
            adjusted_p=p.baseline_comparison.adjusted_p,
        )
        for p in sorted(profiles, key=lambda p: p.horizon_bars)
    )

    evidence_provenance = EvidenceProvenance(
        evaluation_run_id=run_registry.evaluation_run_id,
        evaluation_engine_version=run_registry.evaluation_engine_version,
        evaluation_config_version=run_registry.evaluation_config_version,
        signature_id=signature.signature_id,
        signature_set_id=run_registry.signature_set_id,
        discovery_engine_version=run_registry.discovery_engine_version,
        discovery_config_version=run_registry.discovery_config_version,
        timeframe=run_registry.timeframe,
    )

    return EvidencePacket(
        signature_id=signature.signature_id,
        entry_conditions_summary=_entry_conditions_summary(signature),
        timeframe=signature.timeframe,
        evidence_provenance=evidence_provenance,
        decay_curve=decay_curve,
        primary_evidence_horizon_bars=primary.horizon_bars,
        primary_support_status=primary.support.support_status,
        primary_valid_episode_n=primary.support.valid_episode_n,
        primary_unique_security_count=primary.concentration.unique_security_count,
        primary_largest_security_share=primary.concentration.largest_security_share_of_episodes,
        primary_episodes_per_20_sessions=primary.opportunity_density.episodes_per_20_sessions,
        primary_episodes_per_60_sessions=primary.opportunity_density.episodes_per_60_sessions,
        primary_absolute_mean=primary.absolute_outcome.mean,
        primary_relative_mean=primary.relative_outcome.mean,
        primary_relative_median=primary.relative_outcome.median,
        primary_baseline_median=primary.baseline_comparison.baseline_median,
        primary_standardized_effect=primary.baseline_comparison.standardized_effect,
        primary_adjusted_p=primary.baseline_comparison.adjusted_p,
        primary_missingness_ratio=_missingness_ratio(primary),
        primary_has_stability_bins=len(primary.stability) > 0,
        warnings=primary.warnings,
    )
