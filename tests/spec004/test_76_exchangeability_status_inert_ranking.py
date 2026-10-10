"""TEST 76 -- `exchangeability_status` is UNCONDITIONALLY inert in V1
ranking (joint remediation design 003+004 section 5-6; decision
registry A4, Stage 4; GPT's own decision: a "no constructor argument"
structural check does not prove authenticity, and was REJECTED).

`evidence/queue.py`'s `compute_review_priority()` sets `p_key =
float("inf")` UNCONDITIONALLY for V1 -- it does not read or branch on
`exchangeability_status` AT ALL, so no value that field could ever
hold (including one artificially injected via `dataclasses.replace()`)
changes the ranking. BEHAVIORAL tests, replacing the rejected
structural-signature check: absent/`None`, an unknown string, and an
artificially-injected `"VERIFIED"` ALL leave `p_key = inf` and rank NO
HIGHER than `adjusted_p = None` would -- three cases, not one
structural scan.
"""
import dataclasses

from hypothesis.evidence.queue import compute_review_priority


def test_default_real_packet_is_unverified(evidence_packet):
    assert evidence_packet.primary_exchangeability_status == "UNVERIFIED"


def test_injected_verified_status_does_not_change_ranking(evidence_packet):
    baseline_key = compute_review_priority(evidence_packet)
    tampered = dataclasses.replace(evidence_packet, primary_exchangeability_status="VERIFIED")
    tampered_key = compute_review_priority(tampered)
    assert tampered_key == baseline_key
    assert tampered_key[0] == float("inf")


def test_unknown_status_string_does_not_change_ranking(evidence_packet):
    baseline_key = compute_review_priority(evidence_packet)
    tampered = dataclasses.replace(evidence_packet, primary_exchangeability_status="GARBAGE_NOT_A_REAL_STATUS")
    tampered_key = compute_review_priority(tampered)
    assert tampered_key == baseline_key
    assert tampered_key[0] == float("inf")


def test_absent_none_status_does_not_change_ranking(evidence_packet):
    baseline_key = compute_review_priority(evidence_packet)
    tampered = dataclasses.replace(evidence_packet, primary_exchangeability_status=None)
    tampered_key = compute_review_priority(tampered)
    assert tampered_key == baseline_key
    assert tampered_key[0] == float("inf")


def test_p_key_never_ranks_higher_than_adjusted_p_none_would(evidence_packet):
    # Even a packet with a real, favorable primary_adjusted_p (e.g.
    # 0.03, the "3 bars" horizon in profiles_all_horizons) must rank
    # p_key IDENTICALLY to a packet whose primary_adjusted_p is None --
    # proving raw/adjusted significance never drives ranking in V1,
    # with or without an injected exchangeability_status.
    assert evidence_packet.primary_adjusted_p is not None  # sanity: this packet has a REAL adjusted_p
    key_with_real_p = compute_review_priority(evidence_packet)

    none_p_packet = dataclasses.replace(
        evidence_packet, primary_adjusted_p=None, primary_exchangeability_status="VERIFIED",
    )
    key_with_none_p = compute_review_priority(none_p_packet)
    assert key_with_real_p[0] == key_with_none_p[0] == float("inf")


def test_decay_curve_points_carry_exchangeability_status_as_metadata_only(evidence_packet):
    # DecayPoint.exchangeability_status is explanatory metadata ONLY --
    # never consumed by anything that selects/ranks across the curve
    # (decay_curve() in engine.py just reports it, per Spec #003 SS52-53).
    assert len(evidence_packet.decay_curve) == 5
    for point in evidence_packet.decay_curve:
        assert point.exchangeability_status == "UNVERIFIED"
