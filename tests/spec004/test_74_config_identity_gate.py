"""TEST 74 -- the Stage 3 config identity mechanism wired into
`preregister_hypothesis()` (decision registry, Stage 3; authorized
2026-10-07): the mandatory live re-read gate (decision registry C1),
verified through the REAL gate, not only the shared helper in
isolation. CORRECTED round 3 -- GPT changes-required verdict on
`955f482`: nothing previously tied the gate back to the SPECIFIC
snapshot the DRAFT itself was built under -- a draft built under
config A was wrongly accepted once BOTH the caller-supplied
`hypothesis_config` argument AND the live file had already moved to a
self-consistent config B, with no `config_registry` shared to catch
the drift via the cross-call registry tie. `draft.strategy_config_
version` is now checked, unconditionally, against the active config
actually used at the gate (see `preregistration.py`'s own Step -1(c)).

Every existing call site in this package (TEST 53/56/62/63/etc.)
already supplies a genuinely-loaded `hypothesis_config`, with the
draft built under THAT SAME config (the `hypothesis_config` fixture is
`load_config()`'s own real output, confirmed in `conftest.py`) -- so
the new mandatory checks are UNCONDITIONAL (not opt-in) and still
leave every one of them unaffected; `config_registry` is a SEPARATE,
optional parameter only needed to additionally catch a config that
changed since an EARLIER registration in the same workflow.
"""
import dataclasses

import pytest

from config_identity.registry import ConfigRegistry
from fixtures.config_overrides import hypothesis_config_with_overrides

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


def _gate(
    entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry,
    *, config_registry=None, draft_config=None, registry=None,
):
    """`draft_config` (default: `hypothesis_config`) is the config the
    DRAFT itself is built under -- separate from `hypothesis_config`,
    the argument actually passed to `preregister_hypothesis()`'s own
    gate call. Every pre-round-3 test leaves it at the default (draft
    and gate call always under the SAME config); the round-3
    regressions below set it explicitly DIFFERENT, to reproduce GPT's
    own finding that nothing previously tied the gate back to the
    SPECIFIC snapshot the draft was built under."""
    draft_config = draft_config if draft_config is not None else hypothesis_config
    draft = _draft(entry_definition, horizon_candidates, evidence_provenance, draft_config)
    variants = materialize_variants(draft, created_at="2026-09-25T00:00:00Z")
    draft = dataclasses.replace(draft, variant_ids=tuple(v.strategy_variant_id for v in variants))
    proposal = _proposal()
    consensus = compute_consensus(proposal.proposal_id, (), human_decision=approved_human_decision())
    registry = registry if registry is not None else HypothesisRegistry()
    return preregister_hypothesis(
        draft, variants, proposal=proposal, proposal_validation=ProposalValidationResult(True, "OK", (), proposal.proposal_id),
        consensus=consensus, registry=registry, run_registry=run_registry, hypothesis_config=hypothesis_config,
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
    config_registry.register_or_verify("hypothesis", real.config_version, real.data, real.raw_texts)  # earlier registration

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
    config_registry.register_or_verify("hypothesis", real.config_version, real.data, real.raw_texts)  # earlier registration, same content

    frozen = _gate(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry, config_registry=config_registry)
    assert frozen.status == HypothesisStatus.PREREGISTERED.value


def _tightened_hypothesis_budget_config(base):
    budget = base.data["hypothesis_budget"]
    return hypothesis_config_with_overrides(
        hypothesis_budget={**budget, "max_hypotheses_per_signature": budget["max_hypotheses_per_signature"] + 1},
    )


def test_a_draft_built_under_an_earlier_config_is_rejected_when_the_active_config_moved_on_with_no_shared_context(
    entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry, monkeypatch,
):
    """GPT's own reproduction on `955f482`: the draft is built under
    config A; the CALLER-supplied `hypothesis_config` argument AND the
    live file itself (monkeypatched) have both already moved to a
    genuinely different, self-consistent config B; NO `config_registry`
    is shared, so there is nothing for mechanism (b) to catch the
    drift against. Before the round-3 fix this was wrongly ACCEPTED,
    with the returned hypothesis carrying `strategy_config_version=A`
    while the config actually used at the gate was B."""
    config_a = hypothesis_config
    config_b = _tightened_hypothesis_budget_config(config_a)
    assert config_b.config_version != config_a.config_version  # sanity: genuinely different

    import hypothesis.registry.preregistration as prereg_module
    monkeypatch.setattr(prereg_module, "load_hypothesis_config", lambda: config_b)

    with pytest.raises(PreregistrationError, match="does not match the active"):
        _gate(
            entry_definition, horizon_candidates, evidence_provenance, config_b, run_registry,
            draft_config=config_a,
        )


def test_a_draft_built_under_an_earlier_config_is_rejected_when_a_shared_registry_still_pins_it(
    entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry, monkeypatch,
):
    """SAME scenario as above, but this time `config_registry` was
    ALREADY pinned to A earlier in the workflow -- mechanism (b) alone
    already catches this (confirmed working since round 2); kept as
    its own explicit regression per GPT's required list, distinct from
    the no-context case above."""
    config_a = hypothesis_config
    config_registry = ConfigRegistry()
    config_registry.register_or_verify("hypothesis", config_a.config_version, config_a.data, config_a.raw_texts)

    config_b = _tightened_hypothesis_budget_config(config_a)

    import hypothesis.registry.preregistration as prereg_module
    monkeypatch.setattr(prereg_module, "load_hypothesis_config", lambda: config_b)

    with pytest.raises(PreregistrationError, match="changed since it was registered earlier"):
        _gate(
            entry_definition, horizon_candidates, evidence_provenance, config_b, run_registry,
            draft_config=config_a, config_registry=config_registry,
        )


def test_unchanged_config_with_a_shared_registry_still_succeeds(
    entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry,
):
    """Sanity/positive counterpart: config genuinely UNCHANGED (draft,
    gate call, and shared registry all agree on the SAME real config)
    -- must still succeed, confirming the round-3 fix does not turn
    sharing a registry into a reason to reject on its own."""
    config_registry = ConfigRegistry()
    config_registry.register_or_verify(
        "hypothesis", hypothesis_config.config_version, hypothesis_config.data, hypothesis_config.raw_texts,
    )

    frozen = _gate(
        entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry,
        config_registry=config_registry,
    )
    assert frozen.status == HypothesisStatus.PREREGISTERED.value


def test_a_draft_whose_recorded_config_version_disagrees_with_the_active_snapshot_is_rejected_before_any_writes(
    entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry,
):
    """`draft.strategy_config_version` itself disagrees with the
    active, genuinely-current config -- rejected by the new check
    alone, with no tamper anywhere else (the caller's own
    `hypothesis_config` argument is the real, current file) and no
    `config_registry` at all; confirms nothing is written to the
    HypothesisRegistry before the rejection."""
    config_b = _tightened_hypothesis_budget_config(hypothesis_config)
    hyp_registry = HypothesisRegistry()

    with pytest.raises(PreregistrationError, match="does not match the active"):
        _gate(
            entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry,
            draft_config=config_b, registry=hyp_registry,
        )
    assert hyp_registry.all_hypotheses() == ()
