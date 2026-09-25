"""TEST 21 -- hypothesis fingerprint changes if direction changes (Spec
#004 SS31, Radu's SS110-E: direction is part of trading meaning)."""
from hypothesis.registry.hypotheses import build_hypothesis_id, hypothesis_fingerprint


def test_fingerprint_differs_when_direction_flips(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config):
    fp_long = hypothesis_fingerprint("SIG_X", "LONG", entry_definition, "NEXT_BAR_OPEN", horizon_candidates, evidence_provenance, hypothesis_config.config_version)
    fp_short = hypothesis_fingerprint("SIG_X", "SHORT", entry_definition, "NEXT_BAR_OPEN", horizon_candidates, evidence_provenance, hypothesis_config.config_version)
    assert fp_long != fp_short
    id_long, hash_long = build_hypothesis_id(fp_long)
    id_short, hash_short = build_hypothesis_id(fp_short)
    assert id_long != id_short
    assert hash_long != hash_short
