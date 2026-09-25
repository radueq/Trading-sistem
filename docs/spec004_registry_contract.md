# Spec #004 v1.0 -- Registry Contract

The Hypothesis Registry's exact guarantees for any consumer (Spec #005,
a future dashboard, a human audit) -- what it promises, and what it
deliberately refuses to do.

## Identity

| Entity | Id field | Derived from | Excludes |
|---|---|---|---|
| `StrategyHypothesis` | `hypothesis_id` = `f"hyp_{digest}"` | `hypothesis_fingerprint()`: `parent_signature_id`, `direction`, `entry_definition`, `entry_execution_policy`, `horizon_candidate_set`, every field of `evidence_provenance`, `strategy_config_version` | `direction_basis`, `created_at`, `created_by`, `hypothesis_provenance` (all administrative/audit-trail) |
| `StrategyVariant` | `strategy_variant_id` = `f"var_{digest}"` | `variant_fingerprint()`: parent's `definition_hash` + this variant's own `exit_hypothesis` (all fields, including `parameter_source`) | `variant_tag`, `created_at` |
| `StrategyDefinition` | `strategy_id` = `f"strat_{digest}"` | `hypothesis_id` + `strategy_variant_id` | -- |

`build_hypothesis_id()`/`build_variant_id()` are pure functions of their
fingerprint string -- identical inputs always reproduce the identical id
(TEST 44), with no random or time-based component anywhere.

## Mutability rules

1. **DRAFT / REVIEWED / REJECTED** records may be freely re-registered
   with the SAME id as long as content (`definition_hash`) hasn't
   changed; registering different content under an id already used for
   different content raises `ImmutableHypothesisError` regardless of
   status.
2. **PREREGISTERED is immutable.** `HypothesisRegistry.register()`
   refuses any write to an existing `PREREGISTERED` id whose content
   differs at all, even by one field, from what's stored.
3. **The only way to change a hypothesis after the fact is
   `create_new_version(parent, **overrides)`**, which recomputes the
   fingerprint from the merged fields, ALWAYS produces a new
   `hypothesis_id` (raising `ValueError` if nothing that affects the hash
   actually changed), sets `hypothesis_version = parent.hypothesis_version
   + 1`, and sets `supersedes_hypothesis_id = parent.hypothesis_id`. The
   new record starts back at `status = DRAFT` -- it must go through
   consensus/human-approval again before it can reach PREREGISTERED.
4. **Nothing is ever deleted.** `HypothesisRegistry` has no delete/remove
   method for hypotheses, variants, or proposals. A rejected proposal
   stays in `all_proposals()` forever; `mark_proposal_rejected()` only
   adds it to `rejected_proposal_ids()`, it never removes the record.

## Variant materialization contract

`materialize_variants(hypothesis, signal_invalidation_exits=(), created_at=...)`
must be called with the hypothesis's FINAL `horizon_candidate_set`
BEFORE `status` is set to `PREREGISTERED`, and the resulting
`strategy_variant_id`s must be written into `StrategyHypothesis.
variant_ids` in full. Two enforcement points:

- `validation/rules.py:validate_for_preregistration()` rejects a
  hypothesis whose `variant_ids` doesn't exactly match the variants
  actually supplied to it (TEST 47).
- `registry/strategy_registry.py:build_strategy_definition()` raises
  `ValueError` if asked to build a `StrategyDefinition` for a variant
  whose id is not already present in the parent hypothesis's
  `variant_ids` -- this is the structural guarantee that Spec #005 can
  only ever select among pre-existing variants, never mint one after
  seeing a result.

## Provenance contract

Every `StrategyHypothesis.evidence_provenance` (an `EvidenceProvenance`)
names, in full: `evaluation_run_id`, `evaluation_engine_version`,
`evaluation_config_version`, `signature_id`, `signature_set_id`,
`discovery_engine_version`, `discovery_config_version`, `timeframe`.
`validation/provenance.py:check_provenance_matches_run()` compares this
against the ACTUAL `EvaluationRunRegistry` a caller supplies, field by
field -- a mismatch on any single field is a hard rejection (TEST 42-43),
mirroring Spec #003's own FORMAL_DEVELOPMENT provenance guard
(PATCH #003-B) one layer up the chain.

## Budget contract

`validate_for_preregistration()` counts, among a signature's currently
`PREREGISTERED`/`HANDOFF_TO_BACKTEST` hypotheses (never counting
`DRAFT`/`REJECTED` ones), and rejects a NEW hypothesis whose addition
would push that count past `hypothesis_budget.max_hypotheses_per_
signature` (config-versioned, default 3). This is a Level 1 research
control, not a validated trading rule (Spec #004 SS52) -- raising it
never manufactures more findings, it only limits how many distinct
families one signature may spawn before a human must consciously decide
to raise the limit.

## HypothesisUniverse accounting

`registry/hypotheses.py:build_hypothesis_universe()` snapshots, straight
from the append-only registry, with no filtering toward "the winners":
`all_proposals` (every `proposal_id` ever registered), `all_rejected`
(every hypothesis or proposal id marked `REJECTED`), `all_preregistered`
(every hypothesis id currently `PREREGISTERED`). This is the artifact
Spec #005 needs for selection-bias accounting -- "we considered 40,
preregistered 3" must remain provable from this snapshot alone.
