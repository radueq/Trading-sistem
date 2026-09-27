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

Batch 2 patch round-3 review (two more P1 findings closed then):

1. A changed `discovery_config` served under an UNCHANGED claimed
   `config_version` string used to pass straight through, including on
   what would otherwise be a cache hit.
2. Supervising Discovery's own indirect PIT reads by checking the
   returned `as_of` label alone (still done below) cannot catch a
   caller that reads out-of-scope data internally and then reports an
   honest label anyway. `StageReadContext` passes this function an
   AUTHORIZED SUBSET connection (see `backtest.data.pit_access.
   build_authorized_subset_connection()`).

Batch 2 patch round-4 review (finding #3 and the P2 config finding):

3. `as_of` was only checked against `manifest.max_as_of` -- nothing
   stopped a request for a date before this run's own declared
   warm-up/history start, a domain the manifest's own `min_as_of` field
   now names explicitly (see `backtest.data.snapshot`). `get_or_compute()`
   now rejects `as_of < manifest.min_as_of` too.
4. (P2) `_require_fresh_discovery_config()` used to always reload from
   the CURRENT DEFAULT config directory (`discovery.config.loader.
   load_config()` with no argument) -- this ties every run to whatever
   the live default happens to be TODAY, when the contract is to verify
   the FROZEN ARTIFACT actually supplied to THIS run. A validly archived
   config (its own genuinely-computed `config_version`, loaded from a
   directory that is no longer the live default) must remain usable
   even after the default has since changed. `get_or_compute()` now
   takes an optional `config_dir` -- the directory `discovery_config`
   itself was loaded from -- and reloads from THAT path; `None` (the
   default for every caller today, since Batch 2 has no ResearchPlan-
   level archived-config-directory field yet) reloads the current
   default directory, preserving prior behavior for the common case.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

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


def _require_fresh_discovery_config(discovery_config: DiscoveryConfig, config_dir: Optional[Path]) -> None:
    fresh = load_discovery_config(config_dir)
    if fresh != discovery_config:
        raise ValueError(
            f"discovery_config (config_version={discovery_config.config_version!r}) does not match a "
            f"fresh reload from {config_dir or 'the default config directory'!r} "
            f"(config_version={fresh.config_version!r}) -- either the claimed version is stale, or the "
            f"content was changed while keeping the same claimed version; both must be rejected before "
            f"any cache lookup, against the artifact actually supplied to this run (Spec #005 SS7/SS21)"
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
        config_dir: Optional[Path] = None,
    ) -> HistoricalObservationCache:
        _require_fresh_discovery_config(discovery_config, config_dir)

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
        if as_of < manifest.min_as_of:
            raise ValueError(
                f"as_of={as_of!r} is before this snapshot's own min_as_of={manifest.min_as_of!r} -- the "
                f"calendar never vouched for anything earlier, and this snapshot never hashed it"
            )

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
