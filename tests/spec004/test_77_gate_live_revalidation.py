"""TEST 77 -- Stage 6, decision registry D1 (tied to C1): `preregister_
hypothesis()` RE-RUNS `validate_proposal()` live on the `proposal`
argument, against the config snapshots REGISTERED for this operation --
never trusting the cached `proposal_validation.valid` flag.

The narrative fields `facts_from_evidence`/`interpretation` are
deliberately outside every content fingerprint (joint remediation design
003+004 section 10, option (ii)'s gap): emptying them AFTER approval
leaves `HumanDecision.content_fingerprint` matching -- only the live
re-validation can catch it, which is why these cases isolate D1.
"""
import dataclasses

import pytest

from config_identity.registry import ConfigRegistry
from hypothesis.models.entities import EntryDefinition, LaneStateCondition
from hypothesis.registry.hypotheses import HypothesisRegistry, proposal_content_fingerprint
from hypothesis.registry.preregistration import PreregistrationError

from spec004.gate_inputs import draft_from_proposal, gate, make_proposal, registry_state, with_variants


def _inputs(proposal, hypothesis_config):
    return with_variants(draft_from_proposal(proposal, hypothesis_config), proposal)


@pytest.mark.parametrize("narrative_change", [
    {"facts_from_evidence": ()},
    {"interpretation": "   "},
    {"facts_from_evidence": (), "interpretation": ""},
])
def test_emptied_narrative_fields_with_a_stale_cached_valid_flag_are_caught_by_the_live_revalidation(
    narrative_change, hypothesis_config, hypothesis_config_registry, run_registry,
):
    approved = make_proposal()
    stale = dataclasses.replace(approved, **narrative_change)
    # The precondition that makes this a D1-only case: the economic
    # fingerprint the human approved is blind to the narrative change.
    assert proposal_content_fingerprint(stale) == proposal_content_fingerprint(approved)
    draft, variants = _inputs(stale, hypothesis_config)
    reg = HypothesisRegistry()

    with pytest.raises(PreregistrationError) as exc_info:
        gate(
            draft, variants, stale, approval_proposal=approved, cached_valid=True,
            hypothesis_config=hypothesis_config, config_registry=hypothesis_config_registry,
            run_registry=run_registry, registry=reg,
        )
    message = str(exc_info.value)
    assert "decision registry D1" in message
    assert "Finding 14" not in message  # nothing else fired: D1 alone caught it
    assert reg.all_hypotheses() == () and reg.all_variants() == ()


def test_an_entry_condition_outside_the_registered_discovery_vocabulary_is_caught_live(
    hypothesis_config, hypothesis_config_registry, run_registry,
):
    """The `UNAPPROVED_RSI` reproduction named in the remediation proposal
    (section 1): a vocabulary violation with a cached `valid=True` and an
    approval bound to that same content -- only the live re-run sees it."""
    proposal = dataclasses.replace(
        make_proposal(),
        entry_definition=EntryDefinition(core_conditions=(LaneStateCondition("UNAPPROVED_RSI", "HIGH"),)),
    )
    draft, variants = _inputs(proposal, hypothesis_config)
    with pytest.raises(PreregistrationError, match=r"decision registry D1.*UNAPPROVED_RSI"):
        gate(
            draft, variants, proposal, cached_valid=True, hypothesis_config=hypothesis_config,
            config_registry=hypothesis_config_registry, run_registry=run_registry,
        )


def test_the_gate_validates_the_live_proposal_against_the_pinned_snapshots_not_reloaded_objects(
    hypothesis_config, hypothesis_config_registry, run_registry, monkeypatch,
):
    """C1/D1 'verification needed': the validation runs on the LIVE
    `proposal` argument, and on the SAME frozen snapshot objects the
    registry resolved -- not a second, independently re-loaded config."""
    import hypothesis.registry.preregistration as prereg_module

    seen = []
    real_validate = prereg_module.validate_proposal

    def spy(proposal, discovery_config, hypothesis_config_arg):
        seen.append((proposal, discovery_config, hypothesis_config_arg))
        return real_validate(proposal, discovery_config, hypothesis_config_arg)

    monkeypatch.setattr(prereg_module, "validate_proposal", spy)
    proposal = make_proposal()
    draft, variants = _inputs(proposal, hypothesis_config)
    gate(
        draft, variants, proposal, hypothesis_config=hypothesis_config,
        config_registry=hypothesis_config_registry, run_registry=run_registry,
    )

    assert len(seen) == 1
    live_proposal, discovery_cfg, hypothesis_cfg = seen[0]
    assert live_proposal is proposal
    pinned_h = hypothesis_config_registry.resolve("hypothesis")
    pinned_d = hypothesis_config_registry.resolve("discovery")
    assert hypothesis_cfg.data is pinned_h.content and hypothesis_cfg.config_version == pinned_h.version
    assert discovery_cfg.states is pinned_d.content["states"] and discovery_cfg.config_version == pinned_d.version
    assert hypothesis_cfg.data is not hypothesis_config.data  # never the caller's own mutable object


def test_a_valid_live_proposal_still_passes(hypothesis_config, hypothesis_config_registry, run_registry):
    proposal = make_proposal()
    draft, variants = _inputs(proposal, hypothesis_config)
    frozen = gate(
        draft, variants, proposal, hypothesis_config=hypothesis_config,
        config_registry=hypothesis_config_registry, run_registry=run_registry,
    )
    assert frozen.status == "PREREGISTERED"


def test_a_cached_invalid_flag_is_still_refused_never_overridden_by_the_live_run(
    hypothesis_config, hypothesis_config_registry, run_registry,
):
    proposal = make_proposal()
    draft, variants = _inputs(proposal, hypothesis_config)
    with pytest.raises(PreregistrationError, match="failed proposals/validator.py's own check"):
        gate(
            draft, variants, proposal, cached_valid=False, hypothesis_config=hypothesis_config,
            config_registry=hypothesis_config_registry, run_registry=run_registry,
        )


def test_no_registered_discovery_snapshot_is_refused_before_any_write(hypothesis_config, run_registry):
    """The gate never establishes the Discovery reference itself -- a
    registry with only "hypothesis" registered is refused."""
    config_registry = ConfigRegistry()
    config_registry.register_or_verify(
        "hypothesis", hypothesis_config.config_version, hypothesis_config.data, hypothesis_config.raw_texts,
    )
    proposal = make_proposal()
    draft, variants = _inputs(proposal, hypothesis_config)
    reg = HypothesisRegistry()
    before = registry_state(reg)
    with pytest.raises(PreregistrationError, match="no 'discovery' domain registered yet"):
        gate(
            draft, variants, proposal, hypothesis_config=hypothesis_config, config_registry=config_registry,
            run_registry=run_registry, registry=reg,
        )
    assert registry_state(reg) == before
    assert config_registry.try_resolve("discovery") is None  # never registered by the gate either
