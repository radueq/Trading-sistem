# Spec #003 -- Example Evaluation Output (Deliverable D-equivalent)

**All four examples below are computed from deterministic synthetic
(date, return) series fed directly into the statistics primitives
(describe/bootstrap/permutation) -- no live-market data anywhere.
Every number is exactly what the code computed, not hand-edited.**

Fast-Swing framing (Spec #003 v1.1): horizons are 1/2/3/5/10 BARS,
never calendar days -- see docs/spec003_architecture.md.

### Example A -- Fast effect, decays by 5-10 bars

- **1 bar(s)**: mean=0.0169, median=0.0166, 95% CI=(0.0144, 0.0191), raw_p=0.0010
- **2 bar(s)**: mean=0.0193, median=0.0210, 95% CI=(0.0147, 0.0243), raw_p=0.0010
- **3 bar(s)**: mean=0.0261, median=0.0276, 95% CI=(0.0244, 0.0277), raw_p=0.0010
- **5 bar(s)**: mean=0.0091, median=0.0076, 95% CI=(0.0070, 0.0114), raw_p=0.0010
- **10 bar(s)**: mean=0.0013, median=0.0004, 95% CI=(-0.0012, 0.0050), raw_p=0.9560

Interpretation: the effect is strongest at 1-3 bars and has essentially vanished by 10 -- exactly the profile a Fast-Swing target (~1-5 day holding) should care about. #003 reports this curve; it does NOT pick '3 bars' as 'the exit' (Spec #003 SS53).

### Example B -- Delayed effect, builds into 3-5 bars

- **1 bar(s)**: mean=0.0019, median=0.0011, 95% CI=(-0.0014, 0.0050), raw_p=0.5674
- **2 bar(s)**: mean=0.0063, median=0.0062, 95% CI=(0.0023, 0.0105), raw_p=0.0090
- **3 bar(s)**: mean=0.0158, median=0.0154, 95% CI=(0.0132, 0.0186), raw_p=0.0010
- **5 bar(s)**: mean=0.0216, median=0.0203, 95% CI=(0.0196, 0.0236), raw_p=0.0010
- **10 bar(s)**: mean=0.0131, median=0.0146, 95% CI=(0.0100, 0.0158), raw_p=0.0010

Interpretation: the opposite decay shape from A -- weak immediately, stronger after 3-5 bars. Reported the same way, same machinery, no special-casing.

### Example C -- Pure noise, no true difference

- **1 bar(s)**: mean=0.0004, median=-0.0002, 95% CI=(-0.0038, 0.0043), raw_p=0.4615
- **2 bar(s)**: mean=0.0011, median=0.0038, 95% CI=(-0.0030, 0.0048), raw_p=0.2917
- **3 bar(s)**: mean=-0.0006, median=-0.0027, 95% CI=(-0.0033, 0.0022), raw_p=0.7183
- **5 bar(s)**: mean=0.0003, median=-0.0006, 95% CI=(-0.0034, 0.0037), raw_p=0.4705
- **10 bar(s)**: mean=-0.0006, median=-0.0013, 95% CI=(-0.0046, 0.0032), raw_p=0.7023

Interpretation: raw_p should NOT cluster near 0 across horizons here -- if it does, that is itself a red flag about the method, not a discovery. Demonstrated below to behave as expected.

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

