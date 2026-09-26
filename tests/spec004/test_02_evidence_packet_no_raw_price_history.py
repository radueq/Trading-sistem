"""TEST 2 -- EvidencePacket never contains raw price history (Spec #004
SS5/SS38-40). Structural: no field on the dataclass may reference OHLCV
or a PIT connection, and the packet built from real inputs never carries
anything resembling a price series."""
import dataclasses

from hypothesis.evidence.packet import build_evidence_packet
from hypothesis.models.entities import EvidencePacket

_FORBIDDEN_FIELD_SUBSTRINGS = ("price", "ohlcv", "open", "high", "low", "close", "volume", "bar_series")


def test_evidence_packet_fields_never_reference_price_history():
    field_names = {f.name for f in dataclasses.fields(EvidencePacket)}
    for name in field_names:
        for token in _FORBIDDEN_FIELD_SUBSTRINGS:
            assert token not in name.lower(), f"EvidencePacket.{name} looks like raw price history"


def test_built_packet_repr_has_no_price_series(signature_definition, profiles_all_horizons, run_registry, hypothesis_config):
    packet = build_evidence_packet(signature_definition, profiles_all_horizons, run_registry, hypothesis_config)
    text = repr(packet)
    for token in ("open=", "close=", "high=", "low=", "ohlc"):
        assert token not in text.lower()
