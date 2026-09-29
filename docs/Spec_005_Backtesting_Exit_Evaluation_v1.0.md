# Implementation Specification #005 — Backtesting & Exit Evaluation

Version: 1.0 — TECHNICAL CONSENSUS CLOSED; PENDING RADU'S APPROVAL TO IMPLEMENT

Date: 2026-09-26

Project: Trading sistem. Intended baseline: #001–#004 accepted, PATCH #001-D implementation b1bb301 and closure cfa0809, as reported in the handoff. GPT inspected relevant source excerpts in the #003/#004 review bundles and their patches, not a fresh checkout of cfa0809. Claude subsequently confirmed HEAD cfa0809 and a clean working tree, completed the full review, and accepted the final calendar and identity-hash corrections. No new checkout or test run by GPT is claimed.

## 1. Purpose and scope

Build a deterministic Daily backtester that replays preregistered US-equity strategies, compares their frozen exit variants, selects at most one variant per hypothesis using a preregistered rule, and evaluates only that selection on an untouched Development Validation interval.

The core makes zero LLM calls. GPT/Claude may review reports outside the runtime. Level 1 data supports infrastructure validation, not a research-grade profitability or deployment claim. Crypto, options, broker orders, capital allocation, portfolio optimization, new indicators, ATR-stop optimization and Locked OOS evaluation are out of scope.

No upstream source, registry entry, fingerprint or validator may be silently changed. A genuine incompatibility is an IMPLEMENTATION BLOCKER with a minimal proposed patch. This specification does not reopen accepted patches without evidence.

## 2. Review conclusions and changes from the scaffold

1. Accept explicit EvaluationRunRegistry inputs; no new #003 lookup store is required.
2. Verify the existing evaluation_run_id using the EXACT existing fingerprint recipe, then cross-check every linked provenance field. A valid hash is a consistency check, not proof of historical execution or of unviewed data.
3. Treat development_end as a conservative outcome boundary only for accepted, bounded #003 runs. Require non-null dates and matching evidence lineage. Do not generalize a guard in one outcome function into proof that every upstream data access was bounded.
4. Reactive invalidation detected using a completed close fills at the next eligible session open, never at the close just used to calculate the decision.
5. Preserve the hard max_holding_bars cap: a scheduled close exit at the cap wins over an invalidation first detected at that same close. There is no routine cap+1 extension.
6. Do not silently redefine #004 exit_execution_policy as detection timing. Its name and fixed BAR_CLOSE value are ambiguous when read beside its docstring. Use the explicit, versioned compatibility interpretation in section 9, confirmed in the completed review.
7. Selection folds are development diagnostics. They are not independent validation after #003/#004 used the containing period to form hypotheses.
8. No formal trade-level p-values or confidence-interval deployment gates in V1.

## 3. Research lifecycle

The three zones are:

| Zone | Permitted use | Outputs |
|---|---|---|
| FORMATION_SELECTION | #003 evidence, #004 hypothesis formation, #005 comparison and selection | All variant reports and a frozen selection record |
| DEVELOPMENT_VALIDATION | Replay selected variant(s), with unchanged definitions, costs and rules | Descriptive validation report, data adequacy status |
| LOCKED_OOS | No reads, evaluation or release in #005 V1 | Boundary metadata only |

Different functions/services own selection and validation. Validation accepts a frozen selection record; it cannot call the selector or enumerate unselected variants for performance evaluation. A future LockedOOSEvaluationEngine must be separate and is not implemented here.

ResearchPlan is frozen before outcome replay. It contains explicit inclusive zone dates, session calendar, hypothesis cohort, immutable configuration artifacts, costs, selection rule, fold boundaries and approval/provenance metadata. Actual dates and quantitative support thresholds remain required run inputs; this specification does not invent them from unavailable data.

Required inequalities:

    formation_start <= formation_end < validation_start <= validation_end < locked_oos_start
    each_evidence_run.development_end <= formation_end
    each_evidence_run.development_end < validation_start

The maximum exposure boundary includes ALL evidence runs and prior research relevant to the cohort, not only the winning hypothesis. Record other known manual/agent inspection in an ExposureManifest. Prior views of validation outcomes invalidate an UNSEEN claim. If no clean interval remains, report VALIDATION_UNAVAILABLE; do not relabel old data or borrow from Locked OOS.

Warm-up data before a zone may be read to compute already-frozen rolling features. It cannot create pre-zone trades or refit thresholds using validation outcomes. No validation entry signal originates before validation_start. Each stage starts flat and has no carry-in trades.

## 4. Input contracts and evidence integrity

Required inputs: preregistered hypothesis and full frozen variants, read-only Hypothesis Registry view, relevant HypothesisUniverse, every referenced EvaluationRunRegistry, corresponding frozen evaluation/discovery configuration artifacts, ResearchPlan, execution profile, data capability manifest and bounded data access.

Preflight must reject:

- Missing/non-preregistered hypothesis, missing or duplicate variant, foreign parent, or a variant-set mismatch.
- Changed parent or variant definition hashes; failed upstream proposal/approval lineage checks.
- Mismatched evaluation_run_id, signature_id/set, timeframe, config or engine versions wherever linked.
- Missing evidence dates, invalid order, evidence extending into validation, or an unsupported evaluation mode.
- Config content inconsistent with a supplied version identifier.
- Missing information required to validate the existing content-address recipe.

Recompute #003 run identity using EXACTLY these eight fields: development_start, development_end, timeframe, signature_set_id, discovery_config_version, evaluation_config_version, bootstrap_seed and comparison_seed. This recipe was confirmed by Claude in evaluation/engine.py:370-376 at cfa0809. Pass no other field into build_run_id.

Then reuse hypothesis.validation.provenance.check_provenance_matches_run() unchanged as an independent linkage check. It compares evaluation_run_id, evaluation_engine_version, evaluation_config_version, discovery_engine_version, discovery_config_version, signature_set_id and timeframe between hypothesis provenance and the supplied registry. signature_set_id and timeframe are covered by both mechanisms intentionally: internal identity consistency and cross-object agreement are different checks.

Additionally require run_registry.mode == "FORMAL_DEVELOPMENT" and match run_registry.benchmark_security_id to the ResearchPlan benchmark. Neither the legacy hash nor the linkage function establishes these two requirements.

Archive the complete registry and configuration artifacts in EvidenceInputBundle. Preserve horizons, bootstrap_iterations, comparison_iterations, multiple_testing_method and created_at even though they are not in the eight-field recipe. Existing config-consistency checks still apply; audit retention is not permission to ignore a known inconsistency. These fields are not substitutes for the explicit period and mode guards.

Hash recomputation verifies only that the supplied fields produce the supplied ID. It does not authenticate the object, prove that a historical run occurred, establish that data were unseen, or detect coordinated replacement of both fields and ID. It is not an anti-forgery certificate. Immutable lineage artifacts and the exposure record remain necessary. #005 cannot retroactively certify an old #003 dataset that #003 did not retain.

## 5. Entities owned by #005

| Entity | Minimum semantic content |
|---|---|
| ResearchPlan | Zone dates, folds, full cohort, selection policy, costs, calendar, execution profile, exposure declarations, hashes |
| DataCapabilityManifest | Provider, Level 1/2, survivorship/delisting support, knowledge-time quality, return basis, limitations |
| EvidenceInputBundle | Full supplied registries/configs and cross-check results |
| DataSnapshotManifest | Scope, table/field manifests, canonicalization version, content digest, replay artifact reference |
| HistoricalObservationCache | Session/security observations and explicit missingness, discovery config/code and snapshot scope |
| SignalEvent | Family/security/session, matched conditions and originating observation identity |
| SignalDisposition | Signal/variant reference, EXECUTED or explicit non-execution reason |
| BacktestTrade | Entry/exit events, intended and actual timing, direction, fills, quantities/basis, costs, status, diagnostics |
| VariantComparisonReport | Every frozen variant, metrics, support, exclusions and fold results |
| StrategySelectionRecord | All candidates, gates, ranking metric values, rule/config hashes, selected ID or none, source comparison identity |
| BacktestRunRegistry | Semantic identity, stage, inputs, stage snapshot, code/config versions, outputs and audit timestamps |
| ValidationConsumptionRecord | Selection identity, validation window, first-open event, reruns and disclosure history |
| DevelopmentValidationReport | Selected variants only, adequacy, metrics, limitations, no reselection |
| CostSensitivityReport | Fixed trade paths under frozen alternative cost assumptions |

Use immutable typed records. Field names may follow existing conventions if mappings are documented; economic semantics cannot drift.

## 6. Data access and snapshot identity

All market information used in decisions flows through #001 PIT APIs with the appropriate session as_of. Never query raw tables as an alternative feature/fill engine. A separate read-only fingerprint/snapshot operation may read underlying facts inside the stage's authorized scope.

Freeze or open a consistent read snapshot for the entire run. Hash exactly that snapshot; concurrent ingestion must not produce a digest from one state and trades from another.

Use streaming SHA-256 over canonical typed records. Include all relevant raw OHLCV, security/symbol history, corporate actions, available_at/knowledge status, listing/status facts, benchmark inputs and calendar facts consumed or capable of affecting the bounded query. Include warm-up and adjustment dependencies, not only signal dates. Include unknown/fallback facts and absence-defining query scope. A correction affecting eligibility must change the fingerprint even if it removes the security from the final eligible set.

Canonicalization: versioned table/field names, stable primary-key ordering, UTF-8, explicit nulls, ISO dates/UTC timestamps, finite numbers with a stable representation, no ambiguous concatenation. Reject NaN/infinite prices and inconsistent duplicate keys. Administrative ingestion times may be excluded only where no runtime decision depends on them; document that choice.

Each stage has its own scoped fingerprint. Selection must not inspect or hash validation/OOS price content. A plan can commit future window boundaries without opening those data. Locked OOS mutation must leave every #005 output identity unchanged.

A hash detects change but does not preserve data. Retain the immutable authorized SQLite subset or equivalent canonical extract required for replay, plus a manifest. Otherwise label the run NOT_REPLAYABLE_FROM_RETAINED_DATA. Never copy sealed OOS prices into the replay artifact.

## 7. Historical observations and matching

Compute compute_discovery_observations once per session/universe/config/snapshot and reuse the PRE-budget output for all relevant variants and invalidation checks. Do not call the candidate selector, use REVIEW_PRIORITY, or let budget/ranking suppress historical signals.

Cache keys bind stage, session, universe/benchmark, snapshot, discovery code/config and PIT policy. Observation matching uses a dedicated EntryDefinition adapter with parity tests against the accepted vocabulary and AND/OR semantics. No fuzzy match or LLM inference.

A missing observation is UNKNOWN, not automatically a false entry or true invalidation. No entry is created from UNKNOWN. For an existing trade, inability to evaluate required invalidation inputs marks exit-path evaluation incomplete; a cap-only continuation may be reported separately as a diagnostic but cannot enter selected-strategy performance as if invalidation had been observed.

Preserve all valid SignalEvents. Apply overlap and boundary rules only to their per-variant dispositions.

## 8. Session timing and event order

Use an explicit exchange-session calendar, including holidays/early closes; dates are not calendar-day increments. Daily completed bars are available for close decisions only after that close. No intrabar path is inferred from OHLC.

Event order for each session:

1. Execute previously scheduled open exits.
2. Execute previous-close pending entries where permitted.
3. Track eligible intraday high/low for positions held during that session.
4. Execute pre-scheduled TIME_EXIT/MAX_HOLDING_CAP close exits.
5. Evaluate completed-close invalidation for positions still open.
6. Evaluate entry matches and assign dispositions for next-open entries.

Signals while a trade remains active at step 6 are suppressed, even if it has a pending next-open exit. Signals generated after a scheduled close exit may create a next-session entry. No deferred queue of previously suppressed signals.

Pending entries reserve the security/variant slot. Pending exits retain it until filled. No pyramiding within one security/variant. Other securities and other variants are independent simulations, without a shared capital budget.

## 9. Execution profile and compatibility with #004

Define immutable ExecutionSemanticsProfile v1:

    entry_fill = NEXT_SESSION_OPEN
    invalidation_detection = COMPLETED_BAR_CLOSE
    invalidation_fill = NEXT_SESSION_OPEN_AFTER_DETECTION
    time_exit_fill = SCHEDULED_HOLDING_BAR_CLOSE
    cap_fill = SCHEDULED_MAX_HOLDING_BAR_CLOSE
    cap_is_hard = true

The profile hash enters run and selection identities. It is common to all compared variants and cannot be tuned after results.

Confirmed compatibility rule: preserve the #004 frozen record verbatim, explicitly interpret its BAR_CLOSE field alongside its anti-lookahead docstring, and bind actual fill timing through this #005 profile. Do not state that the existing field universally means only detection. For TIME_EXIT/cap it denotes scheduled execution; reactive invalidation requires the deferred profile. Claude confirmed this interpretation against cfa0809. It requires no #004 patch. Preserve the original frozen fields and bind the explicit #005 profile in every run identity.

Holding bar 1 is the entry session. A TIME_EXIT of N exits at close(entry_session_index + N - 1).

For invalidation with cap M, choose the earliest executable event between a pending invalidation open and the pre-scheduled cap close. An invalidation first calculable at the cap close cannot extend the trade: the previously scheduled cap exit has already fired. If trading is halted or the required price is absent, record an unfilled/unevaluable trade; never fabricate a cap fill or silently call a late fill on time.

Worked examples (consecutive trading sessions):

| Signal | Entry | Rule/event | Expected exit |
|---|---|---|---|
| Monday close | Tuesday open | TIME_EXIT N=3 | Thursday close, TIME_EXIT |
| Monday close | Tuesday open | Invalidation Wednesday close, M=5 | Thursday open, SIGNAL_INVALIDATION |
| Monday close | Tuesday open | Invalidation Wednesday close, M=2 | Wednesday close, MAX_HOLDING_CAP |
| Monday close | Tuesday open | Invalidation Tuesday close, M=2 | Wednesday open, SIGNAL_INVALIDATION |
| Monday close | Tuesday open | M=1 | Tuesday close, MAX_HOLDING_CAP |

Scheduled close fills are a declared Daily execution approximation for an order planned in advance, not evidence of guaranteed live fill. No final-close-dependent change is allowed in that same scheduled order.

## 10. Invalidation matching

Use the existing #004 InvalidationCondition vocabulary. Lane trigger: observed label outside holds_labels. Multiple invalidation triggers combine with OR under this execution profile.

The reason-code docstring refers to a flip relative to entry. Confirmed V1 rule: capture the completed signal observation as the pre-entry reference; trigger when current presence differs from that reference AND current presence equals triggers_on_presence. A reason already in its triggering state at entry does not constitute a new flip. Never inspect entry-day close to initialize a reference for an entry filled that morning.

Claude confirmed the signal-observation reference and flip semantics in the completed review. Store this rule in ExecutionSemanticsProfile before any outcome run; do not switch to a level/presence predicate after observing results.

## 11. Missing sessions, prices and delisting

A session calendar is a separate, verified, versioned input, not inferred from benchmark bars or a vote/union of security series. Record its source, calendar identifier, version, covered dates, timezone, session open/close times (including holidays, early closes and exceptional closures), verification provenance and content hash. Include the authorized calendar artifact in the snapshot and its identity in ResearchPlan and run identity.

Compare benchmark/security bars against this calendar. An expected session without a bar is a data gap and remains a session for NEXT_SESSION_OPEN and holding counts, even if the date is absent from every series. An unexpected bar on a non-session is a data/calendar inconsistency to resolve, not authority to alter the schedule silently. Per-security gaps follow the explicit missing-entry/exit rules below; failure to establish calendar validity or coverage blocks the formal run.

Without a verified calendar covering the stage and required warm-up, fail closed with CALENDAR_UNVERIFIED or CALENDAR_COVERAGE_INCOMPLETE before formal execution. Synthetic infrastructure tests may declare their own explicit fixture calendar; they cannot label it a verified real-market calendar. Selecting and sourcing the production calendar is a run-readiness requirement, not an upstream #001–#004 patch.

The #003 benchmark-derived helper remains unchanged. No claim is made that #003 statistics are insensitive to missing sessions: horizons and temporal blocks can also be affected. Such a finding would be assessed separately and is not silently repaired inside #005.

NEXT_SESSION_OPEN means the immediately following scheduled market session. Do not skip an absent daily bar and pretend a later open was the intended next open. Missing entry open yields NO_ENTRY_BAR with no trade. Missing scheduled exit yields NO_EXIT_BAR on an executed but unevaluable trade. In V1 no resumed-trading fill model is inferred from sparse Daily data.

Report missing interior session bars separately; do not compress them out of holding duration. Reconcile the chosen session counting with #004 on clean histories. Missing data and trading suspensions are not zero returns.

Attach PIT listing status, reason and data-quality facts as diagnostics. A delisting is not assigned a terminal value of zero, last close, or any invented price. DATA_TERMINATION is a failure/status category, not an executable exit with a realized return.

Every signal disposition and executed trade remains in accounting. Performance explicitly uses evaluable trades only. Report no_exit_bar_count/ratio and other unevaluable reasons. Level 1 cannot support research-grade claims while delisting returns and universe survivorship are unresolved.

## 12. Split-safe price accounting

Never directly divide adjusted prices obtained at different as_of dates without proving that they share a split basis. Example: entry 100 before a 2:1 split and exit 50 after it is not a 50% loss.

Decision snapshots remain strictly session-PIT. For realized trade measurement after exit, request the entry-through-exit OHLC window at one common exit as_of and use the uniform split-adjusted basis supplied by #001. This measurement view cannot feed entry/exit decisions or retroactively alter signals. Snapshot identity includes facts used by this view.

Record both actual raw fill reference prices and common-basis measurement prices/factors. Gross price return uses the latter. OHLC ordering, forward/reverse splits and adjusted-volume semantics require independent fixture checks.

If a split or corporate action needed to interpret the trade cannot be reconciled at the allowed cutoff, return UNKNOWN_ADJUSTMENT_BASIS/unevaluable, not a large apparent profit or loss. #005 cannot repair a deficient upstream knowledge-time policy silently.

V1 return basis is SPLIT_ADJUSTED_PRICE_RETURN, not total return. Cash dividends, short dividend payments and non-split reorganizations are not silently assumed captured by adjusted OHLC. Report this limitation; unsupported complex events make the affected trade unevaluable. No total_return_adjusted_close input.

## 13. Directions, costs and fills

Replay only directions accepted in #004; never change a hypothesis direction. Long and short technical simulations use d=+1 and d=-1 respectively. Short output is explicitly hypothetical unless historical borrow availability/costs are supplied; no live-executability claim follows from a short technical backtest.

For positive common-basis reference entry P_e and exit P_x, adverse slippage fractions s_e/s_x:

    F_e = P_e * (1 + d*s_e)
    F_x = P_x * (1 - d*s_x)
    gross_price_return = d * (P_x/P_e - 1)
    net_return = d * (F_x-F_e)/F_e - c_e - c_x*(F_x/F_e) - borrow_drag

Here c_e/c_x are proportional commission rates on entry/exit notional; borrow_drag is normalized to initial executed notional. Restrict rates to finite nonnegative values producing positive fills. Costs are not deducted twice. No fixed-dollar/minimum-ticket commission model without explicit position sizing.

V1 borrow model: declared annual simple rate multiplied by elapsed calendar days/365 on initial notional; zero for long. Zero borrow is permitted only as an explicitly labeled technical assumption. Record rate and accrual convention. This simplified model excludes locate failures, recalls and variable daily borrow fees.

Base cost assumptions are mandatory frozen inputs. Sensitivity scenarios (e.g. 0/5/10 bps per side) use identical events/trades; they are not strategies or selection trials. Selection always uses the one frozen base scenario.

## 14. Overlap and fair comparison

Policy: ONE_ACTIVE_TRADE_PER_SECURITY_PER_VARIANT. Maintain raw family signal identity separately from per-variant execution. Different exits naturally create different future entry availability. Therefore full-path exit comparisons share the signal stream but not necessarily identical executed entries; do not claim perfectly paired experiments.

Report raw signal count, executed entries, active-trade suppression, boundary suppression and entry/data failures for every variant. Optional diagnostics on common executed signals must name their sample restriction and cannot replace the preregistered ranking sample.

## 15. Zone boundaries and eligibility window

Prevent performance-dependent truncation near zone ends. For each family compute H_family = maximum scheduled holding cap across ALL frozen variants. Admit a signal for potential trade creation only if its next-session entry plus H_family-1 scheduled sessions fits fully within the stage. This uses calendar metadata, not future prices or whether an early invalidation would have occurred.

Keep rejected signals as SUPPRESSED_STAGE_BOUNDARY. Use the same family cutoff for all variants, including selected-only validation, so selection does not alter observation support near a boundary. No forced stage-end exit and no borrowing prices from the next zone.

If unforeseen data loss prevents an admitted trade from closing, preserve it as unevaluable. A missing exit in the allowed stage does not authorize reading validation/OOS.

## 16. Folds and comparison

Replay Formation/Selection once as a chronological event stream. Optionally partition eligible signal dates into 2–3 frozen chronological bins for descriptive consistency diagnostics. Attribute each trade to the bin of its signal; a trade may exit in a later selection bin, never outside the selection stage. Do not double-count trades or reset positions at each bin.

These are SELECTION_DIAGNOSTIC_FOLDS, not independent walk-forward validation. No per-fold retuning or dynamic variant choice in V1. Overall ranking uses the pooled evaluable selection trades, not a newly chosen aggregation of fold scores. Fold inadequacy is reported rather than repaired by moving boundaries after outcomes.

## 17. Metrics

Per variant and applicable fold report:

- Total raw signals, each disposition count, executed/evaluable/unevaluable trades, evaluable ratio and missing-exit ratio.
- Gross and net mean/median trade return, win rate (net > 0), loss rate, zero-return count, average win/loss, profit factor where defined, holding-session/calendar-day distributions.
- Raw signals and executed trades per 20/60 scheduled sessions, median session gap, entries/exits per calendar month, completed round trips and suppression rate. Name each denominator; zero opportunities is not missing data.
- MAE/MFE and coverage/limitations. For long, MAE=min(0,min_price/P_e-1), MFE=max(0,max_price/P_e-1); for short, MAE=min(0,1-max_price/P_e), MFE=max(0,1-min_price/P_e). These are cost-free price excursions on a common split basis.

MAE/MFE includes entry-day full range for open entries and exit-day full range only for close exits. For open exits include the exit open and prior held sessions, NEVER that exit day's subsequent high/low. Include opening gaps. Missing interior range makes excursion metrics unavailable even if endpoint return is measurable; report coverage separately.

No portfolio CAGR, portfolio Sharpe or portfolio maximum drawdown without an explicit capital/allocation model. Do not compound overlapping independent trade returns into a fictitious equity curve. A per-trade peak-to-trough price-path diagnostic may be added only with a clearly defined sampling convention and distinct label; it is not a selection gate. Null/undefined metrics are serialized explicitly, not as infinity or NaN.

No formal statistical inference is required in V1. Any later time-block bootstrap is an optional labeled approximation, with no eligibility/deployment role and no claim of complete holding-period dependence capture.

## 18. Formal variant selection

Freeze SelectionRule before any #005 outcome replay:

    minimum_executed_trades: required positive integer
    minimum_evaluable_trades: required positive integer
    minimum_evaluable_ratio: required value in (0,1]
    ranking_metric: MEDIAN_NET_RETURN
    minimum_selection_metric: 0
    threshold_operator: STRICTLY_GREATER
    tie_break: LEXICOGRAPHIC_STRATEGY_VARIANT_ID

These support thresholds are design inputs, not knobs to fit after seeing returns. Numeric values are intentionally not asserted to be statistically sufficient by this document. Missing values prevent a formal selection run; synthetic integration tests supply explicit fixture values.

Process: list every frozen variant; evaluate technical/data eligibility; calculate the single base-cost ranking metric where eligible; retain variants with median > 0; select highest median; break exact numeric ties by ID. Use unrounded stored numbers, not report rounding or a tunable epsilon. If none qualifies: NO_VARIANT_SELECTED with reasons. No hidden Sharpe/drawdown/win-rate tie-break.

Persist the complete considered set, counts, gate results, values and selected ID. Comparison alone creates no winner and no selection record. At most one selection per hypothesis/plan; changed rules produce a new research attempt with lineage, never overwrite.

## 19. Cohort and multiple-attempt accounting

ResearchPlan fixes the full HypothesisUniverse/cohort and links all variants before results. Reconcile every planned item to completed/failed/rejected/unselected output. Report total families, variants, runs, retries and research revisions.

V1 selects within each family, not a top-N portfolio across families. Any later choice among many family winners is additional selection and needs its own declared rule and untouched validation. Reporting all trials improves transparency but does not mathematically remove multiple-testing bias.

## 20. Development Validation

Accept only the frozen selection record and its approved plan. Confirm exact selected definition, profile, discovery config, costs and provenance. Bind the stage's own newly opened snapshot without changing the selection snapshot or result.

Persist a consumption event before first outcome access. After disclosure, any new strategy, threshold or exit inspired by the result makes that interval development data for the new attempt. Reruns on identical input are idempotent technical reproductions, not additional independent validation; corrected-data reruns remain linked and disclosed.

Use the same execution/data rules and support thresholds for adequacy reporting. States: NOT_RUN_NO_SELECTION, INSUFFICIENT_DATA, or EVALUATED. EVALUATED is not an automatic profitability/deployment pass. Report negative results without substituting a second-best selection candidate.

#005 does not unlock OOS, issue a live approval or tune a deployment gate. A future human-reviewed Deployment Report may consume these artifacts along with research-grade data evidence.

## 21. Identity, persistence and reproducibility

Backtest semantic identity includes stage, full strategy hashes, evidence-bundle hash, cohort and ResearchPlan hash, actual code/engine and config hashes, scoped data digest, calendar, execution semantics, costs, return basis and deterministic seeds if used. Exclude created_at and wall-clock performance from semantic identity.

Identical semantic inputs produce identical event/trade/report content and IDs. Different audit timestamps can identify separate execution attempts while referring to the same semantic run. Stable ordering must not depend on sets, filesystem order or query insertion order.

Use a #005-owned append-only store (SQLite is sufficient) for plans, runs, selections and validation-consumption records. Atomically persist a completed run and references to its artifacts; failed attempts retain failure status but cannot appear as completed selections. Same-ID/same-content writes are idempotent; same-ID/different-content writes fail. Never mutate #004 records.

Archive input registries/configs and authorized replay snapshots alongside reports. No credentials in source, prompts or artifacts.

## 22. Proposed package boundary

    src/backtest/
      models/           # immutable entities and enums
      config/           # plan, execution profile and cost validation
      provenance/       # evidence linkage, existing hash recipe adapter
      data/             # bounded PIT facade, snapshots, cache, calendar
      signals/          # entry and invalidation matching
      execution/        # state machine, fills, cap precedence, costs
      trades/           # accounting, common-basis measurements
      metrics/          # descriptive returns, excursions, opportunity
      comparison/       # all variants, chronological diagnostics
      selection/        # preregistered rule and frozen selection records
      validation/       # selected-only development validation, OOS guards
      registry/         # append-only #005 persistence
      reports/          # machine-readable JSON and readable Markdown
      engine.py         # separate comparison/selection/validation entrypoints

Dependencies may point from #005 to accepted upstream public interfaces. No discovery/evaluation/hypothesis import of backtest. No LLM SDK, broker SDK or network fetch in the deterministic core. Data ingestion is a separate operation before snapshotting.

## 23. Required acceptance tests

Use small synthetic fixtures with independently computed expected outcomes. No artificial test-count target.

| Family | Required invariant |
|---|---|
| Provenance | Field/ID mismatch fails; exact eight-field recipe succeeds; linkage, mode and benchmark mismatches fail; hash consistency is never reported as authenticity |
| Date safety | Missing/reversed evidence dates fail; outcome boundary touching validation fails; warm-up cannot create trades |
| Exposure | Known prior validation disclosure prevents UNSEEN status; all cohort lineage is accounted for |
| Registry | Missing/extra/duplicate variants fail; tampered hashes fail; no upstream writes |
| Calendar | A common missing date across all price series remains a session under the verified calendar; invalid/unverified coverage blocks formal runs; synthetic fixtures are explicitly labeled; calendar changes alter identity |
| Entry | Close signal fills next scheduled open; missing open is not skipped |
| Time exit | Entry bar=1; N=1 and N=3 examples have exact close dates |
| Invalidation | Wednesday close detection cannot use Wednesday close fill; state/reason semantics and UNKNOWN tested |
| Cap precedence | Cap-close invalidation exits at cap close; previous-close invalidation may exit at cap-session open |
| Split basis | Forward/reverse split spanning entry/exit creates correct neutral return absent price movement; mixed-as_of ratio rejected |
| PIT | Future observations/actions cannot alter earlier decisions; unsupported basis is explicit, not a false return |
| Missing data | Halts/interior gaps/no exit preserve trade and missingness accounting; no invented liquidation |
| Costs | Hand-computed long and short cases; adverse slippage both sides; commission and borrow applied exactly once |
| MAE/MFE | Open-exit day later high/low excluded; close-exit day included; gaps and shorts correct |
| Overlap | Every signal retained; active trade suppresses creation only; pending-exit suppression and post-close reentry deterministic |
| Boundary | Common family cutoff does not depend on realized invalidation; no trade crosses stage |
| Selection | Single metric, exact deterministic tie, strict zero threshold, null metrics and no-selection case |
| Validation | Only selected variant evaluated; rejected candidates cannot be replayed; consumption recorded before data access |
| Isolation | Mutating validation data cannot alter selection; mutating OOS cannot alter any #005 output or hash; access spy forbids OOS queries |
| Snapshot | One relevant fact correction changes hash; input order does not; concurrent ingestion cannot mix states |
| Determinism | Same snapshot/definitions/config reproduce events and semantic IDs; timestamp-only changes do not |
| Persistence | Atomic commit/rollback, failure retention, idempotence and conflicting same-ID rejection |
| Architecture | AST dependency guards, zero LLM/broker calls, no total-return substitution |

Run the accepted upstream suite unchanged after implementation. Report actual results and any pre-existing skip; do not claim the reported 282 passed/1 skipped baseline was rerun by GPT in drafting this document.

## 24. Consensus closure, approval and implementation sequence

Technical review is complete. Claude confirmed cfa0809 with no baseline drift, accepted the six priority areas, reviewed the remaining sections, and confirmed the final independent-calendar and hash-consistency corrections. No known upstream implementation blocker remains. This closes design review; it does not claim code exists or tests have run.

Operator approval is still pending. Radu's approval of Spec #005 v1.0 authorizes Claude to implement this specification, starting with Batch 1 below. Approval is required by the agreed project workflow, not by a tool or skill. No further whole-document review is requested.

Implementation batches:

1. Typed entities, config validation, evidence-provenance preflight, calendar-input contract and synthetic fixtures. Acceptance: exact legacy hash/linkage/mode/benchmark guards, valid fixture calendar and fail-closed calendar coverage. Return delta bundle and test report.
2. Consistent scoped snapshots, canonical hashing, bounded PIT access and historical observation cache.
3. Event engine, invalidation/cap ordering, overlap, missingness, split-safe measurement and costs.
4. Metrics, complete variant comparison, pooled selection and append-only persistence.
5. Selected-only Development Validation, consumption records, reports and integration/isolation tests.

Return a coherent delta bundle, actual test results and limitations at each batch review. Do not silently patch #001–#004. A newly discovered concrete incompatibility must be reported as an IMPLEMENTATION BLOCKER with the minimal proposed correction.

Approval permits implementation and synthetic testing. It does not authorize opening real validation outcomes before the ResearchPlan and selection are frozen, and never authorizes Locked OOS access or broker execution.

Actual study dates, support thresholds, base costs and a verified production calendar must be supplied and frozen before a formal run. Their absence blocks that run, not implementation with explicit synthetic fixtures. Keep credentials local and out of every artifact.

## 25. Source basis

- User-supplied Claude review, 2026-09-26: current baseline inspection, EvaluationRunRegistry handoff and invalidation proposal.
- spec004_review_bundle.md: ExitHypothesis/InvalidationCondition contracts, fixed BAR_CLOSE, parent/variant identity and evidence provenance.
- patch004A_delta_bundle.md: corrected holding-bar/date convention and explicit parameter_source.
- patch004B_delta_bundle.md: latest supplied #004 integrity patch; no replacement exit-timing contract identified in the targeted inspection.
- spec003_review_bundle.md and patches A/B: registry fields, build_run_id call recipe and development-boundary regression references.

The cap correction follows the explicit #004 clause: invalidation OR the close of max_holding_bars, whichever happens first. Subsequent full-review confirmations supplied by Radu closed BAR_CLOSE compatibility, signal-reference invalidation, the eight-field recipe and remaining sections. The final calendar correction rejects inference of market closures from missing price data. These policies have technical consensus; operator approval and implementation are distinct subsequent events.
