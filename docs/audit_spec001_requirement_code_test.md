# Spec #001 -- Requirement -> Code -> Test Correspondence Matrix

**Status: background-agent output, partially spot-checked by Claude, NOT
independently verified by Radu.** Produced by a Claude subagent tasked
with reading `docs/Spec_001_Data_Foundation_v1.0.md` section-by-section
and citing exact `src/`/`tests/` evidence for each of the 29 sections --
conservative by instruction (PARTIAL/AMBIGUOUS over MET when evidence is
thin; a passing test suite alone never counts as proof).

**Claude's own spot-check on 3 of the agent's highest-impact claims, done
directly against the source (not re-trusting the agent):**
1. `repository.get_security_by_provider_id` (`src/data_foundation/model/repository.py:62`) has exactly one occurrence in the whole repo -- its own definition. **Confirmed dead code, exactly as the agent claims.**
2. `pit/access.py:311` filters QA rows by `r.date <= as_of` only; `computed_at` exists on the QA result entity/schema and is populated at insert time (`qa/engine.py:165`, `schema.sql:77,155`) but is never checked against `as_of` in that filter. **Confirmed: QA pass/fail is not knowledge-time-gated the way prices/corporate actions are.**
3. `tests/test_10_direct_access.py` does contain the AST-based import-graph scan the agent describes (`ALLOWED_DIRS`, `_imports_repository`, `test_no_module_outside_allowed_layers_imports_repository_directly`). **Confirmed as described.**

All three held up. The rest of the table below was not independently
re-verified line-by-line by Claude; treat citations as agent-reported
until Radu or a further pass checks them.

Full suite for this spec's own tests: **34 passed, 1 skipped** (`tests/test_01_*.py` through `tests/test_17_*.py`; skip is TEST 8, `PENDING_LEVEL_2_DATA`, already an approved deferral).

---

## Section-by-section table

| # | Requirement (paraphrase) | Code location | Test location | Status |
|---|---|---|---|---|
| 1 | Build a standardized, auditable, PIT-safe data foundation; no signals/indicators/edge/trade decisions | `src/data_foundation/{adapters,model,pit,qa,storage}` (whole tree); grep confirms no trading-signal/indicator/alpha-score concepts | No dedicated test -- scope adherence is manual-inspection only | PARTIAL -- compliant today, no structural guard |
| 2 | Separate Data Quality (in scope) from Universe Eligibility (out of scope) | `qa/engine.py:43-46`, `qa/config/severity_mapping.yaml:1-6`; grep confirms no `min_price`/`ADV`/`market_cap`/`spread_limit` | none | PARTIAL -- same no-guard caveat |
| 3 | Data model = distinct components; 3.1 Security Master fields | `storage/schema.sql:17-157` (7 tables); `model/entities.py:54-62` (`SecurityMaster` matches spec fields) | `tests/test_01_ohlc_integrity.py` and most others exercise it incidentally | MET, but see Finding 6 -- the provider-id-to-security_id resolver is dead code |
| 4 | Symbol History is temporal; reuse must not merge histories | `model/entities.py:65-72`; `pit/access.py:192-207` | `tests/test_05_ticker_change.py`, `tests/test_06_ticker_reuse.py` (both sub-cases) | MET |
| 5 | Price History minimal schema; raw never overwritten by adjusted | `model/entities.py:75-85`; `model/repository.py:132-150` (`INSERT OR IGNORE`, no update path) | `tests/test_02_split_correctness.py`, `tests/test_03_dividend_handling.py` | MET |
| 6 | Distinguish raw/split-adjusted/total-return; explicit methodology; provider's own adjusted kept separate | `model/adjustment_engine.py:1-40,65-92`; `pit/access.py:257-305`; provider-adjusted close never used as input | Split-adjustment tested (`test_02`); **total-return math has zero correctness test** -- explicitly marked `EXPERIMENTAL_NOT_APPROVED_FOR_RESEARCH` | PARTIAL |
| 7 | Corporate Actions stored separately; announcement != effective date | `storage/schema.sql:108-121`; `model/entities.py:17-24,101-125` (all 7 `ActionType` candidates) | `tests/test_11_corporate_action_timing.py` | MET for SPLIT/REVERSE_SPLIT/DIVIDEND; `MERGER/ACQUISITION/SPINOFF/OTHER` exist only as enum values, never produced or tested -> PARTIAL overall |
| 8 | Corporate Action Status candidates; `UNRESOLVED` = genuine ambiguity, not "announced but not yet effective" | `pit/access.py:90-116`; `entities.py:35-40` (4 of 5 candidates -- no `CONFIRMED`, no status-level `UNRESOLVED`); `qa/engine.py:125-132` (`CORPORATE_ACTION_UNRESOLVED` reason code, narrow/correct-looking condition) | ANNOUNCED/EFFECTIVE/CANCELLED tested; **`CORPORATE_ACTION_UNRESOLVED` itself has zero test coverage anywhere**, including the specific "don't false-flag a valid future action" case the spec calls out by name | PARTIAL |
| 9 | Listing/Status History; `delisting_reason` audit-only | `model/entities.py:27-32,128-143`; `pit/access.py:216-242` | Only `ACTIVE`/`DELISTED` ever exercised; `HALTED`/`SUSPENDED`/`PRE_IPO` (3 of 5) have zero coverage | PARTIAL |
| 10 | All research-consumer access via PIT gateway `get_data(as_of=X)` | `pit/access.py:308-322` | `tests/test_10_direct_access.py` -- real AST scan of the import graph | MET |
| 11 | PIT layer is the single gateway; storage/adapter tests may inspect storage directly | Same as SS10; carve-out documented `model/repository.py:23-27` | Same test + legitimate direct-construction tests (`test_13`/`test_14`) | MET |
| 12 | Event date vs information-availability date distinguished; enforced by access layer not deletion | `pit/access.py:1-74,90-142` | `tests/test_09_pit_look_ahead.py`, `tests/test_13_knowledge_time_policy.py` | MET |
| 13 | QA produces `qa_pass` + `reason_codes[]` + `severity[]` (list-valued, not enum) | `model/entities.py:146-153`; `qa/engine.py:166-176` | Structure proven throughout; **no test proves one date carrying >1 simultaneous code** | PARTIAL |
| 14 | 13 named, extensible QA reason codes | `qa/reason_codes.py:7-20` (all 13 present) | Only 4/13 ever triggered by a test (`MISSING_BAR`, `OHLC_INVALID`/`NEGATIVE_PRICE`, `IDENTIFIER_CONFLICT`) | PARTIAL -- see Finding 1 |
| 15 | Severity levels; ERROR->`qa_pass=FALSE` fixed; mapping externally configurable | `qa/reason_codes.py:23-26`; `qa/engine.py:169`; `qa/config/severity_mapping.yaml` | Fixed-ERROR rule tested; **no test ever swaps the mapping to prove "configurable" actually changes behavior** | PARTIAL |
| 16 | Test fixtures marked `TEST_CONFIG`, never `DEFAULT_TRADING_RULES` | `tests/fixtures/market_data.py:1-9` (explicit docstring) | Same file consumed by every test | MET |
| 17 | No silent forward-fill; missing data detected/kept/flagged | `model/repository.py:132-150` (no fill logic); `qa/engine.py:100-105` | `tests/test_07_missing_data.py` | MET |
| 18 | Provider Adapter contract: map, convert, declare unavailable, never invent, preserve metadata | `adapters/base.py:28-73`; `adapters/yfinance_adapter.py:58-163` | Exercised via `tests/fixtures/fake_yfinance.py` across several tests | PARTIAL -- explicit "unavailable fields" list exists only for `RawSecurityInfo`, not the other two carriers (which signal via bare `None`) |
| 19 | No provider-name branching outside adapters | `adapters/base.py:18`; grep confirms zero violations | **No structural test**, unlike the analogous SS10/11 AST scan | PARTIAL -- compliant today, unenforced |
| 20 | Full provenance retrievable and traceable | `model/entities.py:54-125` (provider/id/timestamps on every table) | `tests/test_14_cancelled_action_adjustment.py` touches audit-trail correctness; **no test traces a QA anomaly end-to-end back to its source** | PARTIAL |
| 21 | Three data levels; Level 1 = schema/adapters/PIT/QA only | Pervasive "Level 1" framing in docstrings | `tests/test_08_provider_consistency.py` -- explicit, visible `PENDING_LEVEL_2_DATA` skip | MET -- honest, visible deferral |
| 22 | Provider bake-off before Level-3 provider choice | NOT FOUND | NOT FOUND | GAP -- expected at this stage, but no `PENDING_LEVEL_3` marker records it as a conscious deferral (unlike SS21's TEST 8) |
| 23 | 12 mandatory PASS/FAIL tests | One test file per requirement, `test_01`-`test_12` | Same | PARTIAL -- 11/12 run and pass; TEST 8 is an approved `PENDING_LEVEL_2_DATA` |
| 24 | 12 acceptance criteria + mandatory suite pass | See rows above | Same | PARTIAL -- criteria 9 (QA codes, ~31% tested) and 11 (provenance) are the weakest |
| 25 | Out-of-scope items must not appear in this module | Grep confirms no hits | No automated guard | PARTIAL -- same no-guard pattern as SS1/2 |
| 26 | Correctness/auditability before performance; no premature optimization | `storage/db.py:1-19` (plain sqlite3, explicit rationale); `schema.sql:9-15` | Not mechanically testable | AMBIGUOUS -- qualitative engineering philosophy, no pass/fail predicate exists for it |
| 27 | Deliverables A-E (code, tests, test report, architecture note, known limitations) | All 5 present and substantive | N/A | MET |
| 28 | "IMPLEMENTATION BLOCKER" process rule (stop, report, wait) for architectural changes | One documented real instance: the PATCH #001-D blocker (`docs/test_report.md:93`), correctly followed | Not testable by pytest -- a human/process rule | PARTIAL/process-only |
| 29 | Next Gate: review chain -> ACCEPTED -> next spec begins | `docs/ACCEPTANCE.md` documents this chain having occurred (`918f3f7`) | N/A | AMBIGUOUS -- **the recovered source text itself ends mid-sentence** ("începem proiectarea:") with nothing after it; a pre-flagged gap in the transcript, not something code could ever satisfy |

---

## Top findings (highest-impact gaps/ambiguities)

1. **9 of 13 QA reason codes have zero test coverage in the Spec #001 suite** (`DUPLICATE_BAR, ZERO_VOLUME, SUSPICIOUS_GAP, STALE_PRICE, CORPORATE_ACTION_UNRESOLVED, ADJUSTMENT_MISMATCH, STATUS_CONFLICT, INSUFFICIENT_HISTORY, SOURCE_DISCREPANCY`). A refactor that inverts `SUSPICIOUS_GAP`'s threshold comparison or breaks `STALE_PRICE`'s run-length counter would ship with a fully green CI run.
2. **`STATUS_CONFLICT` (overlapping listing-status windows) has zero test coverage anywhere in the entire repository**, not just this spec. Two overlapping `ACTIVE`/`HALTED` windows for the same security -- a realistic bad-data case -- would silently pass QA undetected.
3. **QA results are not knowledge-time-gated** (Claude-verified, see spot-check above): `get_data(as_of=T)` filters QA rows by observation date only, never by `computed_at`. If QA is recomputed later (e.g. a `SUSPICIOUS_GAP` verdict changes after new bars arrive), querying the same historical date before vs. after that recompute can return two different `qa_pass` values for date T -- exactly the leakage class TEST 9 exists to catch for prices/actions, with nothing analogous for QA.
4. **The one nuance SS8 calls out by name is untested**: an announced-but-not-yet-effective corporate action must not be flagged `CORPORATE_ACTION_UNRESOLVED`. The code looks narrow/correct, but no test -- positive or negative -- exercises it.
5. **`repository.get_security_by_provider_id` is dead code** (Claude-verified): the function that would resolve `security_id` from a `(provider, provider_id)` pair is never called anywhere; the real, tested path requires the caller to already know/choose `security_id`.
6. **Total-return adjustment math has zero correctness test** -- honestly marked `EXPERIMENTAL_NOT_APPROVED_FOR_RESEARCH`, but a sign error in the reinvestment formula would go undetected indefinitely regardless.
7. **3 of 5 listing statuses (`HALTED`, `SUSPENDED`, `PRE_IPO`) are never used in any test.**
8. **2 of 5 corporate-action status candidates are unimplemented**: `CONFIRMED` (already disclosed in `docs/known_limitations.md`) and a status-level `UNRESOLVED` (not disclosed anywhere as a gap -- only its QA-reason-code cousin exists).
9. **Provider Independence (SS19) has no structural guard**, unlike the directly analogous SS10/11 rule, which got an explicit AST-scan test per Radu's own 2026-09-20 instruction. Compliant today, silently unenforced going forward.
10. **SS21/22/26/28/29 are process or philosophy statements, not testable predicates**, yet SS24 nominally gates full acceptance on all of them together -- a structural ambiguity in the document itself, not an implementation defect.
