"""TEST 1 -- legacy `evaluation_run_id` recomputation (Spec #005 v1.0
SS4, Batch 1). `verify_evaluation_run_identity()` recomputes
`build_run_id()` from EXACTLY the 8 fields `evaluation/engine.py:370-376`
uses and compares to the supplied registry's own claimed id -- a
CONSISTENCY check, never proof of historical execution (SS4)."""
import dataclasses

from backtest.provenance.evaluation_run import recompute_legacy_evaluation_run_id, verify_evaluation_run_identity

from spec005.conftest import build_run_registry


def test_genuine_registry_passes():
    registry = build_run_registry()
    ok, errors = verify_evaluation_run_identity(registry)
    assert ok, errors


def test_recompute_matches_the_registrys_own_id():
    registry = build_run_registry()
    assert recompute_legacy_evaluation_run_id(registry) == registry.evaluation_run_id


def test_tampered_development_end_with_stale_id_is_rejected():
    registry = build_run_registry()
    tampered = dataclasses.replace(registry, development_end="2099-01-01")
    ok, errors = verify_evaluation_run_identity(tampered)
    assert not ok
    assert any("does not match the recomputed legacy hash" in e for e in errors)


def test_tampered_bootstrap_seed_with_stale_id_is_rejected():
    registry = build_run_registry()
    tampered = dataclasses.replace(registry, bootstrap_seed=999)
    ok, errors = verify_evaluation_run_identity(tampered)
    assert not ok


def test_only_the_eight_legacy_fields_affect_the_hash():
    """Changing a field OUTSIDE the 8-field recipe (e.g. horizons,
    discovery_engine_version) must NOT change the recomputed id --
    proves the recipe really is exactly those 8 fields, not all 15."""
    registry = build_run_registry()
    same_hash_different_metadata = dataclasses.replace(
        registry, horizons=(99,), discovery_engine_version="v9.9.9",
        bootstrap_iterations=1, comparison_iterations=1, multiple_testing_method="BONFERRONI",
    )
    assert recompute_legacy_evaluation_run_id(same_hash_different_metadata) == registry.evaluation_run_id
    ok, errors = verify_evaluation_run_identity(same_hash_different_metadata)
    assert ok, errors
