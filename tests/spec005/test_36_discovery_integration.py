"""TEST 36 -- Spec #005 Discovery Integration & Legacy Exits, obligations
1-2: `matches_entry_definition()` (EntryDefinition matching against real
DiscoveryObservation output) and `evaluate_invalidation_conditions()`
(InvalidationCondition evaluation), plus the two small builders/adapter
that turn a caller-supplied `observations_by_session` mapping into
`entry_signals`/an `invalidation_observer` satisfying `SessionEngine`'s/
`LegacySessionEngine`'s existing, unchanged contracts.
"""
from __future__ import annotations

from discovery.candidate.reason_codes import ReasonCode
from discovery.models.entities import DescriptiveMetrics, DiscoveryObservation

from hypothesis.models.entities import (
    EntryDefinition,
    InvalidationCondition,
    LaneStateCondition,
    ReasonCodeCondition,
)
from hypothesis.registry.hypotheses import HypothesisRegistry

from backtest.exits.discovery_integration import (
    INVALIDATED,
    UNKNOWN,
    VALID_HOLD,
    build_entry_signals_from_observations,
    build_invalidation_observer,
    evaluate_invalidation_conditions,
    matches_entry_definition,
    observations_by_session_from_caches,
)
from backtest.models.entities import HistoricalObservationCache

from spec005.fixtures.stop_managed_variants import build_registered_stop_managed_hypothesis


def _obs(security_id: str, as_of: str, lane_states: dict | None = None, reason_codes: list | None = None) -> DiscoveryObservation:
    lane_states = lane_states or {}
    return DiscoveryObservation(
        security_id=security_id, ticker_as_of=security_id, as_of=as_of, timeframe="1D",
        feature_vector={}, normalized_feature_vector={}, state_signature=lane_states,
        transition_vector={}, active_lanes=list(lane_states.keys()),
        descriptive_metrics=DescriptiveMetrics(extremeness=0.0, persistence=1, state_frequency=None, sample_count=1, support_status="SUFFICIENT"),
        reason_codes=list(reason_codes or []),
        config_version="cfg_test", feature_engine_version="v1.0.0", discovery_engine_version="v1.0.0",
    )


# -- matches_entry_definition() ---------------------------------------

def test_no_observation_never_matches():
    entry = EntryDefinition(core_conditions=(LaneStateCondition("volatility", "COMPRESSION"),))
    assert matches_entry_definition(None, entry) is False


def test_single_core_condition_matches_on_exact_label():
    entry = EntryDefinition(core_conditions=(LaneStateCondition("volatility", "COMPRESSION"),))
    assert matches_entry_definition(_obs("S", "2024-01-01", {"volatility": "COMPRESSION"}), entry) is True
    assert matches_entry_definition(_obs("S", "2024-01-01", {"volatility": "EXPANSION"}), entry) is False
    assert matches_entry_definition(_obs("S", "2024-01-01", {}), entry) is False


def test_reason_code_condition_matches_on_presence():
    entry = EntryDefinition(core_conditions=(ReasonCodeCondition(ReasonCode.TREND_EXTREME.value),))
    assert matches_entry_definition(_obs("S", "2024-01-01", reason_codes=[ReasonCode.TREND_EXTREME.value]), entry) is True
    assert matches_entry_definition(_obs("S", "2024-01-01", reason_codes=[ReasonCode.VOLUME_ANOMALY.value]), entry) is False


def test_core_and_confirmation_conditions_are_all_and_combined():
    entry = EntryDefinition(
        core_conditions=(LaneStateCondition("volatility", "COMPRESSION"),),
        confirmation_conditions=(ReasonCodeCondition(ReasonCode.TREND_EXTREME.value),),
    )
    both = _obs("S", "2024-01-01", {"volatility": "COMPRESSION"}, [ReasonCode.TREND_EXTREME.value])
    only_core = _obs("S", "2024-01-01", {"volatility": "COMPRESSION"}, [])
    only_confirmation = _obs("S", "2024-01-01", {}, [ReasonCode.TREND_EXTREME.value])
    assert matches_entry_definition(both, entry) is True
    assert matches_entry_definition(only_core, entry) is False
    assert matches_entry_definition(only_confirmation, entry) is False


def test_negated_condition_flips_the_match():
    entry = EntryDefinition(core_conditions=(LaneStateCondition("volatility", "COMPRESSION", negate=True),))
    assert matches_entry_definition(_obs("S", "2024-01-01", {"volatility": "COMPRESSION"}), entry) is False
    assert matches_entry_definition(_obs("S", "2024-01-01", {"volatility": "EXPANSION"}), entry) is True


# -- evaluate_invalidation_conditions() --------------------------------

def test_missing_current_observation_is_unknown():
    conditions = (InvalidationCondition(lane="relative_strength", holds_labels=("HIGH", "VERY_HIGH")),)
    assert evaluate_invalidation_conditions(None, None, conditions) == UNKNOWN


def test_lane_condition_invalidates_when_label_leaves_holds_set():
    conditions = (InvalidationCondition(lane="relative_strength", holds_labels=("HIGH", "VERY_HIGH")),)
    still_holding = _obs("S", "2024-01-02", {"relative_strength": "HIGH"})
    broken = _obs("S", "2024-01-02", {"relative_strength": "LOW"})
    assert evaluate_invalidation_conditions(still_holding, None, conditions) == VALID_HOLD
    assert evaluate_invalidation_conditions(broken, None, conditions) == INVALIDATED


def test_reason_code_condition_triggers_on_presence_flip():
    appears = InvalidationCondition(reason_code=ReasonCode.STATE_TRANSITION.value, triggers_on_presence=True)
    entry_obs = _obs("S", "2024-01-01", reason_codes=[])
    current_with_it = _obs("S", "2024-01-05", reason_codes=[ReasonCode.STATE_TRANSITION.value])
    current_without_it = _obs("S", "2024-01-05", reason_codes=[])
    assert evaluate_invalidation_conditions(current_with_it, entry_obs, (appears,)) == INVALIDATED
    assert evaluate_invalidation_conditions(current_without_it, entry_obs, (appears,)) == VALID_HOLD


def test_reason_code_condition_triggers_on_disappearance():
    disappears = InvalidationCondition(reason_code=ReasonCode.MOMENTUM_ACCELERATION.value, triggers_on_presence=False)
    entry_obs = _obs("S", "2024-01-01", reason_codes=[ReasonCode.MOMENTUM_ACCELERATION.value])
    current_still_present = _obs("S", "2024-01-05", reason_codes=[ReasonCode.MOMENTUM_ACCELERATION.value])
    current_gone = _obs("S", "2024-01-05", reason_codes=[])
    assert evaluate_invalidation_conditions(current_still_present, entry_obs, (disappears,)) == VALID_HOLD
    assert evaluate_invalidation_conditions(current_gone, entry_obs, (disappears,)) == INVALIDATED


def test_reason_code_condition_without_entry_observation_is_unknown():
    appears = InvalidationCondition(reason_code=ReasonCode.STATE_TRANSITION.value, triggers_on_presence=True)
    current = _obs("S", "2024-01-05", reason_codes=[ReasonCode.STATE_TRANSITION.value])
    assert evaluate_invalidation_conditions(current, None, (appears,)) == UNKNOWN


def test_a_definite_invalidation_is_never_suppressed_by_an_unrelated_unknown():
    lane_cond = InvalidationCondition(lane="relative_strength", holds_labels=("HIGH",))
    reason_cond_needing_entry = InvalidationCondition(reason_code=ReasonCode.STATE_TRANSITION.value, triggers_on_presence=True)
    current = _obs("S", "2024-01-05", {"relative_strength": "LOW"}, [])
    # entry_observation=None starves the reason-code condition, but the
    # lane condition is independently, definitely INVALIDATED.
    assert evaluate_invalidation_conditions(current, None, (reason_cond_needing_entry, lane_cond)) == INVALIDATED


def test_no_condition_triggers_is_valid_hold():
    conditions = (
        InvalidationCondition(lane="relative_strength", holds_labels=("HIGH", "VERY_HIGH")),
        InvalidationCondition(reason_code=ReasonCode.STATE_TRANSITION.value, triggers_on_presence=True),
    )
    entry_obs = _obs("S", "2024-01-01", reason_codes=[])
    current = _obs("S", "2024-01-05", {"relative_strength": "HIGH"}, [])
    assert evaluate_invalidation_conditions(current, entry_obs, conditions) == VALID_HOLD


# -- observations_by_session_from_caches() -----------------------------

def _cache(as_of: str, observations: tuple) -> HistoricalObservationCache:
    return HistoricalObservationCache(
        cache_id="obscache_x", cache_hash="x", stage="FORMATION_SELECTION", as_of=as_of,
        security_ids=tuple(sorted(o.security_id for o in observations)), benchmark_security_id="SBENCH",
        snapshot_id="snap_x", discovery_engine_version="v1.0.0", discovery_config_version="cfg_disc",
        pit_access_policy="BOUNDED_PIT_V1", observations=observations, missing_security_ids=(),
        observations_content_hash="x",
    )


def test_observations_by_session_from_caches_reshapes_by_security_id():
    d1_cache = _cache("2024-01-01", (_obs("SEC_A", "2024-01-01", {"volatility": "COMPRESSION"}),))
    result = observations_by_session_from_caches({"2024-01-01": d1_cache})
    assert result == {"2024-01-01": {"SEC_A": d1_cache.observations[0]}}


def test_observations_by_session_from_caches_rejects_as_of_key_mismatch():
    wrong_cache = _cache("2024-01-02", ())  # cache's own as_of != the key below
    try:
        observations_by_session_from_caches({"2024-01-01": wrong_cache})
        assert False, "expected ValueError"
    except ValueError as e:
        assert "does not match" in str(e)


# -- build_entry_signals_from_observations() ---------------------------

def test_build_entry_signals_emits_one_signal_per_variant_on_a_match():
    registry = HypothesisRegistry()
    hid, vid = build_registered_stop_managed_hypothesis(registry, signature_id="SIG_ENTRY_BUILD")
    # The fixture's own horizon_candidate_set (values=(3,)) auto-materializes
    # a TIME_EXIT variant too (materialize_variants()'s established
    # behavior) -- so this hypothesis has TWO variants: TIME_EXIT (auto)
    # plus the requested STOP_MANAGED_INVALIDATION one (`vid`). A shared
    # entry match must produce one EntrySignal per variant, not just one.
    all_variant_ids = {v.strategy_variant_id for v in registry.variants_for(hid)}
    assert vid in all_variant_ids and len(all_variant_ids) == 2

    observations_by_session = {
        "2024-01-01": {"SEC_A": _obs("SEC_A", "2024-01-01", {"volatility": "COMPRESSION"})},
    }
    signals = build_entry_signals_from_observations(observations_by_session, registry, frozenset({hid}))
    expected_keys = {("SEC_A", v, "2024-01-01") for v in all_variant_ids}
    assert set(signals.keys()) == expected_keys
    assert signals[("SEC_A", vid, "2024-01-01")].security_id == "SEC_A"
    assert signals[("SEC_A", vid, "2024-01-01")].strategy_variant_id == vid


def test_build_entry_signals_skips_a_non_matching_observation():
    registry = HypothesisRegistry()
    hid, _vid = build_registered_stop_managed_hypothesis(registry, signature_id="SIG_ENTRY_NOMATCH")
    observations_by_session = {
        "2024-01-01": {"SEC_A": _obs("SEC_A", "2024-01-01", {"volatility": "EXPANSION"})},
    }
    signals = build_entry_signals_from_observations(observations_by_session, registry, frozenset({hid}))
    assert signals == {}


def test_build_entry_signals_ignores_a_hypothesis_outside_the_accepted_cohort():
    registry = HypothesisRegistry()
    hid, _vid = build_registered_stop_managed_hypothesis(registry, signature_id="SIG_ENTRY_OFFCOHORT")
    observations_by_session = {
        "2024-01-01": {"SEC_A": _obs("SEC_A", "2024-01-01", {"volatility": "COMPRESSION"})},
    }
    signals = build_entry_signals_from_observations(observations_by_session, registry, frozenset())  # empty cohort
    assert signals == {}


def test_build_entry_signals_ignores_an_unresolvable_hypothesis_id():
    registry = HypothesisRegistry()
    observations_by_session = {"2024-01-01": {"SEC_A": _obs("SEC_A", "2024-01-01", {"volatility": "COMPRESSION"})}}
    signals = build_entry_signals_from_observations(observations_by_session, registry, frozenset({"NOT_REGISTERED"}))
    assert signals == {}


# -- build_invalidation_observer() --------------------------------------

class _FakePosition:
    def __init__(self, security_id, strategy_variant_id, entry_date):
        self.security_id = security_id
        self.strategy_variant_id = strategy_variant_id
        self.entry_date = entry_date


def test_invalidation_observer_evaluates_the_resolved_variants_own_conditions():
    registry = HypothesisRegistry()
    hid, vid = build_registered_stop_managed_hypothesis(registry, signature_id="SIG_OBSERVER")
    # build_registered_stop_managed_hypothesis's own exit hypothesis uses
    # InvalidationCondition(lane="relative_strength", holds_labels=("HIGH", "VERY_HIGH")).
    observations_by_session = {
        "2024-01-01": {"SEC_A": _obs("SEC_A", "2024-01-01", {"relative_strength": "HIGH"})},
        "2024-01-05": {"SEC_A": _obs("SEC_A", "2024-01-05", {"relative_strength": "LOW"})},
    }
    observer = build_invalidation_observer(observations_by_session, registry)
    position = _FakePosition("SEC_A", vid, "2024-01-01")
    assert observer(position, "2024-01-01") == VALID_HOLD
    assert observer(position, "2024-01-05") == INVALIDATED


def test_invalidation_observer_reports_unknown_for_an_unresolvable_variant():
    registry = HypothesisRegistry()
    observer = build_invalidation_observer({}, registry)
    position = _FakePosition("SEC_A", "NOT_A_REAL_VARIANT", "2024-01-01")
    assert observer(position, "2024-01-05") == UNKNOWN
