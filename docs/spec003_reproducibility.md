# Spec #003 v1.1 -- Reproducibility

Per Spec #003 SS60: the same data + config + signature set + seeds +
versions must produce IDENTICAL output, including the run's own
metadata -- not just "statistically similar" results. TEST 31 verifies
this directly against the real end-to-end pipeline.

## What is deterministic, and why

- **`EvaluationRunRegistry.evaluation_run_id`** (`registry/runs.py`) is
  a SHA-256 hash of the run's own defining inputs (development window,
  timeframe, `signature_set_id`, `discovery_config_version`,
  `evaluation_config_version`, bootstrap/comparison seeds) -- not a
  random or incrementing counter. Identical inputs always produce the
  identical run id, which is itself part of what TEST 31 checks.
- **`SignatureSet.signature_set_id`** (`registry/signatures.py`) is a
  hash of the SORTED signature fingerprints -- order-independent (TEST
  28), so listing signatures in a different order never produces a
  different id, but adding/removing one always does.
- **Bootstrap replicates** (`statistics/bootstrap.py`) use Python's
  `random.Random(seed)`, seeded explicitly per call -- never the global
  `random` module state, never `numpy`'s global RNG. Per-bin stratified
  baseline replicates use a stable, non-hash-based per-bin seed offset
  (`_stable_bin_offset`, an index into a SORTED bin-label list) --
  Python's built-in `hash()` is salted per-process for strings by
  design (a security feature), which would silently break
  cross-process/cross-run reproducibility if used here (TEST 18 confirms
  same-seed determinism directly).
- **Permutation test** (`statistics/comparison.py`) is likewise seeded
  explicitly via `random.Random(seed)`.
- **`config_version`** (both `discovery.config.loader` and
  `evaluation.config.loader`) is a SHA-256 hash of the relevant YAML
  file(s)' raw content -- a silent parameter/threshold change is
  structurally impossible to hide (mirrors Spec #002 SS45).

## What is NOT claimed reproducible across environments

- Floating-point summation order in `numpy`/`pandas` operations can
  differ by platform/BLAS backend at the level of the last few bits --
  not a concern for any threshold/bucket decision in this codebase
  (percentile buckets, support thresholds, BH-FDR comparisons), all of
  which use comfortable margins, but exact bit-for-bit equality across
  different hardware is not a claim this document makes.
- Wall-clock fields (`EvaluationRunRegistry.created_at`) are real
  timestamps by design -- excluded from any equality check that matters
  for reproducibility (TEST 31 compares `evaluation_run_id` and the
  `EvidenceProfile` list, not `created_at`).

## Reproducing a specific run

Given an `EvaluationRunRegistry` record, re-running `run_evaluation()`
with the same `security_ids`, `benchmark_security_id`,
`development_start`/`development_end`, the `SignatureSet` that hashes to
the recorded `signature_set_id`, and `DiscoveryConfig`/`EvaluationConfig`
objects whose `config_version` matches the recorded values, reproduces
the identical `evaluation_run_id` and `EvidenceProfile` list -- this is
exactly what TEST 31 does.
