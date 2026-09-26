# Spec #001 -- Test Report

Run: `python3 -m pytest tests/ -v` -- Python 3.11.15, pytest 9.1.1, yfinance 1.7.0, pandas 3.0.6, PyYAML 6.0.1.

Result: **34 passed, 1 skipped (PENDING_LEVEL_2_DATA)**, 0 failed.

Updated 2026-09-26, fifth round -- PATCH #001-D: `split_adjusted_open`/
`split_adjusted_high`/`split_adjusted_low` added to `PITPriceBar`
(surfaced while architecting Spec #005's Backtester -- an executable
`NEXT_BAR_OPEN` entry price and MAE/MFE both need adjusted open/high/low,
which only `split_adjusted_close` didn't cover). Fixed in Data
Foundation, before any #005 code was written, per the same standing rule
as PATCH #001-C. TEST 17 added (factor correctness, OHLC ordering
preservation, boundary continuity, PIT knowledge-time immunity). TESTs
1-16 unchanged and still passing.

Prior round (fourth) -- PATCH #001-C: `split_adjusted_volume`
added to `PITPriceBar` (Radu's correction, prompted by a real gap Spec
#002's Discovery Engine surfaced -- raw, unadjusted volume paired with
split-adjusted close produced a mechanical level-shift around a split).
Fixed in Data Foundation, not in the downstream Discovery module, per
Radu's own standing rule. TEST 16 added (formula/continuity/round-trip
invariant). TESTs 1-15 unchanged and still passing.

Prior round (third) -- GPT Final Review #001 on commit
`bc4c914` confirmed PATCH A/B were correct at the PIT/query layer, but
found a more important bug underneath: `corporate_actions` and
`listing_status_history` writes used `INSERT OR IGNORE`, which would
have silently dropped a real re-ingested revision (e.g. a status update
to `CANCELLED`) forever, making PATCH A's fix unreachable in the actual
ingestion pipeline. Fixed with an enrichment upsert (see
`docs/architecture.md`). TEST 14c added (exercises the fix through the
real `ingestion -> repository -> PIT` path, not a directly-constructed
row) and a matching enrichment test added to TEST 15. TESTs 1-13
unchanged and still passing.

| # | Test | File | Result | Notes |
|---|------|------|--------|-------|
| 1 | OHLC integrity | `tests/test_01_ohlc_integrity.py` | **PASS** | Injected `low>high` and negative-price bars both detected via QA (`OHLC_INVALID`, `NEGATIVE_PRICE`, `qa_pass=False`); clean bars unflagged. |
| 2 | Split correctness | `tests/test_02_split_correctness.py` | **PASS** | Parametrized over a forward split (AAPL, real ratio+date anchor: 4-for-1, ex-date 2020-08-31) and a reverse split (RVSQ, synthetic, 1-for-5). Raw prices preserved, corporate action recorded, split-adjusted series continuous across the boundary (<5% residual jump vs >50% raw jump). |
| 3 | Dividend handling | `tests/test_03_dividend_handling.py` | **PASS** | Dividend identified as `DIVIDEND`, never `SPLIT`; raw price bars unmodified. |
| 4 | Delisting PIT | `tests/test_04_delisting_pit.py` | **PASS** | `as_of` before delisting shows ACTIVE with no delisting reason (including the day immediately before effective); `as_of` after shows DELISTED with reason. No hindsight leakage. |
| 5 | Ticker change | `tests/test_05_ticker_change.py` | **PASS** | Real anchor: FB -> META rename, effective 2022-06-09. Same `security_id` throughout; `get_ticker_as_of` / `get_security_id_for_ticker_as_of` resolve correctly on both sides of the rename; price history continuous. |
| 6 | Ticker reuse | `tests/test_06_ticker_reuse.py` | **PASS** | Synthetic ticker "ZZZQ" used by two unrelated companies in non-overlapping eras: distinct `security_id`s, disjoint price histories, no `IDENTIFIER_CONFLICT` for the legitimate case. A second, deliberately-corrupted case (overlapping windows) confirms `IDENTIFIER_CONFLICT` fires when it should. |
| 7 | Missing data | `tests/test_07_missing_data.py` | **PASS** | An injected gap produces no synthesized row (no silent fill) and is reported as `MISSING_BAR`. |
| 8 | Provider consistency | `tests/test_08_provider_consistency.py` | **PENDING_LEVEL_2_DATA** | Requires a second provider adapter to cross-compare; Level 1 runs yfinance only. Approved by Radu (2026-09-20) to defer rather than claim a false PASS. |
| 9 | PIT look-ahead | `tests/test_09_pit_look_ahead.py` | **PASS** | The most critical test. `get_data(as_of=X)` snapshot taken, then future-dated bars *and* the split corporate action itself are ingested, then `get_data(as_of=X)` repeated. Snapshots are asserted byte-identical (full dataclass equality). |
| 10 | Direct access | `tests/test_10_direct_access.py` | **PASS** | Structural, not conventional: an AST scan of `src/data_foundation/**/*.py` asserts no module outside `model/ adapters/ storage/ pit/ qa/` imports the repository layer directly. Also asserts `pit.access.get_data` exists as the gateway entry point. |
| 11 | Corporate action timing | `tests/test_11_corporate_action_timing.py` | **PASS** | Reproduces Radu's own worked example (`announcement_date=2024-05-22`, `effective_date=2024-06-10`, now also set as `available_at`) exactly: `NOT_KNOWN` / `ANNOUNCED` / `EFFECTIVE` at the three checkpoints, each with `knowledge_time_status="KNOWN"`; invisible to `get_corporate_actions_as_of` before availability; adjustment factor confirmed still `1.0` while merely `ANNOUNCED` (not applied prematurely). |
| 12 | Universe sanity | `tests/test_12_universe_sanity.py` | **PASS** | Plausibility check (not exact equality) over a 6-security Level 1 test universe: security count and per-security bar counts fall within the expected weekday-calendar range. |
| 13a | Knowledge-time: `available_at > effective_date` | `tests/test_13_knowledge_time_policy.py::test_available_at_after_effective_date_is_respected` | **PASS** | Retroactively-disclosed action (event happened 2024-03-01, only knowable from 2024-03-15): status stays `NOT_KNOWN` and the action is invisible even though `effective_date` has passed; the split-adjusted price series also does not reflect the split until `available_at`, then correctly does for pre-split historical dates. |
| 13b | Knowledge-time: `available_at=NULL` preserves Level 1 behavior | `tests/test_13_knowledge_time_policy.py::test_available_at_null_preserves_level1_effective_date_fallback` | **PASS** | AAPL split (yfinance-sourced, no announcement date available): confirms no `ANNOUNCED` phase ever appears and every result is tagged `knowledge_time_status="UNKNOWN"`, matching the documented Level 1 fallback. |
| 13c | Knowledge-time: ingestion time never substitutes for knowledge time | `tests/test_13_knowledge_time_policy.py::test_ingestion_timestamp_never_used_as_knowledge_time` | **PASS** | Two rows for the same historical split, `ingestion_timestamp` set to 2020 vs. 2026 respectively, produce byte-identical PIT results at every `as_of` tested -- directly the "downloading a 2020 split today must not make it unknown in 2020" property Radu flagged. |
| 14a | Cancelled action does not adjust prices | `tests/test_14_cancelled_action_adjustment.py::test_cancelled_split_does_not_adjust_prices_once_cancellation_is_known` | **PASS** | Reproduces GPT's exact bug report: `available_at`=2024-03-01, `effective_date`=2024-03-20, cancelled 2024-03-15, queried `as_of`=2024-03-25. Metadata correctly reports `CANCELLED`; before the fix, `split_adjusted_close` would still have reflected the (never-executed) split -- after the fix it equals `raw_close` on every date. |
| 14b | Pending action still adjusts before its cancellation is knowable | `tests/test_14_cancelled_action_adjustment.py::test_pending_action_still_adjusts_before_its_cancellation_is_knowable` | **PASS** | Symmetry check on the PATCH A fix: at an `as_of` before `source_status_date`, a since-cancelled action is treated as still pending/effective, matching what a PIT-simulated researcher at that earlier moment would actually have seen. |
| 15a | Listing status hidden before `available_at` | `tests/test_15_listing_status_knowledge_time.py::test_listing_status_hidden_before_available_at` | **PASS** | A retroactively-confirmed delisting (`effective_from`=2019-03-01, `available_at`=2019-03-20) is invisible at `as_of`=2019-03-10 (`listing_status=None`) and visible, tagged `KNOWN`, at `as_of`=2019-03-20. |
| 15b | Listing status `available_at=NULL` tagged UNKNOWN | `tests/test_15_listing_status_knowledge_time.py::test_listing_status_available_at_null_is_tagged_unknown` | **PASS** | No knowledge-time signal -> falls back to `effective_from`/`effective_to`-only behavior, explicitly tagged `knowledge_time_status="UNKNOWN"`, never silently treated as `KNOWN`. |
| 14c | Re-ingested cancellation reaches PIT through the real pipeline | `tests/test_14_cancelled_action_adjustment.py::test_reingested_cancellation_reaches_pit_through_real_pipeline` | **PASS** | The persistence-lifecycle bug GPT's follow-up review flagged: same `action_id` ingested twice via the real `ingestion.ingest_corporate_actions()` path (T0 pending, T1 `CANCELLED`). Confirms a single row is updated (not duplicated), `ingestion_timestamp` preserved as first-seen, `last_updated_timestamp` reflects the revision, and the adjusted price series correctly stops reflecting the split once queried `as_of` >= `source_status_date`. Would have failed against the pre-fix `INSERT OR IGNORE` behavior. |
| 15c | Listing status `available_at` enrichment via re-ingestion | `tests/test_15_listing_status_knowledge_time.py::test_listing_status_available_at_enrichment_updates_existing_row` | **PASS** | Same persistence-lifecycle class of fix for listing status: re-upserting the same `(security_id, effective_from)` with a newly-supplied `available_at` updates the existing row rather than being dropped, and a date visible under the old NULL/UNKNOWN policy correctly becomes hidden again once the real `available_at` shows it wasn't actually knowable yet. |
| 16a | Split-adjusted volume round-trip invariant | `tests/test_16_split_adjusted_volume.py::test_split_adjusted_volume_round_trip_invariant` | **PASS** (2 sub-cases: forward AAPL 4-for-1, reverse RVSQ 1-for-5) | `split_adjusted_close * split_adjusted_volume == raw_close * raw_volume` for every bar; `raw_volume` confirmed unmodified. Verified to fail if the volume formula's direction is inverted (`raw_volume * split_factor` instead of `/`). |
| 16b | Split-adjusted volume continuity across the split boundary | `tests/test_16_split_adjusted_volume.py::test_split_adjusted_volume_continuous_across_split_boundary` | **PASS** (2 sub-cases: 4-for-1 forward, 1-for-5 reverse) | Dedicated fixture where `raw_volume` already reflects a genuine post-split share-count change proportional to the ratio (100->400 forward, 500->100 reverse) -- `split_adjusted_volume` stays constant across the boundary for both directions, same formula, no special-casing. |
| 17a | Split-adjusted OHLC factor correctness | `tests/test_17_split_adjusted_ohlc.py::test_split_adjusted_ohlc_factor_correctness` | **PASS** (2 sub-cases: forward AAPL 4-for-1, reverse RVSQ 1-for-5) | `split_adjusted_open/high/low == raw_open/high/low * split_factor` for every bar, using the SAME factor implicitly recovered from `split_adjusted_close`; `raw_open/high/low` confirmed unmodified. |
| 17b | Split-adjusted OHLC ordering preserved | `tests/test_17_split_adjusted_ohlc.py::test_split_adjusted_ohlc_ordering_preserved` | **PASS** (2 sub-cases) | `split_adjusted_low <= split_adjusted_open,close <= split_adjusted_high` for every bar -- scaling by a positive factor must never invert a bar's own internal ordering. |
| 17c | Split-adjusted OHLC continuity across the split boundary | `tests/test_17_split_adjusted_ohlc.py::test_split_adjusted_ohlc_continuous_across_split_boundary` | **PASS** (2 sub-cases) | Mirrors TEST 2's close-only continuity check, extended to open/high/low (<5% residual jump at the boundary). |
| 17d | Split-adjusted OHLC PIT immunity before the split is knowable | `tests/test_17_split_adjusted_ohlc.py::test_split_adjusted_ohlc_pit_immune_before_split_knowable` | **PASS** | Mirrors TEST 9 exactly (byte-identical `get_data`-equivalent snapshot before/after future-dated split data is ingested), asserting specifically on `split_adjusted_open/high/low` -- proves the as_of-scoped factor computation that already protected `split_adjusted_close` protects the new fields with no separate PIT logic to get wrong. |

## GPT Review #001 (commit `8492ade`) findings and resolution

| Finding | Severity | Resolution |
|---|---|---|
| PATCH A: `_is_action_known_for_adjustment()` ignored `CANCELLED` status -- a cancelled split/dividend could still alter the adjusted price series even though `derive_corporate_action_pit_status()` correctly reported it as cancelled. | Bug (adjustment/PIT correctness) | Fixed: the same cancellation gate (`source_status == "CANCELLED"` and `as_of >= source_status_date`) is now checked in both functions. TEST 14a/14b. |
| PATCH B: `listing_status_history` had no knowledge-time field -- a retroactively-confirmed status change could appear before it was actually knowable. | Confirmed gap (previously documented) | Closed: nullable `available_at` added, same `KNOWN`/`UNKNOWN` pattern as corporate actions, deliberately minimal. TEST 15a/15b. |
| `qa_results.computed_at` not checked against `as_of` -- a QA recompute using later data can retroactively change a historical `qa_pass`. | Documentation-only, `PENDING` | Not fixed (explicitly deferred, no mandatory test exercises it). Logged in `docs/known_limitations.md` as a blocker for Discovery consuming `qa_pass`, not for Level 1 acceptance. |

## GPT Final Review #001 (commit `bc4c914`) findings and resolution

| Finding | Severity | Resolution |
|---|---|---|
| `corporate_actions`/`listing_status_history` writes used `INSERT OR IGNORE`, keyed on `action_id` / `(security_id, effective_from)` -- a real re-ingested revision (e.g. status -> `CANCELLED`) would be silently dropped forever, making PATCH A's fix unreachable in the actual pipeline. | Bug (persistence lifecycle) -- flagged as more important than PATCH A/B themselves | Fixed: enrichment upsert (`repository.upsert_corporate_action`, `repository.upsert_listing_status`) -- only genuinely-revisable fields updated, only when the new value is non-NULL, `ingestion_timestamp` preserved, new `last_updated_timestamp` added. TEST 14c, TEST 15c. |
| Schema change doesn't migrate an existing on-disk database (`CREATE TABLE IF NOT EXISTS` doesn't add new columns). | Documentation-only, accepted for Level 1 | Not fixed (no migration infrastructure built). `SCHEMA_VERSION` comment added to `schema.sql`; policy documented in `storage/db.py` and `docs/known_limitations.md`: delete and recreate the SQLite file on a schema change. No persisted `.db` file exists anywhere in this repo currently, so this is presently inert. |
| Two narrower gaps in the enrichment-upsert design itself. | Documentation-only, accepted for Level 1 | `action_id` changes if `action_type`/`effective_date`/`value` are corrected (treated as a new action, not a revision); `COALESCE` can't clear a previously-set fact back to unknown. Both logged in `docs/known_limitations.md`, neither needed by any Level 1 scenario. |

## PATCH #001-C (Radu's correction, 2026-09-21) finding and resolution

| Finding | Severity | Resolution |
|---|---|---|
| `PITPriceBar` exposed only `raw_volume` (unadjusted); Spec #002's Discovery Engine paired it with `split_adjusted_close` (adjusted), so a split produced a mechanical level-shift in volume that could look like a real spike -- a real Data Foundation gap surfaced by a downstream consumer, not a Spec #002 defect. | Bug (missing interface, pre-real-data-backtesting blocker per `docs/spec002_known_limitations.md`) | Fixed in Data Foundation, not in Discovery, per Radu's own standing rule: `split_adjusted_volume` added to `PITPriceBar`, derived on-the-fly as `raw_volume / split_factor` (opposite direction from price) using the same PIT-safe `split_factor`. No schema change. TEST 16. Discovery's `_price_series_to_df()` updated to consume it (Spec #002 PATCH, no lane/formula changes -- see `docs/spec002_known_limitations.md` and TEST 23). |

## PATCH #001-D (GPT Review #005 scaffold blocker A, 2026-09-26) finding and resolution

| Finding | Severity | Resolution |
|---|---|---|
| `PITPriceBar` exposed `split_adjusted_close`/`split_adjusted_volume` but only `raw_open`/`raw_high`/`raw_low` -- surfaced while architecting Spec #005's Backtester: an executable `NEXT_BAR_OPEN` entry price and MAE/MFE both need adjusted open/high/low, and #005 cannot derive them from `split_adjusted_close` alone. | IMPLEMENTATION BLOCKER for Spec #005 (flagged explicitly, not silently patched around in #005) | Fixed in Data Foundation, before any #005 code was written: `split_adjusted_open/high/low` added to `PITPriceBar`, computed as `raw_open/high/low * split_factor` -- the SAME PIT-safe `split_factor` already used for `split_adjusted_close`, applied identically (a split scales an entire OHLC bar uniformly). No schema change, no new methodology, `raw_open/high/low` untouched, total-return-adjusted OHLC deliberately not added (no #005 v1 consumer -- price-return only). TEST 17. |

## How to reproduce

```bash
pip install -r requirements.txt
python3 -m pytest tests/ -v
```

No network access is required or attempted -- all tests run against recorded fixture data (`tests/fixtures/`) or directly-constructed rows for pure PIT-logic cases, since live Yahoo Finance access is blocked in the sandbox this suite was built in (see `docs/known_limitations.md`).
