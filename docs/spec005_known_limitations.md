# Spec #005 Batch 3 -- Known Limitations

Scope: `src/backtest/exits/` -- the STOP_MANAGED_INVALIDATION exit engine
implementing `docs/spec005_exit_amendment_v1.0.md` (ACCEPTED).

## Scope boundary: no base session/universe engine exists yet

Batch 1/2 of Spec #005 (`backtest.models.entities`, `backtest.data.*`,
`backtest.zones.*`) are explicitly CONTRACTS AND PIT ACCESS ONLY -- no
multi-security session loop, entry-signal matching, or TIME_EXIT/
SIGNAL_INVALIDATION execution engine exists anywhere in this codebase for
ANY exit family, old or new. Batch 3 does not add one either: it
implements exactly what the accepted amendment itself fully specifies --
the STOP_MANAGED_INVALIDATION position's own per-position mechanics
(`backtest/exits/protection.py`, `session.py`, `costs.py`, `taxonomy.py`,
`mae_mfe.py`, `entities.py`), taking an already-determined entry fill and
already-fetched PIT bars/corporate actions as input, all reached only
through `backtest.data.pit_access.BoundedPITAccess` (the one sanctioned
gateway, Spec #005 SS3/SS6).

Steps 1/2/4/6 of the amendment's own session order (scheduled exits,
entry matching, TIME_EXIT/CAP, new entries) are explicitly "unchanged"
per the amendment and belong to a base multi-security engine that has not
been built yet for any family. Wiring this package's Pas 0 (`backtest.
exits.session.reconcile_split_for_open_position`) and Pas 3'
(`advance_intrabar`) functions into a real session loop -- calling them in
the right order relative to those still-unbuilt steps 1/2/4/6, across a
real universe of securities and sessions -- is future work outside this
amendment's own scope, and outside what Batch 3 delivers.

## Declared limitations (amendment section 14, carried forward as-is)

- Fill at open for a level already breached, and `slippage=0` for the
  target order, are conventions of the Daily model -- not guarantees of
  real execution (`StopManagedExecutionSemanticsProfile`, section 7).
- MAE/MFE on an intraday-exit day is partial, not complete, by
  construction -- daily OHLC does not permit exact intraday ordering
  (`backtest.exits.mae_mfe`, section 12).
- `MEDIAN_NET_RETURN_TO_EXIT_OR_STAGE_END` reduces, but does not
  eliminate, the risk of favorable-sample selection via censoring
  (`backtest.exits.taxonomy`, section 11).
- V1 does not cover capital reallocation between positions (deferred to
  a future portfolio stage, confirmed separately).

## Batch-3-specific implementation notes

- ATR reuses `discovery.features.volatility.compute()` verbatim, on the
  SAME mixed raw-high/low + split-adjusted-close basis `discovery.engine.
  _price_series_to_df()` already builds it from (Spec #002's own existing
  convention) -- no new indicator, no independently "more correct" fully
  split-adjusted variant. `backtest/exits/protection.py` replicates that
  3-line DataFrame construction locally (with a citation comment) rather
  than importing a private, underscore-prefixed function across a package
  boundary.
- The explicit temporal-access-at-open evidence (`same_day_evidence`/
  `known_before_open_same_day`) is a NEW input this batch introduces --
  `available_at` in #001's schema is date-only (compared as a plain
  string against `as_of`, itself a bare date) and cannot by itself supply
  "beyond the date" evidence. A caller must supply this explicitly
  (e.g. a verified pre-market disclosure timestamp tracked outside #001's
  current schema); the default, absent such evidence, is NOT authorized.
- `_is_action_known_for_adjustment()` (`data_foundation.pit.access`) is
  imported directly despite its leading underscore -- the accepted
  amendment names this exact function as the gate to reuse "nemodificat"
  (section 6). It performs no PIT read itself (a pure classification
  over an already-fetched `CorporateAction`), so this does not bypass the
  one-PIT-gateway rule the leading underscore would otherwise suggest
  warrants more caution about.
- Section 9's cost formulas take a tranche's own already-determined exit
  fill (`F_x`) as an input, not an output: the base spec's own SS13
  slippage-application formula for a stop/invalidation fill
  (`nivel_fill·(1−d·s_x)`) is referenced by the amendment but its full
  text was not available to derive independently here, so `backtest.
  exits.costs` computes the RETURN from a given fill rather than also
  deriving the fill's own slippage adjustment -- the caller (the
  not-yet-built base engine) is responsible for supplying an already
  slippage-adjusted `F_x` for stop/invalidation tranches, and the raw
  target level for a target tranche (no adverse slippage, per section 9).
