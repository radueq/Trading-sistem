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
described in their own section below, also now fixed). A follow-up to
THAT round (`ba38a4b`) closed one further finding in the entry_signals
identity check itself -- Session Engine & Integration's own review is
now closed (ACCEPTED for the key/signal identity fix; the general
accepted baseline itself remains `3cdc532`, with each delivery's own
acceptance tracked separately). A NEW delivery, "Discovery Integration &
Legacy Exits" (its own section at the end of this document), then
addressed the three obligations Session Engine & Integration's own
acceptance explicitly left outstanding: Discovery-based entry-signal
matching, real `InvalidationCondition` evaluation, and a TIME_EXIT/
SIGNAL_INVALIDATION execution engine. This document describes what each
delivery does; it is not itself a claim of acceptance -- that newest
delivery is UNACCEPTED, pending review, exactly like every other section
in this document before it was reviewed.**

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

**Status update:** the three obligations below were the subject of the
"Discovery Integration & Legacy Exits" delivery (its own section further
down describes what it built). They are restated here, unedited, as the
historical record of what was outstanding going into that delivery --
whether that delivery actually closes them is for review to say, exactly
like every other section in this document.

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

## Session Engine & Integration review, round 2 follow-up correction

Review of `7bf2035` confirmed all three round-2 findings fixed, but found
one further problem in finding #3's own fix: the `entry_signals` KEY
`(security_id, strategy_variant_id, signal_date)` and the `EntrySignal`
VALUE stored at it both carry `security_id`/`strategy_variant_id` --
`_evaluate_pending_entry()` resolves the variant and stores the resulting
position under `signal.strategy_variant_id` (the VALUE's own field),
while the "already open" check at Pas 2 tests `(security_id, variant_id)
in self._open_positions` using the KEY's fields. These were never checked
against each other. Repro: a dict with key `(SEC, VAR_A, d1)` -> a
correctly-matching `EntrySignal(SEC, VAR_A)` (opens fine), plus a SECOND
entry, key `(SEC, VAR_B, d2)` -> an EntrySignal that still claims
`strategy_variant_id=VAR_A` (a mismatched value) -- the "already open"
check tests `(SEC, VAR_B)`, finds nothing, proceeds, then stores the
result at `(SEC, VAR_A)` (from the signal's own field) -- silently
overwriting the FIRST position with no trace it ever existed.

`SessionEngine.__init__()` now validates every `entry_signals` entry
before anything else runs: each key's `(security_id, strategy_variant_id)`
must equal its own stored `EntrySignal`'s `(security_id,
strategy_variant_id)` exactly, or construction raises immediately --
before any PIT read, before any position is opened or overwritten.
Regressions (`test_33`):
`test_variant_mismatch_between_key_and_signal_is_rejected_at_construction`,
`test_the_exact_overwrite_repro_is_rejected_before_either_signal_ever_runs`
(the precise two-signal scenario above -- construction rejects the WHOLE
`entry_signals` mapping, so neither signal ever runs),
`test_security_mismatch_between_key_and_signal_is_rejected_at_
construction`, and
`test_consistent_keys_for_two_variants_on_the_same_security_still_
construct_fine` (confirming the new check does not reject the
already-accepted, valid two-variants case).

## Discovery Integration & Legacy Exits delivery

Addresses the three obligations left outstanding after Session Engine &
Integration's own acceptance (`ba38a4b`), pursued at the effort level
Radu requested for this delivery. Nothing in `SessionEngine`/`session.py`/
`protection.py`/`costs.py`/`taxonomy.py`/`plan_integration.py` is modified
-- every new capability lives in NEW files or additive extensions of
`engine.py`'s own `run_stage()` function body (never its already-accepted
`SessionEngine` class), so the STOP_MANAGED_INVALIDATION path this
document already describes is untouched, byte-for-byte (confirmed by the
full suite: the pre-existing 638 passed/1 skipped baseline is unchanged
within the new total below).

1. **Discovery-based entry-signal matching** (`backtest.exits.
   discovery_integration.matches_entry_definition()`): a real
   implementation of Spec #004 SS11-13's `EntryDefinition` vocabulary --
   AND over `core_conditions`/`confirmation_conditions`, each a
   `LaneStateCondition` (exact `state_signature[lane]` match, `negate`
   honored generically even though entry conditions are validator-
   enforced non-negated) or `ReasonCodeCondition` (presence in
   `reason_codes`) -- evaluated against a real `discovery.models.entities.
   DiscoveryObservation`, mirroring `evaluation.observations.signatures.
   matches()`'s own established pattern for the structurally distinct
   Spec #003 vocabulary. `False` outright when no observation exists for
   a security that session (an ineligible/unobserved security can never
   satisfy an entry thesis).
2. **`InvalidationCondition` evaluation** (`discovery_integration.
   evaluate_invalidation_conditions()`): lane-based (invalidates when the
   CURRENT observed label leaves `holds_labels`) and reason-code-based
   (invalidates when that code's presence flips relative to an
   `entry_observation` snapshot, `triggers_on_presence` deciding
   appearance vs. disappearance) -- exactly `InvalidationCondition`'s own
   documented semantics, the SAME field shared by SIGNAL_INVALIDATION and
   STOP_MANAGED_INVALIDATION alike (Spec #004's own design: one shared
   `invalidation_conditions` vocabulary, not a per-family reinvention).
   Combining MULTIPLE conditions as an OR (any one triggers) is this
   function's own documented INFERENCE -- no spec text states how more
   than one simultaneously-active condition combines; OR is the
   conservative, risk-side reading, consistent with `advance_intrabar()`'s
   own stop-over-target tie-break precedent. Returns `UNKNOWN` (never a
   false negative) when the current observation is missing, or a
   reason-code condition cannot be evaluated for lack of an entry
   snapshot -- but a definite `INVALIDATED` from any OTHER, evaluable
   condition is still reported; an unrelated data gap never suppresses a
   real invalidation.
3. **TIME_EXIT/SIGNAL_INVALIDATION execution engine**
   (`backtest.exits.legacy.LegacySessionEngine`): a SEPARATE engine from
   `SessionEngine`, never an extension of it, sharing only the SAME
   `entry_signals`/`EntryDisposition` shapes and the SAME identity/
   ordering/stage-bound construction guards, independently reimplemented
   (never a refactor of `SessionEngine.__init__()`). Both older families
   use a FIXED `exit_execution_policy=BAR_CLOSE` (no deferred/scheduled
   fill state at all, unlike STOP_MANAGED_INVALIDATION's own,
   separately-versioned execution-semantics profile): TIME_EXIT counts
   holding bars against the position's own `entry_session_index` in the
   stage's `session_dates` ("holding bar 1 = entry bar itself; holding
   bar N = entry bar index + (N-1)", Spec #004's own formula, including
   the N=1 same-session-exit edge case); SIGNAL_INVALIDATION exits on
   invalidation OR `max_holding_bars`, whichever first, PREFERRING
   invalidation on an exact same-session tie (this module's own explicit,
   documented tie-break -- no spec text covers this exact simultaneity).
   `reconcile_split_for_legacy_position()` is an INDEPENDENT
   reimplementation of `session.reconcile_split_for_open_position()`'s
   authorization/lateness logic, narrowed to the one field a
   `LegacyPosition` has to rescale (`entry_fill_price` -- the same
   frozen-entry-price staleness problem `StopManagedPosition` has, not
   specific to that one family). `classify_legacy_position()`/
   `evaluate_legacy_stage_results()` mirror `taxonomy.classify_position()`/
   `engine.evaluate_stage_results()` narrowed to a `LegacyPosition`'s own
   shape (no partial-profit tranche ever, so `w` is always 0 -- neither
   `costs.compute_w()` nor `aggregate_position_return()` is needed).
4. **Mixed-family integration through `run_stage()`**: `run_stage()`'s
   OWN body (not `SessionEngine`) now partitions the SAME `entry_signals`
   mapping by each signal's resolved variant's `exit_family`
   (`_partition_entry_signals_by_family()`), constructs a SECOND,
   independent `LegacySessionEngine` alongside the existing `SessionEngine`
   against the SAME `session_dates`/`stage_end_date`/cohort/cost_
   assumptions, and merges both results into the SAME `SessionEngineResult`
   (positions concatenated, dispositions concatenated, `final_closes`
   unioned -- asserted, not silently preferred, on the disagreement that
   should structurally never happen since both derive it from the same
   underlying price series). A signal naming an unresolvable variant is
   routed to `SessionEngine` by convention, producing exactly ONE
   rejection disposition, never one from each engine (its VARIANT_NOT_
   FOUND/NOT_IN_ACCEPTED_COHORT checks are family-agnostic, checked before
   the family check itself). `run_stage()`'s existing `entry_signals`/
   `invalidation_observer` PARAMETERS are unchanged -- an existing caller
   supplying only STOP_MANAGED signals sees byte-for-byte identical
   behavior (confirmed: the pre-existing test suite is unaffected).
   `tests/spec005/test_38_mixed_family_run_stage.py` is the integrated
   demonstration: one hypothesis, three materialized variants (TIME_EXIT,
   SIGNAL_INVALIDATION, STOP_MANAGED_INVALIDATION) sharing one Discovery-
   matched entry signal, each exiting differently (bar-count, real
   invalidation, still-censored-at-horizon) in the SAME `run_stage()` call,
   with entry AND exit slippage plus commissions verified against the
   same cost primitives `test_35` already established, for all three
   families.

**What this delivery does NOT do -- stated explicitly, not silently
narrowed:**

- `run_stage()` itself still does not invoke Spec #002's Discovery engine,
  or `backtest.data.context.StageReadContext`, internally. A caller/test
  builds `entry_signals`/`invalidation_observer` from real
  `DiscoveryObservation`s via `discovery_integration`'s functions, THEN
  passes them to `run_stage()` exactly as before -- the two are still
  composed by the caller, not fused into one call. `discovery_
  integration.observations_by_session_from_caches()` is a real, tested
  adapter over Batch 2's already-accepted `HistoricalObservationCache`
  (the type `StageReadContext.get_or_compute_observations()` produces),
  so a caller wanting LIVE, PIT-safe Discovery computation has a genuine,
  regression-tested path to it -- but deciding a canonical universe/
  benchmark/config-version policy for `run_stage()` to resolve entirely on
  its own remains a further, separate integration step (`ResearchPlan`
  carries `benchmark_security_id` but no canonical non-benchmark universe
  declaration yet).
- The mixed-cohort integrated test (`test_38`) uses HAND-BUILT
  `DiscoveryObservation` objects, not a live `compute_discovery_
  observations()` run -- Spec #002's own test suite already proves that
  function computes correct states from price data; re-deriving specific
  percentile-based lane states deterministically from synthetic price
  series was judged orthogonal to what this delivery needs to prove
  (that real entry-matching/invalidation-evaluation and the legacy
  execution engine are wired and correct), and risked adding an entire
  second surface of potential mistakes to a single delivery.
- 638 passed/1 skipped was the reported baseline before this delivery;
  682 passed/1 skipped (44 new tests: 20 in `test_36`, 23 in `test_37`,
  1 in `test_38`) is this delivery's own self-reported full-suite result
  -- not independently verified.

## Discovery Integration & Legacy Exits review corrections

Review of `e5ee331` found the matching/legacy-engine substance real
progress, but identified four defects and one further integration
obligation. All five addressed here; none of the four already-delivered
capabilities above (matching, invalidation evaluation, `LegacySessionEngine`,
`run_stage()` partitioning/merge) were reopened beyond the specific fixes
below.

1. **A missing lane component produced a certain INVALIDATED instead of
   UNKNOWN.** `evaluate_invalidation_conditions()`'s lane-based branch read
   `state_signature.get(condition.lane) not in holds_labels` -- when the
   lane was absent from the observation entirely (a real Discovery data
   gap, e.g. insufficient history for that lane's own percentile window),
   `.get()` returned `None`, and `None not in holds_labels` is `True`,
   producing a false, certain `INVALIDATED` instead of `UNKNOWN`. Fixed:
   the lane's PRESENCE in `state_signature` is checked first -- absent
   contributes `saw_unknown` (the same mechanism already used for a
   reason-code condition missing its `entry_observation`), never an
   immediate `INVALIDATED`; a lane that IS present with a label outside
   `holds_labels` is unaffected, still `INVALIDATED` immediately.
   Regressions: `test_lane_missing_from_the_observation_is_unknown_not_
   invalidated`, `test_a_definite_invalidation_from_another_lane_survives_
   a_missing_lane` (`test_36`); `test_a_missing_lane_from_a_real_discovery_
   observer_taints_the_engine_permanently` (`test_37`) exercises the SAME
   fix end to end through `LegacySessionEngine` via the real
   `build_invalidation_observer()` closure (not a hand-typed `"UNKNOWN"`
   stub), confirming `invalidation_path_incomplete` is set and survives a
   later, clean session.
2. **Observations were never checked against the exact key they were
   filed under.** Neither `build_entry_signals_from_observations()` nor
   `build_invalidation_observer()` verified that
   `observations_by_session[as_of][security_id]` actually carried THAT
   `(security_id, as_of)` pair's own identity -- an observation dated or
   attributed differently than its own dict key would silently drive a
   match or an invalidation verdict off the wrong day or instrument.
   `observations_by_session_from_caches()` had the same gap one level
   down: it checked `cache.as_of` against its own dict key, but never
   each individual observation INSIDE `cache.observations` against that
   same `as_of`, and a dict comprehension keyed by `security_id` let a
   duplicate silently overwrite instead of being rejected. Fixed: a new
   `_validate_observations_by_session()` check runs eagerly, over the
   WHOLE mapping, at the START of both builders (for
   `build_invalidation_observer()`, at closure-BUILD time, never lazily
   on first call); `observations_by_session_from_caches()` now checks
   each observation's own `as_of` against its cache's `as_of` and rejects
   two observations for the same `security_id` outright. Regressions
   (`test_36`): `test_build_entry_signals_rejects_an_observation_dated_
   differently_than_its_key`, `..._naming_a_different_security`,
   `test_invalidation_observer_build_rejects_inconsistent_observations_
   eagerly`, `test_observations_by_session_from_caches_rejects_an_
   internally_mismatched_observation`, `..._rejects_duplicate_security_ids`.
3. **The legacy partition's own validation ran after the STOP_MANAGED
   simulation had already executed.** `run_stage()` constructed AND ran
   `SessionEngine` (every PIT read and `invalidation_observer` call its
   STOP_MANAGED signals need) BEFORE `LegacySessionEngine` was even
   constructed -- so an inconsistent `legacy_signals` partition (the exact
   entry_signals identity mismatch `ba38a4b` already guards against) only
   surfaced AFTER that simulation ran, losing the "inconsistent input
   rejected before any PIT read or position mutation" guarantee for the
   mixed-cohort path specifically. Fixed: BOTH engines are now
   CONSTRUCTED (where that validation happens, on a pure Python mapping,
   with no PIT access at all) before EITHER is ever run. Regression
   (`test_38`): `test_a_valid_stop_managed_signal_never_runs_when_a_
   legacy_signal_fails_identity_validation` -- monkeypatches
   `BoundedPITAccess`'s own read methods and the `invalidation_observer`
   to raise if ever called, making "zero PIT reads, zero observer calls"
   self-enforcing; independently confirmed to fail (catching the bug) when
   temporarily re-ordered back to construct-then-immediately-run
   `SessionEngine`.
4. **`LegacySessionEngine` accepted non-finite/non-positive prices as
   real fills.** `advance_legacy_position_at_close()` rejected only
   `close_price is None` -- NaN, +/-infinity, zero, and negative all
   passed straight through into a CLOSED/EVALUABLE tranche when an exit
   was due. The same gap existed for the entry-day open (`_evaluate_
   pending_entry()`), for the engine's own `_last_close_observation`
   recording (a corrupted final-session close could become a still-open
   position's censored mark), and for `evaluate_legacy_stage_results()`'s
   own `final_closes` lookup. Fixed: a new `_is_usable_price()` helper
   (finite AND strictly positive, mirroring `session.update_trailing_
   stop_at_close()`'s own established rigor for `close_price`/`atr_today`)
   is applied at all four points -- an unusable exit/entry price is
   treated exactly like a missing bar (`EXIT_FAILED` / `ENTRY_NO_ENTRY_
   BAR`), an unusable close is never recorded as a final-mark candidate
   (falls through to the EXISTING `CENSORED_MARK_UNAVAILABLE` path, no
   new machinery needed), and `evaluate_legacy_stage_results()` raises
   rather than feeding a bad mark into `open_remainder_net_return()`.
   Regressions (`test_37`): `test_advance_legacy_position_at_close_
   rejects_non_finite_or_non_positive_close_prices` (NaN/+inf/-inf/0/-1,
   direct function call), `test_entry_with_non_finite_or_non_positive_
   open_is_rejected_as_no_entry_bar`, `test_final_close_with_a_non_finite_
   price_is_never_used_as_the_censored_mark` (both through a real
   `LegacySessionEngine` run), `test_evaluate_legacy_stage_results_
   rejects_a_non_usable_final_mark`.
5. **The real Discovery -> execution pipeline itself was never
   traversed end to end.** `test_38`'s own hand-built observations proved
   the matching/invalidation/execution WIRING but never `StageReadContext`
   -> real `compute_discovery_observations()` -> the `HistoricalObservation
   Cache` adapter -> `run_stage()`, in one run. Confirmed acceptable to
   keep as a SEPARATE orchestrator (never fused into `run_stage()` itself)
   -- `tests/spec005/test_39_real_discovery_pipeline_run_stage.py` is that
   orchestrator, built once: roughly 1.5 years of smooth, deterministic
   daily bars (no randomness) puts the real, unmodified Discovery
   computation's own `volatility` lane at `EXTREME_COMPRESSION` throughout
   (read off empirically from the actual computation, never assumed), then
   a sharp price swing introduced on the stage's third session flips it to
   `EXTREME_EXPANSION` -- a genuine state transition Discovery itself
   detects (it also emits `STATE_TRANSITION` in `reason_codes`). A real
   `StageReadContext` computes one `HistoricalObservationCache` per session
   via the actual, unmodified `compute_discovery_observations()`;
   `observations_by_session_from_caches()` reshapes them; `build_entry_
   signals_from_observations()`/`build_invalidation_observer()` build
   `run_stage()`'s inputs from that REAL output; `run_stage()` runs
   unmodified. The SIGNAL_INVALIDATION position opens on the real match and
   closes exactly on the real state-transition session, with a hand-
   verifiable +30% zero-cost return. `test_38`'s own hand-built-observation
   test is kept unchanged, for the exact economic-formula verification a
   1.5-year synthetic price history would make unwieldy to hand-derive.

`test_39`'s own price path also confirms an incidental, harmless
byproduct of feeding a real, multi-day-persistent Discovery state into
`build_entry_signals_from_observations()`: the shared entry condition
holds on two consecutive sessions (D1 and D2), so the hypothesis's own
auto-materialized TIME_EXIT(1) sibling variant (which exits on its very
own entry day, freeing its `(security_id, strategy_variant_id)` key
immediately) opens a SECOND, independent position from the second day's
signal -- expected, correct behavior of the "one signal per day the
condition holds, already-open positions are skipped" design, not a
defect; the test asserts the resulting position count explicitly rather
than silently assuming two.

Full suite after these five fixes: 696 passed, 1 skipped (was 682/1;
14 new tests: 7 in `test_36`, 5 in `test_37`, 1 in `test_38`, 1 new file
`test_39`) -- self-reported, not independently verified.

---

## Consolidated closure status at `9feb4a5` (Batch 3 closure verification)

This section is the SINGLE current-status summary requested for the Batch 3
closure verification. It supersedes no prior section above -- every review
round, finding, and fix described earlier in this document stands as the
historical record of what was found and corrected, in the order it happened.
This section only adds where things stand now, at commit `9feb4a5`, and
names two contractual gaps this verification pass found that no earlier
section disclosed.

**Point-in-time acceptances on record for this code (`9feb4a5`) and its
direct ancestors**, each scoped exactly as stated, none implying the others
or the whole:
- Batch 3 core (STOP_MANAGED_INVALIDATION mechanics, amendment sections
  1-14): three GPT review rounds plus the narrow round-3 follow-up, the
  follow-up's own acceptance covering only that one regression.
- "Session Engine & Integration" (multi-security loop, mandatory plan gate,
  exit slippage, aggregate cost evaluation): its own review closed, ACCEPTED
  for the key/signal identity fix at `ba38a4b` -- not a statement that Batch
  3 as a whole is accepted.
- "Discovery Integration & Legacy Exits" (Discovery-based entry matching,
  real `InvalidationCondition` evaluation, `TIME_EXIT`/`SIGNAL_INVALIDATION`
  execution engine, mixed-family `run_stage()` integration): ACCEPTED for
  all five review-round-1 findings at `9feb4a5`. This acceptance is
  explicitly NOT a statement that Batch 3 or Spec #005 is closed.
- The general accepted baseline remains `3cdc532` (Spec #005 Batch 1/2)
  throughout all of the above -- unchanged by any of these point
  acceptances.

**Correction to an overclaiming statement in this document.** Line 46 above
lists `mae_mfe.py` alongside `protection.py`, `session.py`, `costs.py`,
`taxonomy.py`, `entities.py`, and `plan_integration.py` as modules that
implement "the STOP_MANAGED_INVALIDATION position's own per-position
mechanics in full" -- grouping it with modules that ARE wired into the
running engine. This is not accurate for `mae_mfe.py`. Evidence:
`compute_tranche_mae_mfe()` (`backtest/exits/mae_mfe.py:57`, amendment
section 12) is a correct, independently unit-tested formula (`test_28`) --
but it has no caller anywhere in `backtest/exits/engine.py`,
`backtest/exits/session.py`, or `backtest/exits/legacy.py` (confirmed by
a full-tree grep for `mae_mfe`/`compute_tranche_mae_mfe`: the only other
hit is a docstring comment in `costs.py:48`, which merely explains why
`Tranche.exit_fill_price` is never overwritten with a slipped value "for
MAE/MFE" -- it does not call the function or wire it in). Neither
`Tranche` (`backtest/exits/entities.py:79-108`) nor `StopManagedPosition`
(`entities.py:112-167`) carries an `mae`/`mfe` field at all. Every other
mention of MAE/MFE elsewhere in this document (lines 99-101, 150-154,
234-243, 295) discusses the formula's own internal correctness -- partial
coverage on an intraday-exit day, numeric validation, the known-zero
excursion at entry -- never once disclosing that the formula is not
reachable from any real `run_stage()` result. No `Tranche`, `StopManagedPosition`,
or `LegacyPosition` produced by an actual stage run carries an MAE/MFE
value today. This is a genuine integration gap against amendment section
12, found by this closure verification, not a new defect introduced by any
of the deliveries described above -- `mae_mfe.py` has been in this state
since Batch 3's own initial delivery.

**A second contractual gap found by this closure verification.** Amendment
section 11 names an OPTIONAL `SelectionRule.maximum_censored_ratio` field
(interval `[0,1]`, "a declared-adequacy requirement... NOT a remedy for
selection bias" -- the amendment's own wording). A full-tree grep for
`maximum_censored_ratio` across `src/`, `tests/`, and `docs/` finds it
ONLY inside `docs/spec005_exit_amendment_v1.0.md` itself. The field does
not exist on `SelectionRule` (`backtest/models/entities.py`), is not
validated by `validate_selection_rule()`, and has no test. Reported here
with evidence per instruction, regardless of the field's optional status
in the contract text -- the decision on whether this blocks anything is
left to review, not made here.

**Selection/ranking orchestration -- scope boundary, not a new gap.**
Section 11's mandatory `ranking_metric = MEDIAN_NET_RETURN_TO_EXIT_OR_STAGE_END`
requirement for any cohort containing `STOP_MANAGED_INVALIDATION` variants
IS enforced (`backtest/exits/plan_integration.py:86`, tested by `test_32`).
What does NOT exist anywhere in the codebase is a function that actually
COMPUTES `executed_entries_count`/`censored_ratio`/`evaluable_ratio` for a
real cohort of variants and uses them, together with `minimum_executed_
trades`/`minimum_evaluable_trades`/`minimum_evaluable_ratio`, to accept,
reject, or rank that cohort. The metric computation itself exists and is
unit-tested (`test_30`, `backtest/exits/taxonomy.py`); the orchestration
across a real, multi-variant cohort does not. This is consistent with
Batch 3 having never claimed to include cohort-level selection -- it is
named here as a precise scope boundary, with its exact contractual
reference (amendment section 11), for whichever stage takes it up next.

**Conventions implemented by inference, not yet explicitly confirmed
against contract text.** Each of these is a real, tested behavior of the
current code; none is a verbatim quote from either amendment text or the
(absent) base contract. Listed here once, together, so a future reviewer
does not have to rediscover them from docstrings scattered across the
tree:
- **OR-combination of multiple `InvalidationCondition`s** for one exit
  hypothesis (`discovery_integration.evaluate_invalidation_conditions()`):
  any one triggering condition invalidates the whole position. The
  function's own docstring states this is its documented inference, not a
  spec quote, reasoned from `advance_intrabar()`'s own stop-before-target,
  risk-side-wins precedent. Tested (`test_36`, multi-condition cases).
- **Invalidation-detected-at-close vs. time-cap tie-break** and the general
  "protective/risk side always wins" convention carried from `advance_
  intrabar()` into the legacy engine's own invalidation-vs-cap ordering
  (`legacy.advance_legacy_position_at_close()`).
- **The derived entry-slippage formula** (`costs.apply_entry_slippage()`):
  the amendment's section 9 gives an explicit exit-side slippage sub-formula
  but never an entry-side one for `CostAssumptions.slippage_entry_bps` --
  the entry-side formula is this codebase's own construction from the same
  "slippage always makes the fill worse" principle, not a quoted formula.
- **Routing an unresolvable exit-family variant to `SessionEngine` by
  convention** (`engine._partition_entry_signals_by_family()`): a signal
  whose variant cannot be resolved to a known exit family is routed to the
  STOP_MANAGED path by default, where its own existing rejection logic
  (`test_unresolvable_variant_id_is_rejected_before_any_price_read`) is
  reused rather than duplicated for the legacy path. An implementation
  convenience, not a documented contractual assignment.
- **No single classify-and-evaluate dispatcher exists across a mixed-family
  `result.positions`.** `run_stage()` returns `StopManagedPosition` and
  `LegacyPosition` instances concatenated in one tuple; `taxonomy.
  classify_position()`/`evaluate_stage_results()` handle the former,
  `legacy.classify_legacy_position()`/`evaluate_legacy_stage_results()`
  the latter -- a caller wanting one taxonomy pass over a mixed cohort must
  call both, keyed on instance type. Both delivery review rounds treated
  this as within scope (never raised as a finding); it is named here only
  as a real, undocumented shape a future integration should know about.

**Full suite at `9feb4a5`:** `PYTHONPATH=src:tests python3 -m pytest -q -rs`
-> `696 passed, 1 skipped` in ~38s, re-run for this closure verification
(not merely carried forward from the prior report) -- self-reported by
Claude, not independently executed by Radu. The one skip is
`tests/test_08_provider_consistency.py:12`, `PENDING_LEVEL_2_DATA`: only
one data provider (yfinance) exists at Level 1, so cross-provider
comparison has nothing to compare against; deferred to Level 2/3 per
Radu's approval (2026-09-20). This skip predates Spec #005 entirely and is
unrelated to any of the deliveries described in this document.
