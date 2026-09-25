"""TEST 44 -- identical inputs always reproduce the identical
hypothesis_id (Spec #004 SS86-87 -- reproducibility via the structured
record, no random component anywhere)."""
from hypothesis.registry.hypotheses import build_hypothesis_id, hypothesis_fingerprint


def test_repeated_calls_with_identical_inputs_reproduce_the_same_id(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config):
    ids = set()
    for _ in range(5):
        fp = hypothesis_fingerprint("SIG_X", "LONG", entry_definition, "NEXT_BAR_OPEN", horizon_candidates, evidence_provenance, hypothesis_config.config_version)
        hid, _ = build_hypothesis_id(fp)
        ids.add(hid)
    assert len(ids) == 1
