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
  differ, since `entry_execution_policy` is part of it).
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
  SS110 architecture-review amendments (TEST 45-52) pass -- see
  `docs/spec004_test_report.md`. None are `PENDING`; hand-constructed
  fixtures are sufficient to exercise every required property, since no
  PIT/pipeline dependency exists in this package at all.
