"""TEST 48 -- definition_hash excludes administrative timestamps
(created_at, approved_at) but DOES change when trading meaning or
evidence/config provenance changes (Radu's SS110-E)."""
import dataclasses

from hypothesis.registry.hypotheses import build_hypothesis_id, hypothesis_fingerprint


def test_hash_is_identical_regardless_of_created_at_or_approved_at(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config):
    # hypothesis_fingerprint() doesn't even take a timestamp parameter --
    # this test proves that by construction, not just by observation:
    # two calls differing only in some OUT-OF-BAND timestamp (never
    # passed in) always produce the identical fingerprint/hash.
    fp1 = hypothesis_fingerprint("SIG_X", "LONG", entry_definition, "NEXT_BAR_OPEN", horizon_candidates, evidence_provenance, hypothesis_config.config_version)
    fp2 = hypothesis_fingerprint("SIG_X", "LONG", entry_definition, "NEXT_BAR_OPEN", horizon_candidates, evidence_provenance, hypothesis_config.config_version)
    assert fp1 == fp2
    assert build_hypothesis_id(fp1) == build_hypothesis_id(fp2)

    import inspect
    params = list(inspect.signature(hypothesis_fingerprint).parameters)
    assert not any("created_at" in p or "approved_at" in p or "timestamp" in p for p in params), (
        f"hypothesis_fingerprint() must never accept a timestamp-like parameter, got params={params}"
    )


def test_hash_changes_when_evidence_provenance_changes_but_not_from_timestamps(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config):
    fp_original = hypothesis_fingerprint("SIG_X", "LONG", entry_definition, "NEXT_BAR_OPEN", horizon_candidates, evidence_provenance, hypothesis_config.config_version)
    changed_provenance = dataclasses.replace(evidence_provenance, discovery_config_version="cfg_disc_v2")
    fp_changed = hypothesis_fingerprint("SIG_X", "LONG", entry_definition, "NEXT_BAR_OPEN", horizon_candidates, changed_provenance, hypothesis_config.config_version)
    assert fp_original != fp_changed
