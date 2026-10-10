"""TEST 84 -- Stage 8, Finding 18 (GPT-G5): the PRIMARY horizon's
stability-bin VALUES reach the EvidencePacket (`primary_stability_
summary`), with CORRECT values -- not merely a presence flag
(the design's own regression wording). Pre-Stage-8 the packet carried
only `primary_has_stability_bins: bool` (reproduced on `051d9a1`).

Field list per the explicitly recorded AMENDMENT (decision sheet
revision 23): exactly `(bin_label, episode_n, unique_securities, mean,
median, mean_relative, positive_rate)` -- GPT's technical
clarification, relayed by Radu, after the design sketch's `valid_n` was
shown not to exist on `StabilityBinResult`. Requirements tested here,
from that clarification: faithful copy (no recomputation, no renaming,
`None` never turned into zero); source order and empty bins preserved;
fixtures with `mean != mean_relative` and distinct values per horizon;
every field checked; serialized packet size measured against SS40's
~1-3KB target.
"""
import dataclasses
import json

import pytest

from evaluation.models.entities import StabilityBinResult
from hypothesis.evidence.packet import build_evidence_packet
from hypothesis.models.entities import StabilityBinSummary

from spec004.conftest import make_evidence_profile

_SEVEN_FIELDS = ("bin_label", "episode_n", "unique_securities", "mean", "median", "mean_relative", "positive_rate")
_HORIZONS = (1, 2, 3, 5, 10)


def _bins(h: int) -> tuple[StabilityBinResult, ...]:
    """Distinct values per horizon; `mean` (absolute) != `mean_relative`
    in every populated bin; a genuinely EMPTY middle bin (None stats) in
    the middle of the source order."""
    return (
        StabilityBinResult("early", 14 + h, 6 + h, 0.0110 + h / 1000, 0.0090 + h / 1000, 0.0040 + h / 1000, 0.60 + h / 100),
        StabilityBinResult("middle", 0, 0, None, None, None, None),
        StabilityBinResult("late", 12 + h, 5 + h, -0.0020 - h / 1000, -0.0010 - h / 1000, 0.0070 + h / 1000, 0.40 + h / 100),
    )


@pytest.fixture
def profiles():
    return [make_evidence_profile(h, stability=_bins(h)) for h in _HORIZONS]


@pytest.fixture
def packet(signature_definition, profiles, run_registry, hypothesis_config):
    return build_evidence_packet(signature_definition, profiles, run_registry, hypothesis_config)


def test_the_summary_type_carries_exactly_the_seven_amended_fields_in_order():
    assert tuple(f.name for f in dataclasses.fields(StabilityBinSummary)) == _SEVEN_FIELDS
    assert "valid_n" not in _SEVEN_FIELDS  # the sketch's field that does not exist at the source
    # Same names as the source type -- nothing renamed.
    assert tuple(f.name for f in dataclasses.fields(StabilityBinResult)) == _SEVEN_FIELDS


def test_the_fixture_actually_distinguishes_mean_from_mean_relative_and_horizons(profiles):
    for p in profiles:
        for b in p.stability:
            if b.episode_n:
                assert b.mean != b.mean_relative
    as_tuples = [tuple(dataclasses.astuple(b) for b in p.stability) for p in profiles]
    assert len(set(as_tuples)) == len(_HORIZONS)  # every horizon's bins differ


def test_every_field_of_every_primary_bin_is_copied_faithfully(packet, profiles):
    primary = next(p for p in profiles if p.horizon_bars == packet.primary_evidence_horizon_bars)
    assert len(packet.primary_stability_summary) == len(primary.stability) == 3
    for got, src in zip(packet.primary_stability_summary, primary.stability, strict=True):
        for name in _SEVEN_FIELDS:
            source_value, packet_value = getattr(src, name), getattr(got, name)
            if source_value is None:
                assert packet_value is None, f"{name}: None must stay None, got {packet_value!r}"
            else:
                assert packet_value == source_value and type(packet_value) is type(source_value), name


def test_source_order_and_the_empty_bin_are_preserved(packet):
    assert [b.bin_label for b in packet.primary_stability_summary] == ["early", "middle", "late"]
    empty = packet.primary_stability_summary[1]
    assert (empty.episode_n, empty.unique_securities) == (0, 0)
    assert empty.mean is None and empty.median is None and empty.mean_relative is None and empty.positive_rate is None


def test_absolute_and_relative_means_are_not_swapped(packet, profiles):
    primary = next(p for p in profiles if p.horizon_bars == packet.primary_evidence_horizon_bars)
    early_src, early = primary.stability[0], packet.primary_stability_summary[0]
    assert early.mean == early_src.mean and early.mean_relative == early_src.mean_relative
    assert early.mean != early.mean_relative


def test_only_the_primary_horizon_bins_are_carried(packet, profiles):
    summary = tuple(dataclasses.astuple(b) for b in packet.primary_stability_summary)
    for p in profiles:
        source = tuple(dataclasses.astuple(b) for b in p.stability)
        assert (source == summary) is (p.horizon_bars == packet.primary_evidence_horizon_bars), p.horizon_bars


def test_no_source_bins_means_an_empty_summary_consistent_with_the_presence_flag(
    signature_definition, run_registry, hypothesis_config,
):
    no_bins = [make_evidence_profile(h, stability=()) for h in _HORIZONS]
    packet = build_evidence_packet(signature_definition, no_bins, run_registry, hypothesis_config)
    assert packet.primary_stability_summary == ()
    assert packet.primary_has_stability_bins is False


def test_presence_flag_unchanged_and_consistent_when_bins_exist(packet):
    assert packet.primary_has_stability_bins is True
    assert packet.primary_has_stability_bins == bool(packet.primary_stability_summary)


def test_serialized_packet_size_is_measured_against_the_ss40_target(packet):
    """SS40 targets ~1-3KB. Measured as compact JSON of the packet's
    dataclass fields (the form handed to an agent); the indented form is
    reported too, never substituted. This measures THIS packet shape (5
    decay points, 3 stability bins) -- it does not settle the general
    token-budget question (Finding 8), which remains its own item."""
    as_dict = dataclasses.asdict(packet)
    compact = len(json.dumps(as_dict, separators=(",", ":"), sort_keys=True).encode())
    indented = len(json.dumps(as_dict, indent=2, sort_keys=True).encode())
    without_summary = len(json.dumps({**as_dict, "primary_stability_summary": []}, separators=(",", ":"), sort_keys=True).encode())
    print(f"EvidencePacket compact={compact}B indent2={indented}B compact_without_summary={without_summary}B")
    assert compact <= 3 * 1024, f"compact serialized packet {compact}B exceeds the ~3KB SS40 target"
    assert compact > without_summary  # the summary is actually serialized, not dropped
