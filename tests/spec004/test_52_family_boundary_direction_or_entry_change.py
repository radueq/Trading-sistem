"""TEST 52 -- a different `direction` OR a different `entry_definition`
always produces a different StrategyHypothesis (family) id; ONLY the
exit/horizon differing keeps the SAME family (Radu's SS110-D formal
boundary rule, 2026-09-25)."""
import dataclasses

from hypothesis.models.entities import LaneStateCondition
from hypothesis.registry.hypotheses import build_hypothesis_id, hypothesis_fingerprint


def test_different_entry_definition_is_always_a_different_family(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config):
    other_entry = dataclasses.replace(entry_definition, core_conditions=(LaneStateCondition("volatility", "COMPRESSION"),))
    fp1 = hypothesis_fingerprint("SIG_X", "LONG", entry_definition, "NEXT_BAR_OPEN", horizon_candidates, evidence_provenance, hypothesis_config.config_version)
    fp2 = hypothesis_fingerprint("SIG_X", "LONG", other_entry, "NEXT_BAR_OPEN", horizon_candidates, evidence_provenance, hypothesis_config.config_version)
    assert build_hypothesis_id(fp1)[0] != build_hypothesis_id(fp2)[0]


def test_different_direction_is_always_a_different_family(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config):
    fp_long = hypothesis_fingerprint("SIG_X", "LONG", entry_definition, "NEXT_BAR_OPEN", horizon_candidates, evidence_provenance, hypothesis_config.config_version)
    fp_short = hypothesis_fingerprint("SIG_X", "SHORT", entry_definition, "NEXT_BAR_OPEN", horizon_candidates, evidence_provenance, hypothesis_config.config_version)
    assert build_hypothesis_id(fp_long)[0] != build_hypothesis_id(fp_short)[0]


def test_only_horizon_candidates_differing_still_changes_the_family_id_but_keeps_entry_and_direction():
    # horizon_candidate_set IS part of the family fingerprint (it's the
    # frozen candidate set the family commits to) -- this test documents
    # that fact plainly, distinguishing it from the EXIT/variant level
    # (which never affects the family's own id at all, see TEST 22).
    from hypothesis.models.entities import HorizonCandidateSet
    entry = None  # placeholder not needed; use direct fingerprint args below
    import hypothesis.models.entities as ent
    ed = ent.EntryDefinition(core_conditions=(ent.LaneStateCondition("volatility", "COMPRESSION"),))
    ev = ent.EvidenceProvenance("run_x", "v1.0.0", "cfg_eval", "SIG_X", "sigset_x", "v1.0.0", "cfg_disc", "1D")
    hs_a = HorizonCandidateSet(unit="BARS", values=(2, 3, 5), selection_basis="x", parameter_source="PRE_SPECIFIED")
    hs_b = HorizonCandidateSet(unit="BARS", values=(2, 3), selection_basis="x", parameter_source="PRE_SPECIFIED")
    fp_a = hypothesis_fingerprint("SIG_X", "LONG", ed, "NEXT_BAR_OPEN", hs_a, ev, "cfg_hyp")
    fp_b = hypothesis_fingerprint("SIG_X", "LONG", ed, "NEXT_BAR_OPEN", hs_b, ev, "cfg_hyp")
    assert fp_a != fp_b, "a different horizon_candidate_set is a different family commitment, and must change the id"
