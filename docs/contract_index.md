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
not rename any derived document as if it were a source contract.

**Status of the requirement→code→test correspondence check, stated once
here and not contradicted elsewhere in this document (updated
2026-10-04): Spec #001 and Spec #002 have each been audited in full by
GPT, reconciled against Claude's own independent pass, and closed as
reconciliation rounds (see each matrix's own status line and revision
history -- further findings can still surface later, but the
reconciliation process itself is not left "in progress" for either).
Spec #003 has now also been audited in full by GPT -- all 75 sections,
against package `0c1d3cc` -- delivering six groups of findings (F1-F6)
plus further suspicions/gaps (S1, S2, G1, G2); Claude's own independent
reconciliation against that audit is recorded in
`docs/audit_spec003_requirement_code_test.md`. **As of commit `8a0f152`
(2026-10-04), that reconciliation of the F1-F6 findings themselves is
CLOSED from GPT's side** -- matching #001/#002's own closed rounds, and
unlike the earlier state of this document. This closes the FINDINGS
stage only: **remediation DESIGN for those findings
(`docs/spec003_remediation_proposal_2026-10-04.md`) remains a separate,
OPEN stage** -- several designs, notably F1's OOS-classification
mechanism, have no working answer yet -- and **implementation/
acceptance of any fix is a third, separate stage, NOT AUTHORIZED.**
Spec #004 is not yet audited in full by GPT -- its matrix remains at
the original point-by-point spot-check level. Radu's own contractual
verdict on any finding -- in any of the four matrices -- remains
separate from this technical reconciliation throughout, and has not
been given.** The
matrices exist as
`docs/audit_spec00{1,2,3,4}_requirement_code_test.md` (commit `edf8dbe`,
reclassified per the key below at a later commit -- see each file's own
revision note). Producing and reconciling them is evidence-gathering
Claude and GPT have done; neither substitutes for Radu's own verdict.

**Classification key used in all four matrices (2026-10-03, corrected
2026-10-03):** finding a gap is not the same claim as finding a defect.
Each distinct finding -- a row may raise more than one, and each gets
its own tag rather than the row being forced into a single label -- is
tagged with one of:
- **DEMONSTRATED DEFECT** -- the code does the wrong thing today,
  confirmed by reading it; a concrete failure scenario is real now, not
  hypothetical.
- **SUSPECTED ISSUE -- VERIFICATION PENDING** -- a real red flag in code
  or config (a dead setting, a discarded value, a missing check) whose
  contractual consequence is plausible but not yet fully traced or
  reproduced; worth a targeted check, not yet proven either way.
- **TEST-COVERAGE GAP** -- the mechanism is present and reads correctly
  by inspection; no regression test proves it. This means no defect was
  demonstrated in the verification actually performed -- it does NOT
  mean nothing is wrong; inspection without a test cannot rule out a
  subtle bug the way a test would, and a future regression could slip
  through unnoticed either way. Compliance verifiable by inspection does
  not become "PARTIAL" merely because no dedicated test exists for it --
  that conflation was an earlier round's main correction.
- **KNOWN LIMITATION -- ALREADY DOCUMENTED** -- disclosed elsewhere in
  this project's own documentation (exact citation given); reporting it
  again here is a cross-reference, not a new finding.
- **FUTURE / PROCEDURAL REQUIREMENT** -- the spec text only bites later
  (e.g. before Locked-OOS or live use) or is a human/process rule not
  expressible in code; the current build not yet being exercised against
  it is not a defect in the current build.

**On attributing the verification work itself:** the matrices themselves
and their initial checks against the source (code exists at a given
line, a grep returns zero hits, a field is or isn't populated) were
produced by Claude, not by Radu or by GPT. Separately, GPT -- the same
reviewer role this project has used throughout ("GPT Review #001", "GPT
Review #003 Round 1", etc.) -- has verified specific findings flagged in
its reviews on a point-by-point basis; a full independent re-verification
of every row by GPT has not been completed, **except for Specs #001,
#002, and (as of this revision) #003, where GPT has now each run its
own full row-by-row pass (all 29 rows for #001 on commit `34acd9c`;
all 50 rows for #002 on commit `d289a02`; all 75 rows for #003 on
commit `0c1d3cc`), reconciled against Claude's own independent pass in
`docs/audit_spec001_requirement_code_test.md`,
`docs/audit_spec002_requirement_code_test.md`, and
`docs/audit_spec003_requirement_code_test.md`** (status line at the top
of each document -- #001/#002's reconciliation rounds are closed,
#003's is in progress). Spec #004 remains at the point-by-point level.
Phrases like "Radu-endorsed"
or "Radu caught" overstated Radu's own personal involvement in this
technical work. The corrected framing used from this revision onward:
**the matrices and initial verifications were produced by Claude; GPT
has verified specific findings flagged in reviews on a point-by-point
basis, with full independent verification not yet finished for Spec
#004 (Specs #001, #002, and #003 have each had a full GPT pass
reconciled by Claude, see above -- #001/#002 closed, #003 in progress);
Radu's own verdict on what any of this means contractually remains
separate** and
is not implied by either. This does not apply to historical messages reproduced verbatim
(e.g. in `docs/evidence_spec002_acceptance_message.md`,
`docs/evidence_004c_verdict_status.md`, or quotes from the recovered
`Spec_00X_*.md` files) -- those remain exactly what Radu actually sent,
unedited.

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

**2026-10-03 update -- acceptance evidence for #002 and PATCH #004-C
located directly in this session's own transcript, and a "Master
Context" gap surfaced.** Searching the same transcript used to recover
#001-#004's text (not Radu's GPT library) turned up: (1) Radu's own
explicit acceptance message for Spec #002, and (2) Radu's own explicit
statement, as of 2026-09-28, that PATCH #004-C's implementation had not
yet received a verdict -- a bounded, dated claim, not proof that no
verdict exists anywhere; Claude did not find a later one in the
transcript it checked. Both are quoted in full in standalone files
(`docs/evidence_spec002_acceptance_message.md`,
`docs/evidence_004c_verdict_status.md`) and referenced with exact
transcript line/timestamp in their respective rows below -- this is
primary evidence Claude located, not an inference, but it is still
Claude's own search of its own transcript, not something Radu has
independently checked. Separately: "Master
Context" (referenced inside the recovered #001/#002 text itself, e.g.
"Master Context v2.0 -- Baseline 001: LOCKED") was searched for across
the entire transcript and found to exist ONLY as these short references
-- its own full text was never pasted into this Claude Code session, in
any version, at any point. See the new "Master Context" entry below.

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
| **Flag** | Text now present but NOT YET independently verified by Radu ("byte-for-byte" is Claude's description of its own extraction process, not something Radu can confirm without the raw transcript fragments himself). Correspondence matrix: `docs/audit_spec001_requirement_code_test.md` -- status per the top of this document. Does not reopen the existing acceptance. See also "Superseded rules," below, for the SIGNAL_INVALIDATION timing and risk-exit items this spec's recovered text touches. |

## Spec #002 -- Feature Engine + Outcome-Blind Discovery Engine

| | |
|---|---|
| **Original contract file** | **PRESENT.** `docs/Spec_002_Feature_Engine_Discovery_v1.0.md` -- recovered from this session's own transcript, 2026-09-30. Sent as a single message, already final (self-labeled "Status: APPROVED FOR IMPLEMENTATION"). |
| **Version** | v1.0, per the recovered text's own header. |
| **Source** | This Claude Code session's transcript. Not Radu's GPT conversation history. |
| **Approval** | **ACCEPTED -- primary evidence now located (2026-10-03).** Found directly in this session's own transcript, Radu's own words, verbatim: *"Decizia mea / Spec #002 Discovery Engine = ACCEPTED la commit 4f36708. / Nu mai cer PATCH #002-B. / Dar înainte să pornim primul backtest real trebuie să închidem explicit: / Data Foundation: split-adjusted volume / corporate-action-consistent historical volume."* (transcript timestamp `2026-09-21T17:36:08Z`). This resolves the earlier "cited only, primary evidence not recovered" status -- it is a genuine, explicit acceptance decision, not an inference from later specs' citations. Note Radu's own "Nu mai cer PATCH #002-B" (not requesting PATCH #002-B) was superseded days later by a *different* trigger -- Spec #003's own IMPLEMENTATION BLOCKER SS74A -- which is why PATCH #002-B exists anyway; this is not a contradiction, just a later, separate reason. The full message is reproduced in `docs/evidence_spec002_acceptance_message.md` -- not only quoted here. #002 still has no self-contained `docs/ACCEPTANCE.md`-equivalent file of its own the way #001/#003/#004 do, but per GPT's correction (relayed by Radu), that file is optional now that this index points clearly to the full message; its absence is documentation housekeeping, not missing evidence. |
| **Amendments** | PATCH #002-A `4f36708` (cross-sectional RS eligibility-ordering fix, GPT Review #002 Round 1 mandatory finding). PATCH #002-B `136bf94` (pre-budget `DiscoveryObservation` isolation, resolving Spec #003's own IMPLEMENTATION BLOCKER SS74A -- a new trigger arising after the SS2 acceptance above, not a reopening of it). |
| **Derived documentation** | `docs/spec002_architecture.md`, `spec002_known_limitations.md`, `spec002_test_report.md`, `spec002_examples.md`, `spec002_volume_report.md`. |
| **Flag** | Base text present; acceptance now evidenced (see above, and see `docs/evidence_spec002_acceptance_message.md` for the full source message). Correspondence matrix: `docs/audit_spec002_requirement_code_test.md` -- status per the top of this document. No dedicated `docs/ACCEPTANCE.md`-equivalent file exists for #002, but per GPT's correction (relayed by Radu) that is optional documentation housekeeping now that this index points clearly to the full message -- not an open gap. See also "Superseded rules," below, for the holding-domain figure this spec's own text carries. |

## Spec #003 -- Outcome-Aware Evaluation Engine (Fast-Swing / Bar-Based)

| | |
|---|---|
| **Original contract file** | **PRESENT.** `docs/Spec_003_Outcome_Aware_Evaluation_v1.1.md` -- recovered from this session's own transcript, 2026-09-30. Two original messages: the main text (initially `PROPOSED FOR CLAUDE REVIEW -- DO NOT IMPLEMENT YET`), followed ~16 minutes later by Radu's response to Claude's review questions, carrying the final clarifications/approval before implementation began. |
| **Version** | **v1.1** -- confirmed directly from the recovered text's own header ("IMPLEMENTATION SPECIFICATION #003 v1.1", "Version: 1.1"), not merely inferred from derived docs as before. |
| **Source** | This Claude Code session's transcript. Not Radu's GPT conversation history. |
| **Approval** | **ACCEPTED.** Technical baseline `d889049` (PATCH #003-B). Verdict recorded in commit `266cc6f` ("GPT Review #003 Final verdict", doc-only, immediately after the baseline commit). |
| **Amendments** | PATCH #003-A `203233d` (6 statistical/correctness findings, GPT Review #003 Round 1). PATCH #003-B `d889049` (2 findings, GPT Review #003 Round 2). |
| **Derived documentation** | `docs/spec003_architecture.md`, `spec003_known_limitations.md`, `spec003_test_report.md`, `spec003_examples.md`, `spec003_performance_report.md`, `spec003_multiple_testing_report.md`, `spec003_reproducibility.md`. |
| **Flag** | Text now present but not yet independently verified by Radu. Correspondence matrix: `docs/audit_spec003_requirement_code_test.md` -- GPT audited all 75 sections independently (package `0c1d3cc`), reconciled by Claude (Top Findings 11-19: F1-F6, S1/S2, G1/G2). **As of `8a0f152`: findings reconciliation CLOSED (GPT's side); remediation design (`docs/spec003_remediation_proposal_2026-10-04.md`) OPEN; implementation/acceptance NOT AUTHORIZED** -- three distinct stages, only the first done. The historical `ACCEPTED` status below (baseline `d889049`) is preserved as a record, not revoked or re-affirmed by this audit. |

## Spec #004 -- Hypothesis Generation & Strategy Definition

| | |
|---|---|
| **Original contract file** | **PRESENT.** `docs/Spec_004_Hypothesis_Generation_v1.0.md` -- recovered from this session's own transcript, 2026-09-30. Two original messages: the main text (initially `PROPOSED FOR CLAUDE REVIEW -- DO NOT IMPLEMENT YET`), followed ~30 minutes later by Radu's response to Claude's review questions, carrying the final approval before implementation began. |
| **Version** | v1.0, per the recovered text's own header. |
| **Source** | This Claude Code session's transcript. Not Radu's GPT conversation history. |
| **Approval** | **ACCEPTED.** Base implementation `6082215`. PATCH #004-A `feb8470`. Technical baseline at acceptance: PATCH #004-B `d19dd25`. Verdict recorded in commit `74daadc` ("Spec #004 v1.0 ACCEPTED", GPT Review #004 Round 3 closure). |
| **Amendments** | PATCH #004-A `feb8470` (7 findings, GPT Review #004 Round 1). PATCH #004-B `d19dd25` (5 findings, GPT Review #004 Round 2). PATCH #004-C `28473d0` (additive `STOP_MANAGED_INVALIDATION` exit family, entities/validation/fingerprint layer only). |
| **Derived documentation** | `docs/spec004_architecture.md`, `spec004_known_limitations.md`, `spec004_test_report.md`, `spec004_examples.md`, `spec004_agent_interface.md`, `spec004_registry_contract.md`. |
| **Flag** | Text now present but not yet independently verified by Radu. Correspondence matrix: `docs/audit_spec004_requirement_code_test.md` -- status per the top of this document. Separately, and unaffected by the text recovery: **PATCH #004-C's own implementation has a confirmed-pending verdict, sourced precisely.** Found in this session's own transcript, Radu's own words, verbatim, immediately after a Batch 3 CHANGES-REQUIRED verdict: *"Nu închidem Batch 3 și nu promovăm încă baseline-ul `3cdc532`. PATCH #004-C rămâne separat pentru verdict; constatările de mai sus vizează Batch 3."* (transcript timestamp `2026-09-28T16:08:13Z`; full message reproduced in `docs/evidence_004c_verdict_status.md`). **Separate verdict still pending as of the quoted date; Claude did not identify a later one in the transcript checked** -- this is a bounded claim about what was searched, not proof that no later verdict exists anywhere. The only "ACCEPTED" text on record remains the *Spec #005 Exit Amendment v1.0 document itself* (commit `2fa5575`, baseline `3cdc532`, dated BEFORE PATCH #004-C `28473d0` was even written) -- an acceptance of the contract text, not of #004-C's implementation. Its 7 tests (TEST 67-73) pass, but green tests are not the verdict Radu is withholding. See also "Superseded rules," below, for the SIGNAL_INVALIDATION timing and risk-exit items this spec's own recovered text (including its final approval message) carries. |

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

## Master Context (project-level, precedes all numbered specs)

| | |
|---|---|
| **Original contract file** | **ABSENT -- no partial trace either, unlike #001.** Searched exhaustively across the entire transcript (its full length at time of search, 2026-10-03): the phrase appears in exactly 4 places, and in every one it is a short reference to an already-existing, already-decided document, never the document's own text. |
| **What the references say** | Spec #001's own final approval message (2026-09-20): *"Master Context v2.0 -- Baseline 001: LOCKED"* -- stated as a precondition already satisfied before Spec #001's own approval, not something being decided in this session. Spec #002's own recovered text (SS4): *"Transitions must use the dimensional representation already accepted in Master Context"* -- again treated as pre-existing, external, settled. No "Master Context v1.0" or any other version is referenced anywhere; v2.0 is the only version this transcript ever names. |
| **Version** | v2.0, per the one reference above. Nothing else about it (scope, sections, date) is recoverable from this transcript. |
| **Source** | Almost certainly Radu's own GPT conversation history, likely the same "Creare Master Context Trading" conversation he named as the source of #001's recovered trace -- that title is a strong match for a document literally called "Master Context." Not confirmed; Claude cannot access that conversation. |
| **Approval** | Unknown from this transcript beyond "LOCKED" as of 2026-09-20. |
| **Amendments** | Unknown. |
| **Derived documentation** | None -- no `docs/*.md` in this repo claims to be derived from or to document Master Context specifically; the individual spec architecture notes each stand on their own. |
| **Flag** | This is a DEEPER gap than #001-#004's, not a parallel one: Master Context is the document the specs themselves say they already depend on and that any contradiction/ambiguity audit of #001-#004 would ultimately trace back to, and this repo has never had any version of it, not even a fragment. If Radu can locate and supply it, it belongs in this inventory as its own entry, parallel to the specs; until then, any "contradiction" found between a spec and Master Context cannot be checked from this repo at all -- only contradictions among the specs' own recovered texts, or between a spec and the actual code, are checkable today. |

## Amendments and contractual changes -- one exhaustive search, one non-exhaustive list

**Corrected framing (Radu, 2026-10-03): a keyword search for the word
"amendament" only finds documents that use that word -- it does not
inventory every contractual change.** The accurate statement is: **one
standalone document titled "Amendment" has been identified (that search
WAS exhaustive); contractual changes are also tracked through approved
clarifications/corrections within the conversation, not only through
documents bearing that title (that list is NOT claimed exhaustive --
see below).**

**The one standalone "Amendment" document (exhaustive search):** the
Spec #005 Exit Amendment v1.0 (`docs/spec005_exit_amendment_v1.0.md`),
already tracked in the Spec #005 row above. Every occurrence of
"amendament"/"amendment" in the transcript (42 hits across user
messages) refers to this same document, or is this index's/Radu's own
recent discussion of it.

**Contractual changes carried by approval/clarification messages
instead, each already cross-referenced elsewhere in this project's own
documentation (not a new finding, collected here for completeness):**

- **#002's pre-budget `DiscoveryObservation` interface** (PATCH #002-B,
  `136bf94`) -- Discovery was required to expose a NEW interface (data
  available before Candidate Budget reduction) that its own original
  text did not specify; settled via Radu's clarification responding to
  Spec #003's own IMPLEMENTATION BLOCKER SS74A, not via a document
  titled "Amendment."
- **#003's statistical-method decisions** -- e.g. the baseline changed
  from a plain eligible-universe distribution to the
  `TEMPORALLY_STRATIFIED_ELIGIBLE_BASELINE`, and the standardized-effect
  formula fixed to the robust `median_diff/(baseline_IQR/1.349)` --
  both real changes to what #003's contract requires, settled by Radu's
  approval within the conversation (see `docs/audit_spec003_
  requirement_code_test.md` rows 33/38 for where the implementation
  reflects them), never issued as a separate amendment document.
- **#005's SIGNAL_INVALIDATION timing** -- already documented under
  "Superseded rules" below: #004's same-close rule was superseded by
  #005 base contract section 9's `NEXT_SESSION_OPEN_AFTER_DETECTION`,
  carried by #005's own base specification text, not by an amendment to
  #004.

This list is cross-referenced from material Claude already had, not the
result of a fresh, exhaustive search for every clarification that ever
changed a requirement -- unlike the literal-word search above, it is not
claimed to be complete. PATCH #001-C/D, #002-A/B, #003-A/B, #004-A/B
(listed under each spec's own "Amendments" row above) are GPT-review-
round fixes against an already-accepted spec's *code*, distinct again
from both categories here, which are about what the *contract* itself
requires.

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

1. **Independent audit track in progress ("Audit independent #001-#004",
   Radu's instruction, 2026-10-03) -- Master Context does not block this;
   only findings that would themselves depend on its text would be, and
   none have arisen so far.** Matrices originally produced by 4 parallel
   Claude research passes, each spot-checked (not fully re-verified) by
   Claude before being written up. This track replaces that spot-check
   with a full, row-by-row independent re-verification, spec by spec,
   starting with #001.
   - **Spec #001: two rounds done (2026-10-03).** Round 1 (Claude, solo):
     every file in `src/data_foundation/` and all 17 of its test files
     independently read and traced; found the TEST 10 AST-scan scope gap
     (SS10-11 enforcement cannot see the real downstream packages --
     `backtest/`, `discovery/`, `evaluation/`, `hypothesis/` -- where
     SS10's named consumers now live; one licensed exception already
     exists at `src/backtest/data/snapshot.py`, Spec #005 SS6's own
     carve-out, with nothing structurally confirming it's the only one).
     Round 2 (GPT's own independent pass over the same matrix on
     `34acd9c`, reconciled by Claude): **two further findings, both
     independently reproduced by Claude directly against the real code
     before being written up -- the first two DEMONSTRATED DEFECT
     entries in this whole audit track.** (1) The PIT gateway's derived
     `pit_status` is correct, but `PITCorporateAction`/`get_data()`
     embed the full raw `CorporateAction` row alongside it, so a
     consumer reading `.action.source_status` directly can see a future
     cancellation before the derived status says it's knowable --
     neither TEST 9 nor TEST 13 asserts on the raw embedded fields, only
     on the derived ones, so this was invisible to the suite. (2)
     `ingestion.ensure_security()` discards the adapter's own
     `source_security_id` and persists the raw ticker instead, breaking
     SS3.1's provider-ID-to-security_id mapping whenever they differ --
     invisible today only because the one implemented adapter (yfinance)
     happens to set its own `source_security_id` equal to the ticker.
     Plus three secondary corrections: `DUPLICATE_BAR`/`SOURCE_DISCREPANCY`
     have no detection code at all (not merely untested, as this
     document previously said); TEST 12 checks self-consistency against
     its own fixture, not the "independent reference" SS23 calls for;
     SS20's provenance claim is narrowed given finding (2). See
     `docs/audit_spec001_requirement_code_test.md`'s revised Top
     Findings 1-2 (new) and 4-6, 14 for full detail and reproduction.
     Neither DEMONSTRATED DEFECT has been fixed -- documentary only, per
     Radu's instruction.
   - **Spec #002: two rounds done (2026-10-04).** Round 1 (Claude alone):
     all 18 files in `src/discovery/`, all 4 config YAML files,
     `config/loader.py`, and both structural AST-scan tests read in
     full; concluded "no new DEMONSTRATED DEFECT found" -- **that
     conclusion was wrong.** Round 2 (GPT's own full pass over all 50
     rows on `d289a02`, reconciled by Claude): two further DEMONSTRATED
     DEFECTs Claude's round 1 missed despite having already read the
     exact files involved -- (1) `engine.py`'s `_price_series_to_df()`
     mixes raw open/high/low with split-adjusted close in the same bar,
     for every bar still carrying a non-1.0 split factor. The mismatch
     is NOT a one-time boundary event -- every pre-split historical bar
     already has raw high/low paired with an adjusted close scaled by
     the same constant factor as every other pre-split bar, so ATR's
     true-range calculation is already wrong throughout the pre-split
     history. Once Wilder's recursive smoothing is seeded from that
     already-wrong history, the accumulated error simply persists,
     decaying slowly, across the otherwise-correct post-split sessions
     that follow. Demonstrated at two separate points: Claude's own
     reproduction (AAPL_SPLIT_2020), decaying 305→244→196→157→126→102
     across five sessions immediately after its own split; GPT's own
     probe (an 80-observation synthetic fixture, 4-for-1 split at index
     64), measured at its own last observation -- 16 observations
     starting with the split session itself, inclusive (indices
     64-79): ATR_pct=0.94 against a coherent ~0.02 for that same
     fixture -- one specific value in one specific scenario, not a
     claim about every session. Already disclosed as a known limitation
     in `docs/spec005_known_limitations.md:127-135`, just never carried
     into this matrix's own rows); (2) `config/features.yaml`'s
     `relative_strength.driving_return_window` is declared configurable
     but never read -- `engine.py` hardcodes `"relative_return_63d"`
     regardless of the config value (contrast with `momentum.py`, which
     correctly reads its own analogous key). Two of Claude's own
     SUSPECTED ISSUE findings (SS15 normalization-type absent from
     output; SS30/SS32 discarded per-feature status) promoted to
     DEMONSTRATED DEFECT with concrete reproduction. TEST 17/18's AST
     guards shown to have confirmed bypasses (TEST 17 never inspects
     import statements at all; TEST 18 is fooled by
     `from X import Y as Z` form) beyond the identifier-only point
     already recorded. TEST 18's `src/discovery/`-only scope itself is
     still NOT the same class of gap as Spec #001's TEST 10 -- GPT's own
     report agrees with that distinction explicitly. See
     `docs/audit_spec002_requirement_code_test.md`'s own status line
     and revised Top Findings 1-5.
   - **Spec #003: now started this way (2026-10-04).** GPT's full
     75-section independent audit against `0c1d3cc` delivered six
     groups of findings (F1-F6: incomplete OOS isolation/knowledge-time
     leakage into Development; frozen-signature-set integrity gaps;
     reported-vs-tested population mismatch in the stratified baseline
     comparison; zero-weight-bin IQR pooling; within-bin raw-row
     weighting contradicting amendment SS74C's own text) plus S1/S2/G1/G2
     suspicions and gaps, all independently reproduced by Claude. See
     `docs/audit_spec003_requirement_code_test.md`'s own status line and
     Top Findings 11-19. **As of `8a0f152`: findings reconciliation
     CLOSED (GPT's side); remediation design
     (`docs/spec003_remediation_proposal_2026-10-04.md`) remains OPEN --
     F1's own OOS-classification mechanism has no working design yet;
     implementation/acceptance of any fix is NOT AUTHORIZED.**
   - **Spec #004: not yet started this way.** Still at the original
     spot-check level; next in this track.
   Radu's own contractual verdict on any finding remains separate from
   this technical re-verification throughout.
2. **Primary evidence located for both open acceptance questions, each
   now backed by a standalone source document, not just a quoted
   excerpt:** `docs/evidence_spec002_acceptance_message.md` and
   `docs/evidence_004c_verdict_status.md`. Both still Claude's own
   transcript search -- see the precise, bounded wording in each spec's
   own row above (not "proven absent," but "pending as of the date
   checked, nothing later found").
3. **Open: Master Context.** Absent from this repo and from Claude's own
   search of this transcript (see its own entry above) -- the one item
   in this whole inventory Claude cannot progress further on its own.
   Radu has separately searched his own Library and found only
   references there too, not the full document -- that does not prove
   the document doesn't exist in the original conversation, only that
   neither search has located it yet. Needs Radu to locate and supply it
   from that original conversation if he wants it included.
4. **Open, if Radu wants it: an independent second source.** Locate his
   own GPT-side copies of #001-#004 to cross-check against the transcript
   recovery above (they need not match verbatim word-for-word if the
   content is equivalent, but a material difference would matter).
5. **Open, documentation housekeeping:** write a self-contained
   `docs/ACCEPTANCE.md`-equivalent for Spec #002, quoting the acceptance
   message now on record -- mirroring what #001/#003/#004 already have.
