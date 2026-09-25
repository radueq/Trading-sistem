# Spec #003 -- Multiple-Testing Report

Worked demonstration (Example D) of why raw p-values across many
tested signatures cannot be trusted naively, and why BH-FDR
(config `multiple_testing.method: BENJAMINI_HOCHBERG`, default
q=0.05) is mandatory for FORMAL_DEVELOPMENT mode (Spec #003 SS44).

### Example D -- Multiple-testing trap

30 independent PURE-NOISE synthetic signatures (no real
effect by construction, mean=0 for both groups), single horizon
(3 bars), tested together as ONE frozen family. Raw p-values alone
already look tempting for several of them; BH-FDR is what exposes
that as an artifact of testing many things at once.

| Signature | raw_p | adjusted_p (BH-FDR, q=0.05) | 'significant' at raw p<0.05? | after BH-FDR? |
|---|---|---|---|---|
| trap_sig_14 | 0.0030 | 0.0899 | YES | no |
| trap_sig_07 | 0.0380 | 0.5694 | YES | no |
| trap_sig_10 | 0.0899 | 0.7193 | no | no |
| trap_sig_20 | 0.1119 | 0.7193 | no | no |
| trap_sig_02 | 0.1489 | 0.7193 | no | no |
| trap_sig_26 | 0.1568 | 0.7193 | no | no |
| trap_sig_12 | 0.1678 | 0.7193 | no | no |
| trap_sig_19 | 0.2458 | 0.8747 | no | no |
| trap_sig_08 | 0.3167 | 0.8747 | no | no |
| trap_sig_17 | 0.3287 | 0.8747 | no | no |
| trap_sig_09 | 0.3746 | 0.8747 | no | no |
| trap_sig_04 | 0.4585 | 0.8747 | no | no |
| trap_sig_00 | 0.4665 | 0.8747 | no | no |
| trap_sig_16 | 0.4745 | 0.8747 | no | no |
| trap_sig_25 | 0.5135 | 0.8747 | no | no |
| trap_sig_22 | 0.5584 | 0.8747 | no | no |
| trap_sig_18 | 0.5844 | 0.8747 | no | no |
| trap_sig_29 | 0.6054 | 0.8747 | no | no |
| trap_sig_28 | 0.6204 | 0.8747 | no | no |
| trap_sig_01 | 0.6523 | 0.8747 | no | no |
| trap_sig_05 | 0.6623 | 0.8747 | no | no |
| trap_sig_03 | 0.7173 | 0.8747 | no | no |
| trap_sig_11 | 0.7173 | 0.8747 | no | no |
| trap_sig_06 | 0.7243 | 0.8747 | no | no |
| trap_sig_27 | 0.7433 | 0.8747 | no | no |
| trap_sig_23 | 0.7642 | 0.8747 | no | no |
| trap_sig_15 | 0.7872 | 0.8747 | no | no |
| trap_sig_21 | 0.8781 | 0.9341 | no | no |
| trap_sig_24 | 0.9321 | 0.9341 | no | no |
| trap_sig_13 | 0.9341 | 0.9341 | no | no |

**2/30** signatures look 'significant' by raw p<0.05 alone (pure chance, since every signature here is genuinely pure noise) -- BH-FDR correctly brings that down to **0/30**. This is exactly why Spec #003 SS26 freezes the Signature Set before looking at outcomes, and SS44 makes BH-FDR mandatory for FORMAL_DEVELOPMENT: testing 30 things and reporting only the 'winners' would silently reproduce this exact trap.

## Family definition (Spec #003 SS45)

A family = same `timeframe` + `horizon_bars` + `outcome_type` + 
`evaluation_run` (see `evaluation.statistics.multiple_testing.family_id`).
Signatures tested at a DIFFERENT horizon never correct each other's
p-values (TEST 22 proves this in isolation).
