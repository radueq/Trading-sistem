"""TEST 33 -- Candidate Budget isolation (Spec #003 SS23/SS66,
IMPLEMENTATION BLOCKER Sec.74A).

Changing max_candidates must NOT alter the Evidence generated from
pre-budget observations -- proven from Evaluation's own consuming side
(Spec #002's TEST 24 proves the same property at the source).
"""
import dataclasses

from evaluation.engine import run_evaluation
from evaluation.models.entities import EvaluationSignatureDefinition, LaneStateCondition
from evaluation.registry.signatures import freeze_signature_set
from fixtures.config_overrides import discovery_config_with_overrides

from spec003.conftest import COMPRESSION_WINDOW_END, COMPRESSION_WINDOW_START


def _without_run_dependent_fields(profiles):
    """`family_id` embeds `run_id` (build_run_id()), which is itself
    built from `discovery_config_version` among other things -- honest
    hashing (Stage 3) means it legitimately differs between the two
    runs below even though the STATISTICAL content doesn't; excluded
    here, asserted separately."""
    return [
        dataclasses.replace(p, baseline_comparison=dataclasses.replace(p.baseline_comparison, family_id=None))
        for p in profiles
    ]


def _sigset(discovery_config_version):
    sig = EvaluationSignatureDefinition(
        signature_id="VOLATILITY_COMPRESSION", lane_conditions=(LaneStateCondition("volatility", "COMPRESSION"),),
        reason_code_conditions=(), timeframe="1D", discovery_engine_version="v1.0.0",
        discovery_config_version=discovery_config_version, creation_mode="PRE_REGISTERED",
        created_before_outcome_evaluation=True,
    )
    return freeze_signature_set([sig])


def test_changing_max_candidates_does_not_change_evidence_profiles(
    conn, tiny_universe, reduced_discovery_config, fast_evaluation_config, formal_calendar_registry, formal_calendar_id,
):
    default_cfg = reduced_discovery_config
    # Stage 3 (config identity infrastructure, authorized 2026-10-07,
    # CORRECTED round 2): this deliberately different config must be
    # genuinely loader-sourced -- re-apply reduced_discovery_config's
    # OWN already-applied overrides plus the new candidate_budget one,
    # in a single real reload (see tests/fixtures/config_overrides.py).
    # Honest hashing means candidate_budget genuinely changing also
    # changes discovery_config_version -- even though it has zero
    # effect on compute_discovery_observations() -- so each run needs
    # its OWN signature, pre-registered against ITS OWN actual config.
    tiny_budget_cfg = discovery_config_with_overrides(
        features=reduced_discovery_config.features,
        eligibility=reduced_discovery_config.eligibility,
        discovery={**reduced_discovery_config.discovery, "candidate_budget": {"enabled": True, "max_candidates": 1}},
    )
    assert tiny_budget_cfg.config_version != default_cfg.config_version  # sanity: genuinely different

    profiles_default, _ = run_evaluation(
        conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
        COMPRESSION_WINDOW_START, COMPRESSION_WINDOW_END, _sigset(default_cfg.config_version), default_cfg, fast_evaluation_config,
        calendar_registry=formal_calendar_registry, calendar_id=formal_calendar_id,
    )
    profiles_tiny_budget, _ = run_evaluation(
        conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
        COMPRESSION_WINDOW_START, COMPRESSION_WINDOW_END, _sigset(tiny_budget_cfg.config_version), tiny_budget_cfg, fast_evaluation_config,
        calendar_registry=formal_calendar_registry, calendar_id=formal_calendar_id,
    )

    assert _without_run_dependent_fields(profiles_default) == _without_run_dependent_fields(profiles_tiny_budget), (
        "Evaluation's dataset must be built from compute_discovery_observations(), never run_discovery()'s "
        "post-budget output -- max_candidates must have zero effect here"
    )
    assert profiles_default[0].baseline_comparison.family_id != profiles_tiny_budget[0].baseline_comparison.family_id
