"""TEST 74 -- the Stage 3 config identity mechanism wired into
`preregister_hypothesis()` (decision registry, Stage 3; authorized
2026-10-07): the mandatory live re-read gate (decision registry C1),
verified through the REAL gate, not only the shared helper in
isolation. CORRECTED round 4 -- GPT changes-required verdict on
`565c306`: round 3's `draft.strategy_config_version` check closed one
gap, but the gate could still establish its OWN reference AT
preregistration time whenever nothing was registered yet (`config_
registry=None`, or an empty `ConfigRegistry()`) -- a label on the
draft proves nothing was registered earlier; it is just a string any
caller can set. `config_registry` is now REQUIRED to already have the
"hypothesis" domain registered by an EARLIER step in this workflow,
resolved via `ConfigRegistry.resolve()` (never `register_or_verify()`,
which could register the first reference AT the gate) -- see
`preregistration.py`'s own Step -1.

Every existing call site in this package (TEST 53/56/62/63/etc.) now
threads a `hypothesis_config_registry` fixture (conftest.py) through,
simulating the earlier step that legitimately establishes this context
before preregistration ever runs.
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
from hypothesis.registry.persistence import PersistentHypothesisRegistry
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
    gate call. `config_registry` is NOT defaulted to anything seeded --
    every test must supply its own (or deliberately omit/empty it, to
    exercise the round-4 requirement that the gate never establishes
    its own reference)."""
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


def _tightened_hypothesis_budget_config(base):
    budget = base.data["hypothesis_budget"]
    return hypothesis_config_with_overrides(
        hypothesis_budget={**budget, "max_hypotheses_per_signature": budget["max_hypotheses_per_signature"] + 1},
    )


def test_genuine_hypothesis_config_passes_the_mandatory_live_re_read(
    entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, hypothesis_config_registry, run_registry,
):
    frozen = _gate(
        entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry,
        config_registry=hypothesis_config_registry,
    )
    assert frozen.status == HypothesisStatus.PREREGISTERED.value


def test_a_hypothesis_config_whose_content_disagrees_with_the_real_file_is_rejected(
    entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, hypothesis_config_registry, run_registry,
):
    """Correct label, wrong content -- the SAME real config_version,
    but hand-mutated data that no longer matches what hypothesis.yaml
    actually says right now. The draft is built under the REAL config
    (so check (c) stays silent); only the hypothesis_config ARGUMENT
    passed to the gate is tampered, caught by check (b) against the
    resolved context."""
    tampered_data = dict(hypothesis_config.data)
    tampered_data["hypothesis_budget"] = {**hypothesis_config.data["hypothesis_budget"], "max_hypotheses_per_signature": 999999}
    tampered = dataclasses.replace(hypothesis_config, data=tampered_data)
    assert tampered.config_version == hypothesis_config.config_version

    with pytest.raises(PreregistrationError, match="mandatory live re-read"):
        _gate(
            entry_definition, horizon_candidates, evidence_provenance, tampered, run_registry,
            draft_config=hypothesis_config, config_registry=hypothesis_config_registry,
        )


def test_a_hypothesis_config_whose_label_disagrees_with_its_own_content_is_rejected(
    entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, hypothesis_config_registry, run_registry,
):
    """Wrong label, correct content -- the real data, but a dishonest
    config_version string, as the hypothesis_config ARGUMENT; the draft
    itself is built under the real config."""
    mislabeled = dataclasses.replace(hypothesis_config, config_version="cfg_DISHONEST_LABEL")

    with pytest.raises(PreregistrationError, match="mandatory live re-read"):
        _gate(
            entry_definition, horizon_candidates, evidence_provenance, mislabeled, run_registry,
            draft_config=hypothesis_config, config_registry=hypothesis_config_registry,
        )


def test_a_directly_constructed_inconsistent_hypothesis_config_is_rejected(
    entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, hypothesis_config_registry, run_registry,
):
    """Neither the label nor the content of the hypothesis_config
    ARGUMENT were ever produced by a real load_config() call -- both
    checks fail at once. The draft is built under the real config."""
    forged = dataclasses.replace(hypothesis_config, data={"hand_built": True}, config_version="cfg_MADE_UP")

    with pytest.raises(PreregistrationError, match="mandatory live re-read"):
        _gate(
            entry_definition, horizon_candidates, evidence_provenance, forged, run_registry,
            draft_config=hypothesis_config, config_registry=hypothesis_config_registry,
        )


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


def test_a_draft_built_under_an_earlier_config_is_rejected_when_a_shared_registry_still_pins_it(
    entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry, monkeypatch,
):
    """Context A (shared registry pinned to A), but the live file AND
    the hypothesis_config argument have both moved to a genuinely
    different, self-consistent config B -- rejected via the mandatory
    live re-read against the resolved A."""
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
    entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, hypothesis_config_registry, run_registry,
):
    """Sanity/positive counterpart: config genuinely UNCHANGED (draft,
    gate call, and shared registry all agree on the SAME real config)
    -- must still succeed."""
    frozen = _gate(
        entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry,
        config_registry=hypothesis_config_registry,
    )
    assert frozen.status == HypothesisStatus.PREREGISTERED.value


def test_unchanged_config_succeeds_through_the_persistent_wrapper_too(
    tmp_path, entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, hypothesis_config_registry, run_registry,
):
    """GPT's required positive case, through `PersistentHypothesisRegistry.
    preregister()` specifically -- `config_registry` must thread through
    the persistence wrapper with no fallback to a new one, and a
    genuinely unchanged config must still succeed through it."""
    draft = _draft(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config)
    variants = materialize_variants(draft, created_at="2026-09-25T00:00:00Z")
    draft = dataclasses.replace(draft, variant_ids=tuple(v.strategy_variant_id for v in variants))
    proposal = _proposal()
    consensus = compute_consensus(proposal.proposal_id, (), human_decision=approved_human_decision())

    persistent = PersistentHypothesisRegistry.open(tmp_path / "audit.jsonl")
    frozen = persistent.preregister(
        draft, variants, proposal=proposal, proposal_validation=ProposalValidationResult(True, "OK", (), proposal.proposal_id),
        consensus=consensus, run_registry=run_registry, hypothesis_config=hypothesis_config,
        config_registry=hypothesis_config_registry,
    )
    assert frozen.status == HypothesisStatus.PREREGISTERED.value
    assert persistent.registry.get(frozen.hypothesis_id) == frozen


def test_a_draft_whose_recorded_config_version_disagrees_with_the_active_snapshot_is_rejected_before_any_writes(
    entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, hypothesis_config_registry, run_registry,
):
    """Context A properly established, hypothesis_config argument is
    the real, current file -- but the DRAFT itself was built under a
    genuinely different config B. Rejected by check (c) alone; confirms
    nothing is written to the HypothesisRegistry before the rejection."""
    config_b = _tightened_hypothesis_budget_config(hypothesis_config)
    hyp_registry = HypothesisRegistry()

    with pytest.raises(PreregistrationError, match="does not match the active"):
        _gate(
            entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry,
            draft_config=config_b, registry=hyp_registry, config_registry=hypothesis_config_registry,
        )
    assert hyp_registry.all_hypotheses() == ()


def test_omitting_config_registry_entirely_is_rejected_before_any_writes(
    entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry,
):
    """Finding (round 4): the gate must never be the place that FIRST
    establishes trust in a config. With NO config_registry at all --
    even though the draft and the hypothesis_config argument are both
    genuinely consistent with the real, current file, with no drift
    anywhere -- the call is still refused, because nothing proves the
    'hypothesis' domain was registered by an EARLIER step. Distinct
    from the next test (a context IS supplied, just empty) and from
    the A/B-mismatch tests above (this one has NO mismatch at all)."""
    hyp_registry = HypothesisRegistry()
    with pytest.raises(PreregistrationError, match="requires an explicit config_registry"):
        _gate(
            entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry,
            registry=hyp_registry,  # config_registry omitted (defaults to None)
        )
    assert hyp_registry.all_hypotheses() == ()


def test_a_config_registry_with_no_hypothesis_domain_registered_yet_is_rejected_before_any_writes(
    entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry,
):
    """Same requirement as above, but `config_registry` IS supplied --
    a real, freshly-constructed `ConfigRegistry()` that nothing has
    registered the "hypothesis" domain into yet. `resolve()` must
    raise (never silently register the gate's own fresh read as the
    reference, which `register_or_verify()` would have done) -- again
    with no drift anywhere else, isolating this one requirement."""
    empty_registry = ConfigRegistry()
    hyp_registry = HypothesisRegistry()
    with pytest.raises(PreregistrationError, match="no 'hypothesis' domain registered yet"):
        _gate(
            entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry,
            registry=hyp_registry, config_registry=empty_registry,
        )
    assert hyp_registry.all_hypotheses() == ()
    assert empty_registry.try_resolve("hypothesis") is None  # the gate never registered anything either
