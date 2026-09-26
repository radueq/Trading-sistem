"""Spec #004 SS71-72 -- deterministic pre-preregistration validation.

Runs on an already-assembled StrategyHypothesis + its eagerly-materialized
StrategyVariants, as the LAST gate before status may become PREREGISTERED
-- with full registry context available (per-signature hypothesis budget,
SS52). Distinct from `proposals/validator.py` (which runs on a raw
HypothesisProposal, before any registry exists): this module re-checks the
outcome-contamination rule (SS72) defensively on the fully-built objects,
not just the proposal that led to them.

PATCH #004-A finding #2 (GPT Review #004 Round 1): `validate_for_
preregistration()` now REQUIRES `run_registry` and calls `validation.
provenance.check_provenance_matches_run()` itself -- the provenance guard
existed but nothing wired it into this gate, so a caller could skip it
entirely. Also adds the internal consistency check the review flagged:
`StrategyHypothesis.parent_signature_id`/`signature_set_id` are stored
separately from `evidence_provenance.signature_id`/`signature_set_id`
(kept for the top-level registry/budget-accounting API), and nothing
previously verified they actually agree -- a caller could register a
hypothesis whose declared "parent signature" and budget accounting
didn't match the Evidence it actually claims to rest on.

PATCH #004-B finding #2 (GPT Review #004 Round 2): the design's central
claim is that `hypothesis_id`/`definition_hash`/`strategy_variant_id`/
`variant_definition_hash` are CONTENT-ADDRESSED -- but nothing at the
gate actually recomputed the fingerprint and compared it against the
id/hash a caller supplied. A hand-built `StrategyHypothesis`/
`StrategyVariant` with an arbitrary, non-matching id/hash could pass
every other check here and reach the registry, silently breaking "the id
proves the content" for every future lookup. `validate_for_
preregistration()` now recomputes `hypothesis_fingerprint()` from the
hypothesis's OWN fields and hard-fails if `hypothesis_id`/
`definition_hash` don't match, then does the same per-variant with
`variant_fingerprint()` against the INDEPENDENTLY-recomputed
`definition_hash` (never the hypothesis's own possibly-wrong claim) --
TEST 63.
"""
from __future__ import annotations

from evaluation.models.entities import EvaluationRunRegistry

from hypothesis.models.entities import (
    Direction,
    ExitFamily,
    HypothesisStatus,
    InvalidationCondition,
    LaneStateCondition,
    ReasonCodeCondition,
    StrategyHypothesis,
    StrategyVariant,
)
from hypothesis.registry.hypotheses import (
    HypothesisRegistry,
    build_hypothesis_id,
    build_variant_id,
    hypothesis_fingerprint,
    variant_fingerprint,
)
from hypothesis.validation.provenance import check_provenance_matches_run

# Spec #004 SS72 -- Evidence/outcome fields that must NEVER become part of
# a runtime entry/exit signal condition (a research finding motivates a
# hypothesis; it can never become a live feature).
FORBIDDEN_OUTCOME_FIELD_NAMES = {
    "adjusted_p", "raw_p", "forward_return", "relative_return", "mean_return",
    "median_return", "win_rate", "standardized_effect", "baseline_mean",
    "baseline_median", "expectancy", "sharpe", "valid_episode_n",
    "opportunity_density", "review_priority",
}


def _scan_condition_for_outcome_contamination(
    condition: "LaneStateCondition | ReasonCodeCondition | InvalidationCondition", where: str, errors: list[str],
) -> None:
    for attr in ("lane", "label", "reason_code"):
        token = getattr(condition, attr, None)
        if isinstance(token, str) and token.lower() in FORBIDDEN_OUTCOME_FIELD_NAMES:
            errors.append(
                f"{where}: {attr}={token!r} looks like an Evidence/outcome field, forbidden in a "
                f"runtime signal condition (SS72, TEST 18-20)"
            )
    holds_labels = getattr(condition, "holds_labels", None) or ()
    for lbl in holds_labels:
        if isinstance(lbl, str) and lbl.lower() in FORBIDDEN_OUTCOME_FIELD_NAMES:
            errors.append(f"{where}: holds_labels contains {lbl!r}, forbidden outcome field (SS72)")


def validate_for_preregistration(
    hypothesis: StrategyHypothesis, variants: tuple[StrategyVariant, ...],
    registry: HypothesisRegistry, hypothesis_config: dict, run_registry: EvaluationRunRegistry,
) -> tuple[bool, tuple[str, ...]]:
    errors: list[str] = []

    expected_fp = hypothesis_fingerprint(
        hypothesis.parent_signature_id, hypothesis.direction, hypothesis.entry_definition,
        hypothesis.entry_execution_policy, hypothesis.horizon_candidate_set,
        hypothesis.evidence_provenance, hypothesis.strategy_config_version,
    )
    expected_hypothesis_id, expected_definition_hash = build_hypothesis_id(expected_fp)
    if hypothesis.hypothesis_id != expected_hypothesis_id or hypothesis.definition_hash != expected_definition_hash:
        errors.append(
            f"hypothesis_id={hypothesis.hypothesis_id!r}/definition_hash={hypothesis.definition_hash!r} "
            f"do not match the content-addressed fingerprint of this hypothesis's own fields "
            f"(expected hypothesis_id={expected_hypothesis_id!r}, definition_hash="
            f"{expected_definition_hash!r}) -- ids are content-addressed and must never be supplied "
            f"by hand (PATCH #004-B finding #2, TEST 63)"
        )

    for v in variants:
        expected_variant_fp = variant_fingerprint(expected_definition_hash, v.exit_hypothesis)
        expected_variant_id, expected_variant_hash = build_variant_id(expected_variant_fp)
        if v.strategy_variant_id != expected_variant_id or v.variant_definition_hash != expected_variant_hash:
            errors.append(
                f"variant {v.strategy_variant_id!r}: strategy_variant_id/variant_definition_hash="
                f"{v.variant_definition_hash!r} do not match the content-addressed fingerprint of its "
                f"own exit_hypothesis against the parent's TRUE definition_hash (expected "
                f"strategy_variant_id={expected_variant_id!r}, variant_definition_hash="
                f"{expected_variant_hash!r}) -- PATCH #004-B finding #2, TEST 63"
            )

    if hypothesis.direction not in (Direction.LONG.value, Direction.SHORT.value):
        errors.append(f"direction {hypothesis.direction!r} is not a valid Direction (TEST 4)")

    if not hypothesis.evidence_provenance.timeframe:
        errors.append("evidence_provenance.timeframe is required (TEST 41)")

    provenance_ok, provenance_errors = check_provenance_matches_run(hypothesis.evidence_provenance, run_registry)
    if not provenance_ok:
        errors.extend(provenance_errors)

    if hypothesis.parent_signature_id != hypothesis.evidence_provenance.signature_id:
        errors.append(
            f"hypothesis.parent_signature_id={hypothesis.parent_signature_id!r} does not match "
            f"hypothesis.evidence_provenance.signature_id={hypothesis.evidence_provenance.signature_id!r} "
            f"(PATCH #004-A finding #2 -- budget accounting must key on the same signature the "
            f"evidence actually rests on, TEST 56)"
        )
    if hypothesis.signature_set_id != hypothesis.evidence_provenance.signature_set_id:
        errors.append(
            f"hypothesis.signature_set_id={hypothesis.signature_set_id!r} does not match "
            f"hypothesis.evidence_provenance.signature_set_id={hypothesis.evidence_provenance.signature_set_id!r} "
            f"(PATCH #004-A finding #2, TEST 56)"
        )

    if not hypothesis.horizon_candidate_set.values:
        errors.append("horizon_candidate_set.values must not be empty (TEST 11)")

    if not variants:
        errors.append(
            "no StrategyVariant supplied -- at least the TIME_EXIT family must already be "
            "materialized before PREREGISTERED (SS104-109)"
        )

    variant_ids = {v.strategy_variant_id for v in variants}
    if set(hypothesis.variant_ids) != variant_ids:
        errors.append(
            f"hypothesis.variant_ids {sorted(hypothesis.variant_ids)} does not match the supplied "
            f"variants {sorted(variant_ids)} -- variants must be materialized BEFORE freeze, never "
            f"added or removed afterward (SS106-109, TEST 28)"
        )

    for c in hypothesis.entry_definition.core_conditions + hypothesis.entry_definition.confirmation_conditions:
        _scan_condition_for_outcome_contamination(c, "entry_definition", errors)

    for v in variants:
        if v.exit_hypothesis.exit_family not in (ExitFamily.TIME_EXIT.value, ExitFamily.SIGNAL_INVALIDATION.value):
            errors.append(f"variant {v.strategy_variant_id!r} has invalid exit_family {v.exit_hypothesis.exit_family!r} (TEST 15)")
        if v.exit_hypothesis.exit_family == ExitFamily.SIGNAL_INVALIDATION.value and v.exit_hypothesis.max_holding_bars is None:
            errors.append(
                f"variant {v.strategy_variant_id!r}: SIGNAL_INVALIDATION requires max_holding_bars "
                f"(Radu's SS110-B -- no unbounded holding period)"
            )
        for ic in v.exit_hypothesis.invalidation_conditions:
            _scan_condition_for_outcome_contamination(ic, f"variant {v.strategy_variant_id}.invalidation_conditions", errors)

    has_time_exit = any(v.exit_hypothesis.exit_family == ExitFamily.TIME_EXIT.value for v in variants)
    if variants and not has_time_exit:
        errors.append("TIME_EXIT is the mandatory baseline exit family (SS24) -- no variant found for it")

    same_signature_families = [
        h for h in registry.all_hypotheses()
        if h.parent_signature_id == hypothesis.parent_signature_id
        and h.hypothesis_id != hypothesis.hypothesis_id
        and h.status in (HypothesisStatus.PREREGISTERED.value, HypothesisStatus.HANDOFF_TO_BACKTEST.value)
    ]
    max_per_sig = hypothesis_config["hypothesis_budget"]["max_hypotheses_per_signature"]
    if len(same_signature_families) + 1 > max_per_sig:
        errors.append(
            f"parent_signature_id={hypothesis.parent_signature_id!r} would have "
            f"{len(same_signature_families) + 1} PREREGISTERED hypotheses, exceeds "
            f"max_hypotheses_per_signature={max_per_sig} (SS52)"
        )

    return (not errors, tuple(errors))
