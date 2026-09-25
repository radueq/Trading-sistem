"""TEST 36 -- BH-FDR routes each horizon's own adjusted-p (PATCH #003-A,
GPT Review #003 Round 1, mandatory finding #1).

The pre-patch bug: `benjamini_hochberg()` returned {signature_id: ...},
but the SAME signature is tested at every horizon_bars (a different
family each time) -- so the dict had one entry per signature_id, and
each family processed OVERWROTE the previous one's result. With a
single signature evaluated across the standard 5 horizons, the old code
would have applied ONE horizon's family_id/adjusted_p to ALL 5 profiles.
This test proves each profile now carries its OWN family's identity.
"""
from evaluation.engine import run_evaluation
from evaluation.models.entities import EvaluationSignatureDefinition, LaneStateCondition
from evaluation.registry.signatures import freeze_signature_set

from spec003.conftest import COMPRESSION_WINDOW_END, COMPRESSION_WINDOW_START


def test_each_horizon_gets_its_own_family_id_and_adjusted_p(conn, tiny_universe, reduced_discovery_config, fast_evaluation_config):
    sig = EvaluationSignatureDefinition(
        signature_id="VOLATILITY_COMPRESSION", lane_conditions=(LaneStateCondition("volatility", "COMPRESSION"),),
        reason_code_conditions=(), timeframe="1D", discovery_engine_version="v1.0.0",
        discovery_config_version=reduced_discovery_config.config_version, creation_mode="PRE_REGISTERED",
        created_before_outcome_evaluation=True,
    )
    sigset = freeze_signature_set([sig])
    profiles, registry = run_evaluation(
        conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
        COMPRESSION_WINDOW_START, COMPRESSION_WINDOW_END, sigset, reduced_discovery_config, fast_evaluation_config,
    )
    assert registry.mode == "FORMAL_DEVELOPMENT"
    horizons_seen = {p.horizon_bars for p in profiles}
    assert len(horizons_seen) >= 2, "sanity: need at least two distinct horizons to catch a cross-horizon overwrite"

    family_ids_by_horizon = {}
    for p in profiles:
        expected_family_id = f"1D|{p.horizon_bars}bars|relative_return|{registry.evaluation_run_id}"
        if p.baseline_comparison.raw_p is not None:
            assert p.baseline_comparison.family_id == expected_family_id, (
                f"horizon {p.horizon_bars}'s family_id does not match its own horizon -- "
                f"got {p.baseline_comparison.family_id!r}, expected {expected_family_id!r} "
                "(a cross-horizon overwrite would produce the SAME family_id string on every profile)"
            )
            family_ids_by_horizon.setdefault(p.horizon_bars, p.baseline_comparison.family_id)
            # with exactly one signature per horizon, BH-FDR on a
            # singleton family is the identity function: adjusted_p == raw_p.
            assert p.baseline_comparison.adjusted_p == p.baseline_comparison.raw_p

    distinct_family_ids = set(family_ids_by_horizon.values())
    assert len(distinct_family_ids) == len(family_ids_by_horizon), "each horizon must have a DISTINCT family_id"
