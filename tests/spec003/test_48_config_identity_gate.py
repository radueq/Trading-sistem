"""TEST 48 -- the Stage 3 config identity mechanism wired into
`run_evaluation()` (decision registry, Stage 3; authorized
2026-10-07; CORRECTED round 2 -- GPT changes-required verdict on
commit `8650f17`), verified through the REAL engine -- registers/
verifies BOTH `discovery_config` and `evaluation_config`, and consumes
exclusively the frozen result (including indirectly, through
`_collect_observations()`'s own Discovery calls, which now share the
SAME registry).

Verification is MANDATORY BY DEFAULT (finding #1) -- `config_registry`
is optional only for SHARING one verified baseline across multiple
calls; omitting it still verifies locally. Every pre-Stage-3 test in
this package (TEST 1-47) remains unaffected ONLY because
`reduced_discovery_config`/`fast_evaluation_config` are now genuinely
loader-sourced (`tests/fixtures/config_overrides.py`) -- their content
deliberately differs from the real on-disk YAML, but their
`config_version` genuinely, differently corresponds to that content.
"""
from dataclasses import replace

import pytest

from config_identity.registry import ConfigIdentityError, ConfigRegistry
from evaluation.engine import run_evaluation
from evaluation.models.entities import EvaluationSignatureDefinition, LaneStateCondition
from evaluation.registry.signatures import freeze_signature_set

from spec003.fixtures.tiny_universe import DATES


def _sigset(reduced_discovery_config):
    sig = EvaluationSignatureDefinition(
        signature_id="VOLATILITY_COMPRESSION", lane_conditions=(LaneStateCondition("volatility", "COMPRESSION"),),
        reason_code_conditions=(), timeframe="1D", discovery_engine_version="v1.0.0",
        discovery_config_version=reduced_discovery_config.config_version, creation_mode="PRE_REGISTERED",
        created_before_outcome_evaluation=True,
    )
    return freeze_signature_set([sig])


def test_run_evaluation_registers_then_reuses_the_same_config_registry(
    conn, tiny_universe, reduced_discovery_config, fast_evaluation_config, formal_calendar_registry, formal_calendar_id,
):
    config_registry = ConfigRegistry()
    sigset = _sigset(reduced_discovery_config)
    dev_start, dev_end = DATES[30], DATES[45]

    profiles_1, _ = run_evaluation(
        conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
        dev_start, dev_end, sigset, reduced_discovery_config, fast_evaluation_config,
        calendar_registry=formal_calendar_registry, calendar_id=formal_calendar_id, config_registry=config_registry,
    )
    profiles_2, _ = run_evaluation(
        conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
        dev_start, dev_end, sigset, reduced_discovery_config, fast_evaluation_config,
        calendar_registry=formal_calendar_registry, calendar_id=formal_calendar_id, config_registry=config_registry,
    )
    assert profiles_1 == profiles_2  # same configs, shared registry -- second call verifies and reuses


def test_run_evaluation_rejects_a_discovery_config_whose_content_changed_since_registration(
    conn, tiny_universe, reduced_discovery_config, fast_evaluation_config, formal_calendar_registry, formal_calendar_id,
):
    config_registry = ConfigRegistry()
    sigset = _sigset(reduced_discovery_config)
    dev_start, dev_end = DATES[30], DATES[45]

    run_evaluation(
        conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
        dev_start, dev_end, sigset, reduced_discovery_config, fast_evaluation_config,
        calendar_registry=formal_calendar_registry, calendar_id=formal_calendar_id, config_registry=config_registry,
    )  # registers

    tampered_discovery = replace(reduced_discovery_config, eligibility={**reduced_discovery_config.eligibility, "minimum_history_days": 999})
    assert tampered_discovery.config_version == reduced_discovery_config.config_version  # content-only tamper
    with pytest.raises(ConfigIdentityError, match="does not structurally match"):
        run_evaluation(
            conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
            dev_start, dev_end, sigset, tampered_discovery, fast_evaluation_config,
            calendar_registry=formal_calendar_registry, calendar_id=formal_calendar_id, config_registry=config_registry,
        )


def test_run_evaluation_rejects_an_evaluation_config_whose_label_disagrees_with_its_own_content(
    conn, tiny_universe, reduced_discovery_config, fast_evaluation_config, formal_calendar_registry, formal_calendar_id,
):
    config_registry = ConfigRegistry()
    sigset = _sigset(reduced_discovery_config)
    dev_start, dev_end = DATES[30], DATES[45]

    run_evaluation(
        conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
        dev_start, dev_end, sigset, reduced_discovery_config, fast_evaluation_config,
        calendar_registry=formal_calendar_registry, calendar_id=formal_calendar_id, config_registry=config_registry,
    )  # registers

    mislabeled_evaluation = replace(fast_evaluation_config, config_version="cfg_DISHONEST_LABEL")
    with pytest.raises(ConfigIdentityError, match="does not match the"):
        run_evaluation(
            conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
            dev_start, dev_end, sigset, reduced_discovery_config, mislabeled_evaluation,
            calendar_registry=formal_calendar_registry, calendar_id=formal_calendar_id, config_registry=config_registry,
        )


def test_genuinely_loader_sourced_alternative_configs_keep_working_without_any_config_registry(
    conn, tiny_universe, reduced_discovery_config, fast_evaluation_config, formal_calendar_registry, formal_calendar_id,
):
    """No config_registry supplied -- reduced_discovery_config/
    fast_evaluation_config, which deliberately differ from the real
    on-disk YAML, keep working exactly as every other test in
    tests/spec003/ relies on, PRECISELY BECAUSE they are genuinely
    loader-sourced (their config_version really, differently
    corresponds to their own content) -- never because verification
    is skipped."""
    sigset = _sigset(reduced_discovery_config)
    dev_start, dev_end = DATES[30], DATES[45]

    run_evaluation(
        conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
        dev_start, dev_end, sigset, reduced_discovery_config, fast_evaluation_config,
        calendar_registry=formal_calendar_registry, calendar_id=formal_calendar_id,
    )


def test_a_tampered_discovery_config_is_rejected_on_the_very_first_call_with_a_brand_new_registry(
    conn, tiny_universe, reduced_discovery_config, fast_evaluation_config, formal_calendar_registry, formal_calendar_id,
):
    """Finding #2: the FIRST registration for a domain must never trust
    whatever the caller's object merely claims -- even a brand-new
    `ConfigRegistry()` must reject it."""
    sigset = _sigset(reduced_discovery_config)
    dev_start, dev_end = DATES[30], DATES[45]
    tampered_discovery = replace(reduced_discovery_config, eligibility={**reduced_discovery_config.eligibility, "minimum_history_days": 999})
    assert tampered_discovery.config_version == reduced_discovery_config.config_version

    with pytest.raises(ConfigIdentityError, match="is not self-consistent"):
        run_evaluation(
            conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
            dev_start, dev_end, sigset, tampered_discovery, fast_evaluation_config,
            calendar_registry=formal_calendar_registry, calendar_id=formal_calendar_id, config_registry=ConfigRegistry(),
        )


def test_a_tampered_discovery_config_is_rejected_even_without_any_config_registry(
    conn, tiny_universe, reduced_discovery_config, fast_evaluation_config, formal_calendar_registry, formal_calendar_id,
):
    """Finding #1: protection is the DEFAULT -- this is the exact shape
    of tamper GPT reproduced through `build_research_queue()` (TEST
    75's own repro); `run_evaluation()` must refuse it identically,
    with no registry at all."""
    sigset = _sigset(reduced_discovery_config)
    dev_start, dev_end = DATES[30], DATES[45]
    tampered_discovery = replace(reduced_discovery_config, eligibility={**reduced_discovery_config.eligibility, "minimum_history_days": 999})

    with pytest.raises(ConfigIdentityError, match="is not self-consistent"):
        run_evaluation(
            conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
            dev_start, dev_end, sigset, tampered_discovery, fast_evaluation_config,
            calendar_registry=formal_calendar_registry, calendar_id=formal_calendar_id,
        )
