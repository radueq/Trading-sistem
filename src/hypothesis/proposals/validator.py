"""Spec #004 SS6-13/SS17-22/SS71-72 -- structural validation of a
HypothesisProposal, run at INGESTION time (before any AgentReview/
consensus step, and before validation/rules.py's later pre-preregistration
checks, which need registry/provenance context this module deliberately
does not).

Checks here are all DETERMINISTIC and derivable from the proposal plus
two config objects: entry/invalidation conditions restricted to the
approved Discovery vocabulary (states.yaml lanes/labels + ReasonCode
enum -- both pure data/enum imports, zero PIT, per Radu's SS110-F), fixed
V1 execution/exit policies, horizon candidates within `allowed_values`,
and the complexity/budget guardrails (SS12/SS52, HYPOTHESIS_COMPLEXITY_
EXCEEDED status -- never a silent truncation, SS107).
"""
from __future__ import annotations

from dataclasses import dataclass

from discovery.candidate.reason_codes import ReasonCode
from discovery.config.loader import DiscoveryConfig

from hypothesis.config.loader import HypothesisConfig
from hypothesis.models.entities import (
    ComplexityStatus,
    Direction,
    EntryDefinition,
    ExitFamily,
    ExitHypothesis,
    HorizonCandidateSet,
    HypothesisProposal,
    InvalidationCondition,
    LaneStateCondition,
    ParameterSource,
    ReasonCodeCondition,
)


@dataclass(frozen=True)
class ProposalValidationResult:
    """PATCH #004-B finding #1 (GPT Review #004 Round 2): carries
    `proposal_id` so a caller of `preregister_hypothesis()` cannot supply
    a validation result for a DIFFERENT proposal than the one actually
    being preregistered -- before this field existed, nothing tied this
    result back to the proposal it was computed from (TEST 62)."""
    valid: bool
    complexity_status: str  # ComplexityStatus
    errors: tuple[str, ...]
    proposal_id: str


def _lane_label_vocabulary(discovery_states: dict) -> dict[str, set[str]]:
    compression_lanes = set(discovery_states.get("compression_vocabulary_lanes", []))
    percentile_labels = {b["label"] for b in discovery_states["percentile_buckets"]}
    compression_labels = {b["label"] for b in discovery_states["compression_buckets"]}
    lanes: dict[str, set[str]] = {}
    for lane in discovery_states["lane_drivers"]:
        lanes[lane] = compression_labels if lane in compression_lanes else percentile_labels
    return lanes


def _valid_reason_codes() -> set[str]:
    return {rc.value for rc in ReasonCode}


def _check_condition(
    c: "LaneStateCondition | ReasonCodeCondition", lane_vocab: dict[str, set[str]],
    reason_vocab: set[str], allow_negate: bool, where: str, errors: list[str],
) -> None:
    if isinstance(c, LaneStateCondition):
        if c.lane not in lane_vocab:
            errors.append(f"{where}: unknown lane {c.lane!r} -- not an approved #002 lane (TEST 7)")
        elif c.label not in lane_vocab[c.lane]:
            errors.append(f"{where}: lane {c.lane!r} has no label {c.label!r} in the approved vocabulary")
        if c.negate and not allow_negate:
            errors.append(f"{where}: entry conditions must never be negated (SS8/SS9 -- no derived flips)")
    elif isinstance(c, ReasonCodeCondition):
        if c.reason_code not in reason_vocab:
            errors.append(f"{where}: unknown reason_code {c.reason_code!r} -- not an approved #002 reason code (TEST 7)")
        if c.negate and not allow_negate:
            errors.append(f"{where}: entry conditions must never be negated (SS8/SS9 -- no derived flips)")
    else:
        errors.append(f"{where}: unsupported condition type {type(c)!r}")


def _check_entry_definition(
    entry: EntryDefinition, lane_vocab: dict[str, set[str]], reason_vocab: set[str],
    complexity_cfg: dict, errors: list[str],
) -> str:
    for c in entry.core_conditions:
        _check_condition(c, lane_vocab, reason_vocab, allow_negate=False, where="entry.core_conditions", errors=errors)
    for c in entry.confirmation_conditions:
        _check_condition(c, lane_vocab, reason_vocab, allow_negate=False, where="entry.confirmation_conditions", errors=errors)

    complexity_status = ComplexityStatus.OK.value
    if len(entry.core_conditions) == 0:
        errors.append("entry.core_conditions must have at least one condition")
    if len(entry.core_conditions) > complexity_cfg["max_entry_conditions"]:
        complexity_status = ComplexityStatus.HYPOTHESIS_COMPLEXITY_EXCEEDED.value
        errors.append(
            f"entry.core_conditions has {len(entry.core_conditions)}, exceeds "
            f"max_entry_conditions={complexity_cfg['max_entry_conditions']} (SS12/TEST 8)"
        )
    if len(entry.confirmation_conditions) > complexity_cfg["max_optional_confirmation_conditions"]:
        complexity_status = ComplexityStatus.HYPOTHESIS_COMPLEXITY_EXCEEDED.value
        errors.append(
            f"entry.confirmation_conditions has {len(entry.confirmation_conditions)}, exceeds "
            f"max_optional_confirmation_conditions={complexity_cfg['max_optional_confirmation_conditions']}"
        )
    return complexity_status


def _check_horizon_candidates(hs: HorizonCandidateSet, cfg: dict, errors: list[str]) -> None:
    if hs.unit != cfg["horizon_candidates"]["unit"]:
        errors.append(f"horizon_candidates.unit must be {cfg['horizon_candidates']['unit']!r} (TEST 10), got {hs.unit!r}")
    allowed = set(cfg["horizon_candidates"]["allowed_values"])
    if not hs.values:
        errors.append("horizon_candidates.values must not be empty")
    extra = set(hs.values) - allowed
    if extra:
        errors.append(f"horizon_candidates.values {sorted(extra)} not in allowed_values={sorted(allowed)} (TEST 11)")
    if not hs.selection_basis or not hs.selection_basis.strip():
        errors.append("horizon_candidates.selection_basis is required (SS20 -- provenance for WHY this range)")
    valid_parameter_sources = {p.value for p in ParameterSource}
    if hs.parameter_source not in valid_parameter_sources:
        errors.append(
            f"horizon_candidates.parameter_source {hs.parameter_source!r} is not a recognized "
            f"ParameterSource (PATCH #004-A finding #5) -- must be one of {sorted(valid_parameter_sources)!r}"
        )


def _check_invalidation_condition(ic: InvalidationCondition, lane_vocab: dict[str, set[str]], reason_vocab: set[str], errors: list[str]) -> None:
    lane_populated = ic.lane is not None
    reason_populated = ic.reason_code is not None
    if lane_populated == reason_populated:
        errors.append("InvalidationCondition must populate exactly one of (lane, reason_code), never both/neither")
        return
    if lane_populated:
        if ic.lane not in lane_vocab:
            errors.append(f"invalidation lane {ic.lane!r} is not an approved #002 lane")
        elif not ic.holds_labels or any(lbl not in lane_vocab[ic.lane] for lbl in ic.holds_labels):
            errors.append(f"invalidation holds_labels for lane {ic.lane!r} must be non-empty and within the approved vocabulary")
    else:
        if ic.reason_code not in reason_vocab:
            errors.append(f"invalidation reason_code {ic.reason_code!r} is not an approved #002 reason code")
        if ic.triggers_on_presence is None:
            errors.append("invalidation reason_code condition requires triggers_on_presence to be set")


def _check_exit_hypothesis(ex: ExitHypothesis, cfg: dict, lane_vocab: dict, reason_vocab: set, errors: list[str]) -> None:
    if ex.exit_family not in cfg["exit_families"]:
        errors.append(f"exit_family {ex.exit_family!r} not in configured exit_families={cfg['exit_families']} (TEST 15)")
    if ex.horizon_reference_point != cfg["horizon_reference_point"]:
        errors.append(f"horizon_reference_point must be {cfg['horizon_reference_point']!r}, got {ex.horizon_reference_point!r}")
    if ex.exit_execution_policy != cfg["exit_execution_policy"]:
        errors.append(f"exit_execution_policy must be {cfg['exit_execution_policy']!r}, got {ex.exit_execution_policy!r}")

    if ex.exit_family == ExitFamily.SIGNAL_INVALIDATION.value:
        if ex.max_holding_bars is None:
            errors.append(
                "SIGNAL_INVALIDATION requires max_holding_bars (Radu's SS110-B: exit on invalidation "
                "OR the time cap, whichever first -- an unbounded hold is never allowed, TEST 16-adjacent)"
            )
        elif ex.max_holding_bars <= 0:
            errors.append("max_holding_bars must be a positive number of bars")
        if not ex.invalidation_conditions:
            errors.append("SIGNAL_INVALIDATION requires at least one invalidation_conditions entry")
        for ic in ex.invalidation_conditions:
            _check_invalidation_condition(ic, lane_vocab, reason_vocab, errors)
    else:
        errors.append(
            f"HypothesisProposal.exit_hypotheses must only contain SIGNAL_INVALIDATION variants -- "
            f"TIME_EXIT is always auto-derived from horizon_candidates, got exit_family={ex.exit_family!r}"
        )

    if cfg.get("risk_exit", {}).get("enabled") is not False:
        errors.append("risk_exit.enabled must be false in V1 (TEST 16 -- risk exits are out of scope)")


def validate_proposal(
    proposal: HypothesisProposal, discovery_config: DiscoveryConfig, hypothesis_config: HypothesisConfig,
) -> ProposalValidationResult:
    cfg = hypothesis_config.data
    errors: list[str] = []

    if proposal.direction not in cfg["allowed_directions"]:
        errors.append(f"direction {proposal.direction!r} not in allowed_directions={cfg['allowed_directions']} (TEST 4)")
    if proposal.direction not in (Direction.LONG.value, Direction.SHORT.value):
        errors.append(f"direction {proposal.direction!r} is not a recognized Direction value")

    if proposal.entry_execution_policy not in cfg["allowed_entry_execution"]:
        errors.append(
            f"entry_execution_policy {proposal.entry_execution_policy!r} not in "
            f"allowed_entry_execution={cfg['allowed_entry_execution']} (TEST 9)"
        )

    lane_vocab = _lane_label_vocabulary(discovery_config.states)
    reason_vocab = _valid_reason_codes()

    complexity_status = _check_entry_definition(
        proposal.entry_definition, lane_vocab, reason_vocab, cfg["hypothesis_complexity"], errors,
    )

    _check_horizon_candidates(proposal.horizon_candidates, cfg, errors)

    for ex in proposal.exit_hypotheses:
        _check_exit_hypothesis(ex, cfg, lane_vocab, reason_vocab, errors)

    if len(proposal.exit_hypotheses) > cfg["hypothesis_budget"]["max_exit_families_per_hypothesis"] - 1:
        # -1: TIME_EXIT (always present) already occupies one exit-family slot.
        errors.append(
            f"proposal has {len(proposal.exit_hypotheses)} SIGNAL_INVALIDATION exit variant(s), which combined "
            f"with the mandatory TIME_EXIT family exceeds max_exit_families_per_hypothesis="
            f"{cfg['hypothesis_budget']['max_exit_families_per_hypothesis']}"
        )

    total_variants = len(proposal.horizon_candidates.values) + len(proposal.exit_hypotheses)
    if total_variants > cfg["hypothesis_budget"]["max_variants_per_family"]:
        complexity_status = ComplexityStatus.HYPOTHESIS_COMPLEXITY_EXCEEDED.value
        errors.append(
            f"total variant count {total_variants} exceeds max_variants_per_family="
            f"{cfg['hypothesis_budget']['max_variants_per_family']} (SS106-107)"
        )

    if not proposal.facts_from_evidence:
        errors.append("facts_from_evidence must not be empty (SS49-50 -- facts vs interpretation must be separable, TEST 33)")
    if not proposal.interpretation or not proposal.interpretation.strip():
        errors.append("interpretation must not be empty (SS49-50)")

    return ProposalValidationResult(
        valid=not errors, complexity_status=complexity_status, errors=tuple(errors), proposal_id=proposal.proposal_id,
    )
