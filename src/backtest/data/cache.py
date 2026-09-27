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

`_ObservationCacheStore` (module-private) is reached ONLY through
`backtest.data.context.StageReadContext.get_or_compute_observations()`
-- never construct or call it directly outside a test exercising this
exact mechanism. `StageReadContext` is what supplies a connection
already narrowed to this stage's authorized data (see its own
docstring) and holds the read transaction the cache's own key is
implicitly trusting; calling this store directly, with an arbitrary
`conn`, defeats every guarantee `StageReadContext` exists to provide.

Batch 2 patch round-3 review (two more P1 findings closed here):

1. A changed `discovery_config` served under an UNCHANGED claimed
   `config_version` string used to pass straight through, including on
   what would otherwise be a cache hit (the stale cached entry was
   returned without ever re-checking the config that supposedly
   produced it). `get_or_compute()` now reloads the config fresh from
   disk and requires it to `==` the supplied `discovery_config` --
   covering BOTH a stale version (the reload's own `config_version`
   differs) and content tampered under an unchanged version (the
   reload's parsed dicts differ) -- BEFORE any cache-key lookup, not
   after.
2. Supervising Discovery's own indirect PIT reads by checking the
   returned `as_of` label alone (still done below) cannot catch a
   caller that reads out-of-scope data internally and then reports an
   honest label anyway. `StageReadContext` now passes this function an
   AUTHORIZED SUBSET connection (see `backtest.data.pit_access.
   build_authorized_price_subset_connection()`) with every price_history
   row beyond the stage's own boundary physically absent -- so even a
   substitute that ignores its own `as_of` parameter and reads with a
   larger one internally still cannot reach that data, regardless of
   what label it reports.
"""
from __future__ import annotations

from discovery.config.loader import DiscoveryConfig, load_config as load_discovery_config
from discovery.engine import DISCOVERY_ENGINE_VERSION, compute_discovery_observations

from backtest.models.entities import (
    PIT_ACCESS_POLICY_V1,
    DataSnapshotManifest,
    HistoricalObservationCache,
    StageAccessBoundary,
    build_historical_observation_cache_content_hash,
    build_historical_observation_cache_id,
    historical_observation_cache_content_fingerprint,
    historical_observation_cache_fingerprint,
    verify_snapshot_content_address,
)


def _require_fresh_discovery_config(discovery_config: DiscoveryConfig) -> None:
    fresh = load_discovery_config()
    if fresh != discovery_config:
        raise ValueError(
            f"discovery_config (config_version={discovery_config.config_version!r}) does not match a "
            f"fresh reload from disk (config_version={fresh.config_version!r}) -- either the claimed "
            f"version is stale, or the config content was changed while keeping the same claimed "
            f"version; both must be rejected before any cache lookup (Spec #005 SS7/SS21)"
        )


class _ObservationCacheStore:
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
        _require_fresh_discovery_config(discovery_config)

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
        # _assert_no_future_leakage precedent. This alone cannot catch a
        # caller that reads out-of-scope data and reports an honest
        # label anyway -- `conn` itself must already be the authorized
        # subset connection `StageReadContext` builds for exactly that
        # reason (see module docstring, point 2).
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
        content_fp = historical_observation_cache_content_fingerprint(tuple(observations), missing)
        content_hash = build_historical_observation_cache_content_hash(content_fp)
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
