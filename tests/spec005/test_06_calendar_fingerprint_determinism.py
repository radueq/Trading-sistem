"""TEST 6 -- calendar content-address determinism (Spec #005 v1.0
SS11/SS21, Batch 1). Same economic content -> same calendar_id, always;
a changed economic field -> a different id; administrative provenance
(verified_by/verified_at) is excluded, mirroring #004's own
`created_at`/`approved_at` exclusion discipline."""
from backtest.data.calendar import build_trading_calendar
from backtest.models.entities import CalendarSource

_BASE = dict(
    source=CalendarSource.OFFICIAL_VERIFIED.value, calendar_identifier="NYSE_NASDAQ_COMPOSITE",
    calendar_version="v1", market="US_EQUITIES", timezone="America/New_York",
    coverage_start="2024-01-01", coverage_end="2024-01-31",
    session_dates=("2024-01-02", "2024-01-03", "2024-01-04"),
    session_open_time="09:30", session_close_time="16:00",
)


def test_identical_inputs_produce_the_identical_id():
    a = build_trading_calendar(**_BASE, verified_by="radu", verified_at="t1")
    b = build_trading_calendar(**_BASE, verified_by="radu", verified_at="t1")
    assert a.calendar_id == b.calendar_id
    assert a.calendar_hash == b.calendar_hash


def test_verification_provenance_does_not_affect_the_hash():
    a = build_trading_calendar(**_BASE, verified_by="radu", verified_at="2026-01-01")
    b = build_trading_calendar(**_BASE, verified_by="someone_else", verified_at="2027-06-15")
    assert a.calendar_id == b.calendar_id


def test_different_session_dates_produce_a_different_id():
    a = build_trading_calendar(**_BASE)
    changed = dict(_BASE, session_dates=("2024-01-02", "2024-01-03"))  # dropped one date
    b = build_trading_calendar(**changed)
    assert a.calendar_id != b.calendar_id


def test_session_dates_input_order_does_not_affect_the_id():
    """SS21: "Stable ordering must not depend on... insertion order." """
    a = build_trading_calendar(**_BASE)
    reordered = dict(_BASE, session_dates=tuple(reversed(_BASE["session_dates"])))
    b = build_trading_calendar(**reordered)
    assert a.calendar_id == b.calendar_id


def test_synthetic_source_with_identical_dates_is_a_different_calendar_identity():
    """A synthetic fixture calendar with the EXACT same dates as a real
    one must never be interchangeable with it -- source participates in
    the fingerprint on purpose (mirrors PATCH #004-A's
    HorizonCandidateSet.parameter_source discipline)."""
    verified = build_trading_calendar(**_BASE)
    synthetic = dict(_BASE)
    synthetic["source"] = CalendarSource.SYNTHETIC_TEST_FIXTURE.value
    synthetic_calendar = build_trading_calendar(**synthetic)
    assert verified.calendar_id != synthetic_calendar.calendar_id


def test_coverage_window_participates_in_the_fingerprint():
    a = build_trading_calendar(**_BASE)
    changed = dict(_BASE, coverage_end="2024-12-31")
    b = build_trading_calendar(**changed)
    assert a.calendar_id != b.calendar_id
