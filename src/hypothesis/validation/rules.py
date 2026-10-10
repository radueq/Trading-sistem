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

Stage 6 -- Finding 15 (GPT-G2), joint remediation design 003+004
section 10, complete contract: (i) exactly one TIME_EXIT variant per
`horizon_candidate_set.values` entry, no fewer and no more -- the
pre-Stage-6 check only compared two caller-controlled id sets, so a
missing OR an extra TIME_EXIT variant passed; (ii) every variant unique
by its FULL content fingerprint (`variant_fingerprint()`, never a
hand-picked field subset), so any number of SIGNAL_INVALIDATION/
STOP_MANAGED_INVALIDATION variants is allowed as long as none repeats;
(iii) exit semantics validated per variant: `time_exit_bars` a positive
integer for TIME_EXIT, `horizon_reference_point`/`exit_execution_policy`
equal to the config's single V1 value -- previously plain, unchecked
strings at this gate.
"""
from __future__ import annotations

import math
from collections import Counter

from evaluation.models.entities import EvaluationRunRegistry

from hypothesis.models.entities import (
    Direction,
    ExitFamily,
    ExitHypothesis,
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


def _check_stop_managed_invalidation_exit(variant_id: str, ex: ExitHypothesis, errors: list[str]) -> None:
    """PATCH #004-C / Spec #005 Exit Amendment v1.0 (ACCEPTED, section 1) --
    structural validation for the additive STOP_MANAGED_INVALIDATION family.
    No automatic time-based exit (Radu's explicit design decision, distinct
    from and narrower than SS110-B's own no-unbounded-hold rule for
    SIGNAL_INVALIDATION): `max_holding_bars`/`time_exit_bars` are forbidden
    here, never required."""
    if ex.stop_loss is None:
        errors.append(f"variant {variant_id!r}: STOP_MANAGED_INVALIDATION requires stop_loss (PATCH #004-C)")
    else:
        if ex.stop_loss.basis != "ATR_TRAILING_V1":
            errors.append(
                f"variant {variant_id!r}: stop_loss.basis must be 'ATR_TRAILING_V1', got "
                f"{ex.stop_loss.basis!r} (PATCH #004-C, only allowed value V1)"
            )
        if not (math.isfinite(ex.stop_loss.atr_multiple) and ex.stop_loss.atr_multiple > 0):
            errors.append(
                f"variant {variant_id!r}: stop_loss.atr_multiple must be a finite number > 0, got "
                f"{ex.stop_loss.atr_multiple!r}"
            )
    if ex.partial_profit is not None:
        if not (math.isfinite(ex.partial_profit.r_multiple) and ex.partial_profit.r_multiple > 0):
            errors.append(
                f"variant {variant_id!r}: partial_profit.r_multiple must be a finite number > 0, got "
                f"{ex.partial_profit.r_multiple!r}"
            )
        if not (math.isfinite(ex.partial_profit.fraction) and 0 < ex.partial_profit.fraction < 1):
            errors.append(
                f"variant {variant_id!r}: partial_profit.fraction must satisfy 0 < fraction < 1, got "
                f"{ex.partial_profit.fraction!r}"
            )
    if ex.max_holding_bars is not None:
        errors.append(
            f"variant {variant_id!r}: max_holding_bars must be None for STOP_MANAGED_INVALIDATION -- "
            f"no automatic time-based exit (Radu's explicit design decision, PATCH #004-C)"
        )
    if ex.time_exit_bars is not None:
        errors.append(f"variant {variant_id!r}: time_exit_bars must be None for STOP_MANAGED_INVALIDATION")
    if not ex.invalidation_conditions:
        errors.append(
            f"variant {variant_id!r}: STOP_MANAGED_INVALIDATION requires at least one "
            f"invalidation_conditions entry, written explicitly at freeze time (PATCH #004-C -- "
            f"never auto-copied from the entry definition)"
        )


def _check_variant_completeness_uniqueness_semantics(
    hypothesis: StrategyHypothesis, variants: tuple[StrategyVariant, ...], true_definition_hash: str,
    hypothesis_config: dict, errors: list[str],
) -> None:
    """Stage 6 -- Finding 15 (GPT-G2), parts (i)-(iii) of the module
    docstring's contract."""
    # (i) completeness, BOTH directions: one TIME_EXIT per candidate value.
    time_exit_bars = Counter(
        v.exit_hypothesis.time_exit_bars for v in variants
        if v.exit_hypothesis.exit_family == ExitFamily.TIME_EXIT.value
    )
    expected_bars = set(hypothesis.horizon_candidate_set.values)
    missing = sorted(expected_bars - set(time_exit_bars), key=repr)
    extra = sorted(set(time_exit_bars) - expected_bars, key=repr)
    repeated = sorted((b for b, n in time_exit_bars.items() if n > 1), key=repr)
    if missing:
        errors.append(
            f"no TIME_EXIT variant for horizon_candidate_set value(s) {missing!r} -- exactly one TIME_EXIT "
            f"variant per candidate value is required, none may be missing (Stage 6, Finding 15)"
        )
    if extra:
        errors.append(
            f"TIME_EXIT variant(s) for time_exit_bars {extra!r} not in horizon_candidate_set.values="
            f"{sorted(expected_bars)!r} -- no TIME_EXIT variant may exist outside the declared "
            f"candidate set (Stage 6, Finding 15)"
        )
    if repeated:
        errors.append(
            f"more than one TIME_EXIT variant for time_exit_bars {repeated!r} -- exactly one per "
            f"candidate value (Stage 6, Finding 15)"
        )

    # (ii) uniqueness by FULL content fingerprint, recomputed against the
    # parent's TRUE definition_hash (never the hypothesis's own claim).
    fingerprints = Counter(variant_fingerprint(true_definition_hash, v.exit_hypothesis) for v in variants)
    duplicated = sorted(fp for fp, n in fingerprints.items() if n > 1)
    if duplicated:
        errors.append(
            f"{len(duplicated)} variant content fingerprint(s) occur more than once in this batch -- every "
            f"variant must be unique by its FULL variant_fingerprint() (Stage 6, Finding 15): "
            f"{duplicated!r}"
        )

    # (iii) exit semantics, per variant.
    required_reference_point = hypothesis_config["horizon_reference_point"]
    required_exit_execution = hypothesis_config["exit_execution_policy"]
    for v in variants:
        ex = v.exit_hypothesis
        if ex.horizon_reference_point != required_reference_point:
            errors.append(
                f"variant {v.strategy_variant_id!r}: horizon_reference_point={ex.horizon_reference_point!r}, "
                f"must be {required_reference_point!r} (Stage 6, Finding 15)"
            )
        if ex.exit_execution_policy != required_exit_execution:
            errors.append(
                f"variant {v.strategy_variant_id!r}: exit_execution_policy={ex.exit_execution_policy!r}, "
                f"must be {required_exit_execution!r} (Stage 6, Finding 15)"
            )
        if ex.exit_family == ExitFamily.TIME_EXIT.value and not (
            isinstance(ex.time_exit_bars, int) and not isinstance(ex.time_exit_bars, bool) and ex.time_exit_bars > 0
        ):
            errors.append(
                f"variant {v.strategy_variant_id!r}: TIME_EXIT time_exit_bars={ex.time_exit_bars!r} must be a "
                f"positive integer number of bars (Stage 6, Finding 15)"
            )


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
        ex = v.exit_hypothesis
        if ex.exit_family not in (
            ExitFamily.TIME_EXIT.value, ExitFamily.SIGNAL_INVALIDATION.value,
            ExitFamily.STOP_MANAGED_INVALIDATION.value,
        ):
            errors.append(f"variant {v.strategy_variant_id!r} has invalid exit_family {ex.exit_family!r} (TEST 15)")
        if ex.exit_family == ExitFamily.SIGNAL_INVALIDATION.value and ex.max_holding_bars is None:
            errors.append(
                f"variant {v.strategy_variant_id!r}: SIGNAL_INVALIDATION requires max_holding_bars "
                f"(Radu's SS110-B -- no unbounded holding period)"
            )
        if ex.exit_family in (ExitFamily.TIME_EXIT.value, ExitFamily.SIGNAL_INVALIDATION.value):
            if ex.stop_loss is not None or ex.partial_profit is not None:
                errors.append(
                    f"variant {v.strategy_variant_id!r}: stop_loss/partial_profit must be None for "
                    f"{ex.exit_family!r} -- these fields are scoped exclusively to "
                    f"STOP_MANAGED_INVALIDATION (PATCH #004-C, SS79-81 derogation is strictly "
                    f"family-conditioned, never a free field on the old families)"
                )
        elif ex.exit_family == ExitFamily.STOP_MANAGED_INVALIDATION.value:
            _check_stop_managed_invalidation_exit(v.strategy_variant_id, ex, errors)
        for ic in v.exit_hypothesis.invalidation_conditions:
            _scan_condition_for_outcome_contamination(ic, f"variant {v.strategy_variant_id}.invalidation_conditions", errors)

    _check_variant_completeness_uniqueness_semantics(
        hypothesis, variants, expected_definition_hash, hypothesis_config, errors,
    )

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
