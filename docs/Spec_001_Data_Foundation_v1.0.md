# Spec #001 -- Data Foundation -- Recovered Original Text

**Recovery note (Claude, 2026-09-30), not part of the original specification:**
This text was recovered directly from this Claude Code session's own transcript (`5232cc45-b2e4-59d6-ba23-9687d55bed17.jsonl`) -- the chat messages Radu actually sent to Claude Code at the time this spec was implemented -- not from Radu's separate GPT conversation history, and not paraphrased or reconstructed from memory. **Four original Radu-authored messages are reproduced below, verbatim, in the order sent:** (1) the introduction, which was cut off before the specification body reached Claude; (2) the body's sections 1-15; (3) the body's sections 16-29; (4) a correction to point 1 plus the final lock/approval. Claude's own reply between (1) and (2) -- noting the cutoff and asking Radu to resend -- is **not** one of these four and is **not** reproduced as a message; it is mentioned only in a one-line aside below, for context. Each of the four fragments is Claude's direct copy of that message's own `content` field from the transcript, in the exact chronological order it was sent, with no correction, no reformatting, and no added or removed text beyond this note and the fragment-boundary/aside markers. **This recovery has not yet been independently verified by Radu** -- "byte-for-byte" describes Claude's own extraction process, not something Radu can confirm without the raw transcript fragments themselves; he should treat this file as a candidate primary source to check, not as confirmed.

**Completeness caveat (Radu, 2026-09-30):** all 29 numbered sections (1 through 29) are present below. Section 29 itself, however, ends mid-sentence -- "începem proiectarea:" ("we begin designing:") -- with nothing after it anywhere in this transcript. That closing line is recorded as missing here, not completed or inferred; it should be confirmed from source if a further fragment can still be located.

---

---

> **Original message 1/4** -- Radu, to Claude Code, session `5232cc45-b2e4-59d6-ba23-9687d55bed17`, transcript line 2, timestamp `2026-09-20T11:57:07.471Z` (UTC).

---

Implementăm un sistem automat de research și trading pentru acțiuni US. Acesta este primul modul: Implementation Specification #001 — Standard Internal Data Schema + Provider Adapter + Point-in-Time Data Access + Data QA.

Provider pentru Level 1 (Technical Prototype): yfinance.

Regulă critică de proces: dacă în timpul implementării identifici că specificația necesită o schimbare arhitecturală, NU modifica designul unilateral. Marchează explicit "IMPLEMENTATION BLOCKER" și descrie problema, cauza, soluția propusă și impactul, apoi oprește-te și așteaptă confirmarea mea. Bug fixes și detalii pur implementative nu necesită asta.

Te rog confirmă mai întâi că ai înțeles arhitectura de mai jos înainte să începi să scrii cod.

--- SPECIFICAȚIA COMPLETĂ ---

> *(Claude noted the message ended here and asked Radu to resend the specification body; Radu's reply follows.)*

---

> **Original message 2/4** -- Radu, to Claude Code, session `5232cc45-b2e4-59d6-ba23-9687d55bed17`, transcript line 29, timestamp `2026-09-20T12:08:07.383Z` (UTC).

---

1. SCOP
Construirea fundației de date a Trading System.
Modulul trebuie să producă:
date standardizate, auditabile și point-in-time safe, independent de provider.
Nu produce semnale de trading.
Nu calculează indicatori.
Nu caută edge.
Nu decide ce acțiuni vrem să tranzacționăm.
Arhitectura:

```text
EXTERNAL PROVIDER
       ↓
PROVIDER ADAPTER
       ↓
STANDARD INTERNAL DATA MODEL
       ↓
POINT-IN-TIME ACCESS LAYER
       ↓
DATA QA
       ↓
CLEAN / FLAGGED DATA
```

2. PRINCIPIU CENTRAL
Separăm explicit:
Data Quality
Datele sunt valide și utilizabile?
de:
Universe Eligibility
Dorim să tranzacționăm acest instrument conform regulilor sistemului?
Acest modul implementează Data Quality.
Universe Eligibility este OUT OF SCOPE pentru Spec #001.
Prin urmare:

* minimum price;
* minimum ADV;
* market-cap floor;
* spread limits pentru tradability;
* alte reguli de selecție

NU devin reguli permanente în acest modul.
3. STANDARD INTERNAL DATA MODEL
Nu folosim o singură tabelă gigantică.
Modelul logic conține componente distincte.
3.1 SECURITY MASTER
Identitatea internă a instrumentului.
Câmpuri minime:

```text
security_id
security_type
primary_exchange
currency
source_provider
source_security_id
```

`security_id` este identificatorul intern stabil.
Tickerul NU este identificitatea instrumentului.
Provider IDs trebuie mapate către `security_id`.
4. SYMBOL HISTORY
Tickerul este atribut temporal.
Schema conceptuală:

```text
security_id
ticker
exchange
valid_from
valid_to
source_provider
```

Trebuie să putem răspunde:
Ce ticker avea security X la data t?
și:
Ce security reprezenta ticker XYZ la data t?
Reutilizarea ulterioară a aceluiași ticker de altă companie NU trebuie să combine istoricele.
5. PRICE HISTORY
Schema minimă:

```text
security_id
date

raw_open
raw_high
raw_low
raw_close
raw_volume

source_provider
ingestion_timestamp
```

Raw data trebuie păstrate.
Nu suprascriem datele brute cu versiuni ajustate.
6. ADJUSTMENT DATA
Nu folosim un singur `adj_close` ambiguu.
Trebuie să putem distinge conceptual:
Raw prices
Prețurile efectiv raportate.
Split-adjusted series
Ajustare pentru split/reverse split.
Total-return series
Poate include efectul dividendelor/reinvestirii.
Metodologia exactă de generare a seriilor ajustate va fi explicită.
Dacă providerul oferă propriile adjusted prices, acestea pot fi păstrate pentru audit/comparison, dar nu trebuie confundate cu metodologia internă.
7. CORPORATE ACTIONS
Corporate Actions sunt stocate separat de Price History.
Schema conceptuală:

```text
security_id
action_type

announcement_date
effective_date

value
source_provider
status
```

Candidate `action_type`:

```text
SPLIT
REVERSE_SPLIT
DIVIDEND
MERGER
ACQUISITION
SPINOFF
OTHER
```

Regula temporală
`announcement_date` = când informația a devenit publică, dacă este disponibilă.
`effective_date` = când evenimentul a devenit efectiv.
Acestea NU sunt același lucru.
Exemplu:
un split poate fi anunțat la T1 și executat la T2.
Piața poate cunoaște evenimentul după T1.
Dar price adjustment nu se aplică ca și cum split-ul ar fi fost executat înainte de T2.
8. CORPORATE ACTION STATUS
Candidate status:

```text
ANNOUNCED
CONFIRMED
EFFECTIVE
CANCELLED
UNRESOLVED
```

`CORPORATE_ACTION_UNRESOLVED` în Data QA înseamnă:
există o discrepanță, ambiguitate sau informație insuficientă pentru a determina în siguranță efectul corporate action asupra seriei de preț.
Nu înseamnă pur și simplu:
evenimentul a fost anunțat dar încă nu a avut loc.
Un eveniment valid anunțat pentru viitor nu este automat eroare de date.
9. LISTING / STATUS HISTORY
Schema conceptuală:

```text
security_id
status
effective_from
effective_to
source_provider
```

Candidate statuses:

```text
PRE_IPO
ACTIVE
HALTED
SUSPENDED
DELISTED
```

Dacă există:

```text
delisting_reason
```

poate fi păstrat pentru audit/reporting.
Nu poate fi folosit retroactiv ca predictor înainte ca informația să fi devenit disponibilă.
10. POINT-IN-TIME DATA ACCESS
Aceasta este o cerință critică.
Data Store poate conține informații despre evenimente care s-au produs ulterior.
Dar modulele de research trebuie să vadă numai informația permisă la momentul simulat.
Prin urmare:
orice acces al Research Engine la date trece obligatoriu prin Point-in-Time Access Layer.
Interfața conceptuală:

```text
get_data(as_of = X, ...)
```

Nu există acces direct al:

* Discovery Engine;
* Candidate Selector;
* Hypothesis Engine;
* Backtester;
* Evaluation Engine

la tabelele brute.
11. SINGLE POINT OF ACCESS
Point-in-Time Access Layer este:
single controlled gateway către date pentru modulele downstream.
Nu se permit query-uri directe către Data Store „pentru comoditate” sau performanță.
Dacă ulterior performanța devine problemă, optimizăm gateway-ul.
Nu ocolim gateway-ul.
Această regulă există pentru prevenirea:
look-ahead leakage accidental.
12. PIT KNOWLEDGE VS EVENT DATA
Trebuie distinse:
event date
de:
information availability date.
Exemplu:
Data Store în 2026 poate ști:

```text
security X
delisted = 2021
```

Dar:

```text
get_data(as_of=2020)
```

nu poate expune downstream informația:
această security va fi delistată în 2021.
PIT correctness este impusă prin access layer.
Nu prin ștergerea informațiilor viitoare din Data Store.
13. DATA QUALITY MODEL
Nu folosim un singur enum:

```text
clean / suspicious / bad
```

Data QA produce:

```text
security_id
date
qa_pass
reason_codes[]
severity[]
```

O observație poate avea mai multe reason codes.
14. INITIAL QA REASON CODES
Lista inițială poate include:

```text
MISSING_BAR
DUPLICATE_BAR
ZERO_VOLUME
OHLC_INVALID
NEGATIVE_PRICE
SUSPICIOUS_GAP
STALE_PRICE
CORPORATE_ACTION_UNRESOLVED
ADJUSTMENT_MISMATCH
STATUS_CONFLICT
IDENTIFIER_CONFLICT
INSUFFICIENT_HISTORY
SOURCE_DISCREPANCY
```

Lista este extensibilă.
Reason codes trebuie să fie machine-readable și auditabile.
15. SEVERITY
Candidate severity:

```text
INFO
WARNING
ERROR
```

Semnificație:
INFO
Observație relevantă pentru audit, fără compromiterea datelor.
WARNING
Situație neobișnuită care necesită atenție, dar nu invalidează automat observația.
ERROR
Datele nu sunt considerate suficient de sigure pentru consum downstream.
În principiu:

```text
ERROR → qa_pass = FALSE
```

Dar maparea exactă:

```text
reason_code → severity
```

este configurabilă, nu hardcoded.

---

> **Original message 3/4** -- Radu, to Claude Code, session `5232cc45-b2e4-59d6-ba23-9687d55bed17`, transcript line 38, timestamp `2026-09-20T12:09:15.844Z` (UTC).

---

16. NIVEL 1 — TEST FIXTURES
În Technical Prototype putem folosi praguri și severity mappings pentru testare.
Acestea trebuie marcate explicit:

```text
TEST_CONFIG
```

Nu:

```text
DEFAULT_TRADING_RULES
```

Nicio valoare introdusă doar pentru a permite testarea software nu devine implicit regulă de trading.
17. MISSING DATA
Regulă:
NO SILENT FORWARD-FILL pentru OHLCV.
Missing data trebuie:

* detectată;
* păstrată ca informație;
* marcată prin reason code;
* tratată explicit.

Dacă ulterior un modul decide că o metodă de imputare este justificată, acea transformare trebuie:

* explicită;
* auditabilă;
* separată de raw data.

18. PROVIDER ADAPTER
Fiecare provider are adapter separat.
Conceptual:

```text
Provider A ─┐
Provider B ─┼→ ADAPTER → INTERNAL DATA MODEL
Provider C ─┘
```

Adapterul:

1. primește datele providerului;
2. mapează identifiers;
3. convertește în schema internă;
4. declară câmpurile indisponibile;
5. nu inventează valori pentru câmpurile lipsă;
6. păstrează provider/source metadata.

19. PROVIDER INDEPENDENCE
Niciun modul downstream nu trebuie să conțină logică precum:

```text
if provider == "X":
```

Provider-specific behavior trebuie izolat în adapter.
Regulă:
providerul nu dictează arhitectura internă.
20. DATA PROVENANCE
Trebuie să putem determina pentru datele importante:

* provider;
* provider security identifier;
* ingestion timestamp;
* event/source timestamp dacă disponibil;
* transformările aplicate.

Scop:
orice anomalie importantă trebuie să poată fi urmărită înapoi către sursă.
21. CELE TREI NIVELURI DE DATE
LEVEL 1 — TECHNICAL PROTOTYPE
Provider gratuit/ieftin.
Scop:

* schema;
* adapters;
* PIT gateway;
* QA logic;
* software correctness.

Nu tragem concluzii de trading.
LEVEL 2 — QA VALIDATION DATASET
Dataset controlat cu cazuri reale precum:

* normal securities;
* delistings;
* bankruptcies;
* M&A;
* ticker changes;
* splits;
* reverse splits;
* dividends;
* extreme illiquidity;
* halts/suspensions;
* missing/bad data.

Scop:
testarea Data QA și PIT pe failure modes reale.
Dimensiunea datasetului nu este fixată arbitrar.
Trebuie să acopere suficient tipurile importante de cazuri.
LEVEL 3 — RESEARCH-GRADE DATASET
Univers larg:

* PIT;
* delisted;
* corporate actions;
* historical universe;
* suficient istoric;
* calitate adecvată research-ului.

Discovery Engine nu produce concluzii serioase înainte de acest nivel.
22. PROVIDER BAKE-OFF
Înainte de alegerea providerului research-grade se execută un test controlat.
Evaluăm:

* delisted coverage;
* historical universe;
* corporate actions;
* raw data;
* adjustments;
* identifier stability;
* PIT capability;
* missing/bad data;
* Python accessibility;
* API/rate limits;
* licensing;
* cost.

Providerul final este ales pe baza rezultatului testului.
Nu pe baza marketingului.
23. TESTS — PASS/FAIL
Spec #001 nu este ACCEPTED până când testele obligatorii trec.
TEST 1 — OHLC integrity
Pentru sample controlat:

```text
low <= open <= high
low <= close <= high
```

și alte relații OHLC valide.
Anomaliile trebuie detectate.
TEST 2 — Split correctness
Cel puțin câteva evenimente cunoscute, inclusiv split/reverse split.
Verificăm:

* raw prices;
* corporate action;
* adjustment methodology;
* continuity.

TEST 3 — Dividend handling
Verificăm că dividendul:

* este identificat corect;
* nu este confundat cu split;
* nu modifică nejustificat raw prices.

TEST 4 — Delisting PIT
Pentru security delistată:
înainte de eveniment trebuie să apară conform informației disponibile atunci.
După delisting statusul trebuie să reflecte evenimentul.
Nu trebuie să existe hindsight leakage.
TEST 5 — Ticker change
Pentru caz real:

```text
OLD_TICKER
     ↓
same security_id
     ↓
NEW_TICKER
```

Istoricul trebuie să rămână continuu.
TEST 6 — Ticker reuse
Dacă același simbol este utilizat ulterior de altă security:
istoricele NU trebuie combinate.
TEST 7 — Missing data
Injectăm artificial missing bar.
Rezultat:

* detectat;
* reason code;
* fără silent fill.

TEST 8 — Provider consistency
Același instrument/perioadă prin doi provideri.
Diferențele trebuie:

* identificate;
* explicate sau marcate;
* niciodată ascunse.

TEST 9 — PIT LOOK-AHEAD TEST
Executăm:

```text
get_data(as_of=X)
```

Apoi încărcăm în Data Store evenimente/data ulterioare lui X.
Executăm din nou:

```text
get_data(as_of=X)
```

Informația disponibilă downstream trebuie să rămână identică.
Orice schimbare produsă exclusiv de informație viitoare:
FAIL CRITICAL.
TEST 10 — DIRECT ACCESS TEST
Modulele downstream nu trebuie să poată ocoli PIT Access Layer prin interfața normală a aplicației.
Orice asemenea cale:
architecture FAIL.
TEST 11 — Corporate Action timing
Pentru un eveniment:

```text
announcement_date < effective_date
```

verificăm că:

* informația despre announcement poate exista după announcement;
* adjustment-ul nu este aplicat prematur;
* effective event este tratat la data corectă.

TEST 12 — Universe sanity
Pentru date istorice selectate, verificăm dacă numărul și structura securities disponibile sunt plauzibile față de referințe independente.
Acesta este sanity check, nu test de egalitate exactă.
24. ACCEPTANCE CRITERIA
Spec #001 trece în status:
IMPLEMENTED / ACCEPTED
numai dacă:

1. internal schema funcționează;
2. cel puțin un Provider Adapter funcționează;
3. raw data sunt păstrate;
4. security_id funcționează independent de ticker;
5. Symbol History funcționează;
6. Corporate Actions sunt separate;
7. PIT gateway funcționează;
8. downstream access respectă gateway-ul;
9. QA reason codes/severity funcționează;
10. missing data nu sunt silently filled;
11. provenance este păstrată;
12. test suite obligatoriu trece.

Pentru unele teste Level 2 poate fi necesar un dataset mai bun decât cel gratuit.
Aceste teste pot rămâne explicit:

```text
PENDING_LEVEL_2_DATA
```

fără a pretinde că au trecut.
25. OUT OF SCOPE — SPEC #001
Nu implementăm încă:

* Trend;
* Momentum;
* Relative Strength;
* ATR;
* Bollinger Band Width;
* RVOL;
* percentiles;
* state dimensions;
* ΔX;
* Discovery Engine;
* Candidate Selector;
* Evaluation Engine;
* strategy logic;
* Alpha Score;
* Universe Eligibility;
* market-cap floor;
* minimum trading price;
* final liquidity thresholds;
* entry;
* exit;
* portfolio;
* broker execution.

26. IMPLEMENTATION PRINCIPLE
Claude Code trebuie să favorizeze:
correctness + auditability + modularity
înainte de:
performance + sophistication.
Nu optimizăm prematur.
Nu construim infrastructură pentru probleme pe care încă nu le avem.
Nu introducem o bază de date complexă doar pentru că arhitectura finală ar putea avea nevoie de una.
27. LIVRABILE CLAUDE CODE
La finalul implementării #001 trebuie să existe:
A. Cod executabil
Implementarea componentelor definite aici.
B. Automated test suite
Testele care pot fi executate cu Level 1 data.
C. Test report

```text
PASS
FAIL
PENDING_LEVEL_2_DATA
```

pentru fiecare test obligatoriu.
D. Architecture note
Scurt document care explică:

* structura implementată;
* unde sunt adapters;
* unde este PIT gateway;
* unde este QA;
* cum se adaugă un provider nou.

E. Known limitations
Listă explicită.
Nu ascundem limitările pentru a declara modulul „terminat”.
28. REGULA DE SCHIMBARE
Dacă în timpul implementării Claude Code descoperă că această specificație necesită o schimbare arhitecturală:
NU modifică unilateral designul.
Marchează:

```text
IMPLEMENTATION BLOCKER
```

și descrie:

* problema;
* cauza;
* soluția propusă;
* impactul.

Problema revine pentru review GPT + Claude + Radu dacă este materială.
Bug fixes și detalii pur implementative nu necesită redeschiderea arhitecturii.
29. NEXT GATE
După implementare:
Claude Code → Test Report
↓
Claude review
↓
GPT architecture/data-leakage review
↓
dacă PASS:
Spec #001 ACCEPTED
↓
începem proiectarea:

---

> **Original message 4/4** -- Radu, to Claude Code, session `5232cc45-b2e4-59d6-ba23-9687d55bed17`, transcript line 45, timestamp `2026-09-20T12:10:01.088Z` (UTC).

---

Confirm. Spec #001 rămâne FINAL v1.0 și poate intra în implementare.

Am însă o corecție la punctul 1 înainte ca Claude Code să pornească:

Corporate Action status nu trebuie derivat folosind timpul curent al calculatorului. Acest lucru ar putea face același dataset să producă metadata diferită în funcție de ziua în care rulează ingestion-ul.

Prefer:

announcement_date și effective_date = fapte temporale persistente furnizate/validate din date.

source_status = statusul providerului, dacă există.

Iar starea relevantă pentru o simulare la momentul t este derivată de PIT Access Layer în raport cu as_of=t, nu materializată în funcție de „azi”.

De exemplu:

announcement_date = 2024-05-22
effective_date    = 2024-06-10

get_data(as_of=2024-05-20) → NOT_KNOWN
get_data(as_of=2024-05-25) → ANNOUNCED
get_data(as_of=2024-06-10) → EFFECTIVE

Asta face comportamentul determinist și PIT-safe.

Punctele 2 și 3 sunt aprobate: severity mapping extern configurabil; Test 8 poate fi PENDING_LEVEL_2_DATA.

Iar pentru întrebarea explicită privind §10–11: da, aprob exact abordarea propusă. data_access.py devine gateway-ul unic pentru consumatorii downstream, iar testele care simulează un consumator downstream trebuie să folosească același gateway. TEST 10 trebuie să verifice această constrângere structural, nu doar prin convenție.

Fac doar distincția că testele foarte low-level ale storage/adapterului pot inspecta direct storage-ul atunci când testează storage-ul însuși. Interdicția privește consumatorii research/downstream; altfel am ajunge în situația absurdă în care nu putem testa baza de date deoarece testul nu are voie să o inspecteze.

Status

Master Context v2.0 — Baseline 001: LOCKED
Implementation Specification #001 v1.0: APPROVED / LOCKED
Implementation: AUTHORIZED

Claude Code poate începe.

Următorul lucru pe care vreau să-l văd aici este pachetul de rezultate prevăzut în §27: Test Report + Architecture Note + Known Limitations. Nu deschidem Spec #002 până nu facem review-ul #001.
