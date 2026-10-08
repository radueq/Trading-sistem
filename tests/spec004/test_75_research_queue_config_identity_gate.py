"""TEST 75 -- the Stage 3 config identity mechanism wired into
`build_research_queue()` (decision registry, Stage 3; authorized
2026-10-07; CORRECTED round 2 -- GPT changes-required verdict on
commit `8650f17`, reproduced through exactly this function: a
content-only tamper under the SAME config_version silently changed
eligibility results when `config_registry` was omitted), verified
through the REAL function.

Verification is now MANDATORY BY DEFAULT -- `config_registry` is
optional only for SHARING one verified baseline across multiple
calls; omitting it still verifies locally, every call. TEST 50's own
`test_changing_the_eligibility_config_changes_its_version_and_can_
change_results` remains unaffected ONLY because its `tightened_config`
is now genuinely loader-sourced (`tests/fixtures/config_overrides.py`)
-- never because verification is skipped.
"""
import dataclasses

import pytest

from config_identity.registry import ConfigIdentityError, ConfigRegistry
from fixtures.config_overrides import hypothesis_config_with_overrides
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


def test_genuinely_loader_sourced_alternative_config_keeps_working_without_any_config_registry(evidence_packet, hypothesis_config):
    """Mirrors TEST 50's own scenario exactly: a deliberately
    different config, with NO config_registry supplied -- keeps
    working, PRECISELY BECAUSE it is genuinely loader-sourced (see
    tests/fixtures/config_overrides.py), never because verification
    is skipped."""
    tightened_config = hypothesis_config_with_overrides(
        research_queue_eligibility={
            **hypothesis_config.data["research_queue_eligibility"], "minimum_valid_episode_n": 10_000,
        },
    )
    entries = build_research_queue([evidence_packet], tightened_config)  # no config_registry
    assert entries[0].eligibility_config_version == tightened_config.config_version


def test_a_tampered_config_is_rejected_on_the_very_first_call_with_a_brand_new_registry(evidence_packet, hypothesis_config):
    """Finding #2: the FIRST registration for a domain must never
    trust whatever the caller's object merely claims -- even a
    brand-new `ConfigRegistry()`, with nothing registered yet, must
    reject a content-only tamper."""
    tampered_data = dict(hypothesis_config.data)
    tampered_data["research_queue_eligibility"] = dict(
        tampered_data["research_queue_eligibility"], minimum_valid_episode_n=10_000,
    )
    tampered = dataclasses.replace(hypothesis_config, data=tampered_data)  # SAME config_version -- content-only tamper
    assert tampered.config_version == hypothesis_config.config_version

    with pytest.raises(ConfigIdentityError, match="is not self-consistent"):
        build_research_queue([evidence_packet], tampered, config_registry=ConfigRegistry())


def test_a_tampered_config_is_rejected_even_without_any_config_registry(evidence_packet, hypothesis_config):
    """Finding #1: protection is the DEFAULT -- this is the EXACT
    tamper GPT reproduced through this real function (same
    config_version, different minimum_valid_episode_n) silently
    changing eligibility results when `config_registry` was omitted.
    Must now be rejected with no registry at all."""
    tampered_data = dict(hypothesis_config.data)
    tampered_data["research_queue_eligibility"] = dict(
        tampered_data["research_queue_eligibility"], minimum_valid_episode_n=10_000,
    )
    tampered = dataclasses.replace(hypothesis_config, data=tampered_data)

    with pytest.raises(ConfigIdentityError, match="is not self-consistent"):
        build_research_queue([evidence_packet], tampered)  # no config_registry -- still verified, still rejected
