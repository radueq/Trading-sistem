"""TEST 83 -- Stage 6, decision registry G1 (Finding 1) + Finding 2:
`preregister_hypothesis()` hard-rejects evidence not from
FORMAL_DEVELOPMENT, enforced against the REAL `EvaluationRunRegistry`,
never a self-reported field alone; and rejects `research_mode !=
PREREGISTERED_STRATEGY`. Procedural discipline only: this does NOT make
FORMAL_DEVELOPMENT evidence confirmatory (G1's known limitation, G2).

The two G1 regressions the registry names:
(1) rejection when `source_evidence.evaluation_mode == "EXPLORATORY"`;
(2) rejection when `evaluation_mode` FALSELY claims FORMAL_DEVELOPMENT
    while the real run registry shows EXPLORATORY.
Plus the marking itself (`EvidenceProvenance.evaluation_mode`, its
fingerprint input, and the packet copying it from the real run).
"""
import dataclasses

import pytest

from hypothesis.evidence.packet import build_evidence_packet
from hypothesis.models.entities import HypothesisResearchMode
from hypothesis.registry.hypotheses import HypothesisRegistry, _evidence_fp, build_hypothesis_id, hypothesis_fingerprint
from hypothesis.registry.preregistration import PreregistrationError
from hypothesis.validation.provenance import check_provenance_matches_run

from spec004.gate_inputs import draft_from_proposal, gate, make_proposal, registry_state, with_variants


def _run(gate_kwargs, proposal, hypothesis_config, **draft_overrides):
    draft, variants = with_variants(draft_from_proposal(proposal, hypothesis_config, **draft_overrides), proposal)
    reg = HypothesisRegistry()
    before = registry_state(reg)
    with pytest.raises(PreregistrationError) as exc_info:
        gate(draft, variants, proposal, hypothesis_config=hypothesis_config, registry=reg, **gate_kwargs)
    assert registry_state(reg) == before
    return str(exc_info.value)


def test_exploratory_evidence_from_a_real_exploratory_run_is_rejected(
    hypothesis_config, hypothesis_config_registry, run_registry,
):
    proposal = make_proposal(source_evidence_overrides={"evaluation_mode": "EXPLORATORY"})
    exploratory_run = dataclasses.replace(run_registry, mode="EXPLORATORY")
    message = _run(
        dict(config_registry=hypothesis_config_registry, run_registry=exploratory_run), proposal, hypothesis_config,
    )
    assert "proposal.source_evidence.evaluation_mode='EXPLORATORY'" in message
    assert "run_registry.mode='EXPLORATORY'" in message


def test_a_false_formal_development_claim_is_caught_against_the_real_run_record(
    hypothesis_config, hypothesis_config_registry, run_registry,
):
    proposal = make_proposal()  # declares FORMAL_DEVELOPMENT
    assert proposal.source_evidence.evaluation_mode == "FORMAL_DEVELOPMENT"
    real_run_is_exploratory = dataclasses.replace(run_registry, mode="EXPLORATORY")
    message = _run(
        dict(config_registry=hypothesis_config_registry, run_registry=real_run_is_exploratory), proposal, hypothesis_config,
    )
    assert "run_registry.mode='EXPLORATORY'" in message
    assert "proposal.source_evidence.evaluation_mode" not in message  # the declared field alone said FORMAL
    # ...and the provenance cross-check sees the lie on its own, too:
    ok, errors = check_provenance_matches_run(proposal.source_evidence, real_run_is_exploratory)
    assert not ok and any("evaluation_mode mismatch" in e for e in errors)


def test_an_undeclared_evaluation_mode_is_rejected(hypothesis_config, hypothesis_config_registry, run_registry):
    proposal = make_proposal(source_evidence_overrides={"evaluation_mode": None})
    assert proposal.source_evidence.evaluation_mode is None
    message = _run(dict(config_registry=hypothesis_config_registry, run_registry=run_registry), proposal, hypothesis_config)
    assert "proposal.source_evidence.evaluation_mode=None" in message


def test_an_exploratory_research_mode_is_rejected(hypothesis_config, hypothesis_config_registry, run_registry):
    message = _run(
        dict(config_registry=hypothesis_config_registry, run_registry=run_registry), make_proposal(), hypothesis_config,
        research_mode=HypothesisResearchMode.EXPLORATORY_HYPOTHESIS.value,
    )
    assert "draft.research_mode='EXPLORATORY_HYPOTHESIS'" in message


def test_provenance_mode_check_is_symmetric_and_skips_only_an_undeclared_mode(evidence_provenance, run_registry):
    assert check_provenance_matches_run(evidence_provenance, run_registry) == (True, ())
    claims_exploratory = dataclasses.replace(evidence_provenance, evaluation_mode="EXPLORATORY")
    ok, errors = check_provenance_matches_run(claims_exploratory, run_registry)
    assert not ok and any("evaluation_mode mismatch" in e for e in errors)
    # Undeclared (every pre-Stage-6 record, Spec #005's existing inputs):
    # not a lie about the run, left to each consumer -- the #004 gate
    # rejects it (test above).
    assert check_provenance_matches_run(dataclasses.replace(evidence_provenance, evaluation_mode=None), run_registry) == (True, ())


def test_evaluation_mode_is_a_fingerprint_input_and_none_keeps_the_pre_stage_6_formula(evidence_provenance):
    undeclared = dataclasses.replace(evidence_provenance, evaluation_mode=None)
    # Byte-for-byte the pre-Stage-6 formula, hand-derived:
    assert _evidence_fp(undeclared) == "run_x::v1.0.0::cfg_eval::VOL_COMPRESSION_RS_HIGH::sigset_x::v1.0.0::cfg_disc::1D"
    assert _evidence_fp(evidence_provenance) == _evidence_fp(undeclared) + "::MODE:FORMAL_DEVELOPMENT"

    from hypothesis.models.entities import EntryDefinition, HorizonCandidateSet, LaneStateCondition
    entry = EntryDefinition(core_conditions=(LaneStateCondition("volatility", "COMPRESSION"),))
    hcs = HorizonCandidateSet("BARS", (2, 3), "x", "PRE_SPECIFIED")
    ids = {
        mode: build_hypothesis_id(hypothesis_fingerprint(
            "VOL_COMPRESSION_RS_HIGH", "LONG", entry, "NEXT_BAR_OPEN", hcs,
            dataclasses.replace(evidence_provenance, evaluation_mode=mode), "cfg_h",
        ))[0]
        for mode in (None, "EXPLORATORY", "FORMAL_DEVELOPMENT")
    }
    assert len(set(ids.values())) == 3


def test_the_evidence_packet_marks_its_provenance_with_the_real_run_mode(
    signature_definition, profiles_all_horizons, run_registry, hypothesis_config,
):
    packet = build_evidence_packet(signature_definition, profiles_all_horizons, run_registry, hypothesis_config)
    assert packet.evidence_provenance.evaluation_mode == run_registry.mode == "FORMAL_DEVELOPMENT"
