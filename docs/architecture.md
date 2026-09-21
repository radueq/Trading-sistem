# Spec #001 -- Architecture Note

## Structure

```
src/data_foundation/
  adapters/
    base.py                 ProviderAdapter contract + Raw* carriers
    yfinance_adapter.py      Level 1 provider adapter
  model/
    entities.py              dataclasses for the 7 schema components
    repository.py            typed reads/writes against sqlite (the ONLY module
                              that touches SQL directly outside storage/)
    ingestion.py              orchestration: drives an adapter, assigns
                              security_id, writes via repository
    adjustment_engine.py      split / total-return factor computation
  storage/
    schema.sql                table definitions
    db.py                    sqlite connection + schema init
  pit/
    access.py                 THE single gateway -- get_data(security_id, as_of)
  qa/
    engine.py                  Data QA checks
    reason_codes.py           ReasonCode / Severity enums
    config/severity_mapping.yaml   external, editable severity config
tests/
  fixtures/                  TEST_CONFIG data (market_data.py, fake_yfinance.py)
  test_01..12_*.py            the 12 mandatory tests (Spec #001 SS23)
  test_13_knowledge_time_policy.py  knowledge-time patch coverage (2026-09-21)
docs/
  architecture.md             this file
  known_limitations.md
  test_report.md
```

## Where things are

- **Provider Adapter**: `adapters/yfinance_adapter.py`, implementing the
  `ProviderAdapter` contract in `adapters/base.py`. All yfinance-specific
  behavior (column names, `auto_adjust=False` semantics, the fact that
  yfinance never exposes a corporate-action announcement date) is
  isolated here. The `yfinance.Ticker` object is injected via a
  `ticker_factory` callable, so tests exercise the real adapter code
  against recorded fixture data without live network access, and
  production use just passes the default factory (real `yfinance.Ticker`).

- **PIT Access Layer**: `pit/access.py`. `get_data(conn, security_id,
  as_of)` is the single entry point. It composes ticker resolution,
  listing-status resolution, corporate-action status derivation, and
  price/adjustment retrieval -- all filtered or recomputed against
  `as_of`. Crucially, it does **not** read the precomputed, full-history
  `adjustment_factors` table (that table reflects today's best
  knowledge and would leak future corporate actions into a simulated
  historical query) -- it recomputes split/total-return factors from an
  `as_of`-scoped corporate-actions set every time (see the module
  docstring and TEST 9).

- **Data QA**: `qa/engine.py`. Runs against the model layer directly
  (see below), not through the PIT gateway -- it is a Data Foundation
  pipeline stage in its own right (Spec #001 SS1's own diagram places
  QA after PIT, as part of the same pipeline, not as a downstream
  research consumer), and it needs full observed history to do its job
  (e.g. detecting a missing bar requires scanning the whole date range).
  Severity classification (`reason_code -> severity`) is loaded from
  `qa/config/severity_mapping.yaml`, editable without a code change.

- **Corporate action status**: never stored. `corporate_actions` rows
  hold only `announcement_date`, `effective_date`, `source_status`,
  `source_status_date`, `available_at` -- persisted facts.
  `pit.access.derive_corporate_action_pit_status()` computes
  `NOT_KNOWN` / `ANNOUNCED` / `EFFECTIVE` / `CANCELLED` fresh for a given
  `as_of` every call, per Radu's 2026-09-20 correction to SS8/28 -- this
  keeps the same stored row from ever changing meaning based on which
  wall-clock day ingestion happened to run.

- **Knowledge-time (`available_at`)**: added 2026-09-21 per Radu's
  correction. Three time axes are kept strictly separate on every
  corporate action: `effective_date` (event time), `available_at`
  (knowledge time, nullable), and `ingestion_timestamp` (pure audit
  metadata). `derive_corporate_action_pit_status()` now returns
  `(pit_status, knowledge_time_status)`: when `available_at` is known,
  it gates exposure directly; when it's `NULL` (every yfinance-sourced
  action today -- yfinance supplies no announcement date), the function
  falls back to gating on `effective_date` alone (no `ANNOUNCED` phase,
  since there's no evidence one was ever observable) and tags the result
  `knowledge_time_status = UNKNOWN`. `ingestion_timestamp` is never
  substituted as a knowledge-time proxy anywhere in this codebase --
  doing so would make a 2020 split downloaded today appear "unknown" in
  2020, which is simply wrong (TEST 13-C). `pit.get_price_series_as_of`'s
  as_of-scoped adjustment-factor recomputation respects the same rule:
  a corporate action only affects the adjusted price series once it has
  both happened (`effective_date <= as_of`) and, where a validated signal
  exists, been knowable (`available_at <= as_of`) -- see
  `_is_action_known_for_adjustment()` and TEST 13-A (a retroactively-
  disclosed action, `available_at > effective_date`).
  `model/ingestion.py`'s Level 1 policy: `available_at` is set to the
  adapter's `announcement_date` when supplied, else left `NULL` --
  never guessed.

- **Total-return methodology status**: `AdjustmentFactor.total_return_status`
  and `PITPriceBar.total_return_status` are always
  `EXPERIMENTAL_NOT_APPROVED_FOR_RESEARCH` (Radu's correction,
  2026-09-21, `adjustment_engine.TOTAL_RETURN_STATUS`) -- the dividend-
  reinvestment math has not been validated against real provider or
  reference data. `split_adjustment_factor` / `split_adjusted_close`
  carry no such caveat and remain available as-is (TEST 2 validates
  them directly).

## Who may call what

Per SS10-11 ("single controlled gateway"): only `model/`, `adapters/`,
`storage/`, `pit/`, and `qa/` may import `model/repository.py` directly.
A downstream research consumer (Discovery Engine, Candidate Selector,
Hypothesis Engine, Backtester, Evaluation Engine -- none exist yet,
out of scope for Spec #001) must go through `pit.access.get_data()`
only. This is enforced structurally, not just by convention: TEST 10
(`tests/test_10_direct_access.py`) runs an AST scan of every file under
`src/data_foundation/` and fails the build if any module outside that
allow-list imports the repository layer.

Storage-level and adapter-level tests are the one exemption from the
gateway rule (Radu's clarification, 2026-09-20) -- they test storage/the
adapter itself, and that exemption is scoped to `tests/`, never to
`src/`.

## Adding a new provider

1. Add `adapters/<provider>_adapter.py` implementing `ProviderAdapter`
   (`fetch_security_info`, `fetch_price_history`, `fetch_corporate_actions`),
   returning the same `Raw*` carriers `adapters/base.py` defines.
   Provider-specific quirks stay inside this one file (SS19: no
   `if provider == "X":` anywhere else).
2. Reuse `model/ingestion.py` unchanged -- it's generic over any
   `ProviderAdapter`.
3. For cross-provider comparison (TEST 8 / SOURCE_DISCREPANCY), ingest
   the same security under both adapters and compare via `pit.get_data`
   snapshots, or extend `qa/engine.py`'s `SOURCE_DISCREPANCY` check
   (currently dormant with a single provider).

## Pipeline order dependency

`qa/engine.py`'s `ADJUSTMENT_MISMATCH` check reads the precomputed
`adjustment_factors` table, so the expected pipeline order per security is:

```
ingest prices + corporate actions
  -> adjustment_engine.compute_and_store_adjustment_factors
  -> qa.engine.run_and_store_qa_checks
```

Skipping the adjustment step just means `ADJUSTMENT_MISMATCH` never
fires (there's nothing to compare against) -- it does not affect any of
the other checks or any mandatory test.

## Why sqlite, no ORM

Per SS26 ("don't optimize prematurely, don't build infrastructure for
problems we don't have yet"): plain `sqlite3` + hand-written SQL in
`storage/schema.sql` and `model/repository.py`. Nothing upstream depends
on sqlite specifics -- migrating to Postgres later means replacing
`storage/db.py` and the connection type, not the schema design or any
caller.
