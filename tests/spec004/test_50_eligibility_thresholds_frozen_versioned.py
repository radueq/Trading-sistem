"""TEST 50 -- Research Queue eligibility thresholds are config-versioned
and produce identical results for identical inputs -- never silently
tuned after seeing which signatures pass/fail (Radu's SS110-H: "Nu vreau
sa le ajustam dupa ce vedem ce signatures dispar din queue")."""
from dataclasses import replace

from hypothesis.evidence.queue import build_research_queue


def test_same_profiles_and_config_reproduce_identical_eligibility(profiles_all_horizons, hypothesis_config):
    entries_1 = build_research_queue(profiles_all_horizons, "run_x", hypothesis_config)
    entries_2 = build_research_queue(profiles_all_horizons, "run_x", hypothesis_config)
    assert entries_1 == entries_2
    for e in entries_1:
        assert e.eligibility_config_version == hypothesis_config.config_version


def test_changing_the_eligibility_config_changes_its_version_and_can_change_results(profiles_all_horizons, hypothesis_config):
    tightened_data = dict(hypothesis_config.data)
    tightened_data["research_queue_eligibility"] = dict(
        tightened_data["research_queue_eligibility"], minimum_valid_episode_n=10_000,
    )
    tightened_config = replace(hypothesis_config, data=tightened_data, config_version="cfg_tightened_test")

    loose_entries = build_research_queue(profiles_all_horizons, "run_x", hypothesis_config)
    tight_entries = build_research_queue(profiles_all_horizons, "run_x", tightened_config)

    assert any(e.eligible for e in loose_entries)
    assert not any(e.eligible for e in tight_entries)
    assert tight_entries[0].eligibility_config_version == "cfg_tightened_test"
