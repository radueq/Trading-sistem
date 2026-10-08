"""TEST 43 -- run-identity fingerprint, S2 fields + run_id_scheme_version
(joint remediation design 003+004, section 12; decision registry I1,
revision 5-6; authorized 2026-10-06, Stage 2).

`build_run_id()`'s fingerprint gained, together, this stage:
`security_ids` (sorted), `benchmark_security_id`, `data_as_of`,
`horizons` (sorted), and a new `run_id_scheme_version` literal. Five
INDEPENDENT axis checks, not one -- two runs identical in every other
input but differing in exactly ONE of these five must produce
different `evaluation_run_id`s.
"""
from evaluation.engine import RUN_ID_SCHEME_VERSION, run_evaluation
from fixtures.config_overrides import evaluation_config_with_overrides
from evaluation.models.entities import EvaluationSignatureDefinition, LaneStateCondition
from evaluation.registry.runs import build_run_id
from evaluation.registry.signatures import freeze_signature_set

from spec003.conftest import COMPRESSION_WINDOW_END, COMPRESSION_WINDOW_START


def _signature(discovery_config_version):
    return EvaluationSignatureDefinition(
        signature_id="VOLATILITY_COMPRESSION", lane_conditions=(LaneStateCondition("volatility", "COMPRESSION"),),
        reason_code_conditions=(), timeframe="1D", discovery_engine_version="v1.0.0",
        discovery_config_version=discovery_config_version, creation_mode="PRE_REGISTERED",
        created_before_outcome_evaluation=True,
    )


def _run_id(
    conn, security_ids, benchmark_security_id, reduced_discovery_config, evaluation_config,
    calendar_registry, calendar_id, data_as_of=None,
):
    sigset = freeze_signature_set([_signature(reduced_discovery_config.config_version)])
    _, registry = run_evaluation(
        conn, security_ids, benchmark_security_id,
        COMPRESSION_WINDOW_START, COMPRESSION_WINDOW_END, sigset, reduced_discovery_config, evaluation_config,
        data_as_of=data_as_of, calendar_registry=calendar_registry, calendar_id=calendar_id,
    )
    return registry.evaluation_run_id


def test_different_security_ids_produce_different_run_ids(
    conn, tiny_universe, reduced_discovery_config, fast_evaluation_config, formal_calendar_registry, formal_calendar_id,
):
    full = tiny_universe["non_benchmark_ids"]
    subset = full[:-1]
    assert len(subset) < len(full)  # otherwise this axis isn't actually exercised
    id_full = _run_id(conn, full, tiny_universe["benchmark_security_id"], reduced_discovery_config, fast_evaluation_config, formal_calendar_registry, formal_calendar_id)
    id_subset = _run_id(conn, subset, tiny_universe["benchmark_security_id"], reduced_discovery_config, fast_evaluation_config, formal_calendar_registry, formal_calendar_id)
    assert id_full != id_subset


def test_different_benchmark_security_id_produces_different_run_id(
    conn, tiny_universe, reduced_discovery_config, fast_evaluation_config, formal_calendar_registry, formal_calendar_id,
):
    security_ids = tiny_universe["non_benchmark_ids"]
    real_benchmark = tiny_universe["benchmark_security_id"]
    swapped_benchmark = security_ids[0]
    id_real = _run_id(conn, security_ids, real_benchmark, reduced_discovery_config, fast_evaluation_config, formal_calendar_registry, formal_calendar_id)
    id_swapped = _run_id(conn, security_ids, swapped_benchmark, reduced_discovery_config, fast_evaluation_config, formal_calendar_registry, formal_calendar_id)
    assert id_real != id_swapped


def test_different_data_as_of_produces_different_run_id(
    conn, tiny_universe, reduced_discovery_config, fast_evaluation_config, formal_calendar_registry, formal_calendar_id,
):
    security_ids = tiny_universe["non_benchmark_ids"]
    benchmark = tiny_universe["benchmark_security_id"]
    id_a = _run_id(conn, security_ids, benchmark, reduced_discovery_config, fast_evaluation_config, formal_calendar_registry, formal_calendar_id, data_as_of=COMPRESSION_WINDOW_END)
    earlier_as_of = COMPRESSION_WINDOW_START
    id_b = _run_id(conn, security_ids, benchmark, reduced_discovery_config, fast_evaluation_config, formal_calendar_registry, formal_calendar_id, data_as_of=earlier_as_of)
    assert id_a != id_b


def test_different_horizons_produce_different_run_id(
    conn, tiny_universe, reduced_discovery_config, fast_evaluation_config, formal_calendar_registry, formal_calendar_id,
):
    security_ids = tiny_universe["non_benchmark_ids"]
    benchmark = tiny_universe["benchmark_security_id"]
    other_cfg = evaluation_config_with_overrides(horizons={"unit": "BARS", "values": [1, 2]})
    id_a = _run_id(conn, security_ids, benchmark, reduced_discovery_config, fast_evaluation_config, formal_calendar_registry, formal_calendar_id)
    id_b = _run_id(conn, security_ids, benchmark, reduced_discovery_config, other_cfg, formal_calendar_registry, formal_calendar_id)
    assert id_a != id_b


def test_different_run_id_scheme_version_produces_different_id():
    """`run_id_scheme_version` is a module constant, not a run_evaluation()
    parameter -- exercised directly at the build_run_id() level, holding
    every other fingerprint field fixed."""
    common = dict(
        development_start="2024-01-01", development_end="2024-01-31", timeframe="1D",
        signature_set_id="sigset_x", discovery_config_version="d1", evaluation_config_version="e1",
        bootstrap_seed=1, comparison_seed=2, security_ids=("a", "b"), benchmark_security_id="bench",
        data_as_of="2024-01-31", horizons=(1, 2, 3),
    )
    id_v2 = build_run_id(**common, run_id_scheme_version=RUN_ID_SCHEME_VERSION)
    id_other = build_run_id(**common, run_id_scheme_version="v1")
    assert id_v2 != id_other
