"""TEST 47 -- StrategyVariants are materialized EAGERLY at freeze time;
a hypothesis whose `variant_ids` doesn't match its actually-supplied
variants is rejected at the pre-preregistration gate -- #005 must never
be able to invent a missing variant on demand (Radu's SS110-C/D: "asta va
demonstra ca 2,3 si 5 au existat inainte de backtest")."""
from hypothesis.registry.strategy_registry import build_strategy_definition
from hypothesis.validation.rules import validate_for_preregistration


def _build_hypothesis(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config):
    from hypothesis.models.entities import (
        Direction, HypothesisComplexitySnapshot, HypothesisProvenance, HypothesisResearchMode, HypothesisStatus, StrategyHypothesis,
    )
    from hypothesis.registry.hypotheses import build_hypothesis_id, hypothesis_fingerprint, materialize_variants

    fp = hypothesis_fingerprint("SIG_X", Direction.LONG.value, entry_definition, "NEXT_BAR_OPEN", horizon_candidates, evidence_provenance, hypothesis_config.config_version)
    hid, dh = build_hypothesis_id(fp)
    comp = HypothesisComplexitySnapshot(3, 1, hypothesis_config.config_version)
    prov = HypothesisProvenance("HUMAN:radu", None, None, "radu", "t")
    hyp = StrategyHypothesis(
        hypothesis_id=hid, hypothesis_version=1, definition_hash=dh, status=HypothesisStatus.PREREGISTERED.value,
        research_mode=HypothesisResearchMode.PREREGISTERED_STRATEGY.value, parent_signature_id="SIG_X",
        signature_set_id=evidence_provenance.signature_set_id, direction=Direction.LONG.value, direction_basis="EVIDENCE_SIGN",
        entry_definition=entry_definition, entry_execution_policy="NEXT_BAR_OPEN", horizon_candidate_set=horizon_candidates,
        variant_ids=(), evidence_provenance=evidence_provenance, hypothesis_provenance=prov, constraints=comp,
        created_at="t", created_by="radu", strategy_config_version=hypothesis_config.config_version,
    )
    variants = materialize_variants(hyp, created_at="t")
    hyp = hyp.__class__(**{**hyp.__dict__, "variant_ids": tuple(v.strategy_variant_id for v in variants)})
    return hyp, variants


def test_all_candidate_horizons_are_pre_materialized_before_any_selection(entry_definition, horizon_candidates, evidence_provenance, registry, hypothesis_config):
    hyp, variants = _build_hypothesis(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config)
    assert len(variants) == len(horizon_candidates.values)
    ok, errors = validate_for_preregistration(hyp, variants, registry, hypothesis_config.data)
    assert ok, errors
    # #005 must only ever pick among these pre-existing ids -- never mint a new one.
    for v in variants:
        sd = build_strategy_definition(hyp, v)
        assert sd.strategy_variant_id in hyp.variant_ids


def test_a_variant_not_declared_on_the_hypothesis_is_rejected_by_the_gate(entry_definition, horizon_candidates, evidence_provenance, registry, hypothesis_config):
    hyp, variants = _build_hypothesis(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config)
    hyp_missing_one = hyp.__class__(**{**hyp.__dict__, "variant_ids": hyp.variant_ids[:-1]})
    ok, errors = validate_for_preregistration(hyp_missing_one, variants, registry, hypothesis_config.data)
    assert not ok
    assert any("does not match the supplied variants" in e for e in errors)


def test_005_cannot_build_a_strategy_definition_for_an_un_registered_variant(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config):
    hyp, variants = _build_hypothesis(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config)
    hyp_missing_one = hyp.__class__(**{**hyp.__dict__, "variant_ids": hyp.variant_ids[:-1]})
    missing_variant = variants[-1]
    try:
        build_strategy_definition(hyp_missing_one, missing_variant)
        assert False, "expected ValueError for an un-registered variant"
    except ValueError as e:
        assert "not eagerly materialized" in str(e)
