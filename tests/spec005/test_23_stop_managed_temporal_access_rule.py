"""TEST 23 -- the explicit temporal-access-at-open rule (docs/spec005_
exit_amendment_v1.0.md, ACCEPTED, section 3): a date-only knowledge-time
gate cannot distinguish morning from afternoon, so same-day availability
requires EXPLICIT additional evidence beyond the bare date, defaulting to
NOT authorized. Applies identically to initial protection and to Pas 0's
reconciliation of already-open positions (section 6) -- both call this
exact same function."""
from backtest.exits.protection import is_authorized_at_open


def test_strictly_before_session_date_auto_authorizes():
    assert is_authorized_at_open("2024-01-10", "2024-01-11") is True


def test_same_day_without_evidence_is_not_authorized():
    assert is_authorized_at_open("2024-01-11", "2024-01-11") is False
    assert is_authorized_at_open("2024-01-11", "2024-01-11", known_before_open_same_day=False) is False


def test_same_day_with_explicit_evidence_is_authorized():
    assert is_authorized_at_open("2024-01-11", "2024-01-11", known_before_open_same_day=True) is True


def test_effective_date_after_session_date_is_never_authorized():
    """Not a case the callers above actually reach (both only invoke this
    for actions #001 already reports as date-effective), but the
    function itself must never silently authorize a future effective
    date regardless of the evidence flag."""
    assert is_authorized_at_open("2024-01-12", "2024-01-11", known_before_open_same_day=True) is False
