"""TEST 85 -- Stage 8, Finding 20 (P004C): PATCH #004-C's nested exit
types `StopLossRule` and `PartialProfitRule` were missing from
`registry/persistence.py`'s `_TYPE_REGISTRY`. `to_jsonable()` wrote them
out fine; `from_jsonable()` raised `KeyError` on the way back in.
Reproduced on `051d9a1`: both minimal round-trips -> KeyError, and a
full STOP_MANAGED_INVALIDATION family preregistered through the real
gate was committed as one audit line that `replay()` could then never
read (`KeyError: 'PartialProfitRule'`) -- a durable record unreadable
after any restart.

The design's two required regressions: both nested types round-trip
(not just one); AND a complete STOP_MANAGED_INVALIDATION hypothesis +
variant family survives a full persist-then-reload cycle through
`JsonlAuditLog.append()`/`replay()` -- not only the minimal probe.
"""
import pytest

from hypothesis.consensus.consensus import compute_consensus
from hypothesis.models.entities import ExitFamily, PartialProfitRule, StopLossRule
from hypothesis.proposals.validator import ProposalValidationResult
from hypothesis.registry.persistence import JsonlAuditLog, PersistentHypothesisRegistry, from_jsonable, to_jsonable

from spec004.conftest import approved_human_decision
from spec004.gate_inputs import APPROVED_AT, APPROVED_BY, draft_from_proposal, make_proposal, with_variants


@pytest.mark.parametrize("obj", [
    StopLossRule(basis="ATR_TRAILING_V1", atr_multiple=2.5),
    PartialProfitRule(r_multiple=1.5, fraction=0.4),
], ids=["StopLossRule", "PartialProfitRule"])
def test_each_nested_type_round_trips(obj):
    restored = from_jsonable(to_jsonable(obj))
    assert restored == obj and type(restored) is type(obj)


def _smi_raw(partial_profit):
    raw = {
        "exit_family": "STOP_MANAGED_INVALIDATION", "horizon_reference_point": "ENTRY_BAR",
        "exit_execution_policy": "BAR_CLOSE", "parameter_source": "AGENT_PROPOSED",
        "invalidation_conditions": [{"lane": "relative_strength", "holds_labels": ["HIGH", "VERY_HIGH"]}],
        "stop_loss": {"basis": "ATR_TRAILING_V1", "atr_multiple": 2.5},
    }
    if partial_profit:
        raw["partial_profit"] = {"r_multiple": 1.5, "fraction": 0.4}
    return raw


@pytest.mark.parametrize("partial_profit", [True, False], ids=["with_partial_profit", "stop_only"])
def test_a_full_stop_managed_family_survives_persist_then_replay(
    partial_profit, tmp_path, hypothesis_config, hypothesis_config_registry, run_registry,
):
    proposal = make_proposal(exit_hypotheses=[_smi_raw(partial_profit)])
    draft, variants = with_variants(draft_from_proposal(proposal, hypothesis_config), proposal)
    log_path = tmp_path / "audit.jsonl"

    persistent = PersistentHypothesisRegistry.open(log_path)
    frozen = persistent.preregister(
        draft, variants, proposal=proposal,
        proposal_validation=ProposalValidationResult(True, "OK", (), proposal.proposal_id),
        consensus=compute_consensus(proposal.proposal_id, (), human_decision=approved_human_decision(
            by=APPROVED_BY, at=APPROVED_AT, proposal=proposal,
        )),
        run_registry=run_registry, hypothesis_config=hypothesis_config, config_registry=hypothesis_config_registry,
    )
    assert len(log_path.read_text().splitlines()) == 1  # one atomic commit line (TEST 65 unchanged)

    for reloaded in (JsonlAuditLog(log_path).replay(), PersistentHypothesisRegistry.open(log_path).registry):
        assert reloaded.get(frozen.hypothesis_id) == frozen
        assert len(reloaded.all_variants()) == len(variants)
        for v in variants:
            assert reloaded.get_variant(v.strategy_variant_id) == v
        smi = [v for v in reloaded.all_variants() if v.exit_hypothesis.exit_family == ExitFamily.STOP_MANAGED_INVALIDATION.value]
        assert len(smi) == 1
        ex = smi[0].exit_hypothesis
        assert type(ex.stop_loss) is StopLossRule and ex.stop_loss == StopLossRule("ATR_TRAILING_V1", 2.5)
        if partial_profit:
            assert type(ex.partial_profit) is PartialProfitRule and ex.partial_profit == PartialProfitRule(1.5, 0.4)
        else:
            assert ex.partial_profit is None
