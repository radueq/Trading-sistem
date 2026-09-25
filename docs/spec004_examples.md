# Spec #004 v1.0 -- Example Hypothesis Generation Output

**All four examples below run the REAL #004 pipeline (normalize ->
validate -> consensus -> materialize_variants -> pre-preregistration
gate -> registry) against hand-built #003-shaped EvidenceProfiles --
no live-market data, nothing hand-edited.**

### Example A -- Valid LONG continuation hypothesis

EvidencePacket: signature=VOL_COMPRESSION_RS_HIGH, primary_horizon_bars=2, primary_relative_mean=0.0080, primary_adjusted_p=0.0200

Proposal valid: True (complexity_status=OK)
StrategyHypothesis: hypothesis_id=hyp_ea1393605875fe9f, direction=LONG, status=PREREGISTERED
Materialized variants (4): var_cf72475929..=TIME_EXIT:1, var_1ec51eda72..=TIME_EXIT:2, var_bc9f176aa0..=TIME_EXIT:3, var_3322a6256f..=SIGNAL_INVALIDATION:5

### Example B -- Negative effect must NOT auto-flip to SHORT

LONG proposal (built from negative-effect evidence) stays LONG: valid=True, hypothesis_id=hyp_792205fe4ead5603
SHORT proposal is a SEPARATE, explicit hypothesis: valid=True, hypothesis_id=hyp_a662e0696f3df933
Two distinct hypothesis_ids: True (never the same record silently flipped)
Registry now holds both: 2 PREREGISTERED hypotheses on the same signature

### Example C -- Horizon trap: peak at 3 bars, no auto exit=3

Decay curve: [(1, 0.002), (2, 0.006), (3, 0.012), (5, 0.008), (10, 0.001)]
Strongest single point: 3 bars (mean=0.0120) -- tempting to declare 'exit=3', but #004 never does this automatically.
materialize_variants() produced 3 TIME_EXIT variants (bars=[2, 3, 5]), all frozen into hypothesis.variant_ids BEFORE any backtest -- #005 selects among these, never invents 'the' 3-bar exit after the fact.
No field named selected_horizon/optimal_horizon exists anywhere on StrategyHypothesis: confirmed structurally by TEST 12.

### Example D -- Over-complex proposal rejected by the complexity guardrail

Proposal: 5 entry core_conditions + 4 SIGNAL_INVALIDATION exit variants
validate_proposal(): valid=False, complexity_status=HYPOTHESIS_COMPLEXITY_EXCEEDED
  - entry.core_conditions has 5, exceeds max_entry_conditions=3 (SS12/TEST 8)
  - proposal has 4 SIGNAL_INVALIDATION exit variant(s), which combined with the mandatory TIME_EXIT family exceeds max_exit_families_per_hypothesis=2
  - total variant count 7 exceeds max_variants_per_family=6 (SS106-107)
hyp registered as PREREGISTERED: False (must be False)
Proposal record retained in registry (never silently deleted): True
Proposal marked rejected: True
