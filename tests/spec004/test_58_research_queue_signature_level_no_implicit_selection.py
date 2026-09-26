"""TEST 58 -- the Research Queue is signature-level: ONE
`ResearchQueueEntry` per signature regardless of how many horizons its
decay curve covers, and priority is computed from the SAME
policy-fixed reference horizon for every signature -- never from
whichever horizon happens to look best (PATCH #004-A finding #4, GPT
Review #004 Round 1). The original per-(signature, horizon) design let
the same signature occupy up to 5 queue slots, an implicit backdoor form
of exactly the best-horizon selection Spec #004 exists to forbid."""
import dataclasses

import pytest

from hypothesis.evidence.queue import build_research_queue, compute_review_priority


def test_one_entry_per_signature_regardless_of_decay_curve_length(evidence_packet, hypothesis_config):
    entries = build_research_queue([evidence_packet], hypothesis_config)
    assert len(entries) == 1
    assert len(evidence_packet.decay_curve) == 5  # the full curve still exists, just not one queue slot per horizon


def test_priority_uses_only_the_configured_reference_horizon_not_the_strongest_one(evidence_packet, hypothesis_config):
    # profiles_all_horizons's strongest horizon is 3 bars (see conftest),
    # but reference_horizon_bars is a fixed policy value (also 3, by
    # coincidence of the default config) -- prove the priority key is
    # computed from `primary_*` fields, which are always the policy
    # horizon's own values, not a max/min search across the curve.
    key = compute_review_priority(evidence_packet)
    assert key == (evidence_packet.primary_adjusted_p, -abs(evidence_packet.primary_standardized_effect), -evidence_packet.primary_valid_episode_n)


def test_a_packet_not_built_at_the_configured_reference_horizon_is_rejected(evidence_packet, hypothesis_config):
    # Simulates a packet that was (incorrectly) built under a different
    # reference-horizon policy than the one build_research_queue() is
    # told to use -- must hard-fail, never silently compare apples to oranges.
    off_policy_packet = dataclasses.replace(evidence_packet, primary_evidence_horizon_bars=5)
    with pytest.raises(ValueError, match="reference_horizon_bars"):
        build_research_queue([off_policy_packet], hypothesis_config)


def test_multiple_signatures_each_get_exactly_one_entry(evidence_packet, hypothesis_config):
    other_packet = dataclasses.replace(evidence_packet, signature_id="OTHER_SIGNATURE")
    entries = build_research_queue([evidence_packet, other_packet], hypothesis_config)
    assert len(entries) == 2
    assert {e.signature_id for e in entries} == {evidence_packet.signature_id, "OTHER_SIGNATURE"}
