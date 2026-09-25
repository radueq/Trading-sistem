"""Spec #002 -- Feature Engine + Outcome-Blind Discovery Engine models.

Three concepts kept strictly separate (Spec #002 SS3), never conflated
in the data model:
- Feature: a raw numerical observation (FeatureObservation).
- State: interpretation of the current feature position (StateSignature).
- Transition: change in that state over time (TransitionVector).

No field on any of these dataclasses may represent a forward-looking
outcome (future returns, win rate, expectancy, Sharpe, alpha score,
backtest results, ...) -- Spec #002 SS2/SS24, enforced structurally by
tests/discovery/test_17_no_outcome_fields.py (an AST/text scan, not just
convention).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class FeatureStatus(str, Enum):
    VALID = "VALID"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    MISSING_INPUT = "MISSING_INPUT"
    INVALID_INPUT = "INVALID_INPUT"


class NormalizationType(str, Enum):
    TIME_SERIES = "TIME_SERIES"
    CROSS_SECTIONAL = "CROSS_SECTIONAL"


class SupportStatus(str, Enum):
    SUFFICIENT = "SUFFICIENT"
    INSUFFICIENT = "INSUFFICIENT"


@dataclass(frozen=True)
class FeatureObservation:
    security_id: str
    as_of: str
    timeframe: str
    feature_name: str
    feature_value: Optional[float]
    status: str


@dataclass(frozen=True)
class NormalizedFeatureObservation:
    security_id: str
    as_of: str
    timeframe: str
    feature_name: str
    percentile_value: Optional[float]
    normalization_type: str
    window: Optional[int]
    status: str


@dataclass(frozen=True)
class TransitionEntry:
    feature_name: str
    current_value: Optional[float]
    delta_1: Optional[float]
    delta_n: Optional[float]
    delta_n_window: int
    acceleration: Optional[float]
    status: str


@dataclass(frozen=True)
class TransitionVector:
    security_id: str
    as_of: str
    timeframe: str
    entries: dict[str, TransitionEntry]


@dataclass(frozen=True)
class StateSignature:
    security_id: str
    as_of: str
    timeframe: str
    lane_states: dict[str, str]
    feature_vector: dict[str, float]
    normalized_feature_vector: dict[str, float]
    persistence: int


@dataclass(frozen=True)
class EligibilityResult:
    security_id: str
    as_of: str
    eligible: bool
    failed_rules: list[str]
    market_cap_filter_status: str


@dataclass(frozen=True)
class DescriptiveMetrics:
    """Statistically noteworthy, NOT expected-profitable (Spec #002 SS24).
    Never rename these to imply predictive/trading meaning."""
    extremeness: float
    persistence: int
    state_frequency: Optional[float]
    sample_count: int
    support_status: str


@dataclass(frozen=True)
class DiscoveryObservation:
    """The pre-budget layer (PATCH #002-B, Radu's decision, 2026-09-25,
    approving Spec #003's IMPLEMENTATION BLOCKER §74A): one entry per
    ELIGIBLE security at `as_of` -- everything Discovery computed for it,
    before Candidate Budget ever runs. This is the statistical dataset
    Evaluation (Spec #003) must consume; `max_candidates` must never be
    able to change what this layer contains (see
    tests/spec002/test_24_pre_budget_observation_isolation.py and Spec
    #003 TEST 33). Deliberately a distinct type from `DiscoveryCandidate`
    (identical fields today) rather than reusing that name, so a
    statistical dataset can never be confused with an operational,
    budget-selected candidate list -- see `discovery.engine.run_discovery`'s
    docstring for how one is built from the other."""
    security_id: str
    ticker_as_of: Optional[str]
    as_of: str
    timeframe: str
    feature_vector: dict[str, float]
    normalized_feature_vector: dict[str, float]
    state_signature: dict[str, str]
    transition_vector: dict[str, TransitionEntry]
    active_lanes: list[str]
    descriptive_metrics: DescriptiveMetrics
    reason_codes: list[str]
    config_version: str
    feature_engine_version: str
    discovery_engine_version: str


@dataclass(frozen=True)
class DiscoveryCandidate:
    """Post-budget, operational output of `run_discovery()` -- the same
    fields as `DiscoveryObservation`, after `candidate.selector.select_candidates()`
    has ranked/trimmed/diversified. Never the statistical dataset for
    Evaluation (Spec #003) -- see `DiscoveryObservation` above."""
    security_id: str
    ticker_as_of: Optional[str]
    as_of: str
    timeframe: str
    feature_vector: dict[str, float]
    normalized_feature_vector: dict[str, float]
    state_signature: dict[str, str]
    transition_vector: dict[str, TransitionEntry]
    active_lanes: list[str]
    descriptive_metrics: DescriptiveMetrics
    reason_codes: list[str]
    config_version: str
    feature_engine_version: str
    discovery_engine_version: str
