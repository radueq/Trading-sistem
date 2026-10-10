"""Spec #003 v1.1 -- Outcome-Aware Evaluation Engine models.

Evaluation is outcome-aware; Discovery (Spec #002) remains permanently
outcome-blind (Spec #003 SS10-11). These dataclasses are exactly the
place forward-looking fields ARE allowed -- the mirror image of Spec
#002's models/entities.py, which forbids them structurally.

No field here may collapse into a single combined score (SS49 -- no
EvaluationScore/AlphaScore under any name); descriptive/statistical
fields are reported separately and never summed/weighted together.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class OutcomeStatus(str, Enum):
    VALID = "VALID"
    INSUFFICIENT_FUTURE_DATA = "INSUFFICIENT_FUTURE_DATA"
    CROSSES_LOCKED_OOS = "CROSSES_LOCKED_OOS"
    MISSING_BENCHMARK = "MISSING_BENCHMARK"
    INVALID_INPUT = "INVALID_INPUT"
    # Joint remediation design 003+004, section 1.3; decision registry
    # B2, revision 5; authorized 2026-10-06, Stage 2. Covers BOTH "no
    # bar at the calendar-resolved target session" and "a bar exists at
    # the target session but its own price is None" -- both a data-
    # quality gap at an ALREADY-REACHED session, never conflated with
    # INSUFFICIENT_FUTURE_DATA's own "not yet reached" meaning. Produced
    # only by compute_forward_outcome()'s calendar-aware path (the
    # `calendar=` parameter); the legacy bar-position-based path's own
    # existing INSUFFICIENT_FUTURE_DATA mapping for a None exit price is
    # unchanged.
    DATA_GAP = "DATA_GAP"


class EvaluationMode(str, Enum):
    EXPLORATORY = "EXPLORATORY"
    FORMAL_DEVELOPMENT = "FORMAL_DEVELOPMENT"


class SignatureCreationMode(str, Enum):
    PRE_REGISTERED = "PRE_REGISTERED"
    EXPLORATORY_POST_HOC = "EXPLORATORY_POST_HOC"


class SupportStatus(str, Enum):
    SUFFICIENT = "SUFFICIENT"
    INSUFFICIENT = "INSUFFICIENT"


@dataclass(frozen=True)
class ForwardOutcome:
    """R_{i,t,h} and its benchmark-relative counterpart, for ONE security,
    ONE observation bar, ONE horizon (Spec #003 SS15/SS18/SS20). Research
    measurement (close(t) -> close(t+h)), never claimed to be an
    executable trade P&L (SS17) -- the Backtester (future spec)
    introduces executable entry."""
    security_id: str
    observation_as_of: str
    timeframe: str
    horizon_bars: int

    entry_reference_price: Optional[float]
    exit_reference_price: Optional[float]
    exit_as_of: Optional[str]

    forward_return: Optional[float]
    benchmark_return: Optional[float]
    relative_return: Optional[float]

    outcome_status: str

    development_end: Optional[str]

    outcome_engine_version: str
    config_version: str


@dataclass(frozen=True)
class LaneStateCondition:
    """Matches DiscoveryObservation.state_signature[lane] == label."""
    lane: str
    label: str


@dataclass(frozen=True)
class ReasonCodeCondition:
    """Matches `reason_code in DiscoveryObservation.reason_codes`."""
    reason_code: str


@dataclass(frozen=True)
class EvaluationSignatureDefinition:
    """A signature is a pure AND-combination of conditions over fields
    DiscoveryObservation ALREADY carries (Spec #003 SS25) -- no new
    outcome-aware indicator is ever invented here. `signature_id` and
    every condition are frozen once a `signature_set_id` run starts
    (SS26-27) -- see registry/signatures.py."""
    signature_id: str
    lane_conditions: tuple[LaneStateCondition, ...]
    reason_code_conditions: tuple[ReasonCodeCondition, ...]
    timeframe: str
    discovery_engine_version: str
    discovery_config_version: str
    creation_mode: str  # SignatureCreationMode
    created_before_outcome_evaluation: bool


@dataclass(frozen=True)
class SignatureSet:
    """A frozen, named list of EvaluationSignatureDefinitions tested
    together in one FORMAL_DEVELOPMENT run (Spec #003 SS26): the entire
    multiple-testing universe for that run, no silent post-hoc pruning."""
    signature_set_id: str
    signatures: tuple[EvaluationSignatureDefinition, ...]


@dataclass(frozen=True)
class Episode:
    """Consecutive DiscoveryObservation dates (gap <= max_gap_bars) for
    the same (security_id, signature_id) collapsed into one statistical
    unit (Spec #003 SS30) -- the default REPRESENTATIVE observation
    (config `episode.representative`, default FIRST) is the one whose
    ForwardOutcome the episode-level statistics use."""
    episode_id: str
    security_id: str
    signature_id: str
    member_as_ofs: tuple[str, ...]
    representative_as_of: str


@dataclass(frozen=True)
class ConfidenceInterval:
    lower: Optional[float]
    upper: Optional[float]
    method: str


@dataclass(frozen=True)
class DescriptiveStats:
    """Absolute or relative outcome distribution (Spec #003 SS35)."""
    n: int
    mean: Optional[float]
    median: Optional[float]
    std: Optional[float]
    q10: Optional[float]
    q25: Optional[float]
    q75: Optional[float]
    q90: Optional[float]
    positive_rate: Optional[float]
    confidence_interval: Optional[ConfidenceInterval]


@dataclass(frozen=True)
class SessionMassBin:
    """A2 diagnostic (joint remediation design 003+004 section 3;
    decision registry A2) -- WEIGHTED per-session mass within ONE
    temporal bin of the baseline pool, normalized to sum to `1.0`
    within that bin. `session_mass` sums per-security row WEIGHTS per
    session (the SAME `w_row` the point estimate uses), never a raw
    row-count `Counter` -- see `baseline/universe.py:compute_session_
    mass()`. Purely descriptive, same category as `ConcentrationStats`:
    never consumed by the point estimate, bootstrap, or permutation
    test."""
    bin_label: str
    session_mass: dict  # {as_of: fraction of this bin's weighted mass}


@dataclass(frozen=True)
class BaselineComparison:
    """Signature vs TEMPORALLY_STRATIFIED_ELIGIBLE_BASELINE (Spec #003
    SS33-34/38, Radu's amendment to the original SS33 -- never raw-row
    weighted). raw_p comes from a SEPARATE permutation test, never
    informally derived from a bootstrap CI crossing zero (Radu's explicit
    correction to the original draft). standardized_effect is the robust
    formula median_difference / (baseline_IQR / 1.349); `None` when
    baseline_IQR is ~0 (UNDEFINED_ZERO_SCALE, not a silent division).

    `family_test_count`, `exchangeability_status`, and
    `session_mass_by_bin` were ADDED this round (joint remediation
    design 003+004, Stage 4; decision registry A2/A4/F6) -- all three
    default so every pre-Stage-4 construction site is unaffected.
    `exchangeability_status` is hard-coded `"UNVERIFIED"` by whatever
    function builds this record (`evaluation/engine.py`) -- no V1 code
    path ever produces `"VERIFIED"`; `evidence/queue.py`'s
    `compute_review_priority()` sets `p_key = inf` UNCONDITIONALLY,
    never reading this field at all, so no value it could ever hold
    (including one artificially injected via `dataclasses.replace()`)
    changes ranking."""
    baseline_mean: Optional[float]
    baseline_median: Optional[float]
    mean_difference: Optional[float]
    median_difference: Optional[float]
    mean_difference_ci: Optional[ConfidenceInterval]
    standardized_effect: Optional[float]
    standardized_effect_status: str  # "OK" | "UNDEFINED_ZERO_SCALE"
    raw_p: Optional[float]
    adjusted_p: Optional[float]
    family_id: Optional[str]
    multiple_testing_method: Optional[str]
    family_test_count: Optional[int] = None
    exchangeability_status: str = "UNVERIFIED"
    session_mass_by_bin: tuple[SessionMassBin, ...] = ()


@dataclass(frozen=True)
class ConcentrationStats:
    unique_security_count: int
    largest_security_share_of_episodes: Optional[float]


@dataclass(frozen=True)
class StabilityBinResult:
    bin_label: str  # "early" | "middle" | "late"
    episode_n: int
    unique_securities: int
    mean: Optional[float]
    median: Optional[float]
    mean_relative: Optional[float]
    positive_rate: Optional[float]


@dataclass(frozen=True)
class OpportunityDensity:
    """Descriptive frequency-of-occurrence -- NEVER part of significance
    calculation (Spec #003 SS37)."""
    episode_count: int
    episodes_per_20_sessions: Optional[float]
    episodes_per_60_sessions: Optional[float]
    median_sessions_between_episodes: Optional[float]


@dataclass(frozen=True)
class MissingnessReport:
    eligible_observations: int
    raw_observations: int
    episodes: int
    valid_outcomes: int
    insufficient_future_data: int
    crosses_locked_oos: int
    missing_benchmark: int
    invalid_input: int
    # Joint remediation design 003+004, section 1.3; decision registry
    # B2; authorized 2026-10-06, Stage 2; ADDED this round per GPT's own
    # changes-required review -- DATA_GAP outcomes were silently absent
    # from this report's own reconciliation (missing_outcomes.episodes
    # == sum(every OTHER field) would have failed to hold the moment
    # DATA_GAP-producing outcomes reached this report). Defaults to 0 so
    # every pre-Stage-2 construction site (which never produces
    # DATA_GAP) is unaffected.
    data_gap: int = 0


@dataclass(frozen=True)
class SupportInfo:
    """`episode_n` is the TOTAL episode count (every outcome status);
    `valid_episode_n` is the subset with a usable VALID relative_return
    outcome -- the population the formal comparison/effect-size/p-value
    actually run on. `support_status` gates on `valid_episode_n` and
    `unique_security_count` (also computed over that same valid
    population), never on the raw total (GPT Review #003 Round 1,
    finding #5): a signature with 35 total episodes but only 12 VALID
    relative outcomes must not silently read as SUFFICIENT_SUPPORT
    against a threshold of 30. `episode_n` stays available for
    reconciliation against `missingness.episodes`."""
    raw_n: int
    episode_n: int
    valid_episode_n: int
    unique_security_count: int
    support_status: str  # SupportStatus


@dataclass(frozen=True)
class EvidenceProfile:
    """Spec #003 SS50 -- the terminal output. Factual support status only
    (SS51): SUFFICIENT_SUPPORT / INSUFFICIENT_SUPPORT, never GOOD/BAD/
    TRADE/EDGE_CONFIRMED/WINNER. No field anywhere aggregates into a
    single score (SS49)."""
    signature_id: str
    timeframe: str
    horizon_bars: int
    evaluation_mode: str

    support: SupportInfo
    opportunity_density: OpportunityDensity

    absolute_outcome: DescriptiveStats
    relative_outcome: DescriptiveStats

    baseline_comparison: BaselineComparison
    concentration: ConcentrationStats
    stability: tuple[StabilityBinResult, ...]
    missingness: MissingnessReport

    warnings: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class EvaluationRunRegistry:
    """Spec #003 SS59-60 -- reproducibility metadata. Same data + config +
    signature set + seed + versions must produce identical output."""
    evaluation_run_id: str
    created_at: str

    mode: str  # EvaluationMode

    development_start: Optional[str]
    development_end: Optional[str]

    timeframe: str
    horizons: tuple[int, ...]

    benchmark_security_id: str

    discovery_engine_version: str
    discovery_config_version: str

    evaluation_engine_version: str
    evaluation_config_version: str

    signature_set_id: str

    bootstrap_seed: int
    bootstrap_iterations: int
    comparison_seed: int
    comparison_iterations: int

    multiple_testing_method: str

    # Joint remediation design 003+004, section 12; decision registry
    # I1; authorized 2026-10-06, Stage 2; ADDED this round per GPT's own
    # changes-required review -- the registry must retain the full set
    # of fields build_run_id()'s own v2 fingerprint now hashes, so a
    # v2 evaluation_run_id can actually be RECOMPUTED and re-verified
    # later (the prior version computed the id but never stored the
    # inputs needed to check it again). All four default to a value
    # meaning "not part of this run's own fingerprint" so every
    # pre-Stage-2 construction site is unaffected. `security_ids` is
    # the run's own FULL input universe (sorted), matching the field
    # build_run_id() hashes -- never the observed subset.
    security_ids: tuple[str, ...] = ()
    data_as_of: Optional[str] = None
    calendar_id: Optional[str] = None
    run_id_scheme_version: Optional[str] = None
