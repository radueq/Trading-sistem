"""TEST 1 -- `RegisteredConfigVersion`/`ConfigRegistry` (Section 7 of
the joint remediation design 003+004, 2026-10-04, revision 11; decision
registry, Stage 3; authorized 2026-10-07; CORRECTED round 2 -- GPT
changes-required verdict on commit `8650f17`).

Shared-mechanism unit coverage, independent of any domain -- Discovery/
Evaluation/Hypothesis/Research Queue each get their own real-consumer
tests (tests/spec002, tests/spec003, tests/spec004) proving THIS same
mechanism wired into their own production code paths, not just this
module in isolation.
"""
from types import MappingProxyType

import pytest

from config_identity.registry import (
    ConfigIdentityError,
    ConfigRegistry,
    freeze,
    normalize_for_comparison,
    register_config_version,
)

_CONTENT = {"a": 1, "b": {"c": [1, 2, 3], "d": "x"}, "e": [{"f": 1}, {"g": [9, 8]}]}
_RAW_TEXTS = ("dummy raw source text -- shared-mechanism unit tests, independent of any real domain",)


def test_legitimate_config_registers_and_verifies():
    registered = register_config_version("test_domain", "cfg_v1", _CONTENT, _RAW_TEXTS)
    ok, errors = registered.verify("cfg_v1", _CONTENT)
    assert ok, errors
    assert registered.raw_texts == _RAW_TEXTS


def test_wrong_label_correct_content_is_rejected_by_the_label_check_specifically():
    registered = register_config_version("test_domain", "cfg_v1", _CONTENT, _RAW_TEXTS)
    ok, errors = registered.verify("cfg_v1_WRONG_LABEL", _CONTENT)
    assert not ok
    assert any("does not match the" in e and "registered for this operation" in e for e in errors)
    # The structural-equality check must NOT ALSO fire -- content genuinely matches.
    assert not any("does not structurally match" in e for e in errors)


def test_correct_label_wrong_content_is_rejected_by_the_structural_check_specifically():
    registered = register_config_version("test_domain", "cfg_v1", _CONTENT, _RAW_TEXTS)
    tampered_content = {**_CONTENT, "b": {**_CONTENT["b"], "c": [1, 2, 999]}}
    ok, errors = registered.verify("cfg_v1", tampered_content)
    assert not ok
    assert any("does not structurally match" in e for e in errors)
    # The label check must NOT ALSO fire -- the label genuinely matches.
    assert not any("does not match the" in e and "registered for this operation" in e for e in errors)


def test_both_label_and_content_wrong_reports_both_separately():
    registered = register_config_version("test_domain", "cfg_v1", _CONTENT, _RAW_TEXTS)
    ok, errors = registered.verify("cfg_WRONG", {"totally": "different"})
    assert not ok
    assert len(errors) == 2


def test_directly_constructed_inconsistent_object_is_rejected():
    """A hand-built candidate whose label/content were never produced
    by any real load_config() call, with no relationship to the
    registered snapshot, is refused -- its own internal self-
    consistency (or lack thereof) is irrelevant; it simply does not
    match what was registered."""
    registered = register_config_version("test_domain", "cfg_v1", _CONTENT, _RAW_TEXTS)
    forged_content = {"hand_built": True, "nested": {"made_up": [1, 2, 3]}}
    ok, errors = registered.verify("cfg_HAND_BUILT", forged_content)
    assert not ok
    assert len(errors) == 2


def test_freeze_is_recursive_not_shallow():
    """A list nested two levels deep inside a dict-of-dicts becomes a
    tuple -- `MappingProxyType` alone wraps only the OUTER dict, never
    the inner lists (the exact gap section 7 names)."""
    frozen = freeze(_CONTENT)
    assert isinstance(frozen["b"], MappingProxyType)
    assert isinstance(frozen["b"]["c"], tuple)
    assert isinstance(frozen["e"], tuple)
    assert isinstance(frozen["e"][0], MappingProxyType)
    assert isinstance(frozen["e"][1]["g"], tuple)


def test_freeze_recurses_into_an_externally_supplied_mappingproxytype_identically_to_a_dict():
    """Finding #4 (GPT changes-required verdict on `8650f17`): `freeze()`
    used to fall through to `return value` for an externally-supplied
    `MappingProxyType` (it is not a `dict` subclass, so a bare
    `isinstance(value, dict)` check missed it) -- a nested mutable list
    inside it then passed through un-recursed, un-frozen. Mutating the
    ORIGINAL list after "freezing" must never be visible through the
    snapshot, exactly as it already isn't for a plain dict."""
    mutable_list = [1, 2, 3]
    external_proxy = MappingProxyType({"nested": {"inner_list": mutable_list}})
    frozen = freeze(external_proxy)
    assert isinstance(frozen, MappingProxyType)
    assert isinstance(frozen["nested"], MappingProxyType)
    assert isinstance(frozen["nested"]["inner_list"], tuple)
    assert frozen["nested"]["inner_list"] == (1, 2, 3)

    mutable_list.append(999)  # mutate the ORIGINAL list the proxy wraps, AFTER freezing
    assert frozen["nested"]["inner_list"] == (1, 2, 3), "mutation leaked through the MappingProxyType gap"


def test_register_config_version_rejects_an_externally_supplied_mappingproxytype_with_nested_lists():
    """Same gap as above, exercised through `register_config_version()`
    itself (the actual entry point every call site uses) rather than
    `freeze()` directly -- required regression: "a MappingProxyType
    containing nested lists"."""
    mutable_list = ["a", "b"]
    external_proxy = MappingProxyType({"thresholds": {"values": mutable_list}})
    registered = register_config_version("test_domain", "cfg_v1", external_proxy, _RAW_TEXTS)
    mutable_list.append("TAMPERED_AFTER_REGISTRATION")
    ok, errors = registered.verify("cfg_v1", external_proxy)
    # external_proxy ITSELF now reflects the mutation (it wraps the same
    # mutable_list) -- verify() must see registered.content as still
    # holding the ORIGINAL, pre-mutation values, so comparing it against
    # the NOW-mutated external_proxy must fail the structural check.
    assert not ok
    assert any("does not structurally match" in e for e in errors)


def test_freeze_rejects_an_unsupported_mutable_type():
    """Any type freeze() does not recognize as either a recursable
    container (dict/MappingProxyType/list/tuple) or an atomic,
    already-immutable scalar is explicitly REJECTED -- silently
    passing it through (the pre-round-2 catch-all `return value`)
    would let an unrecognized mutable value alias into a snapshot
    callers rely on being immutable."""
    with pytest.raises(ConfigIdentityError, match="cannot safely freeze"):
        freeze({"thresholds": {1, 2, 3}})  # a bare set is mutable and unordered


def test_normalize_for_comparison_treats_frozen_and_unfrozen_equivalently():
    unfrozen = {"a": [1, 2], "b": {"c": 3}}
    frozen = freeze(unfrozen)
    assert unfrozen != frozen  # Python's own == is NOT structural here
    assert normalize_for_comparison(unfrozen) == normalize_for_comparison(frozen)


def test_mutating_the_source_after_freezing_never_reaches_the_frozen_snapshot():
    """The frozen snapshot is built from a fresh traversal -- it never
    aliases the original dict/list objects, so a nested mutation to
    the SOURCE after freezing cannot reach the registered content."""
    source = {"outer": {"inner_list": [1, 2, 3]}}
    registered = register_config_version("test_domain", "cfg_v1", source, _RAW_TEXTS)
    source["outer"]["inner_list"].append(999)  # mutate the ORIGINAL, nested, after freezing
    assert registered.content["outer"]["inner_list"] == (1, 2, 3)


def test_config_registry_has_no_public_unconditional_overwrite():
    """Finding #3: the public API must not expose an unconditional
    overwrite path -- `register()` was removed; `register_or_verify()`
    is the ONLY public write method."""
    registry = ConfigRegistry()
    assert not hasattr(registry, "register")


def test_config_registry_first_call_registers_second_call_with_same_content_is_idempotent():
    registry = ConfigRegistry()
    first = registry.register_or_verify("test_domain", "cfg_v1", _CONTENT, _RAW_TEXTS)
    second = registry.register_or_verify("test_domain", "cfg_v1", _CONTENT, _RAW_TEXTS)
    assert first is second


def test_config_registry_source_changed_after_registration_is_rejected():
    """The SAME domain, registered once, then a LATER call within the
    same registry supplies DIFFERENT content under the SAME label --
    this is exactly the 'file mutated between registration and now'
    scenario section 7's mandatory-live-re-read policy targets, AND
    the required regression "an attempt to replace an already-
    registered reference" -- it must be REJECTED, keeping the
    original, never silently overwritten."""
    registry = ConfigRegistry()
    registry.register_or_verify("test_domain", "cfg_v1", _CONTENT, _RAW_TEXTS)
    changed_content = {**_CONTENT, "b": {**_CONTENT["b"], "c": [1, 2, 999]}}
    with pytest.raises(ConfigIdentityError, match="does not structurally match"):
        registry.register_or_verify("test_domain", "cfg_v1", changed_content, _RAW_TEXTS)
    # The original registration is untouched by the rejected attempt.
    assert registry.resolve("test_domain").content["b"]["c"] == (1, 2, 3)


def test_config_registry_rejects_a_totally_different_replacement_for_an_already_registered_domain():
    """Same requirement, a fully unrelated replacement attempt (not
    merely a tweaked field) -- `register_or_verify()` must reject it
    exactly the same way; a new, unrelated config is never a reason to
    silently adopt it as the domain's new reference."""
    registry = ConfigRegistry()
    registry.register_or_verify("test_domain", "cfg_v1", _CONTENT, _RAW_TEXTS)
    with pytest.raises(ConfigIdentityError):
        registry.register_or_verify("test_domain", "cfg_UNRELATED", {"nothing": "alike"}, ("other raw text",))
    assert registry.resolve("test_domain").content == freeze(_CONTENT)


def test_config_registry_resolve_without_a_prior_register_is_refused():
    registry = ConfigRegistry()
    with pytest.raises(ConfigIdentityError, match="no RegisteredConfigVersion registered"):
        registry.resolve("never_registered_domain")


def test_config_registry_separate_domains_are_fully_independent():
    registry = ConfigRegistry()
    registry.register_or_verify("domain_a", "cfg_a", {"x": 1}, _RAW_TEXTS)
    registry.register_or_verify("domain_b", "cfg_b", {"x": 2}, _RAW_TEXTS)
    assert registry.resolve("domain_a").content["x"] == 1
    assert registry.resolve("domain_b").content["x"] == 2
