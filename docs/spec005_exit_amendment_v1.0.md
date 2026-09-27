# Spec #005 — Amendament Exit v1.0 — ACCEPTED

**Status: ACCEPTED.** Baseline tehnic la momentul acceptării: `3cdc532`
(Spec #005 Batch 2, patch round 5 — acceptat separat). Batch 3 (motorul de
exit) și PATCH #004-C (implementarea de cod) sunt condiționate de acest
document și îl urmează, în commit-uri distincte.

PATCH #004-C + Amendament #005 (secțiunile 8, 9, 10, 12, 13, 15, 17, 18 din
`Spec_005_Backtesting_Exit_Evaluation_v1.0.md`).

Document autonom — nicio regulă de mai jos nu se bazează pe trimiteri la
conversația care a produs-o.

Context de proiectare (Radu, la deschiderea acestei runde): stop-loss
obligatoriu; fără ieșire automată pe timp; profit parțial ca variantă
testabilă (prag/fracție nedecise a priori); poziția rămasă păstrată până la
invalidarea trendului, cu stop-ul activ; realocarea capitalului între
poziții rămâne pentru o etapă viitoare de portofoliu (out of scope aici).
Decizie de proiectare explicită: condiția de intrare și condiția de
păstrare a poziției sunt separate — dispariția semnalului de intrare nu
declanșează niciodată, singură, un exit.

---

## 1. PATCH #004-C — `ExitHypothesis`, familie nouă

Aditiv. `ExitFamily.TIME_EXIT` și `ExitFamily.SIGNAL_INVALIDATION`, cu
validatorul lor existent (`hypothesis/validation/rules.py:166-171`, SS110-B —
`max_holding_bars` obligatoriu pentru `SIGNAL_INVALIDATION`), rămân
neschimbate, byte-cu-byte, pentru orice ipoteză/variantă deja înghețată.
Nicio modificare retroactivă.

```
ExitFamily.STOP_MANAGED_INVALIDATION   (nou)

ExitHypothesis (câmpuri noi, folosite doar de familia nouă):
    stop_loss: StopLossRule                       # OBLIGATORIU
        basis: "ATR_TRAILING_V1"                   # unica valoare permisă
        atr_multiple: float                         # k
    partial_profit: Optional[PartialProfitRule] = None
        r_multiple: float
        fraction: float                              # 0 < fraction < 1
    invalidation_conditions: tuple[InvalidationCondition, ...]  # >=1, scris explicit,
                                                                  # NU derivat din entry_definition
    max_holding_bars: None                          # interzis pentru această familie
    time_exit_bars: None                             # interzis pentru această familie
```

**Validator — reguli noi, aditive:**

- `exit_family == STOP_MANAGED_INVALIDATION` ⟹ `stop_loss` prezent,
  `stop_loss.basis == "ATR_TRAILING_V1"`, `stop_loss.atr_multiple` finit și
  `> 0`; dacă `partial_profit` prezent: `r_multiple > 0` finit,
  `0 < fraction < 1`; `max_holding_bars is None`; `time_exit_bars is None`;
  `len(invalidation_conditions) >= 1`, fiecare validă per regula SS22B/25
  existentă (nemodificată).
- `exit_family in (TIME_EXIT, SIGNAL_INVALIDATION)` ⟹ `stop_loss is None` ȘI
  `partial_profit is None`, respins altfel. Motiv: `_exit_fp()`
  (`hypothesis/registry/hypotheses.py:91`) nu referențiază aceste câmpuri
  pentru familiile vechi — fără interdicție, un `stop_loss` populat
  accidental pe o ipoteză veche ar fi un parametru ignorat de hash (două
  obiecte diferite, aceeași identitate).

`invalidation_conditions` pentru familia nouă se scrie explicit, la
înghețare — etichetele de păstrare (`holds_labels`) NU se copiază automat
din condițiile de intrare ale ipotezei-părinte.

**Derogare precisă de la SS79-81 (confirmată de Radu):** garda structurală
existentă (`tests/spec004/test_17_no_atr_multiplier_fields.py`, care scanează
`dataclasses.fields(ExitHypothesis)`/`StrategyDefinition` pentru token-urile
interzise `("atr","trailing","stop_loss","take_profit","kelly")`) și
gateway-ul de config `risk_exit.enabled == false`
(`hypothesis/proposals/validator.py:175-176`, `hypothesis.yaml`) rămân
regula generală, nemodificată — nici switch-ul, nici testul 16 nu se
schimbă. Derogarea de aici este STRICTĂ și NU redeschide sensul lor
original: acoperă EXCLUSIV câmpurile `stop_loss`/`partial_profit` de pe
`ExitHypothesis` și comportamentul de execuție pe care le definește acest
document pentru `STOP_MANAGED_INVALIDATION` — autorizate SEPARAT, printr-o
familie de exit nouă și explicită, fără a activa `risk_exit.enabled` și
fără a reinterpreta acel switch ca fiind, de la început, exclusiv despre
sizing/Kelly. Niciun alt câmp, pe `ExitHypothesis` sau pe
`StrategyDefinition`, nu beneficiază de această derogare; `test_17` este
actualizat (nu eliminat) ca să permită exact cele două câmpuri aprobate și
să continue să respingă orice altceva.

---

## 2. Validare — la înghețare vs. la intrarea simulată

**La înghețarea ipotezei** (nicio dată de piață disponibilă încă):
`k > 0`, `R > 0` (dacă există `partial_profit`), valori finite,
`0 < fraction < 1`, structură/vocabular valide (secțiunea 1). Nu se validează
poziția lui `S_initial`/țintei față de un preț de intrare — nu există încă
unul.

**La fiecare intrare simulată candidată** (secvență obligatorie, în ordine):

1. `SUPPRESSED_STAGE_BOUNDARY` — data NEXT_SESSION_OPEN a intrării nu se
   află în etapa autorizată (calendar; niciun preț citit).
2. `NO_ENTRY_BAR` — bara de open lipsește (regula §11 existentă,
   nemodificată).
3. `NO_VALID_STOP_BASIS` — `ATR_14(s)` (`s` = ultima sesiune încheiată
   înainte de fill, sesiunea semnalului), reconciliat pe baza intrării
   (secțiunea 3), lipsește, nu e strict pozitiv, sau reconcilierea de bază
   nu e posibilă (split între `s` și data intrării, fără informație
   suficientă pentru a re-exprima ATR-ul pe noua bază).
4. `INVALID_PROTECTIVE_LEVELS` — `S_initial`/țintă calculabile, dar
   economic imposibile:
   - long: cere `0 < S_initial < F_e` și (dacă `partial_profit`)
     `țintă > F_e`;
   - short: cere `S_initial > F_e > 0` și (dacă `partial_profit`)
     `0 < țintă < F_e`.

Fiecare dispoziție e înregistrată explicit (contorizată, auditabilă). Nu se
respinge retroactiv ipoteza; nu se șterge evidența intrării neexecutate.

---

## 3. Formule — long și short, complete

```
s = sesiunea semnalului (ultima încheiată înainte de fill)
F_e = preț de fill la intrare (NEXT_SESSION_OPEN, convenția #004 existentă)

S_initial(long)  = F_e − k·ATR_14(s)
S_initial(short) = F_e + k·ATR_14(s)

risc_inițial(long)  = F_e − S_initial       # distanță, FIXĂ la intrare
risc_inițial(short) = S_initial − F_e

țintă(long)  = F_e + R·risc_inițial          # dacă partial_profit configurat
țintă(short) = F_e − R·risc_inițial

La finalul sesiunii t (t >= sesiunea de intrare):
S_next(long)(t)  = max(S_activ, close(t) − k·ATR_14(t))
S_next(short)(t) = min(S_activ, close(t) + k·ATR_14(t))
```

`S_next` devine `S_activ` abia din sesiunea `t+1` — niciodată aplicat
retroactiv minimului/maximului zilei `t`. `risc_inițial` nu se recalculează
când stop-ul urcă/scade — rămâne referința fixă pentru țintă, pe toată
durata poziției (cu excepția rescalării de split, secțiunea 6).

**Reconciliere de bază între semnal și intrare — regulă exactă.** ATR-ul
inițial este calculat EXCLUSIV din barele încheiate până la sesiunea
semnalului `s`, inclusiv, folosind aceeași metodă, inițializare și istorie
necesară ca implementarea acceptată din #002 (Wilder, `discovery/features/
volatility.py`: aceeași fereastră `atr_window`, aceeași inițializare prin
media primelor `atr_window` true ranges). Bara zilei intrării NU participă
la calcul — nici ca bară adițională a ferestrei, nici pentru vreo altă
ajustare a rezultatului. Seria istorică (barele din fereastra ATR) e
exprimată pe baza prețului de intrare folosind NUMAI ajustările efective
și cunoscute la momentul deschiderii — schimbarea bazei nu autorizează
extinderea ferestrei de observație dincolo de `s`.

**Regulă explicită de acces temporal la open** (un gate zilnic, ca al #001,
nu poate singur distinge dimineața de după-amiază — regula de mai jos
suplinește exact acest gol, fără să modifice implicit politica Daily
existentă a #001 în alte contexte):

- O ajustare a cărei disponibilitate e cunoscută NUMAI ca dată e
  considerată disponibilă pentru o operație la open dacă acea dată e
  STRICT anterioară datei sesiunii (`data_disponibilității <
  data_sesiunii`).
- Disponibilitatea în ACEEAȘI zi ca sesiunea e acceptată NUMAI dacă există
  dovadă temporală suficientă (dincolo de simpla dată) că precedă sau
  coincide cu deschiderea. Fără o asemenea dovadă, ziua curentă a sesiunii
  NU se consideră autorizată la open.
- Regula se aplică ATÂT protecției inițiale (`S_initial`, mai sus), CÂT ȘI
  reconcilierii pozițiilor deja deschise la Pasul 0 (secțiunea 6) — aceeași
  cerință, aceleași două cazuri (strict anterior / aceeași zi cu dovadă).
- Dacă un split e deja efectiv, dar informația nu poate fi autorizată la
  open conform acestei reguli, NU combinăm prețul post-split cu ATR-ul
  pre-split: la intrare, respingem prin `NO_VALID_STOP_BASIS` (secțiunea 2);
  pentru poziții deja deschise la Pasul 0, marcăm reconcilierea incompletă
  — `SPLIT_RECONCILIATION_INCOMPLETE` (secțiunea 10).

**Mecanic** (când disponibilitatea E autorizată la open, conform regulii
de mai sus): fereastra ATR (barele până la `s`, inclusiv) se re-exprimă pe
baza intrării aplicând raportul `factor(s, as_of=data_intrării) /
factor(s, as_of=s)` — aceeași construcție ca Pasul 0 (secțiunea 6), dar o
singură re-derivare, o singură dată, ÎNAINTE ca poziția să existe, nu
sesiune-cu-sesiune. Multiplicarea întregului `ATR_14` cu un singur raport
e permisă NUMAI când ajustarea scalează UNIFORM întregul istoric folosit
de ATR — cazul unui split obișnuit (`compute_factors` din #001 scalează
fiecare bară anterioară `effective_date` cu același factor constant, deci
orice diferență/interval calculat din ele, inclusiv true range-urile care
alcătuiesc ATR, se scalează identic). O corecție istorică NEUNIFORMĂ de-a
lungul ferestrei (nu cazul unui split simplu) NU se poate rescala prin
multiplicarea indicatorului agregat — ar necesita reconcilierea seriei de
prețuri sursă, bară cu bară, și RECALCULAREA ATR-ului din seria
reconciliată, niciodată o scalare a valorii finale.

Exemplu (inegalitatea `s < effective_date <= data_intrării` — split-ul
poate fi efectiv chiar în ziua intrării): luni (`s`) `ATR_14=4` (bază
pre-split). Marți, split 2-for-1 (`value=2.0`), cu dovadă temporală
suficientă că era cunoscut ÎNAINTE de deschiderea de marți (altfel
exemplul nu s-ar autoriza la open, per regula de mai sus); intrare la
`F_e=50` (bază post-split). `ATR_14(s)` re-exprimat pe baza intrării =
`4 × (1/2.0) = 2`. Cu `k=2`: `S_initial = 50 − 2×2 = 46` (nu 42). Fără
această dovadă de anterioritate, aceeași situație s-ar respinge prin
`NO_VALID_STOP_BASIS` — vezi regresia dedicată mai jos.

Dacă re-exprimarea nu e posibilă (date insuficiente pentru fereastra ATR pe
noua bază), intrarea e respinsă — `NO_VALID_STOP_BASIS` (secțiunea 2),
niciodată o valoare aproximată.

**Regresii obligatorii:**
- split, respectiv reverse split, cu `s < effective_date <= data_intrării`
  ȘI dovadă temporală suficientă de anterioritate/coincidență cu
  deschiderea → reconciliere aplicată, `S_initial` corect (secțiunea 13);
- ACEEAȘI configurație, dar disponibilitate cunoscută DOAR ca dată,
  identică cu data sesiunii, FĂRĂ dovadă temporală suplimentară ("aceeași
  zi, oră necunoscută") → NU se autorizează la open; intrare respinsă prin
  `NO_VALID_STOP_BASIS` (sau, pentru o poziție deja deschisă la Pasul 0,
  `SPLIT_RECONCILIATION_INCOMPLETE`) — NU se combină prețul post-split cu
  ATR-ul pre-split;
- modificarea `high`/`low`/`close` din ziua intrării, cu open-ul și
  istoricul anterior lui `s` nemodificate, NU schimbă ATR-ul inițial,
  `S_initial` sau ținta — poate schimba doar execuțiile ulterioare din
  acea zi (Pasul 3′, secțiunea 5);
- o ajustare disponibilă abia după open (confirmat, nu doar neclar) NU e
  folosită pentru protecția inițială — rămâne pe baza cunoscută strict
  înainte de deschidere.

---

## 4. Variante inițiale de cercetare

Ambele variante folosesc **aceleași** condiții de invalidare a trendului
(`invalidation_conditions` identice) și același `stop_loss` (`k=2.0`) — se
diferă STRICT prin `partial_profit`:

| Variantă | `partial_profit` |
|---|---|
| Control | `None` |
| Parțial | `r_multiple=2.0`, `fraction=0.5` |

`k=2.0`, grila Control/2R-0.5 — valori de cercetare inițială, fără pretenția
de optimalitate. Profitul parțial execută o singură dată, pe fracția din
cantitatea deținută **la momentul declanșării** (baza de cantitate curentă,
deja rescalată de orice split anterior — nu cantitatea nominală de la
intrare, dacă un split a intervenit între intrare și declanșare).

---

## 5. Ordinea evenimentelor sesiunii (amendament §8)

Pașii 1, 2, 4, 5, 6 din §8 rămân **exact** cum sunt. Se inserează un pas
preliminar (Pasul 0, înainte de Pasul 1) și un pas nou (3′, după Pasul 2):

```
Pasul 0 (NOU): pentru fiecare poziție STOP_MANAGED_INVALIDATION DEJA
DESCHISĂ (din sesiuni anterioare — nu cele care se deschid azi):
    reconciliază acțiunile corporative devenite cunoscute ȘI efective la
    momentul autorizat al execuției acestei sesiuni (secțiunea 6). Rulează
    ÎNAINTE de Pasul 1, pentru ca o ieșire programată azi (din invalidare
    detectată la close-ul precedent) să se execute pe cantitatea/baza deja
    reconciliată.

Pasul 1 (§8 existent, nemodificat): execută ieșirile programate la
deschidere.

Pasul 2 (§8 existent, nemodificat): execută intrările în așteptare.
Pozițiile nou deschise azi pornesc DIRECT pe baza intrării (deja curentă,
post orice split cunoscut) — nu primesc ajustări istorice, pentru că nu au
încă o bază proprie mai veche de reconciliat.

Pasul 3′ (NOU): pentru fiecare poziție STOP_MANAGED_INVALIDATION activă azi
(inclusiv una intrată la Pasul 2). Ținta se verifică DOAR dacă
`partial_profit` e configurat ȘI nu a fost încă executată pentru această
poziție (o singură execuție, per secțiunea 4) — după ce s-a consumat, orice
sesiune ulterioară (aceeași zi sau mai departe) verifică DOAR stop-ul
pentru cantitatea rămasă:
    a) open(t) atinge/trece S_activ → STOP la open. fill=open(t) (convenție
       de model Daily îngheţată, nu garanție de execuție reală). Poziția
       (tot ce e activ) se închide. Nimic altceva azi pentru ea.
    b) altfel, dacă ținta e încă de verificat și open(t) atinge/trece
       țintă → ȚINTĂ la open. fill=open(t) (convenție de model, nu
       garanție). Vinde fracția F din cantitatea activă curentă. Ținta e
       consumată. Continuă la (c) cu restul, verificând ACUM doar stop-ul.
    c) pentru partea încă activă (nerezolvată de (a)/(b)), pe restul
       sesiunii — cazuri neambigue explicite:
       - doar stop-ul (long: low; short: high) atinge S_activ, ținta
         (dacă încă de verificat) nu → STOP la nivelul S_activ exact.
       - doar ținta (dacă încă de verificat) e atinsă, stop-ul nu →
         ȚINTĂ la nivelul țintă exact. Include explicit cazul: ținta
         executată la open (b) urmată, în ACEEAȘI sesiune, de stop atins
         intraday pe rest — acesta e cazul (b) urmat de "doar stop" de mai
         sus la (c), nu o ambiguitate.
       - AMBELE praguri (stop și, dacă încă de verificat, țintă) atinse în
         bara zilei și (a)/(b) nu a rezolvat deja ordinea prin poziția
         open-ului → ambiguitate reală, cronologia intraday necunoscută.
         Aplică stop-first. Contorizează `AMBIGUOUS_INTRABAR_CONFLICT`.

Pasul 4 (§8 existent): nu se aplică familiei noi (fără TIME_EXIT/CAP).
Pasul 5 (§8 existent, nemodificat pentru familiile vechi): invalidare
trend la close, pentru orice poziție/rest încă activ după Pasul 3′. Dacă
poziția s-a închis COMPLET la Pasul 3′ (cantitate rămasă zero), evaluarea
invalidării din acest close nu se mai cere pentru ea — nu există nimic
activ de verificat.

**Regulă obligatorie (incompletitudine persistentă):** dacă invalidarea
necesară NU poate fi evaluată într-o sesiune în care poziția (sau restul
ei) rămâne activă la Pasul 5 — de exemplu, o observație `UNKNOWN` pe
lane-ul urmărit (§7/§10) — poziția primește un motiv persistent de
incompletitudine (`INVALIDATION_PATH_INCOMPLETE`, secțiunea 10) și NU
intră în clasare, indiferent dacă se închide normal ulterior sau rămâne
cenzurată la limita etapei. O revenire la observații valide în sesiunile
următoare NU repară acest gol — golul e despre ce s-ar fi putut întâmpla
ATUNCI, nu despre starea de azi.

Pasul 6 (§8 existent, nemodificat): intrări noi pentru t+1.

La close(t): recalculează S_next (secțiunea 3) pentru partea activă;
devine S_activ abia din sesiunea t+1.
```

---

## 6. Reconciliere split — mecanism exact

Acest mecanism (Pasul 0) reconciliază poziții DEJA deschise, sesiune cu
sesiune, pe toată durata lor. E distinct de reconcilierea de bază
semnal→intrare (secțiunea 3), care e o singură re-derivare, făcută O DATĂ,
înainte ca poziția să existe — Pasul 0 nu se aplică niciodată la momentul
intrării înseși (poziția pornește direct pe baza curentă, secțiunea 5).

Este supus EXACT aceleiași reguli de acces temporal la open (secțiunea 3):
o ajustare cunoscută doar ca dată identică cu ziua sesiunii curente, fără
dovadă temporală suplimentară, NU se autorizează la open — reconcilierea
acelei sesiuni se marchează incompletă (`SPLIT_RECONCILIATION_INCOMPLETE`),
nu se aplică pe presupunere. Caveat-ul despre scalare uniformă (secțiunea
3) se aplică identic aici — raportul `current_factor/applied_factor` se
poate multiplica direct pe niveluri/cantitate NUMAI pentru o ajustare care
scalează uniform, ca un split obișnuit.

Fiecare poziție reține, ca stare proprie: `applied_factor` (inițial `1.0`
la intrare) și `processed_split_action_ids` (listă, pentru idempotență).

`current_factor` NU este factorul cumulativ generic al security-ului azi —
este factorul de ajustare, recalculat AZI, al PROPRIEI date de intrare a
poziției (aceeași rețetă `compute_factors` din #001, aplicată cu
`as_of=azi` datei de intrare). Un split anterior intrării e deja complet
inclus în baza pe care s-au calculat `F_e`/`S_initial`/țintă/risc la
momentul intrării — nu produce nicio reconciliere ulterioară.

```
La intrare: applied_factor := 1.0

Pasul 0, pentru fiecare poziție deja deschisă:
    current_factor := factorul de ajustare al datei DE INTRARE a acestei
                       poziții, cunoscut/efectiv la momentul autorizat de
                       azi (#001, compute_factors)
    dacă current_factor != applied_factor:
        raport = current_factor / applied_factor
        S_activ *= raport
        țintă *= raport                    (dacă partial_profit configurat)
        risc_inițial *= raport
        F_e_referință *= raport
        cantitate_rămasă /= raport
        applied_factor := current_factor
        processed_split_action_ids += [action_id-ul split-ului nou]
```

**Regulă de bază, pe cazuri:**

- **Anunț** (`available_at` cunoscut, `effective_date` neatins): nicio
  reconciliere. Niciun câmp se schimbă.
- **Cunoscut și efectiv**: reconciliere la Pasul 0 al primei sesiuni unde
  `_is_action_known_for_adjustment` devine `True` pentru acel split (gate
  #001, nemodificat), înainte de Pasul 1.
- **Aflat tardiv** (corecție de date descoperită după ce sesiunile au fost
  deja simulate): deciziile/fill-urile deja simulate NU se repară
  retroactiv. Dacă reconcilierea corectă nu mai poate fi făcută la sesiunea
  ei proprie, poziția primește `SPLIT_RECONCILIATION_INCOMPLETE` —
  neevaluabilă (secțiunea 10), motiv distinct de `TRAILING_PATH_INCOMPLETE`.
- **Tranșă deja închisă**: reconcilierea NU modifică valoarea economică,
  comisionul sau ponderea unei tranșe deja vândute — fapte istorice fixate
  la momentul lor. Ponderea (`F`/`1−F`) e o fracție din cantitatea
  ORIGINALĂ, adimensională, neafectată de split. Doar cantitatea și
  nivelurile RESTULUI, încă activ, se rescalează.
- **Reconciliere idempotentă**: un `action_id` din `processed_split_action_ids`
  nu se aplică a doua oară.

**Regresii obligatorii:** (a) anunț anticipat → zero schimbare de stare;
(b) disponibilitate tardivă → nicio reparare retroactivă a fill-urilor deja
simulate, poziție marcată `SPLIT_RECONCILIATION_INCOMPLETE` dacă
reconcilierea la timp nu a fost posibilă; (c) split imediat după profitul
parțial → tranșa închisă intactă (valoare, comision, pondere neschimbate),
restul corect rescalat; (d) invalidare detectată sesiunea precedentă +
split efectiv chiar în sesiunea ieșirii programate → Pasul 0 rulează
înaintea Pasului 1, ieșirea se execută pe baza deja reconciliată.

---

## 7. Profil de execuție (amendament §9)

Structură **separată**, versionată independent — `StopManagedExecutionSemanticsProfile v1`,
fingerprint și id proprii. `ExecutionSemanticsProfile` existent (6 câmpuri,
`execution_semantics_fingerprint()`) nu se modifică — nicio linie.

```
StopManagedExecutionSemanticsProfile v1:
    stop_loss_detection    = INTRA_BAR_LOW_HIGH_BREACH
    stop_loss_fill         = SAME_BAR_AT_LEVEL_OR_WORSE_OPEN
    partial_profit_fill    = SAME_BAR_AT_TARGET_OR_BETTER_OPEN
```

Ambele convenții de fill sunt reguli îngheţate ale modelului Daily — nu
afirmații despre execuție reală garantată (mirror exact al formulării
deja existente în §9 pentru fill-urile programate la close). Atingerea
unui nivel nu garantează execuția unui ordin limit real.

Invalidarea trendului pe restul poziției reutilizează, neschimbat, profilul
existent: `invalidation_detection = COMPLETED_BAR_CLOSE`,
`invalidation_fill = NEXT_SESSION_OPEN_AFTER_DETECTION`. `cap_is_hard`
rămâne exclusiv al profilului vechi — structural inaplicabil (obiect
diferit, câmp inexistent pe noua structură), nu implicit extins la familia
nouă.

**Obligatoriu pentru identitate**: orice `ResearchPlan`/rulare cu variante
`STOP_MANAGED_INVALIDATION` include AMBELE profiluri (cel vechi, pentru
intrare, + `StopManagedExecutionSemanticsProfile`) în identitatea
semantică. Nu opțional.

---

## 8. Invalidare trend (amendament §10)

Reutilizează vocabularul `InvalidationCondition` existent (lane-based),
neschimbat structural. Combinare OR între condiții multiple (regula §10
existentă). `holds_labels` scris explicit la înghețarea variantei
(secțiunea 1) — poate fi identic sau diferit de etichetele care au
calificat intrarea; separarea entry/holding e reală, nu nominală.

**Regula §7 existentă se păstrează neschimbată**: o observație lipsă e
`UNKNOWN`, niciodată automat "trend valid" și niciodată automat "exit".
Pe o sesiune cu observație `UNKNOWN` pentru lane-ul urmărit, poziția rămâne
deținută (nu se forțează un exit din lipsă de informație) — dar acest gol
NU e tratat ca inofensiv: per regula obligatorie din secțiunea 5 (Pasul 5),
un `UNKNOWN` care ar fi putut ascunde o invalidare reală taie poziția cu
`INVALIDATION_PATH_INCOMPLETE`, permanent, indiferent de ce se întâmplă
ulterior cu ea (se închide normal sau ajunge cenzurată).

---

## 9. Costuri (amendament §13) — formula exactă

Formula §13 originală, aplicată IDENTIC pe fiecare tranșă (niciun simbol
nou, niciun cost pre-normalizat):

```
net_return_tranșă (închisă) =
      d·(F_x − F_e)/F_e
    − c_e
    − c_x·(F_x/F_e)
    − borrow_drag_tranșă
```

`F_e` = fill-ul de intrare, comun ambelor tranșe. `F_x` = fill-ul propriu al
tranșei (`= țintă_fill`, fără slippage advers, pentru tranșa parțială;
`= nivel_fill·(1−d·s_x)` pentru orice tranșă închisă prin stop sau prin
invalidarea trendului — formula §13 originală, neschimbată). `c_x` e rata
de comision (aceeași convenție ca în §13 original: rată, normalizată prin
`F_x/F_e`, niciun cost pre-calculat).

**Pentru partea încă deschisă (cenzurată), formulă distinctă — fără cost
de ieșire imputat:**

```
net_return_rest_deschis =
      d·(mark_final − F_e)/F_e
    − c_e
    − borrow_drag_până_la_limită
```

Niciun termen `c_x`. Nu e "aceeași formulă cu `F_x = mark_final`" — e o
formulă separată, pentru că nu s-a produs nicio vânzare.

`borrow_drag_tranșă = rată_anuală × zile_calendaristice_proprii_tranșei / 365`,
pe notionalul inițial al ei — complet, neponderat, calculat ÎN INTERIORUL
formulei tranșei proprii (zilele proprii ale ei: de la intrare la propriul
ei exit, sau la limita etapei dacă e cenzurată).

```
w = fraction configurată în partial_profit, DACĂ profitul parțial a fost
    efectiv EXECUTAT pentru această poziție (ținta a lovit-o înaintea
    stop-ului sau a invalidării care ar fi închis totul dintr-o dată);
w = 0, în orice alt caz — varianta Control (partial_profit=None), SAU
    varianta Parțial în care stop-ul/invalidarea a închis poziția înainte
    ca ținta să se atingă vreodată.

rezultat_poziție = w·rezultat_tranșă_parțială + (1−w)·rezultat_rest
```

Când `w=0`, nu există `rezultat_tranșă_parțială` de evaluat — termenul e
absent, nu "0 × o valoare nedefinită". `rezultat_rest` folosește formula
de tranșă închisă (secțiunea 9, mai sus) dacă restul s-a închis, sau
`net_return_rest_deschis` dacă restul e încă activ/cenzurat la limita
etapei — niciodată aceeași formulă pentru ambele cazuri.

Ponderarea (`w`/`1−w`) se aplică O SINGURĂ DATĂ, aici, la agregare — nu și
în interiorul calculului de `borrow_drag` (care e deja complet/neponderat
per tranșă, folosind zilele proprii ale ei). Rate proporționale (§13: "no
fixed-dollar model") — combinarea prin medie ponderată cu cantitatea e
echivalentă matematic cu aplicarea o singură dată pe întregul notional,
fără dublă contabilizare.

---

## 10. Taxonomie stări — trei fațete independente

**Fațeta 1 — starea lifecycle-ului poziției** (exclusivă, exhaustivă):

- `CLOSED` — cantitatea rămasă este ZERO după execuții (stop pe tot ce era
  activ, sau succesiunea țintă-parțială + stop/invalidare pe rest). O
  vânzare parțială, singură, NU închide poziția — atâta timp cât rămâne
  cantitate activă, poziția nu e `CLOSED`.
- `CENSORED_AT_HORIZON` — există cantitate rămasă (activă) la limita etapei,
  fără ca vreo execuție DATORATĂ ÎN INTERIORUL etapei să fi eșuat. Include
  explicit cazul central: ținta parțială EXECUTATĂ, restul încă deschis la
  final — profitul parțial realizat nu schimbă fațeta, doar contribuie la
  `w` (secțiunea 9). Include și cazul: o invalidare a fost detectată la
  ULTIMUL close al etapei, cu fill programat pentru NEXT_SESSION_OPEN — dar
  acea dată aparține etapei următoare, deci execuția nu a devenit încă
  datorată în interiorul etapei autorizate; nu se citește open-ul următor.
  Poziția rămâne `CENSORED_AT_HORIZON`, cu ordinul în așteptare înregistrat
  explicit ca notă (`pending_exit_note`), fără efect asupra fațetei sau
  asupra valorii mark-to-market (care folosește doar ultimul close
  autorizat).
- `EXIT_FAILED` — o execuție NECESARĂ ȘI DATORATĂ ÎN INTERIORUL etapei
  autorizate (data ei programată de fill se află, ea însăși, în etapă) nu
  a putut fi realizată conform regulilor (`NO_EXIT_BAR` sau altă cauză de
  date). Distinct de `CENSORED_AT_HORIZON` prin exact acest test: execuția
  era datorată ÎN etapă și a eșuat, nu era datorată abia în etapa
  următoare.

**Fațeta 2 — evaluabilitate**: `EVALUABLE` | `UNEVALUABLE`.

**Fațeta 3 — motiv** (când `UNEVALUABLE`, sau ca etichetă informativă și
pe `EVALUABLE`): `NO_EXIT_BAR`, `TRAILING_PATH_INCOMPLETE`,
`INVALIDATION_PATH_INCOMPLETE` (secțiunea 5, Pasul 5 — o evaluare de
invalidare necesară nu a putut fi făcută, `UNKNOWN` sau altă cauză, cât
timp poziția era activă), `SPLIT_RECONCILIATION_INCOMPLETE`,
`CENSORED_MARK_UNAVAILABLE`, `UNKNOWN_ADJUSTMENT_BASIS` (§12 existent),
sau nimic (evaluare curată).

**Reguli de intersecție:**

- `CLOSED` + niciun motiv de mai sus → `EVALUABLE`.
- `CLOSED` + `TRAILING_PATH_INCOMPLETE`, `INVALIDATION_PATH_INCOMPLETE`
  sau `SPLIT_RECONCILIATION_INCOMPLETE` → `UNEVALUABLE` (s-a închis, dar
  traseul spre acolo nu e complet demonstrat — nu trece drept execuție
  completă a regulii).
- `CENSORED_AT_HORIZON` + close final autorizat disponibil + niciun motiv
  persistent de incompletitudine → `EVALUABLE`, intră în
  `MEDIAN_NET_RETURN_TO_EXIT_OR_STAGE_END` (secțiunea 9, cu `w` corect
  pentru profitul parțial deja realizat, dacă e cazul).
- `CENSORED_AT_HORIZON` + close final indisponibil → `UNEVALUABLE`,
  motiv `CENSORED_MARK_UNAVAILABLE`.
- `CENSORED_AT_HORIZON` + `TRAILING_PATH_INCOMPLETE` sau
  `INVALIDATION_PATH_INCOMPLETE` → `UNEVALUABLE` (motivul persistent
  domină, indiferent de disponibilitatea unui close final).
- `EXIT_FAILED` → **întotdeauna** `UNEVALUABLE`, motiv `NO_EXIT_BAR` (sau
  cauza specifică). O valoare contabilă calculabilă pentru date ulterioare
  poate fi raportată ca diagnostic separat, dar NU transformă poziția
  într-o cenzurare evaluabilă — execuția era datorată în etapă și a rămas
  nerezolvată.

**ATR invalid după intrare** (mid-poziție, nu la semnal): stop-ul rămâne la
ultima valoare validă — nu se relaxează, nu se inventează substitut.
Poziția primește `TRAILING_PATH_INCOMPLETE`, cu efectele de mai sus.

---

## 11. Selecție (amendament §15/§18)

```
executed_entries_count = toate pozițiile cu intrare EXECUTATĂ (indiferent de fațeta 1/2/3)

censored_ratio  = count(fațeta1 == CENSORED_AT_HORIZON) / executed_entries_count
evaluable_ratio = count(fațeta2 == EVALUABLE) / executed_entries_count
```

Ambele numărători/numitori din poziții cu intrare executată — niciodată din
semnale admise fără intrare (`NO_ENTRY_BAR`, `NO_VALID_STOP_BASIS`,
`INVALID_PROTECTIVE_LEVELS`, `SUPPRESSED_STAGE_BOUNDARY` nu contează aici).
`executed_entries_count == 0` → ambele rapoarte nedefinite; varianta ratează
deja `minimum_executed_trades`/`minimum_evaluable_trades` (praguri
existente, nemodificate).

`ranking_metric = MEDIAN_NET_RETURN_TO_EXIT_OR_STAGE_END` — **obligatoriu**
pentru orice `ResearchPlan` a cărui cohortă include variante
`STOP_MANAGED_INVALIDATION` (nu opțional, nu vechiul `MEDIAN_NET_RETURN`).
Planurile compuse exclusiv din familii vechi păstrează `MEDIAN_NET_RETURN`
neschimbat. Calculat pe setul `EVALUABLE` complet (fațeta 2), indiferent de
fațeta 1 (`CLOSED` sau `CENSORED_AT_HORIZON` — niciodată `EXIT_FAILED`,
care e mereu exclus). Pragurile existente `minimum_evaluable_trades`/
`minimum_evaluable_ratio` se aplică acestui set.

Mediana exclusiv pe tranzacții închise rămâne diagnostic separat,
neschimbat, niciodată folosită în clasare.

`maximum_censored_ratio` — opțional pe `SelectionRule`, interval `[0,1]`,
cerință de adecvare declarată — NU remediu pentru bias-ul de selecție (
remediul e metrica de mai sus, care include explicit pozițiile cenzurate
evaluabile).

Metrica nu elimină toate bias-urile de selecție posibile — reduce
specific pe cel identificat (exclusiv pozițiilor închise favorizate de
regula de exit însăși), pe baza informației efectiv observabile PIT-safe
la limita etapei.

---

## 12. MAE/MFE (amendament §17)

Profitul parțial NU încheie deținerea întregii poziții — restul rămâne
expus după vânzare, inclusiv restul acelei zile.

**Raportare pe tranșă**, nu pe poziție agregată, când există două tranșe:

- Tranșa parțială: MAE/MFE pe durata ei (intrare → fill-ul țintei).
- Tranșa rest: MAE/MFE pe durata ei proprie, mai lungă (intrare → exit-ul
  ei propriu, sau limita etapei).

Fără un număr unic "de poziție" combinat, când există două tranșe.

**Regula zilei parțial observate** (extinsă explicit la ambele tipuri de
exit intraday — stop ȘI țintă): pentru tranșa care se închide intraday în
ziua `t`, se păstrează ca inputuri valide: open-ul zilei și prețul de
execuție (ambele cunoscute) — se exclud extremele (low/high) a căror
ordine față de execuție nu poate fi stabilită din OHLC zilnic. Excluderea
nu produce automat un interval complet — rezultatul rămâne etichetat
`coverage: PARTIAL_EXIT_DAY_EXCLUDED`, niciodată prezentat ca precis dacă
nu e.

---

## 13. Compatibilitate — fingerprint, formulă exactă

**`_exit_fp()` (`hypothesis/registry/hypotheses.py:91`)** — extensie
condiționată de familie, string identic pentru familiile vechi:

```python
def _exit_fp(ex: ExitHypothesis) -> str:
    inv = "&".join(sorted(...))          # neschimbat
    base = (
        f"{ex.exit_family}::{ex.horizon_reference_point}::{ex.exit_execution_policy}::"
        f"{ex.time_exit_bars}::{inv}::{ex.max_holding_bars}::{ex.parameter_source}"
    )                                      # exact ca azi
    if ex.exit_family == ExitFamily.STOP_MANAGED_INVALIDATION.value:
        base += f"::{ex.stop_loss.basis}:{ex.stop_loss.atr_multiple}"
        base += (
            f"::{ex.partial_profit.r_multiple}:{ex.partial_profit.fraction}"
            if ex.partial_profit is not None else "::NO_PARTIAL_PROFIT"
        )
    return base
```

Pentru `TIME_EXIT`/`SIGNAL_INVALIDATION`, ramura nouă nu execută niciodată
— `base` e returnat identic, byte-cu-byte, cu comportamentul actual.

**`execution_semantics_fingerprint()`** — nemodificat, nicio linie.
`StopManagedExecutionSemanticsProfile` are propria funcție de fingerprint,
payload separat, id separat (prefix distinct, ex. `smxp_...`).

**Regresii obligatorii înainte de implementare:**

1. Replay pe fixture-uri #004 înghețate existente (din suita curentă) prin
   codul patch-uit → `variant_id`/`profile_id` identice cu cele produse
   azi (comparație directă, nu doar "aceeași formă").
2. Două variante `STOP_MANAGED_INVALIDATION` diferite doar prin `k` →
   `variant_id` diferite.
3. Un `ExitHypothesis(exit_family=SIGNAL_INVALIDATION, stop_loss=<populat>)`
   e respins de validator (secțiunea 1) — nu ajunge niciodată la
   `_exit_fp()` cu un câmp ignorat.
4. `build_execution_semantics_profile_v1()` produce același `profile_id`/
   `profile_hash` ca azi, neafectat de existența noii structuri separate.

**Regresii obligatorii de comportament (secțiunile 3, 5, 9, 10):**

5. Split, respectiv reverse split, cu `s < effective_date <= data_intrării`
   ȘI dovadă temporală suficientă că precede/coincide cu deschiderea →
   `S_initial` calculat pe ATR-ul re-exprimat pe baza intrării (secțiunea
   3), nu pe valoarea brută de la sesiunea semnalului.
5b. ACEEAȘI configurație ca #5, dar disponibilitate cunoscută DOAR ca
    dată, identică cu data sesiunii, FĂRĂ dovadă temporală suplimentară
    ("aceeași zi, oră necunoscută") → NU se autorizează la open; entry
    respins `NO_VALID_STOP_BASIS` (sau `SPLIT_RECONCILIATION_INCOMPLETE`
    pentru o poziție deja deschisă la Pasul 0) — nu se combină prețul
    post-split cu ATR-ul pre-split.
5c. Modificarea `high`/`low`/`close` din ziua intrării (open și istoricul
    până la `s` nemodificate) nu schimbă ATR-ul inițial/`S_initial`/ținta.
5d. O ajustare confirmat disponibilă abia după open nu e folosită pentru
    protecția inițială.
6. Țintă executată la open, urmată în ACEEAȘI sesiune de stop atins
   intraday pe cantitatea rămasă → tranșă parțială înregistrată la țintă,
   restul închis la stop, exact acea sesiune — cazul neambiguu explicit
   din secțiunea 5, nu ramura de ambiguitate.
7. O poziție cu profit parțial executat, al cărei rest rămâne activ până
   la limita etapei, fără alt eveniment → `CENSORED_AT_HORIZON`,
   `EVALUABLE`, `w` = fracția configurată (nu 0), rezultat combinat conform
   secțiunii 9.
8. O poziție cu `partial_profit=None` (Control) care rămâne activă până
   la limita etapei → `CENSORED_AT_HORIZON`, `w=0`, `rezultat_poziție =
   rezultat_rest` (fără termen de tranșă parțială).
9. O invalidare detectată la ultimul close al etapei, cu fill programat în
   etapa următoare → `CENSORED_AT_HORIZON` (nu `EXIT_FAILED`), fără citirea
   open-ului din etapa următoare, cu `pending_exit_note` înregistrat.
10. O sesiune cu observație `UNKNOWN` pe lane-ul de invalidare urmărit,
    cât timp poziția era activă la Pasul 5, urmată de observații valide
    ulterior și de o închidere normală → poziția rămâne
    `INVALIDATION_PATH_INCOMPLETE`, `UNEVALUABLE`, exclusă din clasare —
    revenirea observațiilor nu repară golul.
11. O poziție închisă COMPLET la Pasul 3′ (stop pe toată cantitatea) nu
    declanșează nicio verificare de invalidare la Pasul 5 pentru acea zi —
    nu generează `INVALIDATION_PATH_INCOMPLETE` din lipsă de evaluare
    aplicabilă.

---

## 14. Limitări declarate explicit (pentru Known Limitations, la implementare)

- Fill la open pentru un nivel deja depășit, și `slippage=0` pentru
  ordinul-țintă, sunt convenții ale modelului Daily — nu garanții de
  execuție reală (secțiunea 7).
- MAE/MFE pe ziua unui exit intraday e parțial, nu complet, prin
  construcție — OHLC zilnic nu permite ordonarea intraday exactă
  (secțiunea 12).
- `MEDIAN_NET_RETURN_TO_EXIT_OR_STAGE_END` reduce, nu elimină, riscul de
  selecție pe eșantion favorabil prin cenzurare (secțiunea 11).
- V1 nu acoperă realocarea de capital între poziții (rămâne pentru etapa
  de portofoliu, confirmat separat).
