# Spec #002 -- Example Discovery Output (Deliverable D)

**Actual pipeline outputs generated from deterministic synthetic market data.
No live-market data used anywhere in this document or in Spec #002's test suite**
(GPT Review #002 Round 1: the earlier wording -- "drawn from an actual run_discovery() run"
-- was ambiguous about whether the *market data* was real; it was not. Only the *pipeline
computation* is real: every figure below is exactly what `run_discovery()` computed against
`tests/spec002/fixtures/synthetic_universe.py` (numpy-generated, seeded, fully synthetic),
not hand-edited afterward to match a hoped-for story.

### Ticker: VOLSPK

as_of: 2025-03-24  |  timeframe: 1D

State signature:
  momentum: VERY_LOW
  relative_strength: LOW
  trend: LOW
  volatility: EXPANSION
  volume: VERY_HIGH

Selected raw measurements:
  return_63d: -0.032470829305071724
  relative_return_63d: -0.025283262808259876
  BB_width_20: 0.047911707952359085
  RVOL_20: 12.0
  ROC_10: -0.04826052759859201

Reason codes:
  TREND_EXTREME
  RS_EXTREME
  VOLUME_ANOMALY
  VOLATILITY_EXPANSION
  MOMENTUM_ACCELERATION
  MULTI_LANE_CONVERGENCE
  STATE_TRANSITION

Descriptive metrics:
  extremeness: 0.996
  persistence: 1 trading days
  state_frequency: 0.0323 (sample_count=31, support=SUFFICIENT)

Why candidate: statistically unusual/notable current state relative to
its own history and/or the eligible universe on this date.

What this does NOT mean: no claim that forward return will be positive,
no claim this is a trade recommendation -- Discovery is outcome-blind
(Spec #002 SS2) and produced this candidate using only information
available at as_of.

### Ticker: MOMACC

as_of: 2025-03-24  |  timeframe: 1D

State signature:
  momentum: VERY_HIGH
  relative_strength: VERY_HIGH
  trend: VERY_HIGH
  volatility: EXTREME_EXPANSION
  volume: NEUTRAL

Selected raw measurements:
  return_63d: 0.13598129993561092
  relative_return_63d: 0.14316886643242277
  BB_width_20: 0.07294902747599144
  RVOL_20: 1.0
  ROC_10: 0.03820930160276004

Reason codes:
  TREND_EXTREME
  RS_EXTREME
  VOLATILITY_EXPANSION
  MOMENTUM_ACCELERATION
  MULTI_LANE_CONVERGENCE

Descriptive metrics:
  extremeness: 0.996
  persistence: 2 trading days
  state_frequency: 0.0323 (sample_count=31, support=SUFFICIENT)

Why candidate: statistically unusual/notable current state relative to
its own history and/or the eligible universe on this date.

What this does NOT mean: no claim that forward return will be positive,
no claim this is a trade recommendation -- Discovery is outcome-blind
(Spec #002 SS2) and produced this candidate using only information
available at as_of.

### Ticker: FILL13

as_of: 2025-03-24  |  timeframe: 1D

State signature:
  momentum: VERY_LOW
  relative_strength: VERY_LOW
  trend: LOW
  volatility: EXTREME_EXPANSION
  volume: HIGH

Selected raw measurements:
  return_63d: -0.08875145209723012
  relative_return_63d: -0.08156388560041827
  BB_width_20: 0.08330203658857491
  RVOL_20: 1.0881965318546971
  ROC_10: -0.040241471916769855

Reason codes:
  TREND_EXTREME
  RS_EXTREME
  VOLUME_ANOMALY
  VOLATILITY_EXPANSION
  MULTI_LANE_CONVERGENCE

Descriptive metrics:
  extremeness: 0.9722
  persistence: 1 trading days
  state_frequency: 0.0323 (sample_count=31, support=SUFFICIENT)

Why candidate: statistically unusual/notable current state relative to
its own history and/or the eligible universe on this date.

What this does NOT mean: no claim that forward return will be positive,
no claim this is a trade recommendation -- Discovery is outcome-blind
(Spec #002 SS2) and produced this candidate using only information
available at as_of.

