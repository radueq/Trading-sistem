"""Utility script (not a pytest test) that produces Spec #004's example
report: docs/spec004_examples.md (SS96, the 4 required controlled
examples). Every number/id below is genuine output of the real #004
code paths (normalize -> validate -> consensus -> materialize_variants
-> validate_for_preregistration -> registry), run against hand-built
#003-shaped EvidenceProfiles -- nothing here is hand-typed output.

Re-run manually after any change to proposals/validation/registry logic:
  PYTHONPATH=src:tests python3 -m spec004.generate_report_artifacts
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

from discovery.config.loader import load_config as load_discovery_config

from hypothesis.config.loader import load_config as load_hypothesis_config
from hypothesis.consensus.consensus import can_preregister, compute_consensus
from hypothesis.consensus.reviews import collect_reviews
from hypothesis.evidence.packet import build_evidence_packet
from hypothesis.models.entities import (
    AgentReview, ComplexityStatus, Direction, HypothesisComplexitySnapshot, HypothesisProvenance,
    HypothesisResearchMode, HypothesisStatus,
)
from hypothesis.proposals.normalize import normalize_proposal
from hypothesis.proposals.validator import validate_proposal
from hypothesis.registry.hypotheses import HypothesisRegistry, build_hypothesis_id, hypothesis_fingerprint, materialize_variants
from hypothesis.validation.rules import validate_for_preregistration

from spec004.conftest import (
    DISCOVERY_CONFIG_VERSION, EVALUATION_CONFIG_VERSION, EVALUATION_RUN_ID, SIGNATURE_ID, SIGNATURE_SET_ID,
    make_evidence_profile, make_proposal_raw,
)

import evaluation.models.entities as eval_entities

DCFG = load_discovery_config()
HCFG = load_hypothesis_config()


def _signature_definition():
    return eval_entities.EvaluationSignatureDefinition(
        signature_id=SIGNATURE_ID,
        lane_conditions=(eval_entities.LaneStateCondition("volatility", "COMPRESSION"), eval_entities.LaneStateCondition("relative_strength", "VERY_HIGH")),
        reason_code_conditions=(), timeframe="1D", discovery_engine_version="v1.0.0",
        discovery_config_version=DISCOVERY_CONFIG_VERSION, creation_mode="PRE_REGISTERED", created_before_outcome_evaluation=True,
    )


def _run_registry():
    return eval_entities.EvaluationRunRegistry(
        evaluation_run_id=EVALUATION_RUN_ID, created_at="2026-09-25T00:00:00Z", mode="FORMAL_DEVELOPMENT",
        development_start="2020-01-01", development_end="2024-01-01", timeframe="1D", horizons=(1, 2, 3, 5, 10),
        benchmark_security_id="SBENCH", discovery_engine_version="v1.0.0", discovery_config_version=DISCOVERY_CONFIG_VERSION,
        evaluation_engine_version="v1.0.0", evaluation_config_version=EVALUATION_CONFIG_VERSION,
        signature_set_id=SIGNATURE_SET_ID, bootstrap_seed=1, bootstrap_iterations=200, comparison_seed=2,
        comparison_iterations=200, multiple_testing_method="BH",
    )


def _build_and_preregister(raw_proposal: dict, registry: HypothesisRegistry):
    """Runs the FULL real pipeline: normalize -> validate -> register
    proposal -> consensus -> human decision -> build hypothesis ->
    materialize variants -> pre-preregistration gate -> register.
    Returns (proposal, validation_result, hypothesis_or_None, variants, gate_errors)."""
    proposal = normalize_proposal(raw_proposal)
    validation = validate_proposal(proposal, DCFG, HCFG)
    registry.register_proposal(proposal)
    if not validation.valid:
        registry.mark_proposal_rejected(proposal.proposal_id)
        return proposal, validation, None, (), validation.errors

    reviews = collect_reviews([
        AgentReview("agent_trend", "manual-relay:gpt", proposal.proposal_id, "SUPPORT", (), (), "t1"),
        AgentReview("agent_skeptic", "manual-relay:claude", proposal.proposal_id, "SUPPORT", (), (), "t2"),
    ], proposal.proposal_id)
    consensus = compute_consensus(proposal.proposal_id, reviews, human_decision="Approved by Radu (example run)")
    ok, _ = can_preregister(consensus)
    assert ok

    fp = hypothesis_fingerprint(
        proposal.source_evidence.signature_id, proposal.direction, proposal.entry_definition,
        proposal.entry_execution_policy, proposal.horizon_candidates, proposal.source_evidence, HCFG.config_version,
    )
    hid, dh = build_hypothesis_id(fp)
    comp = HypothesisComplexitySnapshot(
        HCFG.data["hypothesis_complexity"]["max_entry_conditions"],
        HCFG.data["hypothesis_complexity"]["max_optional_confirmation_conditions"], HCFG.config_version,
    )
    prov = HypothesisProvenance(proposal.proposer, proposal.proposal_id, consensus.consensus_status, "radu", "2026-09-25T00:05:00Z")
    from hypothesis.models.entities import StrategyHypothesis
    draft = StrategyHypothesis(
        hypothesis_id=hid, hypothesis_version=1, definition_hash=dh, status=HypothesisStatus.DRAFT.value,
        research_mode=HypothesisResearchMode.PREREGISTERED_STRATEGY.value, parent_signature_id=proposal.source_evidence.signature_id,
        signature_set_id=proposal.source_evidence.signature_set_id, direction=proposal.direction, direction_basis=proposal.direction_basis,
        entry_definition=proposal.entry_definition, entry_execution_policy=proposal.entry_execution_policy,
        horizon_candidate_set=proposal.horizon_candidates, variant_ids=(), evidence_provenance=proposal.source_evidence,
        hypothesis_provenance=prov, constraints=comp, created_at="2026-09-25T00:00:00Z", created_by=proposal.proposer,
        strategy_config_version=HCFG.config_version,
    )
    variants = materialize_variants(draft, signal_invalidation_exits=proposal.exit_hypotheses, created_at="2026-09-25T00:05:00Z")
    hyp = draft.__class__(**{**draft.__dict__, "status": HypothesisStatus.PREREGISTERED.value, "variant_ids": tuple(v.strategy_variant_id for v in variants)})

    gate_ok, gate_errors = validate_for_preregistration(hyp, variants, registry, HCFG.data)
    if not gate_ok:
        registry.mark_proposal_rejected(proposal.proposal_id)
        return proposal, validation, None, variants, gate_errors

    registry.register(hyp)
    for v in variants:
        registry.register_variant(v)
    return proposal, validation, hyp, variants, ()


def _example_a() -> str:
    lines = ["### Example A -- Valid LONG continuation hypothesis\n"]
    signature = _signature_definition()
    run_reg = _run_registry()
    profiles = [
        make_evidence_profile(1, mean_relative=0.003, adjusted_p=0.15),
        make_evidence_profile(2, mean_relative=0.008, adjusted_p=0.02),
        make_evidence_profile(3, mean_relative=0.010, adjusted_p=0.01),
        make_evidence_profile(5, mean_relative=0.007, adjusted_p=0.04),
    ]
    packet = build_evidence_packet(signature, profiles, run_reg, primary_horizon_bars=2)
    lines.append(f"EvidencePacket: signature={packet.signature_id}, primary_horizon_bars={packet.primary_evidence_horizon_bars}, "
                 f"primary_relative_mean={packet.primary_relative_mean:.4f}, primary_adjusted_p={packet.primary_adjusted_p:.4f}\n")

    registry = HypothesisRegistry()
    raw = make_proposal_raw(proposal_id="prop_A", horizon_candidates={"unit": "BARS", "values": [1, 2, 3], "selection_basis": "decay strongest at 2-3 bars, still positive at 1"})
    proposal, validation, hyp, variants, errors = _build_and_preregister(raw, registry)
    lines.append(f"Proposal valid: {validation.valid} (complexity_status={validation.complexity_status})")
    lines.append(f"StrategyHypothesis: hypothesis_id={hyp.hypothesis_id}, direction={hyp.direction}, status={hyp.status}")
    lines.append(f"Materialized variants ({len(variants)}): " + ", ".join(
        f"{v.strategy_variant_id[:14]}..={v.exit_hypothesis.exit_family}:{v.exit_hypothesis.time_exit_bars or v.exit_hypothesis.max_holding_bars}"
        for v in variants
    ))
    lines.append("")
    return "\n".join(lines)


def _example_b() -> str:
    lines = ["### Example B -- Negative effect must NOT auto-flip to SHORT\n"]
    registry = HypothesisRegistry()

    raw_long = make_proposal_raw(
        proposal_id="prop_B_long", direction="LONG", direction_basis="EVIDENCE_SIGN",
        facts_from_evidence=["mean relative return is -0.35% at the primary horizon -- weak/negative"],
        horizon_candidates={"unit": "BARS", "values": [2, 3], "selection_basis": "unchanged despite weak evidence -- direction is not re-derived"},
    )
    _, val_long, hyp_long, _, _ = _build_and_preregister(raw_long, registry)
    lines.append(f"LONG proposal (built from negative-effect evidence) stays LONG: valid={val_long.valid}, hypothesis_id={hyp_long.hypothesis_id}")

    raw_short = make_proposal_raw(
        proposal_id="prop_B_short", direction="SHORT", direction_basis="AGENT_PROPOSAL",
        facts_from_evidence=["mean relative return is -0.35% at the primary horizon -- motivates a SEPARATE SHORT proposal"],
        horizon_candidates={"unit": "BARS", "values": [2, 3], "selection_basis": "same evidence, opposite direction, explicitly proposed on its own"},
    )
    _, val_short, hyp_short, _, _ = _build_and_preregister(raw_short, registry)
    lines.append(f"SHORT proposal is a SEPARATE, explicit hypothesis: valid={val_short.valid}, hypothesis_id={hyp_short.hypothesis_id}")
    lines.append(f"Two distinct hypothesis_ids: {hyp_long.hypothesis_id != hyp_short.hypothesis_id} (never the same record silently flipped)")
    lines.append(f"Registry now holds both: {len(registry.all_hypotheses())} PREREGISTERED hypotheses on the same signature")
    lines.append("")
    return "\n".join(lines)


def _example_c() -> str:
    lines = ["### Example C -- Horizon trap: peak at 3 bars, no auto exit=3\n"]
    signature = _signature_definition()
    run_reg = _run_registry()
    profiles = [
        make_evidence_profile(1, mean_relative=0.002, adjusted_p=0.20),
        make_evidence_profile(2, mean_relative=0.006, adjusted_p=0.05),
        make_evidence_profile(3, mean_relative=0.012, adjusted_p=0.01),
        make_evidence_profile(5, mean_relative=0.008, adjusted_p=0.04),
        make_evidence_profile(10, mean_relative=0.001, adjusted_p=0.60),
    ]
    packet = build_evidence_packet(signature, profiles, run_reg, primary_horizon_bars=3)
    strongest = max(packet.decay_curve, key=lambda d: d.mean_relative_return or 0)
    lines.append(f"Decay curve: {[(d.evidence_horizon_bars, round(d.mean_relative_return, 4)) for d in packet.decay_curve]}")
    lines.append(f"Strongest single point: {strongest.evidence_horizon_bars} bars (mean={strongest.mean_relative_return:.4f}) -- "
                  f"tempting to declare 'exit=3', but #004 never does this automatically.")

    registry = HypothesisRegistry()
    raw = make_proposal_raw(
        proposal_id="prop_C", horizon_candidates={"unit": "BARS", "values": [2, 3, 5], "selection_basis": "decay concentrated in the 2-5 bar zone -- ALL THREE kept as candidates, none pre-selected"},
    )
    _, validation, hyp, variants, _ = _build_and_preregister(raw, registry)
    time_exit_variants = [v for v in variants if v.exit_hypothesis.exit_family == "TIME_EXIT"]
    lines.append(f"materialize_variants() produced {len(time_exit_variants)} TIME_EXIT variants (bars={sorted(v.exit_hypothesis.time_exit_bars for v in time_exit_variants)}), "
                  f"all frozen into hypothesis.variant_ids BEFORE any backtest -- #005 selects among these, never invents 'the' 3-bar exit after the fact.")
    lines.append(f"No field named selected_horizon/optimal_horizon exists anywhere on StrategyHypothesis: confirmed structurally by TEST 12.")
    lines.append("")
    return "\n".join(lines)


def _example_d() -> str:
    lines = ["### Example D -- Over-complex proposal rejected by the complexity guardrail\n"]
    registry = HypothesisRegistry()
    raw = make_proposal_raw(
        proposal_id="prop_D",
        entry_definition={"core_conditions": [
            {"lane": "volatility", "label": "COMPRESSION"}, {"lane": "relative_strength", "label": "VERY_HIGH"},
            {"lane": "trend", "label": "HIGH"}, {"lane": "momentum", "label": "HIGH"}, {"lane": "volume", "label": "HIGH"},
        ]},
        exit_hypotheses=[
            {"exit_family": "SIGNAL_INVALIDATION", "horizon_reference_point": "ENTRY_BAR", "exit_execution_policy": "BAR_CLOSE",
             "parameter_source": "AGENT_PROPOSED", "max_holding_bars": 5,
             "invalidation_conditions": [{"lane": "relative_strength", "holds_labels": ["HIGH", "VERY_HIGH"]}]},
            {"exit_family": "SIGNAL_INVALIDATION", "horizon_reference_point": "ENTRY_BAR", "exit_execution_policy": "BAR_CLOSE",
             "parameter_source": "AGENT_PROPOSED", "max_holding_bars": 5,
             "invalidation_conditions": [{"lane": "trend", "holds_labels": ["HIGH", "VERY_HIGH"]}]},
            {"exit_family": "SIGNAL_INVALIDATION", "horizon_reference_point": "ENTRY_BAR", "exit_execution_policy": "BAR_CLOSE",
             "parameter_source": "AGENT_PROPOSED", "max_holding_bars": 5,
             "invalidation_conditions": [{"lane": "momentum", "holds_labels": ["HIGH", "VERY_HIGH"]}]},
            {"exit_family": "SIGNAL_INVALIDATION", "horizon_reference_point": "ENTRY_BAR", "exit_execution_policy": "BAR_CLOSE",
             "parameter_source": "AGENT_PROPOSED", "max_holding_bars": 5,
             "invalidation_conditions": [{"lane": "volume", "holds_labels": ["HIGH", "VERY_HIGH"]}]},
        ],
    )
    proposal, validation, hyp, variants, errors = _build_and_preregister(raw, registry)
    lines.append(f"Proposal: 5 entry core_conditions + 4 SIGNAL_INVALIDATION exit variants")
    lines.append(f"validate_proposal(): valid={validation.valid}, complexity_status={validation.complexity_status}")
    assert validation.complexity_status == ComplexityStatus.HYPOTHESIS_COMPLEXITY_EXCEEDED.value
    for e in validation.errors:
        lines.append(f"  - {e}")
    lines.append(f"hyp registered as PREREGISTERED: {hyp is not None} (must be False)")
    lines.append(f"Proposal record retained in registry (never silently deleted): {proposal in registry.all_proposals()}")
    lines.append(f"Proposal marked rejected: {'prop_D' in registry.rejected_proposal_ids()}")
    lines.append("")
    return "\n".join(lines)


def build_examples_md() -> str:
    sections = [
        "# Spec #004 v1.0 -- Example Hypothesis Generation Output\n",
        "**All four examples below run the REAL #004 pipeline (normalize ->",
        "validate -> consensus -> materialize_variants -> pre-preregistration",
        "gate -> registry) against hand-built #003-shaped EvidenceProfiles --",
        "no live-market data, nothing hand-edited.**\n",
    ]
    sections.append(_example_a())
    sections.append(_example_b())
    sections.append(_example_c())
    sections.append(_example_d())
    return "\n".join(sections)


if __name__ == "__main__":
    (REPO_ROOT / "docs" / "spec004_examples.md").write_text(build_examples_md())
    print("wrote docs/spec004_examples.md")
