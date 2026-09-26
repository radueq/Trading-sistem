"""TEST 57 -- `build_evidence_packet()` hard-fails on cross-artifact
provenance mismatches instead of quietly building an internally
contradictory packet (PATCH #004-A finding #3, GPT Review #004 Round 1).
The original version only checked that every profile's `signature_id`
matched -- never timeframe, Discovery engine/config versions, which
horizons were actually tested, or whether every profile shared one
evaluation_mode."""
import dataclasses

import pytest

from hypothesis.evidence.packet import build_evidence_packet

from spec004.conftest import make_evidence_profile


def test_signature_timeframe_mismatch_is_rejected(signature_definition, profiles_all_horizons, run_registry, hypothesis_config):
    mismatched_signature = dataclasses.replace(signature_definition, timeframe="4H")
    with pytest.raises(ValueError, match="timeframe"):
        build_evidence_packet(mismatched_signature, profiles_all_horizons, run_registry, hypothesis_config)


def test_discovery_engine_version_mismatch_is_rejected(signature_definition, profiles_all_horizons, run_registry, hypothesis_config):
    mismatched_signature = dataclasses.replace(signature_definition, discovery_engine_version="v0.0.1-stale")
    with pytest.raises(ValueError, match="discovery_engine_version"):
        build_evidence_packet(mismatched_signature, profiles_all_horizons, run_registry, hypothesis_config)


def test_duplicate_horizon_among_profiles_is_rejected(signature_definition, profiles_all_horizons, run_registry, hypothesis_config):
    duplicated = profiles_all_horizons + [profiles_all_horizons[0]]
    with pytest.raises(ValueError, match="duplicate horizon_bars"):
        build_evidence_packet(signature_definition, duplicated, run_registry, hypothesis_config)


def test_profiles_missing_a_horizon_the_run_actually_tested_is_rejected(signature_definition, profiles_all_horizons, run_registry, hypothesis_config):
    incomplete = [p for p in profiles_all_horizons if p.horizon_bars != 10]  # run_registry.horizons still includes 10
    with pytest.raises(ValueError, match="run_registry.horizons"):
        build_evidence_packet(signature_definition, incomplete, run_registry, hypothesis_config)


def test_profiles_with_an_extra_horizon_the_run_never_tested_is_rejected(signature_definition, profiles_all_horizons, run_registry, hypothesis_config):
    extra = profiles_all_horizons + [make_evidence_profile(20)]  # 20 not in run_registry.horizons
    with pytest.raises(ValueError, match="run_registry.horizons"):
        build_evidence_packet(signature_definition, extra, run_registry, hypothesis_config)


def test_mixed_evaluation_mode_across_profiles_is_rejected(signature_definition, profiles_all_horizons, run_registry, hypothesis_config):
    mixed = list(profiles_all_horizons)
    mixed[0] = dataclasses.replace(mixed[0], evaluation_mode="EXPLORATORY")
    with pytest.raises(ValueError, match="evaluation_mode"):
        build_evidence_packet(signature_definition, mixed, run_registry, hypothesis_config)


def test_consistent_artifacts_build_successfully(signature_definition, profiles_all_horizons, run_registry, hypothesis_config):
    packet = build_evidence_packet(signature_definition, profiles_all_horizons, run_registry, hypothesis_config)
    assert packet.timeframe == run_registry.timeframe
    assert packet.primary_evidence_horizon_bars == hypothesis_config.data["evidence_reference"]["reference_horizon_bars"]
