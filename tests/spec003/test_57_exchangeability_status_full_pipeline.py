"""TEST 57 -- `exchangeability_status`, full real pipeline (joint
remediation design 003+004 section 5-6; decision registry A4, Stage 4).

The FULL integration regression required by the implementation plan's
own Stage 4 acceptance criteria: a real `run_evaluation()` ->
`build_evidence_packet()` -> `compute_review_priority()` chain, never a
hand-built packet -- proving `exchangeability_status` is hard-coded
`"UNVERIFIED"` by the real engine, propagates through `DecayPoint` (per
profile) and `EvidencePacket.primary_exchangeability_status`, and that
`p_key` stays `float("inf")` regardless.
"""
from evaluation.engine import run_evaluation
from evaluation.models.entities import EvaluationSignatureDefinition, LaneStateCondition
from evaluation.registry.signatures import freeze_signature_set
from hypothesis.config.loader import load_config as load_hypothesis_config
from hypothesis.evidence.packet import build_evidence_packet
from hypothesis.evidence.queue import compute_review_priority

from spec003.conftest import COMPRESSION_WINDOW_END, COMPRESSION_WINDOW_START


def test_real_pipeline_exchangeability_status_is_unverified_and_p_key_stays_inf(
    conn, tiny_universe, reduced_discovery_config, fast_evaluation_config, formal_calendar_registry, formal_calendar_id,
):
    sig = EvaluationSignatureDefinition(
        signature_id="VOLATILITY_COMPRESSION", lane_conditions=(LaneStateCondition("volatility", "COMPRESSION"),),
        reason_code_conditions=(), timeframe="1D", discovery_engine_version="v1.0.0",
        discovery_config_version=reduced_discovery_config.config_version, creation_mode="PRE_REGISTERED",
        created_before_outcome_evaluation=True,
    )
    sigset = freeze_signature_set([sig])
    profiles, registry = run_evaluation(
        conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
        COMPRESSION_WINDOW_START, COMPRESSION_WINDOW_END, sigset, reduced_discovery_config, fast_evaluation_config,
        calendar_registry=formal_calendar_registry, calendar_id=formal_calendar_id,
    )
    assert profiles, "sanity: need real profiles to run this chain at all"
    for p in profiles:
        assert p.baseline_comparison.exchangeability_status == "UNVERIFIED"

    packet = build_evidence_packet(sig, profiles, registry, load_hypothesis_config())
    assert packet.primary_exchangeability_status == "UNVERIFIED"
    assert len(packet.decay_curve) == len(profiles)
    for point in packet.decay_curve:
        assert point.exchangeability_status == "UNVERIFIED"

    key = compute_review_priority(packet)
    assert key[0] == float("inf")
    # Sanity: this real run actually produces at least one non-None
    # adjusted_p somewhere -- so p_key == inf above is a genuine
    # override, not a vacuous check against an all-None run.
    assert any(p.baseline_comparison.adjusted_p is not None for p in profiles)
