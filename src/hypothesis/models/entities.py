"""Spec #004 v1.0 -- Hypothesis Generation & Strategy Definition models.

#004 turns Evaluation (Spec #003) evidence into explicit, frozen, testable
hypotheses. It is OUTCOME-AWARE FOR HYPOTHESIS FORMATION but NOT A
BACKTESTER (Spec #004 SS2): it may read already-computed EvidenceProfiles,
never raw future returns, never Locked OOS, never PIT/price history.

Two levels, per Radu's final approved decision on SS110-C/D (2026-09-25):
`StrategyHypothesis` is the FAMILY -- everything COMMON to a set of
variants (direction, entry, entry execution, evidence provenance).
`StrategyVariant` is the per-exit materialization, created EAGERLY at
preregistration time, never lazily by #005. The spec text (SS7, SS104-107)
originally sketched an intermediate `StrategyFamily` on top of
`StrategyHypothesis`; Radu's final diagram collapses that into exactly two
levels, so `StrategyHypothesis` here *is* the family record -- documented
explicitly (see docs/spec004_architecture.md), not silently renamed.

No field on any entity here may collapse into a HypothesisScore/AlphaScore
(SS60 forbids it, same discipline as Spec #003 SS49) -- support/effect/
priority/frequency are always reported separately, never summed/weighted
into one number.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# --------------------------------------------------------------------------
# Enums / fixed vocabularies
# --------------------------------------------------------------------------

class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class DirectionBasis(str, Enum):
    """Audit trail only (Spec #004 SS10) -- NEVER used for scoring/ranking."""
    EVIDENCE_SIGN = "EVIDENCE_SIGN"
    ECONOMIC_OR_MARKET_RATIONALE = "ECONOMIC_OR_MARKET_RATIONALE"
    AGENT_PROPOSAL = "AGENT_PROPOSAL"
    HUMAN_DECISION = "HUMAN_DECISION"


class ExitFamily(str, Enum):
    TIME_EXIT = "TIME_EXIT"
    SIGNAL_INVALIDATION = "SIGNAL_INVALIDATION"


class ParameterSource(str, Enum):
    """BACKTEST_SELECTED intentionally absent -- Spec #004 SS27: that
    provenance value does not exist yet, #004 never produces it."""
    PRE_SPECIFIED = "PRE_SPECIFIED"
    EVIDENCE_DERIVED = "EVIDENCE_DERIVED"
    HUMAN_DEFINED = "HUMAN_DEFINED"
    AGENT_PROPOSED = "AGENT_PROPOSED"


class HypothesisResearchMode(str, Enum):
    EXPLORATORY_HYPOTHESIS = "EXPLORATORY_HYPOTHESIS"
    PREREGISTERED_STRATEGY = "PREREGISTERED_STRATEGY"


class HypothesisStatus(str, Enum):
    """Spec #004 SS30-31. PREREGISTERED is immutable -- any further change
    creates a new hypothesis_version/id, never an in-place edit (TEST 24/25).
    REJECTED is a terminal status a proposal can reach without ever
    becoming PREREGISTERED; the record is kept, never deleted (SS53)."""
    DRAFT = "DRAFT"
    REVIEWED = "REVIEWED"
    REJECTED = "REJECTED"
    PREREGISTERED = "PREREGISTERED"
    HANDOFF_TO_BACKTEST = "HANDOFF_TO_BACKTEST"


class AgentStance(str, Enum):
    SUPPORT = "SUPPORT"
    OBJECT = "OBJECT"
    ABSTAIN = "ABSTAIN"


class ConsensusStatus(str, Enum):
    """Consensus is agreement on STRUCTURE, never a vote on truth (SS43)."""
    CONSENSUS = "CONSENSUS"
    DISAGREEMENT = "DISAGREEMENT"
    BLOCKED = "BLOCKED"


class VariantTag(str, Enum):
    BASELINE_VARIANT = "BASELINE_VARIANT"
    EXPERIMENTAL_VARIANT = "EXPERIMENTAL_VARIANT"


class ComplexityStatus(str, Enum):
    OK = "OK"
    HYPOTHESIS_COMPLEXITY_EXCEEDED = "HYPOTHESIS_COMPLEXITY_EXCEEDED"


# --------------------------------------------------------------------------
# Fixed V1 constants (Radu's approval on SS110-A, 2026-09-25)
# --------------------------------------------------------------------------

HYPOTHESIS_ENGINE_VERSION = "v1.0.0"

# Only allowed value in V1 -- signal at CLOSE(t), entry at the next regular
# session's open. Fixed now so #005 can never retroactively try
# same-close/next-close/limit/VWAP variants and keep whichever is profitable
# (Spec #004 SS14-16).
ENTRY_EXECUTION_POLICY = "NEXT_BAR_OPEN"

# Only allowed value in V1. TIME_EXIT N means: entry at the open of the
# entry bar: holding bar 1 = entry bar itself; holding bar N = entry bar
# index + (N-1); exit at the CLOSE of holding bar N (Radu's SS110-A
# worked example: Monday close signal -> Tuesday open entry -> holding bars
# Tue/Wed/Thu -> Thursday close exit for N=3). Deliberately ONE BAR off
# from Spec #003's own horizon_bars semantics (close(signal) -> close(signal+h)),
# because #003 measures from the SIGNAL bar while #004/#005 measure
# holding duration from the EXECUTABLE ENTRY bar -- see
# `evidence_horizon_bars` vs `strategy_holding_bars` in EvidencePacket/
# ExitHypothesis docstrings below, and docs/spec004_architecture.md.
HORIZON_REFERENCE_POINT = "ENTRY_BAR"

# Only allowed value in V1 (Radu's SS110-B addendum).
EXIT_EXECUTION_POLICY = "BAR_CLOSE"


# --------------------------------------------------------------------------
# Entry vocabulary -- deliberately OWN types, not reused from
# evaluation.models.entities (Spec #004 mirrors the DiscoveryObservation/
# DiscoveryCandidate precedent: identical shape, deliberately distinct
# type, so a signature-matching condition used to compute Evidence can
# never be silently confused with a hypothesis's own runtime entry/exit
# vocabulary). Both are validated against the SAME underlying Discovery
# vocabulary (states.yaml lanes/labels, discovery.candidate.reason_codes.
# ReasonCode) at proposal-validation time -- see proposals/validator.py.
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class LaneStateCondition:
    """Entry-side: matches DiscoveryObservation.state_signature[lane] ==
    label exactly. `negate` must be False for every ENTRY condition
    (validator-enforced, SS8/SS9: a direction is never derived by negating
    another); it exists on this type only so ExitHypothesis's
    invalidation vocabulary can stay structurally identical to entry's."""
    lane: str
    label: str
    negate: bool = False


@dataclass(frozen=True)
class ReasonCodeCondition:
    """Matches `reason_code in DiscoveryObservation.reason_codes`."""
    reason_code: str
    negate: bool = False


@dataclass(frozen=True)
class EntryDefinition:
    """Spec #004 SS11-13: AND-combination of `core_conditions` (the
    thesis itself, capped by `hypothesis_complexity.max_entry_conditions`)
    plus optional `confirmation_conditions` (an additional, separately
    budget-capped AND layer -- Level 1 design choice: the spec's
    `max_optional_confirmation_conditions` guardrail doesn't itself define
    the semantic difference between "core" and "confirmation"; V1 treats
    both as required-AND but tracks them under separate budget counters
    for audit/complexity-review purposes). Every condition must reference
    an approved Discovery field (SS11) -- validator-enforced, never
    trusted by construction."""
    core_conditions: tuple["LaneStateCondition | ReasonCodeCondition", ...]
    confirmation_conditions: tuple["LaneStateCondition | ReasonCodeCondition", ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class HorizonCandidateSet:
    """Spec #004 SS17-20: the WHOLE family of horizons considered, frozen
    together -- #004 never auto-selects one. `selection_basis` is a
    human/agent-written description of why this range was proposed (e.g.
    "Development evidence decay concentrated in the 2-5 bar zone"), never
    a claim that any one value is optimal."""
    unit: str  # "BARS" -- only allowed value V1
    values: tuple[int, ...]
    selection_basis: str


@dataclass(frozen=True)
class InvalidationCondition:
    """One SIGNAL_INVALIDATION trigger, restricted to the SAME approved
    #002 vocabulary as entry conditions (SS22B/SS25) -- never a new
    indicator. Exactly one of the two condition kinds must be populated
    (validator-enforced):

    Lane-based (`lane` set): invalidates when the observed lane label is
    NOT one of `holds_labels` ("RS no longer HIGH/VERY_HIGH" ->
    lane="relative_strength", holds_labels=("HIGH","VERY_HIGH")).

    Reason-code-based (`reason_code` set): invalidates when that reason
    code's presence flips relative to entry -- newly appears
    (`triggers_on_presence=True`, e.g. STATE_TRANSITION) or disappears
    (`triggers_on_presence=False`, e.g. MOMENTUM_ACCELERATION no longer
    present) -- Spec #004 SS22B's "momentum transition turns negative"
    example, expressed without inventing a new indicator.
    """
    lane: Optional[str] = None
    holds_labels: Optional[tuple[str, ...]] = None
    reason_code: Optional[str] = None
    triggers_on_presence: Optional[bool] = None


@dataclass(frozen=True)
class ExitHypothesis:
    """Spec #004 SS21-26, restructured per Radu's SS110 final decision.
    One CONCRETE exit per StrategyVariant -- never a candidate family
    (that lives one level up, on HorizonCandidateSet for TIME_EXIT, and is
    expanded into one ExitHypothesis per StrategyVariant at freeze time).

    `time_exit_bars` populated iff exit_family == TIME_EXIT: the strategy
    exits at the CLOSE of holding bar `time_exit_bars`, counted from the
    ENTRY bar per `horizon_reference_point` (see HORIZON_REFERENCE_POINT
    docstring above) -- this is `strategy_holding_bars`, deliberately a
    different number line from Spec #003's `evidence_horizon_bars`.

    `max_holding_bars` is REQUIRED (validator-enforced) whenever
    exit_family == SIGNAL_INVALIDATION (Radu's SS110-B addendum): exit
    fires on invalidation OR at the close of `max_holding_bars`, whichever
    happens first -- an unbounded "hold until RS deteriorates" position is
    never allowed in the Fast-Swing domain. Anti-lookahead: invalidation
    evaluated at bar close can only produce a fill at or after that same
    close, never earlier (#005's responsibility to enforce at execution
    time; #004 only freezes the rule)."""
    exit_family: str  # ExitFamily
    horizon_reference_point: str  # HORIZON_REFERENCE_POINT -- "ENTRY_BAR" only
    exit_execution_policy: str  # EXIT_EXECUTION_POLICY -- "BAR_CLOSE" only
    parameter_source: str  # ParameterSource

    time_exit_bars: Optional[int] = None
    invalidation_conditions: tuple[InvalidationCondition, ...] = field(default_factory=tuple)
    max_holding_bars: Optional[int] = None


# --------------------------------------------------------------------------
# Provenance
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class EvidenceProvenance:
    """Spec #004 SS33-34: exact evidence lineage a hypothesis rests on. If
    Evaluation's config/engine changes, the OLD hypothesis stays bound to
    the old provenance (never silently re-pointed) -- a new interpretation
    under a new config is a NEW hypothesis (SS34)."""
    evaluation_run_id: str
    evaluation_engine_version: str
    evaluation_config_version: str

    signature_id: str
    signature_set_id: str

    discovery_engine_version: str
    discovery_config_version: str

    timeframe: str


@dataclass(frozen=True)
class HypothesisProvenance:
    """Who/what produced and approved this hypothesis (SS86-87). Source of
    truth for reproducibility is this STRUCTURED record, never a claim of
    being able to regenerate identical LLM free text (SS87)."""
    proposer: str  # e.g. "HUMAN:radu", "AGENT:claude", "AGENT:gpt"
    proposal_id: Optional[str]
    consensus_status: Optional[str]  # ConsensusStatus, None if no agent review occurred
    approved_by: str  # human approver -- always required, SS46
    approved_at: str


@dataclass(frozen=True)
class HypothesisComplexitySnapshot:
    """`constraints` field of StrategyHypothesis (SS7) -- the complexity/
    budget config IN EFFECT at creation time, frozen into the record so a
    later config edit never retroactively reinterprets an existing
    hypothesis's own guardrails."""
    max_entry_conditions: int
    max_optional_confirmation_conditions: int
    hypothesis_config_version: str


# --------------------------------------------------------------------------
# StrategyHypothesis (== the family, Radu's SS110-C/D final decision) and
# StrategyVariant (per-exit, materialized eagerly at freeze time)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class StrategyHypothesis:
    """The FAMILY-level record: everything COMMON to every variant sharing
    this direction+entry+execution+evidence (Radu's SS110-D rule: a
    different `direction` or different `entry_definition` is always a
    DIFFERENT StrategyHypothesis, never a variant of this one).

    `variant_ids` is populated EAGERLY, in full, at the moment this record
    is created with status=PREREGISTERED -- #005 must never dynamically
    create a missing variant; every id in `horizon_candidate_set.values`
    (for TIME_EXIT) plus every distinct SIGNAL_INVALIDATION variant
    proposed must already have a matching StrategyVariant before this
    hypothesis can reach PREREGISTERED (validation/rules.py enforces this).

    `definition_hash` covers only fields that define TRADING MEANING
    (direction, entry, execution policy, timeframe, horizon semantics,
    evidence/config provenance) -- Radu's SS110-E: administrative
    timestamps (`created_at`, `approved_at`) are explicitly EXCLUDED so
    the hash represents the strategy's economic identity, not its
    paperwork history."""
    hypothesis_id: str
    hypothesis_version: int
    definition_hash: str

    status: str  # HypothesisStatus
    research_mode: str  # HypothesisResearchMode

    parent_signature_id: str
    signature_set_id: str

    direction: str  # Direction
    direction_basis: str  # DirectionBasis

    entry_definition: EntryDefinition
    entry_execution_policy: str  # ENTRY_EXECUTION_POLICY

    horizon_candidate_set: HorizonCandidateSet

    variant_ids: tuple[str, ...]

    evidence_provenance: EvidenceProvenance
    hypothesis_provenance: HypothesisProvenance
    constraints: HypothesisComplexitySnapshot

    created_at: str
    created_by: str

    strategy_config_version: str  # hypothesis_config_version, kept under Spec #004's own field name for the registry contract

    supersedes_hypothesis_id: Optional[str] = None


@dataclass(frozen=True)
class StrategyVariant:
    """One concrete, fully-specified exit attached to a StrategyHypothesis
    family (SS104-109). `variant_definition_hash` covers the parent's
    `definition_hash` PLUS this variant's own `exit_hypothesis` -- so a
    changed exit always changes the variant's identity (TEST 22) without
    needing to change the parent family's own hash."""
    strategy_variant_id: str
    parent_hypothesis_id: str
    variant_definition_hash: str

    exit_hypothesis: ExitHypothesis
    variant_tag: str  # VariantTag

    created_at: str


@dataclass(frozen=True)
class StrategyDefinition:
    """Spec #004 SS63-67 -- the terminal, tradeable artifact for ONE
    variant, produced only once its parent hypothesis AND this variant
    are PREREGISTERED. `universe_policy` deliberately never a static
    ticker list (SS64-65: no ticker cherry-picking after seeing outcomes)
    -- it names the Discovery eligibility mechanism instead. Placeholders
    are explicit, not silently omitted (SS23/SS79-81: risk/sizing/execution
    remain out of scope for #004/#005-v1)."""
    strategy_id: str
    hypothesis_id: str
    strategy_variant_id: str

    market: str
    timeframe: str
    universe_policy: str

    direction: str
    signal_definition: EntryDefinition
    entry_execution_policy: str

    exit_definition: ExitHypothesis

    status: str  # "PREREGISTERED"

    position_policy_placeholder: str = "NOT_DEFINED_YET"
    execution_assumptions_placeholder: str = "NOT_DEFINED_YET"


# --------------------------------------------------------------------------
# Proposal / Review / Consensus (SS35-50)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class HypothesisProposal:
    """Spec #004 SS48 -- structured input from a human OR an AI agent (the
    core never distinguishes by source, SS93/SS110-G). `facts_from_evidence`
    and `interpretation` are kept in SEPARATE fields on purpose (SS49-50):
    the former must be literal, checkable statements about EvidenceProfile
    fields; the latter is narrative reasoning and is never treated as a
    demonstrated fact."""
    proposal_id: str
    source_evidence: EvidenceProvenance

    direction: str
    direction_basis: str

    entry_definition: EntryDefinition
    entry_execution_policy: str

    horizon_candidates: HorizonCandidateSet
    # SIGNAL_INVALIDATION variants ONLY (Level 1 design choice): the
    # mandatory TIME_EXIT family (SS24) is always auto-derived from
    # `horizon_candidates.values` at materialize_variants() time, one
    # ExitHypothesis per value -- a proposal never needs to enumerate
    # TIME_EXIT individually, and proposals/validator.py rejects any
    # entry here whose exit_family != SIGNAL_INVALIDATION.
    exit_hypotheses: tuple[ExitHypothesis, ...]

    facts_from_evidence: tuple[str, ...]
    interpretation: str
    counterarguments: tuple[str, ...]
    known_failure_modes: tuple[str, ...]

    proposer: str
    created_at: str


@dataclass(frozen=True)
class AgentReview:
    """Spec #004 SS44. `model_id` may be a real model identifier or a
    manual-relay marker (e.g. "manual-relay:gpt") -- the core does not
    care which, per SS93."""
    agent_id: str
    model_id: str
    hypothesis_proposal_id: str
    stance: str  # AgentStance
    objections: tuple[str, ...]
    suggested_changes: tuple[str, ...]
    timestamp: str


@dataclass(frozen=True)
class ConsensusRecord:
    """Spec #004 SS45-46. `human_decision` is None until Radu (or another
    designated human) records one; `consensus_status` ALONE can never
    move a proposal to PREREGISTERED (validator-enforced, TEST 30-31)."""
    proposal_id: str
    reviews: tuple[AgentReview, ...]
    consensus_status: str  # ConsensusStatus
    unresolved_objections: tuple[str, ...]
    human_decision: Optional[str] = None


@dataclass(frozen=True)
class FutureResearchNote:
    """Spec #004 SS84-85 -- an idea an agent raised (e.g. "a volatility-
    scaled protective stop should be studied") that must NOT become part
    of any StrategyHypothesis/ExitHypothesis without its own dedicated
    research step."""
    note_id: str
    topic: str
    rationale: str
    trigger_for_future_spec: str
    source_agent: str
    created_at: str


# --------------------------------------------------------------------------
# EvidencePacket -- the compact, token-bounded artifact handed to an agent
# (SS38-40). Built ONLY from already-materialized #003 outputs; never
# holds raw OHLCV or a PIT connection (SS5/SS39).
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class DecayPoint:
    """One point on the #003 decay curve, carried through unmodified
    (Spec #004 must never auto-pick a "best" horizon from this -- SS12/34,
    TEST 12). `horizon_bars` here is `evidence_horizon_bars` (Spec #003
    close(signal)->close(signal+h)), NOT `strategy_holding_bars` -- see
    ExitHypothesis docstring for why these are two different number lines."""
    evidence_horizon_bars: int
    mean_relative_return: Optional[float]
    median_relative_return: Optional[float]
    valid_episode_n: int
    adjusted_p: Optional[float]


@dataclass(frozen=True)
class EvidencePacket:
    """Spec #004 SS39-40 -- built from exactly three #003 artifacts
    (EvaluationSignatureDefinition + EvidenceProfile(s) + Evaluation
    RunRegistry, per Radu's SS110-F confirmation), never from a live PIT
    connection. Flat/primitive fields on purpose: keeps the packet compact
    for an LLM prompt (target ~1-3KB, SS40), and makes the outcome-
    contamination boundary (SS72) trivial to scan for by field name."""
    signature_id: str
    entry_conditions_summary: tuple[str, ...]
    timeframe: str

    evidence_provenance: EvidenceProvenance

    decay_curve: tuple[DecayPoint, ...]

    primary_evidence_horizon_bars: int
    primary_support_status: str
    primary_valid_episode_n: int
    primary_unique_security_count: int
    primary_largest_security_share: Optional[float]
    primary_episodes_per_20_sessions: Optional[float]
    primary_episodes_per_60_sessions: Optional[float]
    primary_absolute_mean: Optional[float]
    primary_relative_mean: Optional[float]
    primary_relative_median: Optional[float]
    primary_baseline_median: Optional[float]
    primary_standardized_effect: Optional[float]
    primary_adjusted_p: Optional[float]

    warnings: tuple[str, ...] = field(default_factory=tuple)


# --------------------------------------------------------------------------
# Research Queue (SS56-62) -- ELIGIBLE_FOR_REVIEW strictly separate from
# outcome-aware REVIEW_PRIORITY.
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ResearchQueueEntry:
    """`eligible` uses ONLY data-quality fields (support/missingness/
    stability) -- never `adjusted_p`/effect size (SS57-59). `priority_basis`
    is ALWAYS the literal string "DEVELOPMENT_OUTCOME_AWARE_SELECTION"
    whenever `review_priority_key` is populated (Radu's SS110-H guard) and
    "NOT_APPLICABLE" otherwise -- this field, and everything it is derived
    from, must never appear inside a StrategyDefinition (TEST 34)."""
    signature_id: str
    evidence_horizon_bars: int
    evaluation_run_id: str

    eligible: bool
    eligibility_basis: tuple[str, ...]
    eligibility_config_version: str

    review_priority_rank: Optional[int]
    review_priority_key: Optional[tuple]
    priority_basis: str


@dataclass(frozen=True)
class HypothesisUniverse:
    """Spec #004 SS54-55 -- accounting for ONE research cycle. Rejected/
    superseded proposals are kept here forever, never deleted (SS53/SS108):
    "we considered 40, preregistered 3" must remain provable."""
    universe_id: str
    all_proposals: tuple[str, ...]
    all_rejected: tuple[str, ...]
    all_preregistered: tuple[str, ...]
    selection_policy: str
