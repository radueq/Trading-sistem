# Spec #005 Batch 3 -- Known Limitations

Scope: `src/backtest/exits/` -- the STOP_MANAGED_INVALIDATION exit engine
implementing `docs/spec005_exit_amendment_v1.0.md` (ACCEPTED).

**Status: the general accepted baseline remains `3cdc532` (Spec #005
Batch 2, patch round 5). Batch 3 underwent three correction rounds (GPT
review rounds 2 and 3, plus a narrow round-3-follow-up fixing one
regression -- the missing signal-session-bar check, specifically accepted
in `0ed78ca` -- that acceptance covers ONLY that one regression, not
`0ed78ca` as a whole, and not Batch 3's overall acceptance). A further
delivery -- "Session Engine & Integration" -- then addressed the four
obligations that remained after that follow-up: the multi-security session
loop, the mandatory plan-acceptance gate, exit-side slippage, and an
integrated Pas 0-6 test. That delivery's own first review round (`76c0877`)
found six further problems (entry slippage never applied,
missing/incomplete session data silently skipped, a stale final mark,
`stage_end_date` not actually bounding the loop, entry signals not tied to
the plan's own resolved variant, and the integrated test not exercising
the real `run_stage()`/`BoundedPITAccess` path) -- all six fixed in a
follow-up (`4560f93`). That follow-up's OWN review round then found three
more integration-level problems (the executed stage not tied to the
plan's own zone/calendar, `session_dates` not validated for strict
order/uniqueness, and variant-keyed position bookkeeping missing --
described in their own section below, also now fixed). This document
describes what each delivery does; it is not itself a claim of
acceptance -- Batch 3 as a whole remains unaccepted, and whether the
fixes below close it is for review to say.**

## What Batch 3 delivers vs. what remains outstanding

Batch 1/2 of Spec #005 (`backtest.models.entities`, `backtest.data.*`,
`backtest.zones.*`) are CONTRACTS AND PIT ACCESS ONLY. Batch 3 implements
the STOP_MANAGED_INVALIDATION position's own per-position mechanics in
full (`backtest/exits/protection.py`, `session.py`, `costs.py`,
`taxonomy.py`, `mae_mfe.py`, `entities.py`, `plan_integration.py`), and
the Session Engine & Integration delivery (`backtest/exits/engine.py`)
adds the multi-security session LOOP around those mechanics -- see its
own section below for exactly what that loop does and does not cover.
All PIT access, in every layer, is reached only through
`backtest.data.pit_access.BoundedPITAccess` (the one sanctioned gateway,
Spec #005 SS3/SS6). `ResearchPlan`/`SelectionRule` identity and validation
ARE wired to this family's requirements (section 7/11) -- GPT review
round 2 finding #7 confirmed this was achievable now, since that
infrastructure already exists -- and, as of the Session Engine &
Integration delivery, `accept_research_plan()` sits at a real, mandatory
run entry point (`engine.run_stage()`), not merely a test-reachable
function.

**Genuinely outstanding, mapped to the next delivery (not "out of
scope"):**

1. **Discovery-based entry-signal matching does not exist anywhere in
   this codebase, for any exit family.** `SessionEngine` takes
   `entry_signals` as an explicit, caller-supplied mapping keyed by
   `(security_id, signal_date)` -- turning Discovery lane STATES into an
   actual match against a variant's `EntryDefinition` is a separate
   integration surface nothing in Batch 1-3, or elsewhere in this
   codebase, builds. The next delivery that wants a fully autonomous run
   (no caller-supplied signals) must build this first.
2. **Evaluating an `InvalidationCondition` against real Discovery lane
   output does not exist anywhere in this codebase either** (confirmed by
   grep: no function anywhere consumes `InvalidationCondition` to produce
   VALID_HOLD/INVALIDATED/UNKNOWN). `SessionEngine` takes
   `invalidation_observer` as an explicit, caller-supplied callable for
   exactly this reason. Building the real evaluator is a second, separate
   integration surface from (1) -- both are the natural next step once a
   caller wants the engine driven by real Discovery output rather than a
   test/research-supplied signal source.
3. **TIME_EXIT/SIGNAL_INVALIDATION have no execution engine of their
   own.** `SessionEngine` only ever constructs/advances
   `StopManagedPosition` objects -- the two older exit families remain
   pure validation-time contracts (Batch 1/2), with no per-position
   mechanics or session-loop integration of their own. A `ResearchPlan`
   whose cohort mixes old-family and STOP_MANAGED_INVALIDATION variants
   can be ACCEPTED by `accept_research_plan()` (it only inspects the
   cohort's ranking-metric/profile requirements), but `SessionEngine`
   itself has nothing to run for that cohort's old-family variants.

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

Round 3 review of this round's own delta (`24cd4f0`) found one further
regression, since fixed:

## Session Engine & Integration delivery (`backtest/exits/engine.py`)

Addresses the four obligations named after the round-3-follow-up
(`0ed78ca`) was accepted:

1. **Multi-security session loop.** `SessionEngine` runs the amendment's
   Pas 0/1/2/3'/5/6 order (section 5) over a caller-supplied
   `session_dates` sequence and an implicit universe (every security_id
   appearing in `entry_signals`), composing the already-accepted
   per-position functions in `protection.py`/`session.py` -- Pas 0
   (`reconcile_split_for_open_position`, run only for positions opened in
   a strictly prior session, never one opened today), Pas 1
   (`execute_scheduled_invalidation`, for a pending invalidation detected
   at a prior close, run before Pas 2 per section 5), Pas 2
   (`open_stop_managed_position`, for a signal recorded at the PREVIOUS
   session's close), Pas 3' (`advance_intrabar`), Pas 5
   (`check_trend_invalidation` plus the close(t) `S_next` recompute via
   `update_trailing_stop_at_close`). Pas 6 needs no separate code: a
   signal recorded at today's close is simply looked up again as Pas 2's
   `signal_date` on the next iteration. Entry-time rejections (section 2)
   are recorded as `EntryDisposition` objects, never silently dropped;
   `SUPPRESSED_STAGE_BOUNDARY` fires for a signal on the stage's own last
   session with no price ever read for it, matching section 2 item 1
   exactly. See the outstanding-obligations list above for what this loop
   deliberately takes as an external input rather than deriving itself
   (entry-signal matching, invalidation-lane evaluation).
2. **Mandatory plan validation before running.** `engine.run_stage()` is
   the one real "run a stage" entry point: it calls
   `plan_integration.accept_research_plan()` FIRST and raises
   `PlanNotAcceptedError` without ever constructing a `SessionEngine` if
   the plan is rejected. `SessionEngine` itself stays directly callable
   (for tests exercising the loop in isolation, the same way `session.py`
   itself is unit-tested), but the only path that also carries a
   `ResearchPlan`/`HypothesisRegistry` runs the gate unconditionally.
3. **Exit-side slippage (section 9 / "amendament §13").** The amendment's
   own section 9 already restates the base spec's SS13 formula in full,
   including the fill formula this delivery was missing:
   `F_x = nivel_fill` for the partial-profit tranche (no adverse slippage,
   section 4), `F_x = nivel_fill·(1−d·s_x)` for any tranche closed via
   stop or trend invalidation. `costs.apply_exit_slippage()` implements
   this exactly (`s_x` = `CostAssumptions.slippage_exit_bps` via the new
   `slippage_rate_from_bps()` helper); `costs.
   net_return_for_tranche_with_slippage()` composes it with the existing,
   untouched `tranche_net_return()` formula -- fully additive, so every
   existing caller of `net_return_for_tranche()` (which still takes an
   already-decided `F_x`, by the module's own original design) is
   unaffected. `Tranche.exit_fill_price` itself is never overwritten with
   the slipped value -- MAE/MFE deliberately tracks the raw market level
   the price actually reached, never this engine's own execution
   slippage.
4. **Stage-end classification and aggregate cost evaluation.**
   `engine.evaluate_stage_results()` runs `taxonomy.classify_position()`
   plus section 9's aggregation (`compute_w`/`aggregate_position_return`,
   `net_return_for_tranche_with_slippage()` for a closed tranche,
   `open_remainder_net_return()` for a still-open/censored remainder)
   per position, returning `None` wherever the facet is not EVALUABLE --
   section 10's explicit rule, never a number for an UNEVALUABLE or
   EXIT_FAILED position.
   `tests/spec005/test_34_stop_managed_integrated_pas0_to_6.py` is the
   integrated demonstration: two securities across one 6-session stage --
   one entered with partial profit, reconciled through a mid-life 2-for-1
   split at Pas 0, then stopped out (CLOSED, EVALUABLE); the other,
   Control variant, with a trend invalidation detected at the STAGE'S OWN
   LAST close, whose scheduled fill falls in the next stage and is never
   read (CENSORED_AT_HORIZON, EVALUABLE, `pending_exit_note` recorded --
   section 10's central regression #9 case). Where a value depends on
   ATR-driven trailing-stop drift (already covered numerically by
   `test_21`-`test_25`), the test cross-checks `evaluate_stage_results()`'s
   number against the same cost primitives applied directly to the
   position's own actually-recorded tranche fields, rather than
   re-deriving Wilder's ATR by hand a second time; the still-open
   remainder's return (no ATR dependence at all) is hand-verified
   directly. `tests/spec005/test_33_stop_managed_session_engine.py` covers
   `SUPPRESSED_STAGE_BOUNDARY` and the `run_stage()` gate in isolation.

5. **The single-query ATR rewrite (finding #2 above) silently accepted a
   missing signal-session bar.** `compute_atr_basis_reconciliation()`
   filtered `bars_as_of_entry` to `date <= signal_date` and checked only
   the resulting count -- if no bar was dated exactly `signal_date` (a
   data gap, or a `signal_date` misaligned with this security's own
   trading calendar), it silently computed ATR as of whatever session
   preceded it and reported that as ATR_14(s). An explicit
   `_find_bar(bars_as_of_entry, signal_date)` check is restored before
   the window is built -- missing signal bar rejects via
   `SIGNAL_BAR_MISSING`, propagated by `open_stop_managed_position()`
   into `ENTRY_NO_VALID_STOP_BASIS` like every other basis-rejection
   reason. Regressions (`test_22`):
   `test_missing_signal_session_bar_is_rejected_even_with_sufficient_
   history`, `test_missing_signal_session_bar_prevents_the_position_
   from_opening` (the latter exercised through `open_stop_managed_
   position()` itself, confirming the position is never created).

## Session Engine & Integration review, round 1 corrections

Review of `76c0877` found the loop, the exit-side slippage wiring, and the
mandatory-gate SHAPE all real progress, but identified six further
problems -- all fixed here:

1. **Entry slippage was never applied.** `_evaluate_pending_entry()`
   (renamed from `_execute_pending_entry()`) used to set
   `entry_fill_price = bar.split_adjusted_open` directly -- two plans with
   different `slippage_entry_bps` produced the identical entry fill,
   protection levels, and aggregate return. The amendment's own section 9
   restates F_x's sub-formula explicitly but describes F_e only as
   "fill-ul de intrare" with no symbolic entry-side sub-formula --
   `costs.apply_entry_slippage()` is the DERIVED counterpart (documented,
   not quoted) of `apply_exit_slippage()`'s own construction: `F_e =
   nivel_fill*(1+d*s_e)`, always adverse to the trader (a higher buy price
   for LONG, a lower sell-to-open price for SHORT). Applied BEFORE
   `open_stop_managed_position()` is ever called, so `S_initial`/target/
   the aggregate return all reflect it. Regressions (`test_33`):
   `test_entry_slippage_long_shifts_fill_protection_and_aggregate_return`,
   `test_entry_slippage_short_shifts_fill_protection_and_aggregate_return`
   -- both check the fill, the resulting protective level, AND the
   aggregate net_return.
2. **A missing or incomplete session bar was silently skipped.** Pas 3'
   used a bare `continue` when a bar was absent or had a `None` open/high/
   low, and the close(t) trailing-stop update was simply never reached
   either (its own guard already required `bar is not None`) -- neither
   path recorded that a REAL stop/target breach could have gone
   undetected that session. `session.mark_session_data_unavailable()`
   sets `trailing_path_incomplete=True` PERMANENTLY for exactly this case
   -- reusing that existing reason (not inventing a new one) because the
   underlying concept is identical to an unusable ATR (section 10): the
   stop's own forward path is not fully demonstrated, whatever the root
   cause. A later session's data recovering does not repair it. Two
   separate regressions (`test_33`):
   `test_missing_bar_marks_trailing_path_incomplete_permanently` (the
   session has no bar at all) and
   `test_incomplete_ohlc_marks_trailing_path_incomplete_permanently` (the
   bar exists but `low` is `None`) -- both prove the flag survives later
   sessions' clean data.
3. **The final mark could come from a stale, earlier session.**
   `_last_close` only updated when a close was actually observed, so a
   missing bar on the stage's OWN last session silently left the PRIOR
   session's close in place, indistinguishable from a genuine final mark.
   The engine now tracks `(close_price, session_date)` per security and
   only reports a `final_closes` value when that date equals the last
   session actually run; otherwise `None` -- correctly propagating into
   `classify_position()`'s `final_mark_available=False` ->
   `CENSORED_MARK_UNAVAILABLE`, never silently substituted.
   `evaluate_stage_results()` additionally raises if it is ever asked to
   compute a still-open remainder's return with no mark in `final_closes`
   -- a caller/outcome mismatch, not a value to paper over. Regression
   (`test_33`): `test_final_close_from_a_stale_earlier_session_is_never_
   used_as_the_mark`.
4. **`stage_end_date` did not actually bound the loop.** The engine
   iterated every date in `session_dates` regardless of a narrower
   declared `stage_end_date`, and (separately) never checked its own
   `stage_end_date` against the REAL PIT facade's own authorized
   `boundary.max_as_of`. `SessionEngine.__init__()` now refuses
   construction outright -- before a single session runs, before any PIT
   read -- if `session_dates` contains anything past `stage_end_date`, or
   if `stage_end_date` itself exceeds `pit.boundary.max_as_of` (checked
   via `getattr`, so the existing `_UnboundedAccess`/`_EmptyAccess` test
   doubles, which expose no `.boundary`, are unaffected). Regressions
   (`test_33`): `test_session_dates_beyond_stage_end_date_is_refused_at_
   construction`, `test_stage_end_date_beyond_the_pit_facades_own_
   boundary_is_refused_at_construction`; `test_35` (below) additionally
   runs the whole scenario through a REAL `BoundedPITAccess`/
   `StageAccessBoundary`.
5. **The plan-acceptance gate didn't tie to the simulation it authorized.**
   `run_stage()` called `accept_research_plan()` -- real progress -- but
   then handed `SessionEngine` an `EntrySignal` carrying its OWN
   `direction`/`k`/`r_multiple`/`fraction`, completely independent of the
   accepted cohort; even the gate's own positive test used an EMPTY
   cohort while still authorizing a STOP_MANAGED entry to run. `EntrySignal`
   now carries ONLY `security_id`/`strategy_variant_id` -- the engine
   resolves the REAL `StrategyVariant` via `registry.get_variant()`,
   requires `variant.parent_hypothesis_id` to be IN
   `accepted_hypothesis_ids` (which `run_stage()` derives from
   `plan.hypothesis_cohort_ids`, never a caller-asserted set), requires
   `exit_hypothesis.exit_family == STOP_MANAGED_INVALIDATION` (the only
   family this engine has mechanics for), and derives
   direction/k/r_multiple/fraction from that SAME real variant/its parent
   hypothesis -- never from caller-typed fields. Any failure
   (`ENTRY_VARIANT_NOT_FOUND`, `ENTRY_VARIANT_NOT_IN_ACCEPTED_COHORT`,
   `ENTRY_UNSUPPORTED_EXIT_FAMILY`) is rejected before any price is read,
   exactly like the four amendment section-2 reasons. `run_stage()` also
   now threads `plan.cost_assumptions` through to `SessionEngine` itself
   (previously cost assumptions were not even a `SessionEngine`
   parameter at all). Regressions (`test_33`): five new tests covering
   variant-not-found, off-cohort, unsupported-family, and both the
   `run_stage()`-level gate-rejects and gate-ties-to-cohort cases.
6. **The integrated test never exercised the real, obligatory path.**
   `test_34` called `SessionEngine` directly against the `_UnboundedAccess`
   stand-in, never `run_stage()` or a real `BoundedPITAccess`/
   `StageAccessBoundary`, and its only invalidation was detected at the
   stage's OWN last close (never executed in-stage, so Pas 1's own
   priority over a same-day stop/target was never actually exercised).
   `test_34` itself is updated for the new `EntrySignal`/`SessionEngine`
   signature (real registered variants via `spec005.fixtures.
   stop_managed_variants`) and continues to serve as the mechanism-level
   demonstration (`SessionEngine` called directly, the same way
   `session.py`'s own functions are unit-tested in isolation).
   `tests/spec005/test_35_stop_managed_run_stage_end_to_end.py` is NEW:
   it goes through `run_stage()` itself, against a real `BoundedPITAccess`
   bounded by a real `StageAccessBoundary`, with a genuinely accepted
   STOP_MANAGED plan, nonzero costs (BOTH entry and exit slippage), and a
   trend invalidation detected mid-stage and EXECUTED at the very next
   in-stage session's open -- on a day whose own low would ALSO have
   breached the stop, had Pas 3' ever run for it. It asserts the closing
   tranche's `exit_reason` is `INVALIDATION`, never `STOP`, proving Pas 1
   ran first and retired the position before Pas 3' was ever reached.

A shared test helper, `tests/spec005/fixtures/stop_managed_variants.py`
(`build_registered_stop_managed_hypothesis()`,
`build_accepted_stop_managed_plan()`), factors out the
StrategyHypothesis/StrategyVariant/ResearchPlan construction test_32
already used inline -- now reused by test_33/34/35 as well, since all
three now need a REAL registered variant, not a caller-typed parameter
dict.

## Session Engine & Integration review, round 2 corrections

Review of `4560f93` confirmed entry slippage, persistent-incompleteness
marking, and the stale-mark fix all correct, and confirmed `test_35`'s
invalidation-over-stop priority proof. It found three further
integration-level problems, all now fixed:

1. **The executed stage was not tied to the plan's own zone periods.**
   `run_stage()` used to accept an already-built `pit: BoundedPITAccess`
   and a raw `session_dates` list -- nothing checked that the boundary
   backing `pit` was actually DERIVED from `plan`'s own declared zone
   dates. `test_35`'s own original fixture proved the gap: a plan with
   Formation in January, run against April session dates under a
   `StageAccessBoundary(zone=FORMATION_SELECTION, ...)` built completely
   independently of the plan -- `run_stage()` accepted it. `run_stage()`
   no longer takes a `pit` parameter AT ALL: it takes `conn`, `zone`, and
   a real `TradingCalendar`, and BUILDS the `StageAccessBoundary` itself
   via `zones.boundaries.build_stage_access_boundary_from_plan(plan,
   zone)` (already-accepted Batch 1/2 logic, reused, not reimplemented),
   then derives `session_dates` as EXACTLY that calendar's own sessions
   within `[zone_start, boundary.max_as_of]`. There is structurally no
   way left to hand `run_stage()` a period that disagrees with the plan's
   own zone dates. Two further checks close the identity gap completely:
   `trading_calendar.calendar_id` must equal `plan.trading_calendar_id`,
   and the calendar must pass its own content-address verification.
   `tests/spec005/fixtures/stop_managed_variants.py`'s
   `build_accepted_stop_managed_plan()` now also builds a REAL
   `TradingCalendar` bound to the plan by construction. Regressions
   (`test_33`): `test_run_stage_rejects_a_trading_calendar_that_does_not_
   belong_to_the_plan`, `test_run_stage_never_executes_sessions_outside_
   the_plans_own_formation_zone` (a calendar deliberately wider than the
   plan's Formation zone -- an April session is a real calendar session
   but never evaluated; a January session is).
2. **The calendar could be incomplete or out of order.** The prior
   `session_dates` check only excluded dates past `stage_end_date` --
   reversed order, duplicates, and a truncated list stopping before the
   stage's own real last session all passed silently (repro: a calendar
   declared through May 3rd, only May 1-2 actually supplied -- the stale
   final-mark bug from round 1 remained reachable through exactly this
   gap). `SessionEngine.__init__()` now rejects non-strictly-increasing
   or duplicate `session_dates` outright. Completeness against a REAL
   calendar is `run_stage()`'s own responsibility now (finding #1 above):
   since it derives `session_dates` directly from a verified
   `TradingCalendar`'s own sessions, there is no longer a caller-supplied
   list that could be truncated or reordered on that path at all. The
   final mark and any pending invalidation already referenced
   `stage_end_date`/the loop's own last iterated session correctly (round
   1's fix); with `run_stage()` now guaranteeing that list's completeness,
   that reference point is trustworthy on the real path too. Regressions
   (`test_33`): `test_session_dates_out_of_order_is_refused_at_
   construction`, `test_duplicate_session_dates_is_refused_at_
   construction`.
3. **Variants of the same security suppressed each other.** Position
   bookkeeping (`_open_positions`) and the `entry_signals` mapping were
   both keyed by bare `security_id` -- two DIFFERENT accepted variants
   signalling on the SAME security on the SAME day could not even both be
   represented in the `entry_signals` dict (one key collision silently
   overwrote the other), and even if they could, the "already open, not a
   candidate" check would have suppressed the second variant's signal
   entirely. `EntrySignal`/position bookkeeping are now keyed by
   `(security_id, strategy_variant_id)` throughout -- the "at most one
   open position" restriction is scoped to the VARIANT, never the bare
   security. `StopManagedPosition` gained an additive, optional
   `strategy_variant_id` field (default `None`, so every existing
   hand-built `StopManagedPosition(...)` in `protection.py`/`session.py`/
   `costs.py`/`taxonomy.py`'s own unit tests stays valid unchanged);
   `SessionEngine` stamps it immediately after opening a position.
   `EntryDisposition` gained the same field, so two variants' dispositions
   for the same security/day stay distinguishable. Regression (`test_33`):
   `test_two_variants_on_the_same_security_same_day_both_open_independent_
   positions` -- two variants with different `k` both open, both tracked
   distinctly, with correspondingly different `active_stop` values proving
   they are genuinely independent objects, not one shared/overwritten one.
