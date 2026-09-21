# Spec #002 -- Volume / Performance Report (Deliverable E)

Universe: synthetic Level 1 test fixtures (32 named + filler securities), as_of=2025-03-24.

| Stage | Count |
|---|---|
| Initial universe | 32 |
| Eligibility count (passed Universe Eligibility) | 31 |
| Valid-feature count (>= percentile_min_periods history) | 31 |
| Discovery-observation count (state signatures assembled) | 31 |
| Candidate count after budget | 20 |

## Timing (informational, Level 1 synthetic scale -- not an acceptance blocker per Spec #002 SS37)

- Ingestion (33 securities x ~320 daily bars): 0.375s
- Discovery (32 securities, 252-day percentile window): 0.869s
- Per-security average: 27.2ms
