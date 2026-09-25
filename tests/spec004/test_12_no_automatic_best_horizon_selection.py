"""TEST 12 -- #004 never auto-selects a "best" horizon from the decay
curve (Spec #004 SS17-20/SS34, the "horizon trap"). Even when one horizon
has the strongest effect, HorizonCandidateSet.values keeps ALL of them,
and there is no field anywhere claiming one is "selected"/"optimal"."""
import dataclasses

from hypothesis.evidence.packet import build_evidence_packet
from hypothesis.models.entities import HorizonCandidateSet


def test_horizon_candidate_set_has_no_selected_or_optimal_field():
    field_names = {f.name for f in dataclasses.fields(HorizonCandidateSet)}
    assert "selected_horizon" not in field_names
    assert not any("optimal" in n or "best" in n for n in field_names)


def test_decay_curve_reports_every_horizon_even_though_3_bars_is_strongest(signature_definition, profiles_all_horizons, run_registry):
    packet = build_evidence_packet(signature_definition, profiles_all_horizons, run_registry, primary_horizon_bars=3)
    reported_horizons = {d.evidence_horizon_bars for d in packet.decay_curve}
    assert reported_horizons == {1, 2, 3, 5, 10}
    strongest = max(packet.decay_curve, key=lambda d: d.mean_relative_return or 0)
    assert strongest.evidence_horizon_bars == 3
    # ... yet nothing marks it as "selected" -- the caller must still consider all 5.
    assert not hasattr(packet, "selected_horizon")
