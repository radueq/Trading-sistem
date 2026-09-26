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

## Persistence & schema versioning

- **No migration path at Level 1** (GPT Final Review #001, 2026-09-21).
  `storage/schema.sql` carries a `SCHEMA_VERSION` comment (currently 3),
  but `CREATE TABLE IF NOT EXISTS` does **not** add new columns to an
  existing on-disk database -- it silently does nothing if the table
  already exists under an older shape. A schema change (like the
  `available_at` / `last_updated_timestamp` columns added in this patch
  round) requires deleting and recreating the SQLite file, not migrating
  one in place. Accepted explicitly for now: no persisted database file
  exists anywhere in this repository (every test uses `:memory:`), so
  there is currently nothing to actually migrate. Revisit with real
  migration infrastructure (e.g. `ALTER TABLE`-based versioned
  migrations) before any Level 1 database is expected to persist across
  a schema change.

## Adjustment methodology

- **`total_return_adjusted_close` is `EXPERIMENTAL_NOT_APPROVED_FOR_RESEARCH`**
  (Radu's correction, 2026-09-21; `adjustment_engine.TOTAL_RETURN_STATUS`,
  carried on every `AdjustmentFactor` row and every `PITPriceBar` so the
  marking travels with the data itself, not just this document). The
  dividend-reinvestment math has not been validated against real
  provider or reference total-return data. `split_adjustment_factor` /
  `split_adjusted_close` carry no such caveat and remain available as-is.
- `total_return_adjustment_factor` (see `model/adjustment_engine.py`
  docstring for the full formula) uses the **raw** close on the trading
  day before a dividend's ex-date as the ratio denominator, not a
  split-adjusted close. If a split and a dividend fall close together
  for the same security this slightly misstates the combined factor.
  None of the Level 1 fixtures exercise that overlap, so it isn't
  caught by the mandatory test suite. Flagged as a `v2` methodology
  improvement if it ever matters -- moot anyway while the series is
  EXPERIMENTAL.
- Only `NOT_KNOWN` / `ANNOUNCED` / `EFFECTIVE` / `CANCELLED` are
  derived by the PIT layer. The original candidate status list (SS8)
  also included `CONFIRMED`; it isn't implemented because yfinance
  never supplies a distinct confirmation signal to derive it from.
  `source_status` / `source_status_date` are stored so a future,
  richer provider can drive `CANCELLED` (and could drive `CONFIRMED`)
  through the same mechanism without a schema change.

## Knowledge-time (`available_at`)

Added 2026-09-21 per Radu's correction, replacing the earlier implicit
announcement-date-or-effective-date fallback with an explicit, nullable
`available_at` field and an explicit `knowledge_time_status` (`KNOWN` /
`UNKNOWN`) carried on every `PITCorporateAction` result.

- **`available_at` is `NULL` for every yfinance-sourced corporate action
  today.** yfinance's free tier supplies no announcement date, so
  `model/ingestion.py` never has a trustworthy signal to populate it
  with. `pit.access.derive_corporate_action_pit_status()` falls back to
  gating exposure on `effective_date` alone (no `ANNOUNCED` phase) and
  tags every such result `knowledge_time_status = UNKNOWN`. This is a
  Level 1 shortcut, not validated PIT correctness -- **before Level 3,
  any `UNKNOWN` case that could actually affect PIT research must be
  resolved with real provider/announcement data**, not left as a
  permanent substitute.
- `ingestion_timestamp` is never used as a knowledge-time proxy anywhere
  in this codebase (enforced by TEST 13-C: two rows for the same
  historical event, differing only in `ingestion_timestamp`, produce
  identical PIT results at every `as_of`). Using it would have made a
  2020 split downloaded today appear "unknown" in 2020 -- obviously
  wrong, since it really was public knowledge in 2020 regardless of when
  our system got around to ingesting it.
- **Update 2026-09-21 (GPT Review #001 PATCH A):** the first cut of the
  as_of-scoped adjustment recomputation (`_is_action_known_for_adjustment`)
  checked `effective_date` and `available_at` but not cancellation --
  `derive_corporate_action_pit_status()` correctly reported CANCELLED,
  but a cancelled split/dividend could still alter the adjusted price
  series regardless. Fixed: the same function now also excludes an
  action once its cancellation is knowable (`source_status_date <=
  as_of`), symmetric with the status-derivation function. See TEST 14.
- **Update 2026-09-21 (GPT Review #001 PATCH B):** `listing_status_history`
  now carries the same nullable `available_at` field as
  `corporate_actions` (see below) -- the knowledge-time axis is no
  longer corporate-actions-only.
- **Update 2026-09-21 (GPT Final Review #001 -- persistence lifecycle,
  more important than PATCH A/B themselves):** PATCH A/B were correct at
  the PIT/query layer, but `corporate_actions` and `listing_status_history`
  writes used `INSERT OR IGNORE`. In the real pipeline the same action is
  typically ingested more than once as new information arrives (pending
  -> `CANCELLED`); under `INSERT OR IGNORE` that second, more-informative
  row is silently and permanently dropped, so PATCH A's `CANCELLED` gate
  would never actually fire against real re-ingested data. Fixed with an
  enrichment upsert (`repository.upsert_corporate_action`,
  `repository.upsert_listing_status`, see `docs/architecture.md` for the
  exact field-by-field policy) rather than a blind `INSERT OR REPLACE`,
  which would have destroyed the first-seen `ingestion_timestamp`.
  TEST 14c exercises this through the real `ingestion -> repository ->
  PIT` path.
- **Two narrower gaps accepted as out of scope for this patch** (GPT
  Final Review #001, 2026-09-21): (1) `action_id` is derived from
  `action_type`/`effective_date`/`value` (see `ingestion.generate_action_id`),
  so a genuine provider correction to any of those produces a *new*
  `action_id` rather than revising the existing row -- the enrichment
  upsert only helps when the identity-defining fields are unchanged
  (e.g. a status update). A stable identity independent of these mutable
  facts is a Level 2/3 concern. (2) The enrichment upsert uses
  `COALESCE(new, old)`, which can turn a `NULL` into a value but cannot
  express "clear a previously-set fact back to unknown" -- not needed by
  any Level 1 scenario, not built here.

## Volume adjustment

- **`split_adjusted_volume` added (PATCH #001-C, Radu's correction,
  2026-09-21).** Previously `PITPriceBar` exposed only `raw_volume`
  (unadjusted) alongside `split_adjusted_close` (adjusted) -- a real gap
  surfaced by Spec #002's Discovery Engine (not fixed there, per Radu's
  own standing rule that a Data Foundation defect found downstream gets
  fixed in Data Foundation, not silently patched around in the consumer).
  Fixed: `split_adjusted_volume = raw_volume / split_factor`, derived
  on-the-fly in `pit/access.py` from the same `split_factor` already
  used for price, in the opposite direction (price is multiplied,
  volume is divided, since a split changes price and share count
  inversely). Purely additive -- no schema change, `raw_volume`
  untouched. See `docs/architecture.md` for the full note and TEST 16
  for the formula/continuity/round-trip verification.

- **`split_adjusted_open`/`high`/`low` added (PATCH #001-D, GPT Review
  #005 scaffold blocker A, 2026-09-26).** Surfaced while architecting
  Spec #005 (Backtester), before any #005 code was written -- same
  standing rule as PATCH #001-C: a Data Foundation gap found by a
  downstream design review is fixed here, never patched around
  downstream. `PITPriceBar` previously exposed
  `split_adjusted_close`/`split_adjusted_volume` but only `raw_open`/
  `raw_high`/`raw_low` -- insufficient for an executable
  `NEXT_BAR_OPEN` entry price or for MAE/MFE (both need adjusted
  high/low). Fixed: the same `split_factor` already used for
  `split_adjusted_close` is applied identically to
  `raw_open`/`raw_high`/`raw_low` -- one existing PIT-safe multiplier,
  three more fields, no new methodology, no schema change. TEST 17
  covers factor correctness (forward + reverse split), OHLC ordering
  preservation, boundary continuity, and PIT knowledge-time immunity.
  Total-return-adjusted OHLC was NOT added -- #005 v1 is scoped to
  price-return strategies only (total-return remains
  `EXPERIMENTAL_NOT_APPROVED_FOR_RESEARCH`), so no consumer needs it yet.

  **GPT Review verdict: PATCH #001-D -- ACCEPTED at `b1bb301`.** One
  non-blocker point registered rather than requested as a fix: TEST 17d
  exercises "split still in the future relative to `as_of`," not
  separately the narrower `effective_date < as_of < available_at` case
  (the event already happened but wasn't yet knowable). Not required as
  a follow-up patch, since `split_adjusted_open/high/low` run through
  the exact same as_of-scoped `factors` computation TEST 13a already
  validates for `split_adjusted_close` -- there is no separate/parallel
  PIT logic for the new fields that could diverge from it. Blocker A for
  Spec #005 (`NEXT_BAR_OPEN`, MAE, MFE, split-safe executable P&L) is
  closed; Spec #005 design work may proceed.

## Listing status

- `available_at` (added 2026-09-21, GPT Review #001 PATCH B) gates
  `get_listing_status_as_of()` the same way it gates corporate actions:
  `NULL` falls back to the pre-patch `effective_from`/`effective_to`-only
  behavior, tagged `knowledge_time_status=UNKNOWN`; when set, a status
  isn't visible before `available_at` even if its `effective_from` has
  already passed (TEST 15). Deliberately minimal -- no
  announcement/status lifecycle, no `ANNOUNCED`-equivalent intermediate
  phase, just the one field, to avoid building two different PIT models
  in the same foundation.
- **Known minimal-scope gap**: if a status transition's `available_at`
  hasn't been reached yet, `get_listing_status_as_of()` can return `None`
  (no applicable status) rather than carrying the previous status
  forward, even though the previous entry's own `effective_to` has by
  then technically already passed. Building "carry forward the last
  known status until the next one becomes knowable" is a real lifecycle
  feature, deliberately not built in this targeted patch -- flagged here
  rather than silently picked, per Radu's explicit instruction not to
  turn this into an open-ended redesign.
- A delisting that was publicly telegraphed earlier (e.g. a trading halt
  pending delisting, announced before the delisting itself is
  `effective`) isn't modeled as a distinct phase the way corporate
  actions' `ANNOUNCED` is -- `available_at` only answers "knowable or
  not," not "what intermediate state." Deferred to Level 2/3 if that
  granularity turns out to matter.
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
- **`qa_results.qa_pass` is not yet knowledge-time immutable** (flagged
  in GPT Review #001, 2026-09-21, documentation-only -- no code change
  made). `qa_results` has a `computed_at` column, but
  `pit.access.get_data()` only filters QA rows by `date <= as_of`; it
  does not check `computed_at` against `as_of` at all. QA
  (`qa.engine.run_qa_checks`) is described in `docs/architecture.md` as
  working over the security's full observed history, so re-running it
  after new data arrives can change `qa_pass` for an already-historical
  date (e.g. a later-arriving bar changes what looks like a
  `SUSPICIOUS_GAP` around an earlier date). A PIT-simulated
  `get_data(as_of=T)` query run before and after such a QA recompute
  could therefore see a different `qa_pass` for the same historical date
  -- the same class of look-ahead risk TEST 9 exists to catch, just not
  yet closed for the QA field specifically. Classified `PENDING`, not a
  Level 1 blocker (no mandatory test currently exercises this path), but
  it **must be resolved before Discovery Engine or any other downstream
  research module is approved to consume `qa_pass` for research-grade
  use** -- the same `available_at`/`knowledge_time_status` pattern used
  for corporate actions and listing status is the natural fix, not
  designed or built here.

## Test coverage

- **TEST 8 (provider consistency) is `PENDING_LEVEL_2_DATA`**, approved
  by Radu (2026-09-20): Level 1 runs a single provider, so there is
  nothing to cross-compare. Not a false PASS.
- **TESTs 13-15 (knowledge-time policy, cancelled-action adjustment,
  listing-status knowledge-time)** are additional coverage from the
  2026-09-21 GPT Review #001 patch round, not part of the original
  Spec #001 SS23 numbered list -- see `docs/test_report.md` and
  `tests/test_13_knowledge_time_policy.py` /
  `tests/test_14_cancelled_action_adjustment.py` /
  `tests/test_15_listing_status_knowledge_time.py`.
- **TEST 16 (split-adjusted volume)** is additional coverage from
  PATCH #001-C (2026-09-21) -- see `tests/test_16_split_adjusted_volume.py`.
