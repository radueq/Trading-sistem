"""TEST 20 -- StageReadContext (Spec #005 v1.0 SS3/SS5/SS6/SS7, Batch 2
patch round 4).

`StageReadContext` extracts a strictly-authorized, read-only subset from
its source connection at `__enter__()` time and is the only way to reach
`_ObservationCacheStore.get_or_compute()` at all -- `ctx.conn` IS that
subset, for the entire time the context is open, never the source
connection (see `backtest.data.context`'s module docstring for the full
round-4 redesign).
"""
import sqlite3
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from data_foundation.storage.db import connect_and_init
from fixtures.market_data import business_days

from backtest.data.calendar import build_trading_calendar
from backtest.data.context import StageReadContext
from backtest.models.entities import (
    CalendarSource,
    CostAssumptions,
    ExposureManifest,
    FORMATION_SELECTION,
    ResearchPlan,
    SelectionFold,
    SelectionRule,
    build_execution_semantics_profile_v1,
    build_research_plan_id,
    research_plan_fingerprint,
)

from spec005.conftest import (
    PIT_FORMATION_END,
    PIT_FORMATION_START,
    PIT_LOCKED_OOS_START,
    PIT_UNIVERSE_END,
    PIT_VALIDATION_END,
    PIT_VALIDATION_START,
    PIT_WARMUP_START,
)
from spec005.fixtures.pit_universe import insert_price_history, make_security


def test_context_opens_and_builds_a_manifest(conn, pit_universe, pit_calendar, pit_research_plan):
    with StageReadContext(
        conn, pit_research_plan, FORMATION_SELECTION, pit_universe["priced_security_ids"],
        pit_universe["benchmark_security_id"], pit_calendar, PIT_WARMUP_START,
    ) as ctx:
        assert ctx.manifest is not None
        assert ctx.manifest.max_as_of == PIT_FORMATION_END
        assert ctx.manifest.min_as_of == PIT_WARMUP_START
        assert ctx.boundary.zone == FORMATION_SELECTION
        assert ctx.conn is not None


def test_context_rejects_a_calendar_not_matching_the_plans_own_calendar_id(conn, pit_universe, pit_calendar, pit_research_plan):
    other_calendar = build_trading_calendar(
        source=CalendarSource.OFFICIAL_VERIFIED.value, calendar_identifier="A_DIFFERENT_CALENDAR",
        calendar_version="v1", market="US_EQUITIES", timezone="America/New_York",
        coverage_start=PIT_WARMUP_START, coverage_end=PIT_UNIVERSE_END,
        session_dates=pit_calendar.session_dates, session_open_time="09:30", session_close_time="16:00",
        verified_by="test", verified_at="2026-09-27T00:00:00Z",
    )
    with pytest.raises(ValueError, match="does not match"):
        StageReadContext(
            conn, pit_research_plan, FORMATION_SELECTION, pit_universe["priced_security_ids"],
            pit_universe["benchmark_security_id"], other_calendar, PIT_WARMUP_START,
        )


def test_context_rejects_a_benchmark_not_matching_the_plan(conn, pit_universe, pit_calendar, pit_research_plan):
    with pytest.raises(ValueError, match="does not match"):
        StageReadContext(
            conn, pit_research_plan, FORMATION_SELECTION, pit_universe["priced_security_ids"],
            pit_universe["sec_a"], pit_calendar, PIT_WARMUP_START,
        )


def test_context_rejects_a_warmup_start_after_the_zones_own_start(conn, pit_universe, pit_calendar, pit_research_plan):
    """Batch 2 patch round-4 review, finding #3: warm-up, by definition,
    precedes (or coincides with) the zone it prepares."""
    with pytest.raises(ValueError, match="must not be after"):
        StageReadContext(
            conn, pit_research_plan, FORMATION_SELECTION, pit_universe["priced_security_ids"],
            pit_universe["benchmark_security_id"], pit_calendar, "2024-01-15",
        )


def test_context_rejects_a_warmup_start_the_calendar_never_covers(conn, pit_universe, pit_calendar, pit_research_plan):
    """Finding #3: the calendar must cover `[warmup_start, max_as_of]`,
    not merely `[zone_start, max_as_of]` -- a `warmup_start` earlier than
    the calendar's own declared `coverage_start` must be rejected before
    anything is read."""
    from backtest.models.entities import CalendarCoverageIncompleteError

    with pytest.raises(CalendarCoverageIncompleteError):
        StageReadContext(
            conn, pit_research_plan, FORMATION_SELECTION, pit_universe["priced_security_ids"],
            pit_universe["benchmark_security_id"], pit_calendar, "2023-01-01",
        )


def test_get_or_compute_observations_outside_the_with_block_raises(conn, pit_universe, pit_calendar, pit_research_plan):
    ctx = StageReadContext(
        conn, pit_research_plan, FORMATION_SELECTION, pit_universe["priced_security_ids"],
        pit_universe["benchmark_security_id"], pit_calendar, PIT_WARMUP_START,
    )
    from discovery.config.loader import load_config
    with pytest.raises(RuntimeError, match="not open"):
        ctx.get_or_compute_observations(pit_universe["priced_security_ids"], PIT_FORMATION_END, load_config())


def test_get_or_compute_observations_reuses_across_repeated_calls(conn, pit_universe, pit_calendar, pit_research_plan):
    from discovery.config.loader import load_config
    config = load_config()
    with StageReadContext(
        conn, pit_research_plan, FORMATION_SELECTION, pit_universe["priced_security_ids"],
        pit_universe["benchmark_security_id"], pit_calendar, PIT_WARMUP_START,
    ) as ctx:
        entry_a = ctx.get_or_compute_observations(pit_universe["priced_security_ids"], PIT_FORMATION_END, config)
        entry_b = ctx.get_or_compute_observations(pit_universe["priced_security_ids"], PIT_FORMATION_END, config)
        assert entry_a is entry_b
        assert entry_a.snapshot_id == ctx.manifest.snapshot_id


def test_discovery_returning_a_mismatched_as_of_is_caught(conn, pit_universe, pit_calendar, pit_research_plan):
    """Supervises Discovery's own indirect PIT reads (SS7): if
    compute_discovery_observations() ever violated its own as_of
    contract, the context must fail loudly rather than silently cache a
    result that doesn't correspond to the requested session."""
    from discovery.config.loader import load_config
    config = load_config()
    with StageReadContext(
        conn, pit_research_plan, FORMATION_SELECTION, pit_universe["priced_security_ids"],
        pit_universe["benchmark_security_id"], pit_calendar, PIT_WARMUP_START,
    ) as ctx:
        bad_observation = SimpleNamespace(security_id=pit_universe["sec_a"], as_of="1999-01-01")
        with patch("backtest.data.cache.compute_discovery_observations", return_value=[bad_observation]):
            with pytest.raises(AssertionError, match="as_of"):
                ctx.get_or_compute_observations(pit_universe["priced_security_ids"], PIT_FORMATION_END, config)


def test_writing_via_the_context_own_connection_is_blocked_while_open(conn, pit_universe, pit_calendar, pit_research_plan):
    """`ctx.conn` is the authorized subset, read-only for the whole time
    the context is open (round-4 review, finding #2's first half: the
    round-3 patch protected the SOURCE connection but left the connection
    actually handed to Discovery -- the subset -- writable)."""
    sid = pit_universe["sec_a"]
    with StageReadContext(
        conn, pit_research_plan, FORMATION_SELECTION, pit_universe["priced_security_ids"],
        pit_universe["benchmark_security_id"], pit_calendar, PIT_WARMUP_START,
    ) as ctx:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            ctx.conn.execute(
                "UPDATE price_history SET raw_close = 12345.0 WHERE security_id = ? AND date = ? "
                "AND source_provider = 'manual'",
                (sid, PIT_FORMATION_END),
            )

    # The SOURCE connection was only ever forced read-only during the
    # brief extraction step inside __enter__() -- restored immediately
    # after, long before this write, regardless of the context's own
    # open/closed state (round-4 review, finding #2's second half: never
    # unconditionally forced OFF, but restored to whatever it was).
    conn.execute(
        "UPDATE price_history SET raw_close = 12345.0 WHERE security_id = ? AND date = ? "
        "AND source_provider = 'manual'",
        (sid, PIT_FORMATION_END),
    )
    conn.commit()


def test_context_hands_discovery_a_connection_with_out_of_scope_prices_physically_absent(
    conn, pit_universe, pit_calendar, pit_research_plan,
):
    """Supervising Discovery's own indirect PIT reads by checking only
    the RETURNED as_of label cannot catch a substitute that reads
    out-of-scope data internally and reports an honest label anyway.
    `get_or_compute_observations()` must hand Discovery a connection
    where rows beyond `boundary.max_as_of` are not merely unqueried but
    PHYSICALLY ABSENT -- so even a hostile substitute has nothing to
    read, regardless of what label it would report."""
    from discovery.config.loader import load_config

    captured = {}

    def fake_compute(conn_arg, security_ids, as_of, benchmark_security_id, discovery_config):
        captured["conn"] = conn_arg
        return []

    with StageReadContext(
        conn, pit_research_plan, FORMATION_SELECTION, pit_universe["priced_security_ids"],
        pit_universe["benchmark_security_id"], pit_calendar, PIT_WARMUP_START,
    ) as ctx:
        with patch("backtest.data.cache.compute_discovery_observations", side_effect=fake_compute):
            ctx.get_or_compute_observations(pit_universe["priced_security_ids"], PIT_FORMATION_END, load_config())

        subset_conn = captured["conn"]
        assert subset_conn is not conn  # never the raw stage connection
        assert subset_conn is ctx.conn
        cur = subset_conn.execute(
            "SELECT COUNT(*) FROM price_history WHERE security_id = ? AND date > ?",
            (pit_universe["sec_a"], PIT_FORMATION_END),
        )
        assert cur.fetchone()[0] == 0

    # The same rows are genuinely present in the raw stage connection --
    # this is real physical isolation, not an artifact of empty fixture
    # data (pit_universe's price history runs through PIT_UNIVERSE_END,
    # well past PIT_FORMATION_END).
    cur = conn.execute(
        "SELECT COUNT(*) FROM price_history WHERE security_id = ? AND date > ?",
        (pit_universe["sec_a"], PIT_FORMATION_END),
    )
    assert cur.fetchone()[0] > 0


def test_subset_excludes_a_security_outside_the_authorized_universe(conn, pit_universe, pit_calendar, pit_research_plan):
    """Round-4 review, finding #1 (concrete probe: "Prețurile unui
    security din afara universului rămân prezente"): only rows for the
    declared universe + benchmark are ever copied into the subset --
    `sec_nodata` (never passed to the context) must be entirely absent,
    not merely unreachable through some other filter."""
    with StageReadContext(
        conn, pit_research_plan, FORMATION_SELECTION, pit_universe["priced_security_ids"],
        pit_universe["benchmark_security_id"], pit_calendar, PIT_WARMUP_START,
    ) as ctx:
        cur = ctx.conn.execute(
            "SELECT COUNT(*) FROM security_master WHERE security_id = ?", (pit_universe["sec_nodata"],),
        )
        assert cur.fetchone()[0] == 0


def test_subset_excludes_a_corporate_action_not_yet_knowable_by_max_as_of(
    conn, pit_universe, pit_calendar, pit_research_plan,
):
    """Round-4 review, finding #1 (concrete probe: "O acțiune corporativă
    cu `available_at` ulterior limitei rămâne prezentă"): the subset's
    own `corporate_actions` table must exclude a row whose knowledge-time
    signal is after `max_as_of`, not merely rely on #001's own PIT
    function to filter it out downstream."""
    from spec005.fixtures.pit_universe import insert_corporate_action

    sid = pit_universe["sec_a"]
    insert_corporate_action(
        conn, sid, action_id="future_split", action_type="SPLIT", effective_date=PIT_FORMATION_END,
        value=2.0, now="2026-09-27T00:00:00Z", available_at="2024-06-01",  # well after PIT_FORMATION_END
    )
    with StageReadContext(
        conn, pit_research_plan, FORMATION_SELECTION, pit_universe["priced_security_ids"],
        pit_universe["benchmark_security_id"], pit_calendar, PIT_WARMUP_START,
    ) as ctx:
        cur = ctx.conn.execute("SELECT COUNT(*) FROM corporate_actions WHERE action_id = ?", ("future_split",))
        assert cur.fetchone()[0] == 0

    cur = conn.execute("SELECT COUNT(*) FROM corporate_actions WHERE action_id = ?", ("future_split",))
    assert cur.fetchone()[0] == 1  # genuinely present in the source -- proves this isn't vacuous


def _pit_status_for_action(conn, security_id: str, action_id: str, as_of: str):
    from data_foundation.pit.access import get_corporate_actions_as_of
    for pit_action in get_corporate_actions_as_of(conn, security_id, as_of):
        if pit_action.action.action_id == action_id:
            return pit_action.pit_status, pit_action.knowledge_time_status
    return None


def test_subset_retains_a_cancellation_known_via_source_status_date_alone(
    conn, pit_universe, pit_calendar, pit_research_plan,
):
    """Batch 2 patch round-5 review (P1 finding): in #001,
    `derive_corporate_action_pit_status()` reports CANCELLED the moment
    `source_status_date <= as_of`, INDEPENDENTLY of `available_at` -- the
    round-4 subset filter checked only `available_at`/`effective_date`
    and dropped this row entirely, even though #001 itself would have
    reported it CANCELLED/KNOWN. `available_at` is NULL here and
    `effective_date` is still in the future -- only the CANCELLED branch
    keeps this row in the subset."""
    from spec005.fixtures.pit_universe import insert_corporate_action

    sid = pit_universe["sec_a"]
    insert_corporate_action(
        conn, sid, action_id="cancelled_split_1", action_type="SPLIT", effective_date="2024-02-15",
        value=2.0, now="2026-09-27T00:00:00Z", available_at=None,
        source_status="CANCELLED", source_status_date="2024-01-20",
    )
    expected = _pit_status_for_action(conn, sid, "cancelled_split_1", PIT_FORMATION_END)
    assert expected == ("CANCELLED", "KNOWN")

    with StageReadContext(
        conn, pit_research_plan, FORMATION_SELECTION, pit_universe["priced_security_ids"],
        pit_universe["benchmark_security_id"], pit_calendar, PIT_WARMUP_START,
    ) as ctx:
        cur = ctx.conn.execute("SELECT COUNT(*) FROM corporate_actions WHERE action_id = ?", ("cancelled_split_1",))
        assert cur.fetchone()[0] == 1
        actual = _pit_status_for_action(ctx.conn, sid, "cancelled_split_1", PIT_FORMATION_END)
        assert actual == expected


def test_subset_retains_a_cancellation_known_via_source_status_date_with_available_at_set(
    conn, pit_universe, pit_calendar, pit_research_plan,
):
    """Same case, but `available_at` is also set (to a date AFTER
    `max_as_of`) -- #001's own CANCELLED check runs BEFORE its
    `available_at` check, so the result is unchanged; the subset filter
    must reach the same answer via its OR branch, not the `available_at`
    fallback (which alone would have excluded this row)."""
    from spec005.fixtures.pit_universe import insert_corporate_action

    sid = pit_universe["sec_a"]
    insert_corporate_action(
        conn, sid, action_id="cancelled_split_2", action_type="SPLIT", effective_date="2024-02-15",
        value=2.0, now="2026-09-27T00:00:00Z", available_at="2024-02-01",
        source_status="CANCELLED", source_status_date="2024-01-20",
    )
    expected = _pit_status_for_action(conn, sid, "cancelled_split_2", PIT_FORMATION_END)
    assert expected == ("CANCELLED", "KNOWN")

    with StageReadContext(
        conn, pit_research_plan, FORMATION_SELECTION, pit_universe["priced_security_ids"],
        pit_universe["benchmark_security_id"], pit_calendar, PIT_WARMUP_START,
    ) as ctx:
        cur = ctx.conn.execute("SELECT COUNT(*) FROM corporate_actions WHERE action_id = ?", ("cancelled_split_2",))
        assert cur.fetchone()[0] == 1
        actual = _pit_status_for_action(ctx.conn, sid, "cancelled_split_2", PIT_FORMATION_END)
        assert actual == expected


def test_subset_still_excludes_a_cancellation_not_yet_knowable(conn, pit_universe, pit_calendar, pit_research_plan):
    """The new OR branch must not turn into a blanket pass-through:
    a cancellation whose OWN `source_status_date` is still in the
    future (and whose `available_at`/`effective_date` are too) must
    remain excluded -- #001 itself would report NOT_KNOWN for it."""
    from spec005.fixtures.pit_universe import insert_corporate_action

    sid = pit_universe["sec_a"]
    insert_corporate_action(
        conn, sid, action_id="not_yet_known_cancellation", action_type="SPLIT", effective_date="2024-02-15",
        value=2.0, now="2026-09-27T00:00:00Z", available_at=None,
        source_status="CANCELLED", source_status_date="2024-06-01",
    )
    assert _pit_status_for_action(conn, sid, "not_yet_known_cancellation", PIT_FORMATION_END) is None

    with StageReadContext(
        conn, pit_research_plan, FORMATION_SELECTION, pit_universe["priced_security_ids"],
        pit_universe["benchmark_security_id"], pit_calendar, PIT_WARMUP_START,
    ) as ctx:
        cur = ctx.conn.execute(
            "SELECT COUNT(*) FROM corporate_actions WHERE action_id = ?", ("not_yet_known_cancellation",),
        )
        assert cur.fetchone()[0] == 0

    cur = conn.execute("SELECT COUNT(*) FROM corporate_actions WHERE action_id = ?", ("not_yet_known_cancellation",))
    assert cur.fetchone()[0] == 1  # genuinely present in the source -- proves this isn't vacuous


def test_a_write_on_the_source_after_entry_never_reaches_the_context(tmp_path):
    """Round-4 redesign: `StageReadContext` no longer holds the SOURCE
    connection's SAVEPOINT open for its whole lifetime -- extraction into
    an authorized subset is a one-shot, bounded step (see
    `backtest.data.context`'s module docstring). The relevant guarantee
    is not "the source's SAVEPOINT blocks a concurrent writer for as long
    as the context is open" (GPT's own round-2 correction: the relevant
    guarantee is read STABILITY, never mandatory writer-blocking) -- it
    is that a write to the SOURCE, on a SEPARATE connection, made AFTER
    `__enter__()` has already returned, has NO EFFECT WHATSOEVER on this
    context, because everything from that point on reads exclusively
    from the isolated subset copy, never the source again."""
    db_path = str(tmp_path / "spec005_isolation.db")
    conn = connect_and_init(db_path)
    now = "2026-09-27T00:00:00Z"
    sec_a = make_security(conn, "test20:SEC_A", now)
    benchmark = make_security(conn, "test20:BENCH", now)
    insert_price_history(conn, sec_a, now, PIT_WARMUP_START, PIT_UNIVERSE_END, base_price=100.0)
    insert_price_history(conn, benchmark, now, PIT_WARMUP_START, PIT_UNIVERSE_END, base_price=200.0)

    session_dates = tuple(business_days(PIT_WARMUP_START, PIT_UNIVERSE_END))
    calendar = build_trading_calendar(
        source=CalendarSource.OFFICIAL_VERIFIED.value, calendar_identifier="TEST20_CALENDAR",
        calendar_version="v1", market="US_EQUITIES", timezone="America/New_York",
        coverage_start=PIT_WARMUP_START, coverage_end=PIT_UNIVERSE_END, session_dates=session_dates,
        session_open_time="09:30", session_close_time="16:00", verified_by="test", verified_at=now,
    )
    profile = build_execution_semantics_profile_v1()
    rule = SelectionRule(minimum_executed_trades=1, minimum_evaluable_trades=1, minimum_evaluable_ratio=0.5)
    costs = CostAssumptions(
        commission_entry_rate=0.0005, commission_exit_rate=0.0005,
        slippage_entry_bps=5.0, slippage_exit_bps=5.0, borrow_annual_rate=0.0,
    )
    exposure = ExposureManifest(declared_unseen=True)
    folds = (SelectionFold("fold_1", PIT_FORMATION_START, PIT_FORMATION_END),)
    fields = dict(
        formation_start=PIT_FORMATION_START, formation_end=PIT_FORMATION_END,
        validation_start=PIT_VALIDATION_START, validation_end=PIT_VALIDATION_END,
        locked_oos_start=PIT_LOCKED_OOS_START, selection_folds=folds,
        hypothesis_cohort_ids=("hyp_a",), trading_calendar_id=calendar.calendar_id,
        benchmark_security_id=benchmark, execution_semantics_profile_id=profile.profile_id,
        selection_rule=rule, cost_assumptions=costs, exposure_manifest=exposure,
    )
    fp = research_plan_fingerprint(**fields)
    plan_id, plan_hash = build_research_plan_id(fp)
    plan = ResearchPlan(research_plan_id=plan_id, plan_hash=plan_hash, created_at=now, created_by="test", **fields)

    ctx = StageReadContext(conn, plan, FORMATION_SELECTION, (sec_a,), benchmark, calendar, PIT_WARMUP_START)
    ctx.__enter__()
    try:
        manifest_before = ctx.manifest

        # A write on a SEPARATE connection to the SAME source file,
        # after entry has already completed, succeeds immediately --
        # nothing holds the source's SAVEPOINT open any more.
        writer_conn = sqlite3.connect(db_path, timeout=10.0)
        writer_conn.execute(
            "UPDATE price_history SET raw_close = 999999.0 WHERE security_id = ? "
            "AND date = ? AND source_provider = 'manual'",
            (sec_a, PIT_FORMATION_END),
        )
        writer_conn.commit()
        writer_conn.close()

        # ...and it has NO effect on this context: re-building the
        # snapshot from ctx.conn (the subset, never the source) is
        # identical, because ctx.conn never saw that write at all.
        from backtest.data.pit_access import BoundedPITAccess
        from backtest.data.snapshot import build_data_snapshot
        second_manifest = build_data_snapshot(
            BoundedPITAccess(ctx.conn, ctx.boundary), (sec_a,), benchmark, calendar, PIT_WARMUP_START,
        )
        assert second_manifest.snapshot_id == manifest_before.snapshot_id

        cur = ctx.conn.execute(
            "SELECT raw_close FROM price_history WHERE security_id = ? AND date = ? AND source_provider = 'manual'",
            (sec_a, PIT_FORMATION_END),
        )
        assert cur.fetchone()[0] != 999999.0
    finally:
        ctx.__exit__(None, None, None)
    conn.close()
