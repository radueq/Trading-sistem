"""TEST 67 -- a well-formed STOP_MANAGED_INVALIDATION ExitHypothesis (with
its mandatory ATR-trailing stop_loss and explicit invalidation_conditions)
validates successfully at both the proposal-ingestion stage and the
pre-preregistration gate, with and without the optional partial_profit
(PATCH #004-C / Spec #005 Exit Amendment v1.0, ACCEPTED, section 1)."""
from hypothesis.models.entities import ExitFamily, ExitHypothesis, ParameterSource
from hypothesis.proposals.normalize import normalize_proposal
from hypothesis.proposals.validator import validate_proposal
from hypothesis.validation.rules import validate_for_preregistration

from spec004.conftest import build_preregistered_hypothesis_for_test, make_proposal_raw


def _stop_managed_exit_hypothesis_raw(partial_profit: dict | None = None) -> dict:
    raw = {
        "exit_family": "STOP_MANAGED_INVALIDATION", "horizon_reference_point": "ENTRY_BAR",
        "exit_execution_policy": "BAR_CLOSE", "parameter_source": "AGENT_PROPOSED",
        "stop_loss": {"basis": "ATR_TRAILING_V1", "atr_multiple": 2.0},
        "invalidation_conditions": [{"lane": "relative_strength", "holds_labels": ["HIGH", "VERY_HIGH"]}],
    }
    if partial_profit is not None:
        raw["partial_profit"] = partial_profit
    return raw


def test_control_variant_no_partial_profit_accepted_at_proposal_stage(discovery_config, hypothesis_config):
    raw = make_proposal_raw(exit_hypotheses=[_stop_managed_exit_hypothesis_raw()])
    proposal = normalize_proposal(raw)
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert result.valid, result.errors
    ex = proposal.exit_hypotheses[0]
    assert ex.exit_family == "STOP_MANAGED_INVALIDATION"
    assert ex.stop_loss.basis == "ATR_TRAILING_V1"
    assert ex.stop_loss.atr_multiple == 2.0
    assert ex.partial_profit is None
    assert ex.max_holding_bars is None
    assert ex.time_exit_bars is None


def test_partial_profit_variant_accepted_at_proposal_stage(discovery_config, hypothesis_config):
    raw = make_proposal_raw(exit_hypotheses=[
        _stop_managed_exit_hypothesis_raw(partial_profit={"r_multiple": 2.0, "fraction": 0.5}),
    ])
    proposal = normalize_proposal(raw)
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert result.valid, result.errors
    ex = proposal.exit_hypotheses[0]
    assert ex.partial_profit.r_multiple == 2.0
    assert ex.partial_profit.fraction == 0.5


def test_accepted_at_preregistration_gate(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config):
    from hypothesis.models.entities import InvalidationCondition, StopLossRule, PartialProfitRule
    stop_managed_exit = ExitHypothesis(
        exit_family=ExitFamily.STOP_MANAGED_INVALIDATION.value, horizon_reference_point="ENTRY_BAR",
        exit_execution_policy="BAR_CLOSE", parameter_source=ParameterSource.AGENT_PROPOSED.value,
        invalidation_conditions=(InvalidationCondition(lane="relative_strength", holds_labels=("HIGH", "VERY_HIGH")),),
        stop_loss=StopLossRule(basis="ATR_TRAILING_V1", atr_multiple=2.0),
        partial_profit=PartialProfitRule(r_multiple=2.0, fraction=0.5),
    )
    hyp, variants, registry = build_preregistered_hypothesis_for_test(
        entry_definition, horizon_candidates, evidence_provenance, hypothesis_config,
        signal_invalidation_exits=(stop_managed_exit,),
    )
    from evaluation.models.entities import EvaluationRunRegistry
    run_registry = EvaluationRunRegistry(
        evaluation_run_id=evidence_provenance.evaluation_run_id, created_at="t", mode="FORMAL_DEVELOPMENT",
        development_start="2020-01-01", development_end="2024-01-01", timeframe=evidence_provenance.timeframe,
        horizons=(2, 3, 5), benchmark_security_id="SBENCH", discovery_engine_version="v1.0.0",
        discovery_config_version=evidence_provenance.discovery_config_version, evaluation_engine_version="v1.0.0",
        evaluation_config_version=evidence_provenance.evaluation_config_version,
        signature_set_id=evidence_provenance.signature_set_id, bootstrap_seed=1, bootstrap_iterations=200,
        comparison_seed=2, comparison_iterations=200, multiple_testing_method="BH",
    )
    ok, errors = validate_for_preregistration(hyp, variants, registry, hypothesis_config.data, run_registry)
    assert ok, errors
    stop_managed_variants = [v for v in variants if v.exit_hypothesis.exit_family == "STOP_MANAGED_INVALIDATION"]
    assert len(stop_managed_variants) == 1
