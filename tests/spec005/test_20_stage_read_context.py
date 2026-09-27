"""TEST 20 -- StageReadContext (Spec #005 v1.0 SS3/SS5/SS6/SS7, Batch 2
patch round 2).

Closes P1 findings #1 and #3 from the round-2 review: (1) a snapshot
built from successive unprotected reads can mix pre- and post-write
state across two connections; (3) a cache call taking a bare `(conn,
snapshot_id)` pair has nothing tying that string to `conn`'s actual live
state. `StageReadContext` holds one open SAVEPOINT across the snapshot
build AND every subsequent observation-cache call, and is the only way
to reach `ObservationCacheStore.get_or_compute()` at all.
"""
import sqlite3
import threading
import time
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
        pit_universe["benchmark_security_id"], pit_calendar,
    ) as ctx:
        assert ctx.manifest is not None
        assert ctx.manifest.max_as_of == PIT_FORMATION_END
        assert ctx.boundary.zone == FORMATION_SELECTION


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
            pit_universe["benchmark_security_id"], other_calendar,
        )


def test_context_rejects_a_benchmark_not_matching_the_plan(conn, pit_universe, pit_calendar, pit_research_plan):
    with pytest.raises(ValueError, match="does not match"):
        StageReadContext(
            conn, pit_research_plan, FORMATION_SELECTION, pit_universe["priced_security_ids"],
            pit_universe["sec_a"], pit_calendar,
        )


def test_get_or_compute_observations_outside_the_with_block_raises(conn, pit_universe, pit_calendar, pit_research_plan):
    ctx = StageReadContext(
        conn, pit_research_plan, FORMATION_SELECTION, pit_universe["priced_security_ids"],
        pit_universe["benchmark_security_id"], pit_calendar,
    )
    from discovery.config.loader import load_config
    with pytest.raises(RuntimeError, match="not open"):
        ctx.get_or_compute_observations(pit_universe["priced_security_ids"], PIT_FORMATION_END, load_config())


def test_get_or_compute_observations_reuses_across_repeated_calls(conn, pit_universe, pit_calendar, pit_research_plan):
    from discovery.config.loader import load_config
    config = load_config()
    with StageReadContext(
        conn, pit_research_plan, FORMATION_SELECTION, pit_universe["priced_security_ids"],
        pit_universe["benchmark_security_id"], pit_calendar,
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
        pit_universe["benchmark_security_id"], pit_calendar,
    ) as ctx:
        bad_observation = SimpleNamespace(security_id=pit_universe["sec_a"], as_of="1999-01-01")
        with patch("backtest.data.cache.compute_discovery_observations", return_value=[bad_observation]):
            with pytest.raises(AssertionError, match="as_of"):
                ctx.get_or_compute_observations(pit_universe["priced_security_ids"], PIT_FORMATION_END, config)


def test_stage_read_context_holds_one_consistent_transaction_across_two_real_connections(tmp_path):
    """The genuine multi-connection version of "concurrent ingestion
    cannot mix states" (SS23): a SECOND, independent connection to the
    SAME file attempts to commit a write while this context's SAVEPOINT
    is still open. Verified empirically before writing this fix (see
    patch notes): SQLite blocks that writer's COMMIT until our SAVEPOINT
    releases, so every read taken through this context -- both the
    snapshot built at __enter__ and a second snapshot built later, still
    inside the same `with` block -- observes the identical, unchanging
    database state."""
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

    ctx = StageReadContext(conn, plan, FORMATION_SELECTION, (sec_a,), benchmark, calendar)
    ctx.__enter__()
    try:
        writer_result = {}

        def writer():
            # A generous busy-timeout: the writer should simply wait,
            # retrying, for as long as our SAVEPOINT stays open, and
            # succeed once we release it -- not give up early.
            writer_conn = sqlite3.connect(db_path, timeout=10.0)
            try:
                writer_conn.execute(
                    "UPDATE price_history SET raw_close = 999999.0 WHERE security_id = ? "
                    "AND date = ? AND source_provider = 'manual'",
                    (sec_a, PIT_FORMATION_END),
                )
                writer_conn.commit()
                writer_result["status"] = "committed"
            except sqlite3.OperationalError as e:
                writer_result["status"] = f"blocked: {e}"
            writer_conn.close()

        t = threading.Thread(target=writer)
        t.start()
        time.sleep(0.3)
        assert t.is_alive(), "the concurrent writer should still be blocked by our open SAVEPOINT"

        from backtest.data.snapshot import build_data_snapshot
        second_manifest = build_data_snapshot(ctx._bounded_access, (sec_a,), benchmark, calendar)
        assert second_manifest.snapshot_id == ctx.manifest.snapshot_id

        # Still holding the SAVEPOINT -- the writer must still be
        # waiting, never having slipped a change in.
        assert t.is_alive(), "the writer must still be blocked while our SAVEPOINT is open"
    finally:
        ctx.__exit__(None, None, None)

    t.join(timeout=5)
    assert writer_result["status"] == "committed"
    conn.close()
