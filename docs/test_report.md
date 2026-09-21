# Spec #001 -- Test Report

Run: `python3 -m pytest tests/ -v` -- Python 3.11.15, pytest 9.1.1, yfinance 1.7.0, pandas 3.0.6, PyYAML 6.0.1.

Result: **21 passed, 1 skipped (PENDING_LEVEL_2_DATA)**, 0 failed.

Updated 2026-09-21, second round -- GPT Review #001 on commit `8492ade`
found one concrete bug (PATCH A) and one confirmed gap (PATCH B), both
now fixed/closed and covered by new tests. TEST 14 added (cancelled
corporate actions must not leak into the adjusted price series) and
TEST 15 added (listing_status_history gets the same `available_at`
knowledge-time field as corporate_actions). TESTs 1-13 unchanged and
still passing on the patched code -- TEST 4 additionally now doubles as
the `available_at=NULL` case for listing status.

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

## GPT Review #001 (commit `8492ade`) findings and resolution

| Finding | Severity | Resolution |
|---|---|---|
| PATCH A: `_is_action_known_for_adjustment()` ignored `CANCELLED` status -- a cancelled split/dividend could still alter the adjusted price series even though `derive_corporate_action_pit_status()` correctly reported it as cancelled. | Bug (adjustment/PIT correctness) | Fixed: the same cancellation gate (`source_status == "CANCELLED"` and `as_of >= source_status_date`) is now checked in both functions. TEST 14. |
| PATCH B: `listing_status_history` had no knowledge-time field -- a retroactively-confirmed status change could appear before it was actually knowable. | Confirmed gap (previously documented) | Closed: nullable `available_at` added, same `KNOWN`/`UNKNOWN` pattern as corporate actions, deliberately minimal. TEST 15. |
| `qa_results.computed_at` not checked against `as_of` -- a QA recompute using later data can retroactively change a historical `qa_pass`. | Documentation-only, `PENDING` | Not fixed (explicitly deferred, no mandatory test exercises it). Logged in `docs/known_limitations.md` as a blocker for Discovery consuming `qa_pass`, not for Level 1 acceptance. |

## How to reproduce

```bash
pip install -r requirements.txt
python3 -m pytest tests/ -v
```

No network access is required or attempted -- all tests run against recorded fixture data (`tests/fixtures/`) or directly-constructed rows for pure PIT-logic cases, since live Yahoo Finance access is blocked in the sandbox this suite was built in (see `docs/known_limitations.md`).
