# Spec #003 -- Outcome-Aware Evaluation Engine (Fast-Swing / Bar-Based) v1.1 -- Recovered Original Text

**Recovery note (Claude, 2026-09-30), not part of the original specification:**
This text was recovered directly from this Claude Code session's own transcript (`5232cc45-b2e4-59d6-ba23-9687d55bed17.jsonl`) -- the chat messages Radu actually sent to Claude Code at the time this spec was implemented -- not from Radu's separate GPT conversation history, and not paraphrased or reconstructed from memory. The main text was sent as one message (marked v1.1 in its own header, and initially `PROPOSED FOR CLAUDE REVIEW -- DO NOT IMPLEMENT YET`), followed roughly 16 minutes later by Radu's response to Claude's review questions, which carries the final clarifications/approval before implementation began. Each fragment below is reproduced byte-for-byte from the transcript, in the exact chronological order it was sent, with no correction, no reformatting, and no added or removed text beyond this note and the fragment-boundary markers. **This recovery has not yet been independently verified by Radu** -- he should treat this file as a candidate primary source to check, not as confirmed.

---

---

> **Original message 1/2** -- Radu, to Claude Code, session `5232cc45-b2e4-59d6-ba23-9687d55bed17`, transcript line 2762, timestamp `2026-09-25T08:53:31.829Z` (UTC).

---

Înainte de textul formal, fac o corecție importantă față de ce am spus în mesajul anterior: nu trebuie să trecem obligatoriu la 4H ca să avem tranzacții aproape zilnice și exit în 1–5 zile. Pe un univers mare de acțiuni SUA, un sistem Daily poate genera oportunități în fiecare zi, iar holding-ul poate fi 1, 2, 3 sau 5 zile.
Asta ne permite să obținem exact avantajul pe care îl urmărești — feedback live mai rapid — fără să introducem acum toate problemele suplimentare ale datelor intraday. În același timp, proiectăm #003 în bars, nu în „zile”, astfel încât 4H să poată fi adăugat ulterior fără redesign.
Așadar direcția oficială devine:
Trading style target: fast swing, aproximativ 1–5 zile.
V1 research/data implementation: Daily.
4H: extensie planificată și compatibilă arhitectural, activată dacă Daily nu produce suficientă densitate sau dacă demonstrarea incremental value justifică intraday.
1H: ulterior, în special pentru timing/execuție.
Aceasta mi se pare varianta mai sigură și mai economică.
IMPLEMENTATION SPECIFICATION #003 v1.1
Outcome-Aware Evaluation Engine — Fast-Swing / Bar-Based
Version: 1.1
Status: `PROPOSED FOR CLAUDE REVIEW — DO NOT IMPLEMENT YET`
Baseline: accepted code through commit `aa56bb5`
Market V1: US Equities
Current implemented timeframe: `1D`
Target trading style: Fast Swing
Target holding domain: aproximativ `1–5 trading days`, cu tails până la ~10 zile
Future timeframe: `4H`, fără redesign al Evaluation Engine
Implementation owner: Claude Code
Architecture/review: GPT
Final approval: Radu
1. Obiectivul #003
Spec #003 construiește primul modul:
OUTCOME-AWARE
Discovery spune:
„Această stare este neobișnuită/interesantă statistic.”
Evaluation trebuie să răspundă:
„Ce s-a întâmplat ulterior în trecut după această stare?”
Pipeline:

```
PIT-safe historical data
        +
Historical Discovery observations
        ↓
Outcome Engine
        ↓
Episode Engine
        ↓
Statistical Evaluation
        ↓
Evidence Profile
```

#003 nu decide încă dacă tranzacționăm.
2. Schimbarea strategică față de Spec #003 v1.0
Nu mai presupunem un holding principal de:

```
3–30 trading days
```

Noul research domain este:

```
FAST SWING
≈ 1–5 trading days
```

dar vrem să observăm și decay-ul după această zonă.
Pentru Daily, Level-1 horizons:

```
horizons:
  unit: BARS
  values: [1, 2, 3, 5, 10]
```

Deci la `1D`:

```
1 bar  ≈ 1 trading day
2 bars ≈ 2 trading days
3 bars ≈ 3 trading days
5 bars ≈ 1 trading week
10 bars ≈ ~2 trading weeks
```

10 bars este diagnostic/decay horizon, nu holding target.
3. Horizons sunt definite în BARS
Evaluation Engine nu trebuie să știe că:

```
1 bar = 1 zi
```

Contractul este:

```
timeframe
+
horizon_bars
```

Exemplu actual:

```
timeframe = 1D
horizon_bars = 3
```

În viitor:

```
timeframe = 4H
horizon_bars = 6
```

Același engine.
Nu se rescrie Evaluation.
4. Timeframe architecture
Output-urile #003 trebuie să conțină întotdeauna:

```
timeframe
horizon_bars
```

Nu folosi naming hardcoded:

```
forward_return_5d
```

ca structură internă.
Prefer:

```
ForwardOutcome(
    timeframe="1D",
    horizon_bars=5
)
```

Documentele/UI pot afișa:

```
~5 trading days
```

dar modelul intern rămâne bar-based.
5. De ce păstrăm Daily acum
Aceasta este o decizie de implementare, nu afirmația că Daily este superior 4H.
Avem deja:

* PIT Daily;
* features Daily;
* Discovery Daily;
* teste Daily;
* corporate actions Daily;
* benchmark alignment Daily.

4H ar necesita suplimentar:

* timestamp-level PIT;
* timezone/session policy;
* regular vs extended hours;
* canonical bar construction;
* missing intraday bars;
* intraday volume seasonality;
* benchmark bar alignment;
* feature-window recalibration.

Nu le introducem pe ascuns în #003.
6. Intraday readiness gate
#003 trebuie proiectat pentru 4H, dar NU trebuie implementat un bypass intraday.
Dacă Claude consideră că orice parte a implementării #003 necesită schimbarea contractelor #001/#002 pentru a deveni timeframe-agnostic, trebuie să raporteze:

```
IMPLEMENTATION BLOCKER — INTRADAY CONTRACT
```

înainte de cod.
Nu se modifică Data Foundation unilateral.
7. Future 4H policy
Când activăm 4H, va exista un spec separat pentru:

```
Intraday Data + Feature Readiness
```

În acel moment trebuie rezolvate explicit:

```
session definition
bar timestamps
timezone
RTH / ETH
bar construction
intraday volume seasonality
bar-slot normalization
corporate-action boundary
benchmark synchronization
```

Evaluation #003 nu trebuie redesenat.
8. Live-validation practicality
Un obiectiv nou explicit al sistemului:
Viitoarea strategie trebuie să permită strângerea într-un timp rezonabil a suficientor observații live cu capital redus pentru validarea operațională.
Dar această cerință NU poate modifica outcome-blind Discovery.
Forbidden:

```
"pattern-ul acesta apare des,
deci îi schimbăm threshold-ul ca să avem mai multe trades"
```

pe baza rezultatelor.
9. Două lucruri diferite: edge și opportunity density
#003 trebuie să mențină separat:
Statistical evidence
Ce outcomes urmează după signature.
Opportunity density
Cât de frecvent apare signature.
Exemple:

```
episodes_per_20_sessions
episodes_per_60_sessions
median_gap_between_episodes
```

Acestea sunt descriptive.
Nu reprezintă Alpha Score.
10. Discovery rămâne outcome-blind
Spec #002 nu trebuie să vadă niciodată:

* forward returns;
* win rate;
* expectancy;
* effect size;
* p-values;
* Evaluation results.

Dependency:

```
Discovery
    ↓
observations
    ↓
Evaluation
```

Nu:

```
Evaluation
    ↓
Discovery
```

11. Evaluation este outcome-aware
Evaluation poate utiliza:

```
future price
forward return
benchmark future return
positive rate
distribution
effect size
confidence intervals
statistical tests
```

Aceasta este zona autorizată pentru outcomes.
12. Locked OOS
Full history:

```
FULL DATA
│
├── DEVELOPMENT
│
└── LOCKED OOS
```

Spec #003 operează exclusiv în:
DEVELOPMENT
Locked OOS nu poate fi folosit pentru:

* debugging;
* threshold choice;
* feature choice;
* signature choice;
* screenshots;
* sanity checks;
* „doar să vedem”.

13. Real calendar boundaries sunt încă OPEN
Nu hardcodăm acum:

```
2012–2022 Development
2023–2026 OOS
```

până nu avem provider research-grade.
Config:

```
research_period:
  development_start: null
  development_end: null
  locked_oos_start: null
  locked_oos_end: null
```

Testele folosesc date sintetice.
14. Outcome cannot cross development boundary
Exemplu:

```
development_end = 2025-12-31
observation = 2025-12-29
horizon = 5 bars
```

dacă outcome necesită o bară din OOS:

```
CROSSES_LOCKED_OOS
```

Nu calculăm outcome.
15. Primary outcome
Pentru fiecare security `i`, observation bar `t` și horizon `h`:
\[ R_{i,t,h} = \frac{P_{i,t+h}}{P_{i,t}}-1 \]
`P` = `split_adjusted_close`.
Baseline obligatoriu:

```
aa56bb5
```

care include și corporate-action-consistent volume.
16. Total return
`total_return_adjusted_close`
rămâne:

```
EXPERIMENTAL_NOT_APPROVED_FOR_RESEARCH
```

Nu îl folosește #003.
17. Research return ≠ executable trade P&L
Outcome:

```
close(t) → close(t+h)
```

este research measurement.
Nu înseamnă că sistemul ar fi putut:

```
receive signal at close
+
execute at exactly same close
```

Backtester-ul ulterior va introduce executable entry.
18. Benchmark-relative outcome
Pentru fiecare bar horizon:
\[ AR_{i,t,h} = R_{i,t,h} - R_{benchmark,t,h} \]
Raportăm:

```
forward_return
benchmark_return
relative_return
```

Benchmark configurabil.
Default future research config:

```
SPY
```

În teste folosim synthetic benchmark.
19. Benchmark alignment
Benchmark trebuie aliniat după:

```
actual observation timestamp/date
actual exit timestamp/date
```

Nu după poziția numerică în DataFrame.
Dacă benchmark-ul nu are bar valid:

```
MISSING_BENCHMARK
```

20. ForwardOutcome entity
Minimum:

```
ForwardOutcome

security_id
observation_as_of
timeframe
horizon_bars

entry_reference_price
exit_reference_price
exit_as_of

forward_return
benchmark_return
relative_return

outcome_status

development_end

outcome_engine_version
config_version
```

21. Outcome statuses
Minimum:

```
VALID
INSUFFICIENT_FUTURE_DATA
CROSSES_LOCKED_OOS
MISSING_BENCHMARK
INVALID_INPUT
```

Nu silently drop.
22. Evaluation dataset
Unitatea raw:

```
security_id
×
observation_as_of
×
evaluation_signature
```

Dar raw observations NU sunt automat statistical samples independente.
23. Candidate Budget NU definește Evaluation dataset
Critical.
`max_candidates = 20`
din #002 există pentru:

```
LLM/downstream compute budget
```

Nu pentru statistica istorică.
#003 trebuie să evalueze:
pre-budget eligible Discovery observations.
Dacă actual API #002 expune numai candidații post-budget:

```
IMPLEMENTATION BLOCKER
```

Claude nu are voie să folosească doar top 20.
24. Pre-budget observation interface
Prefer o structură conceptuală:

```
DiscoveryObservation
```

care conține:

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
descriptive_metrics
reason_codes

eligibility_status
config_version
engine_version
```

Candidate Selector trebuie să fie downstream de acest layer.
Dacă acesta nu există formal în #002, Claude trebuie să propună cea mai mică schimbare posibilă înainte de implementare.
25. EvaluationSignature
Exemple:

```
VOLATILITY_COMPRESSION
```

sau:

```
TREND_HIGH + RS_VERY_HIGH
```

sau:

```
VOLUME_VERY_HIGH +
MOMENTUM_ACCELERATION
```

Signature utilizează numai date existente în #002.
Nu creează noi indicators outcome-aware.
26. Signature Set trebuie înghețat
Formal run:

```
signature_set_id
```

cu lista exactă de signatures testate.
Nu permitem:

```
test 1000
pick 10 winners
pretend only 10 were tested
```

Toate fac parte din multiple-testing universe.
27. Signature provenance
Minimum:

```
signature_id
definition
source_fields
timeframe
discovery_engine_version
discovery_config_version

creation_mode
created_before_outcome_evaluation
```

`creation_mode`:

```
PRE_REGISTERED
EXPLORATORY_POST_HOC
```

28. Evaluation modes
Două:
EXPLORATORY
Permite investigație flexibilă.
Output explicit:

```
EXPLORATORY
```

FORMAL_DEVELOPMENT
Signature set înghețat înainte de outcomes.
Multiple testing obligatoriu.
Output:

```
FORMAL_DEVELOPMENT
```

Niciunul nu vede Locked OOS.
29. Consecutive observations și pseudo-sample-size
Exemplu:

```
AAPL

Monday    compression
Tuesday   compression
Wednesday compression
Thursday  compression
```

Nu putem pretinde:

```
N = 4 independent experiments
```

Mai ales pentru horizon 5–10 bars.
30. Episode Engine
Default:

```
episode:
  max_gap_bars: 1
  representative: FIRST
```

Pentru același:

```
security
+
evaluation_signature
```

observațiile consecutive formează un episod.
31. Două views obligatorii
Raportăm:

```
RAW_OBSERVATIONS
```

și:

```
EPISODE_DEDUPLICATED
```

Default statistical view:
`EPISODE_DEDUPLICATED`
32. Important: overlapping forward windows rămân posibile
Episode deduplication rezolvă o parte din dependență.
Dar două episoade separate pot avea forward windows suprapuse.
Exemplu:

```
episode A → horizon 10
episode B 5 bars later → horizon 10
```

Nu presupunem independență perfectă.
De aceea #003 nu trebuie să utilizeze t-test naiv ca metodă implicită.
33. Baseline
Minimum V1:
Unconditional eligible-universe baseline
Pentru același:

```
timeframe
horizon
Development period
```

și aceleași reguli de validitate.
Plus:
Benchmark-relative distribution
prin `relative_return`.
34. Baseline nu trebuie să vină din Candidate Budget
Baseline provine din eligible observation universe.
Nu:

```
top 20 candidates
```

35. Metrics per signature × horizon
Minimum:

```
raw_observation_count
episode_count

mean
median
std

q10
q25
q75
q90

positive_rate
```

Pentru absolute.
Și:

```
mean_relative
median_relative
std_relative
relative_positive_rate
```

36. Missingness report
Per signature/horizon:

```
eligible_observations
raw_observations
episodes

valid_outcomes

insufficient_future_data
crosses_locked_oos
missing_benchmark
invalid_input
```

Counts trebuie să se reconcilieze.
37. Opportunity-density metrics
Pentru live practicality:

```
episode_count
episodes_per_20_sessions
episodes_per_60_sessions
median_sessions_between_episodes
```

Acestea NU intră în significance calculation.
38. Effect size
Trebuie raportat minimum:

```
mean_difference_vs_baseline
median_difference_vs_baseline
standardized_effect_size
```

Formula standardized effect size trebuie fixată înainte de real-data evaluation.
Claude trebuie să răspundă înainte de cod dacă vede mai multe variante rezonabile.
39. Confidence intervals
V1:
bootstrap CI
pentru:

```
mean forward return
mean relative return
difference vs baseline
```

Bootstrap sampling unit trebuie să respecte episode structure.
Nu resampling naiv al raw rows.
40. Statistical comparison
Nu hardcodez în Spec un t-test.
Vreau ca Claude să propună concret înainte de implementation:

* permutation test?
* clustered/bootstrap comparison?
* altă metodă?

Condiții:

* non-normal returns;
* dependence within securities;
* temporal overlap;
* repeated observations.

Aceasta este o întrebare de arhitectură statistică.
41. Security concentration
Evidence Profile trebuie să includă minimum:

```
unique_security_count
largest_security_share_of_episodes
```

Exemplu problematic:

```
N episodes = 80
dar 52 provin din aceeași acțiune
```

Asta trebuie să fie vizibil.
42. Temporal concentration
Raportăm și distribuția episoadelor pe timp.
Un „edge” nu trebuie să pară robust dacă toate observations provin dintr-un singur an/regim.
43. Stability bins
Config:

```
stability:
  temporal_bins: 3
```

Pe Development:

```
early
middle
late
```

Per bin:

```
episode_n
unique_securities
mean
median
mean_relative
positive_rate
```

Nu producem „stability score”.
44. Multiple testing
Mandatory pentru:

```
FORMAL_DEVELOPMENT
```

Output:

```
raw_p_value
adjusted_p_value
family_id
family_test_count
multiple_testing_method
```

Default:
Benjamini–Hochberg FDR
45. Multiple-testing family
Default proposal:
O familie:

```
same timeframe
+
same horizon_bars
+
same outcome_type
+
same formal evaluation run
```

Exemplu:

```
1D
5 bars
relative_return
run_0042
```

Toate signatures testate aici formează aceeași familie.
46. Minimum statistical support
Level-1 TEST_CONFIG:

```
minimum_episode_count: 30
minimum_unique_securities: 10
```

Dacă nu:

```
INSUFFICIENT_SUPPORT
```

30/10 sunt engineering defaults.
Nu sunt thresholds validate.
47. Important pentru frecvența mare
Nu reducem `minimum_episode_count` pentru că vrem rezultate mai repede.
Mai multe oportunități trebuie să vină din:

```
large universe
+
shorter holding horizon
+
real signal density
```

nu din slăbirea standardelor statistice.
48. Directionality
Nu transformăm automat:

```
mean forward return = -3%
```

în:

```
great short strategy
```

Short hypothesis trebuie creată ulterior explicit.
Previne:

```
flip sign until profitable
```

49. No Alpha/Evaluation Score
Forbidden:

```
EvaluationScore =
effect_size +
pvalue +
frequency +
stability
```

Nu agregăm într-un scor unic.
Output:
Evidence Profile
50. EvidenceProfile
Conceptual:

```
EvidenceProfile

signature_id
timeframe
horizon_bars
evaluation_mode

support:
    raw_n
    episode_n
    unique_security_count
    support_status

opportunity_density:
    episodes_per_20_sessions
    episodes_per_60_sessions
    median_gap

absolute_outcome:
    mean
    median
    std
    q10
    q25
    q75
    q90
    positive_rate
    confidence_interval

relative_outcome:
    mean
    median
    std
    positive_rate
    confidence_interval

baseline_comparison:
    mean_difference
    median_difference
    standardized_effect
    raw_p
    adjusted_p
    family_id

concentration:
    largest_security_share

stability:
    temporal_bins[...]

missingness:
    ...

warnings[]
```

51. No automatic verdict
#003 nu produce:

```
GOOD
BAD
TRADE
NO_TRADE
EDGE_CONFIRMED
WINNER
```

Poate spune factual:

```
SUFFICIENT_SUPPORT
INSUFFICIENT_SUPPORT
```

52. Holding-horizon decay profile
Pentru target-ul nostru Fast Swing, acesta devine un output important.
Pentru fiecare signature:

```
1 bar
2 bars
3 bars
5 bars
10 bars
```

raportăm aceeași familie de outcomes.
Astfel putem vedea:

```
efect apare imediat?
crește după 2–3 zile?
dispare după 5 zile?
inversează ulterior?
```

Fără să alegem încă exit-ul optim.
53. Nu alegem horizon-ul câștigător în #003
Foarte important.
Dacă:

```
1D +0.2%
2D +0.8%
3D +1.4%
5D +1.1%
10D -0.1%
```

#003 raportează curba.
Nu spune:

```
EXIT = 3 days
```

Asta ar deveni hypothesis/backtesting work și trebuie să țină cont de multiple selection.
54. Path-dependent outcomes
MAE/MFE:

```
OUT OF SCOPE #003 V1.1
```

Vor fi foarte utile pentru Exit Strategy.
Dar dacă le introducem acum, multiplicăm masiv outcome mining.
Le adăugăm controlat ulterior.
55. Transaction costs
OUT OF SCOPE #003.
Evaluation măsoară fenomenul.
Backtesting măsoară strategia executabilă.
Pe holding 1–5 zile, costurile vor fi mai importante decât în versiunea veche 3–30 zile, deci Backtester-ul ulterior va trebui să le trateze serios.
56. Slippage/spread
OUT OF SCOPE #003, dar:
MUST HAVE în Backtesting.
Mai ales dacă ulterior coborâm la 4H/1H.
57. Real-data missing future bars
Dacă security dispare înainte de horizon:

```
INSUFFICIENT_FUTURE_DATA
```

Nu:

```
return = 0
```

Nu forward fill.
Nu silent drop.
58. Delistings
Level-1 nu inventează economic delisting return.
Când avem research-grade survivorship-free data, trebuie introdusă politica corectă.
Până atunci missingness rămâne vizibil.
59. Evaluation Registry
Minimum metadata:

```
evaluation_run_id
created_at

mode

development_start
development_end

timeframe
horizons

benchmark

discovery_engine_version
discovery_config_version

evaluation_engine_version
evaluation_config_version

signature_set_id

bootstrap_seed
bootstrap_iterations

multiple_testing_method
```

60. Reproducibility
Aceeași:

```
data
+
config
+
signature set
+
seed
+
versions
```

trebuie să producă output identic.
61. Runtime
Evaluation V1:
Python only

```
LLM tokens = 0
```

Nu OpenAI/Claude calls în runtime.
62. Performance
Evitați:

```
1 query × observation × horizon
```

Prefer:

```
one PIT history fetch/security
+
local/vectorized horizon computations
```

Benchmark reuse.
63. Suggested config

```
evaluation_mode: FORMAL_DEVELOPMENT

timeframe: 1D

horizons:
  unit: BARS
  values: [1, 2, 3, 5, 10]

support:
  minimum_episode_count: 30
  minimum_unique_securities: 10

episode:
  max_gap_bars: 1
  representative: FIRST

bootstrap:
  iterations: 2000
  seed: 42

multiple_testing:
  method: BENJAMINI_HOCHBERG
  family:
    - timeframe
    - horizon_bars
    - outcome_type
    - evaluation_run

stability:
  temporal_bins: 3

benchmark: TEST_CONFIG
```

`2000` este TEST_CONFIG, nu parametru validat.
64. Future 4H example
Același config ar putea deveni:

```
timeframe: 4H

horizons:
  unit: BARS
  values: [1, 2, 4, 6, 10, 20]
```

Evaluation Engine nu se schimbă.
Doar Data/Discovery trebuie să poată produce 4H corect.
65. Daily context în viitorul 4H
Când folosim 4H, Daily poate deveni:

```
context/regime timeframe
```

Exemplu:

```
4H compression
+
Daily trend HIGH
```

Dar aceasta este o nouă EvaluationSignature.
Trebuie pre-registrată și intră în multiple testing.
Nu se adaugă gratuit după ce vedem outcomes.
66. Required Tests
Minimum:
TEST 1 — Forward return arithmetic
1/2/3/5/10 bars manual.
TEST 2 — Bar-horizon semantics
Engine folosește bars, nu calendar days.
TEST 3 — Configurable timeframe metadata
Nicio structură outcome nu este hardcoded `DAYS`.
TEST 4 — Benchmark relative return
TEST 5 — Benchmark actual-date alignment
TEST 6 — Development boundary
TEST 7 — OOS mutation invariance
TEST 8 — Missing future data
TEST 9 — Episode deduplication
TEST 10 — Episode separation
TEST 11 — Raw vs episode counts
TEST 12 — Baseline distribution
TEST 13 — Absolute descriptive metrics
TEST 14 — Relative descriptive metrics
TEST 15 — Minimum episode support
TEST 16 — Minimum unique-security support
TEST 17 — Security concentration
TEST 18 — Bootstrap determinism
TEST 19 — Episode-aware bootstrap
TEST 20 — Statistical comparison
TEST 21 — BH-FDR hand calculation
TEST 22 — Multiple-testing family isolation
TEST 23 — Stability temporal bins
TEST 24 — Opportunity-density arithmetic
TEST 25 — No Evaluation/Alpha Score
TEST 26 — Discovery cannot import Evaluation
TEST 27 — Locked OOS protection
TEST 28 — Signature set completeness
TEST 29 — Post-hoc labeling
TEST 30 — Total-return prohibition
TEST 31 — Reproducibility metadata
TEST 32 — Missingness reconciliation
TEST 33 — Candidate Budget isolation
Must demonstrate:

```
changing max_candidates
```

does NOT alter Evaluation evidence generated from pre-budget observations.
TEST 34 — Holding-decay curve
Known synthetic outcomes at different bars → correct horizon profile.
TEST 35 — Zero LLM imports/runtime
67. Controlled examples
Minimum 4 examples.
Example A — fast effect
Synthetic signature:

```
strong effect at 1–3 bars
decays by 5–10 bars
```

Demonstrates Fast-Swing use case.
Example B — delayed effect
Weak at 1 bar, stronger at 3–5 bars.
Example C — pure noise
No true difference.
Example D — multiple-testing trap
Many random signatures create attractive raw p-values.
BH-FDR shows why they cannot be interpreted naively.
68. Performance report
Must report:

```
securities
bars
raw observations
episodes
signatures
horizon evaluations
statistical tests
runtime
```

No token usage except:

```
0 LLM runtime tokens
```

69. Package structure
Suggested:

```
src/evaluation/

  models/
    entities.py

  outcomes/
    forward_returns.py
    benchmark.py

  observations/
    signatures.py
    episodes.py

  baseline/
    universe.py

  statistics/
    descriptive.py
    bootstrap.py
    comparison.py
    multiple_testing.py
    stability.py
    concentration.py

  config/
    loader.py
    evaluation.yaml

  registry/
    runs.py
    signatures.py

  engine.py
```

Claude poate schimba low-level structure.
70. Deliverables
Minimum:

```
docs/spec003_architecture.md
docs/spec003_test_report.md
docs/spec003_known_limitations.md
docs/spec003_examples.md
docs/spec003_multiple_testing_report.md
docs/spec003_reproducibility.md
docs/spec003_performance_report.md
```

71. Hard FAIL conditions
Spec #003 este respins dacă:

* Locked OOS este accesat;
* outcome data ajunge în Discovery;
* Candidate Budget definește dataset-ul statistic;
* horizon crossing OOS este calculat;
* missing outcomes sunt dropped silent;
* statistical unit = raw consecutive observations fără episode handling;
* `p < .05` este tratat drept evidence fără multiple-testing context;
* signature set formal poate fi schimbat după outcomes;
* Alpha/Evaluation Score este produs;
* total-return experimental este folosit;
* implementation este hardcoded exclusiv pe „days”;
* LLM este folosit în runtime.

72. OUT OF SCOPE
Nu implementăm acum:

* executable trade entries;
* next-bar fills;
* exit strategy;
* stop loss;
* trailing stop;
* take profit;
* MAE/MFE;
* transaction costs;
* slippage;
* spread;
* sizing;
* portfolio;
* walk-forward;
* Locked OOS evaluation;
* 4H data ingestion;
* 1H;
* crypto;
* options;
* broker APIs;
* live trading.

73. Important: ce înseamnă succesul #003
Nu:
„Am găsit strategia profitabilă.”
Ci:
„Avem un motor statistic care poate măsura fără leakage și fără data-mining evident ce s-a întâmplat după stările Discovery și cât de repede efectul apare/dispare.”
Acest lucru este mult mai valoros pentru etapa următoare.
74. Întrebări obligatorii pentru Claude înainte de COD
Claude trebuie să răspundă explicit la următoarele.
A. Pre-budget observations
Poate #002 actual la `aa56bb5` furniza în mod curat toate eligible Discovery observations înainte de Candidate Selector, sau este necesară o mică extensie de API?
Dacă necesită schimbarea #002:

```
IMPLEMENTATION BLOCKER
```

și propune contractul minim.
B. Statistical comparison
Ce metodă propune concret pentru:

```
signature vs unconditional baseline
```

având:

* returns non-normal;
* repeated securities;
* overlapping horizons;
* episode dependence?

Să explice unitatea de resampling/test.
Nu începe codul înainte să aprobăm.
C. Baseline construction
Cum evită ca:

* securities cu istoric lung;
* securities foarte active;
* anumite perioade

să domine baseline-ul?
Propune dacă baseline-ul trebuie construit:

```
security × time
```

sau prin alt sampling/weighting.
D. Bootstrap
Este suficient:

```
episode-level bootstrap
```

sau recomandă:

```
security-clustered
time-block
two-way
```

pentru Level 1?
Vreau argumentul, nu doar alegerea.
E. Intraday readiness
Confirmă că actuala implementare #003 poate fi făcută:

```
bar-based / timeframe-agnostic
```

fără implementarea acum a 4H.
Dacă vede un hardcoded Daily dependency care ar necesita redesign ulterior, să îl declare acum.
75. Instrucțiunea finală pentru Claude Code
Poți copia integral Spec-ul de mai sus și să adaugi exact:
Review Implementation Specification #003 v1.1 completely before writing any code.
Baseline: `aa56bb5`.
DO NOT IMPLEMENT YET.
First confirm your understanding of:

1. Fast-Swing target ≈ 1–5 trading days;
2. current Level-1 implementation uses Daily data;
3. Evaluation architecture must be BAR-based and timeframe-agnostic so 4H can be added later without redesign;
4. Development / Locked-OOS hard isolation;
5. Evaluation is outcome-aware, Discovery remains permanently outcome-blind;
6. Evaluation must consume PRE-BUDGET eligible observations, never just Candidate Budget output;
7. episode deduplication and statistical dependence;
8. benchmark-relative outcomes;
9. minimum support and concentration diagnostics;
10. multiple-testing correction and frozen Signature Set;
11. opportunity density is descriptive and separate from edge.

Then answer questions §74A–E.
If any answer requires modifying the accepted #001/#002 contracts, label it:
`IMPLEMENTATION BLOCKER`
and describe the smallest proposed change.
Do not write code until GPT/Radu explicitly approve those decisions.
Do not implement Spec #004.
Do not implement 4H ingestion inside #003.
Pentru tine, Radu
Această versiune ne păstrează opțiunile deschise.
Putem ajunge la un sistem în care, de exemplu, avem câteva intrări pe săptămână sau chiar aproape zilnic, cu poziții care ies în 1–5 zile, fără să plătim acum costul tehnic al intraday.
Iar dacă după date reale constatăm că Daily produce prea puține oportunități sau 4H aduce valoare incrementală clară, coborâm la 4H fără să reconstruim Evaluation Engine. Asta este exact motivul pentru care am schimbat #003 de la `trading days` la bars.

> *(Claude's review/clarifying questions in response are not reproduced here -- only Radu's own messages. Radu's reply follows.)*

---

> **Original message 2/2** -- Radu, to Claude Code, session `5232cc45-b2e4-59d6-ba23-9687d55bed17`, transcript line 2810, timestamp `2026-09-25T09:09:29.353Z` (UTC).

---

Am verificat critic propunerile lui Claude. A este corect ca blocker și trebuie rezolvat înainte de #003. B/C/D sunt în direcția bună, dar nu le-aș aproba exact în forma propusă — există două riscuri statistice importante pe care merită să le corectăm acum.
Decizie §74A — APPROVED, dar cu tip distinct
Confirm extensia minimă în #002, însă aș evita reutilizarea numelui `DiscoveryCandidate` pentru output-ul pre-budget.
Vreau:

```
compute_discovery_observations(...)
    -> list[DiscoveryObservation]
```

și apoi:

```
run_discovery(...)
    -> compute_discovery_observations(...)
    -> convert/assemble candidates if needed
    -> select_candidates(...)
```

Motivul nu este estetic. Avem acum o separare conceptuală importantă:

```
DiscoveryObservation
        ↓
Candidate Selector
        ↓
DiscoveryCandidate
```

Dacă folosim `DiscoveryCandidate` înainte de selector, peste câteva luni devine foarte ușor să confundăm dataset-ul statistic cu lista de candidați operaționali.
`DiscoveryObservation` poate avea practic aceleași câmpuri. Nu vreau duplicare inutilă de logică; Claude poate factoriza structura internă elegant. Dar contractele publice trebuie să exprime diferența semantică.
Hard requirement:
schimbarea `max_candidates` nu trebuie să modifice niciodată output-ul `compute_discovery_observations()`.
TEST 33 din #003 trebuie să protejeze exact acest lucru.
Deci:
IMPLEMENTATION BLOCKER A → APPROVED cu `DiscoveryObservation` distinct.
§74B/D — nu aprob încă bootstrap doar pe security
Aici am o obiecție importantă.
Claude identifică corect problema:
observațiile din aceeași acțiune nu sunt independente.
Dar pe bursă există și dependența opusă:
acțiuni diferite în aceeași perioadă nu sunt independente între ele.
Exemplu:
Într-o săptămână în care Nasdaq sare +8%, putem avea:

```
NVDA episode
AMD episode
AVGO episode
CRDO episode
MRVL episode
...
```

Un bootstrap doar pe `security_id` poate trata aceste rezultate drept mult mai independente decât sunt în realitate, deși toate au fost expuse aceluiași șoc de piață.
Pentru sistemul nostru, acesta nu este un caz exotic. Trend / Momentum / RS / Volatility pot activa multe companii simultan tocmai în același regim de piață.
De aceea nu vreau să amân complet problema temporală.
Soluția V1 pe care o aprob
Aș folosi două niveluri:
Primary inference: time-block clustered bootstrap
Unitatea de resampling = blocuri temporale care păstrează toate securities/episodes din acea perioadă împreună.
Asta conservă:

* market-wide correlation;
* sector-wide shocks;
* clustering temporal;
* o parte din overlap-ul forward horizons.

Iar separat păstrăm diagnosticul deja cerut:

```
unique_security_count
largest_security_share_of_episodes
```

pentru concentrarea pe security.
Nu este nevoie încă de un sofisticat two-way bootstrap academic.
V1 poate folosi:

```
bootstrap:
    clustering: TIME_BLOCK
    block_length_bars: ...
```

Lungimea exactă trebuie să fie configurabilă.
Pentru Level 1 synthetic tests putem utiliza o valoare mică și verificabilă.
Pentru date reale nu optimizăm block length după rezultate.
De ce nu doar episode bootstrap
Respins ca metodă principală.
De ce nu doar security bootstrap
Mai bun decât episode bootstrap, dar ignoră common market shocks.
De ce nu two-way bootstrap complet acum
Probabil prea multă complexitate pentru #003 V1.
Decizia:
TIME-BLOCK bootstrap ca inferență principală + security concentration diagnostics.
Putem păstra ulterior `SECURITY_CLUSTER` ca metodă diagnostică secundară, dar nu vreau ca ea să fie singura bază pentru CI/p-values.
Un alt punct: „p-value derivat din CI”
Aici vreau o corecție.
Claude spune:
„p-value derivat din CI (proporția de replicate care traversează 0)”
Nu vreau această formulare/implementare.
CI și p-value sunt înrudite, dar nu sunt același obiect și „CI traversează zero” nu produce pur și simplu un p-value valid.
Mai curat:
bootstrap distribution pentru statistică:
\[ D = mean_{signature} - mean_{baseline} \]
iar two-sided bootstrap probability poate fi calculată explicit din distribuția bootstrap în jurul ipotezei nule, cu metoda exactă documentată.
Sau poate utiliza un permutation/randomization test separat pentru p-value.
Aici prefer claritate în locul economisirii a 50 de linii de cod.
Propunere finală:

* bootstrap → Confidence Intervals;
* permutation test → raw p-value;
* BH-FDR → adjusted p-value.

Este conceptual mult mai curat.
§74C — baseline security × temporal_bin: aproape, dar trebuie schimbat
Claude încearcă să evite două distorsiuni reale:

* o acțiune cu istoric lung să domine;
* perioade cu univers foarte mare să domine.

Corect.
Dar un baseline egal ponderat pe toate:

```
security × temporal_bin
```

poate produce o altă problemă.
Să presupunem că signature-ul nostru apare aproape exclusiv în 2024–2025, perioadă bullish.
Dacă îl comparăm cu un baseline care dă greutate egală:

```
2012–2016
2017–2021
2022–2025
```

o parte din „edge” poate fi pur și simplu diferența de regim temporal.
Nu vreau încă matched controls sofisticate, dar baseline-ul trebuie să respecte compoziția temporală a signature-ului.
Baseline V1 aprobat
Pentru fiecare signature, baseline-ul să fie construit din eligible universe folosind aceeași distribuție temporală ca episoadele signature-ului.
Conceptual:

```
signature episode in temporal stratum T
        ↓
compare against eligible-universe observations in same T
```

Apoi agregăm strata.
Astfel nu comparăm un pattern dintr-o piață bullish cu media brută a 15 ani de piață.
Putem numi aceasta:
`TEMPORALLY_STRATIFIED_ELIGIBLE_BASELINE`
Nu este încă matched-control după:

* sector;
* volatility;
* market cap;
* beta.

Acelea rămân pentru versiuni ulterioare.
Dar baseline-ul nu trebuie să conțină observația însăși?
Ideal, pentru fiecare signature observation, exclude security/date observation corespunzătoare din control pool dacă este prezentă.
Nu este un blocker statistic major într-un univers de mii de companii, dar e curat și simplu:

```
control != same security_id + observation_as_of
```

Standardized effect size
Claude nu a răspuns încă explicit cu formula, iar Spec-ul cerea asta.
Pentru returns nu aș folosi automat Cohen's d clasic din cauza tails/outliers.
Pentru V1 propun:
\[ RobustEffect = \frac{Median_{signature} - Median_{baseline}} {IQR_{baseline}/1.349} \]
unde denominator-ul aproximează o scară robustă.
Raportăm oricum separat:

```
mean_difference
median_difference
robust_standardized_effect
```

Nu îl transformăm într-un score.
Dacă Claude vede o problemă cu această formulă, poate argumenta înainte de cod.
§74E — APPROVED
Aici sunt de acord.
#003 poate fi complet:

```
bar-based
timeframe-aware
```

chiar dacă #001/#002 produc acum numai Daily.
Și observația privind:

```
TIMEFRAME = "1D"
```

din Discovery este corectă.
O documentăm ca:
future intraday activation gate, nu blocker pentru #003 Daily.
Nu o reparăm acum.
Decizia finală pentru Claude înainte de implementare
Poți să-i trimiți următoarea decizie:
§74A APPROVED WITH MODIFICATION
Add a public pre-budget API:
`compute_discovery_observations(...) -> list[DiscoveryObservation]`
Do not reuse the semantic name `DiscoveryCandidate` for the pre-budget layer. `run_discovery()` must retain identical external behavior and remain the post-budget candidate API.
Add regression protection proving Candidate Budget changes cannot affect pre-budget observations.
§74B/D MODIFIED
Do not use episode-only or security-only bootstrap as the primary inference method.
V1 primary CI mechanism shall use time-block clustered bootstrap, keeping securities/episodes occurring in the same sampled temporal blocks together, to preserve common market/regime dependence.
Security concentration remains separately reported via `unique_security_count` and `largest_security_share_of_episodes`.
Block size must be configurable and not optimized against outcomes.
Bootstrap produces confidence intervals.
For raw significance testing, use a separately documented permutation/randomization test, rather than deriving a p-value informally from whether a bootstrap CI crosses zero.
BH-FDR remains the formal multiple-testing correction.
§74C MODIFIED
Baseline shall be a `TEMPORALLY_STRATIFIED_ELIGIBLE_BASELINE`: control observations come from the eligible universe in the same temporal strata represented by the signature episodes, and strata are aggregated using the signature's temporal composition.
Avoid raw-row weighting that lets long-history securities or high-universe periods dominate.
Exclude the identical `security_id × observation_as_of` observation from its own control pool where applicable.
Sector/volatility/beta/market-cap matched controls remain out of scope.
Standardized effect
Unless Claude identifies a statistical objection before implementation, use a robust standardized effect:
`median_difference / (baseline_IQR / 1.349)`
while continuing to report unstandardized mean and median differences separately.
§74E APPROVED
#003 must remain bar-based/timeframe-aware. Existing `Discovery.TIMEFRAME="1D"` is documented as a future intraday activation issue, not fixed inside #003.
After making the small approved #002 API patch, run the full existing suite before beginning #003 implementation.
If that patch changes existing `run_discovery()` behavior or output ordering, STOP and report `IMPLEMENTATION BLOCKER`.
Otherwise proceed with #003 v1.1.
Cu aceste modificări, Claude are aprobarea mea să facă patch-ul minim #002 și apoi să înceapă implementarea #003. Nu mai este necesar încă un pre-review, cu excepția cazului în care găsește un nou `IMPLEMENTATION BLOCKER`.
