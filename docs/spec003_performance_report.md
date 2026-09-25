# Spec #003 -- Performance Report

Universe: `tests/spec003/fixtures/tiny_universe.py` (3 securities + benchmark), Development window 2024-02-13..2024-03-19 (26 sessions).

| Metric | Value |
|---|---|
| Securities | 3 |
| Total ingested bars | 280 |
| Sessions in Development window | 26 |
| Raw observations (1 signature, all horizons) | 75 |
| Episodes (EPISODE_DEDUPLICATED) | 40 |
| Signatures tested | 1 |
| Horizon evaluations (signatures x horizons) | 5 |
| Statistical tests (bootstrap + permutation) per horizon | 3 (abs CI, rel CI, comparison) |

## Timing (informational, Level 1 tiny-universe scale -- not an acceptance blocker, mirrors Spec #002 SS37)

- Ingestion (4 securities): 0.016s
- Full run_evaluation() (26 sessions x 3 securities, 1 signature x 5 horizon evaluations): 1.119s
- Per-session average: 43.0ms

**LLM runtime tokens: 0** (Spec #003 SS61 -- zero LLM calls anywhere in this path, TEST 35).

Cost driver (documented, not hidden): one Discovery pass (compute_discovery_observations) per session, O(sessions x universe) -- the same acknowledged Level 1 tradeoff as Spec #002's own cross-sectional computation (docs/spec002_known_limitations.md). Fine at this scale; a real research-scale universe/date-range would need either a much larger time budget or an incremental/cached Discovery pass -- not built here, see docs/spec003_known_limitations.md.
