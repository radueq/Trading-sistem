"""TEST 42 -- a Discovery config/engine version mismatch between a
hypothesis's evidence_provenance and the actual run is detected (Spec
#004 SS70-71, mirrors Spec #003 PATCH #003-B's provenance guard)."""
import dataclasses

from hypothesis.validation.provenance import check_provenance_matches_run


def test_discovery_config_version_mismatch_is_detected(evidence_provenance, run_registry):
    mismatched = dataclasses.replace(evidence_provenance, discovery_config_version="cfg_disc_DIFFERENT")
    ok, errors = check_provenance_matches_run(mismatched, run_registry)
    assert not ok
    assert any("discovery_config_version" in e for e in errors)


def test_discovery_engine_version_mismatch_is_detected(evidence_provenance, run_registry):
    mismatched = dataclasses.replace(evidence_provenance, discovery_engine_version="v0.0.1-stale")
    ok, errors = check_provenance_matches_run(mismatched, run_registry)
    assert not ok
    assert any("discovery_engine_version" in e for e in errors)


def test_matching_discovery_provenance_is_accepted(evidence_provenance, run_registry):
    ok, errors = check_provenance_matches_run(evidence_provenance, run_registry)
    assert ok, errors
