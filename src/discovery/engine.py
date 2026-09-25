"""Spec #002 -- Feature Engine + Outcome-Blind Discovery Engine orchestration.

Two public entry points (PATCH #002-B, Radu's decision, 2026-09-25,
approving Spec #003's IMPLEMENTATION BLOCKER §74A):
- run_discovery() -- post-budget, operational DiscoveryCandidate list.
  What every existing Spec #002 consumer/test uses; unchanged behavior.
- compute_discovery_observations() -- pre-budget DiscoveryObservation
  list, every ELIGIBLE security, never trimmed by Candidate Budget. This
  is what Spec #003's Evaluation Engine (statistical dataset) must
  consume -- see models/entities.py's DiscoveryObservation docstring.
run_discovery() is a thin wrapper: compute observations, convert to the
operational type, then apply select_candidates(). Both are PIT-only:
this module, and every module under src/discovery/, may
reach Data Foundation ONLY through data_foundation.pit.access, never
data_foundation.model.repository or data_foundation.storage.db directly
(Spec #002 SS7) -- enforced structurally by
tests/discovery/test_18_pit_gateway_enforcement.py (an AST scan
mirroring Spec #001's TEST 10).

Runtime requires ZERO LLM calls (Spec #002 SS36/SS41): every computation
below is plain Python/pandas numerical work.

Outcome-blind (Spec #002 SS2): nothing in this pipeline reads or derives
from information dated after `as_of`, and no field anywhere represents a
forward-looking outcome -- see models/entities.py and
tests/discovery/test_17_no_outcome_fields.py.

Performance (Spec #002 SS37): exactly one PIT call per security (and one
for the benchmark) retrieves the full local history in a single shot;
every feature family is then computed from that same in-memory series --
never one query per feature per ticker per day.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from data_foundation.pit import access as pit

from discovery.candidate.convergence import (
    active_lanes_for, build_descriptive_metrics, compute_extremeness, reason_codes_for,
)
from discovery.candidate.selector import select_candidates
from discovery.config.loader import DiscoveryConfig, load_config
from discovery.eligibility.engine import evaluate_eligibility
from discovery.features import momentum, relative_strength, trend, volatility, volume
from discovery.models.entities import (
    DiscoveryCandidate,
    DiscoveryObservation,
    EligibilityResult,
    StateSignature,
    TransitionEntry,
)
from discovery.normalization.cross_sectional import cross_sectional_percentile
from discovery.normalization.rolling_percentile import PercentilePoint, rolling_percentile
from discovery.states.mapper import compute_lane_states, compute_persistence
from discovery.states.transitions import compute_transition

FEATURE_ENGINE_VERSION = "v1.0.0"
DISCOVERY_ENGINE_VERSION = "v1.0.0"
TIMEFRAME = "1D"  # Spec #002 SS5: V1 computes Daily only; every output still carries this explicitly.

# The raw features that get a TIME_SERIES rolling-percentile companion,
# and the percentile feature name it's published under. Covers every
# "_percentile" feature Spec #002 explicitly names (BB_width_percentile,
# ATR_percentile, realized_volatility_percentile, volume_percentile)
# plus this Level 1 build's documented driver choices for the
# trend/momentum lanes (Spec #002 doesn't name one for those two --
# see config/states.yaml).
_TIME_SERIES_NORMALIZED_FEATURES = {
    "return_63d": "return_63d_percentile",
    "BB_width_20": "BB_width_percentile",
    "ATR_pct": "ATR_percentile",
    "realized_volatility_20": "realized_volatility_percentile",
    "volume": "volume_percentile",
    "ROC_10": "ROC_10_percentile",
}

# relative_strength is deliberately excluded from the historical
# persistence/transition computation below: its driver
# (rs_percentile_cross_sectional) needs the whole eligible universe at
# every historical date to compute properly, which would require an
# expensive full-universe recomputation across history -- out of scope
# for Level 1 (see docs/spec002_known_limitations.md). Persistence and
# transitions here cover the four time-series-driven lanes only.
_TIME_SERIES_DRIVEN_LANES = ("trend", "volatility", "volume", "momentum")


def _price_series_to_df(bars) -> pd.DataFrame:
    return pd.DataFrame({
        "date": [b.date for b in bars],
        "open": [b.raw_open for b in bars],
        "high": [b.raw_high for b in bars],
        "low": [b.raw_low for b in bars],
        # split-adjusted close is the approved PIT-safe price
        # representation (Spec #002 SS31) -- total_return_adjusted_close
        # is EXPERIMENTAL_NOT_APPROVED_FOR_RESEARCH and never used here.
        "close": [b.split_adjusted_close for b in bars],
        # split_adjusted_volume (PATCH #001-C): raw_volume mixed with a
        # split-adjusted close produced a mechanical level-shift around
        # split dates, previously a documented BLOCKER before real-data
        # backtesting (see docs/spec002_known_limitations.md). Both
        # close and volume are now on the same post-adjustment share
        # basis.
        "volume": [b.split_adjusted_volume for b in bars],
    })


def _series_to_list(series: pd.Series) -> list[Optional[float]]:
    return [None if pd.isna(v) else float(v) for v in series]


def _last_or_none(series: pd.Series) -> Optional[float]:
    if len(series) == 0 or pd.isna(series.iloc[-1]):
        return None
    return float(series.iloc[-1])


def _assert_no_future_leakage(security_id: str, bars, as_of: str) -> None:
    """Fail-fast invariant, NOT a filtering mechanism (GPT Review #002
    Round 1, recommended, non-blocker): pit.access.get_price_series_as_of()
    is solely responsible for the as_of bound (Spec #001), and Feature
    Engine deliberately does not re-filter -- duplicating that rule here
    would create two sources of truth for the same guarantee. This
    assertion exists only to fail loudly if the PIT gateway's contract
    is ever violated, not to enforce PIT-safety itself. Bars are already
    ordered ascending by date (repository.get_price_history), so
    checking the last one suffices."""
    if bars and bars[-1].date > as_of:
        raise AssertionError(
            f"PIT gateway contract violation: {security_id} returned a bar dated "
            f"{bars[-1].date} after as_of={as_of}"
        )


def _compute_security_local(bars, benchmark_df: pd.DataFrame, config: DiscoveryConfig) -> dict:
    df = _price_series_to_df(bars)

    raw: dict[str, pd.Series] = {}
    raw.update(trend.compute(df, config.features["trend"]))
    raw.update(relative_strength.compute(df, benchmark_df, config.features["relative_strength"]))
    raw.update(volatility.compute(df, config.features["volatility"]))
    raw.update(volume.compute(df, config.features["volume"]))
    raw.update(momentum.compute(df, config.features["momentum"]))

    window = config.features["percentile_window"]
    min_periods = config.features["percentile_min_periods"]
    normalized_series: dict[str, list[PercentilePoint]] = {
        pct_name: rolling_percentile(_series_to_list(raw[raw_name]), window=window, min_periods=min_periods)
        for raw_name, pct_name in _TIME_SERIES_NORMALIZED_FEATURES.items()
    }

    states_config = config.states
    n = len(df)
    lane_states_history: list[dict[str, Optional[str]]] = []
    for i in range(n):
        normalized_at_i = {name: series[i].value for name, series in normalized_series.items()}
        full_states = compute_lane_states(normalized_at_i, states_config)
        lane_states_history.append({lane: full_states[lane] for lane in _TIME_SERIES_DRIVEN_LANES})

    persistence = compute_persistence(lane_states_history, states_config["persistence_lookback_cap"])

    delta_n_window = config.discovery["transition"]["delta_n_window"]
    transitions: dict[str, TransitionEntry] = {}
    for lane in _TIME_SERIES_DRIVEN_LANES:
        driver_feature = states_config["lane_drivers"][lane]
        series_values = [p.value for p in normalized_series[driver_feature]]
        transitions[driver_feature] = compute_transition(driver_feature, series_values, delta_n_window)

    return {
        "raw_features": raw,
        "normalized_series": normalized_series,
        "persistence": persistence,
        "transitions": transitions,
        "latest_close": _last_or_none(df["close"]),
        "history_days": int(df["close"].notna().sum()),
        "latest_adv_20": _last_or_none(raw["ADV_20"]),
    }


def _observation_to_candidate(obs: DiscoveryObservation) -> DiscoveryCandidate:
    """DiscoveryCandidate is DiscoveryObservation after Candidate Budget --
    identical fields today (PATCH #002-B, Radu's decision, 2026-09-25).
    A plain field-for-field copy, not a transformation: the distinction
    between the two types is semantic (statistical dataset vs operational,
    budget-selected output), not structural."""
    return DiscoveryCandidate(
        security_id=obs.security_id, ticker_as_of=obs.ticker_as_of, as_of=obs.as_of, timeframe=obs.timeframe,
        feature_vector=obs.feature_vector, normalized_feature_vector=obs.normalized_feature_vector,
        state_signature=obs.state_signature, transition_vector=obs.transition_vector,
        active_lanes=obs.active_lanes, descriptive_metrics=obs.descriptive_metrics,
        reason_codes=obs.reason_codes, config_version=obs.config_version,
        feature_engine_version=obs.feature_engine_version, discovery_engine_version=obs.discovery_engine_version,
    )


def compute_discovery_observations(
    conn, security_ids: list[str], as_of: str, benchmark_security_id: str,
    config: Optional[DiscoveryConfig] = None,
) -> list[DiscoveryObservation]:
    """The pre-budget layer (PATCH #002-B, Radu's decision, 2026-09-25,
    approving Spec #003's IMPLEMENTATION BLOCKER §74A): every ELIGIBLE
    security at `as_of`, fully computed, BEFORE Candidate Budget/diversity
    ever run. This is what Spec #003's Evaluation Engine must consume --
    never `run_discovery()`'s post-budget output, and never affected by
    `config.discovery["candidate_budget"]["max_candidates"]` (TEST 33,
    Spec #003; tests/spec002/test_24_pre_budget_observation_isolation.py).
    `run_discovery()` is a thin wrapper around this function -- see below."""
    config = config or load_config()
    states_config = config.states

    benchmark_bars = pit.get_price_series_as_of(conn, benchmark_security_id, as_of)
    _assert_no_future_leakage(benchmark_security_id, benchmark_bars, as_of)
    benchmark_df = _price_series_to_df(benchmark_bars)

    locals_by_security: dict[str, dict] = {}
    for security_id in security_ids:
        bars = pit.get_price_series_as_of(conn, security_id, as_of)
        if not bars:
            continue
        _assert_no_future_leakage(security_id, bars, as_of)
        locals_by_security[security_id] = _compute_security_local(bars, benchmark_df, config)

    # Eligibility (Spec #002 SS29) FIRST -- establishes the reference
    # population for any cross-sectional computation. GPT Review #002
    # Round 1 (mandatory finding): computing rs_percentile_cross_sectional
    # before filtering to eligible_ids lets a security that will never
    # become a candidate (e.g. failing minimum_price) still skew the RS
    # percentile of securities that ARE eligible -- see TEST 22. Kept
    # separate from Data QA and from Discovery's own descriptive metrics.
    # primary_exchange is passed as None: the PIT gateway (Spec #001)
    # doesn't expose security_master.primary_exchange, so
    # EXCHANGE_ELIGIBILITY can't be evaluated at Level 1 -- disabled by
    # default (allowed_exchanges: null in eligibility.yaml), documented
    # in Known Limitations rather than reading repository directly.
    eligibility_by_security: dict[str, EligibilityResult] = {
        sid: evaluate_eligibility(
            security_id=sid, as_of=as_of, latest_close=r["latest_close"],
            history_days=r["history_days"], latest_adv_20=r["latest_adv_20"],
            primary_exchange=None, config=config.eligibility,
        )
        for sid, r in locals_by_security.items()
    }
    eligible_ids = [sid for sid, e in eligibility_by_security.items() if e.eligible]

    # Cross-sectional pass: relative_return_63d -> rs_percentile_cross_sectional,
    # computed ONLY over eligible_ids (see note above).
    relative_return_63d_by_security = {
        sid: _last_or_none(locals_by_security[sid]["raw_features"]["relative_return_63d"])
        for sid in eligible_ids
    }
    rs_percentiles = cross_sectional_percentile(relative_return_63d_by_security)

    state_signatures: dict[str, StateSignature] = {}
    for sid in eligible_ids:
        r = locals_by_security[sid]
        normalized_at_as_of = {name: series[-1].value for name, series in r["normalized_series"].items()}
        normalized_at_as_of["rs_percentile_cross_sectional"] = rs_percentiles[sid].value

        lane_states = compute_lane_states(normalized_at_as_of, states_config)
        raw_at_as_of = {name: _last_or_none(series) for name, series in r["raw_features"].items()}

        state_signatures[sid] = StateSignature(
            security_id=sid, as_of=as_of, timeframe=TIMEFRAME,
            lane_states=lane_states, feature_vector=raw_at_as_of,
            normalized_feature_vector=normalized_at_as_of, persistence=r["persistence"],
        )

    # state_frequency (Spec #002 SS25): cross-sectional rarity among
    # ELIGIBLE securities sharing the exact same full lane_states
    # combination as this candidate -- descriptive only, never a
    # trading trigger.
    signature_key_counts: dict[tuple, int] = {}
    for sid in eligible_ids:
        key = tuple(sorted(state_signatures[sid].lane_states.items()))
        signature_key_counts[key] = signature_key_counts.get(key, 0) + 1
    sample_count = len(eligible_ids)
    min_sample_support = config.discovery["min_sample_support"]

    observations: list[DiscoveryObservation] = []
    for sid in eligible_ids:
        r = locals_by_security[sid]
        sig = state_signatures[sid]
        active_lanes = active_lanes_for(sig)
        extremeness = compute_extremeness(sig, states_config, config.discovery)
        key = tuple(sorted(sig.lane_states.items()))
        state_frequency = (signature_key_counts[key] / sample_count) if sample_count else None
        metrics = build_descriptive_metrics(
            extremeness=extremeness, persistence=sig.persistence, state_frequency=state_frequency,
            sample_count=sample_count, min_sample_support=min_sample_support,
        )
        reason_codes = reason_codes_for(sig, r["transitions"], active_lanes, states_config, config.discovery)

        observations.append(DiscoveryObservation(
            security_id=sid,
            ticker_as_of=pit.get_ticker_as_of(conn, sid, as_of),
            as_of=as_of, timeframe=TIMEFRAME,
            feature_vector=sig.feature_vector,
            normalized_feature_vector=sig.normalized_feature_vector,
            state_signature=sig.lane_states,
            transition_vector=r["transitions"],
            active_lanes=active_lanes,
            descriptive_metrics=metrics,
            reason_codes=reason_codes,
            config_version=config.config_version,
            feature_engine_version=FEATURE_ENGINE_VERSION,
            discovery_engine_version=DISCOVERY_ENGINE_VERSION,
        ))

    return observations


def run_discovery(
    conn, security_ids: list[str], as_of: str, benchmark_security_id: str,
    config: Optional[DiscoveryConfig] = None,
) -> list[DiscoveryCandidate]:
    """THE single entry point for operational (post-budget) output. PIT-only,
    outcome-blind, zero LLM calls. A thin wrapper: compute every eligible
    observation, convert to the operational type, then apply Candidate
    Budget/diversity -- `config.discovery["candidate_budget"]` affects only
    this function's return value, never `compute_discovery_observations()`'s
    (PATCH #002-B, Spec #003 IMPLEMENTATION BLOCKER §74A)."""
    config = config or load_config()
    observations = compute_discovery_observations(conn, security_ids, as_of, benchmark_security_id, config)
    candidates = [_observation_to_candidate(obs) for obs in observations]
    return select_candidates(candidates, config.discovery)
