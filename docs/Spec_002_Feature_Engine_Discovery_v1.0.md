# Spec #002 -- Feature Engine + Outcome-Blind Discovery Engine -- Recovered Original Text

**Recovery note (Claude, 2026-09-30), not part of the original specification:**
This text was recovered directly from this Claude Code session's own transcript (`5232cc45-b2e4-59d6-ba23-9687d55bed17.jsonl`) -- the chat messages Radu actually sent to Claude Code at the time this spec was implemented -- not from Radu's separate GPT conversation history, and not paraphrased or reconstructed from memory. It was sent as a single message, already final. Each fragment below is reproduced byte-for-byte from the transcript, in the exact chronological order it was sent, with no correction, no reformatting, and no added or removed text beyond this note and the fragment-boundary markers. **This recovery has not yet been independently verified by Radu** -- he should treat this file as a candidate primary source to check, not as confirmed.

---

---

> **Original message 1/1** -- Radu, to Claude Code, session `5232cc45-b2e4-59d6-ba23-9687d55bed17`, transcript line 1396, timestamp `2026-09-21T16:52:58.866Z` (UTC).

---

Da. Mai jos este varianta pe care o consider suficient de precisă pentru a fi dată direct în aceeași sesiune Claude Code.
Fac însă o corecție față de mesajul meu anterior: am folosit expresia „candidate scoring/ranking”. Asta ar contrazice consensul deja stabilit cu Claude. Discovery nu va produce Alpha Score și nu va face ranking după „cât de bun este trade-ul”. Discovery rămâne outcome-blind și descrie stări/tranziții. Reducerea volumului de candidați se face determinist, fără forward returns.
IMPLEMENTATION SPECIFICATION #002
Feature Engine + Outcome-Blind Discovery Engine — Level 1
Version: 1.0
Status: APPROVED FOR IMPLEMENTATION
Depends on: Spec #001 Accepted Baseline — commit `918f3f7`
Primary market: US Equities
Primary timeframe V1: Daily
Research holding domain downstream: 3–30 trading days
Architecture requirement: timeframe-agnostic; 4H/1H must be addable later without redesign
Execution owner: Claude Code
Thread Lead / final review: GPT
1. OBJECTIVE
Build the first quantitative layer above Data Foundation.
The module must transform PIT-safe OHLCV data into:

```
OHLCV
  ↓
Feature Engine
  ↓
Normalized Feature State
  ↓
State Signature
  ↓
State Transition
  ↓
Outcome-Blind Discovery
  ↓
Research Candidates
```

This module does NOT determine whether a state predicts profitable returns.
It answers:
„Ce se întâmplă neobișnuit sau structural interesant ACUM în comportamentul acestei acțiuni?”
It does NOT answer:
„Ce acțiune va crește?”
That belongs downstream.
2. FUNDAMENTAL RULE
Discovery Engine is:
OUTCOME-BLIND
The following are forbidden inputs:

* future returns;
* forward returns;
* win rate;
* expectancy;
* profit factor;
* Sharpe derived from subsequent performance;
* future maximum excursion;
* future drawdown;
* labels such as WINNER/LOSER;
* backtest results;
* analyst targets;
* LLM opinions about future price.

No feature may use information after `as_of`.
Violation = IMPLEMENTATION BLOCKER / TEST FAILURE.
3. IMPORTANT DISTINCTION
We have three different concepts:
Feature
A numerical observation.
Example:

```
RS_63D_percentile = 0.91
BBWidth_percentile = 0.08
RVOL_20D = 2.4
```

State
Interpretation of the current feature position.
Example:

```
RS = HIGH
VOLATILITY = COMPRESSED
VOLUME = EXTREME
```

Transition
Change in that state.
Example:

```
VOLATILITY:
COMPRESSED → EXPANDING
```

These must remain separate in the data model.
4. NO COMBINATORIAL TRANSITION ENGINE
Do NOT enumerate:

```
State A → State B → State C
```

across all possible state combinations.
Transitions must use the dimensional representation already accepted in Master Context:

```
X(t)
ΔX(t)
Δ²X(t)
```

where appropriate.
Example:

```
BBWidth percentile = 0.08
ΔBBWidth            = +0.04
Δ²BBWidth           = +0.03
```

This describes compression beginning to expand without generating thousands/millions of categorical transition paths.
5. TIMEFRAME ARCHITECTURE
V1 calculates features on:
`1D`
But no calculation engine should assume internally that Daily is the only possible timeframe.
Every feature output must contain:

```
security_id
as_of
timeframe
feature_name
feature_value
```

Example:

```
12345
2026-09-21
1D
bb_width_percentile
0.07
```

Later we must be able to introduce:

```
4H
1H
```

without redesigning Feature Engine.
Do not implement 4H or 1H now.
6. TRADING HORIZON
The current research domain is:
3–30 trading days
This is NOT an exit rule.
It exists so that future Evaluation/Backtesting modules know what outcome horizons matter.
Spec #002 must NOT calculate those outcomes.
Daily lookback and holding period are different concepts.
7. DATA ACCESS
All historical market data must come through the accepted PIT interface from Spec #001.
Downstream Discovery modules must NOT:

* query SQLite directly;
* import repository functions to bypass PIT;
* read raw database tables;
* access future corporate actions/status information.

Add an architectural test preventing direct storage/repository access from Feature/Discovery modules.
8. IMPORTANT #001 LIMITATIONS
Two known limitations from Spec #001 remain hard gates before research-grade Discovery:
QA knowledge-time
Historical `qa_pass` is not yet guaranteed knowledge-time immutable.
Listing status carry-forward
Last known listing status is not yet carried forward correctly in all situations.
Therefore:
Level 1 #002 may prototype and test the Discovery software.
But:
No result from #002 may be labelled research-grade until these two #001 limitations are resolved.
Do not silently fix them inside #002.
If they prevent implementation, report `IMPLEMENTATION BLOCKER`.
9. FEATURE LANES
V1 contains five primary feature families.
Lane A — Trend
Minimum features:

```
return_20d
return_63d
return_126d

sma_20
sma_50
sma_200

distance_sma20
distance_sma50
distance_sma200

slope_sma20
slope_sma50
```

Do not define:

```
trend_score = 87
```

as an alpha score.
The individual measurements remain observable.
10. LANE B — RELATIVE STRENGTH
Relative strength must be relative to a benchmark, initially configurable.
Default TEST_CONFIG benchmark may be:

```
SPY
```

Features:

```
relative_return_20d
relative_return_63d
relative_return_126d

rs_percentile_cross_sectional
```

Architecture must later permit:

```
sector benchmark
industry benchmark
alternative market benchmark
```

without redesign.
Do not implement sector/industry RS now.
11. LANE C — VOLATILITY
We explicitly want both ATR and Bollinger Band Width.
Minimum:

```
ATR_14
ATR_pct
ATR_percentile

BB_width_20
BB_width_percentile

realized_volatility_20
realized_volatility_percentile
```

Important:
ATR and BB Width are not interchangeable.
We want to detect both absolute/relative volatility and compression.
12. LANE D — VOLUME
Minimum:

```
ADV_20
volume_ratio_20
volume_percentile
RVOL_20
```

We specifically want detection of unusual volume.
Do not include unusual options activity.
Options flow = OUT OF SCOPE V1.
13. LANE E — MOMENTUM / CHANGE
Minimum:

```
ROC_5
ROC_10
ROC_20

momentum_delta
momentum_acceleration
```

Where appropriate represent:

```
X(t)
ΔX(t)
Δ²X(t)
```

Do not turn these into BUY/SELL signals.
14. NORMALIZATION
Primary normalization method V1:
rolling percentile
not global z-score.
Reason:
Different features have different distributions and outlier behaviour.
Architecture:

```
raw feature
↓
rolling historical distribution
↓
percentile
```

Window length must be configurable.
For Level 1 TEST_CONFIG use:

```
252 trading observations
```

This is a test/default engineering parameter, not a validated trading rule.
It must be identifiable in config as:

```
TEST_CONFIG
```

not:

```
OPTIMAL_PARAMETER
```

15. CROSS-SECTIONAL VS TIME-SERIES NORMALIZATION
Do not conflate them.
Support metadata:

```
normalization_type:
    TIME_SERIES
    CROSS_SECTIONAL
```

Example:
BB Width percentile:
Where is this stock's BB Width relative to its own historical BB Width?
= TIME_SERIES.
RS percentile:
Where is this stock's RS relative to today's eligible universe?
= CROSS_SECTIONAL.
The distinction must survive into output.
16. STATE REPRESENTATION
Feature values may be translated into descriptive states.
Example configurable state vocabulary:

```
VERY_LOW
LOW
NEUTRAL
HIGH
VERY_HIGH
```

For compression-type features, semantic aliases may be:

```
EXTREME_COMPRESSION
COMPRESSION
NORMAL
EXPANSION
EXTREME_EXPANSION
```

Thresholds belong in external config.
For Level 1 they are TEST_CONFIG only.
Do not claim that these thresholds generate alpha.
17. STATE SIGNATURE
For each security/date:

```
StateSignature
```

Example:

```
security_id: 12345
as_of: 2026-09-21
timeframe: 1D

trend: HIGH
relative_strength: VERY_HIGH
volatility: COMPRESSION
volume: HIGH
momentum: HIGH
```

But retain the underlying numerical features.
Never store only labels.
18. TRANSITION REPRESENTATION
For every relevant normalized feature, permit:

```
current_value
delta_1
delta_n
acceleration
```

where mathematically meaningful.
Example:

```
bb_width_percentile = 0.08
delta_5 = +0.07
acceleration = +0.03
```

Possible semantic description:

```
COMPRESSION → EXPANDING
```

But the numeric values remain source of truth.
19. DISCOVERY ENGINE
Discovery consumes:

```
FeatureVector
StateSignature
TransitionVector
```

and produces:

```
DiscoveryCandidate
```

Discovery may use ONLY information available at `as_of`.
It must identify phenomena based on characteristics such as:

* extremeness;
* unusual cross-sectional position;
* unusual time-series position;
* state changes;
* multi-lane convergence;
* contradictions between lanes;
* persistence;
* acceleration/deceleration.

But it may NOT use future outcomes.
20. CONVERGENCE
Convergence Engine does NOT create one global Alpha Score.
Forbidden:

```
score =
0.3 Trend +
0.2 RS +
0.2 Volume +
...
```

unless someday empirically justified downstream.
Instead output something like:

```
active_lanes:
    TREND
    RELATIVE_STRENGTH
    VOLUME

state_signature:
    TREND_HIGH
    RS_VERY_HIGH
    VOLUME_EXTREME
```

Convergence = description, not prediction.
21. CANDIDATE REDUCTION
We still need to prevent thousands of observations reaching LLMs.
Reduction must therefore be:
outcome-blind.
Allowed mechanisms:

* feature extremeness;
* transition magnitude;
* persistence;
* statistical unusualness;
* multi-lane activation;
* deterministic candidate budget;
* diversity sampling.

Forbidden:

* historical profitability;
* forward-return performance;
* win rate;
* expectancy;
* backtest ranking.

22. CANDIDATE BUDGET
Candidate Budget must be configurable.
Do NOT hardcode:

```
top 50 stocks
```

as a trading truth.
Implement something such as:

```
candidate_budget:
    enabled: true
    max_candidates: TEST_CONFIG
```

Selection must remain deterministic for identical input/config.
If two candidates tie, use a deterministic tie-breaker such as stable `security_id`.
23. DIVERSITY
Candidate Budget must not simply select 100 copies of the same phenomenon.
Support diversity across the feature/state space.
But do NOT invent hand-built „strategy families” claiming they are optimal.
At Level 1 diversity can use observable state dimensions such as:

```
dominant_lane
state_signature
transition_signature
```

The exact policy must be visible in config and documentation.
No hidden heuristic.
24. NO ALPHA SCORE
This is important enough to repeat.
DiscoveryCandidate MUST NOT contain `alpha_score`.
It may contain descriptive measures such as:

```
extremeness
persistence
transition_magnitude
active_lane_count
rarity
```

These mean:
statistically noteworthy
NOT:
expected profitable.
Field names and documentation must preserve that distinction.
25. RARITY
Rarity is descriptive only.
Example:

```
state_frequency = 0.014
```

means the state occurred in 1.4% of the relevant observations.
It does NOT mean the state is attractive.
Do not implement:

```
rarity < 2% → BUY candidate
```

as a trading rule.
Any rarity threshold used to control computational volume is `TEST_CONFIG`.
26. MINIMUM SAMPLE SUPPORT
When calculating descriptive historical frequency/persistence, insufficient samples must be explicit.
Example:

```
sample_count
support_status:
    SUFFICIENT
    INSUFFICIENT
```

Level 1 test floor may be configurable.
Do not silently calculate impressive-looking statistics from tiny samples.
No outcome statistics are involved here.
27. OUTPUT CONTRACT
A `DiscoveryCandidate` should contain at minimum:

```
security_id
ticker_as_of
as_of
timeframe

feature_vector
normalized_feature_vector

state_signature
transition_vector

active_lanes

descriptive_metrics:
    extremeness
    persistence
    state_frequency
    sample_count

reason_codes

config_version
feature_engine_version
```

No prose from an LLM is required.
28. REASON CODES
Candidate selection must be explainable.
Examples:

```
TREND_EXTREME
RS_EXTREME
VOLUME_ANOMALY
VOLATILITY_COMPRESSION
VOLATILITY_EXPANSION
MOMENTUM_ACCELERATION
MULTI_LANE_CONVERGENCE
STATE_TRANSITION
PERSISTENT_STATE
```

These are descriptions, not recommendations.
Output example:

```
AAPL
reason_codes:
    RS_EXTREME
    VOLATILITY_COMPRESSION
    VOLUME_ANOMALY
```

29. UNIVERSE ELIGIBILITY
We previously separated:

```
Data QA
```

from:

```
Universe Eligibility
```

Keep that separation.
Create a dedicated eligibility layer.
Potential rules:

```
minimum price
minimum history
minimum liquidity
exchange eligibility
market-cap floor
```

But values remain configurable.
Important decision already made by Radu:
Market cap ≈ $1–2B must NOT define a narrow target universe.
If market cap filtering is later used, conceptually it is:

```
minimum floor
```

not:

```
select companies around $1–2B
```

For Level 1, if reliable PIT market cap is unavailable, do NOT fabricate it.
Mark:

```
MARKET_CAP_FILTER = PENDING_DATA
```

and continue with available eligibility dimensions.
30. MISSING DATA
No silent forward-fill.
Feature calculations must expose:

```
VALID
INSUFFICIENT_HISTORY
MISSING_INPUT
INVALID_INPUT
```

If a 252-observation percentile requires 252 observations and only 100 exist:
do not silently calculate an equivalent 252-day statistic.
Configuration may permit `min_periods`, but it must be explicit.
31. CORPORATE ACTIONS
Features must use the appropriate PIT-safe price representation.
For V1:
split-adjusted prices are approved.
`total_return_adjusted_close` is:
EXPERIMENTAL_NOT_APPROVED_FOR_RESEARCH
Do not use it as Feature Engine input unless explicitly overridden in a test.
32. BENCHMARK DATA
RS requires benchmark data.
Benchmark must:

* use same PIT principles;
* use same timeframe;
* have explicit missing-data handling;
* be configurable.

TEST_CONFIG:

```
benchmark = SPY
```

Do not embed SPY throughout calculation code.
33. CONFIGURATION
All tunable parameters must live outside calculation logic.
Suggested structure:

```
config/
    features.yaml
    states.yaml
    discovery.yaml
    eligibility.yaml
```

Every output must carry:

```
config_version
```

so historical results can be reproduced.
34. DETERMINISM
Identical:

```
data
as_of
config
software version
```

must produce identical Feature/Discovery output.
No randomness unless an explicit seed is supplied.
Prefer no randomness in Level 1.
35. STORAGE
Do not prematurely optimize storage.
Correctness > performance.
Feature results may initially use:

* Python objects/dataframes;
* SQLite tables if useful;
* serialized test fixtures.

Claude Code may choose the simplest implementation consistent with reproducibility.
But raw Data Foundation tables must not be modified.
36. TOKEN ECONOMY
Normal execution of Spec #002 must require:
0 LLM tokens
All calculations are Python.
Future LLM agents will receive compact structures such as:

```
Ticker
State Signature
Transition Signature
Reason Codes
Selected statistics
```

not raw candles.
This remains a structural requirement.
37. PERFORMANCE
Do not optimize prematurely.
But implementation must avoid obviously pathological designs such as:

```
one database query
per feature
per ticker
per day
```

Prefer retrieving the required PIT history once and calculating feature families from the same local series.
Performance benchmark is informational in Level 1, not an acceptance blocker unless implementation is unusably slow.
38. REQUIRED TESTS
At minimum:
TEST 1 — Feature determinism
Same data/config → identical features.
TEST 2 — No future candle leakage
Add future candles → features for earlier `as_of` unchanged.
TEST 3 — Rolling percentile
Known synthetic series → expected percentile manually verifiable.
TEST 4 — Trend calculations
Synthetic monotonic series → expected returns/slopes/distances.
TEST 5 — Relative Strength
Ticker vs benchmark synthetic series → manually verifiable RS.
TEST 6 — BB Width compression
Construct compressed price series → BB Width falls appropriately.
TEST 7 — ATR
Known OHLC sequence → ATR manually verifiable.
TEST 8 — Volume anomaly
Known volume spike → RVOL/percentile behaves correctly.
TEST 9 — Momentum delta/acceleration
Synthetic acceleration → expected Δ/Δ².
TEST 10 — Missing history
Insufficient observations → explicit status, no silent calculation.
TEST 11 — State mapping
Known percentile values → expected state labels.
TEST 12 — Transition representation
Known X(t) path → expected ΔX/Δ²X.
TEST 13 — Convergence without Alpha Score
Multiple active lanes → descriptive convergence output; no global predictive score.
TEST 14 — Candidate determinism
Same universe → same candidates/order.
TEST 15 — Candidate Budget
Large synthetic candidate set → configured budget respected.
TEST 16 — Diversity
Budget reduction does not collapse trivially into one identical state signature when alternatives satisfying policy exist.
TEST 17 — No outcome fields
Static/schema/AST test ensuring Discovery does not import/use forward-return/backtest/evaluation modules.
TEST 18 — PIT gateway enforcement
Discovery/Feature Engine cannot directly access Data Foundation repository/storage.
TEST 19 — Total-return prohibition
Experimental total-return series rejected as research input by default.
TEST 20 — Benchmark configuration
Changing benchmark changes RS through config, not code modification.
39. MANUAL CONTROLLED EXAMPLES
In addition to automated tests, Test Report must contain at least 3 human-readable examples.
Example format:

```
Ticker: SYNTH_A

Trend:
HIGH

RS:
VERY_HIGH

BB Width:
8th percentile

Volume:
2.3x ADV

Momentum:
accelerating

Reason Codes:
RS_EXTREME
VOLATILITY_COMPRESSION
VOLUME_ANOMALY

Why candidate:
statistically unusual current state

What this DOES NOT mean:
no claim that forward return will be positive
```

This distinction is mandatory.
40. OUTPUT VOLUME REPORT
Because token economy is part of the architecture, #002 must report:

```
initial universe count
eligibility count
valid-feature count
discovery-observation count
candidate count after budget
```

For synthetic tests these can be synthetic counts.
Later these become operational telemetry.
41. NO LLM
Claude/GPT may design/review the module.
But runtime module must not call:

* Claude API;
* OpenAI API;
* external reasoning model.

If LLM-related imports appear in #002 runtime code:
FAIL.
42. OUT OF SCOPE
Explicitly NOT part of #002:

* forward returns;
* historical profitability;
* Evaluation Engine;
* Hypothesis Generator;
* Walk-Forward;
* OOS validation;
* Alpha Score;
* trade entry decision;
* trade exit decision;
* stop-loss;
* position sizing;
* portfolio construction;
* broker integration;
* XTB;
* Tastytrade;
* crypto;
* options flow;
* Reddit/X/StockTwits sentiment;
* news;
* fundamentals;
* analyst ratings;
* LLM consensus.

Do not implement them.
43. 4H / 1H
Architecture must permit later:

```
1D → context
4H → setup/timing
1H → execution refinement
```

But #002 implements only Daily.
Do not add intraday downloads, indicators or tests now.
We will only introduce 4H/1H if later evidence shows incremental value or insufficient opportunity density on Daily.
44. CANDIDATE FREQUENCY
Do not design the system to manufacture a predetermined number of trades.
We will eventually measure:

```
candidate frequency
qualified hypothesis frequency
trade frequency
expectancy
robustness
```

If Daily produces few valid opportunities, we investigate additional independent edge/timeframes.
We do NOT loosen filters simply to produce more trades.
45. VERSIONING
Feature output must identify:

```
feature_engine_version
config_version
```

Discovery output:

```
discovery_engine_version
config_version
```

Changing a feature definition must change the appropriate version.
No silent formula changes.
46. IMPLEMENTATION BLOCKER PROTOCOL
Claude Code may make normal low-level engineering choices.
It must STOP and report an `IMPLEMENTATION BLOCKER` before making unilateral decisions involving:

* changing accepted PIT semantics;
* changing Data Foundation contract;
* introducing outcome awareness;
* adding predictive scoring;
* redefining state dimensions;
* using future information;
* changing universe philosophy;
* introducing a new external paid data dependency;
* adding LLM calls;
* making 4H/1H part of V1;
* changing the 3–30 day research domain.

Do not invent a workaround silently.
47. DELIVERABLES
At completion return:
A. Test Report

```
PASS
FAIL
PENDING
```

for every required test.
B. Architecture Note
Including:

* modules created;
* data flow;
* feature formulas;
* normalization;
* state representation;
* transition representation;
* candidate-budget mechanism;
* PIT enforcement;
* configuration;
* versioning.

C. Known Limitations
Explicitly list:

* Data Foundation QA knowledge-time limitation;
* listing-status carry-forward limitation if still present;
* Level 1 provider limitations;
* lack of PIT market cap if applicable;
* Daily-only limitation;
* any insufficient historical data issues.

D. Example Discovery Output
At least 3 controlled examples.
E. Performance/Volume Report
Basic execution time plus universe → candidates counts.
48. ACCEPTANCE GATE
Spec #002 is NOT accepted merely because tests execute.
Acceptance requires:

```
No future leakage
No outcome contamination
No Alpha Score
Deterministic calculations
PIT gateway respected
Features manually verifiable
State/transition representation reproducible
Candidate reduction outcome-blind
Config externalized
No LLM runtime
```

Any violation of the first three:
HARD FAIL.
49. EXPECTED PACKAGE STRUCTURE
Claude Code may adjust names for good engineering reasons, but conceptually:

```
src/
  discovery/
      features/
          trend.py
          relative_strength.py
          volatility.py
          volume.py
          momentum.py

      normalization/
          rolling_percentile.py
          cross_sectional.py

      states/
          mapper.py
          transitions.py

      eligibility/
          engine.py

      candidate/
          convergence.py
          selector.py
          reason_codes.py

      config/
          loader.py

      models/
          entities.py

      engine.py
```

Tests should mirror this structure.
50. INSTRUCTION TO CLAUDE CODE
Poți copia de aici în jos ca instrucțiune finală:
Implement Implementation Specification #002 against the accepted Spec #001 baseline at commit `918f3f7`.
Spec #001 Data Foundation is CLOSED. Do not redesign or refactor it unless implementation of #002 reveals a genuine blocker.
Build a Daily, timeframe-agnostic Feature Engine and Outcome-Blind Discovery Engine.
Discovery must not use forward outcomes, profitability, backtest results or Alpha Scores.
The five initial lanes are:
Trend / Relative Strength / Volatility / Volume / Momentum-Change.
Preserve raw features, normalized features, state signatures and dimensional transitions separately.
Candidate reduction must be deterministic and outcome-blind.
All tunable thresholds are external TEST_CONFIG, not claimed trading rules.
Normal runtime must use zero LLM calls.
Implement the required tests and produce Test Report, Architecture Note, Known Limitations, controlled Discovery examples and Volume/Performance Report.
Known #001 limitations concerning QA knowledge-time and listing-status carry-forward remain hard gates before research-grade Discovery. Do not silently fix them inside #002.
If the specification requires an architectural decision not explicitly authorized, report `IMPLEMENTATION BLOCKER` rather than choosing it unilaterally.
Do not implement Spec #003.
Un punct important pentru tine, Radu
În #002 nu încercăm încă să găsim strategia profitabilă. Construim „simțurile” sistemului: să poată vedea riguros că o acțiune este în trend, are RS neobișnuit, volum anormal, compresie de volatilitate sau că aceste lucruri tocmai se schimbă.
Abia următoarea separare Discovery → Evaluation ne permite să întrebăm:
„Când am mai văzut această stare, ce s-a întâmplat în următoarele 3/5/10/20/30 zile?”
Acolo începe efectiv căutarea edge-ului — și tocmai separarea asta ne protejează de data mining-ul pe care l-am discutat cu Claude.
