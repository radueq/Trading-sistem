"""TEST 17 -- historical observation cache (Spec #005 v1.0 SS5/SS7,
Batch 2).

"Compute compute_discovery_observations once per session/universe/
config/snapshot and reuse the PRE-budget output for all relevant
variants and invalidation checks. Do not call the candidate selector,
use REVIEW_PRIORITY, or let budget/ranking suppress historical signals."
"A missing observation is UNKNOWN, not automatically a false entry or
true invalidation."
"""
import ast
from pathlib import Path

import pytest

from discovery.config.loader import load_config as load_discovery_config
from discovery.engine import DISCOVERY_ENGINE_VERSION

from backtest.data.cache import ObservationCacheStore
from backtest.models.entities import (
    FORMATION_SELECTION,
    PIT_ACCESS_POLICY_V1,
    OutOfScopeAccessError,
    StageAccessBoundary,
    verify_historical_observation_cache_identity,
)

from spec005.conftest import PIT_FORMATION_END


@pytest.fixture
def discovery_config():
    return load_discovery_config()


def test_repeated_calls_with_the_same_key_reuse_the_entry_without_recomputing(conn, pit_universe, discovery_config):
    store = ObservationCacheStore()
    boundary = StageAccessBoundary(zone=FORMATION_SELECTION, max_as_of=PIT_FORMATION_END)
    ids = pit_universe["priced_security_ids"]
    bench = pit_universe["benchmark_security_id"]
    entry_a = store.get_or_compute(conn, boundary, ids, PIT_FORMATION_END, bench, "snap_x", discovery_config)
    entry_b = store.get_or_compute(conn, boundary, ids, PIT_FORMATION_END, bench, "snap_x", discovery_config)
    assert entry_a is entry_b
    assert store.compute_count == 1


def test_a_different_as_of_computes_a_separate_entry(conn, pit_universe, discovery_config):
    store = ObservationCacheStore()
    boundary = StageAccessBoundary(zone=FORMATION_SELECTION, max_as_of=PIT_FORMATION_END)
    ids = pit_universe["priced_security_ids"]
    bench = pit_universe["benchmark_security_id"]
    store.get_or_compute(conn, boundary, ids, "2024-01-15", bench, "snap_x", discovery_config)
    store.get_or_compute(conn, boundary, ids, PIT_FORMATION_END, bench, "snap_x", discovery_config)
    assert store.compute_count == 2


def test_a_different_snapshot_id_computes_a_separate_entry(conn, pit_universe, discovery_config):
    store = ObservationCacheStore()
    boundary = StageAccessBoundary(zone=FORMATION_SELECTION, max_as_of=PIT_FORMATION_END)
    ids = pit_universe["priced_security_ids"]
    bench = pit_universe["benchmark_security_id"]
    store.get_or_compute(conn, boundary, ids, PIT_FORMATION_END, bench, "snap_x", discovery_config)
    store.get_or_compute(conn, boundary, ids, PIT_FORMATION_END, bench, "snap_y", discovery_config)
    assert store.compute_count == 2


def test_universe_order_does_not_affect_the_cache_key(conn, pit_universe, discovery_config):
    store = ObservationCacheStore()
    boundary = StageAccessBoundary(zone=FORMATION_SELECTION, max_as_of=PIT_FORMATION_END)
    ids = pit_universe["priced_security_ids"]
    bench = pit_universe["benchmark_security_id"]
    entry_a = store.get_or_compute(conn, boundary, ids, PIT_FORMATION_END, bench, "snap_x", discovery_config)
    entry_b = store.get_or_compute(conn, boundary, tuple(reversed(ids)), PIT_FORMATION_END, bench, "snap_x", discovery_config)
    assert entry_a is entry_b
    assert store.compute_count == 1


def test_out_of_scope_as_of_is_rejected_before_any_compute(conn, pit_universe, discovery_config):
    store = ObservationCacheStore()
    boundary = StageAccessBoundary(zone=FORMATION_SELECTION, max_as_of=PIT_FORMATION_END)
    ids = pit_universe["priced_security_ids"]
    bench = pit_universe["benchmark_security_id"]
    with pytest.raises(OutOfScopeAccessError):
        store.get_or_compute(conn, boundary, ids, "2024-02-15", bench, "snap_x", discovery_config)
    assert store.compute_count == 0


def test_a_security_with_no_price_history_is_explicitly_named_as_missing(conn, pit_universe, discovery_config):
    store = ObservationCacheStore()
    boundary = StageAccessBoundary(zone=FORMATION_SELECTION, max_as_of=PIT_FORMATION_END)
    ids = pit_universe["security_ids_with_nodata"]
    bench = pit_universe["benchmark_security_id"]
    entry = store.get_or_compute(conn, boundary, ids, PIT_FORMATION_END, bench, "snap_x", discovery_config)
    assert pit_universe["sec_nodata"] in entry.missing_security_ids
    observed_ids = {obs.security_id for obs in entry.observations}
    assert pit_universe["sec_nodata"] not in observed_ids


def test_priced_and_eligible_securities_produce_real_pre_budget_observations(conn, pit_universe, discovery_config):
    """Confirms the fixture's warm-up history actually clears discovery's
    own `minimum_history_days: 60` eligibility floor by PIT_FORMATION_END
    -- both securities produce a real observation, not an empty list."""
    store = ObservationCacheStore()
    boundary = StageAccessBoundary(zone=FORMATION_SELECTION, max_as_of=PIT_FORMATION_END)
    ids = pit_universe["priced_security_ids"]
    bench = pit_universe["benchmark_security_id"]
    entry = store.get_or_compute(conn, boundary, ids, PIT_FORMATION_END, bench, "snap_x", discovery_config)
    assert entry.missing_security_ids == ()
    observed_ids = {obs.security_id for obs in entry.observations}
    assert observed_ids == set(ids)
    assert entry.discovery_engine_version == DISCOVERY_ENGINE_VERSION
    assert entry.pit_access_policy == PIT_ACCESS_POLICY_V1


def test_cache_entry_passes_its_own_identity_re_verification(conn, pit_universe, discovery_config):
    store = ObservationCacheStore()
    boundary = StageAccessBoundary(zone=FORMATION_SELECTION, max_as_of=PIT_FORMATION_END)
    ids = pit_universe["priced_security_ids"]
    bench = pit_universe["benchmark_security_id"]
    entry = store.get_or_compute(conn, boundary, ids, PIT_FORMATION_END, bench, "snap_x", discovery_config)
    ok, errors = verify_historical_observation_cache_identity(entry)
    assert ok, errors


def test_cache_module_never_imports_the_candidate_selector_or_run_discovery():
    """SS7: "Do not call the candidate selector, use REVIEW_PRIORITY, or
    let budget/ranking suppress historical signals." AST import scan
    (mirroring `tests/spec002/test_24_pre_budget_observation_isolation.py`
    and `tests/spec005/test_10`'s own discipline), not a raw text grep,
    so a docstring merely discussing budget/REVIEW_PRIORITY is never a
    false positive."""
    path = Path(__file__).resolve().parents[2] / "src" / "backtest" / "data" / "cache.py"
    tree = ast.parse(path.read_text(), filename=str(path))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                imported.add(f"{node.module}.{alias.name}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
    forbidden = {
        "discovery.candidate.selector.select_candidates",
        "discovery.engine.run_discovery",
        "discovery.engine.select_candidates",
    }
    assert not (imported & forbidden)
    assert "discovery.engine.compute_discovery_observations" in imported
