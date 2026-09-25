"""TEST 5 -- no automatic LONG<->SHORT flip: if a signature's evidence is
negative, the system must never silently reinterpret the SAME proposal as
the opposite direction. A negative-effect proposal that keeps direction=
LONG stays a (structurally valid, though evidentially weak) LONG proposal
-- flipping is only ever a NEW, separate, explicit SHORT proposal (Spec
#004 SS8-9)."""
from hypothesis.proposals.normalize import normalize_proposal
from hypothesis.proposals.validator import validate_proposal
from hypothesis.registry.hypotheses import build_hypothesis_id, hypothesis_fingerprint

from spec004.conftest import make_proposal_raw


def test_negative_effect_long_proposal_is_not_rewritten_to_short(discovery_config, hypothesis_config):
    long_proposal = normalize_proposal(make_proposal_raw(
        direction="LONG", direction_basis="EVIDENCE_SIGN",
        facts_from_evidence=["mean relative return is -0.4% at the primary horizon"],
    ))
    result = validate_proposal(long_proposal, discovery_config, hypothesis_config)
    assert result.valid, result.errors
    assert long_proposal.direction == "LONG"


def test_long_and_short_on_the_same_entry_are_two_distinct_hypotheses(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config):
    fp_long = hypothesis_fingerprint("SIG_X", "LONG", entry_definition, "NEXT_BAR_OPEN", horizon_candidates, evidence_provenance, hypothesis_config.config_version)
    fp_short = hypothesis_fingerprint("SIG_X", "SHORT", entry_definition, "NEXT_BAR_OPEN", horizon_candidates, evidence_provenance, hypothesis_config.config_version)
    id_long, _ = build_hypothesis_id(fp_long)
    id_short, _ = build_hypothesis_id(fp_short)
    assert id_long != id_short, "LONG and SHORT on identical entry conditions must be two distinct, both-registrable hypotheses"
