# Spec #001 -- Test Report

Run: `python3 -m pytest tests/ -v` -- Python 3.11.15, pytest 9.1.1, yfinance 1.7.0, pandas 3.0.6, PyYAML 6.0.1.

Result: **14 passed, 1 skipped (PENDING_LEVEL_2_DATA)**, 0 failed.

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
| 11 | Corporate action timing | `tests/test_11_corporate_action_timing.py` | **PASS** | Reproduces Radu's own worked example (`announcement_date=2024-05-22`, `effective_date=2024-06-10`) exactly: `NOT_KNOWN` / `ANNOUNCED` / `EFFECTIVE` at the three checkpoints; invisible to `get_corporate_actions_as_of` before announcement; adjustment factor confirmed still `1.0` while merely `ANNOUNCED` (not applied prematurely). |
| 12 | Universe sanity | `tests/test_12_universe_sanity.py` | **PASS** | Plausibility check (not exact equality) over a 6-security Level 1 test universe: security count and per-security bar counts fall within the expected weekday-calendar range. |

## How to reproduce

```bash
pip install -r requirements.txt
python3 -m pytest tests/ -v
```

No network access is required or attempted -- all 12 tests run against recorded fixture data (`tests/fixtures/`), since live Yahoo Finance access is blocked in the sandbox this suite was built in (see `docs/known_limitations.md`).
