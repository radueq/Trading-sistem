# Spec #002 -- Known Limitations

Explicit per Spec #002 SS47C (mirrors Spec #001 SS27E: don't hide
limitations to declare the module "done"). None of these block Level 1
acceptance; they are the honest boundaries of what this build can claim.

## Hard gates inherited from Spec #001 (Spec #002 SS8)

**No result from this module may be labelled research-grade until both
of these are resolved.** Not silently fixed here -- Spec #002 explicitly
forbids that.

- **QA knowledge-time**: `qa_results.qa_pass` is not yet guaranteed
  knowledge-time immutable (Spec #001's own Known Limitations, GPT
  Review #001, 2026-09-21). Feature Engine at Level 1 does **not**
  consume `qa_pass` at all -- no filtering, no gating, nothing reads
  `pit.access.get_data(...).qa_pass_by_date` anywhere in
  `src/discovery/`. This is the safest posture given the acknowledged
  gap: not building on top of a foundation that isn't research-grade
  yet, rather than integrating QA now and inheriting its immutability
  risk silently.
- **Listing status carry-forward**: `pit.access.get_listing_status_as_of()`
  can return `None` (no applicable status) rather than carrying the
  previous status forward when a transition's `available_at` hasn't
  been reached yet (Spec #001's own Known Limitations). Eligibility at
  Level 1 does **not** filter on listing status at all (see below) --
  deliberately, to avoid building a filtering rule on an acknowledged-
  unreliable field.

## Eligibility

- **`EXCHANGE_ELIGIBILITY` cannot be evaluated at Level 1.**
  `pit.access` (Spec #001) doesn't expose `security_master.primary_exchange`
  anywhere in its public interface -- `run_discovery()` always passes
  `primary_exchange=None` to `evaluate_eligibility()`. Rather than read
  `data_foundation.model.repository` directly (forbidden, SS7) or
  unilaterally extend Spec #001's PIT gateway, the rule is simply
  disabled by default (`allowed_exchanges: null` in `eligibility.yaml`).
  **This is exactly the kind of missing interface Radu asked to be
  flagged rather than silently worked around** -- extending
  `pit.access.get_data()` to expose `primary_exchange` (a static,
  non-time-varying field, so no PIT-correctness concern) is a small,
  well-scoped Spec #001 addition if/when exchange filtering is needed.
- **No listing-status-based eligibility rule** (e.g. excluding delisted
  securities) -- deliberately, tied to the listing-status carry-forward
  gate above. Spec #002's own example eligibility dimensions (price,
  history, liquidity, exchange, market cap) don't include it either.
- **`market_cap_floor` is always `PENDING_DATA`.** No PIT market cap
  field exists anywhere in the Spec #001 schema; never fabricated.
  Eligibility proceeds on the other dimensions regardless of
  `eligibility.yaml`'s `market_cap_floor` value.

## Feature computation

- **Volume is not split-adjusted.** `data_foundation.pit.access.PITPriceBar`
  exposes only `raw_volume` -- there is no split-adjusted volume field
  in Spec #001's PIT output. A security that underwent a split will show
  a level shift in raw volume around the split date (share count
  changes), which can produce a spurious `RVOL_20`/`volume_percentile`
  reading near that boundary. Not fabricated/adjusted here; flagged as
  a Level 1 gap. A proper fix belongs in Spec #001 (a split-adjusted
  volume field on `PITPriceBar`), not invented unilaterally in this
  module.
- **`relative_strength`'s historical persistence/transition is not
  computed.** `states/mapper.compute_persistence()` and the
  `TransitionVector` cover only the four TIME_SERIES-driven lanes
  (trend, volatility, volume, momentum). `relative_strength`'s driver
  (`rs_percentile_cross_sectional`) is CROSS_SECTIONAL and would need
  the whole eligible universe recomputed at every historical date to
  measure properly -- an expensive full-universe-across-history
  computation, out of scope for Level 1. `relative_strength`'s current
  `as_of` state IS computed correctly (via the cross-sectional pass);
  only its historical run-length/delta are the gap.
- **`ATR_14` / `BB_width_20` are fixed literal names**, independent of
  the configured `atr_window`/`bb_window` value (matching Spec #002's
  own naming convention of one named feature per volatility measure,
  not a list like the return windows). Reconfiguring the window changes
  the *values*, not the output key -- documented in `features/volatility.py`
  and exercised deliberately in TEST 7 (a small window, for a
  hand-verifiable series, still labeled `ATR_14`).
- **`RVOL_20` and `volume_ratio_20` are literal aliases** of the same
  ratio (`volume / ADV_20`). Spec #002 SS12 lists both names in its
  minimum feature list without distinguishing them; inventing an
  arbitrary difference the spec doesn't specify would be worse than
  being explicit they're the same computation under two names.
- **Lane driver choices for `trend` (`return_63d_percentile`) and
  `momentum` (`ROC_10_percentile`)** are this Level 1 build's own design
  choice -- Spec #002 names a driver for volatility/volume/relative_strength
  implicitly (their own `_percentile` features) but not for trend/momentum.
  Externally configurable (`config/states.yaml`'s `lane_drivers`), not
  claimed to be the only valid choice.
- **`slope_smaN` is a percentage-based slope**
  (`(sma[t]/sma[t-w] - 1) / w`), not an absolute one. On a security with
  a constant *absolute* daily price change, this slope shrinks over
  time as the price base grows -- a real, correct property of a
  percentage-based measure, not a bug (see TEST 4's comments).

## Universe / performance

- **No automatic universe discovery.** `run_discovery()` takes an
  explicit `security_ids` list; nothing in this module decides *which*
  securities exist to run Discovery over -- that's a caller/orchestration
  concern (mirroring Spec #001's `model/ingestion.py` not doing identity
  resolution automatically either).
- **Cross-sectional computations require the whole batch at once.**
  `rs_percentile_cross_sectional` and `state_frequency` are computed in
  a single pass over all securities passed to one `run_discovery()` call
  -- there's no incremental/streaming update if a new security is added
  later; the whole batch is recomputed. Fine at Level 1 synthetic scale
  (~0.03s/security, see `docs/spec002_volume_report.md`); a real
  concern only at much larger universe sizes, deferred per Spec #002
  SS37 ("informational in Level 1, not an acceptance blocker").
- **No live yfinance data** -- same sandbox network restriction as Spec
  #001 (see its Known Limitations). All Spec #002 tests run against
  fully synthetic fixtures (`tests/spec002/fixtures/synthetic_universe.py`),
  explicitly labeled TEST_CONFIG, not claimed to resemble real market
  behavior.

## Test coverage

- All 21 required tests (the 20 named in Spec #002 SS38 plus a
  structural no-LLM-imports check, SS41) pass -- see
  `docs/spec002_test_report.md`. None are `PENDING`; Level 1's
  synthetic universe is sufficient to exercise every required property.
