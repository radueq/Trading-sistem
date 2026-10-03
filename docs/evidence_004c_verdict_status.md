# Evidence -- PATCH #004-C Verdict Status (as of 2026-09-28)

**Recovery note (Claude, 2026-10-03), not part of the original message:**
Recovered verbatim, byte-for-byte as Claude's own extraction of the
`content` field, from this Claude Code session's own transcript
(`5232cc45-b2e4-59d6-ba23-9687d55bed17.jsonl`), transcript line 11590,
timestamp `2026-09-28T16:08:13.175Z` (UTC). This is Radu's own message to Claude Code, in
full, with nothing added, removed, or reformatted below this note.

**What this message is:** Radu's Round-1 review verdict on Batch 3
(commit `cb9d67f`) -- CHANGES REQUIRED, with 7 numbered findings (these
7 findings were subsequently fixed; see commit `4f2a5f9`, "Batch 3
correction round: fix 7 findings from GPT review round 2," for that
unrelated-to-this-document resolution). The sentence this file is cited
for is the second-to-last paragraph: Radu explicitly separating PATCH
#004-C from this verdict, stating it remains its own, separate, open
item.

**Bounded claim, not an eternal one:** this message proves PATCH #004-C
had no verdict as of this timestamp. It does not by itself prove no
verdict was ever given later -- see `docs/contract_index.md`'s Spec #004
row for the bounded wording this evidence supports, and Claude's
statement there that nothing *later* in the transcript *checked* gives
it one either, which is a claim about what was searched, not a claim
that no such message exists anywhere. Not independently verified by
Radu as of this writing.

---

Da. Verdict: CHANGES REQUIRED pentru Batch 3 (`cb9d67f`). Am identificat erori concrete în diff; cele 570 passed / 1 skipped raportate nu le acoperă, iar un test confirmă chiar comportamentul greșit.
Pentru Claude, corecțiile necesare sunt:
1. Regula temporală verifică data greșită — blocant
`is_authorized_at_open()` compară `effective_date` cu data sesiunii. Contractul cere verificarea disponibilității informației, separat de data efectivă.
Consecințe:

* Split anunțat ieri, efectiv azi: codul cere inutil dovadă suplimentară.
* Split efectiv anterior, aflat azi după open: codul îl poate autoriza automat.

Corecție: verifică separat „efectiv până azi” și „cunoscut la open”, folosind politica knowledge-time existentă plus dovada temporală pentru aceeași zi. Aplică identic la intrare și Pasul 0.
2. Split-ul aflat tardiv este declarat evaluabil — contrar contractului
`test_late_known_split_still_open_position_catches_up_via_ratio` cere explicit `split_reconciliation_incomplete is False`, deși split-ul este efectiv pe 15 și aflat pe 25.
Faptul că poziția încă este deschisă nu demonstrează că verificările stop/țintă din sesiunile intermediare au fost corecte.
Corecție: când au fost simulate sesiuni afectate fără reconcilierea necesară, păstrează permanent `SPLIT_RECONCILIATION_INCOMPLETE`. O rescalare ulterioară nu repară evaluabilitatea traseului. Înlocuiește regresia care legitimează recuperarea „curată”.
3. ATR-ul nu este calculat pe o bază coerentă
`_raw_high_low_split_adjusted_close_df()` combină high/low brute cu close ajustat. În plus, reconcilierea multiplică întregul ATR cu raportul unei singure bare, fără să demonstreze scalarea uniformă a istoricului.
Contractul cere aceeași metodă Wilder și inițializare ca #002, dar seria folosită trebuie exprimată coerent pe baza intrării. Nu autorizează preluarea unei inconsistențe din #002.
Corecție: reconciliază seria OHLC până la `s`; folosește multiplicarea ATR doar dacă uniformitatea este demonstrată. Adaugă cazuri cu split în istoricul ATR, reverse split și ajustare neuniformă. Posibila problemă din #002 trebuie consemnată separat, fără modificarea tacită a rezultatelor istorice.
4. Factorul cumulativ poate include acțiuni neautorizate la open
În Pasul 0, după autorizarea unei acțiuni, `_current_split_factor()` preia factorul din seria PIT zilnică. Acesta poate include și alt split disponibil în aceeași zi, neautorizat la open.
Corecție: factorul aplicat trebuie construit exclusiv din acțiunile autorizate pentru acel open. Regresie cu două acțiuni: una autorizată și una blocată.
5. Economia tranșei închise nu este păstrată suficient în model
Split-ul modifică `position.entry_fill_price`, dar tranșa deja închisă păstrează doar propriul preț de ieșire, fără baza intrării sau rezultatul economic fixat.
Exemplu: intrare 100, profit parțial la 120, apoi split 2:1. Intrarea poziției devine 50; folosirea ei cu fill-ul istoric 120 produce +140% în loc de +20%.
Corecție: păstrează baza economică proprie tranșei sau rezultatul și costurile fixate la închidere. Testul trebuie să verifice randamentul agregat și comisioanele înainte/după split, nu doar egalitatea obiectului `partial_tranche`.
6. Validarea numerică și acoperirea MAE/MFE sunt incomplete

* `update_trailing_stop_at_close()` tratează drept invalid doar `None`; ATR zero, negativ sau nefin it nu primește obligatoriu marcajul persistent.
* Protecția inițială nu verifică explicit finitudinea tuturor nivelurilor calculate.
* MAE/MFE poate raporta `FULL` când lipsește bara ieșirii sau există valori lipsă. Lipsa datelor nu demonstrează acoperire completă.

Sunt necesare verificări și regresii pentru aceste cazuri.
7. Livrarea nu închide integrarea contractuală
Profilul nou și funcția medianei există separat, dar diff-ul nu conectează cerințele obligatorii la identitatea `ResearchPlan` și validarea metricii de selecție. Nici aplicarea slippage-ului și ordinea completă a sesiunii nu sunt demonstrate printr-un traseu integrat.
Separarea implementării în subetape este posibilă. Nu accept însă declararea acestor obligații ca fiind în afara scopului doar fiindcă infrastructura nu exista încă. Documentația trebuie să le marcheze drept cerințe restante, cu o mapare clară către livrarea următoare.
Nu închidem Batch 3 și nu promovăm încă baseline-ul `3cdc532`. PATCH #004-C rămâne separat pentru verdict; constatările de mai sus vizează Batch 3.
Am verificat codul din diff și raportul furnizat; nu am rulat independent suita. Continuăm aici, în Work, cu efort Ridicat, pentru corecții și verificarea deltei.
