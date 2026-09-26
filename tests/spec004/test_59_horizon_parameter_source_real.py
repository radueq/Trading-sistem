"""TEST 59 -- `HorizonCandidateSet.parameter_source` is a real,
propagated declaration, not a hardcoded lie (PATCH #004-A finding #5,
GPT Review #004 Round 1). The original `materialize_variants()` always
wrote `EVIDENCE_DERIVED` onto every TIME_EXIT variant regardless of how
the candidate set was actually chosen -- if Radu pre-specified [2,3,5]
before ever seeing evidence, the code would falsely claim otherwise."""
import dataclasses

from hypothesis.models.entities import ParameterSource
from hypothesis.registry.hypotheses import hypothesis_fingerprint, materialize_variants

from spec004.conftest import build_preregistered_hypothesis_for_test


def test_time_exit_variants_inherit_the_declared_parameter_source_pre_specified(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config):
    assert horizon_candidates.parameter_source == ParameterSource.PRE_SPECIFIED.value
    hyp, variants, _ = build_preregistered_hypothesis_for_test(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config)
    time_exit_variants = [v for v in variants if v.exit_hypothesis.exit_family == "TIME_EXIT"]
    assert time_exit_variants
    for v in time_exit_variants:
        assert v.exit_hypothesis.parameter_source == ParameterSource.PRE_SPECIFIED.value


def test_time_exit_variants_inherit_evidence_derived_when_declared_so(entry_definition, evidence_provenance, hypothesis_config):
    from hypothesis.models.entities import HorizonCandidateSet
    hs = HorizonCandidateSet(unit="BARS", values=(2, 3), selection_basis="decay curve concentrated here", parameter_source=ParameterSource.EVIDENCE_DERIVED.value)
    hyp, variants, _ = build_preregistered_hypothesis_for_test(entry_definition, hs, evidence_provenance, hypothesis_config)
    for v in variants:
        assert v.exit_hypothesis.parameter_source == ParameterSource.EVIDENCE_DERIVED.value


def test_parameter_source_is_part_of_the_family_fingerprint(entry_definition, evidence_provenance, hypothesis_config):
    from hypothesis.models.entities import HorizonCandidateSet
    hs_pre = HorizonCandidateSet(unit="BARS", values=(2, 3, 5), selection_basis="x", parameter_source=ParameterSource.PRE_SPECIFIED.value)
    hs_evidence = dataclasses.replace(hs_pre, parameter_source=ParameterSource.EVIDENCE_DERIVED.value)
    fp_pre = hypothesis_fingerprint(evidence_provenance.signature_id, "LONG", entry_definition, "NEXT_BAR_OPEN", hs_pre, evidence_provenance, hypothesis_config.config_version)
    fp_evidence = hypothesis_fingerprint(evidence_provenance.signature_id, "LONG", entry_definition, "NEXT_BAR_OPEN", hs_evidence, evidence_provenance, hypothesis_config.config_version)
    assert fp_pre != fp_evidence, "the SAME [2,3,5] proposed for a different reason must be a different family commitment"
