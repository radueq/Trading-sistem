"""TEST 47 -- StrategyVariants are materialized EAGERLY at freeze time;
a hypothesis whose `variant_ids` doesn't match its actually-supplied
variants is rejected at the pre-preregistration gate -- #005 must never
be able to invent a missing variant on demand (Radu's SS110-C/D: "asta va
demonstra ca 2,3 si 5 au existat inainte de backtest")."""
from hypothesis.registry.strategy_registry import build_strategy_definition
from hypothesis.validation.rules import validate_for_preregistration

from spec004.conftest import build_preregistered_hypothesis_for_test


def test_all_candidate_horizons_are_pre_materialized_before_any_selection(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry):
    hyp, variants, registry = build_preregistered_hypothesis_for_test(
        entry_definition, horizon_candidates, evidence_provenance, hypothesis_config,
    )
    assert len(variants) == len(horizon_candidates.values)
    ok, errors = validate_for_preregistration(hyp, variants, registry, hypothesis_config.data, run_registry)
    assert ok, errors
    # #005 must only ever pick among these pre-existing ids -- never mint a new one.
    for v in variants:
        sd = build_strategy_definition(hyp, v, registry)
        assert sd.strategy_variant_id in hyp.variant_ids


def test_a_variant_not_declared_on_the_hypothesis_is_rejected_by_the_gate(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry):
    hyp, variants, registry = build_preregistered_hypothesis_for_test(
        entry_definition, horizon_candidates, evidence_provenance, hypothesis_config,
    )
    hyp_missing_one = hyp.__class__(**{**hyp.__dict__, "variant_ids": hyp.variant_ids[:-1]})
    ok, errors = validate_for_preregistration(hyp_missing_one, variants, registry, hypothesis_config.data, run_registry)
    assert not ok
    assert any("does not match the supplied variants" in e for e in errors)


def test_005_cannot_build_a_strategy_definition_for_an_un_registered_variant(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config):
    hyp, variants, registry = build_preregistered_hypothesis_for_test(
        entry_definition, horizon_candidates, evidence_provenance, hypothesis_config,
    )
    # A locally-modified copy (fewer variant_ids) is no longer identical to
    # what the registry actually has on file for this hypothesis_id --
    # build_strategy_definition() (PATCH #004-A finding #1) catches this
    # via its registry-identity check before it would even reach the
    # older "not eagerly materialized" check.
    hyp_missing_one = hyp.__class__(**{**hyp.__dict__, "variant_ids": hyp.variant_ids[:-1]})
    missing_variant = variants[-1]
    try:
        build_strategy_definition(hyp_missing_one, missing_variant, registry)
        assert False, "expected ValueError for a hypothesis that doesn't match the registry's stored record"
    except ValueError as e:
        assert "does not match the registry's own stored record" in str(e)
