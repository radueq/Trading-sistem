# Contract Index -- Spec #001-#005

Requested by Radu (2026-09-30), after the Spec #005 base-contract gap
(the document existed only in Radu's GPT conversation history, never
archived in this repo, until he supplied it directly and it was committed
verbatim at `f477e93`). Purpose: a single table of what original contract
text this repo actually holds, versus what is Claude's own derived
documentation -- so a gap like #005's is caught before it forces an
emergency recovery, not after.

**This index does not itself certify anything.** It records what is
present, what is missing, and what is merely inferred, per spec. It does
not rename any derived document as if it were a source contract, and it
does not substitute for the required→code→test correspondence check and
the contradiction/ambiguity/testability audit Radu separately requested.
Now that original text has been recovered for #001-#004 (see below),
that audit still needs to be run against it -- recovering the text is
not the audit.

**On independent verification of git claims:** a delivered `git archive`
snapshot (a `.tar.gz` bundle) never includes `.git/` -- it is a snapshot
of files at one commit, not the repository. Any claim in this project
that a commit hash exists, or that a file was "committed" as of some
point, is Claude's own `git log`/`git cat-file` output against the actual
repository, not something checkable from a delivered bundle. Independent
verification of such a claim requires the real repository
(`radueq/Trading-sistem`, branch `claude/dazzling-cori-kbgf23`) -- a
clone or `git log` against it directly, not a snapshot archive. This
index's own commit-hash citations below are Claude's `git log` output and
carry the same caveat -- **none of it is independently verified by Radu
as of this revision.**

**2026-09-30 update -- original text recovered for #001-#004, from a
different source than the one Radu was pursuing.** Radu was searching his
own GPT conversation library and could not find exportable full bodies for
#001-#004 (only a partial reference/summary for #001). Separately, this
Claude Code session's own transcript file
(`5232cc45-b2e4-59d6-ba23-9687d55bed17.jsonl`, on the container this
session runs in) turned out to contain the actual chat messages Radu sent
*to Claude Code* when each spec was implemented -- this is the
"messages sent to Claude" alternative Radu himself named as acceptable.
Claude extracted these messages verbatim and committed them below. **This
is a recovery Claude performed and reports; Radu has not independently
verified any of it.** It does not substitute for Radu locating his own
GPT-side copies if he wants a second, independent source to cross-check
against -- it is one primary source, not confirmation.

---

## Spec #001 -- Data Foundation

| | |
|---|---|
| **Original contract file** | **PRESENT.** `docs/Spec_001_Data_Foundation_v1.0.md` -- recovered from this session's own transcript, 2026-09-30 (see update note above). Contains **four original Radu-authored messages**, verbatim, in the order sent: (1) the introduction, cut off before the specification body reached Claude ("--- SPECIFICAȚIA COMPLETĂ ---" with nothing following); (2) the body's SS1-15; (3) the body's SS16-29; (4) a correction to point 1 (Corporate Action status must be PIT-derived from `as_of`, never wall-clock time) plus the final "LOCKED / APPROVED / AUTHORIZED" sign-off. **Claude's own reply between (1) and (2)** -- noting the cutoff and asking Radu to resend -- **is not reproduced as an original message**; it is referenced only in a one-line editorial aside inside the file, for context. Exact transcript line numbers and timestamps for each of the four are recorded inside the file. |
| **Version** | v1.0, per the recovered text's own header. |
| **Source** | This Claude Code session's transcript (messages Radu sent to Claude), not Radu's GPT conversation history -- he still has not located that side's copy. |
| **Approval** | **ACCEPTED.** `docs/ACCEPTANCE.md`. Technical baseline `918f3f7` (persistence-lifecycle fix). Acceptance recorded in commit `a6514b0` (2026-09-21), Radu sign-off. |
| **Amendments** | PATCH #001-C `aa56bb5` (`split_adjusted_volume`, additive, not a reopening). PATCH #001-D `b1bb301`, accepted at `cfa0809` (`split_adjusted_open/high/low`, additive, not a reopening -- surfaced while scaffolding Spec #005). |
| **Derived documentation** | `docs/architecture.md`, `docs/known_limitations.md`, `docs/test_report.md`, `docs/ACCEPTANCE.md`. |
| **Completeness caveat (Radu, 2026-09-30)** | All 29 numbered sections (SS1-SS29) are present. **SS29 itself ends mid-sentence** -- "începem proiectarea:" ("we begin designing:") -- with nothing after it anywhere in the transcript. Every section header is there; this one closing line is not, and it is not completed or inferred here -- it is recorded as missing, to be confirmed from source if Radu can locate a further fragment, never guessed. |
| **Flag** | Text now present but NOT YET independently verified by Radu ("byte-for-byte" is Claude's description of its own extraction process, not something Radu can confirm without the raw transcript fragments himself), and NOT YET run through the requirement→code→test correspondence check or the contradiction/ambiguity/testability audit he requested -- both still open. Does not reopen the existing acceptance. See also "Superseded rules," below, for the SIGNAL_INVALIDATION timing and risk-exit items this spec's recovered text touches. |

## Spec #002 -- Feature Engine + Outcome-Blind Discovery Engine

| | |
|---|---|
| **Original contract file** | **PRESENT.** `docs/Spec_002_Feature_Engine_Discovery_v1.0.md` -- recovered from this session's own transcript, 2026-09-30. Sent as a single message, already final (self-labeled "Status: APPROVED FOR IMPLEMENTATION"). |
| **Version** | v1.0, per the recovered text's own header. |
| **Source** | This Claude Code session's transcript. Not Radu's GPT conversation history. |
| **Approval** | **Acceptance is cited in later specs' own documentation; primary evidence of that acceptance has not been recovered.** This is a precise distinction, not a downgrade to "unaccepted": `docs/spec003_architecture.md` ("Spec #002 Accepted Baseline `4f36708`") and `docs/spec004_known_limitations.md` ("#002 `4f36708`") both cite it as accepted. What is missing is a self-contained acceptance record of #002's own -- unlike #001/#003/#004, there is no `docs/ACCEPTANCE.md`-equivalent, no "ACCEPTED at commit X" line inside #002's own docs, and no dedicated acceptance-recording commit in git history for #002 specifically (`a6514b0`, `266cc6f`, `74daadc` exist for #001/#003/#004; nothing equivalent exists for #002). Radu has explicitly declined to treat the citation chain as confirmation on its own. |
| **Amendments** | PATCH #002-A `4f36708` (cross-sectional RS eligibility-ordering fix, GPT Review #002 Round 1 mandatory finding). PATCH #002-B `136bf94` (pre-budget `DiscoveryObservation` isolation, resolving Spec #003's own IMPLEMENTATION BLOCKER SS74A). |
| **Derived documentation** | `docs/spec002_architecture.md`, `spec002_known_limitations.md`, `spec002_test_report.md`, `spec002_examples.md`, `spec002_volume_report.md`. |
| **Flag** | Base text is now present, but the acceptance question is separate and still open: either the primary evidence of an actual acceptance decision (conversation or delivery) is located and checked, or -- per Radu's own instruction -- a fresh verification is run now and a new acceptance is recorded, explicitly dated, rather than retroactively inferring one from citations. See also "Superseded rules," below, for the holding-domain figure this spec's own text carries. |

## Spec #003 -- Outcome-Aware Evaluation Engine (Fast-Swing / Bar-Based)

| | |
|---|---|
| **Original contract file** | **PRESENT.** `docs/Spec_003_Outcome_Aware_Evaluation_v1.1.md` -- recovered from this session's own transcript, 2026-09-30. Two original messages: the main text (initially `PROPOSED FOR CLAUDE REVIEW -- DO NOT IMPLEMENT YET`), followed ~16 minutes later by Radu's response to Claude's review questions, carrying the final clarifications/approval before implementation began. |
| **Version** | **v1.1** -- confirmed directly from the recovered text's own header ("IMPLEMENTATION SPECIFICATION #003 v1.1", "Version: 1.1"), not merely inferred from derived docs as before. |
| **Source** | This Claude Code session's transcript. Not Radu's GPT conversation history. |
| **Approval** | **ACCEPTED.** Technical baseline `d889049` (PATCH #003-B). Verdict recorded in commit `266cc6f` ("GPT Review #003 Final verdict", doc-only, immediately after the baseline commit). |
| **Amendments** | PATCH #003-A `203233d` (6 statistical/correctness findings, GPT Review #003 Round 1). PATCH #003-B `d889049` (2 findings, GPT Review #003 Round 2). |
| **Derived documentation** | `docs/spec003_architecture.md`, `spec003_known_limitations.md`, `spec003_test_report.md`, `spec003_examples.md`, `spec003_performance_report.md`, `spec003_multiple_testing_report.md`, `spec003_reproducibility.md`. |
| **Flag** | Text now present but not yet independently verified by Radu, and not yet run through the requirement→code→test correspondence check or the contradiction/ambiguity/testability audit. |

## Spec #004 -- Hypothesis Generation & Strategy Definition

| | |
|---|---|
| **Original contract file** | **PRESENT.** `docs/Spec_004_Hypothesis_Generation_v1.0.md` -- recovered from this session's own transcript, 2026-09-30. Two original messages: the main text (initially `PROPOSED FOR CLAUDE REVIEW -- DO NOT IMPLEMENT YET`), followed ~30 minutes later by Radu's response to Claude's review questions, carrying the final approval before implementation began. |
| **Version** | v1.0, per the recovered text's own header. |
| **Source** | This Claude Code session's transcript. Not Radu's GPT conversation history. |
| **Approval** | **ACCEPTED.** Base implementation `6082215`. PATCH #004-A `feb8470`. Technical baseline at acceptance: PATCH #004-B `d19dd25`. Verdict recorded in commit `74daadc` ("Spec #004 v1.0 ACCEPTED", GPT Review #004 Round 3 closure). |
| **Amendments** | PATCH #004-A `feb8470` (7 findings, GPT Review #004 Round 1). PATCH #004-B `d19dd25` (5 findings, GPT Review #004 Round 2). PATCH #004-C `28473d0` (additive `STOP_MANAGED_INVALIDATION` exit family, entities/validation/fingerprint layer only). |
| **Derived documentation** | `docs/spec004_architecture.md`, `spec004_known_limitations.md`, `spec004_test_report.md`, `spec004_examples.md`, `spec004_agent_interface.md`, `spec004_registry_contract.md`. |
| **Flag** | Text now present, but not yet independently verified by Radu or audited. Separately, and unaffected by the text recovery: **a separate verdict on PATCH #004-C's own implementation has not been identified.** Its 7 tests (TEST 67-73) pass, but green tests are not a verdict. The only "ACCEPTED" text on record covers the *Spec #005 Exit Amendment v1.0 document itself* (commit `2fa5575`, baseline `3cdc532`, dated BEFORE PATCH #004-C `28473d0` or Batch 3 `cb9d67f` were even written) -- that is an acceptance of the contract text, not evidence either way about #004-C's implementation of it. Pending verification of the relevant conversations and delivery before this can be marked either accepted or open. See also "Superseded rules," below, for the SIGNAL_INVALIDATION timing and risk-exit items this spec's own recovered text (including its final approval message) carries. |

## Spec #005 -- Backtesting & Exit Evaluation

| | |
|---|---|
| **Original contract file** | **PRESENT, verbatim.** `docs/Spec_005_Backtesting_Exit_Evaluation_v1.0.md`, committed doc-only at `f477e93` (2026-09-29), supplied directly by Radu into this session. |
| **Version** | v1.0 (base contract) + Exit Amendment v1.0 (`docs/spec005_exit_amendment_v1.0.md`, the additive extension for `STOP_MANAGED_INVALIDATION`). |
| **Source** | Base contract: Radu, pasted/uploaded directly. Amendment: drafted through GPT/Claude review rounds, Radu-approved. |
| **Approval** | Exit Amendment v1.0 (the CONTRACT TEXT) **ACCEPTED** at commit `2fa5575`, technical baseline `3cdc532` at that moment -- i.e. accepted BEFORE its own implementation began. Batch 3 (the `STOP_MANAGED_INVALIDATION` exit engine implementing it, plus "Session Engine & Integration" and "Discovery Integration & Legacy Exits") is **explicitly NOT YET ACCEPTED** -- its closure is Radu's own separate verdict, still pending as of this index. |
| **Amendments** | None beyond the Exit Amendment itself. A further correction chain against the amendment's own MAE/MFE requirements is in progress: `8287ebb` -> `3aae3ef` -> `536bad7` -> `842d278`. **`842d278`'s review is explicitly still open (Radu, 2026-09-30) -- this index does not close it.** |
| **Derived documentation** | `docs/spec005_known_limitations.md`. |
| **Flag** | Was, until this revision, the only spec with its base contract archived verbatim in-repo -- now #001-#004 have their recovered text alongside it, from a different source (this session's transcript, not Radu's own GPT copy or upload). |

---

## Superseded rules found in the recovered text (informational -- reopens nothing)

Reading the recovered #002/#004 text surfaced three rules that were later
changed by downstream specs. The recovered text is preserved exactly as
sent, unedited; nothing here proposes reverting any code or documentation
to the superseded rule, and none of it reopens any existing acceptance.

1. **Holding-domain length.** Spec #002's own header states: "Research
   holding domain downstream: 3-30 trading days." Superseded by Spec #003
   v1.1's own header: "Trading style target: fast swing, aproximativ 1-5
   zile" ("approximately 1-5 days"). The later spec is what the
   implementation actually follows; #002's own figure is historical.

2. **`SIGNAL_INVALIDATION` exit timing.** Spec #004's final approval
   message (`docs/Spec_004_Hypothesis_Generation_v1.0.md`, fragment 2/2)
   states explicitly: *"Exit la close-ul primei bare la care condiția de
   invalidare este observabilă, sau la close-ul `max_holding_bars`,
   oricare survine prima"* -- exit AT THE CLOSE of the bar where
   invalidation is detected (same-bar close), not the next session's
   open. Per Radu's point: the recovered text proves this was an
   **explicit rule**, not merely an ambiguous or undecided field, as it
   might otherwise have been read from the derived docs alone. Spec #005
   base contract section 9's `ExecutionSemanticsProfile` supersedes it:
   `invalidation_fill=NEXT_SESSION_OPEN_AFTER_DETECTION` -- what
   `docs/spec005_exit_amendment_v1.0.md` and the current implementation
   both follow (the exact same-close bug this timing rule would produce
   was fixed at commit `8287ebb`, per Radu's own verdict on `db767c9`).
   The #004-era text itself already flagged the rule as provisional, one
   sentence later: *"#005 va aplica exact timing-ul"* ("#005 will apply
   the exact timing"). **No code change follows from this entry** -- the
   current `NEXT_SESSION_OPEN_AFTER_DETECTION` behavior is what Radu's
   own review already required and what is already implemented; this
   only documents, for the record, that the #004-era assumption was real
   and explicit, not a gap Claude is now free to read either way.
3. **Risk exits.** Spec #004's own section 22.C states: *"RISK EXIT --
   Stop-loss / ATR / trailing stop. Nu îl optimizăm în #004"* ("we do not
   optimize it in #004"), enforced structurally by the spec's own TEST 16
   ("Risk exit disabled in V1"). Later extended -- narrowly and
   additively, not by reopening #004 -- by the Spec #005 Exit Amendment
   v1.0 (PATCH #004-C): `stop_loss`/`partial_profit` fields on the new
   `STOP_MANAGED_INVALIDATION` family only; `risk_exit.enabled` stays
   `false` everywhere else. This extension was already on record in
   `docs/spec004_known_limitations.md`'s "PATCH #004-C partial lift"
   note; the recovered text now additionally confirms the ORIGINAL
   restriction's own exact wording and its own enforcing test.

## Baseline

General accepted baseline remains `3cdc532`, unchanged by this index.
Spec #001/#003/#004 acceptances already on record above are **not**
reopened by anything here. Batch 3 and the `842d278` MAE/MFE review
remain separately, and still, open. Recovering #001-#004's original text
does not change any of that -- it makes the text available to audit, it
is not itself the audit.

## Next steps

1. **Radu**, if he wants an independent second source: locate his own
   GPT-side copies of #001-#004 to cross-check against the transcript
   recovery above (they need not match verbatim word-for-word if the
   content is equivalent, but a material difference would matter).
2. **Claude**, once Radu has looked at the recovered text: run the
   requirement→code→test correspondence check plus the
   contradiction/ambiguity/untestable-requirement audit against each of
   #001-#004, exactly as intended for Spec #005's base contract.
3. **Spec #002's acceptance**: either locate primary evidence of an
   actual acceptance decision, or run a fresh verification now and record
   a new, explicitly dated acceptance -- not a retroactive inference from
   citations, per Radu's instruction.
4. **PATCH #004-C's implementation**: verify against the relevant
   conversations/delivery whether it has its own acceptance, separate
   from the Exit Amendment document's acceptance.
