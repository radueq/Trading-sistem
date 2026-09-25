# Spec #004 v1.0 -- Architecture Note

Hypothesis Generation & Strategy Definition. Depends on Spec #001
(`aa56bb5`), Spec #002 (`4f36708` + patches), and Spec #003 (`d889049`),
all accepted. Implemented against repository baseline `266cc6f`, per
Radu's final architecture-review verdict: **"Spec #004 architecture
review -- APPROVED TO IMPLEMENT, with the following clarifications"**
(2026-09-25), covering SS110 A-H below.

## SS0 -- What #004 is and is not

> "#004 nu trebuie sa 'gaseasca strategii profitabile'; trebuie sa
> transforme evidence-ul din #003 in ipoteze explicite, limitate si
> inghetate inainte de backtest." -- Radu

- #004 is **outcome-aware FOR HYPOTHESIS FORMATION** (it reads
  already-computed `EvidenceProfile`s), but **NOT A BACKTESTER**: it
  never touches raw price history, Locked OOS, or executes anything.
- A hypothesis formed using Development evidence is
  **DEVELOPMENT-DERIVED**, never independently validated by that fact
  alone. Validation is Spec #005's job, on data the hypothesis's own
  formation never saw.
- Locked OOS is **completely inaccessible** -- not for direction, entry,
  exit, horizon, or "quick checks." #004's code never imports anything
  that could reach it (TEST 36).

## Pipeline

```
Discovery Signature (Spec #002)
        +
EvidenceProfile (Spec #003)
        +
Human / AI reasoning
        |
        v
HypothesisProposal --[proposals/validator.py]--> ProposalValidationResult
        |
        v
AgentReview(s) --[consensus/consensus.py]--> ConsensusRecord
        |
        v
Human decision (always required, SS46)
        |
        v
StrategyHypothesis (DRAFT) --[registry/hypotheses.py:materialize_variants()]-->
StrategyVariant(s), eagerly, ALL of them, before any status change
        |
        v
validation/rules.py:validate_for_preregistration() -- the last gate
        |
        v
StrategyHypothesis (PREREGISTERED) + StrategyVariant(s) -- both frozen,
registered in the append-only HypothesisRegistry
        |
        v
registry/strategy_registry.py:build_strategy_definition() per variant
        |
        v
StrategyDefinition -- the artifact Spec #005 consumes
```

Two DIFFERENT validation passes exist on purpose, at two different
points with two different amounts of context:
`proposals/validator.py` runs on a raw `HypothesisProposal` alone (no
registry needed -- vocabulary/complexity/policy checks only);
`validation/rules.py` runs on the fully assembled `StrategyHypothesis` +
its materialized variants, with the REGISTRY available (per-signature
budget, SS52) and re-checks outcome-contamination defensively on the
built objects, not just the proposal that led to them.

## SS7/SS104-109 -- StrategyHypothesis IS the family (a documented
reconciliation)

The original spec text (SS7) defines a `StrategyHypothesis` entity with
fields including a single `exit_hypothesis`, then separately (SS104-109)
introduces `StrategyFamily` (common fields + `variants[]`) as a way to
avoid combinatorial explosion. Radu's final SS110-C/D decision collapses
these into exactly **two levels**, with no intermediate `StrategyFamily`
record:

```
StrategyHypothesis   (the FAMILY -- direction, entry_definition,
                       entry_execution_policy, horizon_candidate_set,
                       evidence_provenance, hypothesis_provenance,
                       constraints, variant_ids)
        |
        +-- StrategyVariant A (TIME_EXIT 2)
        +-- StrategyVariant B (TIME_EXIT 3)
        +-- StrategyVariant C (TIME_EXIT 5)
        +-- StrategyVariant D (SIGNAL_INVALIDATION + max_holding_bars)
```

This implementation therefore uses `StrategyHypothesis` (§models/
entities.py) to hold everything Radu's diagram calls "common" fields, and
introduces `StrategyVariant` as the new per-exit entity his diagram
requires -- the `exit_hypothesis` field originally sketched on
`StrategyHypothesis` (SS7) does **not** exist on it; it lives only on
`StrategyVariant`. This is a Level 1 design choice, explicitly documented
here (not silently renamed), matching the reconciliation pattern this
project has used before (e.g. Spec #002's `lane_drivers` choice) whenever
the spec leaves an exact structural decision open and a later review
message settles it.

Radu's formal boundary rule (SS110-D, TEST 52): a different `direction`
OR a different `entry_definition` is **always** a different
`StrategyHypothesis` (family); only the exit (and/or the frozen
`horizon_candidate_set` commitment itself) differing keeps the SAME
family, expressed as different `StrategyVariant`s.

## SS110-A -- Entry execution, horizon_reference_point, and the
`evidence_horizon_bars` vs `strategy_holding_bars` distinction

Frozen for V1 (Radu's approval, no objection raised):

```
signal_time            = CLOSE(t)
entry_execution_policy = NEXT_BAR_OPEN   (ENTRY_EXECUTION_POLICY constant)
horizon_reference_point = ENTRY_BAR      (HORIZON_REFERENCE_POINT constant)
exit_execution_policy  = BAR_CLOSE       (EXIT_EXECUTION_POLICY constant)
```

`TIME_EXIT N` means: entry at the open of the entry bar; holding bar 1
IS the entry bar itself; holding bar N is bar-index `entry_index + (N-1)`;
exit at the CLOSE of holding bar N. Radu's worked example (2026-09-25):

```
Signal: Monday close       Entry: Tuesday open
Holding bar 1 = Tuesday, holding bar 2 = Wednesday, holding bar 3 = Thursday
TIME_EXIT 3 -> exit at Thursday close
```

This is **structurally a different number line** from Spec #003's own
`horizon_bars` (measured `close(signal) -> close(signal+h)`, i.e. from
the SIGNAL bar). The two are named differently everywhere in this
codebase on purpose: `evidence_horizon_bars` (on `DecayPoint`, always
signal-bar-referenced, #003's own quantity, reported unchanged) vs.
`strategy_holding_bars` (the `time_exit_bars` field on `ExitHypothesis`,
always entry-bar-referenced, #004/#005's own quantity). TEST 45
reproduces Radu's worked example via explicit bar-index arithmetic and
shows the two numbers coincide only because entry is exactly one bar
after signal, never because they are the same formula. Documented per
Radu's own closing note:

> "Nu putem afirma ca #003 a demonstrat +1% la 3 zile, deci strategia cu
> entry next-open si exit 3 bars are +1% expectancy. #003 a motivat
> ipoteza; #005 va masura strategia executabila." -- Radu

## SS110-B -- Exit families and the SIGNAL_INVALIDATION time cap

V1 keeps exactly two exit families, `TIME_EXIT` (mandatory baseline,
SS24) and `SIGNAL_INVALIDATION` (optional). Risk exits (ATR/stop-loss/
take-profit/MAE/MFE) remain entirely out of scope (`risk_exit.enabled:
false`, structurally enforced -- TEST 16-17).

Radu's SS110-B addendum, ADDED to the original ExitHypothesis model:
every `SIGNAL_INVALIDATION` variant **must** carry a `max_holding_bars`
time cap. The executable rule is:

> "EXIT on signal invalidation OR mandatory max_holding_bars, whichever
> occurs first." -- Radu

`InvalidationCondition` restricts triggers to the SAME approved #002
vocabulary as entry conditions (lane+`holds_labels`, or a reason code's
presence flipping) -- never a new indicator. Anti-lookahead discipline
(invalidation observed at a bar's close can only produce a fill at or
after that close) is documented here as a rule #004 freezes; enforcing
it at execution time is Spec #005's responsibility.

## SS110-C/D -- Eager variant materialization

`registry/hypotheses.py:materialize_variants()` expands
`horizon_candidate_set.values` into one `StrategyVariant` per value
(TIME_EXIT, shortest tagged `BASELINE_VARIANT`, the rest
`EXPERIMENTAL_VARIANT`), plus one more `EXPERIMENTAL_VARIANT` per
supplied `SIGNAL_INVALIDATION` `ExitHypothesis` -- **at
preregistration time**, before any variant is ever tested. Every
`strategy_variant_id` this produces is written into
`StrategyHypothesis.variant_ids`; `validation/rules.py:
validate_for_preregistration()` rejects a hypothesis whose declared
`variant_ids` doesn't match its actually-supplied variants (TEST 47),
and `registry/strategy_registry.py:build_strategy_definition()` refuses
to build a `StrategyDefinition` for any variant not already on that list
-- Spec #005 can only ever select among pre-existing ids, never invent
one after seeing a backtest result. This is, in Radu's own words, "una
dintre cele mai importante decizii" of the whole project so far.

## SS110-E -- Content-addressed identity, timestamps excluded

`registry/hypotheses.py:hypothesis_fingerprint()` takes **no timestamp
parameter at all** (checked structurally by TEST 48 via
`inspect.signature`) -- `created_at`/`approved_at`/review timestamps
never enter `definition_hash`. What DOES enter it: `parent_signature_id`,
`direction` (not `direction_basis` -- that is audit-trail-only, SS10),
`entry_definition`, `entry_execution_policy`, `horizon_candidate_set`,
every field of `evidence_provenance`, and `strategy_config_version`.
`StrategyVariant.variant_definition_hash` layers the parent's
`definition_hash` with the variant's own `exit_hypothesis` (including
`parameter_source` -- a substantive provenance claim, not mere
metadata).

Identity chain: `definition_hash` (content) -> `hypothesis_id`/
`strategy_variant_id` (`f"hyp_{digest}"`/`f"var_{digest}"`, purely
derived) -> registry record. `HypothesisRegistry` is append-only:
`register()` raises `ImmutableHypothesisError` on a same-id/different-
hash write, and again on any attempt to overwrite an already-
`PREREGISTERED` record with different content under the same id.
`create_new_version()` is the only path to change a hypothesis after the
fact -- it always produces a NEW id (raising if nothing that affects the
hash actually changed) and sets `supersedes_hypothesis_id`.

## SS110-F -- EvidencePacket boundary (zero PIT)

`evidence/packet.py:build_evidence_packet()` takes exactly three already-
materialized Spec #003 artifacts -- `EvaluationSignatureDefinition` +
`list[EvidenceProfile]` (one per horizon, so the full decay curve is
available) + `EvaluationRunRegistry` -- and returns a flat, compact
`EvidencePacket`. Verified concretely (not assumed) before writing this
module: `evaluation/models/entities.py` imports nothing from the rest of
the project (pure dataclasses/enums), so importing it can never pull in
PIT/DB access; `EVALUATION_ENGINE_VERSION` and every provenance field
`EvidenceProvenance` needs already existed on `EvaluationRunRegistry`
before #004 started, so no #003 change was needed.

TEST 36 enforces this two ways: an AST import scan proving nothing under
`src/hypothesis/` imports `data_foundation.*` or any Evaluation/Discovery
*engine* submodule, and a second scan proving the ONLY thing ever
imported from `evaluation.*` is `evaluation.models.entities`. TEST 49
enforces the mirror-image guard Radu asked for: `src/evaluation/` and
`src/discovery/` never import `hypothesis.*` -- the dependency chain
(Data Foundation -> Discovery -> Evaluation -> Hypothesis) stays strictly
one-directional all the way through.

## SS110-G -- No LLM adapter in the core

`src/hypothesis/` contains zero LLM SDK imports (TEST 39) and no
`agents/` adapter package. `proposals/normalize.py` accepts a plain dict
regardless of who produced it -- Radu, a manual GPT/Claude relay (exactly
how Specs #001-#004 themselves were built), or a future automated
adapter. `proposals/validator.py` then checks the resulting
`HypothesisProposal` purely structurally. AI orchestration, if it is ever
built, stays entirely outside this package (SS93-94).

## SS110-H -- Research Queue: eligibility vs priority

`evidence/queue.py` keeps two functions deliberately separate:

- `eligibility_basis()` / `is_eligible_for_review()`: data-QUALITY only
  (missingness ratio, `valid_episode_n`, `unique_security_count`,
  presence of stability bins) against thresholds in `config/
  hypothesis.yaml`'s `research_queue_eligibility` block, versioned via
  `eligibility_config_version` (the config's own hash) -- frozen BEFORE a
  queue run, per Radu's explicit instruction never to retune thresholds
  after seeing which signatures survive (TEST 50).
- `compute_review_priority()`: MAY use `adjusted_p`/`standardized_effect`/
  `valid_episode_n` to order review attention. Every `ResearchQueueEntry`
  it produces carries `priority_basis = "DEVELOPMENT_OUTCOME_AWARE_
  SELECTION"` permanently (TEST 51) whenever a priority key is populated,
  and `ResearchQueueEntry` shares zero field names with
  `StrategyDefinition` (TEST 34/51) -- review priority can never reach a
  runtime trading rule.

## Package layout

```
src/hypothesis/
  models/entities.py       all dataclasses/enums (this doc's SS7 above)
  evidence/
    packet.py               EvidencePacket construction (SS110-F)
    queue.py                 Research Queue (SS110-H)
  proposals/
    normalize.py             raw dict -> HypothesisProposal (shape only)
    validator.py              vocabulary/complexity/policy validation
  consensus/
    reviews.py               AgentReview validation
    consensus.py              ConsensusRecord + can_preregister()
  registry/
    hypotheses.py             fingerprinting, HypothesisRegistry, versions
    strategy_registry.py      StrategyDefinition assembly
  validation/
    rules.py                  pre-preregistration gate (registry context)
    provenance.py              provenance-vs-actual-run guard (SS110-F)
  config/
    hypothesis.yaml            all guardrails (SS90), config_version-hashed
    loader.py
```

No `backtesting/`, `backtest/`, or `agents/` package exists anywhere in
the repository yet (TEST 38-39) -- Spec #005 and any AI-API adapter are
future work, not built here.

## Outcome contamination rule (SS72)

`validation/rules.py:FORBIDDEN_OUTCOME_FIELD_NAMES` (`adjusted_p`,
`raw_p`, `forward_return`, `relative_return`, `mean_return`,
`median_return`, `win_rate`, `standardized_effect`, `baseline_mean`,
`baseline_median`, `expectancy`, `sharpe`, `valid_episode_n`,
`opportunity_density`, `review_priority`) is scanned against every lane/
label/reason_code/holds_labels token on every entry/invalidation
condition, both at proposal-validation time (`proposals/validator.py`)
and again defensively at the pre-preregistration gate. This closes the
spec's own worked forbidden example (SS74: `IF adjusted_p < 0.05 AND
mean_relative_return > 1% THEN BUY`) at the type/vocabulary level, not
just by convention (TEST 18-20).
