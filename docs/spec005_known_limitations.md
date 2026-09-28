# Spec #005 Batch 3 -- Known Limitations

Scope: `src/backtest/exits/` -- the STOP_MANAGED_INVALIDATION exit engine
implementing `docs/spec005_exit_amendment_v1.0.md` (ACCEPTED).

**Status: Batch 3 underwent a correction round (GPT review round 2,
CHANGES REQUIRED) after the initial delivery (`cb9d67f`). All 7 findings
from that round are fixed in the follow-up commit; this document reflects
the corrected state and, per that review's explicit instruction, tracks
what remains OUTSTANDING as concrete obligations mapped to the next
delivery -- not as a closed scope boundary.**

## What Batch 3 delivers vs. what remains outstanding

Batch 1/2 of Spec #005 (`backtest.models.entities`, `backtest.data.*`,
`backtest.zones.*`) are CONTRACTS AND PIT ACCESS ONLY -- no multi-security
session loop, entry-signal matching, or TIME_EXIT/SIGNAL_INVALIDATION
execution engine exists anywhere in this codebase for ANY exit family, old
or new. Batch 3 implements the STOP_MANAGED_INVALIDATION position's own
per-position mechanics in full (`backtest/exits/protection.py`,
`session.py`, `costs.py`, `taxonomy.py`, `mae_mfe.py`, `entities.py`,
`plan_integration.py`), taking an already-determined entry fill and
already-fetched PIT bars/corporate actions as input, all reached only
through `backtest.data.pit_access.BoundedPITAccess` (the one sanctioned
gateway, Spec #005 SS3/SS6). `ResearchPlan`/`SelectionRule` identity and
validation ARE wired to this family's requirements (section 7/11) --
GPT review round 2 finding #7 confirmed this was achievable now, since
that infrastructure already exists, and it is no longer disconnected.

**Genuinely outstanding, mapped to the next delivery (not "out of
scope"):**

1. **The multi-security session/universe loop itself** -- steps 1/2/4/6
   of the amendment's own session order (scheduled exits, entry matching,
   TIME_EXIT/CAP, new entries) do not exist yet for ANY exit family.
   Wiring this package's Pas 0 (`reconcile_split_for_open_position`) and
   Pas 3' (`advance_intrabar`) functions into a real loop -- in the right
   order relative to those still-unbuilt steps, across a real universe of
   securities and sessions -- requires that base engine to exist first.
   This is the next delivery's primary content.
2. **Full session-order demonstration through an integrated path** --
   until (1) exists, there is no end-to-end test exercising a complete
   session (Pas 0 through Pas 6) against a real multi-day, multi-security
   fixture. The 90-plus unit/integration-level regressions in
   `tests/spec005/test_21` through `test_32` cover each mechanism in
   isolation; they are not a substitute for that integrated demonstration,
   and the next delivery must add it once (1) lands.
3. **The base spec's own SS13 slippage-application formula for a stop/
   invalidation fill** (`nivel_fill·(1−d·s_x)`) -- referenced by the
   amendment but its full text was not available to derive independently
   here. `backtest.exits.costs` computes the RETURN from an
   already-determined fill; it does not derive the fill's own slippage
   adjustment. The next delivery (or a request for the base document's
   full SS13 text) must close this before `costs.py` can be exercised
   end-to-end against `CostAssumptions.slippage_entry_bps`/
   `slippage_exit_bps` rather than a caller-supplied fill.

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

## GPT review round 2 corrections (applied in the follow-up commit)

1. **Temporal-access rule used the wrong date.** `is_authorized_at_open()`
   now applies to the action's `knowledge_date()` (its `available_at`,
   falling back to `effective_date` only when no validated knowledge-time
   signal exists) -- never to `effective_date` directly. A split announced
   in advance and effective same-day needs no evidence; a split effective
   long ago but only disclosed today needs exactly the same same-day
   scrutiny a same-day-effective split would. Applied identically at
   entry (`check_new_splits_authorized_at_open`) and at Pas 0
   (`reconcile_split_for_open_position`).
2. **Late reconciliation was declared clean.** `reconcile_split_for_open_
   position()` now marks `split_reconciliation_incomplete=True`
   permanently whenever a split's `effective_date` is strictly before the
   session that actually reconciles it -- intervening sessions were
   necessarily simulated on the stale basis, regardless of whether that
   was itself PIT-correct at the time. The ratio catch-up still corrects
   the position going forward; the flag records that the path to get
   there is not fully demonstrated.
3. **ATR mixed raw and split-adjusted fields.** `backtest/exits/
   protection.py` now computes ATR from `split_adjusted_high`/
   `split_adjusted_low`/`split_adjusted_close` together (all under the
   same as-of query, PATCH #001-D fields) -- an internally coherent basis,
   never #002's own `raw_high`/`raw_low` + `split_adjusted_close` mix
   (which would inject an artificial true-range spike at any split inside
   the window). #002's own `discovery.engine._price_series_to_df()` keeps
   that mixed convention unchanged -- fixing it is out of scope for this
   batch; noted here only as an observation.
4. **Pas 0's applied factor could include an unauthorized same-day
   action.** `reconcile_split_for_open_position()` now computes the
   factor via `data_foundation.model.adjustment_engine.compute_factors()`
   restricted to exactly the actions this position has itself authorized
   (already-processed + newly-authorized this call) -- never delegated to
   `get_price_series_as_of()`'s own full known-action set, which has no
   notion of this position's own same-day-authorization distinction and
   could silently fold in a different, unauthorized same-day split.
5. **A later split could corrupt an already-closed tranche's return.**
   `Tranche` now carries its own `entry_fill_price_reference`, snapshotted
   from `position.entry_fill_price` at the exact moment each tranche is
   created. `backtest.exits.costs.net_return_for_tranche()` always reads
   F_e from this field, never from a position's current (possibly
   later-rescaled) `entry_fill_price`.
6. **Numeric validation and MAE/MFE coverage were incomplete.**
   `update_trailing_stop_at_close()` now flags `trailing_path_incomplete`
   for any non-finite or non-positive ATR (not just `None`).
   `compute_initial_protection()` now checks finiteness of every computed
   level, not just its economic ordering. `compute_tranche_mae_mfe()` now
   always includes the exit fill as an observation and reports
   `PARTIAL_EXIT_DAY_EXCLUDED` whenever the exit day's own bar is absent
   from the input or any other bar is missing a high/low -- coverage can
   no longer read `FULL` merely because data was missing.
7. **The delivery didn't close the contractual integration.**
   `ResearchPlan` now carries an optional, family-conditioned
   `stop_managed_execution_semantics_profile_id` field (fingerprinted
   only when set -- byte-identical for a plan that doesn't use it).
   `SelectionRule.ranking_metric` now also accepts
   `RANKING_METRIC_STOP_MANAGED_V1`. `backtest.exits.plan_integration.
   validate_stop_managed_plan_requirements()` cross-checks that a plan
   whose cohort includes STOP_MANAGED_INVALIDATION variants sets both.
