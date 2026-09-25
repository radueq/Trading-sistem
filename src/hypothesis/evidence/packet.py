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
"""
from __future__ import annotations

from evaluation.models.entities import EvaluationRunRegistry, EvaluationSignatureDefinition, EvidenceProfile

from hypothesis.models.entities import DecayPoint, EvidencePacket, EvidenceProvenance


def _entry_conditions_summary(sig: EvaluationSignatureDefinition) -> tuple[str, ...]:
    lane_part = tuple(f"{c.lane}={c.label}" for c in sig.lane_conditions)
    reason_part = tuple(f"reason_code={c.reason_code}" for c in sig.reason_code_conditions)
    return lane_part + reason_part


def build_evidence_packet(
    signature: EvaluationSignatureDefinition,
    profiles: list[EvidenceProfile],
    run_registry: EvaluationRunRegistry,
    primary_horizon_bars: int,
) -> EvidencePacket:
    """`profiles` must be every EvidenceProfile for THIS signature across
    all horizons tested in one run (so the decay curve is complete, SS39)
    -- never a single horizon in isolation, which would silently hide the
    rest of the decay curve from the reviewer (SS18-20/TEST 12)."""
    if not profiles:
        raise ValueError("build_evidence_packet() requires at least one EvidenceProfile")
    signature_ids = {p.signature_id for p in profiles}
    if signature_ids != {signature.signature_id}:
        raise ValueError(
            f"all profiles must belong to signature_id={signature.signature_id!r}, got {signature_ids!r}"
        )

    primary = next((p for p in profiles if p.horizon_bars == primary_horizon_bars), None)
    if primary is None:
        raise ValueError(
            f"primary_horizon_bars={primary_horizon_bars!r} has no matching EvidenceProfile "
            f"among horizons {sorted(p.horizon_bars for p in profiles)!r}"
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
        warnings=primary.warnings,
    )
