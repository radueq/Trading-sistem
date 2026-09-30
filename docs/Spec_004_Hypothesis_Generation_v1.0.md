# Spec #004 -- Hypothesis Generation & Strategy Definition -- Recovered Original Text

**Recovery note (Claude, 2026-09-30), not part of the original specification:**
This text was recovered directly from this Claude Code session's own transcript (`5232cc45-b2e4-59d6-ba23-9687d55bed17.jsonl`) -- the chat messages Radu actually sent to Claude Code at the time this spec was implemented -- not from Radu's separate GPT conversation history, and not paraphrased or reconstructed from memory. The main text was sent as one message (initially `PROPOSED FOR CLAUDE REVIEW -- DO NOT IMPLEMENT YET`), followed roughly 30 minutes later by Radu's response to Claude's review questions, which carries the final approval before implementation began. Each fragment below is reproduced byte-for-byte from the transcript, in the exact chronological order it was sent, with no correction, no reformatting, and no added or removed text beyond this note and the fragment-boundary markers. **This recovery has not yet been independently verified by Radu** -- he should treat this file as a candidate primary source to check, not as confirmed.

---

---

> **Original message 1/2** -- Radu, to Claude Code, session `5232cc45-b2e4-59d6-ba23-9687d55bed17`, transcript line 4373, timestamp `2026-09-25T11:10:30.034Z` (UTC).

---

Da. Aici intrăm într-o zonă unde disciplina metodologică devine chiar mai importantă decât codul. Spec #004 nu trebuie să „găsească strategii profitabile”; trebuie să transforme evidence-ul din #003 în ipoteze explicite, limitate și înghețate înainte de backtest.
Mai jos este specificația completă pentru review la Claude. Nu implementăm până nu răspunde la întrebările de la final.
IMPLEMENTATION SPECIFICATION #004
Hypothesis Generation & Strategy Definition
Version: 1.0
Status: `PROPOSED FOR CLAUDE REVIEW — DO NOT IMPLEMENT YET`
Repository baseline: latest repo `266cc6f`
Executable baseline: Spec #003 accepted at `d889049`
Depends on: Spec #001 + #002 + #003
Market V1: US Equities
Research timeframe V1: `1D`
Trading style target: Fast Swing
Expected holding domain: aproximativ 1–5 trading days, cu 10 bars ca diagnostic tail
Future-ready: 4H without architecture redesign
Implementation: Claude Code
Architecture/review: GPT
Final approval: Radu
1. Scop
#003 ne spune:
„Pentru signature X, ce s-a întâmplat ulterior?”
#004 trebuie să transforme această informație într-o afirmație testabilă:
„Dacă apare condiția X, propunem să intrăm LONG/SHORT conform regulii Y și să ieșim conform regulii Z.”
Dar #004 NU testează dacă strategia este profitabilă.
Pipeline:

```
Discovery Signature
        +
EvidenceProfile (#003)
        +
Human / AI reasoning
        ↓
Hypothesis Proposal
        ↓
Review / Consensus
        ↓
Frozen StrategyHypothesis
        ↓
Strategy Registry
        ↓
#005 Backtesting
```

2. Boundary critică
#004 este:
OUTCOME-AWARE FOR HYPOTHESIS FORMATION
dar:
NOT A BACKTESTER
Poate vedea Evidence Profiles deja calculate în #003:

* mean/median;
* relative returns;
* decay curve;
* support;
* adjusted p-values;
* stability;
* concentration;
* opportunity density.

Dar NU poate:

* căuta direct prin raw future returns;
* executa backtests;
* modifica Discovery;
* optimiza indicators;
* optimiza stop-uri;
* căuta retrospectiv combinații până apare profit.

3. Regula fundamentală
Un rezultat din Development poate fi utilizat pentru a genera o ipoteză.
Dar atunci ipoteza devine:

```
DEVELOPMENT-DERIVED
```

și trebuie verificată ulterior pe date pe care selecția nu le-a văzut.
Nu avem voie să spunem:
„Evidence-ul din Development demonstrează strategia.”
Evidence-ul generează ipoteza.
Validarea vine ulterior.
4. Locked OOS rămâne complet inaccesibil
#004 NU vede Locked OOS.
Nu:

* pentru alegerea direction;
* pentru entry;
* pentru exit;
* pentru horizon;
* pentru „verificare rapidă”;
* pentru agent consensus.

Locked OOS rămâne sigilat.
5. #004 nu accesează direct Price History
Ideal, core-ul #004 nici măcar nu are nevoie de PIT prices.
Inputurile sunt artifacts deja produse:

```
Evaluation EvidenceProfile
Discovery Signature definition
Discovery/Evaluation versions
research constraints
```

Aceasta creează o protecție structurală importantă.
6. Ce este o Hypothesis
Exemplu:
Când o acțiune eligibilă intră într-o stare de Volatility Compression combinată cu RS ridicat, propunem o ipoteză LONG, executată la următoarea bară disponibilă, cu time-exit analizat în familia 1/2/3/5 bars.
Nu:
„Cumpără pentru că backtest-ul spune că 3 zile este optim.”
7. StrategyHypothesis entity
Minimum:

```
StrategyHypothesis

hypothesis_id
hypothesis_version

status
research_mode

parent_signature_id
signature_set_id

direction

entry_definition
entry_timing_policy

horizon_candidate_set

exit_hypothesis

evidence_provenance

hypothesis_provenance

constraints

created_at
created_by

strategy_config_version
```

8. Direction
V1 structure:

```
LONG
SHORT
```

Dar direction trebuie explicită.
Forbidden:

```
if mean_return > 0 -> LONG
else -> SHORT automatically
```

Dacă aceeași signature generează:

```
LONG hypothesis
SHORT hypothesis
```

acestea sunt două ipoteze distincte.
Ambele trebuie înregistrate în hypothesis universe.
9. Nu facem „flip until profitable”
Exemplu interzis:

```
LONG failed
↓
try SHORT
↓
SHORT works
↓
pretend SHORT was original hypothesis
```

Dacă LONG și SHORT sunt testate:

```
HYPOTHESIS_LONG
HYPOTHESIS_SHORT
```

ambele apar în registry.
10. Direction provenance
Minimum:

```
direction_basis:
    evidence_sign
    economic_or_market_rationale
    agent_proposal
    human_decision
```

Nu folosim această informație pentru scoring.
Este audit trail.
11. Entry Definition
Entry-ul trebuie derivat din fields existente în #002.
Exemplu:

```
volatility = COMPRESSION
AND
relative_strength = VERY_HIGH
```

Permis.
Exemplu:

```
RSI_7 > 63.4
```

dacă RSI_7 nu există în #002:
NOT ALLOWED
Trebuie Feature Spec separat.
12. Entry clause budget
Pentru a evita combinatorial explosion:
Level-1 TEST_CONFIG:

```
hypothesis_complexity:
    max_entry_conditions: 3
    max_optional_confirmation_conditions: 1
```

Nu sunt reguli validate de trading.
Sunt guardrails de research.
13. Entry Conditions trebuie să fie auditable
Nu:

```
strong momentum
```

Ci:

```
lane=momentum
label=VERY_HIGH
```

sau:

```
reason_code=MOMENTUM_ACCELERATION
```

14. Entry timing
#003 a măsurat:

```
close(t) → close(t+h)
```

dar aceasta nu este o execuție posibilă garantată.
#004 trebuie să definească:

```
signal_time = CLOSE(t)
```

și politica executabilă propusă:

```
NEXT_EXECUTABLE_BAR
```

V1 suggested:

```
entry_execution_policy = NEXT_BAR_OPEN
```

Dar execuția reală și slippage-ul sunt responsabilitatea #005.
15. De ce fixăm entry timing acum
Pentru că altfel backtester-ul poate încerca retrospectiv:

```
same close
next open
next close
limit order
VWAP
```

și apoi să păstreze varianta profitabilă.
Asta ar fi o nouă dimensiune de data mining.
16. Primary V1 entry execution hypothesis
Propun ca baseline:

```
Signal detected after Daily close
→ earliest executable entry = next regular-session open
```

Acest lucru trebuie confirmat înainte de cod.
17. Horizon candidates
Evidence #003 raportează:

```
1
2
3
5
10 bars
```

#004 NU alege automat:

```
max(mean_return)
```

18. HorizonCandidateSet
Exemplu:

```
horizon_candidate_set:
    unit: BARS
    values: [1, 2, 3, 5]
```

10 bars poate rămâne diagnostic tail.
19. Nu declarăm „3 bars optimal”
Dacă #003 arată:

```
1 bar   +0.4%
2 bars  +0.8%
3 bars  +1.2%
5 bars  +0.9%
10 bars +0.1%
```

putem formula:
efectul Development pare concentrat în zona 2–5 bars.
Dar nu:
exit optim = 3 zile.
Dacă testăm:

```
2
3
5
```

toate cele trei au fost considerate.
20. Horizon provenance
Hypothesis trebuie să păstreze:

```
horizon_candidates_considered
horizon_selection_basis
```

Dacă ulterior selectăm unul:

```
selected_horizon
selection_stage
```

nu poate fi rescris retroactiv.
21. Exit Strategy — principiul central
În #004 nu „optimizăm exit-ul”.
Construim:
Exit Hypotheses
care vor fi testate în #005.
22. Exit taxonomy V1
Propun trei familii conceptuale.
A. TIME EXIT
Exemple:

```
exit after 1 bar
exit after 2 bars
exit after 3 bars
exit after 5 bars
```

Este baseline-ul obligatoriu.
B. SIGNAL INVALIDATION EXIT
Exemplu:
Entry:

```
volatility = COMPRESSION
+
RS = VERY_HIGH
```

Exit candidate:

```
RS no longer HIGH/VERY_HIGH
```

sau:

```
momentum transition turns negative
```

Dar numai folosind fields deja disponibile.
C. RISK EXIT
Stop-loss / ATR / trailing stop.
Nu îl optimizăm în #004.
23. Ce NU introducem încă în Exit V1
Nu:

* MAE optimized stop;
* MFE optimized target;
* ATR multiplier grid-search;
* take-profit optimized retrospectiv;
* trailing distance optimized;
* dynamic Kelly sizing.

Acestea necesită un dedicated Risk/Exit research step.
24. De ce Time Exit este baseline obligatoriu
Este cea mai simplă legătură cu evidence-ul #003.
Dacă efectul statistic apare la:

```
1–3 bars
```

un time exit este o ipoteză naturală și auditable.
Nu introduce un indicator nou.
25. Signal Invalidation Exit
Permis doar dacă există o justificare semantică directă.
Exemplu:
Entry thesis:
trend + RS continuation.
Exit thesis:
ieși dacă RS pierde starea care susținea trade-ul.
Aceasta este diferită de:
am testat 50 exits și acesta a dat Sharpe-ul cel mai mare.
26. ExitHypothesis entity

```
ExitHypothesis

exit_family

trigger_definition

time_exit_candidates

invalidation_conditions

risk_exit_status

parameter_source

provenance
```

27. Exit parameter source
Fiecare parametru trebuie etichetat:

```
PRE_SPECIFIED
EVIDENCE_DERIVED
HUMAN_DEFINED
AGENT_PROPOSED
```

Mai târziu:

```
BACKTEST_SELECTED
```

dar acesta nu există încă în #004.
28. Parametrii Evidence-derived
Dacă evidence-ul #003 motivează:

```
2–5 bars
```

acest lucru trebuie scris explicit.
Nu mascăm selecția drept prior.
29. Hypothesis Mode
Două moduri:
EXPLORATORY_HYPOTHESIS
Poate fi discutată/modificată.
Nu poate intra direct în formal backtest validation.
PREREGISTERED_STRATEGY
Immutable.
Poate intra în #005.
30. Lifecycle

```
DRAFT
↓
REVIEWED
↓
PREREGISTERED
↓
HANDOFF_TO_BACKTEST
```

Nu permitem:

```
BACKTESTED
↓
edit hypothesis
↓
same hypothesis_id
```

31. Orice modificare după preregistration
Creează:

```
new hypothesis_version
new hypothesis_id/fingerprint
```

Nu overwrite.
32. Hypothesis Registry
Acesta este parte din Strategy Registry.
Minimum:

```
hypothesis_id
hypothesis_version

status

parent_hypothesis_id
supersedes_hypothesis_id

definition_hash

created_at
approved_at

evidence_run_id
signature_set_id

proposer_provenance
review_provenance
```

33. Evidence provenance obligatorie
Hypothesis trebuie să indice exact:

```
evaluation_run_id
evaluation_engine_version
evaluation_config_version

signature_id
signature_set_id

discovery_engine_version
discovery_config_version

timeframe
```

34. Dacă evidence-ul se schimbă
Aceeași hypothesis nu este silently reused.
Exemplu:

```
Evaluation config v1
→ hypothesis H1
```

apoi:

```
Evaluation config v2
```

H1 rămâne legată de v1.
Noua interpretare generează:

```
H2
```

sau explicit reuse cu provenance nou.
35. AI Agents
#004 poate folosi agenți AI pentru reasoning.
Dar AI-ul NU devine source of truth.
Agentul produce:

```
HypothesisProposal
```

nu StrategyHypothesis finală.
36. Runtime architecture pentru AI
Nu vreau API calls înglobate în core-ul Strategy Registry.
Core #004 trebuie să accepte structured proposals.
Conceptual:

```
Evidence Packet
↓
GPT / Claude / future agent
↓
HypothesisProposal JSON
↓
validator
↓
review
↓
registry
```

37. De ce separăm AI de core
Pentru:

* model independence;
* token control;
* reproducibility;
* audit;
* replacement of models later.

38. Token-economy architecture
LLM nu primește:

* raw OHLCV history;
* mii de observations;
* toate features pe ani.

Primește un:
Compact Evidence Packet
39. EvidencePacket
Minimum:

```
signature_definition

support
concentration
opportunity_density

absolute_outcome summary
relative_outcome summary

baseline comparison

1/2/3/5/10-bar decay curve

stability bins

warnings

provenance
```

40. Token target
Packet-ul trebuie să fie compact.
Level-1 suggested:

```
~1–3 KB structured text / hypothesis candidate
```

nu zeci de mii de tokens.
41. Agent roles V1
Putem utiliza conceptual:

```
Agent A — Trend/market-structure interpretation
Agent B — Statistical skeptic
Agent C — Risk/exit critique
```

GPT/Claude pot juca aceste roluri inițial fără a construi trei API agents reali.
Important:
multiple roles ≠ multiple runtime LLMs obligatorii.
42. Independent first-pass reasoning
Pentru reducerea anchoring:
Ideal:

```
Agent A sees EvidencePacket
Agent B sees same EvidencePacket
```

fără să vadă inițial concluzia celuilalt.
Abia apoi:

```
Consensus pass
```

43. Consensus NU este voting pentru adevăr
Nu:

```
2 agents vote LONG
→ LONG is correct
```

Consensus înseamnă:
mai multe perspective independente ajung la aceeași structură de ipoteză și nu există objection blocker nerezolvat.
44. AgentReview

```
AgentReview

agent_id
model_id

hypothesis_proposal_id

stance:
    SUPPORT
    OBJECT
    ABSTAIN

objections[]
suggested_changes[]

timestamp
```

45. ConsensusRecord

```
ConsensusRecord

proposal_id

reviews[]

consensus_status:
    CONSENSUS
    DISAGREEMENT
    BLOCKED

unresolved_objections[]

human_decision
```

46. Human authority
Radu rămâne final approver.
AI consensus nu poate transforma automat:

```
DRAFT → PREREGISTERED
```

fără approval.
47. Statistical skeptic role
Un agent/review pass trebuie explicit să caute:

* low support;
* security concentration;
* temporal concentration;
* marginal FDR;
* inconsistent horizon behavior;
* regime dependence;
* suspicious opportunity scarcity.

Scopul nu este să inventeze trade-ul.
Este să caute motive pentru care hypothesis ar putea fi fragilă.
48. Hypothesis Proposal
Minimum:

```
HypothesisProposal

proposal_id

source_evidence

direction

entry_conditions

entry_execution_policy

horizon_candidates

exit_hypothesis

rationale

counterarguments

known_failure_modes

proposer
```

49. Rationale nu este statistică
Textul agentului poate spune:
compression + strong RS could represent stored volatility in a strong relative leader.
Aceasta este:

```
INTERPRETATION
```

nu fapt demonstrat.
Trebuie separat de Evidence.
50. Evidence vs Interpretation
Output-ul trebuie să distingă:

```
FACTS_FROM_EVIDENCE
```

de:

```
HYPOTHESIS_INTERPRETATION
```

51. Hypothesis Budget
Avem nevoie de protecție împotriva:

```
100 signatures
×
2 directions
×
5 horizons
×
8 exits
×
10 confirmations
```

Aceasta ar produce mii de strategii.
52. Level-1 Hypothesis Budget
Suggested TEST_CONFIG:

```
hypothesis_budget:
    max_hypotheses_per_signature: 3
    max_exit_families_per_hypothesis: 2
    max_confirmation_conditions: 1
```

Nu este validated trading rule.
Este research-control.
53. Budget nu ascunde hypotheses
Dacă 10 hypotheses au fost generate și doar 3 avansează:
Registry păstrează toate 10.
Nu:

```
delete rejected hypotheses
```

54. HypothesisUniverse
Pentru un research cycle:

```
HypothesisUniverse

universe_id

all_proposals
all_rejected
all_preregistered

selection_policy
```

Acest lucru devine foarte important în #005 pentru multiple strategy selection.
55. De ce păstrăm rejected proposals
Pentru a preveni:
„Am testat doar strategia câștigătoare.”
În realitate poate am considerat 40.
Research history trebuie să știe acest lucru.
56. Evidence eligibility for hypothesis generation
Nu orice EvidenceProfile trebuie să ajungă la AI.
Putem folosi o Research Queue deterministică.
57. Research Queue
Poate filtra pe:

```
support_status
missingness
concentration
stability availability
```

Dar trebuie să fim atenți la outcome selection.
58. Outcome-aware queue
Este permis ca queue-ul să folosească:

```
effect size
adjusted p
```

pentru prioritizarea research review.
Dar atunci aceasta este explicit:

```
DEVELOPMENT OUTCOME-AWARE SELECTION
```

și trebuie logată.
Nu putem pretinde ulterior că hypothesis era pre-specified independent de outcomes.
59. Recomandare pentru V1
Separăm:
ELIGIBILITY
Bazat doar pe quality/support:

```
SUFFICIENT_SUPPORT
missingness acceptable
```

PRIORITY
Poate folosi evidence strength.
Priority este operațională.
Nu este validare.
60. No Hypothesis Score
Nu construim:

```
HypothesisScore =
effect +
pvalue +
frequency +
agent votes
```

Forbidden în V1.
61. Research Queue poate avea ordering descriptiv
Pentru token budget putem ordona după fields transparente.
Exemplu:

```
adjusted_p ascending
robust effect magnitude descending
support descending
```

dar acest ordering trebuie numit:

```
REVIEW_PRIORITY
```

nu Alpha Score.
62. Review priority nu intră în backtest logic
Backtester-ul nu folosește:

```
review_priority
```

ca trading feature.
63. StrategyDefinition
După aprobare:

```
StrategyDefinition

strategy_id
hypothesis_id

market
universe_policy
timeframe

direction

signal_definition
entry_execution_policy

exit_definition

position_policy_placeholder

execution_assumptions_placeholder

status = PREREGISTERED
```

64. Universe Policy
Nu definim acum o listă statică de tickers.
Strategy folosește:

```
Universe Eligibility
```

din Data/Discovery pipeline.
Aceasta păstrează PIT discipline.
65. No ticker cherry-picking
Forbidden:
Strategy works except on AMD/TSLA, so exclude them.
Dacă apare o regulă de excludere după outcomes:
este o nouă hypothesis.
66. Sector restrictions
Dacă în viitor:

```
only semiconductors
```

trebuie explicit în StrategyDefinition.
Nu ad-hoc după backtest.
67. Market regime filters
La fel.
Exemplu:

```
SPY above SMA200
```

nu poate fi introdus după ce backtest-ul general arată slab.
Trebuie preregistered.
68. Daily → 4H readiness
Toate hypothesis entities trebuie să folosească:

```
timeframe
horizon_bars
```

nu:

```
holding_days
```

69. Multi-timeframe future
În viitor:

```
Daily context
+
4H signal
```

va fi o nouă StrategyHypothesis.
Nu trebuie redesign al registry-ului.
70. Entry/Exit feature provenance
Fiecare condition trebuie să indice:

```
source_feature_or_state
source_engine
source_version
```

71. Deterministic validation
Înainte să poată deveni PREREGISTERED:
validator-ul verifică:

* condition exists;
* timeframe exists;
* direction valid;
* exit family valid;
* horizon list valid;
* provenance matches;
* no forbidden fields;
* no future/outcome fields in signal conditions.

72. Outcome contamination rule
Entry / exit signal conditions NU pot include:

```
forward_return
adjusted_p
win_rate
mean_return
EvidenceProfile fields
```

Evidence poate motiva hypothesis.
Dar nu poate deveni feature de runtime.
73. Exemplu permis
Evidence:

```
compression + RS high
→ relative effect peaks around 3 bars
```

Hypothesis:

```
IF compression + RS high
THEN LONG
ENTRY next bar open
TIME_EXIT candidates = [2,3,5]
```

74. Exemplu interzis

```
IF adjusted_p < 0.05
AND mean_relative_return > 1%
THEN BUY
```

`adjusted_p` este research evidence, nu live signal.
75. Exit derivation — exact cum o facem
Aceasta este probabil partea cea mai importantă pentru tine.
Proces:

```
#003 decay profile
        ↓
identify plausible time region
        ↓
create bounded time-exit candidate set
        ↓
optional semantic invalidation exit
        ↓
freeze all variants
        ↓
#005 tests all preregistered variants
```

Nu:

```
backtest hundreds of exits
↓
pick best
↓
call it strategy
```

76. Exemplu complet
Evidence:

```
Signature:
Volatility Compression
+ RS VERY_HIGH

relative return:
1 bar   +0.2%
2 bars  +0.6%
3 bars  +1.0%
5 bars  +0.9%
10 bars +0.1%
```

Hypothesis:

```
Direction:
LONG

Entry:
signal at close(t)
entry next regular-session open

Time Exit Candidate Family:
[2,3,5] bars

Signal Invalidation:
optional exit if RS falls below HIGH

Risk Exit:
NOT DEFINED YET
```

Important:
nu selectăm 3 bars acum.
77. Exit selection în #005
#005 trebuie să știe că:

```
[2,3,5]
```

au fost toate candidate.
Dacă 3 câștigă în Development backtest:
aceasta este o selecție.
Nu este independent validation.
78. Cum evităm exit overfitting
Ideal, #005 va utiliza:

```
inner Development
→ select/compare strategy variant

outer Development validation / walk-forward
→ test selected rule

Locked OOS
→ final untouched confirmation
```

Detaliile apar în Spec #005.
79. Risk stop
Nu vreau să alegem acum:

```
1.2 ATR
1.5 ATR
2 ATR
```

din evidence-ul actual.
Nu avem MAE/MFE research suficient.
80. Prima strategie testabilă trebuie să aibă și un exit simplu
Pentru baseline:

```
TIME EXIT
```

este suficient.
După ce stabilim că entry-ul are valoare, adăugăm risk exits.
81. De ce nu complicăm exit-ul acum
Altfel nu vom ști dacă performanța vine din:

```
entry signal
```

sau:

```
complex exit optimization
```

Vrem decomposition.
82. Minimum strategy family
Pentru fiecare promising hypothesis:

```
Entry + Time Exit
```

este control strategy.
Apoi:

```
Entry + Signal Invalidation Exit
```

poate fi variantă.
83. Counterfactual / Null strategy
#005 va avea nevoie și de controls.
#004 trebuie să permită tagging:

```
BASELINE_VARIANT
EXPERIMENTAL_VARIANT
```

84. AI consensus și exit
Un agent nu poate spune:
„Cred că 1.7 ATR ar merge.”
fără provenance.
Poate propune:
„Un volatility-scaled protective stop ar trebui studiat ulterior.”
Acesta devine:

```
FUTURE_RESEARCH_NOTE
```

nu StrategyDefinition.
85. Research Notes
Entity:

```
FutureResearchNote

topic
rationale
trigger_for_future_spec
source_agent
```

Nu afectează StrategyHypothesis.
86. Reproducibility
Aceleași:

```
Evidence Packet
Hypothesis Config
Agent Proposal inputs
Human decisions
```

trebuie să poată reconstrui:

```
StrategyHypothesis
```

87. Agent output reproducibility
LLM text nu este determinist garantat.
De aceea reproducibility source of truth este:

```
structured accepted proposal
+
review record
+
human approval
```

nu regenerarea identică a textului AI.
88. No LLM in executable trading path
#004 AI reasoning este research-time.
Live trading nu trebuie să apeleze GPT/Claude pentru a decide:

```
BUY NOW?
```

pe baza unui text liber.
89. Live strategy must be deterministic
După StrategyDefinition:

```
same market inputs
→ same signal
```

fără LLM judgement.
90. Config
Suggested:

```
hypothesis_generation:
  mode: REVIEW_ONLY

  allowed_directions:
    - LONG
    - SHORT

  allowed_entry_execution:
    - NEXT_BAR_OPEN

  horizon_candidates:
    unit: BARS
    allowed_values:
      - 1
      - 2
      - 3
      - 5
      - 10

  hypothesis_complexity:
    max_entry_conditions: 3
    max_confirmation_conditions: 1

  hypothesis_budget:
    max_hypotheses_per_signature: 3
    max_exit_families_per_hypothesis: 2

  exit_families:
    - TIME_EXIT
    - SIGNAL_INVALIDATION

  risk_exit:
    enabled: false
```

91. Package structure
Suggested:

```
src/hypothesis/

  models/
    entities.py

  evidence/
    packet.py
    queue.py

  proposals/
    validator.py
    normalize.py

  consensus/
    reviews.py
    consensus.py

  registry/
    hypotheses.py
    strategy_registry.py

  validation/
    rules.py
    provenance.py

  config/
    hypothesis.yaml
    loader.py
```

No broker.
No backtester.
92. Core runtime token usage
The deterministic #004 core:

```
0 LLM tokens
```

External agents may consume tokens only during proposal generation/review.
93. LLM adapters
Optional and OUTSIDE core:

```
agents/
    gpt_adapter
    claude_adapter
```

I would actually not implement these yet.
At first we can manually pass compact EvidencePackets between GPT/Claude exactly as we are doing now.
94. Why delay agent APIs
Because we first need to know:
does the hypothesis schema work?
No reason to automate expensive LLM orchestration before that.
Token economy is part of architecture.
95. Deliverables
Minimum:

```
docs/spec004_architecture.md
docs/spec004_test_report.md
docs/spec004_known_limitations.md
docs/spec004_examples.md
docs/spec004_registry_contract.md
docs/spec004_agent_interface.md
```

96. Controlled examples
Minimum 4.
A — Valid LONG continuation hypothesis
Evidence:

```
strong RS + trend
short-horizon positive relative effect
```

Produces bounded LONG hypothesis.
B — Negative effect
Must NOT automatically flip to SHORT.
Show explicit separate SHORT proposal.
C — Horizon trap
Evidence peak at 3 bars.
System must produce candidate family, not auto `exit=3`.
D — Over-complex proposal
Agent proposes:

```
5 entry conditions
+
4 exit rules
```

Validator rejects based on complexity guardrail.
97. Required Tests
Minimum:
TEST 1 — EvidencePacket provenance
TEST 2 — EvidencePacket contains no raw price history
TEST 3 — StrategyHypothesis deterministic serialization
TEST 4 — Direction explicit
TEST 5 — No automatic LONG/SHORT flip
TEST 6 — Entry conditions only from approved Discovery fields
TEST 7 — Unknown indicator rejected
TEST 8 — Maximum entry complexity enforced
TEST 9 — Entry execution policy explicit
TEST 10 — Horizon unit = BARS
TEST 11 — Horizon candidates subset of allowed values
TEST 12 — No automatic best-horizon selection
TEST 13 — Time Exit hypothesis valid
TEST 14 — Signal Invalidation Exit valid
TEST 15 — Unsupported exit family rejected
TEST 16 — Risk exit disabled in V1
TEST 17 — No optimized ATR multiplier fields
TEST 18 — Evidence fields cannot appear in runtime signal
TEST 19 — No adjusted-p in entry rule
TEST 20 — No forward_return in entry/exit conditions
TEST 21 — Hypothesis fingerprint changes if direction changes
TEST 22 — Fingerprint changes if exit changes
TEST 23 — Fingerprint changes if Evidence provenance changes
TEST 24 — Frozen hypothesis immutable
TEST 25 — Modification creates new version
TEST 26 — Rejected proposals remain in registry
TEST 27 — Hypothesis Budget enforced
TEST 28 — Budget does not silently delete proposals
TEST 29 — AgentReview SUPPORT/OBJECT/ABSTAIN
TEST 30 — Consensus cannot auto-preregister
TEST 31 — Human approval required
TEST 32 — Disagreement preserved
TEST 33 — Facts vs interpretation separated
TEST 34 — Review priority not part of trading rule
TEST 35 — No HypothesisScore
TEST 36 — No direct PIT/raw-price imports
TEST 37 — No broker imports
TEST 38 — No backtesting imports
TEST 39 — No LLM imports in deterministic core
TEST 40 — Daily/4H timeframe metadata generic
TEST 41 — StrategyDefinition provenance consistency
TEST 42 — Discovery config mismatch rejected
TEST 43 — Evaluation run mismatch detectable
TEST 44 — Same inputs reproduce same hypothesis id
98. Hard FAIL conditions
#004 respins dacă:

* backtestează;
* accesează Locked OOS;
* accesează raw future returns direct;
* schimbă Discovery;
* auto-selectează best horizon;
* auto-flips LONG ↔ SHORT;
* optimizează stop-loss;
* introduce new indicators silently;
* LLM free-text devine direct executable signal;
* rejected hypotheses sunt șterse;
* hypothesis poate fi modificată după freeze fără version change;
* Evidence fields ajung în runtime entry conditions;
* AI consensus poate preregister fără human approval;
* HypothesisScore compus.

99. OUT OF SCOPE #004
Nu implementăm:

* backtesting;
* walk-forward;
* Locked OOS evaluation;
* transaction costs;
* slippage;
* fills;
* position sizing;
* portfolio allocation;
* MAE/MFE;
* ATR stop optimization;
* take-profit optimization;
* broker connection;
* live trading;
* 4H ingestion;
* crypto;
* options.

100. Ce produce #004 la final
Nu:
„Strategia este bună.”
Ci:
„Aceasta este ipoteza exactă pe care ne angajăm s-o testăm, inclusiv toate variantele pe care le-am considerat.”
101. Exemplu de StrategyHypothesis final

```
Hypothesis ID:
HYP_0042

Parent Signature:
VOL_COMPRESSION_RS_HIGH

Direction:
LONG

Signal:
volatility = COMPRESSION
AND
relative_strength = VERY_HIGH

Signal Time:
Daily close

Entry:
NEXT_BAR_OPEN

Candidate Time Exits:
2 / 3 / 5 bars

Optional Exit Variant:
RS falls below HIGH

Risk Stop:
NOT DEFINED

Evidence Source:
Evaluation Run EV_0018

Status:
PREREGISTERED
```

Acesta este suficient pentru #005.
102. Important pentru obiectivul nostru „tranzacții dese”
Opportunity density din #003 poate fi inclusă în EvidencePacket.
Dacă o ipoteză apare:

```
1 dată la 6 luni
```

este important operațional.
Dar nu falsificăm edge-ul ca să-i creștem frecvența.
103. Live-validation practicality
Putem raporta separat:

```
estimated_episode_frequency
```

pentru planificarea testului live cu capital mic.
Dar:

```
frequency != statistical quality
```

și nici:

```
frequency != expected profitability
```

104. Strategy family vs single strategy
Prefer ca #004 să producă:

```
StrategyFamily
```

când avem variante deliberate.
Exemplu:

```
Family F12

common entry:
Compression + RS

variant A:
2-bar exit

variant B:
3-bar exit

variant C:
5-bar exit

variant D:
signal invalidation
```

Acest lucru păstrează transparent faptul că am testat patru variante.
105. StrategyFamily entity

```
StrategyFamily

family_id

parent_hypothesis_id

common_entry_definition

variants[]

variant_count

selection_provenance
```

106. Nu generăm Cartesian explosion
StrategyFamily poate avea maxim:

```
configurable variant budget
```

Dacă 20 combinații sunt posibile, nu le generăm automat pe toate.
107. Dacă agentul propune prea multe variante
Status:

```
HYPOTHESIS_COMPLEXITY_EXCEEDED
```

Nu taie silencios lista.
108. Multiple-hypothesis accounting pentru #005
#004 trebuie să exporte:

```
all hypotheses considered
all variants considered
all rejected
all preregistered
```

#005 va avea nevoie de asta pentru selection-bias accounting.
109. Un principiu important
Cu cât #004 este mai liber să inventeze reguli, cu atât #005 devine mai puțin credibil.
De aceea prefer:
few, interpretable, explicitly registered hypotheses
în loc de:
„AI searched intelligently through 50.000 strategies.”
110. Întrebări obligatorii pentru Claude înainte de cod
Vreau răspuns explicit la următoarele.
A. Entry execution
Este de acord ca V1 să preregistreze:

```
signal = close(t)
entry = next regular-session open
```

ca singura convention de entry pentru #005?
Dacă vede problemă structurală, să o spună.
B. Exit V1
Este de acord ca V1 să permită doar:

```
TIME_EXIT
SIGNAL_INVALIDATION
```

iar ATR/protective-stop optimization să fie amânată?
C. Horizon selection
Cum propune să reprezinte:

```
[2,3,5 bars]
```

astfel încât #005 să știe că sunt trei variante considerate, nu trei strategii „independente” inventate după rezultate?
D. Hypothesis identity
Este mai curat ca:

```
StrategyFamily
```

să aibă un ID comun și fiecare variantă propriul:

```
strategy_variant_id
```

sau fiecare variantă să fie StrategyHypothesis complet separat?
Vreau argumentul lui.
E. Registry immutability
Cum garantează tehnic că:

```
PREREGISTERED
```

nu poate fi editat in-place?
Prefer content-addressed hash / append-only versions.
F. EvidencePacket
Poate #004 consuma #003 artifacts fără să importe PIT/Data Foundation?
Dacă nu:

```
IMPLEMENTATION BLOCKER
```

G. Agent integration
Confirmă dacă este de acord ca #004 core să nu implementeze niciun API GPT/Claude.
Doar schemas + proposal ingestion.
AI orchestration vine ulterior.
H. Research Queue
Propune contractul exact pentru:

```
ELIGIBLE_FOR_REVIEW
REVIEW_PRIORITY
```

astfel încât priority să poată utiliza evidence outcome-aware fără a deveni parte din strategy/runtime.
111. Instrucțiunea finală pentru Claude
Poți transmite integral spec-ul și la final:
Review Implementation Specification #004 completely before writing code.
Repository baseline: `266cc6f`.
Executable accepted baseline: Spec #003 at `d889049`.
DO NOT IMPLEMENT YET.
First confirm understanding of:

1. #004 forms hypotheses; it does not backtest them.
2. Locked OOS remains completely inaccessible.
3. Hypothesis formation may use #003 Development evidence, but that makes the hypothesis DEVELOPMENT-DERIVED, not independently validated.
4. Direction must be explicit; never automatically flip LONG/SHORT.
5. Entry conditions may use only approved #002 fields.
6. Entry timing must be preregistered before backtest.
7. Horizon candidates are a family; never auto-select the best Development horizon.
8. Exit V1 is hypothesis formation, not exit optimization.
9. TIME_EXIT is the mandatory baseline exit.
10. SIGNAL_INVALIDATION may be an optional variant.
11. MAE/MFE, ATR-stop optimization, take-profit optimization and position sizing remain out of scope.
12. Every considered/rejected variant remains in the registry.
13. PREREGISTERED hypotheses are immutable; changes create a new version/ID.
14. AI generates proposals; AI free text never becomes executable trading logic.
15. Human approval is required before preregistration.
16. Deterministic #004 core uses zero LLM runtime tokens.

Then answer §110 A–H.
If any answer requires changing accepted #001/#002/#003 contracts, label:
`IMPLEMENTATION BLOCKER`
and propose the smallest possible change.
Do not write code until GPT/Radu explicitly approve the architectural decisions.
Do not implement #005.
Do not implement broker/live trading.
Do not implement automated GPT/Claude API orchestration.
Pentru proiectul nostru, aici aș fi chiar mai strict decât la #003: nu vreau ca #004 să devină „generator AI de strategii” liber. Vreau să fie mai degrabă un registru disciplinat de ipoteze, în care AI-ul poate sugera idei, dar fiecare variantă testată rămâne vizibilă. Asta ne va permite, când vom ajunge la primele tranzacții cu bani puțini, să știm dacă avem un sistem care a trecut printr-un proces de validare real sau doar o strategie aleasă din sute de încercări.

> *(Claude's review/clarifying questions in response are not reproduced here -- only Radu's own messages. Radu's reply follows.)*

---

> **Original message 2/2** -- Radu, to Claude Code, session `5232cc45-b2e4-59d6-ba23-9687d55bed17`, transcript line 4426, timestamp `2026-09-25T11:40:18.161Z` (UTC).

---

Review-ul lui Claude este bun și, în mare, îl aprob. Nu văd nici eu un `IMPLEMENTATION BLOCKER`. Aș fixa însă acum două detalii care altfel vor deveni ambigue exact în #005: cum numărăm holding bars după intrare și cum limităm SIGNAL_INVALIDATION ca să nu creeze poziții cu durată nelimitată.
Decizie pe §110 A–H
A — APPROVED cu precizare obligatorie. Sunt de acord cu:

```
signal_time = CLOSE(t)
entry_execution = NEXT_REGULAR_SESSION_OPEN
horizon_reference_point = ENTRY_BAR
```

Observația lui Claude este importantă: evidence-ul #003 este `close(t) → close(t+h)`, în timp ce strategia executabilă va intra abia la `open(t+1)`. Cele două nu trebuie prezentate ca același return.
Pentru #004 vreau să înghețăm semantic și:

```
TIME_EXIT N bars
=
entry at open of entry bar
exit at close of the N-th holding bar
```

Exemplu pentru `N=3`:

```
Signal: Monday close
Entry: Tuesday open

Holding bar 1 = Tuesday
Holding bar 2 = Wednesday
Holding bar 3 = Thursday

Exit: Thursday close
```

Asta îi va elimina lui #005 libertatea de a interpreta retrospectiv „3 bars” în mai multe moduri.
B — APPROVED, cu o mică modificare.
V1:

```
TIME_EXIT
SIGNAL_INVALIDATION
```

fără ATR / MAE / MFE / optimized stop.
Dar orice `SIGNAL_INVALIDATION` trebuie să aibă și un time cap explicit.
Nu accept:

```
hold until RS deteriorates
```

fără limită, pentru că starea poate rămâne validă săptămâni întregi și ieșim din domeniul Fast-Swing.
Prefer:

```
EXIT on signal invalidation
OR
mandatory max_holding_bars
whichever occurs first
```

Exemplu:

```
RS_LOSS_OR_TIME_5
```

Astfel avem strategie complet definită înainte de backtest.
C — APPROVED.
Materializarea variantelor la freeze/preregistration time, nu în #005, este exact abordarea potrivită.
Dacă familia spune:

```
horizon_candidate_set = [2,3,5]
```

atunci înainte de backtest trebuie să existe deja:

```
variant_2bar
variant_3bar
variant_5bar
```

cu ID-uri proprii.
#005 nu „generează variante”. Doar testează variante deja înregistrate.
D — APPROVED: StrategyFamily + StrategyVariant.
Aș fixa relația exact așa:

```
StrategyFamily
│
├── common direction
├── common signal / entry definition
├── common entry execution policy
├── common evidence provenance
│
├── StrategyVariant A — TIME_EXIT 2
├── StrategyVariant B — TIME_EXIT 3
├── StrategyVariant C — TIME_EXIT 5
└── StrategyVariant D — INVALIDATION + MAX_TIME_CAP
```

Și regula lui Claude devine formală:
direction diferită sau entry logic diferită = alt StrategyFamily.
doar exit-ul diferă = variantă din aceeași familie.
Asta va fi foarte util când #005 va contabiliza selection bias.
E — APPROVED, cu separarea `definition_hash` de metadata administrativă.
Content-addressed design este alegerea corectă.
Dar nu vreau ca timestamp-uri precum:

```
approved_at
created_at
review timestamp
```

să intre în `definition_hash`.
Hash-ul trebuie să reprezinte sensul strategiei, de exemplu:

```
direction
entry definition
entry execution
timeframe
horizon semantics
exit definition
evidence provenance
relevant config provenance
```

Metadata de workflow este append-only, dar nu schimbă identitatea economică a strategiei.
Propun:

```
definition_hash
family_id
strategy_variant_id
registry_record_id
```

unde primele trei sunt content-derived, iar record-ul păstrează audit history.
F — APPROVED.
Exact:

```
EvaluationSignatureDefinition
+
EvidenceProfile
+
EvaluationRunRegistry
↓
EvidencePacket
```

#004 nu importă PIT și nu interoghează price history.
Asta este o boundary foarte bună.
Și aprob sugestia suplimentară:
`evaluation/` nu poate importa `hypothesis/`.
Vreau test structural explicit pentru dependency:

```
Data Foundation
    ↓
Discovery
    ↓
Evaluation
    ↓
Hypothesis
```

niciodată invers.
G — APPROVED fără modificări.
Nici OpenAI API, nici Claude API, nici alt LLM adapter în core-ul #004.
Input:

```
structured HypothesisProposal
```

Output:

```
validated / rejected / registered structure
```

Cine a generat JSON-ul este extern core-ului.
H — APPROVED, cu un guard important.
Separarea propusă este corectă:

```
ELIGIBLE_FOR_REVIEW
```

bazat pe data/evidence quality.
și:

```
REVIEW_PRIORITY
```

poate fi Development outcome-aware.
Vreau însă ca thresholds de eligibility, de exemplu:

```
maximum_missingness
minimum_valid_episode_n
minimum_unique_securities
```

să fie configurate și versionate înainte de queue run.
Nu vreau să le ajustăm după ce vedem ce signatures dispar din queue.
`REVIEW_PRIORITY` poate utiliza:

* adjusted p;
* effect magnitude;
* support;
* opportunity density;

dar trebuie să poarte permanent:

```
priority_basis = DEVELOPMENT_OUTCOME_AWARE_SELECTION
```

și să rămână complet în afara StrategyDefinition.
O modificare importantă la modelul Exit
Aș actualiza Spec #004 astfel:

```
ExitHypothesis

exit_family:
    TIME_EXIT
    SIGNAL_INVALIDATION

horizon_reference_point:
    ENTRY_BAR

time_exit_bars:
    optional

invalidation_conditions:
    optional

max_holding_bars:
    required for SIGNAL_INVALIDATION

exit_execution_policy:
    BAR_CLOSE
```

V1 nu are nevoie de mai multe tipuri de execuție.
Pentru o variantă:

```
SIGNAL_INVALIDATION
```

regula executabilă va fi:
Exit la close-ul primei bare la care condiția de invalidare este observabilă, sau la close-ul `max_holding_bars`, oricare survine prima.
Aici trebuie păstrată disciplina anti-lookahead: invalidarea bazată pe close-ul unei bare nu poate produce fill înainte ca acel close să existe. #005 va aplica exact timing-ul.
O observație importantă despre Evidence → Strategy
Vreau să păstrăm explicit două referințe diferite:

```
evidence_horizon_bars
```

și

```
strategy_holding_bars
```

Nu pentru că vrem două seturi de parametri, ci tocmai pentru a documenta că:

```
#003:
close(signal bar) → future close

#005 strategy:
next-open entry → later executable exit
```

Asta împiedică mai târziu afirmații de tipul:
„#003 a demonstrat +1% la 3 zile, deci strategia cu entry next-open și exit 3 bars are +1% expectancy.”
Nu. #003 a motivat ipoteza; #005 va măsura strategia executabilă.
Verdict pentru Claude
Poți să-i trimiți următoarea decizie:
Spec #004 architecture review — APPROVED TO IMPLEMENT, with the following clarifications.
A. Entry convention
Freeze V1 as:
`signal = CLOSE(t)`
`entry = NEXT_REGULAR_SESSION_OPEN`
`horizon_reference_point = ENTRY_BAR`
A `TIME_EXIT N` means entry at the open of the entry bar and exit at the close of the N-th holding bar.
Preserve explicitly that #003 evidence horizons are measured from the signal-bar close and therefore are not identical to executable #005 holding returns.
B. Exit families
V1 remains limited to:
`TIME_EXIT`
`SIGNAL_INVALIDATION`
No ATR/MAE/MFE/optimized risk exits.
Every `SIGNAL_INVALIDATION` variant MUST include a preregistered `max_holding_bars`; exit occurs on invalidation or the time cap, whichever happens first.
C/D. Family model
APPROVED:
`StrategyFamily` with common direction + entry logic + execution policy and materialized `StrategyVariant` records created at preregistration time.
Direction or entry-definition change → new family.
Exit/horizon change only → variant inside the same family.
#005 must never create missing variants dynamically.
E. Registry
Use content-addressed immutable definitions and append-only registry history.
Do not include administrative timestamps in `definition_hash`. Changes to trading meaning or evidence/config provenance must change the content hash / ID.
F. EvidencePacket
Build only from:
`EvaluationSignatureDefinition + EvidenceProfile + EvaluationRunRegistry`
No PIT/Data Foundation/raw price access from #004.
Add a dependency-direction test proving `evaluation/` cannot import `hypothesis/`.
G. AI
APPROVED: no GPT/Claude API adapters in deterministic #004 core.
H. Research Queue
Keep `ELIGIBLE_FOR_REVIEW` separate from outcome-aware `REVIEW_PRIORITY`.
Eligibility thresholds must be config-versioned and frozen before queue execution.
Any outcome-aware priority must be permanently labeled:
`DEVELOPMENT_OUTCOME_AWARE_SELECTION`
and must never enter StrategyDefinition/runtime rules.
No further architecture review is required unless implementation reveals a new `IMPLEMENTATION BLOCKER`.
Proceed with Spec #004 implementation only. Do not implement #005, broker integration, or automated LLM orchestration.
Cu aceste precizări, Claude are GO pentru implementarea Spec #004.
Și cred că alegerea `StrategyFamily + materialized variants` este una dintre cele mai importante decizii pe care le-am luat până acum: când vom vedea ulterior că „varianta 3-bars a mers cel mai bine”, istoricul va demonstra că 2, 3 și 5 bars au existat înainte de backtest, nu că am inventat 3 bars după ce am văzut rezultatul.
