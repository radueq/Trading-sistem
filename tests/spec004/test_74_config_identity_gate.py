"""TEST 74 -- the Stage 3 config identity mechanism wired into
`preregister_hypothesis()` (decision registry, Stage 3; authorized
2026-10-07): the mandatory live re-read gate (decision registry C1),
verified through the REAL gate, not only the shared helper in
isolation.

Every existing call site in this package (TEST 53/56/62/63/etc.)
already supplies a genuinely-loaded `hypothesis_config` (the
`hypothesis_config` fixture is `load_config()`'s own real output,
confirmed in `conftest.py`) -- so the new mandatory check is
UNCONDITIONAL (not opt-in) and still leaves every one of them
unaffected; `config_registry` is a SEPARATE, optional parameter only
needed to additionally catch a config that changed since an EARLIER
registration in the same workflow.
"""
import dataclasses

import pytest

from config_identity.registry import ConfigRegistry

from hypothesis.config.loader import load_config as load_hypothesis_config
from hypothesis.models.entities import (
    Direction, HypothesisComplexitySnapshot, HypothesisProvenance, HypothesisResearchMode, HypothesisStatus,
    StrategyHypothesis,
)
from hypothesis.registry.hypotheses import HypothesisRegistry, build_hypothesis_id, hypothesis_fingerprint, materialize_variants
from hypothesis.registry.preregistration import PreregistrationError, preregister_hypothesis
from hypothesis.proposals.normalize import normalize_proposal
from hypothesis.proposals.validator import ProposalValidationResult
from hypothesis.consensus.consensus import compute_consensus

from spec004.conftest import approved_human_decision, make_proposal_raw


def _proposal(proposal_id="prop_1"):
    return normalize_proposal(make_proposal_raw(proposal_id=proposal_id))


def _draft(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, proposal_id="prop_1"):
    fp = hypothesis_fingerprint(
        evidence_provenance.signature_id, Direction.LONG.value, entry_definition, "NEXT_BAR_OPEN",
        horizon_candidates, evidence_provenance, hypothesis_config.config_version,
    )
    hid, dh = build_hypothesis_id(fp)
    comp = HypothesisComplexitySnapshot(3, 1, hypothesis_config.config_version)
    prov = HypothesisProvenance("HUMAN:radu", proposal_id, None, "radu", "2026-09-25T00:05:00Z")
    return StrategyHypothesis(
        hypothesis_id=hid, hypothesis_version=1, definition_hash=dh, status=HypothesisStatus.DRAFT.value,
        research_mode=HypothesisResearchMode.PREREGISTERED_STRATEGY.value, parent_signature_id=evidence_provenance.signature_id,
        signature_set_id=evidence_provenance.signature_set_id, direction=Direction.LONG.value, direction_basis="EVIDENCE_SIGN",
        entry_definition=entry_definition, entry_execution_policy="NEXT_BAR_OPEN", horizon_candidate_set=horizon_candidates,
        variant_ids=(), evidence_provenance=evidence_provenance, hypothesis_provenance=prov, constraints=comp,
        created_at="2026-09-25T00:00:00Z", created_by="radu", strategy_config_version=hypothesis_config.config_version,
    )


def _gate(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry, *, config_registry=None):
    draft = _draft(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config)
    variants = materialize_variants(draft, created_at="2026-09-25T00:00:00Z")
    draft = dataclasses.replace(draft, variant_ids=tuple(v.strategy_variant_id for v in variants))
    proposal = _proposal()
    consensus = compute_consensus(proposal.proposal_id, (), human_decision=approved_human_decision())
    return preregister_hypothesis(
        draft, variants, proposal=proposal, proposal_validation=ProposalValidationResult(True, "OK", (), proposal.proposal_id),
        consensus=consensus, registry=HypothesisRegistry(), run_registry=run_registry, hypothesis_config=hypothesis_config,
        config_registry=config_registry,
    )


def test_genuine_hypothesis_config_passes_the_mandatory_live_re_read(
    entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry,
):
    frozen = _gate(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry)
    assert frozen.status == HypothesisStatus.PREREGISTERED.value


def test_a_hypothesis_config_whose_content_disagrees_with_the_real_file_is_rejected(
    entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry,
):
    """Correct label, wrong content -- the SAME real config_version,
    but hand-mutated data that no longer matches what hypothesis.yaml
    actually says right now."""
    tampered_data = dict(hypothesis_config.data)
    tampered_data["hypothesis_budget"] = {**hypothesis_config.data["hypothesis_budget"], "max_hypotheses_per_signature": 999999}
    tampered = dataclasses.replace(hypothesis_config, data=tampered_data)
    assert tampered.config_version == hypothesis_config.config_version

    with pytest.raises(PreregistrationError, match="mandatory live re-read"):
        _gate(entry_definition, horizon_candidates, evidence_provenance, tampered, run_registry)


def test_a_hypothesis_config_whose_label_disagrees_with_its_own_content_is_rejected(
    entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry,
):
    """Wrong label, correct content -- the real data, but a dishonest
    config_version string."""
    mislabeled = dataclasses.replace(hypothesis_config, config_version="cfg_DISHONEST_LABEL")

    with pytest.raises(PreregistrationError, match="mandatory live re-read"):
        _gate(entry_definition, horizon_candidates, evidence_provenance, mislabeled, run_registry)


def test_a_directly_constructed_inconsistent_hypothesis_config_is_rejected(
    entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry,
):
    """Neither the label nor the content were ever produced by a real
    load_config() call -- both checks fail at once."""
    forged = dataclasses.replace(hypothesis_config, data={"hand_built": True}, config_version="cfg_MADE_UP")

    with pytest.raises(PreregistrationError, match="mandatory live re-read"):
        _gate(entry_definition, horizon_candidates, evidence_provenance, forged, run_registry)


def test_config_registry_catches_a_config_that_changed_since_an_earlier_registration(
    entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry, monkeypatch,
):
    """Simulates the exact scenario the mandatory live re-read exists
    for: an EARLIER registration (e.g. at proposal-validation time)
    pins one snapshot into a shared ConfigRegistry; by the time THIS
    gate call's own fresh re-read happens, the file has changed --
    caught even though the CALLER-supplied hypothesis_config argument
    still matches the (now-stale) earlier registration, not the fresh
    read."""
    config_registry = ConfigRegistry()
    real = load_hypothesis_config()
    config_registry.register("hypothesis", real.config_version, real.data)  # earlier registration

    tampered_data = dict(real.data)
    tampered_data["hypothesis_budget"] = {**real.data["hypothesis_budget"], "max_hypotheses_per_signature": 999999}
    tampered_fresh_read = dataclasses.replace(real, data=tampered_data)

    import hypothesis.registry.preregistration as prereg_module
    monkeypatch.setattr(prereg_module, "load_hypothesis_config", lambda: tampered_fresh_read)

    with pytest.raises(PreregistrationError, match="changed since it was registered earlier"):
        _gate(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry, config_registry=config_registry)


def test_config_registry_passes_when_the_fresh_re_read_still_matches_the_earlier_registration(
    entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry,
):
    config_registry = ConfigRegistry()
    real = load_hypothesis_config()
    config_registry.register("hypothesis", real.config_version, real.data)  # earlier registration, same content

    frozen = _gate(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry, config_registry=config_registry)
    assert frozen.status == HypothesisStatus.PREREGISTERED.value
