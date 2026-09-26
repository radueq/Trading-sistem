# Spec #004 v1.0 -- Known Limitations

Explicit per the same discipline Spec #001 SS27E / Spec #002 SS47C /
Spec #003's own known-limitations doc established (don't hide
limitations to declare the module "done"). None of these block Level 1
acceptance; they are the honest boundaries of what this build can claim.

## Hard gates inherited from Spec #001/#002/#003

Evidence quality issues Discovery/Evaluation themselves already document
(QA knowledge-time, listing-status carry-forward, missingness handling,
the temporally-stratified baseline's weighted-average-of-per-bin-
statistics approximation, TIME_BLOCK bootstrap being a fixed/non-
overlapping block bootstrap not a moving one, the deferred joint/paired
resampling revisit) are not re-litigated here -- see
`docs/spec001_known_limitations.md`, `docs/spec002_known_limitations.md`,
`docs/spec003_known_limitations.md`. #004 consumes whatever `EvidenceProfile`
Evaluation produced, exactly as-is.

## Scope decisions made during implementation (Level 1, documented deliberately)

- **`StrategyHypothesis` absorbs the spec's originally-separate
  `StrategyFamily` concept** (see `docs/spec004_architecture.md`'s SS7
  section) -- Radu's final SS110-C/D diagram shows no intermediate layer,
  so this implementation uses exactly two levels (`StrategyHypothesis` =
  family, `StrategyVariant` = per-exit), not three. If a future spec ever
  needs one family to span MULTIPLE distinct entry definitions, this
  would need revisiting -- not needed for anything in Spec #004 v1.0.
- **`EntryDefinition.confirmation_conditions` semantics are a Level 1
  design choice.** The spec's `hypothesis_complexity.max_optional_
  confirmation_conditions` guardrail caps a count, but doesn't itself
  define what distinguishes a "confirmation" condition from a "core"
  one. V1 treats both as required-AND, tracked under separate budget
  counters purely for audit/complexity-review purposes -- there is no
  behavioral difference at match time. A future spec could give
  confirmation conditions genuinely different semantics (e.g. optional/
  soft-match) if that's ever needed.
- **`InvalidationCondition`'s two condition kinds (lane+holds_labels,
  reason_code+triggers_on_presence) are a Level 1 primitive**, chosen to
  express the spec's own two examples ("RS no longer HIGH/VERY_HIGH",
  "momentum transition turns negative" via `STATE_TRANSITION`/
  `MOMENTUM_ACCELERATION` reason codes) without inventing any new
  indicator. A genuinely richer invalidation vocabulary (e.g. referencing
  `TransitionEntry.acceleration`'s sign directly) is a valid future
  extension, not built speculatively now.
- **`HypothesisProposal.exit_hypotheses` holds SIGNAL_INVALIDATION
  variants only.** TIME_EXIT is always auto-derived from
  `horizon_candidates.values` at `materialize_variants()` time -- a
  proposal never enumerates it individually. Enforced by the validator
  (any TIME_EXIT entry in this field is rejected as redundant/invalid).

## Statistical/evidentiary honesty (V1, deliberate)

- **#004 never claims a hypothesis is validated.** `EvidenceProfile`
  fields motivate a proposal; nothing in this package computes or claims
  an expected live-trading return. Radu's own words: "#003 a motivat
  ipoteza; #005 va masura strategia executabila" -- and #005 does not
  exist as code yet.
- **`evidence_horizon_bars` (Spec #003, signal-bar-referenced) and
  `strategy_holding_bars` (Spec #004/#005, entry-bar-referenced) are
  DIFFERENT quantities that happen to coincide numerically only because
  `NEXT_BAR_OPEN` entry is exactly one bar after the signal bar** -- see
  `docs/spec004_architecture.md`'s SS110-A section and TEST 45. Any
  future change to entry timing (there is none planned) would break this
  coincidence and must not silently change what "3 bars" means in
  existing frozen hypotheses (their `definition_hash` would already
  differ, since `entry_execution_policy` is part of it). **PATCH #004-A
  correction (GPT Review #004 Round 1, finding #7):** the same nominal
  horizon currently shares the same exit bar between #003 and #004/#005
  (TEST 45 proves the exit indices are equal) -- it is the ENTRY
  REFERENCE point (`close(signal)` vs `open(entry)`) that differs, not
  the exit date. An earlier version of this note described the two
  conventions as "one bar off," which overclaimed a date difference that
  does not exist under the frozen convention.
- **Rejected proposals/hypotheses are never deleted** (SS53/SS108) -- the
  registry is append-only. This means a research cycle's `HypothesisUniverse`
  snapshot can grow large over many iterations; no pruning/archival
  mechanism exists yet. Not a problem at Level 1 scale; a future spec
  may need a read-only archival tier if the registry ever grows large
  enough to matter operationally.

## Performance (informational, not an acceptance blocker)

- **No live pipeline is exercised anywhere in `tests/spec004/`.** Every
  test and example runs against hand-built #003-shaped objects
  (`tests/spec004/conftest.py`), not a real `run_evaluation()` call --
  because #004 was designed from the start to never need one (SS5,
  SS110-F). This is a deliberate property of the architecture, not a
  test-suite shortcut: production usage will feed #004 the SAME kind of
  already-materialized `EvidenceProfile` objects a real Evaluation run
  produces, and there is nothing in `tests/spec003/` left unexercised by
  this choice.

## Out of scope (Spec #004 SS99, not silently included)

Backtesting, walk-forward, Locked-OOS evaluation, transaction costs,
slippage, fills, position sizing, portfolio allocation, MAE/MFE, ATR
stop optimization, take-profit optimization, broker connection, live
trading, 4H/1H data ingestion, crypto, options, and any automated GPT/
Claude API orchestration. All deferred to Spec #005 (backtesting/
execution) or later specs this one deliberately does not reach into.

## Test coverage

- All 44 required tests (Spec #004 SS97) plus 8 tests added for Radu's
  SS110 architecture-review amendments (TEST 45-52), 33 tests added for
  PATCH #004-A (TEST 53-61), and 19 tests added for PATCH #004-B
  (TEST 62-66) pass -- see `docs/spec004_test_report.md`. None are
  `PENDING`; hand-constructed fixtures are sufficient to exercise every
  required property, since no PIT/pipeline dependency exists in this
  package at all.

## PATCH #004-A (GPT Review #004 Round 1)

Seven findings, six requiring code changes plus one documentation-only
correction -- all fixed:

1. **Fixed -- preregistration could be fully bypassed.**
   `can_preregister()` treated any non-empty `human_decision` string as
   approval (even `"REJECT"`); `HypothesisRegistry.register()` accepted
   a hand-built `StrategyHypothesis(status="PREREGISTERED", ...)`
   directly with no consensus/approval/provenance check;
   `build_strategy_definition()` only checked the object's own claimed
   status, never that it went through the real registry.
   `human_decision` is now a `HumanDecision` dataclass whose `decision`
   field is constrained to `HumanDecisionValue.APPROVE`/`REJECT`;
   `registry/preregistration.py:preregister_hypothesis()` is the ONE
   atomic entry point that may produce a PREREGISTERED hypothesis;
   `HypothesisRegistry.register()` now refuses a first-time
   PREREGISTERED insert; `build_strategy_definition()` now verifies the
   supplied hypothesis/variant against what the registry itself has
   stored. TEST 53-55.
2. **Fixed -- the provenance guard existed but wasn't wired into the
   gate.** `check_provenance_matches_run()` was correct but
   `validate_for_preregistration()` never called it and didn't even
   receive an `EvaluationRunRegistry`. It now requires `run_registry`
   and calls the check itself, plus two new internal-consistency checks
   (`parent_signature_id`/`signature_set_id` must agree with
   `evidence_provenance`'s own copies of those fields). TEST 56.
3. **Fixed -- `EvidencePacket` could combine incompatible artifacts.**
   `build_evidence_packet()` only checked `signature_id` agreement --
   never timeframe, Discovery engine/config version, exact horizon-set
   match, duplicate horizons, or a single shared `evaluation_mode`. All
   six are now hard-fail checks. TEST 57.
4. **Fixed -- the Research Queue reintroduced implicit best-horizon
   selection.** Producing one `ResearchQueueEntry` per `(signature,
   horizon)` meant the same signature could occupy up to 5 slots, with
   whichever horizon looked strongest tending to rank first -- an
   operational backdoor around "never select the best horizon" even
   with no field named `selected_horizon`. The queue is now strictly
   signature-level (one `EvidencePacket` -> one entry), keyed off a
   fixed config policy (`evidence_reference.reference_horizon_bars`)
   applied identically to every signature. TEST 58.
5. **Fixed -- TIME_EXIT provenance was hardcoded, and baseline was
   auto-deduced from `min(horizon)`.** `materialize_variants()` always
   wrote `parameter_source=EVIDENCE_DERIVED` regardless of how the
   candidate set was actually chosen, and tagged the shortest horizon
   `BASELINE_VARIANT` by construction. `HorizonCandidateSet.
   parameter_source` is now a required, fingerprinted field that flows
   through to every TIME_EXIT variant unchanged; no variant is
   auto-tagged baseline -- a caller must explicitly pass
   `baseline_time_exit_bars` (one of the candidate values) to
   `materialize_variants()`, and the default is no baseline assumed
   (all `EXPERIMENTAL_VARIANT`). TEST 59-60.
6. **Fixed -- "append-only registry" was only process memory.**
   `HypothesisRegistry` stored everything in plain Python dicts/sets --
   history vanished on process restart. `registry/persistence.py` adds
   `JsonlAuditLog` (append-only JSONL, one line per event) and
   `PersistentHypothesisRegistry`, which replays the log into an
   equivalent registry from nothing but the file -- verified by
   reconstructing from a completely independent, freshly opened log
   handle. Composes with, never replaces, the pure in-memory
   `HypothesisRegistry`. TEST 61.
7. **Fixed (documentation only) -- imprecise "one bar off" framing.**
   See the corrected note above under "Statistical/evidentiary
   honesty": the same nominal horizon currently shares the same exit bar
   between #003 and #004/#005; the actual difference is the entry
   reference point, not the exit date.

No changes requested to, or made in, Spec #001-#003's architecture, and
Spec #005 remains out of scope -- per Radu's own explicit instruction
closing the review.

## PATCH #004-B (GPT Review #004 Round 2)

Four structural findings plus one minor point -- all fixed. Scope was
strictly these five items; none of PATCH #004-A's 7 findings, nor
Spec #001-#003's architecture, were reopened.

1. **Fixed -- approval was never tied to the hypothesis it approved.**
   `preregister_hypothesis()` received `draft`, `proposal_validation`,
   and `consensus` with nothing verifying they all named the SAME
   proposal -- a caller could hand in APPROVE for proposal A while
   preregistering an unrelated draft B, since `ProposalValidationResult`
   didn't even carry a `proposal_id`. Fixed: `ProposalValidationResult.
   proposal_id` was added; `preregister_hypothesis()` now requires a
   `proposal=` argument and verifies `proposal.proposal_id ==
   proposal_validation.proposal_id == consensus.proposal_id ==
   draft.hypothesis_provenance.proposal_id`, plus
   `draft.hypothesis_provenance.approved_by`/`approved_at` must match
   `consensus.human_decision.decided_by`/`decided_at`. TEST 62.
2. **Fixed -- content-addressed identity was never re-verified at the
   gate.** The design's central claim is that `hypothesis_id`/
   `definition_hash`/`strategy_variant_id`/`variant_definition_hash` are
   derived from content -- but nothing recomputed the fingerprint at
   preregistration and compared it against what a caller supplied. A
   hand-built object with an arbitrary, non-matching id/hash could pass
   every other check and reach the registry. Fixed:
   `validate_for_preregistration()` now recomputes
   `hypothesis_fingerprint()` from the hypothesis's own fields and
   hard-fails on any mismatch, then does the same per-variant with
   `variant_fingerprint()` against the independently-recomputed (never
   the hypothesis's own possibly-wrong) `definition_hash`. TEST 63.
3. **Fixed -- a `StrategyVariant` could be silently rewritten after
   registration if only `variant_tag` changed.** `variant_tag` is
   deliberately excluded from `variant_definition_hash` (it is
   methodological metadata, not trading meaning), but `register_variant()`
   compared only that hash -- so the SAME id with the SAME hash but a
   DIFFERENT `variant_tag` (e.g. EXPERIMENTAL_VARIANT rewritten to
   BASELINE_VARIANT after seeing backtest results) was silently accepted.
   Fixed: `register_variant()` now compares full object equality: any
   difference at all, including `variant_tag`, is rejected. TEST 64.
4. **Fixed -- persistence was durable but not atomic.**
   `PersistentHypothesisRegistry.preregister()` wrote one
   `hypothesis_preregistered` line followed by N separate
   `variant_registered` lines -- a crash between appends could leave the
   log with a hypothesis durable with only some of its variants, or
   none. Fixed: a single `preregistration_committed` record now carries
   `{hypothesis, variants[]}` together in ONE JSONL line; replay is now
   genuinely all-or-nothing. TEST 65.
5. **Fixed (minor) -- Research Queue did not reject a duplicate
   `signature_id`.** `[packet_SIG_A, packet_SIG_A]` could silently
   produce two queue entries for the same signature. `build_research_
   queue()` now hard-fails on any duplicate `signature_id` among the
   supplied packets. TEST 66.

No changes requested to, or made in, PATCH #004-A's 7 findings or
Spec #001-#003's architecture, per GPT's own closing note: "nu mai văd
nevoie de încă un review arhitectural larg."
