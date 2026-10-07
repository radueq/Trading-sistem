"""TEST 25 -- the Stage 3 config identity mechanism wired into
`run_discovery()`/`compute_discovery_observations()` (decision
registry, Stage 3; authorized 2026-10-07), verified through the REAL
engine, not only the shared helper in isolation (see
tests/config_identity/test_01_registered_config_version.py for that).

`config_registry` is optional, default `None` -- every test file in
this package that omits it (TEST 1-24) is completely unaffected.
"""
from dataclasses import replace

import pytest

from config_identity.registry import ConfigIdentityError, ConfigRegistry
from discovery.config.loader import load_config
from discovery.engine import compute_discovery_observations, run_discovery
from spec002.fixtures.synthetic_universe import AS_OF


def test_run_discovery_registers_then_reuses_the_same_config_registry(conn, universe):
    config = load_config()
    sids = universe["non_benchmark_ids"]
    bench = universe["benchmark_security_id"]
    config_registry = ConfigRegistry()

    run1 = run_discovery(conn, sids, AS_OF, bench, config, config_registry=config_registry)
    run2 = run_discovery(conn, sids, AS_OF, bench, config, config_registry=config_registry)
    assert run1 == run2  # identical config, shared registry -- second call verifies and reuses


def test_compute_discovery_observations_registers_then_reuses_the_same_config_registry(conn, universe):
    config = load_config()
    sids = universe["non_benchmark_ids"]
    bench = universe["benchmark_security_id"]
    config_registry = ConfigRegistry()

    obs1 = compute_discovery_observations(conn, sids, AS_OF, bench, config, config_registry=config_registry)
    obs2 = compute_discovery_observations(conn, sids, AS_OF, bench, config, config_registry=config_registry)
    assert obs1 == obs2


def test_run_discovery_rejects_a_config_whose_content_changed_since_registration(conn, universe):
    """Correct label, wrong content -- the SAME config_version string,
    but eligibility thresholds mutated after the first (registering)
    call. Rejected by the structural check specifically, BEFORE any
    PIT/Discovery computation for the second call."""
    config = load_config()
    sids = universe["non_benchmark_ids"]
    bench = universe["benchmark_security_id"]
    config_registry = ConfigRegistry()

    run_discovery(conn, sids, AS_OF, bench, config, config_registry=config_registry)  # registers

    tampered = replace(config, eligibility={**config.eligibility, "minimum_history_days": 999})
    assert tampered.config_version == config.config_version  # label unchanged -- content-only tamper
    with pytest.raises(ConfigIdentityError, match="does not structurally match"):
        run_discovery(conn, sids, AS_OF, bench, tampered, config_registry=config_registry)


def test_run_discovery_rejects_a_config_whose_label_disagrees_with_its_own_content(conn, universe):
    """Wrong label, correct content -- the SAME real content as the
    registered config, but a dishonest config_version string."""
    config = load_config()
    sids = universe["non_benchmark_ids"]
    bench = universe["benchmark_security_id"]
    config_registry = ConfigRegistry()

    run_discovery(conn, sids, AS_OF, bench, config, config_registry=config_registry)  # registers

    mislabeled = replace(config, config_version="cfg_DISHONEST_LABEL")
    with pytest.raises(ConfigIdentityError, match="does not match the"):
        run_discovery(conn, sids, AS_OF, bench, mislabeled, config_registry=config_registry)


def test_default_config_registry_none_leaves_existing_behavior_unchanged(conn, universe):
    """No config_registry supplied -- a deliberately different config
    (e.g. a test fixture never matching real discovery.yaml) must
    still be freely accepted, exactly as every pre-Stage-3 test in
    this package relies on."""
    config = load_config()
    sids = universe["non_benchmark_ids"]
    bench = universe["benchmark_security_id"]
    tampered = replace(config, eligibility={**config.eligibility, "minimum_history_days": 999})

    run_discovery(conn, sids, AS_OF, bench, tampered)  # no config_registry -- never rejected
