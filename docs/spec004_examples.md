# Spec #004 v1.0 -- Example Hypothesis Generation Output

**All four examples below run the REAL #004 pipeline (normalize ->
validate -> consensus -> materialize_variants -> the ONE atomic
`preregister_hypothesis()` gate -> registry) against hand-built
#003-shaped EvidenceProfiles -- no live-market data, nothing
hand-edited. Updated for PATCH #004-A: the gate that used to be a
hand-rolled sequence of checks in this script is now the SAME
`registry.preregistration.preregister_hypothesis()` production code
path every other caller must use.**

### Example A -- Valid LONG continuation hypothesis

EvidencePacket: signature=VOL_COMPRESSION_RS_HIGH, primary_horizon_bars=3 (from config evidence_reference.reference_horizon_bars, never a free per-call parameter), primary_relative_mean=0.0100, primary_adjusted_p=0.0100 (DIAGNOSTIC ONLY in V1 -- exchangeability_status='UNVERIFIED', never drives Research Queue ranking: p_key=inf unconditionally)

Proposal valid: True (complexity_status=OK)
StrategyHypothesis: hypothesis_id=hyp_6f630f4e89cdfb2a, direction=LONG, status=PREREGISTERED
Materialized variants (4): var_09a129a226..=TIME_EXIT:1, var_17d7fa1f46..=TIME_EXIT:2, var_2809cada3f..=TIME_EXIT:3, var_62ae6ec7f9..=SIGNAL_INVALIDATION:5
Preregistered through the ONE atomic gate (registry.preregistration.preregister_hypothesis()) -- never a hand-built PREREGISTERED object handed to register() (PATCH #004-A finding #1).

### Example B -- Negative effect must NOT auto-flip to SHORT

LONG proposal (built from negative-effect evidence) stays LONG: valid=True, hypothesis_id=hyp_ac492ed399f95495
SHORT proposal is a SEPARATE, explicit hypothesis: valid=True, hypothesis_id=hyp_f4dab11069d75780
Two distinct hypothesis_ids: True (never the same record silently flipped)
Registry now holds both: 2 PREREGISTERED hypotheses on the same signature

### Example C -- Horizon trap: peak at 3 bars, no auto exit=3

Decay curve: [(1, 0.002), (2, 0.006), (3, 0.012), (5, 0.008), (10, 0.001)]
Strongest single point: 3 bars (mean=0.0120) -- tempting to declare 'exit=3', but #004 never does this automatically.
materialize_variants() produced 3 TIME_EXIT variants (bars=[2, 3, 5]), all frozen into hypothesis.variant_ids BEFORE any backtest -- #005 selects among these, never invents 'the' 3-bar exit after the fact.
No variant is auto-tagged BASELINE_VARIANT by `min(horizon)` either (PATCH #004-A finding #5, TEST 60): variant_tags here are ['EXPERIMENTAL_VARIANT'] -- all EXPERIMENTAL_VARIANT unless a baseline is explicitly pre-designated via `baseline_time_exit_bars`.
No field named selected_horizon/optimal_horizon exists anywhere on StrategyHypothesis: confirmed structurally by TEST 12.

### Example D -- Over-complex proposal rejected by the complexity guardrail

Proposal: 5 entry core_conditions + 4 SIGNAL_INVALIDATION exit variants
validate_proposal(): valid=False, complexity_status=HYPOTHESIS_COMPLEXITY_EXCEEDED
  - entry.core_conditions has 5, exceeds max_entry_conditions=3 (SS12/TEST 8)
  - total variant count 7 exceeds max_variants_per_family=6 (SS106-107)
hyp registered as PREREGISTERED: False (must be False)
Proposal record retained in registry (never silently deleted): True
Proposal marked rejected: True
