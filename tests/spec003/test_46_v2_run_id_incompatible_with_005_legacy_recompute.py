"""TEST 46 -- a REAL v2 evaluation_run_id, run through #005's own
LEGACY identity cross-check, concretely fails (joint remediation design
003+004, section 12; decision registry I1; GPT review, Stage 2
changes-required round).

`backtest/provenance/evaluation_run.py`'s `LEGACY_RUN_ID_FIELDS`/
`verify_evaluation_run_identity()` recompute `build_run_id()` from the
OLD 8-field recipe only. This is a KNOWN, FLAGGED consequence of the S2
fingerprint change (registry I1), documented but deliberately NOT
fixed this round -- `backtest/provenance/evaluation_run.py` is Spec
#005-side code, out of #003's own Stage 2 authorized scope; fixing it
is presented as a minimal-delta proposal for separate authorization
(see docs/implementation_plan_003_004_2026-10-05.md's own Stage 2
section), never silently implemented here.

This test does not fix anything -- it PROVES the consequence is real
with a genuine run_evaluation() output, rather than resting on a code
comment's own claim.
"""
from evaluation.engine import run_evaluation
from evaluation.models.entities import EvaluationSignatureDefinition, LaneStateCondition
from evaluation.registry.signatures import freeze_signature_set

from backtest.provenance.evaluation_run import verify_evaluation_run_identity

from spec003.conftest import COMPRESSION_WINDOW_END, COMPRESSION_WINDOW_START


def test_real_v2_run_registry_fails_005_own_legacy_recompute(
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
    assert not ok, (
        "a genuinely-produced v2 evaluation_run_id is EXPECTED to fail #005's own legacy 8-field "
        "recompute -- if this ever starts passing, either the v2 fingerprint stopped actually "
        "changing the hash, or #005's own recompute was updated (in which case this test's own "
        "docstring/assertion needs revisiting, not silently flipping)"
    )
    assert errors
