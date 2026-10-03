# Spec #001 -- Requirement -> Code -> Test Correspondence Matrix

**Status: background-agent output, partially spot-checked by Claude, NOT
independently verified by Radu.** Produced by a Claude subagent tasked
with reading `docs/Spec_001_Data_Foundation_v1.0.md` section-by-section
and citing exact `src/`/`tests/` evidence for each of the 29 sections.

**Revision note (2026-10-03):** GPT verified two concrete misclassifications
in the first version of this document and a general pattern behind them;
Radu's own verdict on these findings remains separate from this
technical check. Both are fixed below regardless, with the
classification key from `docs/contract_index.md` now applied to every
row and finding:
1. SS9's row and Top Finding 2 (originally) claimed `STATUS_CONFLICT`
   overlapping-window detection would "silently pass QA undetected."
   **Wrong**: the detection code exists and is active
   (`qa/engine.py:134-139`). The justified finding is a missing
   regression test for that existing mechanism, not an absent one --
   now tagged **TEST-COVERAGE GAP**, not a defect.
2. Top Finding 3 (originally) presented the QA `computed_at`/knowledge-
   time gap as a new discovery. **It is not new**: it is already
   disclosed in `docs/known_limitations.md:260-279`, flagged by GPT
   Review #001 on 2026-09-21, classified `PENDING` there, with the exact
   same "must be resolved before Discovery Engine or any downstream
   research module is approved to consume `qa_pass`" condition already
   on record. Retagged **KNOWN LIMITATION -- ALREADY DOCUMENTED**.
3. General correction applied throughout: several rows below had marked
   "PARTIAL" for a requirement that is, on inspection, fully satisfied by
   the code -- with the only real gap being the absence of a dedicated
   regression test. Compliance verifiable by inspection is not
   "PARTIAL" just because no test exists for it; those rows now read
   "MET (by inspection)" with a separate **TEST-COVERAGE GAP** tag.

**Claude's own spot-check on 3 of the agent's highest-impact claims, done
directly against the source (not re-trusting the agent):**
1. `repository.get_security_by_provider_id` (`src/data_foundation/model/repository.py:62`) has exactly one occurrence in the whole repo -- its own definition. **Confirmed dead code, exactly as the agent claims.**
2. `pit/access.py:311` filters QA rows by `r.date <= as_of` only; `computed_at` exists on the QA result entity/schema and is populated at insert time (`qa/engine.py:165`, `schema.sql:77,155`) but is never checked against `as_of` in that filter. **Confirmed the mechanism Claude's own known-limitation cross-reference (above) is about.**
3. `tests/test_10_direct_access.py` does contain the AST-based import-graph scan the agent describes (`ALLOWED_DIRS`, `_imports_repository`, `test_no_module_outside_allowed_layers_imports_repository_directly`). **Confirmed as described.**
4. (2026-10-03) `qa/engine.py:134-139` -- `STATUS_CONFLICT` detection over `listing_status_history` windows. **Confirmed present and active**, contradicting the original Top Finding 2's "silently pass undetected" framing.
5. (2026-10-03) `docs/known_limitations.md:260-279` -- the QA `computed_at`/knowledge-time gap, with the exact pre-research-grade condition. **Confirmed already documented**, contradicting the original Top Finding 3's "new discovery" framing.

All five held up. The rest of the table below was not independently
re-verified line-by-line by Claude; treat citations as agent-reported
until Radu or a further pass checks them.

Full suite for this spec's own tests: **34 passed, 1 skipped** (`tests/test_01_*.py` through `tests/test_17_*.py`; skip is TEST 8, `PENDING_LEVEL_2_DATA`, already an approved deferral).

---

## Section-by-section table

| # | Requirement (paraphrase) | Code location | Test location | Status |
|---|---|---|---|---|
| 1 | Build a standardized, auditable, PIT-safe data foundation; no signals/indicators/edge/trade decisions | `src/data_foundation/{adapters,model,pit,qa,storage}` (whole tree); grep confirms no trading-signal/indicator/alpha-score concepts | No dedicated test | **MET (by inspection)** [TEST-COVERAGE GAP: no structural/AST guard against future scope creep, unlike SS10/11's] |
| 2 | Separate Data Quality (in scope) from Universe Eligibility (out of scope) | `qa/engine.py:43-46`, `qa/config/severity_mapping.yaml:1-6`; grep confirms no `min_price`/`ADV`/`market_cap`/`spread_limit` | none | **MET (by inspection)** [TEST-COVERAGE GAP: same pattern as SS1] |
| 3 | Data model = distinct components; 3.1 Security Master fields | `storage/schema.sql:17-157` (7 tables); `model/entities.py:54-62` (`SecurityMaster` matches spec fields) | `tests/test_01_ohlc_integrity.py` and most others exercise it incidentally | MET [see Finding 5 -- SUSPECTED ISSUE on the provider-id resolver, a separate point from this row] |
| 4 | Symbol History is temporal; reuse must not merge histories | `model/entities.py:65-72`; `pit/access.py:192-207` | `tests/test_05_ticker_change.py`, `tests/test_06_ticker_reuse.py` (both sub-cases) | MET |
| 5 | Price History minimal schema; raw never overwritten by adjusted | `model/entities.py:75-85`; `model/repository.py:132-150` (`INSERT OR IGNORE`, no update path) | `tests/test_02_split_correctness.py`, `tests/test_03_dividend_handling.py` | MET |
| 6 | Distinguish raw/split-adjusted/total-return; explicit methodology; provider's own adjusted kept separate | `model/adjustment_engine.py:1-40,65-92`; `pit/access.py:257-305`; provider-adjusted close never used as input | Split-adjustment tested (`test_02`) | **MET** -- the contractual requirement (explicit methodology, no confusion with provider's own adjusted) is satisfied; the total-return field is itself marked `EXPERIMENTAL_NOT_APPROVED_FOR_RESEARCH`, which IS the explicit-methodology discipline the section calls for [TEST-COVERAGE GAP: the formula's own arithmetic has no correctness test, independent of its research-approval status] |
| 7 | Corporate Actions stored separately; announcement != effective date | `storage/schema.sql:108-121`; `model/entities.py:17-24,101-125` (all 7 `ActionType` candidates) | `tests/test_11_corporate_action_timing.py` | MET for SPLIT/REVERSE_SPLIT/DIVIDEND (storage separation and announcement != effective date both hold). **SUSPECTED ISSUE -- VERIFICATION PENDING** for the other 4: `MERGER/ACQUISITION/SPINOFF/OTHER` exist only as enum values, with no adapter ever producing them -- whether SS7's "action_type candidates" requirement is satisfied by enum-presence alone is a contractual reading for Radu, not something this audit can settle by inspection |
| 8 | Corporate Action Status candidates; `UNRESOLVED` = genuine ambiguity, not "announced but not yet effective" | `pit/access.py:90-116`; `entities.py:35-40` (4 of 5 candidates); `qa/engine.py:125-132` (`CORPORATE_ACTION_UNRESOLVED` reason code, narrow/correct-looking by inspection) | ANNOUNCED/EFFECTIVE/CANCELLED tested; `CORPORATE_ACTION_UNRESOLVED` reason-code mechanism itself untested | Reason-code mechanism: **MET (by inspection)** [TEST-COVERAGE GAP, including the specific "don't false-flag a valid future action" case the spec names]. Separately: `CONFIRMED` status [**KNOWN LIMITATION -- ALREADY DOCUMENTED** in `docs/known_limitations.md`]; status-level `UNRESOLVED` [**SUSPECTED ISSUE -- VERIFICATION PENDING**, not disclosed anywhere as a gap] |
| 9 | Listing/Status History; `delisting_reason` audit-only | `model/entities.py:27-32,128-143` (all 5 candidates defined); `pit/access.py:216-242` (`get_listing_status_as_of` -- generic date-windowed lookup, not special-cased per status value) | Only `ACTIVE`/`DELISTED` ever exercised | **MET (by inspection: lookup logic is status-agnostic by design)** [TEST-COVERAGE GAP: `HALTED`/`SUSPENDED`/`PRE_IPO` transitions never exercised by any test] |
| 10 | All research-consumer access via PIT gateway `get_data(as_of=X)` | `pit/access.py:308-322` | `tests/test_10_direct_access.py` -- real AST scan of the import graph | MET |
| 11 | PIT layer is the single gateway; storage/adapter tests may inspect storage directly | Same as SS10; carve-out documented `model/repository.py:23-27` | Same test + legitimate direct-construction tests (`test_13`/`test_14`) | MET |
| 12 | Event date vs information-availability date distinguished; enforced by access layer not deletion | `pit/access.py:1-74,90-142` | `tests/test_09_pit_look_ahead.py`, `tests/test_13_knowledge_time_policy.py` | MET |
| 13 | QA produces `qa_pass` + `reason_codes[]` + `severity[]` (list-valued, not enum) | `model/entities.py:146-153`; `qa/engine.py:166-176` (list-typed fields by design) | Structure proven throughout | **MET (structure)** [TEST-COVERAGE GAP: no test exercises >1 simultaneous code on one date] |
| 14 | 13 named, extensible QA reason codes | `qa/reason_codes.py:7-20` (all 13 present, each with detection logic in `qa/engine.py`) | Only 4/13 ever triggered by a test (`MISSING_BAR`, `OHLC_INVALID`/`NEGATIVE_PRICE`, `IDENTIFIER_CONFLICT`) | **MET (all 13 implemented)** [TEST-COVERAGE GAP for the other 9 -- see Finding 1; correctness beyond inspection is unverified for those 9, which is why this is a test gap and not a confirmed MET] |
| 15 | Severity levels; ERROR->`qa_pass=FALSE` fixed; mapping externally configurable | `qa/reason_codes.py:23-26`; `qa/engine.py:169`; `qa/config/severity_mapping.yaml` (real external file, not hardcoded) | Fixed-ERROR rule tested | **MET (by inspection: real YAML, loaded, not hardcoded)** [TEST-COVERAGE GAP: no test swaps the mapping to demonstrate the configurable behavior actually changes] |
| 16 | Test fixtures marked `TEST_CONFIG`, never `DEFAULT_TRADING_RULES` | `tests/fixtures/market_data.py:1-9` (explicit docstring) | Same file consumed by every test | MET |
| 17 | No silent forward-fill; missing data detected/kept/flagged | `model/repository.py:132-150` (no fill logic); `qa/engine.py:100-105` | `tests/test_07_missing_data.py` | MET |
| 18 | Provider Adapter contract: map, convert, declare unavailable, never invent, preserve metadata | `adapters/base.py:28-73`; `adapters/yfinance_adapter.py:58-163` | Exercised via `tests/fixtures/fake_yfinance.py` across several tests | MET (bare `None` on 2 of 3 carriers does signal unavailability) [**SUSPECTED ISSUE -- VERIFICATION PENDING**: whether `None` alone satisfies SS18's literal "declare unavailable fields" as explicitly as `RawSecurityInfo`'s own named list does, for the other two carriers, is a contractual reading for Radu] |
| 19 | No provider-name branching outside adapters | `adapters/base.py:18`; grep confirms zero violations | **No structural test**, unlike the analogous SS10/11 AST scan | **MET (by inspection)** [TEST-COVERAGE GAP: no AST/structural guard -- the same pattern Radu's STATUS_CONFLICT correction applies to] |
| 20 | Full provenance retrievable and traceable | `model/entities.py:54-125` (provider/id/timestamps present and populated on every table) | `tests/test_14_cancelled_action_adjustment.py` touches audit-trail correctness | **MET (by inspection: all provenance fields present and populated)** [TEST-COVERAGE GAP: no single test traces a QA anomaly end-to-end back to its source in one assertion] |
| 21 | Three data levels; Level 1 = schema/adapters/PIT/QA only | Pervasive "Level 1" framing in docstrings | `tests/test_08_provider_consistency.py` -- explicit, visible `PENDING_LEVEL_2_DATA` skip | MET -- honest, visible, Radu-approved deferral |
| 22 | Provider bake-off before Level-3 provider choice | NOT FOUND | NOT FOUND | **FUTURE / PROCEDURAL REQUIREMENT** -- explicitly a pre-Level-3 gate, not a Level 1 deliverable; absence here is expected, not a defect in this build |
| 23 | 12 mandatory PASS/FAIL tests | One test file per requirement, `test_01`-`test_12` | 11/12 run and pass; TEST 8 is the SS21-approved `PENDING_LEVEL_2_DATA` | MET -- the one non-PASS is the already-approved deferral from SS21, not an independent gap |
| 24 | 12 acceptance criteria + mandatory suite pass | See rows above | Same | Historical acceptance preserved (`a6514b0`); full re-verification of all 12 criteria against this matrix is not finished; the open findings on individual criteria (SS8, SS14, SS20) are listed separately above and in Top Findings, not resolved by this row |
| 25 | Out-of-scope items must not appear in this module | Grep confirms no hits | No automated guard | **MET (by inspection)** [TEST-COVERAGE GAP: same no-guard pattern as SS1/SS2] |
| 26 | Correctness/auditability before performance; no premature optimization | `storage/db.py:1-19` (plain sqlite3, explicit rationale); `schema.sql:9-15` | Not mechanically testable | **FUTURE / PROCEDURAL REQUIREMENT** -- a qualitative engineering philosophy with no pass/fail predicate, not an implementation gap |
| 27 | Deliverables A-E (code, tests, test report, architecture note, known limitations) | All 5 present and substantive | N/A | MET |
| 28 | "IMPLEMENTATION BLOCKER" process rule (stop, report, wait) for architectural changes | One documented real instance: the PATCH #001-D blocker (`docs/test_report.md:93`), correctly followed | Not testable by pytest -- a human/process rule | **FUTURE / PROCEDURAL REQUIREMENT** |
| 29 | Next Gate: review chain -> ACCEPTED -> next spec begins | `docs/ACCEPTANCE.md` documents this chain having occurred (`918f3f7`) | N/A | Document-completeness issue, not a code finding: the recovered source text itself ends mid-sentence ("începem proiectarea:") -- already flagged in `docs/contract_index.md`'s SS29 completeness caveat, not re-litigated here |

---

## Top findings (highest-impact, reclassified)

1. **[TEST-COVERAGE GAP]** 9 of 13 QA reason codes have no test exercising them in the Spec #001 suite (`DUPLICATE_BAR, ZERO_VOLUME, SUSPICIOUS_GAP, STALE_PRICE, CORPORATE_ACTION_UNRESOLVED, ADJUSTMENT_MISMATCH, STATUS_CONFLICT, INSUFFICIENT_HISTORY, SOURCE_DISCREPANCY`). Detection logic exists for all 13 (`qa/reason_codes.py`, `qa/engine.py`); this is a coverage gap, not a known defect in any of the 9. A refactor that inverted a threshold comparison or broke a run-length counter among these 9 would ship with a fully green CI run -- that is the risk the gap carries, not a claim any of them is currently broken.
2. **[TEST-COVERAGE GAP, corrected 2026-10-03]** `STATUS_CONFLICT` (overlapping listing-status windows, `qa/engine.py:134-139`) has detection code that is present and active -- confirmed by direct read. It has no test exercising it, which is the real, narrower finding. The original version of this document said it would "silently pass QA undetected," which overstated the gap as an absence of detection; corrected here.
3. **[KNOWN LIMITATION -- ALREADY DOCUMENTED, corrected 2026-10-03]** QA's `qa_pass` is not knowledge-time-gated by `computed_at` the way prices/corporate actions are gated by `as_of` -- but this is not a new finding. It is disclosed in `docs/known_limitations.md:260-279`, flagged by GPT Review #001 (2026-09-21), classified `PENDING`, with the explicit condition that it **must be resolved before Discovery Engine or any downstream research module is approved to consume `qa_pass` for research-grade use**. The original version of this document presented it as freshly discovered; corrected here to point at the existing disclosure.
4. **[TEST-COVERAGE GAP]** The one nuance SS8 calls out by name -- an announced-but-not-yet-effective corporate action must not be flagged `CORPORATE_ACTION_UNRESOLVED` -- has no test, positive or negative. The code looks narrow/correct by inspection.
5. **[SUSPECTED ISSUE -- VERIFICATION PENDING]** `repository.get_security_by_provider_id` is dead code (Claude-verified): the function that would resolve `security_id` from a `(provider, provider_id)` pair is never called anywhere; the real, tested path requires the caller to already know/choose `security_id`. Whether this leaves SS3.1's "provider IDs mapped to security_id" requirement genuinely unmet, or merely met by a different mechanism than the one this function suggests, needs Radu's contractual read, not just a dead-code observation.
6. **[TEST-COVERAGE GAP]** Total-return adjustment math has no correctness test -- the field itself is honestly marked `EXPERIMENTAL_NOT_APPROVED_FOR_RESEARCH` (satisfying the explicit-methodology requirement), but a sign error in the reinvestment formula would go undetected indefinitely regardless of that marking.
7. **[TEST-COVERAGE GAP]** 3 of 5 listing statuses (`HALTED`, `SUSPENDED`, `PRE_IPO`) are never used in any test. The lookup mechanism is status-agnostic by design (a generic date-windowed query, not special-cased per value), which is why this is tagged a coverage gap rather than a suspected defect.
8. **[KNOWN LIMITATION -- ALREADY DOCUMENTED (`CONFIRMED`) / SUSPECTED ISSUE -- VERIFICATION PENDING (status-level `UNRESOLVED`)]** 2 of 5 corporate-action status candidates are unimplemented: `CONFIRMED` (already disclosed in `docs/known_limitations.md`) and a status-level `UNRESOLVED` (not disclosed anywhere as a gap -- only its QA-reason-code cousin exists).
9. **[TEST-COVERAGE GAP]** Provider Independence (SS19) has no structural guard, unlike the directly analogous SS10/11 rule, which got an explicit AST-scan test per Radu's own 2026-09-20 instruction. Compliant by inspection today; the gap is the missing structural test, not a current violation.
10. **[FUTURE / PROCEDURAL REQUIREMENT]** SS21/22/26/28/29 are process or philosophy statements, not testable predicates, yet SS24 nominally gates full acceptance on all of them together -- a structural property of the document itself, not an implementation defect.
