"""TEST 46 -- a REAL v2 `evaluation_run_id`, run through #005's own
identity cross-check, is ACCEPTED (joint remediation design 003+004,
section 12; decision registry I1; minimal #003 v2 -> #005
compatibility delta, authorized 2026-10-07, commit TBD).

History: `backtest/provenance/evaluation_run.py`'s `verify_evaluation_
run_identity()` originally recomputed ONLY the legacy 8-field recipe
(`LEGACY_RUN_ID_FIELDS`), so a genuine v2 run_id always failed -- a
KNOWN, FLAGGED, deliberately NOT-fixed consequence at the time of
Stage 2 (Spec #005-side code, out of Stage 2's own authorized scope;
this test used to assert exactly that failure, with that reasoning).

`verify_evaluation_run_identity()` now dispatches by the registry's
own `run_id_scheme_version`: `None` -> the unchanged legacy recipe
(every historical identity still verifies exactly as before); `"v2"`
-> the new 14-field v2 recipe (registry I1's own field set,
reconstructed exactly as `run_evaluation()` itself feeds
`build_run_id()`); anything else -> refused outright, no fallback.
This test proves the v2 path with a GENUINE `run_evaluation()` output,
not a hand-built registry -- `tests/spec005/test_41_...py` is #005's
own white-box coverage of the dispatcher's edge cases (missing
required fields, tampering, unknown schemes, no-fallback).
"""
from evaluation.engine import run_evaluation
from evaluation.models.entities import EvaluationSignatureDefinition, LaneStateCondition
from evaluation.registry.signatures import freeze_signature_set

from backtest.provenance.evaluation_run import recompute_legacy_evaluation_run_id, verify_evaluation_run_identity

from spec003.conftest import COMPRESSION_WINDOW_END, COMPRESSION_WINDOW_START


def test_real_v2_run_registry_is_accepted_by_005_own_identity_check(
    conn, tiny_universe, reduced_discovery_config, fast_evaluation_config, formal_calendar_registry, formal_calendar_id,
):
    sig = EvaluationSignatureDefinition(
        signature_id="VOLATILITY_COMPRESSION", lane_conditions=(LaneStateCondition("volatility", "COMPRESSION"),),
        reason_code_conditions=(), timeframe="1D", discovery_engine_version="v1.0.0",
        discovery_config_version=reduced_discovery_config.config_version, creation_mode="PRE_REGISTERED",
        created_before_outcome_evaluation=True,
    )
    sigset = freeze_signature_set([sig])
    _, run_registry = run_evaluation(
        conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
        COMPRESSION_WINDOW_START, COMPRESSION_WINDOW_END, sigset, reduced_discovery_config, fast_evaluation_config,
        calendar_registry=formal_calendar_registry, calendar_id=formal_calendar_id,
    )
    assert run_registry.run_id_scheme_version == "v2"

    ok, errors = verify_evaluation_run_identity(run_registry)
    assert ok, (
        f"a genuinely-produced v2 evaluation_run_id is now expected to be ACCEPTED by #005's own "
        f"identity cross-check, via the v2 recipe -- errors: {errors!r}"
    )

    # The LEGACY 8-field recipe still does NOT match this v2 id -- the
    # two recipes genuinely diverge; the fix is the DISPATCH by scheme,
    # not a change to what the legacy recipe itself computes.
    assert recompute_legacy_evaluation_run_id(run_registry) != run_registry.evaluation_run_id
