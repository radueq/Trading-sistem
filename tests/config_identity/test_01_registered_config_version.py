"""TEST 1 -- `RegisteredConfigVersion`/`ConfigRegistry` (Section 7 of
the joint remediation design 003+004, 2026-10-04, revision 11; decision
registry, Stage 3; authorized 2026-10-07).

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


def test_legitimate_config_registers_and_verifies():
    registered = register_config_version("test_domain", "cfg_v1", _CONTENT)
    ok, errors = registered.verify("cfg_v1", _CONTENT)
    assert ok, errors


def test_wrong_label_correct_content_is_rejected_by_the_label_check_specifically():
    registered = register_config_version("test_domain", "cfg_v1", _CONTENT)
    ok, errors = registered.verify("cfg_v1_WRONG_LABEL", _CONTENT)
    assert not ok
    assert any("does not match the" in e and "registered for this operation" in e for e in errors)
    # The structural-equality check must NOT ALSO fire -- content genuinely matches.
    assert not any("does not structurally match" in e for e in errors)


def test_correct_label_wrong_content_is_rejected_by_the_structural_check_specifically():
    registered = register_config_version("test_domain", "cfg_v1", _CONTENT)
    tampered_content = {**_CONTENT, "b": {**_CONTENT["b"], "c": [1, 2, 999]}}
    ok, errors = registered.verify("cfg_v1", tampered_content)
    assert not ok
    assert any("does not structurally match" in e for e in errors)
    # The label check must NOT ALSO fire -- the label genuinely matches.
    assert not any("does not match the" in e and "registered for this operation" in e for e in errors)


def test_both_label_and_content_wrong_reports_both_separately():
    registered = register_config_version("test_domain", "cfg_v1", _CONTENT)
    ok, errors = registered.verify("cfg_WRONG", {"totally": "different"})
    assert not ok
    assert len(errors) == 2


def test_directly_constructed_inconsistent_object_is_rejected():
    """A hand-built candidate whose label/content were never produced
    by any real load_config() call, with no relationship to the
    registered snapshot, is refused -- its own internal self-
    consistency (or lack thereof) is irrelevant; it simply does not
    match what was registered."""
    registered = register_config_version("test_domain", "cfg_v1", _CONTENT)
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


def test_mutating_the_source_after_freezing_never_reaches_the_frozen_snapshot():
    """The frozen snapshot is built from a fresh traversal -- it never
    aliases the original dict/list objects, so a nested mutation to
    the SOURCE after freezing cannot reach the registered content."""
    source = {"outer": {"inner_list": [1, 2, 3]}}
    registered = register_config_version("test_domain", "cfg_v1", source)
    source["outer"]["inner_list"].append(999)  # mutate the ORIGINAL, nested, after freezing
    assert registered.content["outer"]["inner_list"] == (1, 2, 3)


def test_normalize_for_comparison_treats_frozen_and_unfrozen_equivalently():
    unfrozen = {"a": [1, 2], "b": {"c": 3}}
    frozen = freeze(unfrozen)
    assert unfrozen != frozen  # Python's own == is NOT structural here
    assert normalize_for_comparison(unfrozen) == normalize_for_comparison(frozen)


def test_config_registry_first_call_registers_second_call_with_same_content_is_idempotent():
    registry = ConfigRegistry()
    first = registry.register_or_verify("test_domain", "cfg_v1", _CONTENT)
    second = registry.register_or_verify("test_domain", "cfg_v1", _CONTENT)
    assert first is second


def test_config_registry_source_changed_after_registration_is_rejected():
    """The SAME domain, registered once, then a LATER call within the
    same registry supplies DIFFERENT content under the SAME label --
    this is exactly the 'file mutated between registration and now'
    scenario section 7's mandatory-live-re-read policy targets."""
    registry = ConfigRegistry()
    registry.register_or_verify("test_domain", "cfg_v1", _CONTENT)
    changed_content = {**_CONTENT, "b": {**_CONTENT["b"], "c": [1, 2, 999]}}
    with pytest.raises(ConfigIdentityError, match="does not structurally match"):
        registry.register_or_verify("test_domain", "cfg_v1", changed_content)
    # The original registration is untouched by the rejected attempt.
    assert registry.resolve("test_domain").content["b"]["c"] == (1, 2, 3)


def test_config_registry_resolve_without_a_prior_register_is_refused():
    registry = ConfigRegistry()
    with pytest.raises(ConfigIdentityError, match="no RegisteredConfigVersion registered"):
        registry.resolve("never_registered_domain")


def test_config_registry_separate_domains_are_fully_independent():
    registry = ConfigRegistry()
    registry.register_or_verify("domain_a", "cfg_a", {"x": 1})
    registry.register_or_verify("domain_b", "cfg_b", {"x": 2})
    assert registry.resolve("domain_a").content["x"] == 1
    assert registry.resolve("domain_b").content["x"] == 2
