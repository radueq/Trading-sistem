# Spec #004 v1.0 -- Test Report

Run: `PYTHONPATH=src:tests python3 -m pytest tests/spec004/ -v` -- Python
3.11.15, pytest 9.1.1, pandas 3.0.6, numpy 2.4.6, PyYAML 6.0.1.

Result: **150 passed, 0 failed, 0 pending** (across the 44 required
tests, TEST 45-52 added per Radu's SS110 A/B/C/D/E/F/H amendments during
architecture review, TEST 53-61 added for PATCH #004-A -- GPT Review
#004 Round 1 -- and TEST 62-66 added for PATCH #004-B -- GPT Review #004
Round 2 -- several have multiple focused sub-tests). Full repo (Spec #001
+ Spec #002 + Spec #003 + Spec #004): **275 passed, 1 skipped** (Spec
#001 TEST 8, `PENDING_LEVEL_2_DATA`, unaffected).

No PIT/ingestion/database is exercised anywhere in this package -- every
test runs against hand-built #003-shaped `EvaluationSignatureDefinition`/
`EvidenceProfile`/`EvaluationRunRegistry` objects (see
`tests/spec004/conftest.py`), since #004 never needs a live pipeline to
receive already-materialized Evaluation artifacts.

| # | Test | File | Result | Notes |
|---|------|------|--------|-------|
| 1 | EvidencePacket provenance | `test_01_evidence_packet_provenance.py` | **PASS** | Packet carries the full 8-field provenance tuple from the signature/run it was built from. |
| 2 | No raw price history in EvidencePacket | `test_02_evidence_packet_no_raw_price_history.py` | **PASS** (2 sub-tests) | Field-name scan on the dataclass itself, plus a repr scan on a real built packet. |
| 3 | StrategyHypothesis deterministic serialization | `test_03_strategy_hypothesis_deterministic_serialization.py` | **PASS** | Two independently-built, identical hypotheses serialize (dict/repr) byte-identically. |
| 4 | Direction explicit | `test_04_direction_explicit.py` | **PASS** (2 sub-tests) | `LONG`/`SHORT` accepted; an unrecognized value rejected. |
| 5 | No automatic LONG/SHORT flip | `test_05_no_automatic_direction_flip.py` | **PASS** (2 sub-tests) | A negative-effect LONG proposal is not rewritten; LONG and SHORT on the same entry are two distinct hypothesis ids. |
| 6 | Entry conditions from approved fields only | `test_06_entry_conditions_approved_fields_only.py` | **PASS** (2 sub-tests) | Lane/label and reason_code conditions validated against `states.yaml`/`ReasonCode`. |
| 7 | Unknown indicator rejected | `test_07_unknown_indicator_rejected.py` | **PASS** (2 sub-tests) | The spec's own `RSI_7` example, plus an unknown reason code. |
| 8 | Maximum entry complexity enforced | `test_08_maximum_entry_complexity_enforced.py` | **PASS** (2 sub-tests) | Within-budget accepted; over `max_entry_conditions` flips `complexity_status`. |
| 9 | Entry execution policy explicit | `test_09_entry_execution_policy_explicit.py` | **PASS** (2 sub-tests) | `NEXT_BAR_OPEN` is the only allowed V1 value; anything else rejected. |
| 10 | Horizon unit = BARS | `test_10_horizon_unit_bars.py` | **PASS** (2 sub-tests) | `DAYS` rejected. |
| 11 | Horizon candidates subset of allowed values | `test_11_horizon_candidates_subset_allowed.py` | **PASS** (2 sub-tests) | A value outside `allowed_values` is rejected. |
| 12 | No automatic best-horizon selection | `test_12_no_automatic_best_horizon_selection.py` | **PASS** (2 sub-tests) | No `selected_horizon`/`optimal` field exists; the decay curve reports every horizon even when one dominates. |
| 13 | TIME_EXIT hypothesis valid | `test_13_time_exit_hypothesis_valid.py` | **PASS** | `materialize_variants()` expands one TIME_EXIT variant per candidate value. |
| 14 | SIGNAL_INVALIDATION exit valid | `test_14_signal_invalidation_exit_valid.py` | **PASS** (2 sub-tests) | Lane-based and reason-code-based invalidation triggers, both with a time cap. |
| 15 | Unsupported exit family rejected | `test_15_unsupported_exit_family_rejected.py` | **PASS** | `ATR_TRAILING_STOP` rejected. |
| 16 | Risk exit disabled in V1 | `test_16_risk_exit_disabled_v1.py` | **PASS** (2 sub-tests) | Config default confirmed `false`; a tampered `true` config is rejected by the validator. |
| 17 | No ATR-multiplier fields | `test_17_no_atr_multiplier_fields.py` | **PASS** (2 sub-tests) | Structural field-name scan on `ExitHypothesis`/`StrategyDefinition`. |
| 18 | Evidence fields cannot appear in runtime signal | `test_18_evidence_fields_not_in_runtime_signal.py` | **PASS** (2 sub-tests) | `FORBIDDEN_OUTCOME_FIELD_NAMES` covers the spec's examples; a condition using one as a lane is flagged. |
| 19 | No adjusted-p in entry rule | `test_19_no_adjusted_p_in_entry_rule.py` | **PASS** (2 sub-tests) | The spec's own forbidden example (SS74), as a lane and as a reason code. |
| 20 | No forward_return in entry/exit conditions | `test_20_no_forward_return_in_conditions.py` | **PASS** (2 sub-tests) | Checked in both an entry condition and an invalidation condition. |
| 21 | Fingerprint changes if direction changes | `test_21_fingerprint_changes_direction.py` | **PASS** | LONG vs SHORT on identical everything-else produces different fingerprint/id/hash. |
| 22 | Fingerprint changes if exit changes | `test_22_fingerprint_changes_exit.py` | **PASS** (2 sub-tests) | At the VARIANT level (`variant_definition_hash`) -- 2-bar vs 3-bar TIME_EXIT, and TIME_EXIT vs SIGNAL_INVALIDATION. |
| 23 | Fingerprint changes if Evidence provenance changes | `test_23_fingerprint_changes_evidence_provenance.py` | **PASS** (2 sub-tests) | `evaluation_run_id` and `evaluation_config_version` changes each change the fingerprint. |
| 24 | Frozen hypothesis immutable | `test_24_frozen_hypothesis_immutable.py` | **PASS** (2 sub-tests) | `dataclasses.FrozenInstanceError` on field assignment; registry refuses a same-id/different-content overwrite of a PREREGISTERED record. |
| 25 | Modification creates new version | `test_25_modification_creates_new_version.py` | **PASS** (2 sub-tests) | `create_new_version()` bumps version and changes id; a no-op call is rejected. |
| 26 | Rejected proposals remain in registry | `test_26_rejected_proposals_remain_in_registry.py` | **PASS** (2 sub-tests) | Retrievable via `all_proposals()`/`rejected_proposal_ids()`; marking an unregistered proposal fails loudly. |
| 27 | Hypothesis Budget enforced | `test_27_hypothesis_budget_enforced.py` | **PASS** | The 4th hypothesis on one signature exceeds `max_hypotheses_per_signature=3`. |
| 28 | Budget does not silently delete proposals | `test_28_budget_does_not_delete_proposals.py` | **PASS** | An over-budget rejection keeps every prior proposal registered. |
| 29 | AgentReview SUPPORT/OBJECT/ABSTAIN | `test_29_agent_review_stances.py` | **PASS** (4 sub-tests) | Valid stances accepted; `OBJECT` without an objection is invalid; unrecognized stance invalid. |
| 30 | Consensus cannot auto-preregister | `test_30_consensus_cannot_auto_preregister.py` | **PASS** | Unanimous `SUPPORT` with no `human_decision` still cannot preregister. |
| 31 | Human approval required | `test_31_human_approval_required.py` | **PASS** (2 sub-tests) | Empty decision rejected; explicit decision accepted. |
| 32 | Disagreement preserved | `test_32_disagreement_preserved.py` | **PASS** (2 sub-tests) | Mixed SUPPORT/OBJECT -> `DISAGREEMENT` with objections kept; all-OBJECT -> `BLOCKED`. |
| 33 | Facts vs interpretation separated | `test_33_facts_vs_interpretation_separated.py` | **PASS** (3 sub-tests) | Distinct fields on `HypothesisProposal`; both required non-empty. |
| 34 | Review priority not part of trading rule | `test_34_review_priority_not_trading_rule.py` | **PASS** (2 sub-tests) | No `priority` field on `StrategyDefinition`/`EntryDefinition`/`ExitHypothesis`; `ResearchQueueEntry` shares no field names with `StrategyDefinition`. |
| 35 | No HypothesisScore | `test_35_no_hypothesis_score.py` | **PASS** | AST identifier scan across `src/hypothesis/` -> zero forbidden combined-score identifiers. |
| 36 | No direct PIT/raw-price imports | `test_36_no_pit_raw_price_imports.py` | **PASS** (2 sub-tests) | AST import scan -> no `data_foundation`/engine-internals import anywhere; only `evaluation.models.entities` is ever imported from Evaluation. |
| 37 | No broker imports | `test_37_no_broker_imports.py` | **PASS** | Text scan for broker/live-trading tokens. |
| 38 | No backtesting imports | `test_38_no_backtesting_imports.py` | **PASS** (2 sub-tests) | AST scan for backtest-related imports/definitions (docstring prose explaining the #004/#005 boundary is allowed); no `backtesting`/`backtest` package exists yet. |
| 39 | No LLM imports in deterministic core | `test_39_no_llm_imports_deterministic_core.py` | **PASS** (2 sub-tests) | AST import scan -> no `anthropic`/`openai`/`google.generativeai`/`cohere`/`langchain`; no `agents/` adapter package exists yet. |
| 40 | Daily/4H timeframe metadata generic | `test_40_timeframe_metadata_generic.py` | **PASS** (2 sub-tests) | No day-coupled field name anywhere; `HorizonCandidateSet.unit` is BARS. |
| 41 | StrategyDefinition provenance consistency | `test_41_strategy_definition_provenance_consistency.py` | **PASS** | Built `StrategyDefinition`s trace back to their exact hypothesis/variant. |
| 42 | Discovery config mismatch rejected | `test_42_discovery_config_mismatch_rejected.py` | **PASS** (3 sub-tests) | `discovery_config_version`/`discovery_engine_version` mismatch detected; matching provenance accepted. |
| 43 | Evaluation run mismatch detectable | `test_43_evaluation_run_mismatch_detectable.py` | **PASS** (2 sub-tests) | `evaluation_run_id`/`evaluation_engine_version` mismatch detected. |
| 44 | Same inputs reproduce same hypothesis id | `test_44_same_inputs_same_hypothesis_id.py` | **PASS** | 5 repeated calls with identical inputs produce exactly 1 distinct id. |
| 45 | `horizon_reference_point=ENTRY_BAR` exact semantics | `test_45_horizon_reference_point_entry_bar_semantics.py` | **PASS** (2 sub-tests) | Radu's SS110-A worked example (Monday close signal -> Tuesday open entry -> Thursday close exit for TIME_EXIT 3), reproduced via explicit bar-index arithmetic; contrasted against Spec #003's own signal-bar-referenced horizon semantics. |
| 46 | SIGNAL_INVALIDATION requires max_holding_bars | `test_46_signal_invalidation_requires_max_holding_bars.py` | **PASS** (2 sub-tests) | Rejected at proposal-validation time AND at the later pre-preregistration gate (defense in depth). |
| 47 | Variants materialized eagerly, never lazily | `test_47_variants_materialized_eagerly_not_lazily.py` | **PASS** (3 sub-tests) | All candidate horizons pre-materialized before any selection; a hypothesis whose `variant_ids` doesn't match its variants is rejected; `build_strategy_definition()` refuses an un-registered variant. |
| 48 | definition_hash excludes admin timestamps | `test_48_definition_hash_excludes_admin_timestamps.py` | **PASS** (2 sub-tests) | `hypothesis_fingerprint()` takes no timestamp parameter at all (checked via `inspect.signature`); the hash still changes when evidence provenance changes. |
| 49 | `evaluation/` cannot import `hypothesis/` | `test_49_evaluation_cannot_import_hypothesis.py` | **PASS** (2 sub-tests) | AST import scan of `src/evaluation/` and `src/discovery/` -> no `hypothesis` import anywhere (dependency direction, mirrors Spec #003 TEST 26). |
| 50 | Eligibility thresholds frozen/versioned | `test_50_eligibility_thresholds_frozen_versioned.py` | **PASS** (2 sub-tests) | Identical inputs+config reproduce identical eligibility; a tightened config changes both `eligibility_config_version` and the actual results. |
| 51 | Review priority always labeled and excluded | `test_51_review_priority_always_labeled_and_excluded.py` | **PASS** (2 sub-tests) | Every ranked entry carries `DEVELOPMENT_OUTCOME_AWARE_SELECTION`; the constant never appears as a `StrategyDefinition` field. |
| 52 | Family boundary: direction/entry change | `test_52_family_boundary_direction_or_entry_change.py` | **PASS** (3 sub-tests) | Different entry or direction always changes the family id; a different `horizon_candidate_set` also changes it (the family's own frozen commitment), distinct from the exit/variant level (TEST 22). |
| 53 | Preregistration cannot be bypassed | `test_53_preregistration_cannot_be_bypassed.py` | **PASS** (5 sub-tests) | PATCH #004-A finding #1. `register()` refuses a hand-built first-time PREREGISTERED object; `preregister_hypothesis()` succeeds through the real gate; rejects without human APPROVE, with an invalid proposal, and with a draft already claiming PREREGISTERED. |
| 54 | Human decision is an explicit enum, not free text | `test_54_human_decision_explicit_enum.py` | **PASS** (3 sub-tests) | A REJECT decision with any rationale text is never treated as approval; only the literal APPROVE value passes; `HumanDecision` is a structured dataclass, not a bare string. |
| 55 | StrategyDefinition rejects a fabricated hypothesis | `test_55_strategy_definition_rejects_fabricated_object.py` | **PASS** | Reproduces the exact fabricated-object attack the review described; `build_strategy_definition()` refuses it because the object was never in the registry. |
| 56 | Provenance and signature-id consistency wired into the gate | `test_56_provenance_and_signature_consistency_wired_into_gate.py` | **PASS** (4 sub-tests) | PATCH #004-A finding #2. A provenance mismatch against the actual run is caught; `parent_signature_id`/`signature_set_id` disagreeing with `evidence_provenance`'s own copies is each rejected; a fully consistent hypothesis passes. |
| 57 | EvidencePacket cross-artifact consistency | `test_57_evidence_packet_cross_artifact_consistency.py` | **PASS** (7 sub-tests) | PATCH #004-A finding #3. Signature/profile timeframe mismatch, Discovery engine version mismatch, duplicate horizons, missing/extra horizons vs `run_registry.horizons`, and mixed `evaluation_mode` are each rejected; consistent artifacts build successfully. |
| 58 | Research Queue is signature-level, no implicit selection | `test_58_research_queue_signature_level_no_implicit_selection.py` | **PASS** (4 sub-tests) | PATCH #004-A finding #4. Exactly one entry per signature regardless of decay-curve length; priority uses only the configured reference horizon, never the strongest one; a packet built off-policy is rejected; multiple signatures each get exactly one entry. |
| 59 | `parameter_source` on TIME_EXIT variants is real, not hardcoded | `test_59_horizon_parameter_source_real.py` | **PASS** (3 sub-tests) | PATCH #004-A finding #5. TIME_EXIT variants inherit the declared `parameter_source` (`PRE_SPECIFIED` or `EVIDENCE_DERIVED`), never a hardcoded value; `parameter_source` participates in the family fingerprint. |
| 60 | Baseline variant is never auto-deduced from `min(horizon)` | `test_60_baseline_variant_not_auto_deduced.py` | **PASS** (3 sub-tests) | PATCH #004-A finding #5. Default materialization tags nothing as baseline (including the shortest horizon); an explicit `baseline_time_exit_bars` tags exactly that one; a value outside the candidate set is rejected. |
| 61 | Research history survives a process restart | `test_61_jsonl_audit_log_persistence.py` | **PASS** (3 sub-tests) | PATCH #004-A finding #6. Proposals and a rejection survive a fresh `JsonlAuditLog.replay()`; a preregistered hypothesis and its variants survive a fresh replay AND a third, fully independent `PersistentHypothesisRegistry.open()` call; the log file is never rewritten, only appended to. |
| 62 | Preregistration binding verified | `test_62_preregistration_binding_verified.py` | **PASS** (6 sub-tests) | PATCH #004-B finding #1. A consistent proposal/validation/consensus/draft binding succeeds; a mismatched `proposal_validation.proposal_id`, `consensus.proposal_id`, or `draft.hypothesis_provenance.proposal_id` is each rejected; an `approved_by`/`approved_at` disagreeing with the human decision actually supplied is each rejected. |
| 63 | Content-addressed identity verified at the gate | `test_63_content_addressed_identity_verified_at_gate.py` | **PASS** (5 sub-tests) | PATCH #004-B finding #2. A tampered `hypothesis_id`, `definition_hash`, `strategy_variant_id`, or `variant_definition_hash` is each rejected by a recomputed-fingerprint check; a genuine, untampered hypothesis and its variants pass. |
| 64 | StrategyVariant fully immutable, including variant_tag | `test_64_variant_fully_immutable_including_tag.py` | **PASS** (3 sub-tests) | PATCH #004-B finding #3. Rewriting `variant_tag` on an already-registered variant (same id, same hash) is rejected; re-registering an identical variant is an idempotent no-op; a different `variant_definition_hash` is still rejected (regression). |
| 65 | Preregistration persisted as one atomic record | `test_65_preregistration_persisted_as_one_atomic_record.py` | **PASS** (3 sub-tests) | PATCH #004-B finding #4. Exactly one JSONL line (`preregistration_committed`) is appended for a whole commit, carrying the hypothesis and every variant together; replay reconstructs all of it from that one line; no commit line means no hypothesis at all, never a partial one. |
| 66 | Research Queue rejects duplicate signature_id | `test_66_research_queue_rejects_duplicate_signature.py` | **PASS** (2 sub-tests) | PATCH #004-B finding #5 (minor). `[packet_SIG_A, packet_SIG_A]` is rejected; distinct signature ids are unaffected. |

## How to reproduce

```bash
pip install -r requirements.txt
python3 -m pytest tests/ -v
# regenerate docs/spec004_examples.md:
PYTHONPATH=src:tests python3 -m spec004.generate_report_artifacts
```

No network access is required or attempted -- every test runs against
hand-constructed `EvaluationSignatureDefinition`/`EvidenceProfile`/
`EvaluationRunRegistry` objects (`tests/spec004/conftest.py`).
