"""TEST 2 -- the composed provenance guard (Spec #005 v1.0 SS4, Batch
1). `cross_check_evaluation_run()` composes three INDEPENDENT checks
(legacy hash, `check_provenance_matches_run()` linkage, mode+benchmark)
and never short-circuits -- each failure mode must be individually
catchable, and a pass on one check must never mask a failure on
another."""
import dataclasses

from backtest.provenance.evaluation_run import cross_check_evaluation_run

from spec005.conftest import BENCHMARK_SECURITY_ID, build_evidence_provenance, build_run_registry


def test_fully_consistent_inputs_pass():
    registry = build_run_registry()
    evidence = build_evidence_provenance(registry)
    result = cross_check_evaluation_run("hyp_1", evidence, registry, BENCHMARK_SECURITY_ID)
    assert result.ok, result.errors
    assert result.hash_consistent and result.linkage_ok and result.mode_ok and result.benchmark_ok


def test_linkage_mismatch_fails_independently_of_hash_and_mode():
    registry = build_run_registry()
    mismatched_evidence = build_evidence_provenance(registry, signature_set_id="sigset_DIFFERENT")
    result = cross_check_evaluation_run("hyp_1", mismatched_evidence, registry, BENCHMARK_SECURITY_ID)
    assert not result.ok
    assert result.hash_consistent  # the registry itself is still self-consistent
    assert not result.linkage_ok
    assert any("signature_set_id" in e for e in result.errors)


def test_hash_tampering_fails_even_when_linkage_still_agrees():
    """A tampered registry (development_end changed, id stale) whose
    OWN fields the EvidenceProvenance still happens to agree with
    (linkage passes) must still be caught by the hash check -- the two
    are independent, neither substitutes for the other (SS4)."""
    registry = build_run_registry()
    tampered = dataclasses.replace(registry, development_end="2099-01-01")
    evidence = build_evidence_provenance(tampered)  # agrees with the TAMPERED object's own fields
    result = cross_check_evaluation_run("hyp_1", evidence, tampered, BENCHMARK_SECURITY_ID)
    assert not result.ok
    assert not result.hash_consistent
    assert result.linkage_ok  # linkage alone would have missed this


def test_errors_accumulate_across_all_failing_checks():
    registry = build_run_registry(mode="EXPLORATORY")
    mismatched_evidence = build_evidence_provenance(registry, timeframe="4H")
    result = cross_check_evaluation_run("hyp_1", mismatched_evidence, registry, "SOME_OTHER_BENCHMARK")
    assert not result.ok
    assert not result.linkage_ok
    assert not result.mode_ok
    assert not result.benchmark_ok
    assert len(result.errors) >= 3
