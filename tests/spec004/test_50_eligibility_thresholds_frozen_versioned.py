"""TEST 50 -- Research Queue eligibility thresholds are config-versioned
and produce identical results for identical inputs -- never silently
tuned after seeing which signatures pass/fail (Radu's SS110-H: "Nu vreau
sa le ajustam dupa ce vedem ce signatures dispar din queue")."""
from fixtures.config_overrides import hypothesis_config_with_overrides
from hypothesis.evidence.queue import build_research_queue


def test_same_profiles_and_config_reproduce_identical_eligibility(evidence_packet, hypothesis_config):
    entries_1 = build_research_queue([evidence_packet], hypothesis_config)
    entries_2 = build_research_queue([evidence_packet], hypothesis_config)
    assert entries_1 == entries_2
    for e in entries_1:
        assert e.eligibility_config_version == hypothesis_config.config_version


def test_changing_the_eligibility_config_changes_its_version_and_can_change_results(evidence_packet, hypothesis_config):
    # Stage 3 (config identity infrastructure, authorized 2026-10-07,
    # CORRECTED round 2) requires this deliberately-different config to
    # be genuinely loader-sourced -- see tests/fixtures/config_overrides.py.
    tightened_config = hypothesis_config_with_overrides(
        research_queue_eligibility={
            **hypothesis_config.data["research_queue_eligibility"], "minimum_valid_episode_n": 10_000,
        },
    )
    assert tightened_config.config_version != hypothesis_config.config_version  # sanity: genuinely different

    loose_entries = build_research_queue([evidence_packet], hypothesis_config)
    tight_entries = build_research_queue([evidence_packet], tightened_config)

    assert any(e.eligible for e in loose_entries)
    assert not any(e.eligible for e in tight_entries)
    assert tight_entries[0].eligibility_config_version == tightened_config.config_version
