"""TEST 75 -- the Stage 3 config identity mechanism wired into
`build_research_queue()` (decision registry, Stage 3; authorized
2026-10-07), verified through the REAL function.

`config_registry` is optional, default `None` -- TEST 50's own
`test_changing_the_eligibility_config_changes_its_version_and_can_
change_results` (a deliberately different, but internally self-
consistent, config) is unaffected: it never supplies `config_registry`,
so nothing there is verified against anything.
"""
import dataclasses

import pytest

from config_identity.registry import ConfigIdentityError, ConfigRegistry
from hypothesis.evidence.queue import build_research_queue


def test_build_research_queue_registers_then_reuses_the_same_config_registry(evidence_packet, hypothesis_config):
    config_registry = ConfigRegistry()
    entries_1 = build_research_queue([evidence_packet], hypothesis_config, config_registry=config_registry)
    entries_2 = build_research_queue([evidence_packet], hypothesis_config, config_registry=config_registry)
    assert entries_1 == entries_2


def test_build_research_queue_rejects_a_config_whose_content_changed_since_registration(evidence_packet, hypothesis_config):
    config_registry = ConfigRegistry()
    build_research_queue([evidence_packet], hypothesis_config, config_registry=config_registry)  # registers

    tampered_data = dict(hypothesis_config.data)
    tampered_data["research_queue_eligibility"] = dict(
        tampered_data["research_queue_eligibility"], minimum_valid_episode_n=10_000,
    )
    tampered = dataclasses.replace(hypothesis_config, data=tampered_data)  # SAME config_version -- content-only tamper
    assert tampered.config_version == hypothesis_config.config_version

    with pytest.raises(ConfigIdentityError, match="does not structurally match"):
        build_research_queue([evidence_packet], tampered, config_registry=config_registry)


def test_build_research_queue_rejects_a_config_whose_label_disagrees_with_its_own_content(evidence_packet, hypothesis_config):
    config_registry = ConfigRegistry()
    build_research_queue([evidence_packet], hypothesis_config, config_registry=config_registry)  # registers

    mislabeled = dataclasses.replace(hypothesis_config, config_version="cfg_DISHONEST_LABEL")
    with pytest.raises(ConfigIdentityError, match="does not match the"):
        build_research_queue([evidence_packet], mislabeled, config_registry=config_registry)


def test_default_config_registry_none_leaves_test_50_unaffected(evidence_packet, hypothesis_config):
    """Mirrors TEST 50's own scenario exactly: a deliberately
    different, self-consistent config, with NO config_registry
    supplied -- must keep working, never rejected."""
    tightened_data = dict(hypothesis_config.data)
    tightened_data["research_queue_eligibility"] = dict(
        tightened_data["research_queue_eligibility"], minimum_valid_episode_n=10_000,
    )
    tightened_config = dataclasses.replace(hypothesis_config, data=tightened_data, config_version="cfg_tightened_test")

    entries = build_research_queue([evidence_packet], tightened_config)  # no config_registry
    assert entries[0].eligibility_config_version == "cfg_tightened_test"
