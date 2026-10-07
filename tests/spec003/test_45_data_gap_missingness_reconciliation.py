"""TEST 45 -- DATA_GAP is counted in MissingnessReport's own
reconciliation, through a REAL run_evaluation() call (joint remediation
design 003+004, section 1.3; decision registry B2; GPT review, Stage 2
changes-required round).

`_missingness_from_outcomes()` previously built a `MissingnessReport`
with no `data_gap` field at all -- once the calendar-aware path actually
feeds `compute_forward_outcome()` (TEST 44/engine.py fix), a DATA_GAP
outcome would have silently vanished from the report's own
reconciliation (`sum(every other field) == episodes` would no longer
hold). This test builds a real, minimal universe with ONE security
missing a bar on a date the shared CALENDAR still declares a session --
exactly the 4a case -- and runs it end-to-end through run_evaluation().
"""
import json

from data_foundation.adapters.yfinance_adapter import YFinanceAdapter, utc_now_iso
from data_foundation.calendar.admission import AdmissionRegistry, admit_source_via_operator_attestation
from data_foundation.calendar.contract import build_trading_calendar
from data_foundation.calendar.entities import CalendarSource
from data_foundation.calendar.registry import CalendarRegistry
from data_foundation.model import ingestion as ing
from data_foundation.storage.db import connect_and_init
from fixtures.fake_yfinance import make_ticker_factory
from fixtures.market_data import business_days, make_bars

from evaluation.models.entities import EvaluationSignatureDefinition
from evaluation.registry.signatures import freeze_signature_set
from evaluation.engine import run_evaluation


def test_data_gap_outcomes_are_counted_and_reconcile_through_the_engine(reduced_discovery_config, fast_evaluation_config):
    dates = business_days("2024-01-02", "2024-03-15")[:40]
    gap_date = dates[25]  # a real calendar session; GAPSEC has no bar here

    conn = connect_and_init(":memory:")
    now = utc_now_iso()
    bench_dataset = {
        "ticker": "SBENCH_T45", "info": {"quoteType": "EQUITY", "exchange": "SYNTH", "currency": "USD"},
        "bars": make_bars(dates[0], dates[-1], base_price=100.0, daily_drift=0.05), "splits": {}, "dividends": {},
    }
    gap_dataset = {
        "ticker": "GAPSEC_T45", "info": {"quoteType": "EQUITY", "exchange": "SYNTH", "currency": "USD"},
        "bars": make_bars(dates[0], dates[-1], base_price=50.0, daily_drift=0.02, skip_dates={gap_date}),
        "splits": {}, "dividends": {},
    }
    ticker_to_dataset = {"SBENCH_T45": bench_dataset, "GAPSEC_T45": gap_dataset}
    adapter = YFinanceAdapter(ticker_factory=make_ticker_factory(ticker_to_dataset))

    security_ids = {}
    for ticker, ds in ticker_to_dataset.items():
        sid = ing.new_security_id(f"t45:{ticker}")
        ing.ensure_security(conn, sid, adapter, ticker, now)
        start, end = ds["bars"][0]["date"], ds["bars"][-1]["date"]
        ing.ensure_symbol_history(conn, sid, ticker, start, None, "yfinance")
        ing.ingest_prices(conn, adapter, sid, ticker, start, end, now)
        security_ids[ticker] = sid
    benchmark_security_id = security_ids["SBENCH_T45"]
    gapsec_id = security_ids["GAPSEC_T45"]

    calendar = build_trading_calendar(
        source=CalendarSource.OFFICIAL_VERIFIED.value, calendar_identifier="TEST45_FIXTURE",
        calendar_version="v1", market="US_EQUITIES", timezone="America/New_York",
        coverage_start=dates[0], coverage_end=dates[-1], session_dates=tuple(dates),
        session_open_time="09:30", session_close_time="16:00",
        verified_by="radu", verified_at="2026-10-06T00:00:00Z",
    )
    admission_registry = AdmissionRegistry()
    raw = json.dumps({"session_dates": list(calendar.session_dates), "early_close_dates": []})
    admitted = admit_source_via_operator_attestation(
        registry=admission_registry, source_identifier="X", operator_name="radu", attested_at="2026-10-06T00:00:00Z",
        version="v1", publication_date=dates[0], coverage_start=calendar.coverage_start,
        coverage_end=calendar.coverage_end, market=calendar.market, timezone=calendar.timezone, raw_content=raw,
    )
    registry = CalendarRegistry()
    registry.register_verified(
        calendar, admission_registry, admitted.artifact_digest, verified_by="radu", verified_at="2026-10-06T00:00:00Z",
    )

    # Empty conditions -- matches EVERY Discovery observation regardless
    # of lane state, so every eligible session for GAPSEC_T45 produces
    # one episode-forming observation.
    sig = EvaluationSignatureDefinition(
        signature_id="MATCH_ALL", lane_conditions=(), reason_code_conditions=(), timeframe="1D",
        discovery_engine_version="v1.0.0", discovery_config_version=reduced_discovery_config.config_version,
        creation_mode="PRE_REGISTERED", created_before_outcome_evaluation=True,
    )
    sigset = freeze_signature_set([sig])

    from dataclasses import replace
    horizon_cfg = replace(fast_evaluation_config, data={**fast_evaluation_config.data, "horizons": {"unit": "BARS", "values": [5]}})

    profiles, _ = run_evaluation(
        conn, [gapsec_id], benchmark_security_id,
        dates[0], dates[-1], sigset, reduced_discovery_config, horizon_cfg,
        data_as_of=dates[-1], calendar_registry=registry, calendar_id=calendar.calendar_id,
    )

    assert profiles
    gap_profile = next(p for p in profiles if p.horizon_bars == 5)
    m = gap_profile.missingness
    assert m.data_gap >= 1, "sanity: the deliberately-skipped bar must actually produce a DATA_GAP outcome"
    assert (
        m.valid_outcomes + m.insufficient_future_data + m.crosses_locked_oos
        + m.missing_benchmark + m.invalid_input + m.data_gap == m.episodes
    ), "DATA_GAP outcomes must be counted exactly once in the reconciliation, never silently dropped"
