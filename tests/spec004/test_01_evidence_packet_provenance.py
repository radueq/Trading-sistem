"""TEST 1 -- EvidencePacket carries full provenance (Spec #004 SS33/SS39)."""
from hypothesis.evidence.packet import build_evidence_packet


def test_evidence_packet_carries_full_provenance(signature_definition, profiles_all_horizons, run_registry):
    packet = build_evidence_packet(signature_definition, profiles_all_horizons, run_registry, primary_horizon_bars=3)
    ep = packet.evidence_provenance
    assert ep.evaluation_run_id == run_registry.evaluation_run_id
    assert ep.evaluation_engine_version == run_registry.evaluation_engine_version
    assert ep.evaluation_config_version == run_registry.evaluation_config_version
    assert ep.discovery_engine_version == run_registry.discovery_engine_version
    assert ep.discovery_config_version == run_registry.discovery_config_version
    assert ep.signature_id == signature_definition.signature_id
    assert ep.signature_set_id == run_registry.signature_set_id
    assert ep.timeframe == signature_definition.timeframe
