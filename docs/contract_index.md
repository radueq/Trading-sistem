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
the contradiction/ambiguity/testability audit Radu separately requested --
those still need each spec's actual original text to run against, which
for #001-#004 this repo does not have.

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
carry the same caveat.

---

## Spec #001 -- Data Foundation

| | |
|---|---|
| **Original contract file** | **ABSENT from this repo.** Partial recovery trace only (Radu, 2026-09-30): ChatGPT conversation "Creare Master Context Trading", message at approx. 2026-09-20 13:40 Romania time, titled "IMPLEMENTATION SPECIFICATION #001", v1.0, SS1-29. The recovery returned a reference/summary, not an exportable full body. |
| **Version** | v1.0 (per the recovered title only -- not cross-checked against full original text). |
| **Source** | Radu's GPT (ChatGPT) conversation history. Full export of the original message(s), including final clarifications/approvals, still pending. |
| **Approval** | **ACCEPTED.** `docs/ACCEPTANCE.md`. Technical baseline `918f3f7` (persistence-lifecycle fix). Acceptance recorded in commit `a6514b0` (2026-09-21), Radu sign-off. |
| **Amendments** | PATCH #001-C `aa56bb5` (`split_adjusted_volume`, additive, not a reopening). PATCH #001-D `b1bb301`, accepted at `cfa0809` (`split_adjusted_open/high/low`, additive, not a reopening -- surfaced while scaffolding Spec #005). |
| **Derived documentation** | `docs/architecture.md`, `docs/known_limitations.md`, `docs/test_report.md`, `docs/ACCEPTANCE.md`. |
| **Flag** | Base contract text not archived in-repo -- the above derived docs are Claude's reconstruction from the original requirement as given in chat, not a verbatim copy. Does not reopen the existing acceptance; recorded here as a documentary gap. |

## Spec #002 -- Feature Engine + Outcome-Blind Discovery Engine

| | |
|---|---|
| **Original contract file** | **ABSENT from this repo.** No recovery trace found yet (as of 2026-09-30). |
| **Version** | Unconfirmed. No derived doc ever states a "#002 vX.Y" -- later specs cite it only as "Spec #002 Accepted Baseline" with no version number. Treat as unverified, not as an assumed v1.0. |
| **Source** | Radu's GPT conversation history. Not yet located/exported. |
| **Approval** | **No self-contained acceptance record exists for Spec #002.** Unlike #001/#003/#004, there is no `docs/ACCEPTANCE.md`-equivalent, no "ACCEPTED at commit X" line inside #002's own docs, and no dedicated acceptance-recording commit in git history (`git log` has no such commit for #002, where #001/#003/#004 each have one -- `a6514b0`, `266cc6f`, `74daadc`). Acceptance is only INFERRED by citation from later specs: `docs/spec003_architecture.md` ("Spec #002 Accepted Baseline `4f36708`") and `docs/spec004_known_limitations.md` ("#002 `4f36708`"). |
| **Amendments** | PATCH #002-A `4f36708` (cross-sectional RS eligibility-ordering fix, GPT Review #002 Round 1 mandatory finding). PATCH #002-B `136bf94` (pre-budget `DiscoveryObservation` isolation, resolving Spec #003's own IMPLEMENTATION BLOCKER SS74A). |
| **Derived documentation** | `docs/spec002_architecture.md`, `spec002_known_limitations.md`, `spec002_test_report.md`, `spec002_examples.md`, `spec002_volume_report.md`. |
| **Flag** | Two gaps stack here: the base contract is absent, AND its own acceptance was never separately recorded (only inferable by citation). If Radu confirms the citation chain is accurate, a proper self-contained acceptance record (mirroring `docs/ACCEPTANCE.md`) should be written retroactively for `4f36708` -- independent of, and not blocked on, recovering the original contract text. |

## Spec #003 -- Outcome-Aware Evaluation Engine (Fast-Swing / Bar-Based)

| | |
|---|---|
| **Original contract file** | **ABSENT from this repo.** No recovery trace found yet. |
| **Version** | **v1.1** -- explicit and consistent throughout derived docs (`spec003_architecture.md`, `spec003_known_limitations.md` both header "Spec #003 v1.1"; SS47 cited by number). Per Radu's explicit correction: do not assume v1.0 once the original is recovered -- the implementation itself already tracks v1.1. |
| **Source** | Radu's GPT conversation history. Not yet located/exported. |
| **Approval** | **ACCEPTED.** Technical baseline `d889049` (PATCH #003-B). Verdict recorded in commit `266cc6f` ("GPT Review #003 Final verdict", doc-only, immediately after the baseline commit). |
| **Amendments** | PATCH #003-A `203233d` (6 statistical/correctness findings, GPT Review #003 Round 1). PATCH #003-B `d889049` (2 findings, GPT Review #003 Round 2). |
| **Derived documentation** | `docs/spec003_architecture.md`, `spec003_known_limitations.md`, `spec003_test_report.md`, `spec003_examples.md`, `spec003_performance_report.md`, `spec003_multiple_testing_report.md`, `spec003_reproducibility.md`. |
| **Flag** | Base contract absent. Version v1.1 is confirmed only from derived docs' own headers, not yet cross-checked against an original document. |

## Spec #004 -- Hypothesis Generation & Strategy Definition

| | |
|---|---|
| **Original contract file** | **ABSENT from this repo.** No recovery trace found yet. |
| **Version** | v1.0. |
| **Source** | Radu's GPT conversation history. Not yet located/exported. |
| **Approval** | **ACCEPTED.** Base implementation `6082215`. PATCH #004-A `feb8470`. Technical baseline at acceptance: PATCH #004-B `d19dd25`. Verdict recorded in commit `74daadc` ("Spec #004 v1.0 ACCEPTED", GPT Review #004 Round 3 closure). |
| **Amendments** | PATCH #004-A `feb8470` (7 findings, GPT Review #004 Round 1). PATCH #004-B `d19dd25` (5 findings, GPT Review #004 Round 2). PATCH #004-C `28473d0` (additive `STOP_MANAGED_INVALIDATION` exit family, entities/validation/fingerprint layer only). |
| **Derived documentation** | `docs/spec004_architecture.md`, `spec004_known_limitations.md`, `spec004_test_report.md`, `spec004_examples.md`, `spec004_agent_interface.md`, `spec004_registry_contract.md`. |
| **Flag** | Base contract absent. **PATCH #004-C's own code-level closure is not separately verdicted anywhere** -- its 7 tests (TEST 67-73) pass, but the only "ACCEPTED" text on record covers the *Spec #005 Exit Amendment v1.0 document itself* (commit `2fa5575`, baseline `3cdc532`, BEFORE PATCH #004-C `28473d0` or Batch 3 `cb9d67f` were even written -- that acceptance is of the contract text, not of #004-C's implementation of it). Needs Radu's explicit confirmation that PATCH #004-C's implementation is itself accepted, distinct from the amendment document being accepted. |

## Spec #005 -- Backtesting & Exit Evaluation

| | |
|---|---|
| **Original contract file** | **PRESENT, verbatim.** `docs/Spec_005_Backtesting_Exit_Evaluation_v1.0.md`, committed doc-only at `f477e93` (2026-09-29), supplied directly by Radu into this session. |
| **Version** | v1.0 (base contract) + Exit Amendment v1.0 (`docs/spec005_exit_amendment_v1.0.md`, the additive extension for `STOP_MANAGED_INVALIDATION`). |
| **Source** | Base contract: Radu, pasted/uploaded directly. Amendment: drafted through GPT/Claude review rounds, Radu-approved. |
| **Approval** | Exit Amendment v1.0 (the CONTRACT TEXT) **ACCEPTED** at commit `2fa5575`, technical baseline `3cdc532` at that moment -- i.e. accepted BEFORE its own implementation began. Batch 3 (the `STOP_MANAGED_INVALIDATION` exit engine implementing it, plus "Session Engine & Integration" and "Discovery Integration & Legacy Exits") is **explicitly NOT YET ACCEPTED** -- its closure is Radu's own separate verdict, still pending as of this index. |
| **Amendments** | None beyond the Exit Amendment itself. A further correction chain against the amendment's own MAE/MFE requirements is in progress: `8287ebb` -> `3aae3ef` -> `536bad7` -> `842d278`. **`842d278`'s review is explicitly still open (Radu, 2026-09-30) -- this index does not close it.** |
| **Derived documentation** | `docs/spec005_known_limitations.md`. |
| **Flag** | The only spec where the base contract is actually archived verbatim in-repo -- the pattern to replicate for #001-#004 once Radu supplies them. |

---

## Baseline

General accepted baseline remains `3cdc532`, unchanged by this index.
Spec #001/#003/#004 acceptances already on record above are **not**
reopened by the gaps documented here -- the absence of archived source
text is a documentary gap, recorded explicitly, not a retroactive
challenge to those verdicts. Batch 3 and the `842d278` MAE/MFE review
remain separately, and still, open.

## Next steps (Radu's, not Claude's, to execute)

1. Copy/export the full original message bodies for Spec #001-#004 from
   the GPT conversation history (or from whatever was sent to Claude at
   the time), including the final clarifications and approvals that
   shaped what actually got implemented -- not just the initial draft.
2. Confirm or correct the inferred Spec #002 acceptance chain above
   (baseline `4f36708`) so a proper acceptance record can be written for
   it independent of recovering the original text.
3. Confirm whether PATCH #004-C's own implementation should be treated as
   accepted, distinct from the Exit Amendment document's acceptance.

Once original text is supplied for a spec, Claude will: commit it
verbatim under its own actual version (not assumed v1.0), cross-link it
from that spec's existing derived docs, and then run the
requirement -> code -> test correspondence check plus the contradiction/
ambiguity/untestable-requirement audit Radu requested -- exactly as was
done for Spec #005's base contract at `f477e93`.
