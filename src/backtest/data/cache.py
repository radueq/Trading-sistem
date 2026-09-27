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

Batch 2 patch round-2 review (P1 finding): `get_or_compute()` used to
take a bare `snapshot_id: str` and a `benchmark_security_id` supplied
separately from `conn` -- nothing tied the string to the connection's
ACTUAL live state, so a caller could compute against changed data while
still labeling the result under a stale snapshot's identity.
`get_or_compute()` now takes the real `DataSnapshotManifest` object,
re-verifies its own content-address first, and derives
`benchmark_security_id` and the allowed `security_ids` FROM it -- a
request for a security outside the snapshot's own scope is rejected.
The connection itself still must be the SAME one, held in the SAME open
transaction, the snapshot was built from -- `backtest.data.context.
StageReadContext` is what actually guarantees that; this module cannot
verify a connection's "freshness" on its own without re-hashing
everything, which would defeat the purpose of caching.
"""
from __future__ import annotations

from discovery.config.loader import DiscoveryConfig
from discovery.engine import DISCOVERY_ENGINE_VERSION, compute_discovery_observations

from backtest.models.entities import (
    PIT_ACCESS_POLICY_V1,
    DataSnapshotManifest,
    HistoricalObservationCache,
    StageAccessBoundary,
    build_historical_observation_cache_id,
    historical_observation_cache_content_fingerprint,
    historical_observation_cache_fingerprint,
    verify_snapshot_content_address,
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
        self, conn, boundary: StageAccessBoundary, manifest: DataSnapshotManifest,
        security_ids: tuple[str, ...], as_of: str, discovery_config: DiscoveryConfig,
    ) -> HistoricalObservationCache:
        ok, errors = verify_snapshot_content_address(manifest)
        if not ok:
            raise ValueError(
                f"cannot compute observations against a snapshot manifest that fails its own "
                f"content-address verification: {errors}"
            )
        if manifest.stage != boundary.zone:
            raise ValueError(
                f"snapshot manifest stage={manifest.stage!r} does not match boundary zone={boundary.zone!r}"
            )
        boundary.require_as_of_in_scope(as_of)
        if as_of > manifest.max_as_of:
            raise ValueError(f"as_of={as_of!r} exceeds this snapshot's own max_as_of={manifest.max_as_of!r}")

        sorted_ids = tuple(sorted(security_ids))
        if not set(sorted_ids) <= set(manifest.security_ids):
            raise ValueError(
                f"requested security_ids {sorted_ids} are not a subset of snapshot "
                f"{manifest.snapshot_id!r}'s own scope {manifest.security_ids}"
            )
        benchmark_security_id = manifest.benchmark_security_id

        key = (
            boundary.zone, as_of, sorted_ids, benchmark_security_id, manifest.snapshot_id,
            DISCOVERY_ENGINE_VERSION, discovery_config.config_version, PIT_ACCESS_POLICY_V1,
        )
        cached = self._entries.get(key)
        if cached is not None:
            return cached

        observations = compute_discovery_observations(
            conn, list(sorted_ids), as_of, benchmark_security_id, discovery_config,
        )
        self.compute_count += 1
        # Supervises Discovery's own indirect PIT reads (SS7): a cheap,
        # fail-loud sanity check on compute_discovery_observations()'s
        # own as_of contract, mirroring discovery/engine.py's own
        # _assert_no_future_leakage precedent -- not a substitute for
        # it, since #005 cannot intercept #002's internal pit.access
        # calls without patching #002.
        for obs in observations:
            if obs.as_of != as_of:
                raise AssertionError(
                    f"compute_discovery_observations() returned an observation with as_of={obs.as_of!r}, "
                    f"expected {as_of!r} -- #002's own as_of contract was violated"
                )

        observed_ids = {obs.security_id for obs in observations}
        # Explicit missingness (SS7): ineligible or no price history at
        # all -- either way, absence from `observations` is named here,
        # never silently indistinguishable from "checked and found
        # nothing to signal."
        missing = tuple(sid for sid in sorted_ids if sid not in observed_ids)

        fp = historical_observation_cache_fingerprint(
            boundary.zone, as_of, sorted_ids, benchmark_security_id, manifest.snapshot_id,
            DISCOVERY_ENGINE_VERSION, discovery_config.config_version, PIT_ACCESS_POLICY_V1,
        )
        cache_id, cache_hash = build_historical_observation_cache_id(fp)
        content_hash = historical_observation_cache_content_fingerprint(tuple(observations), missing)
        entry = HistoricalObservationCache(
            cache_id=cache_id, cache_hash=cache_hash, stage=boundary.zone, as_of=as_of,
            security_ids=sorted_ids, benchmark_security_id=benchmark_security_id, snapshot_id=manifest.snapshot_id,
            discovery_engine_version=DISCOVERY_ENGINE_VERSION,
            discovery_config_version=discovery_config.config_version,
            pit_access_policy=PIT_ACCESS_POLICY_V1, observations=tuple(observations),
            missing_security_ids=missing, observations_content_hash=content_hash,
        )
        self._entries[key] = entry
        return entry
