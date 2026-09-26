"""TEST 55 -- `build_strategy_definition()` refuses a fully fabricated
StrategyHypothesis/StrategyVariant that was NEVER registered anywhere
(PATCH #004-A finding #1, GPT Review #004 Round 1's exact attack: "un
caller poate construi manual StrategyHypothesis(status=PREREGISTERED)
si poate ajunge la StrategyDefinition fara procesul pe care arhitectura
spune ca il garanteaza"). This is the most direct reproduction of that
scenario -- a hand-built object claiming PREREGISTERED, checked against
a registry that has never seen it."""
from hypothesis.models.entities import (
    Direction, HypothesisComplexitySnapshot, HypothesisProvenance, HypothesisResearchMode, HypothesisStatus,
    StrategyHypothesis,
)
from hypothesis.registry.hypotheses import HypothesisRegistry, build_hypothesis_id, build_variant, hypothesis_fingerprint
from hypothesis.registry.strategy_registry import build_strategy_definition


def test_a_fabricated_preregistered_hypothesis_never_produces_a_strategy_definition(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config):
    fp = hypothesis_fingerprint(evidence_provenance.signature_id, Direction.LONG.value, entry_definition, "NEXT_BAR_OPEN", horizon_candidates, evidence_provenance, hypothesis_config.config_version)
    hid, dh = build_hypothesis_id(fp)
    comp = HypothesisComplexitySnapshot(3, 1, hypothesis_config.config_version)
    prov = HypothesisProvenance("HUMAN:radu", None, None, "radu", "t")
    fabricated = StrategyHypothesis(
        hypothesis_id=hid, hypothesis_version=1, definition_hash=dh, status=HypothesisStatus.PREREGISTERED.value,
        research_mode=HypothesisResearchMode.PREREGISTERED_STRATEGY.value, parent_signature_id=evidence_provenance.signature_id,
        signature_set_id=evidence_provenance.signature_set_id, direction=Direction.LONG.value, direction_basis="EVIDENCE_SIGN",
        entry_definition=entry_definition, entry_execution_policy="NEXT_BAR_OPEN", horizon_candidate_set=horizon_candidates,
        variant_ids=("var_fabricated",), evidence_provenance=evidence_provenance, hypothesis_provenance=prov, constraints=comp,
        created_at="t", created_by="radu", strategy_config_version=hypothesis_config.config_version,
    )
    from hypothesis.models.entities import ExitFamily, ExitHypothesis, ParameterSource
    fabricated_exit = ExitHypothesis(
        exit_family=ExitFamily.TIME_EXIT.value, horizon_reference_point="ENTRY_BAR", exit_execution_policy="BAR_CLOSE",
        parameter_source=ParameterSource.EVIDENCE_DERIVED.value, time_exit_bars=3,
    )
    fabricated_variant = build_variant(fabricated, fabricated_exit, "BASELINE_VARIANT", "t")
    fabricated_variant = fabricated_variant.__class__(**{**fabricated_variant.__dict__, "strategy_variant_id": "var_fabricated"})

    empty_registry = HypothesisRegistry()  # never saw either object -- exactly the attack scenario

    try:
        build_strategy_definition(fabricated, fabricated_variant, empty_registry)
        assert False, "expected ValueError -- a never-registered PREREGISTERED claim must never produce a StrategyDefinition"
    except ValueError as e:
        assert "does not match the registry's own stored record" in str(e)
