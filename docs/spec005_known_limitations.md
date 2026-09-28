# Spec #005 Batch 3 -- Known Limitations

Scope: `src/backtest/exits/` -- the STOP_MANAGED_INVALIDATION exit engine
implementing `docs/spec005_exit_amendment_v1.0.md` (ACCEPTED).

**Status: Batch 3 underwent two correction rounds (GPT review round 2 and
round 3, both CHANGES REQUIRED) after the initial delivery (`cb9d67f`).
The round-2 fixes were themselves found incomplete in round 3 on four
specific points (Pas 0 false-incomplete marking, ATR non-uniform
adjustments, plan-gate wiring, MAE/MFE zero baseline); those four are
fixed in a further follow-up commit. This document describes what each
fix does; it is not a claim that the review considers Batch 3 accepted --
as of this writing Batch 3 remains unaccepted, with baseline `3cdc532`
still the last accepted state, and the outstanding obligations below are
unchanged.**

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
   validate_stop_managed_plan_requirements()` cross-checked that a plan
   whose cohort includes STOP_MANAGED_INVALIDATION variants sets both.
   (Round 3 found this wiring itself insufficient -- see below, finding
   #3 -- and it was replaced, not merely extended.)

## GPT review round 3 corrections (applied in a further follow-up commit)

Round 3 found the round-2 fixes for temporal-rule usage (#1), tranche
own-basis freezing (#5), and numeric validity (#6) sufficient -- those are
NOT reopened here. It found four remaining problems, all now fixed:

1. **Pas 0 still marked positions incomplete for splits that were never
   its concern.** `reconcile_split_for_open_position()`'s lateness check
   (`late = any(a.effective_date < session_date for a in
   newly_authorized)`) treated any not-yet-processed split as relevant to
   the position's reconciliation, including one with
   `effective_date <= position.entry_date` -- a split that, by
   `compute_factors()`'s own `effective_date > d` condition, could never
   have needed rescaling at entry in the first place, since the position's
   opening basis already reflects it. Such actions are now skipped
   entirely, before authorization checking, before being counted toward
   lateness, and before being added to `processed_split_action_ids` --
   this includes an action effective the day before entry and one
   effective exactly on the entry day itself, both provably already
   correct at entry. Regressions: `test_split_effective_before_entry_is_
   never_pas0s_concern`, `test_split_effective_exactly_on_entry_day_is_
   never_pas0s_concern`.
2. **ATR reconciliation could not detect a non-uniform, retroactively
   disclosed split.** `check_new_splits_authorized_at_open()` used to skip
   any action with `effective_date <= signal_date`, which excluded exactly
   the actions that matter when disclosure happens between signal and
   entry. `compute_atr_basis_reconciliation()`'s own ratio mechanism
   (`atr_s * (close_asof_entry / close_asof_signal)`) was independently
   incapable of catching this class of split regardless of that skip,
   because a split effective at or before the signal-date bar never
   rescales that bar itself, so the ratio is always 1.0 even when the ATR
   window's earlier bars need reconciling. Both are replaced: the
   authorization check now covers every split known as of `entry_date`
   with no pre-filter, and the ATR window is now fetched as a single
   `get_price_series_as_of(entry_date)` query -- using entry_date's own
   knowledge to correctly re-express the whole historical window, which
   the amendment's own text sanctions ("seria istorică... e exprimată pe
   baza prețului de intrare folosind numai ajustările efective și
   cunoscute la momentul deschiderii"). This removes the need for a
   separate uniformity precondition: `compute_factors()`'s per-date,
   per-action-type computation is structurally uniform already.
   Regressions: `test_split_within_window_disclosed_between_signal_and_
   entry_end_to_end`, `test_split_within_window_disclosed_late_without_
   evidence_is_rejected`.
3. **Plan validation remained optional and disconnected from real data.**
   The round-2 `validate_stop_managed_plan_requirements(plan, bool)` took
   a caller-supplied boolean instead of resolving the cohort from a real
   registry, accepted any non-`None` profile id without checking it
   against an actual profile object, and returned success immediately for
   an old-family cohort even when the new metric was set. It is replaced
   by `accept_research_plan(plan, registry, stop_managed_profile=None)`,
   the package's first real acceptance gate: it resolves every
   `hypothesis_cohort_ids` entry via `HypothesisRegistry.get()`/
   `variants_for()` to determine whether the cohort actually includes a
   STOP_MANAGED_INVALIDATION variant, rejects an unresolvable cohort id
   outright, requires and verifies a real, independently-verified
   `StopManagedExecutionSemanticsProfile` object (not a bare id string)
   whenever the cohort needs one, and now also rejects an old-family-only
   cohort that sets the new ranking metric -- symmetric enforcement,
   neither side of the family split gets a free choice.
   `tests/spec005/test_32_stop_managed_plan_integration.py` was rewritten
   to build real `StrategyHypothesis`/`StrategyVariant` objects through a
   `HypothesisRegistry` and exercise this gate directly (11 tests), rather
   than calling a validator helper in isolation.
4. **MAE/MFE omitted the known-zero excursion at entry.** Excursion
   tracking started from an empty list and only added observations from
   supplied bars and the exit fill -- so an empty-bars tranche with entry
   100 / exit 110 wrongly reported MAE == MFE == +10%, when the price
   never actually traded below entry and the correct MAE is 0%.
   `compute_tranche_mae_mfe()` now seeds the excursion list with the
   entry's own always-known 0.0 excursion unconditionally. Regressions:
   `test_empty_bars_still_includes_the_known_zero_excursion_at_entry`
   (MAE=0%, MFE=+10%), `test_empty_bars_pure_loss_never_reports_a_
   positive_mfe` (MAE=-10%, MFE=0%).
