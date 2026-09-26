"""TEST 66 -- `build_research_queue()` hard-fails on duplicate
`signature_id` among the supplied packets (PATCH #004-B finding #5, GPT
Review #004 Round 2, minor point). PATCH #004-A moved the queue to one
entry per signature, but nothing stopped a caller from accidentally
passing `[packet_SIG_A, packet_SIG_A]` and getting two queue entries for
the SAME signature -- a duplicate that would silently double a
signature's presence on the queue."""
import dataclasses

import pytest

from hypothesis.evidence.queue import build_research_queue


def test_duplicate_signature_id_among_packets_is_rejected(evidence_packet, hypothesis_config):
    duplicated = [evidence_packet, dataclasses.replace(evidence_packet)]
    with pytest.raises(ValueError, match="duplicate signature_id"):
        build_research_queue(duplicated, hypothesis_config)


def test_distinct_signature_ids_are_unaffected(evidence_packet, hypothesis_config):
    other = dataclasses.replace(evidence_packet, signature_id="OTHER_SIGNATURE")
    entries = build_research_queue([evidence_packet, other], hypothesis_config)
    assert len(entries) == 2
