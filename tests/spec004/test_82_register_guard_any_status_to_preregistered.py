"""TEST 82 -- Stage 6, Finding 17 (GPT-G4), design option (a): EVERY
public-API transition path into PREREGISTERED is refused, not only the
from-nothing insert. Pre-Stage-6, `register()` of a HANDOFF_TO_BACKTEST
record followed by `register()` of the SAME id as PREREGISTERED was
accepted (reproduced on `b7d6b02`), since the guard only fired when
`existing is None`.

The one legitimate use kept unchanged: idempotent re-registration of an
ALREADY-PREREGISTERED record with identical content (audit-log replay)."""
import dataclasses

import pytest

from hypothesis.models.entities import HypothesisStatus
from hypothesis.registry.hypotheses import HypothesisRegistry, ImmutableHypothesisError

from spec004.gate_inputs import draft_from_proposal, gate, make_proposal, with_variants

_NON_PREREGISTERED = [s.value for s in HypothesisStatus if s != HypothesisStatus.PREREGISTERED]


def test_every_non_preregistered_status_is_covered():
    assert set(_NON_PREREGISTERED) == {"DRAFT", "REVIEWED", "REJECTED", "HANDOFF_TO_BACKTEST"}


@pytest.mark.parametrize("prior_status", [None] + _NON_PREREGISTERED)
def test_register_refuses_every_transition_into_preregistered(prior_status, hypothesis_config):
    draft = draft_from_proposal(make_proposal(), hypothesis_config)
    reg = HypothesisRegistry()
    if prior_status is not None:
        reg.register(dataclasses.replace(draft, status=prior_status))
    with pytest.raises(ImmutableHypothesisError, match="cannot transition into PREREGISTERED"):
        reg.register(dataclasses.replace(draft, status=HypothesisStatus.PREREGISTERED.value))
    stored = reg.get(draft.hypothesis_id)
    assert (stored is None) if prior_status is None else (stored.status == prior_status)


def test_idempotent_reregistration_of_an_identical_preregistered_record_still_succeeds(
    hypothesis_config, hypothesis_config_registry, run_registry,
):
    proposal = make_proposal()
    draft, variants = with_variants(draft_from_proposal(proposal, hypothesis_config), proposal)
    reg = HypothesisRegistry()
    frozen = gate(
        draft, variants, proposal, hypothesis_config=hypothesis_config,
        config_registry=hypothesis_config_registry, run_registry=run_registry, registry=reg,
    )
    assert reg.register(frozen) == frozen  # e.g. audit-log replay
    with pytest.raises(ImmutableHypothesisError, match="PREREGISTERED and immutable"):
        reg.register(dataclasses.replace(frozen, created_at="changed"))
    assert reg.get(frozen.hypothesis_id) == frozen


def test_non_preregistered_records_still_register_and_update_freely(hypothesis_config):
    draft = draft_from_proposal(make_proposal(), hypothesis_config)
    reg = HypothesisRegistry()
    for status in ("DRAFT", "REVIEWED", "HANDOFF_TO_BACKTEST", "REJECTED"):
        reg.register(dataclasses.replace(draft, status=status))
        assert reg.get(draft.hypothesis_id).status == status
