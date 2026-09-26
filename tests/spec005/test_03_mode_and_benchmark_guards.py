"""TEST 3 -- mode and benchmark guards (Spec #005 v1.0 SS4, Batch 1).
Neither the legacy hash nor `check_provenance_matches_run()` checks
`mode` or `benchmark_security_id` -- SS4 requires both explicitly."""
from backtest.provenance.evaluation_run import verify_benchmark_matches, verify_mode_is_formal_development

from spec005.conftest import BENCHMARK_SECURITY_ID, build_run_registry


def test_formal_development_mode_passes():
    registry = build_run_registry(mode="FORMAL_DEVELOPMENT")
    ok, errors = verify_mode_is_formal_development(registry)
    assert ok, errors


def test_exploratory_mode_is_rejected():
    registry = build_run_registry(mode="EXPLORATORY")
    ok, errors = verify_mode_is_formal_development(registry)
    assert not ok
    assert any("FORMAL_DEVELOPMENT" in e for e in errors)


def test_matching_benchmark_passes():
    registry = build_run_registry(benchmark_security_id=BENCHMARK_SECURITY_ID)
    ok, errors = verify_benchmark_matches(registry, BENCHMARK_SECURITY_ID)
    assert ok, errors


def test_mismatched_benchmark_is_rejected():
    registry = build_run_registry(benchmark_security_id=BENCHMARK_SECURITY_ID)
    ok, errors = verify_benchmark_matches(registry, "SOME_OTHER_BENCHMARK")
    assert not ok
    assert any("benchmark" in e for e in errors)


def test_a_hash_and_linkage_consistent_but_exploratory_run_is_still_rejected_overall():
    """A run whose 8-field hash IS self-consistent and whose provenance
    linkage would pass must still be caught by the mode guard alone --
    otherwise an EXPLORATORY run's development_end could be trusted as
    if it carried FORMAL_DEVELOPMENT's rigor guarantees."""
    registry = build_run_registry(mode="EXPLORATORY")
    from backtest.provenance.evaluation_run import verify_evaluation_run_identity
    hash_ok, _ = verify_evaluation_run_identity(registry)
    assert hash_ok  # the registry itself is perfectly self-consistent
    mode_ok, _ = verify_mode_is_formal_development(registry)
    assert not mode_ok  # yet it must still be rejected
