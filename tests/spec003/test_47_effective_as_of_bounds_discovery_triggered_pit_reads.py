"""TEST 47 -- `effective_as_of` bounds EVERY PIT read this run performs,
including the ones Discovery triggers indirectly through
`_collect_observations()` (joint remediation design 003+004, section
1.3; decision registry B1; GPT review, Stage 2 second changes-required
round).

GPT's own reproduction: `_resolve_session_dates_from_calendar()`
filtered its returned session list by `development_end` only, never
by `effective_as_of` -- whenever `data_as_of < development_end`, that
list could still include calendar sessions AFTER the caller's own
declared vantage point. `_collect_observations()` then called
Discovery once PER DATE in that list, and Discovery performs its OWN
PIT reads as of each one -- a historical run could read data later
than its own `data_as_of`, even though every DIRECT bar fetch in
`engine.py` was already correctly bounded.

This test intercepts `data_foundation.pit.access.get_price_series_as_of`
itself (both `evaluation.engine` and `discovery.engine` import and call
through the SAME module object, so one patch point sees every read
either module performs) and asserts NONE of them ever requests a date
after `effective_as_of`, while confirming CROSSES_LOCKED_OOS and
INSUFFICIENT_FUTURE_DATA classification -- which depend on the FULL,
untruncated calendar passed separately into `compute_forward_outcome()`
-- still work correctly.
"""
import data_foundation.pit.access as pit_access
from evaluation.engine import run_evaluation
from evaluation.models.entities import EvaluationSignatureDefinition, LaneStateCondition, OutcomeStatus
from evaluation.registry.signatures import freeze_signature_set

from spec003.fixtures.tiny_universe import DATES


def test_effective_as_of_bounds_every_pit_read_including_discovery_triggered_ones(
    conn, tiny_universe, reduced_discovery_config, fast_evaluation_config, formal_calendar_registry, formal_calendar_id,
    monkeypatch,
):
    dev_start, dev_end = DATES[30], DATES[50]
    data_as_of = DATES[36]  # strictly BEFORE development_end -- the exact scenario GPT's own reproduction used
    assert data_as_of < dev_end, "sanity: this test only means something when data_as_of < development_end"

    seen_as_of: list[str] = []
    real_get_price_series_as_of = pit_access.get_price_series_as_of

    def _spying_get_price_series_as_of(conn_, security_id, as_of):
        seen_as_of.append(as_of)
        return real_get_price_series_as_of(conn_, security_id, as_of)

    monkeypatch.setattr(pit_access, "get_price_series_as_of", _spying_get_price_series_as_of)

    from dataclasses import replace
    # Two horizons from the SAME entry window: one lands inside
    # development (but past data_as_of -> INSUFFICIENT_FUTURE_DATA),
    # one lands past development_end -> CROSSES_LOCKED_OOS.
    two_horizon_cfg = replace(fast_evaluation_config, data={
        **fast_evaluation_config.data, "horizons": {"unit": "BARS", "values": [5, 20]},
    })

    sig = EvaluationSignatureDefinition(
        signature_id="VOLATILITY_EXTREME_COMPRESSION", lane_conditions=(LaneStateCondition("volatility", "EXTREME_COMPRESSION"),),
        reason_code_conditions=(), timeframe="1D", discovery_engine_version="v1.0.0",
        discovery_config_version=reduced_discovery_config.config_version, creation_mode="PRE_REGISTERED",
        created_before_outcome_evaluation=True,
    )
    sigset = freeze_signature_set([sig])

    profiles, _ = run_evaluation(
        conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
        dev_start, dev_end, sigset, reduced_discovery_config, two_horizon_cfg,
        data_as_of=data_as_of, calendar_registry=formal_calendar_registry, calendar_id=formal_calendar_id,
    )

    # 1. No PIT read -- direct OR Discovery-triggered -- ever asked for
    # a date after effective_as_of (== data_as_of here, since
    # data_as_of < development_end).
    assert seen_as_of, "sanity: this run must have actually performed PIT reads"
    offending = [d for d in seen_as_of if d > data_as_of]
    assert not offending, (
        f"PIT reads requested dates past effective_as_of={data_as_of!r}: {sorted(set(offending))!r} -- "
        f"the historical boundary was violated"
    )

    # 2. Target-session classification, which depends on the calendar's
    # OWN full, untruncated session_dates (passed separately into
    # compute_forward_outcome()), still works correctly: the short
    # horizon (5) lands inside development but past data_as_of
    # (INSUFFICIENT_FUTURE_DATA); the long horizon (20) lands past
    # development_end (CROSSES_LOCKED_OOS).
    by_horizon = {p.horizon_bars: p for p in profiles}
    assert any(by_horizon[5].missingness.insufficient_future_data > 0 for _ in [0]), (
        "sanity: horizon=5 should produce at least one INSUFFICIENT_FUTURE_DATA outcome"
    )
    assert any(by_horizon[20].missingness.crosses_locked_oos > 0 for _ in [0]), (
        "sanity: horizon=20 should produce at least one CROSSES_LOCKED_OOS outcome"
    )
    for p in profiles:
        m = p.missingness
        assert (
            m.valid_outcomes + m.insufficient_future_data + m.crosses_locked_oos
            + m.missing_benchmark + m.invalid_input + m.data_gap == m.episodes
        )
