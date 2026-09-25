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
class BaselineComparison:
    """Signature vs TEMPORALLY_STRATIFIED_ELIGIBLE_BASELINE (Spec #003
    SS33-34/38, Radu's amendment to the original SS33 -- never raw-row
    weighted). raw_p comes from a SEPARATE permutation test, never
    informally derived from a bootstrap CI crossing zero (Radu's explicit
    correction to the original draft). standardized_effect is the robust
    formula median_difference / (baseline_IQR / 1.349); `None` when
    baseline_IQR is ~0 (UNDEFINED_ZERO_SCALE, not a silent division)."""
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


@dataclass(frozen=True)
class SupportInfo:
    raw_n: int
    episode_n: int
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
