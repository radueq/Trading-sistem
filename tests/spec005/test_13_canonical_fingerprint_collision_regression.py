"""TEST 13 -- canonical JSON fingerprints reject the exact delimiter
collisions the old hand-rolled `"::"`/`","`-joined strings had (Spec
#005 v1.0 SS21, Batch 1 patch, GPT review P1 finding #2).

Old recipe: `dates_part = ",".join(sorted(session_dates))`. Two
STRUCTURALLY different inputs -- a single free-text string containing an
embedded comma, versus a list of two separate strings split at that same
comma -- serialize to the IDENTICAL joined string, so the old fingerprint
could not tell them apart. `research_plan_fingerprint()`'s
`exposure_part` had the same collision over `prior_validation_disclosures`.
The new `_canonical_json()`-based recipes keep each value in its own
structured JSON array element, so this collision is now impossible.
"""
from backtest.models.entities import CostAssumptions, ExposureManifest, SelectionFold, SelectionRule, calendar_fingerprint, research_plan_fingerprint

_CAL_BASE = dict(
    source="OFFICIAL_VERIFIED", calendar_identifier="X", calendar_version="v1", market="US_EQUITIES",
    timezone="America/New_York", coverage_start="2024-01-01", coverage_end="2024-01-31",
    session_open_time="09:30", session_close_time="16:00", early_close_dates=(),
)


def test_a_single_comma_embedded_session_date_no_longer_collides_with_two_split_dates():
    """The exact collision: sorted(("2024-01-02,2024-01-03",)) joined by
    "," equals sorted(("2024-01-02", "2024-01-03")) joined by ",\" --
    both produce the literal string "2024-01-02,2024-01-03" under the
    old recipe."""
    fp_one_merged_string = calendar_fingerprint(session_dates=("2024-01-02,2024-01-03",), **_CAL_BASE)
    fp_two_separate_dates = calendar_fingerprint(session_dates=("2024-01-02", "2024-01-03"), **_CAL_BASE)
    assert fp_one_merged_string != fp_two_separate_dates


def _plan_fp(exposure: ExposureManifest) -> str:
    return research_plan_fingerprint(
        formation_start="2020-01-01", formation_end="2024-01-01", validation_start="2024-02-01",
        validation_end="2024-12-31", locked_oos_start="2025-01-01",
        selection_folds=(SelectionFold("fold_1", "2020-01-01", "2021-01-01"),),
        hypothesis_cohort_ids=("hyp_a",), trading_calendar_id="cal_abc", benchmark_security_id="SBENCH",
        execution_semantics_profile_id="exsem_abc",
        selection_rule=SelectionRule(minimum_executed_trades=30, minimum_evaluable_trades=25, minimum_evaluable_ratio=0.8),
        cost_assumptions=CostAssumptions(
            commission_entry_rate=0.0005, commission_exit_rate=0.0005,
            slippage_entry_bps=5.0, slippage_exit_bps=5.0, borrow_annual_rate=0.0,
        ),
        exposure_manifest=exposure,
    )


def test_a_single_comma_embedded_disclosure_no_longer_collides_with_two_split_disclosures():
    """Same collision, reproduced in `research_plan_fingerprint()`'s
    exposure_manifest disclosure-list encoding."""
    fp_one_merged_disclosure = _plan_fp(ExposureManifest(declared_unseen=False, prior_validation_disclosures=("saw run A,saw run B",)))
    fp_two_separate_disclosures = _plan_fp(ExposureManifest(declared_unseen=False, prior_validation_disclosures=("saw run A", "saw run B")))
    assert fp_one_merged_disclosure != fp_two_separate_disclosures
