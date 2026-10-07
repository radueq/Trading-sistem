"""TEST 48 -- the Stage 3 config identity mechanism wired into
`run_evaluation()` (decision registry, Stage 3; authorized
2026-10-07), verified through the REAL engine -- registers/verifies
BOTH `discovery_config` and `evaluation_config` into the SAME shared
`ConfigRegistry`, and consumes exclusively the frozen result (including
indirectly, through `_collect_observations()`'s own Discovery calls).

`config_registry` is optional, default `None` -- every pre-Stage-3
test in this package (TEST 1-47) is completely unaffected, including
`reduced_discovery_config`/`fast_evaluation_config`, which deliberately
differ from the real on-disk YAML content.
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


def test_default_config_registry_none_leaves_existing_behavior_unchanged(
    conn, tiny_universe, reduced_discovery_config, fast_evaluation_config, formal_calendar_registry, formal_calendar_id,
):
    """No config_registry supplied -- reduced_discovery_config/
    fast_evaluation_config, which deliberately differ from the real
    on-disk YAML, must keep working exactly as every other test in
    tests/spec003/ relies on."""
    sigset = _sigset(reduced_discovery_config)
    dev_start, dev_end = DATES[30], DATES[45]

    run_evaluation(
        conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
        dev_start, dev_end, sigset, reduced_discovery_config, fast_evaluation_config,
        calendar_registry=formal_calendar_registry, calendar_id=formal_calendar_id,
    )
