# Spec #001 -- Known Limitations

Explicit per SS27E ("nu ascundem limitările pentru a declara modulul
terminat"). None of these block acceptance per SS24 (TEST 8 is
explicitly allowed to stay `PENDING_LEVEL_2_DATA`); they're the honest
boundaries of what a Level 1 technical prototype, built with a single
free provider and no live network access, can actually claim.

## Environment

- **Live Yahoo Finance access is blocked in the sandbox this suite was
  built in.** The outbound proxy denies `fc.yahoo.com`,
  `guce.yahoo.com`, and `query2.finance.yahoo.com` (403, org egress
  policy). No workaround was attempted, per the environment's own
  instructions. The adapter (`adapters/yfinance_adapter.py`) is written
  against yfinance's real API shape and is exercised end-to-end by all
  12 mandatory tests via an injected fake `Ticker` (`tests/fixtures/fake_yfinance.py`)
  loaded with recorded fixture data -- but a live network smoke test
  has not been run. That should happen in an environment with network
  access before Level 1 is exercised against real data.

## Fixture data provenance

- Test fixtures (`tests/fixtures/market_data.py`) mix **real anchors**
  (event type, ratio, and date) with **synthetic OHLCV values**. Real
  anchors: AAPL's 4-for-1 split (ex-date 2020-08-31) and the FB -> META
  ticker rename (effective 2022-06-09) are well-documented public facts.
  The specific price numbers around them are synthetic placeholders
  (internally consistent, not verified real market prices), because
  live data pull was unavailable when this suite was built. Every other
  fixture (reverse split, dividend, ticker reuse, delisting, missing
  bar, invalid OHLC) is fully synthetic and uses deliberately
  non-real-looking tickers. Full provenance notes are in that file's
  module docstring.

## Identity resolution

- yfinance's free tier exposes no stable per-listing identifier (no
  ISIN/CIK/FIGI). `security_id` assignment is therefore **not**
  automatic: `model/ingestion.py` requires the caller to supply it
  (`ingestion.new_security_id(seed)` with a caller-chosen disambiguating
  seed string). Deciding "this ticker rename is the same company" vs
  "this ticker reuse is an unrelated company" is a Level 1
  orchestration/seed-data judgment call, not something the system
  infers from provider data. A Level 2/3 provider with a real
  cross-listing identifier would let this become automatic.

## Adjustment methodology

- `total_return_adjustment_factor` (see `model/adjustment_engine.py`
  docstring for the full formula) uses the **raw** close on the trading
  day before a dividend's ex-date as the ratio denominator, not a
  split-adjusted close. If a split and a dividend fall close together
  for the same security this slightly misstates the combined factor.
  None of the Level 1 fixtures exercise that overlap, so it isn't
  caught by the mandatory test suite. Flagged as a `v2` methodology
  improvement if it ever matters.
- Only `NOT_KNOWN` / `ANNOUNCED` / `EFFECTIVE` / `CANCELLED` are
  derived by the PIT layer. The original candidate status list (SS8)
  also included `CONFIRMED`; it isn't implemented because yfinance
  never supplies a distinct confirmation signal to derive it from.
  `source_status` / `source_status_date` are stored so a future,
  richer provider can drive `CANCELLED` (and could drive `CONFIRMED`)
  through the same mechanism without a schema change.

## Listing status

- `listing_status_history` has no separate announcement/effective
  distinction the way `corporate_actions` does. PIT filtering uses
  `effective_from` as both the event date and the information
  availability date. A delisting that was publicly telegraphed earlier
  (e.g. a trading halt pending delisting) isn't modeled at Level 1 --
  deferred to Level 2/3 if that granularity turns out to matter.
- At Level 1, no adapter sources listing status automatically (yfinance
  doesn't reliably expose it for free); it's populated directly via
  `repository.insert_listing_status` in test/seed code. Automated
  sourcing is deferred to a Level 2/3 provider or exchange feed.

## Data QA

- `MISSING_BAR` uses a plain Monday-Friday weekday calendar, not a real
  market holiday calendar. A real market holiday would currently be
  flagged as a false-positive gap. Test fixture date ranges were chosen
  to avoid real US holidays so this doesn't produce false positives in
  the mandatory suite; a production deployment needs a real trading
  calendar.
- `DUPLICATE_BAR` and `SOURCE_DISCREPANCY` are structurally wired
  (reason codes exist, severity-mapped, checked in code) but largely
  dormant at Level 1: the storage schema's natural key
  `(security_id, date, source_provider)` already prevents an exact
  same-provider duplicate from persisting, and only one provider
  (yfinance) is active, so there's nothing to cross-compare yet. Both
  become meaningful once Level 2/3 adds multi-provider ingestion or
  pre-storage batch inspection.
- `ADJUSTMENT_MISMATCH` is implemented and wired into the pipeline but
  has no dedicated test -- Level 1 fixtures set the provider's own
  adjusted close equal to raw close (no independent "provider adjusted"
  series was fabricated, to avoid presenting an invented number as if
  it were a real provider value). It will start being exercised once
  real yfinance `Adj Close` data is available.
- QA tuning parameters (`DEFAULT_GAP_THRESHOLD`, `DEFAULT_STALE_RUN_LENGTH`,
  `DEFAULT_MIN_HISTORY_BARS`, `DEFAULT_ADJUSTMENT_MISMATCH_TOLERANCE` in
  `qa/engine.py`) are reasonable Level 1 starting points, not validated
  against real-world false positive/negative rates. Revisit once Level
  2 QA validation data (Spec #001 SS21) is available. None of these are
  Universe Eligibility thresholds (Spec #001 SS2) -- they only affect
  whether an observation looks trustworthy, never whether the system
  wants to trade the instrument.

## Test coverage

- **TEST 8 (provider consistency) is `PENDING_LEVEL_2_DATA`**, approved
  by Radu (2026-09-20): Level 1 runs a single provider, so there is
  nothing to cross-compare. Not a false PASS.
