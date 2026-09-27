"""Spec #005 v1.0 SS5/SS7 -- historical observation cache (Batch 2).

"Compute compute_discovery_observations once per session/universe/
config/snapshot and reuse the PRE-budget output for all relevant
variants and invalidation checks. Do not call the candidate selector,
use REVIEW_PRIORITY, or let budget/ranking suppress historical signals."
"Cache keys bind stage, session, universe/benchmark, snapshot, discovery
code/config and PIT policy."

This module imports ONLY `discovery.engine.compute_discovery_observations`
-- never `discovery.engine.run_discovery()` or
`discovery.candidate.selector.select_candidates()`. Candidate Budget is a
downstream/LLM compute-budget knob (Spec #002/#003's own established
reading); #005 must never let it suppress a historical signal it needs
for invalidation checks (see `tests/spec005/test_17...`'s AST import
guard, mirroring the discipline in `tests/spec002/test_24_pre_budget_
observation_isolation.py`).
"""
from __future__ import annotations

from discovery.config.loader import DiscoveryConfig
from discovery.engine import DISCOVERY_ENGINE_VERSION, compute_discovery_observations

from backtest.models.entities import (
    PIT_ACCESS_POLICY_V1,
    HistoricalObservationCache,
    StageAccessBoundary,
    build_historical_observation_cache_id,
    historical_observation_cache_fingerprint,
)


class ObservationCacheStore:
    """In-memory reuse across variants within ONE #005 stage run.
    `compute_count` is a test/audit hook: how many times
    `compute_discovery_observations()` was actually invoked -- repeated
    `get_or_compute()` calls sharing the same key must reuse the SAME
    entry without recomputing (SS7's "compute... once... and reuse")."""

    def __init__(self):
        self._entries: dict[tuple, HistoricalObservationCache] = {}
        self.compute_count = 0

    def get_or_compute(
        self, conn, boundary: StageAccessBoundary, security_ids: tuple[str, ...], as_of: str,
        benchmark_security_id: str, snapshot_id: str, discovery_config: DiscoveryConfig,
    ) -> HistoricalObservationCache:
        boundary.require_as_of_in_scope(as_of)
        sorted_ids = tuple(sorted(security_ids))
        key = (
            boundary.zone, as_of, sorted_ids, benchmark_security_id, snapshot_id,
            DISCOVERY_ENGINE_VERSION, discovery_config.config_version, PIT_ACCESS_POLICY_V1,
        )
        cached = self._entries.get(key)
        if cached is not None:
            return cached

        observations = compute_discovery_observations(
            conn, list(sorted_ids), as_of, benchmark_security_id, discovery_config,
        )
        self.compute_count += 1
        observed_ids = {obs.security_id for obs in observations}
        # Explicit missingness (SS7): ineligible or no price history at
        # all -- either way, absence from `observations` is named here,
        # never silently indistinguishable from "checked and found
        # nothing to signal."
        missing = tuple(sid for sid in sorted_ids if sid not in observed_ids)

        fp = historical_observation_cache_fingerprint(
            boundary.zone, as_of, sorted_ids, benchmark_security_id, snapshot_id,
            DISCOVERY_ENGINE_VERSION, discovery_config.config_version, PIT_ACCESS_POLICY_V1,
        )
        cache_id, cache_hash = build_historical_observation_cache_id(fp)
        entry = HistoricalObservationCache(
            cache_id=cache_id, cache_hash=cache_hash, stage=boundary.zone, as_of=as_of,
            security_ids=sorted_ids, benchmark_security_id=benchmark_security_id, snapshot_id=snapshot_id,
            discovery_engine_version=DISCOVERY_ENGINE_VERSION,
            discovery_config_version=discovery_config.config_version,
            pit_access_policy=PIT_ACCESS_POLICY_V1, observations=tuple(observations),
            missing_security_ids=missing,
        )
        self._entries[key] = entry
        return entry
