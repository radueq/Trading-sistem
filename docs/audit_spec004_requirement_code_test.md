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

**Status update (2026-10-04): Claude's own fresh, high-effort
independent re-verification pass**, requested by Radu specifically to
finish before the joint F1-F6 remediation design for Spec #003 (to
surface cross-module dependencies first). **This is NOT yet a GPT
round** -- unlike Specs #001/#002/#003, which have each had a full GPT
pass reconciled by Claude, #004 has not yet been independently audited
by GPT; this round is Claude's own re-verification against the real
source on commit `fa8f257` (branch `claude/spec004-audit`), going
further than the original background-agent pass by driving the REAL
`preregister_hypothesis()` gate end-to-end with concrete fixtures,
not just reading code or using the test-only bypass helper in
`conftest.py`.

**Four of the original "SUSPECTED ISSUE" findings are elevated to
DEMONSTRATED DEFECT below**, each with a concrete reproduction (not a
hypothetical future caller): Finding 1 (Locked-OOS/evaluation-mode
boundary), Finding 2 (research_mode never enforced), and Finding 11
(`hypothesis_config_version` never cross-checked) were each driven
through the ACTUAL `preregister_hypothesis()` gate end-to-end. **Finding
10** (`max_exit_families_per_hypothesis` counts variants, not family
types) is reproduced one layer earlier, through `proposals/
validator.py`'s `validate_proposal()` directly -- GPT's own review
(below) correctly caught an overgeneralization in an earlier version of
this paragraph that described Finding 10 as going through the real gate
too; it does not, though the counting bug it demonstrates is real and
would reject the same proposal before a draft claiming those two
variants could even be built. **One new finding** (Top Finding 13,
labeled G1 only within this paragraph -- renamed below to avoid
colliding with GPT's own later, unrelated G1): TEST 49's own
AST import-dependency guard has the identical parent-import blind spot
already found and documented in Spec #002's TEST 17/18 and Spec #003's
TEST 26 -- found while specifically checking cross-module dependencies
per Radu's request.

**Cross-module dependency check (Radu's specific request before the
joint remediation design):** confirmed directly by grep across
`src/evaluation/`, `src/discovery/`, `src/data_foundation/` -- none
import `hypothesis` anywhere, preserving the one-way Data Foundation ->
Discovery -> Evaluation -> Hypothesis chain. `src/hypothesis/` itself
imports only `discovery.config.loader`, `discovery.candidate.
reason_codes`, and `evaluation.models.entities` -- plain config/enum/
dataclass modules, never `discovery.engine`, `evaluation.engine`, or
anything under `data_foundation/`, matching SS5/SS110-F structurally.
`src/backtest/` (Spec #005) legitimately imports from `hypothesis.
models.entities`/`hypothesis.registry.hypotheses` in 5 files (exit
engine, discovery/plan integration, legacy exits, provenance) to
consume already-frozen `StrategyVariant`/`StrategyHypothesis` records
and reuse `check_provenance_matches_run()` -- reading-only consumption
of registry-stored objects, no bypass found. The one structural gap
found in this check is TEST 49 itself (G1 below), not the dependency
direction.

Full suite re-run after this pass (no code or test modified):
`tests/spec004` -- **176 passed**; full repository suite -- **727
passed, 1 skipped**, both unchanged from before this round.

**GPT independent review (2026-10-04), against commit `d272cb8`,
relayed by Radu -- this is the actual GPT round the paragraph above
said had not yet happened.** Scope and limits, as GPT itself states
them: only this matrix and `contract_index.md` differ from `fa8f257`
(no source/test changes); GPT ran `tests/spec004` itself (176 passed);
the global suite was NOT run by GPT (727 passed/1 skipped remains
Claude's own reported figure); all six of Claude's own probes above
reproduced under GPT's own run; GPT's own additional probes explicitly
REUSE Claude's fixture-builder function (`full_preregister()` from
`claude_reproduce_spec004.py`) with new scenarios/assertions layered on
top -- not an independently-built-from-scratch fixture, and GPT says so
itself; a delivered `.tar.gz` has no `.git/` and does not authenticate
branch/commit/push, only package content. **Six new findings (GPT's own
G1-G6, distinct from this document's own "G1" AST finding above, which
is renumbered Top Finding 13 to avoid the collision) plus one finding
specific to PATCH #004-C, all independently re-verified by Claude --
both by reading the exact cited code and by re-running GPT's own probe
script against this repository, not merely trusting GPT's reported
output:**

- **GPT-G1** -- `preregister_hypothesis()` (`registry/preregistration.py:85-116`)
  checks that `proposal`/`proposal_validation`/`consensus`/
  `draft.hypothesis_provenance` all name the SAME `proposal_id`, and
  that `approved_by`/`approved_at` match, but never compares the
  draft's own `direction`/`entry_definition`/`horizon_candidate_set`/
  exit content against what that proposal actually said.
  `validate_for_preregistration()` (`validation/rules.py:143-168`) only
  recomputes the fingerprint of the draft's OWN fields and confirms
  internal self-consistency -- "the hash matches the content," never
  "the content matches what was approved." Reproduced: a LONG proposal,
  genuinely passed through `validate_proposal()` with a real human
  APPROVE tied to its own `proposal_id`, still allows registering a
  SHORT draft under that same `proposal_id` with a correctly
  recomputed hash, and `build_strategy_definition()` exports a SHORT
  `StrategyDefinition` from it. The same binding gap separately allows
  an entry condition (`lane="UNAPPROVED_RSI"`) absent from the
  Discovery-approved vocabulary into the frozen draft, because
  `proposals/validator.py`'s vocabulary check runs only against the
  ORIGINAL proposal, never again against the draft actually frozen at
  the gate, and `validate_for_preregistration()`'s own outcome-scan
  checks only `FORBIDDEN_OUTCOME_FIELD_NAMES` token membership, not
  Discovery-vocabulary membership. TEST 62 only varies `proposal_id`
  mismatches, never content under a matching id; TEST 63 only checks
  the draft's internal hash self-consistency.
- **GPT-G2** -- completeness/semantics of the variant set are not
  enforced at freeze. `validate_for_preregistration()` only checks
  `set(hypothesis.variant_ids) == {v.strategy_variant_id for v in
  variants}` (both supplied by the same caller) and that at least one
  TIME_EXIT variant exists -- it never cross-checks that EVERY value in
  `horizon_candidate_set.values` has its own materialized TIME_EXIT
  variant. Reproduced: a family declaring horizon candidates `(2,3,5)`
  still passes the gate when `variant_ids` and the supplied variants
  are reduced TOGETHER to just the bar=2 TIME_EXIT, with
  `horizon_candidate_set.values` left unchanged at `(2,3,5)` -- the
  "every candidate materialized eagerly" guarantee (SS106-109,
  TEST 47) is enforced only by the normal construction path
  (`materialize_variants()`), never verified independently at the
  gate. Separately, `horizon_reference_point`/`exit_execution_policy`
  are plain `str` fields on `ExitHypothesis` (`models/entities.py:319-
  320`, commented "ENTRY_BAR only"/"BAR_CLOSE only" but never runtime-
  checked), and `time_exit_bars`' sign is never validated for TIME_EXIT
  specifically -- a hand-built TIME_EXIT variant with
  `time_exit_bars=-7`, `horizon_reference_point="SIGNAL_BAR"`,
  `exit_execution_policy="BEFORE_CLOSE"` passes the gate and exports.
  TEST 47 only checks that two DIFFERENT id sets are caught as a
  mismatch, never the case where both omit the same candidate together.
- **GPT-G3** -- the in-memory gate is not atomic across the
  hypothesis/variant boundary. `preregister_hypothesis()`
  (`registry/preregistration.py:143-145`) calls
  `registry._force_register(frozen)` FIRST, then calls
  `registry.register_variant(v)` for each variant in a loop; if any
  `register_variant()` call raises (e.g. a `strategy_variant_id`
  already registered under a conflicting `variant_tag`,
  PATCH #004-B finding #3's own immutability check), the exception
  propagates with NO rollback -- the hypothesis is left sitting in the
  registry as PREREGISTERED despite the overall call having failed.
  Reproduced directly. This is about the in-memory transaction only;
  no crash/disk-full was simulated, and TEST 65 (JSONL record shape and
  replay) does not cover this conflict at all.
- **GPT-G4** -- the public registry API allows reaching PREREGISTERED
  without ever calling the gate. `HypothesisRegistry.register()`
  (`registry/hypotheses.py:241-249`) only refuses a PREREGISTERED
  insert when `existing is None` (first-time insert for that id) --
  the docstring's own "DRAFT/REVIEWED/REJECTED/HANDOFF_TO_BACKTEST
  records" exception means a caller may legitimately `register()` a
  HANDOFF_TO_BACKTEST record for an id, and `_force_register()`'s own
  immutability check (line 265) only blocks overwriting an EXISTING
  PREREGISTERED record, not a HANDOFF_TO_BACKTEST one. Reproduced: on a
  fresh registry, `register()` with status HANDOFF_TO_BACKTEST,
  immediately followed by `register()` for the SAME object/id with
  status PREREGISTERED, succeeds with no error, and
  `register_variant()` + `build_strategy_definition()` then export a
  `StrategyDefinition` -- with no proposal, no consensus, no human
  decision, and `preregister_hypothesis()` never called. TEST 53 covers
  only direct PREREGISTERED insertion into an EMPTY registry, not this
  two-step transition through an intermediate status.
- **GPT-G5** -- `EvidencePacket` discards the actual stability-bin
  values. §39's own minimum-content list names "stability bins" as a
  literal top-level item, distinct from §57's "stability availability"
  (a Research Queue filter criterion) -- the spec text itself treats
  these as two different things. `build_evidence_packet()`
  (`evidence/packet.py:167`) and `EvidencePacket`
  (`models/entities.py:604-647`) carry only
  `primary_has_stability_bins: bool`; no mean/median/positive_rate per
  bin exists anywhere on the packet. Reproduced: two sets of
  `EvidenceProfile`s, identical except one has a stability bin with
  mean=+1% and the other mean=-70% (same `primary_has_stability_bins`
  either way), produce byte-identical `EvidencePacket`s. This is not a
  missing test or a naming mismatch -- the information is gone before
  any review or queue step ever sees it.
- **GPT-G6** -- Research Queue eligibility thresholds can change
  without the recorded config version changing. `HypothesisConfig`
  (`config/loader.py:19-29`) is a frozen dataclass, but its `data`
  field is a plain mutable `dict`; `config_version` is a hash of the
  RAW FILE TEXT computed once at load time, never recomputed from
  `data`'s actual current content. `build_research_queue()`
  (`evidence/queue.py:91,128`) reads `config.data["research_queue_
  eligibility"]` for the live thresholds but stamps every
  `ResearchQueueEntry.eligibility_config_version` from
  `config.config_version` -- the two can silently diverge. Reproduced:
  mutating `config.data["research_queue_eligibility"]
  ["minimum_valid_episode_n"]` from the loaded value to `100000` after
  load flips the SAME packet from eligible to ineligible while
  `eligibility_config_version` stays identical across both runs. This
  is Finding 11's config-integrity gap (`hypothesis_config_version`
  never cross-checked) recurring at the Research Queue, where SS110-H
  explicitly requires thresholds "configured, versioned and frozen
  before queue execution" -- TEST 50 changes the version field by hand
  in its own fixture, so it cannot detect this divergence.
- **P004C (reported separately, does NOT reopen PATCH #004-C's
  acceptance)** -- `registry/persistence.py`'s `_TYPE_REGISTRY`
  (lines 47-53) never lists `StopLossRule`/`PartialProfitRule`, the two
  PATCH #004-C entity types nested inside `ExitHypothesis` for the
  `STOP_MANAGED_INVALIDATION` family. `to_jsonable()` serializes them
  fine (generic dataclass recursion), but `from_jsonable()` raises
  `KeyError: 'StopLossRule'` on the round trip --
  `from_jsonable(to_jsonable(StopLossRule(basis="ATR_TRAILING_V1",
  atr_multiple=2.0)))` fails immediately. Reproduced exactly as
  described; not run as a full preregister-then-restart scenario, and
  not claimed as one. PATCH #004-C's own historical acceptance (commit
  `2fa5575`, the Spec #005 Exit Amendment v1.0 document) predates this
  discovery and is a different thing being accepted (the contract
  text, not this serializer path); this finding does not reopen it, it
  flags a persistence regression in a family added after #004's
  original audit scope.

**All of the above were independently reproduced by Claude**: by
reading the exact cited lines, and by re-running GPT's own
`gpt_probes.py` (which explicitly layers on top of
`claude_reproduce_spec004.py`'s fixture builder, per GPT's own
disclosure above) directly against this repository -- not merely
trusting GPT's self-reported output. See the delivered `gpt_probes.py`/
`gpt_results.txt`/`claude_probes_rerun_by_gpt.txt` and Claude's own
fresh run transcript for the exact reproduction. **GPT's own explicit
limits on these findings, preserved precisely rather than
generalized:** GPT-G1's probes do not call `_force_register()` and use
a genuinely-valid `ProposalValidationResult`, not a fabricated one;
GPT-G2's first probe never changes the horizon-candidate list itself,
only the materialized variants, and its second probe shows #004
exporting an invalid object, not #005 executing it; GPT-G3 is about the
in-memory transaction only, not disk-level corruption (not simulated);
GPT-G4 needs no private-method access; GPT-G5 does not claim every
profile field is lost, only stability bins, and does not imply a real
agent decision was actually wrong; GPT-G6 did not hand-edit any id or
hash, only the nested config dict; P004C is not an end-to-end
preregistration-to-restart demonstration. **Reconciliation of Claude's
own prior Findings 1-13 against GPT's review is below, per finding.**
Findings 1 and 2 keep their 2026-10-04 DEMONSTRATED DEFECT status with
corrections GPT required. For Finding 1, four distinct points, kept
separate rather than merged into one claim: (a) the reproduction never
touches PIT prices or an OOS date range -- it must not be read as
demonstrating actual Locked-OOS price/data access, only that
EXPLORATORY-mode evidence reaches PREREGISTERED; (b) §§3-4/98 do not
literally state a `FORMAL_DEVELOPMENT` allowlist requirement -- the
DEMONSTRATED part is narrower and purely structural: no field anywhere
on the frozen `StrategyHypothesis`/`EvidencePacket` records which mode
the evidence came from; whether the spec's text actually REQUIRES an
admission policy restricting hypothesis formation to FORMAL_DEVELOPMENT
evidence is a separate, still-open contractual reading, not something
this reproduction settles; (c) `evidence_provenance.evaluation_run_id`
IS preserved on the frozen record, so the mode is not unrecoverable
from EVERY source -- if the original `EvaluationRunRegistry` for that
`evaluation_run_id` is still available (e.g. in Spec #003's own
registry), its `mode` field could be looked up separately; the
DEMONSTRATED gap is that nothing on the #004 side itself carries or
checks this, not that the information is destroyed everywhere; (d) the
clean cross-module import scan above must not be read as certifying
that all data received through artifacts is itself correctly
provenanced -- GPT-G1 through G6 show the artifacts' *content*
guarantees have gaps the import scan cannot see. Finding 10
must be described precisely as reproduced through `validate_proposal()`
(the proposal-layer check), not generalized as "all through the real
preregister_hypothesis() gate" -- only Findings 1, 2, 11, and GPT-G1
through G6/P004C above were driven through the actual gate function
itself.

---

## Section-by-section table

| # | Requirement (paraphrase) | Code location | Test location | Status |
|---|---|---|---|---|
| 1 | Purpose: turn #003 evidence into a testable, frozen hypothesis; not a profitability test | Whole-package architecture | N/A (narrative) | N/A |
| 2 | Outcome-aware for hypothesis formation but not a backtester; never raw returns/backtest/Locked OOS/indicator optimization | `evidence/packet.py:31` (imports only `evaluation.models.entities`) | `test_36`, `test_38` | MET |
| 3 | A Development-derived hypothesis must be explicitly marked as such | `EvidenceProvenance` carries run/config lineage but no `evaluation_mode` field | No test asserts a DEVELOPMENT-DERIVED tag exists | **DEMONSTRATED DEFECT, 2026-10-04 (Claude's own fresh reproduction) -- see Top Finding 1, elevated from SUSPECTED ISSUE:** a hypothesis built entirely from `evaluation_mode="EXPLORATORY"` evidence reached PREREGISTERED through the real gate with zero errors; the frozen record carries no field anywhere recording which mode the evidence came from |
| 4 | Locked OOS completely inaccessible | Import-boundary only; no allowlist restricting mode to FORMAL_DEVELOPMENT | `test_36` (import boundary only) | MET for literal Locked-OOS price inaccessibility (the import boundary is real and structural -- `hypothesis/` never imports PIT/`data_foundation`, confirmed by this round's own dependency check). **DEMONSTRATED DEFECT, 2026-10-04 (Claude's own fresh reproduction) -- see Top Finding 1, elevated from SUSPECTED ISSUE:** the narrower, related claim -- that evidence feeding a hypothesis must have gone through FORMAL_DEVELOPMENT discipline -- is not enforced anywhere; same reproduction as §3 |
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
| 29 | Hypothesis Mode: EXPLORATORY vs PREREGISTERED | `HypothesisResearchMode` enum defined | Never checked by `preregister_hypothesis()`/`validate_for_preregistration()` -- Claude-verified, zero occurrences in either file | **DEMONSTRATED DEFECT, 2026-10-04 (Claude's own fresh reproduction) -- see Top Finding 2, elevated from SUSPECTED ISSUE:** a DRAFT explicitly tagged `research_mode="EXPLORATORY_HYPOTHESIS"` was driven through the REAL `preregister_hypothesis()` gate (not the test-only bypass helper) and reached PREREGISTERED unchanged, with no error. **GPT review, 2026-10-04 -- see Top Finding 17 (GPT-G4):** this check is moot anyway on the path GPT found -- a HANDOFF_TO_BACKTEST-then-PREREGISTERED transition through the public `register()` API never calls `preregister_hypothesis()` at all, so `research_mode` (like every other gate check) is skipped entirely on that path |
| 30 | Lifecycle DRAFT->REVIEWED->PREREGISTERED->HANDOFF; no edit-after-backtest | `HypothesisStatus` enum; `register()`/`_force_register()` | `test_24`, `test_53` | MET on the enum/state-machine shape. **DEMONSTRATED DEFECT, 2026-10-04 (GPT review, relayed by Radu) -- see Top Finding 17 (GPT-G4):** `register()`'s own first-time-PREREGISTERED guard (`registry/hypotheses.py:241-249`) checks only `existing is None`; registering a HANDOFF_TO_BACKTEST record first, then re-`register()`-ing the SAME id with status PREREGISTERED, is not first-time (`existing is not None`) and is not blocked -- the lifecycle diagram's implied "PREREGISTERED only via the gate" is not what the public API actually enforces |
| 31 | Post-preregistration modification creates a new id, never overwrites | `create_new_version()` | `test_25` | MET for modification OF an existing PREREGISTERED record via `create_new_version()` itself. **Related to Top Finding 17 (GPT-G4):** this guarantee assumes PREREGISTERED is only ever reached via the gate in the first place -- the public `register()` path GPT found reaches PREREGISTERED without `create_new_version()` or the gate, for a fresh id, so "never overwrites" is correct but doesn't cover how that first record got there |
| 32 | Hypothesis Registry, minimum fields | `models/entities.py:381-430` (field consolidation vs. spec's separate parent/supersedes pair) | `test_25` | MET (minor semantically-equivalent consolidation) |
| 33 | Evidence provenance obligatory | `EvidenceProvenance` | `test_01` | MET |
| 34 | Config change -> new hypothesis (H2), never silent reuse | `hypothesis_fingerprint()` includes every provenance field | `test_23` | MET |
| 35 | AI Agents produce proposals, never a final hypothesis directly | `HypothesisProposal` structurally distinct; only `preregister_hypothesis()` produces the latter | `test_53` (register() refuses hand-built PREREGISTERED) | MET on the structural distinction between the two types. **DEMONSTRATED DEFECT, 2026-10-04 (GPT review, relayed by Radu) -- see Top Finding 17 (GPT-G4):** "only `preregister_hypothesis()` produces [a final hypothesis]" is false as a claim about the code -- the public `register()` API can also produce one, via the HANDOFF_TO_BACKTEST-then-PREREGISTERED transition, with no proposal/consensus/human-decision involved at all |
| 36 | No API calls in core Registry | `proposals/normalize.py` docstring; zero LLM imports | `test_39` | MET |
| 37 | Why separate AI from core | Architecture-level rationale | N/A | N/A |
| 38 | Token-economy: LLM never gets raw OHLCV/thousands of observations | `EvidencePacket` flat/primitive fields only | `test_02` | MET |
| 39 | `EvidencePacket` entity, minimum fields | `models/entities.py:603-647` | `test_01`, `test_57` | MET on every other field in §39's list. **DEMONSTRATED DEFECT, 2026-10-04 (GPT review, relayed by Radu) -- see Top Finding 18 (GPT-G5):** §39 literally lists "stability bins" as its own top-level minimum-content item, distinct from §57's separate "stability availability" -- the packet carries only `primary_has_stability_bins: bool`, no actual bin values, so this one item of §39's list is not met, not merely untested |
| 40 | Token target ~1-3KB per candidate | Flat-field design supports it | No test measures actual serialized size | **MET (design)** [TEST-COVERAGE GAP: size is a numeric measurement, not confirmable by inspection alone] |
| 41 | Agent roles V1 -- conceptual, not real API agents | `agent_id` is a free-form string; no role enum | `docs/spec004_agent_interface.md` explicitly documents this | **FUTURE / PROCEDURAL REQUIREMENT** -- correctly left as process convention |
| 42 | Independent first-pass reasoning | No sequencing/visibility-gating mechanism exists | Not code-testable -- pure human orchestration | **FUTURE / PROCEDURAL REQUIREMENT** |
| 43 | Consensus is not a vote for truth; independent perspectives reaching the same structure | `compute_consensus()` classifies shape only, never correctness | `test_32` | MET |
| 44 | `AgentReview` entity | `models/entities.py:527-538` | `test_29` | MET |
| 45 | `ConsensusRecord` entity | `models/entities.py:555-564` | `test_32` | MET |
| 46 | Human authority final; AI consensus alone can't auto-preregister | `can_preregister()` | `test_30`, `test_31` | MET on the core rule that AI consensus alone cannot auto-preregister via the gate. **SUSPECTED ISSUE -- VERIFICATION PENDING**: whether a human APPROVE can override a BLOCKED (all-objecting) consensus is genuinely unresolved by the spec text and untested for that exact combination -- see Finding 5. **DEMONSTRATED DEFECT, 2026-10-04 (GPT review, relayed by Radu) -- see Top Findings 14 and 17 (GPT-G1, GPT-G4):** "human authority final" assumes the human's APPROVE actually covers the content being frozen (GPT-G1 shows it doesn't -- the gate never compares draft content to what was approved) and that the gate is the only path to PREREGISTERED (GPT-G4 shows a path with no human decision at all) |
| 47 | Statistical-skeptic checklist (support/concentration/FDR/horizon/regime/scarcity) | `objections` is free text; no structured checklist enforced | Nothing enforces the checklist was actually applied | **FUTURE / PROCEDURAL REQUIREMENT** -- whether the checklist was actually applied is a human-judgment question code cannot verify |
| 48 | `HypothesisProposal` entity, minimum fields | `models/entities.py:491-524` | `test_33` | MET |
| 49 | Rationale is interpretation, not statistics; separated from Evidence | `facts_from_evidence`/`interpretation` separate fields | `test_33` | MET |
| 50 | Output distinguishes FACTS from INTERPRETATION | Same as §49 | `test_33` | MET |
| 51 | Hypothesis Budget protects against combinatorial explosion | `config/hypothesis.yaml:54-57` | `test_27` | MET |
| 52 | Level-1 budget values | `config/hypothesis.yaml:50-57`; `validator.py:256-270` | `test_27`, `test_08` | MET on the budget mechanism. **DEMONSTRATED DEFECT, 2026-10-04 (Claude's own fresh reproduction) -- see Top Finding 10, elevated from SUSPECTED ISSUE:** two SIGNAL_INVALIDATION variants (differing only by `max_holding_bars`/`invalidation_conditions`, both the SAME family TYPE) were rejected as "exceeds max_exit_families_per_hypothesis" even though only 2 distinct family types (TIME_EXIT + SIGNAL_INVALIDATION) are present -- `validator.py:256` counts `len(proposal.exit_hypotheses)`, a raw entry count, not `len({e.exit_family for e in proposal.exit_hypotheses})` |
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
| 63 | `StrategyDefinition` entity | `models/entities.py:450-484`; `strategy_registry.py:26-82` | `test_41` | MET on the entity's own field shape. **DEMONSTRATED DEFECT, 2026-10-04 (GPT review, relayed by Radu) -- see Top Findings 14, 15, 17 (GPT-G1, GPT-G2, GPT-G4):** `build_strategy_definition()` exports whatever a `StrategyHypothesis`/`StrategyVariant` pair actually contains, with no re-validation of its own -- each of GPT-G1 (content not bound to approval), GPT-G2 (variant completeness/semantics not enforced), and GPT-G4 (PREREGISTERED reachable without the gate) was reproduced ending in a successful export through this exact entity |
| 64 | Universe Policy uses Discovery eligibility mechanism, not a static list | `UNIVERSE_POLICY="DISCOVERY_ELIGIBLE_UNIVERSE"` constant; no static-list field exists anywhere on `StrategyDefinition` | No dedicated regression test beyond one line | **MET (by inspection: no static-list field exists to misuse)** [TEST-COVERAGE GAP] |
| 65 | No ticker cherry-picking after seeing outcomes | No field capable of expressing a ticker exclusion list | None dedicated | **MET (by inspection)** [TEST-COVERAGE GAP -- see Finding 9] |
| 66 | Sector restrictions must be preregistered | Same structural absence | None | **MET (by inspection)** [TEST-COVERAGE GAP -- see Finding 9] |
| 67 | Market regime filters must be preregistered | Same structural absence | None | **MET (by inspection)** [TEST-COVERAGE GAP -- see Finding 9] |
| 68 | Daily->4H readiness: timeframe/horizon_bars, never holding_days | Forbidden-token scan on entity fields | `test_40` | MET |
| 69 | Multi-timeframe future needs no registry redesign | Generic `timeframe: str` field | Implied by §68's test | MET (forward-looking, reasonably supported) |
| 70 | Each condition carries its own source_feature/engine/version | No per-condition provenance fields exist -- only whole-hypothesis provenance | `test_41`'s docstring cites this but assertions never check it | **SUSPECTED ISSUE -- VERIFICATION PENDING** -- see Finding 3: absence confirmed, contractual necessity for Radu to judge |
| 71 | Deterministic validation before PREREGISTERED (full checklist) | Split across `validator.py:227-279` and `rules.py:137-257` | `test_04,07,09,10,15,18-20,41-43` | MET (two-layer implementation) on every checklist item the two layers actually implement. **DEMONSTRATED DEFECT, 2026-10-04 (Claude's own fresh reproduction) -- see Top Finding 11, elevated from SUSPECTED ISSUE:** `validate_for_preregistration()` receives `hypothesis_config` as a plain `dict` (never the `HypothesisConfig` wrapper carrying `config_version`) and never compares it against `hypothesis.constraints.hypothesis_config_version` -- preregistering against a config dict with `max_hypotheses_per_signature` changed to `999` still succeeded while the frozen record's own `constraints.hypothesis_config_version` kept claiming the ORIGINAL, unmodified config's hash. **Three further gaps in "the full checklist," 2026-10-04 (GPT review, relayed by Radu) -- see Top Findings 14, 15, 16 (GPT-G1, GPT-G2, GPT-G3):** the checklist never compares the draft's content against what was actually approved (GPT-G1); never checks that every `horizon_candidate_set.values` entry has its own materialized TIME_EXIT variant, nor validates `horizon_reference_point`/`exit_execution_policy`/`time_exit_bars` sign for TIME_EXIT (GPT-G2); and the gate itself is not atomic across the hypothesis-then-variants write (GPT-G3) |
| 72 | Outcome contamination forbidden in entry/exit conditions | `FORBIDDEN_OUTCOME_FIELD_NAMES` + scan function; also the Discovery-lane allowlist | `test_18,19,20` | MET -- core-discipline check, no violation found, enforced at both layers |
| 73 | Forbidden example must be structurally inexpressible | Same mechanism as §72 | `test_19` | MET |
| 74 | **Correction, 2026-10-04 (GPT review, relayed by Radu): this is NOT duplicate numbering.** §73 is the "exemplu permis" (a structurally-valid hypothesis built from lane/label conditions); §74 is the separate "exemplu interzis" (`IF adjusted_p < 0.05 AND mean_relative_return > 1% THEN BUY`) -- a distinct requirement illustrating §72's outcome-contamination rule with a concrete forbidden case | Same mechanism as §72: `FORBIDDEN_OUTCOME_FIELD_NAMES` + `_scan_condition_for_outcome_contamination()` (`validation/rules.py:67-88`) | `test_18,19,20` | MET -- the structural condition types (`lane`/`label`/`reason_code`) cannot even express a free-text predicate like §74's example; the forbidden-field scan is the enforcement mechanism, same evidence as §72 |
| 75 | Exit derivation process (decay->region->bounded set->freeze->#005 tests all) | `materialize_variants()` | `test_13`, `test_47` | MET on the normal construction path. **Related to Top Finding 15 (GPT-G2):** this guarantee describes what `materialize_variants()` itself does when used as intended; it is not independently re-verified at the gate, so a hand-built variant set bypassing this function is not caught by "freeze" alone |
| 76 | Full worked example | `docs/spec004_examples.md` Example A/C | `test_13,14,46` | MET |
| 77 | #005 must know all candidates, none invented after backtest | `variant_ids` populated eagerly, checked against materialized variants | `test_47` | MET (#005's own future behavior is out of #004's testable scope) on the "none invented after" half. **DEMONSTRATED DEFECT, 2026-10-04 (GPT review, relayed by Radu) -- see Top Finding 15 (GPT-G2):** the "all candidates" half is not independently guaranteed -- `variant_ids` matching the supplied variants only proves internal consistency between two caller-supplied lists, not that every `horizon_candidate_set.values` entry is actually represented; a family can freeze with fewer TIME_EXIT variants than its own declared horizon candidates |
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
| 98 | Hard FAIL conditions (14 named) | Distributed across `test_05,12,16,24,26,31,35,36,37,38,53` | Same | MET on literal Locked-OOS price inaccessibility (the import boundary is real and structural, confirmed by this round's own dependency check). **DEMONSTRATED DEFECT, 2026-10-04 -- see Top Finding 1**: the narrower, related FAIL condition -- that evidence feeding a hypothesis must itself have gone through FORMAL_DEVELOPMENT discipline -- is not enforced; same reproduction as §3/§4. **Two further Hard FAIL conditions, 2026-10-04 (GPT review, relayed by Radu) -- see Top Findings 14 and 17 (GPT-G1, GPT-G4):** "no hypothesis reaches PREREGISTERED without a human-approved proposal covering that exact content" and "no hypothesis reaches PREREGISTERED without the deterministic gate" are each independently demonstrated not held, by two different code paths |
| 99 | Out-of-scope list | `NOT_DEFINED_YET` placeholders; no broker/backtest imports | `test_37,38` | MET |
| 100 | What #004 produces at the end (not a profitability claim) | Registry accounting | N/A | N/A |
| 101 | Example final `StrategyHypothesis` | `docs/spec004_examples.md` | N/A | N/A |
| 102 | Opportunity density in EvidencePacket, frequency not falsified | `primary_episodes_per_20/60_sessions` fields | `test_01` (indirect) | MET |
| 103 | Frequency reported separately from statistical quality/profitability | Same fields, different name | None dedicated | MET (functionally equivalent naming) |
| 104 | Prefer StrategyFamily output when variants exist | `StrategyHypothesis`(family)+`StrategyVariant`(exit) split | `test_52` | MET (naming diverges from Radu's own §110-D text -- see Finding 12, a textual note, not a functional gap) |
| 105 | `StrategyFamily` entity, minimum fields | Same split as above | `test_52` | MET (same naming note) |
| 106 | No Cartesian explosion; configurable variant budget | `max_variants_per_family: 6` | Report-script Example D | MET |
| 107 | Over-budget -> explicit error, never silent truncation | `ComplexityStatus` enum; full error list returned | `test_08`, Example D | MET on the over-budget direction. **Related to Top Finding 15 (GPT-G2):** the complementary under-representation case (fewer variants than declared horizon candidates, §77/§110-D) is not caught by this or any other check -- "never silent truncation" holds for too many, not for too few |
| 108 | #005-accounting export: all proposals/variants/rejected/preregistered | `HypothesisUniverse` has no `all_variants` field (a separate `registry.all_variants()` method exists but isn't wired in) | No test (same untested status as §54) | `HypothesisUniverse` itself: **MET (by inspection)** [TEST-COVERAGE GAP, same as §54]. Missing `all_variants` field: **SUSPECTED ISSUE -- VERIFICATION PENDING** -- see Finding 7 |
| 109 | Guiding principle: few interpretable hypotheses > mass search | Architectural consequence of budget+registry design | N/A | N/A |
| 110 | Radu's approved answers to §110 A-H | Mapped across `models/entities.py`, `validator.py`, `hypotheses.py`, `evidence/packet.py`, `evidence/queue.py` | `test_45-52` | MET. §110-F's explicit request for "a structural dependency test" (`evaluation/` cannot import `hypothesis/`) is implemented as `test_49`. **TEST-COVERAGE GAP, 2026-10-04 (Claude's own fresh finding) -- see Top Finding 13:** `test_49`'s own AST collector has the identical parent-import blind spot already documented for Spec #002's TEST 17/18 and Spec #003's TEST 26 -- `from src import hypothesis as h` is invisible to it. No actual violation found by manual read of `src/evaluation/`/`src/discovery/` (this round's own dependency check, see status update above); the guard's coverage, not today's dependency direction, is what's gapped. **Two further gaps within §110 itself, 2026-10-04 (GPT review, relayed by Radu):** §110-C/D's "every candidate materialized eagerly" is not independently re-verified at the gate -- see Top Finding 15 (GPT-G2); §110-H's explicit requirement that Research Queue eligibility thresholds be "configured, versioned and frozen before queue execution" is demonstrably not held -- see Top Finding 19 (GPT-G6), where the recorded `eligibility_config_version` does not change when the underlying threshold dict is mutated after load |
| 111 | Final 16-point confirmation checklist | Recap of already-covered points | Same tests as those points | N/A (restates already-assessed items) |

---

## Top findings, with concrete failure scenarios

1. **[DEMONSTRATED DEFECT, 2026-10-04 -- elevated from SUSPECTED ISSUE by Claude's own fresh reproduction]** Locked OOS / evaluation-mode boundary is import-level only, not value-level (SS3-4, SS98). `build_evidence_packet()` checks internal consistency of supplied `evaluation_mode` values but never checks the mode IS `FORMAL_DEVELOPMENT`, and `EvidencePacket`/`EvidenceProvenance` have no `evaluation_mode` field at all. **No longer hypothetical**: a `StrategyHypothesis` built entirely from `evaluation_mode="EXPLORATORY"` evidence was driven through the REAL `preregister_hypothesis()` gate (not the test-only bypass helper) and reached PREREGISTERED with zero errors; the frozen record carries no field anywhere recording which mode the evidence came from on the #004 side itself, so this is indistinguishable from a FORMAL_DEVELOPMENT-sourced hypothesis using only #004's own records. **GPT correction, 2026-10-04 (relayed by Radu), four points kept separate:** this does NOT demonstrate actual Locked-OOS price/data access; §§3-4/98 do not literally state a FORMAL_DEVELOPMENT-allowlist requirement, so whether the spec actually requires one is still a separate open contractual question; `evidence_provenance.evaluation_run_id` IS preserved, so the mode is not unrecoverable from every source, only from #004's own frozen record in isolation; and the clean cross-module import scan elsewhere in this document does not certify that artifact *content* (as opposed to import structure) is itself correctly provenanced -- see the full reconciliation in the GPT review status block above and Top Findings 14-19. See §3/§4 for the reproduction.
2. **[DEMONSTRATED DEFECT, 2026-10-04 -- elevated from SUSPECTED ISSUE by Claude's own fresh reproduction]** `research_mode` (SS29) is never enforced at the preregistration gate (zero occurrences in `registry/preregistration.py` or `validation/rules.py`). **No longer a static-grep claim**: a DRAFT explicitly tagged `research_mode="EXPLORATORY_HYPOTHESIS"` ("cannot enter formal backtest validation directly") was driven through the REAL gate and reached PREREGISTERED unchanged, with no error -- alongside two Spec #002 findings GPT verified the same way by inspection; the contractual verdict on all three is Radu's, not yet given. See §29 above.
3. **[SUSPECTED ISSUE -- VERIFICATION PENDING]** Per-condition provenance (SS70) is missing -- only whole-hypothesis provenance exists, confirmed by inspection. An entry mixing conditions validated under two different Discovery config versions would be indistinguishable from one where both share the same version. Whether SS70 requires this granularity or whole-hypothesis provenance suffices is Radu's contractual reading.
4. **[FUTURE / PROCEDURAL REQUIREMENT]** "Independent first-pass reasoning" and the statistical-skeptic checklist (SS41-43,47) are process requirements code cannot express, honestly documented as unenforced.
5. **[SUSPECTED ISSUE -- VERIFICATION PENDING]** Whether a human APPROVE can override a BLOCKED (all-objecting) consensus (SS43-46) is genuinely unresolved by the spec text; current code takes the permissive reading, untested for this exact combination.
6. **[SUSPECTED ISSUE -- VERIFICATION PENDING]** `FutureResearchNote` (SS84-85) is dead code -- defined but never constructed, validated, or referenced anywhere, confirmed by inspection. Whether this leaves SS84 genuinely unmet or is acceptable unused scaffolding at this stage is Radu's call.
7. **[TEST-COVERAGE GAP (the entity) + SUSPECTED ISSUE -- VERIFICATION PENDING (the missing field)]** `HypothesisUniverse` (SS54, SS108) is a simple accounting object, reasonable by inspection, but has zero test coverage; separately, it omits "all variants considered" as a field, though the data exists via a different, unwired method.
8. **[TEST-COVERAGE GAP]** No test verifies the ~1-3KB EvidencePacket token-budget target (SS40) -- a size measurement, not confirmable by reading the code.
9. **[TEST-COVERAGE GAP]** Ticker/sector/regime-exclusion prohibitions (SS64-67) are enforced only by field absence -- confirmed correct today by inspection (no such field exists to misuse), but with no regression test guarding against a future field being added.
10. **[DEMONSTRATED DEFECT, 2026-10-04 -- elevated from SUSPECTED ISSUE by Claude's own fresh reproduction]** `max_exit_families_per_hypothesis` (SS52) is enforced as a raw variant count, not a family-type count. **Reproduced concretely**: two SIGNAL_INVALIDATION variants (differing only by `max_holding_bars`/`invalidation_conditions`, both the SAME family type) were rejected by `validator.py:256` as "exceeds max_exit_families_per_hypothesis," even though only 2 distinct family types (TIME_EXIT + SIGNAL_INVALIDATION) were actually present. Whether this stricter-than-named behavior matters contractually is still Radu's call; the code behavior itself is no longer just a by-inspection claim. See §52 above.
11. **[DEMONSTRATED DEFECT, 2026-10-04 -- elevated from SUSPECTED ISSUE by Claude's own fresh reproduction]** `hypothesis_config_version` is never cross-checked against the config actually used at the gate. **Reproduced concretely**: preregistering against a tampered config dict (`max_hypotheses_per_signature` changed to `999`) still succeeded through the real gate, while the frozen record's own `constraints.hypothesis_config_version` kept claiming the hash of the ORIGINAL, unmodified config -- the stored version string is decorative, not a verified cross-check. Contractual significance of this gap is still Radu's call. See §71 above.
12. **[Textual note, not a functional gap]** The implementation never uses the name "StrategyFamily," even though Radu's own §110-D approval text literally uses that name for the family-level entity (it's called `StrategyHypothesis` instead). Documented and justified at the time, but a literal-text deviation from the final approval worth Radu's explicit sign-off, given he called this design one of the most important decisions.
13. **[TEST-COVERAGE GAP, 2026-10-04 -- new finding, Claude's own fresh pass]** `test_49`'s AST import-dependency guard (SS110-F's "structural dependency test" that `evaluation/` cannot import `hypothesis/`) has the identical parent-import blind spot already documented in Spec #002's TEST 17/18 and Spec #003's TEST 26: its `_imports()`/`_imported_modules()` helper walks only `ast.ImportFrom.module`, never `alias.name` from `node.names`, so `from src import hypothesis as h` is invisible to it. No actual violation exists today -- this round's own cross-module dependency check (manual read of `src/evaluation/`, `src/discovery/`, `src/data_foundation/`) confirms none of them import `hypothesis` anywhere. The gap is in the guard's coverage, not today's dependency direction. See the status update above and row §110.

**Findings 14-20 below are from GPT's own independent review (2026-10-04, relayed by Radu), against commit `d272cb8` -- each independently re-verified by Claude both by reading the cited code and by re-running GPT's own probe script against this repository. GPT's own identifiers for these are G1-G6 (plus a separate P004C note); they are renumbered 14-19 (+20) here solely to avoid colliding with this document's own pre-existing "G1" (the AST finding above, now Top Finding 13) -- the content is GPT's, not Claude's.**

14. **[DEMONSTRATED DEFECT, 2026-10-04 (GPT review, relayed by Radu) -- GPT's G1]** Approval and content-addressed identity are two different guarantees, and only the second is actually checked. `preregister_hypothesis()` (`registry/preregistration.py:85-116`) verifies that `proposal`/`proposal_validation`/`consensus`/`draft.hypothesis_provenance` all name the SAME `proposal_id` and that the approver/timestamp match; `validate_for_preregistration()` (`rules.py:143-168`) verifies the draft's `hypothesis_id`/`definition_hash` match the fingerprint of its OWN fields. Neither ever compares the draft's actual `direction`/`entry_definition`/`horizon_candidate_set`/exit content against what the referenced proposal said. Reproduced: a genuinely-validated, genuinely-APPROVED LONG proposal still permits registering and exporting a SHORT `StrategyDefinition` under the same `proposal_id` with a correctly-recomputed hash; the same gap separately admits an entry condition (`lane="UNAPPROVED_RSI"`) outside the Discovery-approved vocabulary, since that vocabulary check runs only on the original proposal, never again on the frozen draft. TEST 62 covers only proposal_id mismatches; TEST 63 covers only internal hash self-consistency; neither covers content drift under a matching, correctly-approved id. See §§29-31,35,46,63,71,98 above.
15. **[DEMONSTRATED DEFECT, 2026-10-04 (GPT review, relayed by Radu) -- GPT's G2]** Variant-set completeness and per-variant exit semantics are not independently enforced at the gate. `validate_for_preregistration()` only checks that the declared and supplied variant-id sets are equal to EACH OTHER (both caller-supplied) and that at least one TIME_EXIT exists -- it never cross-checks that every `horizon_candidate_set.values` entry has its own TIME_EXIT variant, and `horizon_reference_point`/`exit_execution_policy`/`time_exit_bars`' sign are enforced only by convention in `materialize_variants()`, never re-checked at the gate. Reproduced: a family declaring horizon candidates `(2,3,5)` freezes successfully with only the bar=2 TIME_EXIT variant (both lists reduced together, `horizon_candidate_set.values` left unchanged); separately, a hand-built TIME_EXIT with `time_exit_bars=-7`, `horizon_reference_point="SIGNAL_BAR"`, `exit_execution_policy="BEFORE_CLOSE"` passes the gate and exports. TEST 47 only catches two DIFFERENT id sets, never both omitting the same candidate together. See §§19,75,77,106-108 and §110-C/D above.
16. **[DEMONSTRATED DEFECT, 2026-10-04 (GPT review, relayed by Radu) -- GPT's G3]** The in-memory gate is not atomic across the hypothesis-then-variants write. `preregister_hypothesis()` (`preregistration.py:143-145`) calls `registry._force_register(frozen)` BEFORE registering any variant; if a later `registry.register_variant()` call raises (e.g. a conflicting `variant_tag` under an already-used `strategy_variant_id`), there is no rollback -- the hypothesis is left sitting in the registry as PREREGISTERED despite the overall call having failed. Reproduced directly. Scoped to the in-memory transaction only -- no crash/disk-full was simulated, and TEST 65 (JSONL record shape/replay) does not cover this conflict.
17. **[DEMONSTRATED DEFECT, 2026-10-04 (GPT review, relayed by Radu) -- GPT's G4]** The public `HypothesisRegistry.register()` API can reach PREREGISTERED without the gate ever running. Its first-time-PREREGISTERED guard (`registry/hypotheses.py:241-249`) checks only `existing is None`; a HANDOFF_TO_BACKTEST record legitimately registered first (the docstring's own documented exception), then re-`register()`-ed under the same id with status PREREGISTERED, is NOT first-time and is NOT blocked. Reproduced: fresh registry, `register()` HANDOFF_TO_BACKTEST, `register()` the same object/id as PREREGISTERED, `register_variant()`, `build_strategy_definition()` -- all succeed, with no proposal, no consensus, no human decision, and `preregister_hypothesis()` never called. TEST 53 covers only direct PREREGISTERED insertion into an EMPTY registry, not this two-step transition. See §§29-31,35,46,63,98 above.
18. **[DEMONSTRATED DEFECT, 2026-10-04 (GPT review, relayed by Radu) -- GPT's G5]** `EvidencePacket` discards actual stability-bin values, keeping only their presence. §39's minimum-content list names "stability bins" as its own top-level item, distinct from §57's separate "stability availability" (a Research Queue filter criterion) -- the spec text itself treats these as two different things. `build_evidence_packet()` (`evidence/packet.py:167`) and `EvidencePacket` (`entities.py:604-647`) carry only `primary_has_stability_bins: bool`. Reproduced: two profile sets, identical except a stability bin mean of +1% vs -70% (same presence flag either way), produce byte-identical `EvidencePacket`s. See §39 above.
19. **[DEMONSTRATED DEFECT, 2026-10-04 (GPT review, relayed by Radu) -- GPT's G6]** Research Queue eligibility thresholds can change without the recorded config version changing -- the same category of gap as Finding 11, now demonstrated at the queue. `HypothesisConfig` (`config/loader.py:19-29`) is a frozen dataclass wrapping a plain MUTABLE `data` dict; `config_version` is a hash of the raw file text, fixed at load time, never recomputed from `data`'s live content. Reproduced: mutating `config.data["research_queue_eligibility"]["minimum_valid_episode_n"]` after load flips the same packet from eligible to ineligible while `eligibility_config_version` stays identical. SS110-H explicitly requires thresholds "configured, versioned and frozen before queue execution"; TEST 50 changes the version field by hand in its own fixture and so cannot detect this divergence. See §110-H above.
20. **[Reported separately, does not reopen PATCH #004-C's historical acceptance]** `registry/persistence.py`'s `_TYPE_REGISTRY` (lines 47-53) omits `StopLossRule`/`PartialProfitRule`, the two PATCH #004-C types nested inside `ExitHypothesis` for `STOP_MANAGED_INVALIDATION`. `to_jsonable()` serializes them via generic dataclass recursion; `from_jsonable()` raises `KeyError: 'StopLossRule'` on the round trip. A persistence regression in a family added after #004's original audit scope, not a defect in #004's own text-conformance; needs its own remediation/approval step, separate from re-litigating PATCH #004-C's acceptance.
