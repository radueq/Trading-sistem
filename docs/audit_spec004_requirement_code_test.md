# Spec #004 -- Requirement -> Code -> Test Correspondence Matrix

**Status: background-agent output, partially spot-checked by Claude, NOT
independently verified by Radu.** Produced by a Claude subagent reading
`docs/Spec_004_Hypothesis_Generation_v1.0.md` section-by-section (all 111
sections, both original messages) against `src/hypothesis/` and
`tests/spec004/test_01_*.py`-`test_66_*.py` (in-#004-scope; tests 67-73
are PATCH #004-C, already-documented out-of-original-scope, and were
checked only for being correctly additive, not mapped to a section).

**Revision note (2026-10-03), the main correction on this document:**
the original version tagged the Locked-OOS/`evaluation_mode` finding
"HIGH PRIORITY" in a way that read as an existing, demonstrated
contamination. **It is not.** It is a real structural gap (no
`evaluation_mode` field is preserved on the frozen record, and no check
enforces the mode is `FORMAL_DEVELOPMENT`) whose failure scenario is a
hypothetical future caller, not something that has happened or can be
reproduced against the current test suite today. Retagged
**SUSPECTED ISSUE -- VERIFICATION PENDING**, per the classification key
in `docs/contract_index.md`: a real red flag worth a targeted check, not
a proven, active defect. The `research_mode` gate finding (Finding 2) is
different in kind -- GPT verified this one too, alongside the Discovery
status-discard and `bucket_key` findings in `docs/audit_spec002_
requirement_code_test.md`, as a confirmed structural gap; Radu's own
verdict on its contractual significance remains separate in all three
cases. It keeps the same SUSPECTED ISSUE tag but flagged as a
higher-priority item within that category, pending that verdict, not
pre-judged as settled.

**Claude's own spot-check on the agent's single highest-priority
claim:** grep for `research_mode` across all of `src/hypothesis/` returns
exactly 2 hits -- the field's own definition (`models/entities.py:406`)
and one copy-through in `create_new_version`'s override mechanism
(`registry/hypotheses.py:382`). **Zero occurrences in
`registry/preregistration.py` or `validation/rules.py`** -- confirming
the agent's claim that `research_mode` (EXPLORATORY_HYPOTHESIS vs
PREREGISTERED_STRATEGY) is never checked anywhere at the preregistration
gate.

This held up. The rest of the table was not independently re-verified
line-by-line by Claude.

---

## Section-by-section table

| # | Requirement (paraphrase) | Code location | Test location | Status |
|---|---|---|---|---|
| 1 | Purpose: turn #003 evidence into a testable, frozen hypothesis; not a profitability test | Whole-package architecture | N/A (narrative) | N/A |
| 2 | Outcome-aware for hypothesis formation but not a backtester; never raw returns/backtest/Locked OOS/indicator optimization | `evidence/packet.py:31` (imports only `evaluation.models.entities`) | `test_36`, `test_38` | MET |
| 3 | A Development-derived hypothesis must be explicitly marked as such | `EvidenceProvenance` carries run/config lineage but no `evaluation_mode` field | No test asserts a DEVELOPMENT-DERIVED tag exists | **SUSPECTED ISSUE -- VERIFICATION PENDING** -- see Finding 1 (not a demonstrated gap: no failure has been reproduced against the current suite) |
| 4 | Locked OOS completely inaccessible | Import-boundary only; no allowlist restricting mode to FORMAL_DEVELOPMENT | `test_36` (import boundary only) | **SUSPECTED ISSUE -- VERIFICATION PENDING** -- see Finding 1, same correction |
| 5 | No direct Price History/PIT access needed | `evidence/packet.py:31` | `test_36` | MET |
| 6 | Worked example of what a Hypothesis is | `docs/spec004_examples.md` Example A | N/A | N/A |
| 7 | `StrategyHypothesis` entity, minimum fields | `models/entities.py:381-430` + `433-447` (`StrategyVariant`) -- spec's single entity split into family+variant per Radu's §110-D | `test_03`, `test_41` | MET (documented restructuring) |
| 8 | Direction explicit; forbidden `if mean>0->LONG` derivation | `Direction` enum; validator only accepts caller-declared direction | `test_04` | MET |
| 9 | No "flip until profitable"; LONG/SHORT are distinct, both-registrable | `hypothesis_fingerprint()` includes direction | `test_05` | MET |
| 10 | Direction provenance audit-only, never used for scoring | `DirectionBasis` enum, excluded from fingerprint (explicit comment) | No scoring code exists at all -- vacuously true | MET |
| 11 | Entry only from approved #002 fields; unapproved indicator forbidden | `validator.py:52-84` | `test_06`, `test_07` | MET |
| 12 | Entry clause budget (max 3 + 1 optional) | `config/hypothesis.yaml:50-52`; `validator.py:96-110` | `test_08` | MET |
| 13 | Entry conditions auditable (lane=x,label=y / reason_code=z), never prose | `models/entities.py:169-185` (structural -- no free-text type) | Implied by `test_06`/`test_07` | MET |
| 14 | Entry timing preregistered: `signal_time=CLOSE(t)` | `ENTRY_EXECUTION_POLICY="NEXT_BAR_OPEN"` constant | `test_09` | MET |
| 15 | Why fix entry timing now | Single allowed value enforced structurally | `test_09` | MET |
| 16 | Primary V1 entry execution proposal | Superseded by Radu's §110-A approval | Same as §14 | N/A (resolved by §110) |
| 17 | Horizon candidates from #003; never auto-select max(mean_return) | `HorizonCandidateSet`; no `selected_horizon`/optimal field anywhere | `test_12` | MET |
| 18 | `HorizonCandidateSet` example structure | `models/entities.py:204-222`; `config/hypothesis.yaml:19-21` | `test_10`, `test_11` | MET |
| 19 | Don't declare an "optimal" horizon; keep the whole considered family | `materialize_variants()` expands every candidate eagerly | `test_12` (decay peak at 3, all 5 still reported) | MET |
| 20 | Horizon provenance kept; no retroactive rewrite | `selection_basis`/`parameter_source` fields; no `selected_horizon` field exists at all | `test_59` | MET |
| 21 | Exit central principle: hypotheses, not an optimized exit | `ExitHypothesis`; TIME_EXIT auto-derived, never "chosen" | `test_13` | MET |
| 22 | Exit taxonomy V1: TIME_EXIT mandatory, SIGNAL_INVALIDATION, RISK_EXIT not optimized | `ExitFamily` enum; risk_exit gate in config + validator | `test_13`, `test_14`, `test_16` | MET (original #004-era restriction correctly enforced) |
| 23 | Exit V1 excludes MAE-stop/MFE-target/ATR-grid/optimized-TP/trailing/Kelly | AST field-name scan, only `stop_loss`/`partial_profit` on the later `STOP_MANAGED_INVALIDATION` family exempted | `test_17` | MET (exemption is the already-documented PATCH #004-C extension) |
| 24 | TIME_EXIT is mandatory baseline | `validate_for_preregistration()` requires >=1 TIME_EXIT variant | Implied by `test_13`, exercised via `test_41` | MET |
| 25 | SIGNAL_INVALIDATION only with direct semantic justification | Vocabulary-restricted to approved lane/reason-code conditions | `test_14` | MET ("semantic justification" itself is a human judgment call, not code-checkable) |
| 26 | `ExitHypothesis` entity, minimum fields | `models/entities.py:275-327` | `test_13`, `test_14` | MET |
| 27 | Exit parameter source labeled; `BACKTEST_SELECTED` must not exist yet | `ParameterSource` enum -- no such member | `test_59` | MET |
| 28 | Evidence-derived exit parameters written explicitly, never masked as prior | `selection_basis`+`parameter_source` propagate through `materialize_variants()` | `test_59` | MET |
| 29 | Hypothesis Mode: EXPLORATORY vs PREREGISTERED | `HypothesisResearchMode` enum defined | Never checked by `preregister_hypothesis()`/`validate_for_preregistration()` -- Claude-verified, zero occurrences in either file | **SUSPECTED ISSUE -- VERIFICATION PENDING; GPT verified the underlying fact, Radu's own verdict remains separate** -- see Finding 2 |
| 30 | Lifecycle DRAFT->REVIEWED->PREREGISTERED->HANDOFF; no edit-after-backtest | `HypothesisStatus` enum; `register()`/`_force_register()` | `test_24`, `test_53` | MET |
| 31 | Post-preregistration modification creates a new id, never overwrites | `create_new_version()` | `test_25` | MET |
| 32 | Hypothesis Registry, minimum fields | `models/entities.py:381-430` (field consolidation vs. spec's separate parent/supersedes pair) | `test_25` | MET (minor semantically-equivalent consolidation) |
| 33 | Evidence provenance obligatory | `EvidenceProvenance` | `test_01` | MET |
| 34 | Config change -> new hypothesis (H2), never silent reuse | `hypothesis_fingerprint()` includes every provenance field | `test_23` | MET |
| 35 | AI Agents produce proposals, never a final hypothesis directly | `HypothesisProposal` structurally distinct; only `preregister_hypothesis()` produces the latter | `test_53` (register() refuses hand-built PREREGISTERED) | MET |
| 36 | No API calls in core Registry | `proposals/normalize.py` docstring; zero LLM imports | `test_39` | MET |
| 37 | Why separate AI from core | Architecture-level rationale | N/A | N/A |
| 38 | Token-economy: LLM never gets raw OHLCV/thousands of observations | `EvidencePacket` flat/primitive fields only | `test_02` | MET |
| 39 | `EvidencePacket` entity, minimum fields | `models/entities.py:603-647` | `test_01`, `test_57` | MET |
| 40 | Token target ~1-3KB per candidate | Flat-field design supports it | No test measures actual serialized size | **MET (design)** [TEST-COVERAGE GAP: size is a numeric measurement, not confirmable by inspection alone] |
| 41 | Agent roles V1 -- conceptual, not real API agents | `agent_id` is a free-form string; no role enum | `docs/spec004_agent_interface.md` explicitly documents this | **FUTURE / PROCEDURAL REQUIREMENT** -- correctly left as process convention |
| 42 | Independent first-pass reasoning | No sequencing/visibility-gating mechanism exists | Not code-testable -- pure human orchestration | **FUTURE / PROCEDURAL REQUIREMENT** |
| 43 | Consensus is not a vote for truth; independent perspectives reaching the same structure | `compute_consensus()` classifies shape only, never correctness | `test_32` | MET |
| 44 | `AgentReview` entity | `models/entities.py:527-538` | `test_29` | MET |
| 45 | `ConsensusRecord` entity | `models/entities.py:555-564` | `test_32` | MET |
| 46 | Human authority final; AI consensus alone can't auto-preregister | `can_preregister()` | `test_30`, `test_31` | MET on the core rule. **SUSPECTED ISSUE -- VERIFICATION PENDING**: whether a human APPROVE can override a BLOCKED (all-objecting) consensus is genuinely unresolved by the spec text and untested for that exact combination -- see Finding 5 |
| 47 | Statistical-skeptic checklist (support/concentration/FDR/horizon/regime/scarcity) | `objections` is free text; no structured checklist enforced | Nothing enforces the checklist was actually applied | **FUTURE / PROCEDURAL REQUIREMENT** -- whether the checklist was actually applied is a human-judgment question code cannot verify |
| 48 | `HypothesisProposal` entity, minimum fields | `models/entities.py:491-524` | `test_33` | MET |
| 49 | Rationale is interpretation, not statistics; separated from Evidence | `facts_from_evidence`/`interpretation` separate fields | `test_33` | MET |
| 50 | Output distinguishes FACTS from INTERPRETATION | Same as §49 | `test_33` | MET |
| 51 | Hypothesis Budget protects against combinatorial explosion | `config/hypothesis.yaml:54-57` | `test_27` | MET |
| 52 | Level-1 budget values | `config/hypothesis.yaml:50-57`; `validator.py:256-270` | `test_27`, `test_08` | MET on the budget mechanism. **SUSPECTED ISSUE -- VERIFICATION PENDING**: `max_exit_families_per_hypothesis` counts proposal entries, not distinct family types -- confirmed code behavior, contractual severity open -- see Finding 10 |
| 53 | Budget rejection doesn't hide hypotheses | `mark_proposal_rejected()` never deletes | `test_28` | MET |
| 54 | `HypothesisUniverse` entity for one research cycle | `models/entities.py:688-697`; `build_hypothesis_universe()` (generic accounting -- collects existing proposals/rejected/preregistered into one object) | No test file exercises this function at all | **MET (by inspection: generic aggregation, no complex logic)** [TEST-COVERAGE GAP] |
| 55 | Why keep rejected proposals | Same evidence as §53 | `test_26` | MET |
| 56 | Deterministic Research Queue | `evidence/queue.py:1-33` | `test_50` | MET |
| 57 | Queue can filter on quality signals, careful about outcome selection | `eligibility_basis()` (data-quality only) | `test_50` | MET |
| 58 | Outcome-aware prioritization allowed but must be logged as such | `PRIORITY_BASIS_OUTCOME_AWARE` | `test_51` | MET |
| 59 | Separate ELIGIBILITY (quality) from PRIORITY (can use evidence strength) | `evidence/queue.py:43-73` vs `76-141` | `test_50`, `test_51` | MET |
| 60 | No HypothesisScore composite | AST identifier scan | `test_35` | MET -- core-discipline check, no violation found, confirmed absent |
| 61 | Queue ordering transparent, labeled, never "Alpha Score" | `compute_review_priority()` always paired with `priority_basis` | `test_51` | MET |
| 62 | Review priority must never enter backtest/trading logic | No shared field names between the two entities | `test_34` | MET |
| 63 | `StrategyDefinition` entity | `models/entities.py:450-484`; `strategy_registry.py:26-82` | `test_41` | MET |
| 64 | Universe Policy uses Discovery eligibility mechanism, not a static list | `UNIVERSE_POLICY="DISCOVERY_ELIGIBLE_UNIVERSE"` constant; no static-list field exists anywhere on `StrategyDefinition` | No dedicated regression test beyond one line | **MET (by inspection: no static-list field exists to misuse)** [TEST-COVERAGE GAP] |
| 65 | No ticker cherry-picking after seeing outcomes | No field capable of expressing a ticker exclusion list | None dedicated | **MET (by inspection)** [TEST-COVERAGE GAP -- see Finding 9] |
| 66 | Sector restrictions must be preregistered | Same structural absence | None | **MET (by inspection)** [TEST-COVERAGE GAP -- see Finding 9] |
| 67 | Market regime filters must be preregistered | Same structural absence | None | **MET (by inspection)** [TEST-COVERAGE GAP -- see Finding 9] |
| 68 | Daily->4H readiness: timeframe/horizon_bars, never holding_days | Forbidden-token scan on entity fields | `test_40` | MET |
| 69 | Multi-timeframe future needs no registry redesign | Generic `timeframe: str` field | Implied by §68's test | MET (forward-looking, reasonably supported) |
| 70 | Each condition carries its own source_feature/engine/version | No per-condition provenance fields exist -- only whole-hypothesis provenance | `test_41`'s docstring cites this but assertions never check it | **SUSPECTED ISSUE -- VERIFICATION PENDING** -- see Finding 3: absence confirmed, contractual necessity for Radu to judge |
| 71 | Deterministic validation before PREREGISTERED (full checklist) | Split across `validator.py:227-279` and `rules.py:137-257` | `test_04,07,09,10,15,18-20,41-43` | MET (two-layer implementation) |
| 72 | Outcome contamination forbidden in entry/exit conditions | `FORBIDDEN_OUTCOME_FIELD_NAMES` + scan function; also the Discovery-lane allowlist | `test_18,19,20` | MET -- core-discipline check, no violation found, enforced at both layers |
| 73 | Forbidden example must be structurally inexpressible | Same mechanism as §72 | `test_19` | MET |
| 74 | (duplicate numbering in source -- see §73) | -- | -- | -- |
| 75 | Exit derivation process (decay->region->bounded set->freeze->#005 tests all) | `materialize_variants()` | `test_13`, `test_47` | MET |
| 76 | Full worked example | `docs/spec004_examples.md` Example A/C | `test_13,14,46` | MET |
| 77 | #005 must know all candidates, none invented after backtest | `variant_ids` populated eagerly, checked against materialized variants | `test_47` | MET (#005's own future behavior is out of #004's testable scope) |
| 78 | Overfitting avoidance via inner/outer split (detail deferred to #005) | N/A -- explicitly deferred | N/A | N/A |
| 79 | Risk stop not chosen now; insufficient MAE/MFE research | `risk_exit.enabled: false` | `test_16` | MET (original #004-era restriction correctly implemented) |
| 80 | TIME_EXIT sufficient for first testable strategy | Always auto-derived and mandatory | `test_13` | MET |
| 81 | Don't complicate exit now (decomposition principle) | Architectural principle | N/A | N/A |
| 82 | Minimum family: Entry+TimeExit control, Entry+SignalInvalidation variant | `materialize_variants()` always creates both | `test_13`, `test_14` | MET |
| 83 | Counterfactual/Null tagging | `VariantTag` enum | `test_60` | MET |
| 84 | Untested parameter -> `FUTURE_RESEARCH_NOTE`, not silently asserted | `FutureResearchNote` dataclass exists but is never constructed, validated, or wired into any gate | No test references it at all | **SUSPECTED ISSUE -- VERIFICATION PENDING** -- see Finding 6: dead code, confirmed by inspection; whether this leaves SS84 genuinely unmet or just not-yet-exercised is Radu's call |
| 85 | `FutureResearchNote` must never affect `StrategyHypothesis` | Same as §84 | None | MET, but only because the type is unused rather than because a gate actively prevents misuse -- same tag as §84 |
| 86 | Reproducibility: same inputs reconstruct the same hypothesis | `hypothesis_fingerprint()` is pure | `test_44` | MET |
| 87 | Agent-output reproducibility via structured proposal, not regenerated LLM text | `HypothesisProvenance` stores structured references only | `test_03` | MET |
| 88 | No LLM in the executable trading path | Zero LLM imports anywhere | `test_39` | MET |
| 89 | Live strategy deterministic: same inputs -> same signal | `StrategyDefinition` has no agent/LLM-callable field | Same as §88 | MET |
| 90 | `hypothesis_generation` config block | `config/hypothesis.yaml:1-67` | `test_09,10,11,16` | MET |
| 91 | Package structure; no broker/backtester | Matches, plus legitimate additions | `test_37,38` | MET |
| 92 | Deterministic core, 0 LLM tokens | Same as §88 | `test_39` | MET |
| 93 | LLM adapters explicitly NOT implemented yet | No `agents/` directory exists | `test_39` | MET |
| 94 | Why delay agent APIs | Rationale | N/A | N/A |
| 95 | Deliverables: 6 named docs | All 6 present | N/A | MET |
| 96 | 4 controlled examples | `docs/spec004_examples.md` (real pipeline run) | Generated by a report script | MET |
| 97 | 44 required tests | `test_01`-`test_44` all present | Same | MET |
| 98 | Hard FAIL conditions (14 named) | Distributed across `test_05,12,16,24,26,31,35,36,37,38,53` | Same | MET, except Locked-OOS access -- see Finding 1's corrected, non-demonstrated framing |
| 99 | Out-of-scope list | `NOT_DEFINED_YET` placeholders; no broker/backtest imports | `test_37,38` | MET |
| 100 | What #004 produces at the end (not a profitability claim) | Registry accounting | N/A | N/A |
| 101 | Example final `StrategyHypothesis` | `docs/spec004_examples.md` | N/A | N/A |
| 102 | Opportunity density in EvidencePacket, frequency not falsified | `primary_episodes_per_20/60_sessions` fields | `test_01` (indirect) | MET |
| 103 | Frequency reported separately from statistical quality/profitability | Same fields, different name | None dedicated | MET (functionally equivalent naming) |
| 104 | Prefer StrategyFamily output when variants exist | `StrategyHypothesis`(family)+`StrategyVariant`(exit) split | `test_52` | MET (naming diverges from Radu's own §110-D text -- see Finding 12, a textual note, not a functional gap) |
| 105 | `StrategyFamily` entity, minimum fields | Same split as above | `test_52` | MET (same naming note) |
| 106 | No Cartesian explosion; configurable variant budget | `max_variants_per_family: 6` | Report-script Example D | MET |
| 107 | Over-budget -> explicit error, never silent truncation | `ComplexityStatus` enum; full error list returned | `test_08`, Example D | MET |
| 108 | #005-accounting export: all proposals/variants/rejected/preregistered | `HypothesisUniverse` has no `all_variants` field (a separate `registry.all_variants()` method exists but isn't wired in) | No test (same untested status as §54) | `HypothesisUniverse` itself: **MET (by inspection)** [TEST-COVERAGE GAP, same as §54]. Missing `all_variants` field: **SUSPECTED ISSUE -- VERIFICATION PENDING** -- see Finding 7 |
| 109 | Guiding principle: few interpretable hypotheses > mass search | Architectural consequence of budget+registry design | N/A | N/A |
| 110 | Radu's approved answers to §110 A-H | Mapped across `models/entities.py`, `validator.py`, `hypotheses.py`, `evidence/packet.py`, `evidence/queue.py` | `test_45-52` | MET |
| 111 | Final 16-point confirmation checklist | Recap of already-covered points | Same tests as those points | N/A (restates already-assessed items) |

---

## Top findings, with concrete failure scenarios

1. **[SUSPECTED ISSUE -- VERIFICATION PENDING, corrected 2026-10-03 from "HIGH PRIORITY"]** Locked OOS / evaluation-mode boundary is import-level only, not value-level (SS3-4, SS98). `build_evidence_packet()` checks internal consistency of supplied `evaluation_mode` values but never checks the mode IS `FORMAL_DEVELOPMENT`, and `EvidencePacket`/`EvidenceProvenance` have no `evaluation_mode` field at all. **This is a future possibility, not a demonstrated existing contamination** -- per Radu's own correction: the failure scenario described ("if a future caller passed Locked-OOS-derived evidence in...") is hypothetical, not something reproduced against the current test suite or known to have occurred. Worth a targeted check, not yet proven either way.
2. **[SUSPECTED ISSUE -- VERIFICATION PENDING; GPT verified the underlying fact, Radu's own verdict remains separate]** `research_mode` (SS29) is never enforced at the preregistration gate (Claude-verified: zero occurrences in `registry/preregistration.py` or `validation/rules.py`). A `StrategyHypothesis` explicitly tagged `EXPLORATORY_HYPOTHESIS` ("cannot enter formal backtest validation directly") passes every other check and can still reach `PREREGISTERED` -- a real, confirmed structural gap, alongside two Spec #002 findings GPT verified the same way; the contractual verdict on all three is Radu's, not yet given.
3. **[SUSPECTED ISSUE -- VERIFICATION PENDING]** Per-condition provenance (SS70) is missing -- only whole-hypothesis provenance exists, confirmed by inspection. An entry mixing conditions validated under two different Discovery config versions would be indistinguishable from one where both share the same version. Whether SS70 requires this granularity or whole-hypothesis provenance suffices is Radu's contractual reading.
4. **[FUTURE / PROCEDURAL REQUIREMENT]** "Independent first-pass reasoning" and the statistical-skeptic checklist (SS41-43,47) are process requirements code cannot express, honestly documented as unenforced.
5. **[SUSPECTED ISSUE -- VERIFICATION PENDING]** Whether a human APPROVE can override a BLOCKED (all-objecting) consensus (SS43-46) is genuinely unresolved by the spec text; current code takes the permissive reading, untested for this exact combination.
6. **[SUSPECTED ISSUE -- VERIFICATION PENDING]** `FutureResearchNote` (SS84-85) is dead code -- defined but never constructed, validated, or referenced anywhere, confirmed by inspection. Whether this leaves SS84 genuinely unmet or is acceptable unused scaffolding at this stage is Radu's call.
7. **[TEST-COVERAGE GAP (the entity) + SUSPECTED ISSUE -- VERIFICATION PENDING (the missing field)]** `HypothesisUniverse` (SS54, SS108) is a simple accounting object, reasonable by inspection, but has zero test coverage; separately, it omits "all variants considered" as a field, though the data exists via a different, unwired method.
8. **[TEST-COVERAGE GAP]** No test verifies the ~1-3KB EvidencePacket token-budget target (SS40) -- a size measurement, not confirmable by reading the code.
9. **[TEST-COVERAGE GAP]** Ticker/sector/regime-exclusion prohibitions (SS64-67) are enforced only by field absence -- confirmed correct today by inspection (no such field exists to misuse), but with no regression test guarding against a future field being added.
10. **[SUSPECTED ISSUE -- VERIFICATION PENDING]** `max_exit_families_per_hypothesis` (SS52) is enforced as a variant count, not a family-type count -- a confirmed code behavior; whether this is stricter than the config's actual intent in a way that matters is Radu's call.
11. **[SUSPECTED ISSUE -- VERIFICATION PENDING]** `hypothesis_config_version` is never cross-checked against the config actually used at the gate -- confirmed absence of a check, contractual significance open.
12. **[Textual note, not a functional gap]** The implementation never uses the name "StrategyFamily," even though Radu's own §110-D approval text literally uses that name for the family-level entity (it's called `StrategyHypothesis` instead). Documented and justified at the time, but a literal-text deviation from the final approval worth Radu's explicit sign-off, given he called this design one of the most important decisions.
