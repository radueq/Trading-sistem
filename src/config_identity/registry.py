"""Config identity infrastructure -- Section 7 of the joint remediation
design (003+004, 2026-10-04, revision 11); decision registry, Stage 3;
Radu's explicit authorization, 2026-10-07, applied to Discovery,
Evaluation, Hypothesis, and Research Queue. CORRECTED round 2 (GPT
changes-required verdict on commit `8650f17`): the first implementation
left verification conditional on an opt-in `config_registry`, trusted
whatever (version, content) a caller claimed as "the" reference on
first use, allowed `ConfigRegistry.register()` to silently overwrite an
existing domain entry, and `freeze()` did not recurse into an
externally-supplied `MappingProxyType`. All four are fixed here.

`config_version` itself is NEVER touched or re-derived -- it remains
EXACTLY what each domain's own, unchanged loader computes
(`sha256(raw_text)[:12]` for hypothesis/evaluation;
`sha256("".join(raw_texts))[:12]` for discovery, preserving its own
multi-source-combination rule byte-for-byte). This module only (a)
retains that version verbatim, (b) builds an immutable, recursively-
frozen snapshot of the already-parsed content for safe reuse, and (c)
compares a CANDIDATE object against an INDEPENDENTLY-SOURCED one.
Historical identities computed under the unchanged loaders are
preserved exactly; nothing here reinterprets them.

The "independent source" a candidate gets compared against is NEVER
built from the candidate's own claimed (version, content) pair --
every call site in discovery/engine.py, evaluation/engine.py,
hypothesis/evidence/queue.py, and hypothesis/registry/preregistration.py
re-derives it from a `raw_texts` tuple via that domain's own
`reparse_raw_texts()` (a pure function, no disk I/O, the EXACT same
parse+hash code `load_config()` itself uses) -- this module stays
domain-agnostic and never parses YAML itself.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Optional

_ATOMIC_TYPES = (str, int, float, bool, type(None), bytes)


class ConfigIdentityError(ValueError):
    pass


def freeze(value: Any) -> Any:
    """Full recursive freeze: dict OR `MappingProxyType` (handled
    IDENTICALLY -- a bare `isinstance(value, dict)` check would miss an
    externally-supplied `MappingProxyType`, letting a nested mutable
    list inside it pass through un-recursed) -> `MappingProxyType` of
    recursively-frozen values; list/tuple -> tuple of recursively-
    frozen elements; an atomic scalar (str/int/float/bool/None/bytes,
    already immutable) returned as-is. Built from a fresh, independent
    traversal -- never aliases the original dict/list objects anywhere
    in the result, so mutating the SOURCE after freezing can never
    reach the frozen snapshot. Any OTHER type (set, bytearray, a
    custom mutable object, ...) is explicitly REJECTED -- silently
    passing an unrecognized mutable value through would let it alias
    into a snapshot callers rely on being immutable."""
    if isinstance(value, (dict, MappingProxyType)):
        return MappingProxyType({k: freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze(v) for v in value)
    if isinstance(value, _ATOMIC_TYPES):
        return value
    raise ConfigIdentityError(
        f"freeze() cannot safely freeze a value of type {type(value).__name__!r} -- only "
        "dict/MappingProxyType, list/tuple, and atomic scalars (str/int/float/bool/None/bytes) "
        "may appear in a config snapshot; an unrecognized type might still be externally mutable"
    )


def normalize_for_comparison(value: Any) -> Any:
    """The SAME recursive traversal as `freeze()`, but reduced to a
    comparable shape BOTH a frozen snapshot and a freshly-parsed,
    unfrozen external dict can be put into before a structural-
    equality comparison -- `{"a": [1, 2]} == {"a": (1, 2)}` is `False`
    in Python even though the two mean the same thing, and a frozen
    `MappingProxyType` is never `==` to a plain `dict` holding
    unfrozen lists. dict/MappingProxyType -> a tuple of (key,
    normalized value) pairs SORTED by key (so comparison never depends
    on insertion order); list/tuple -> a tuple of normalized elements;
    everything else as-is. Apply this to BOTH sides before comparing,
    never compare an unfrozen dict directly against a frozen one."""
    if isinstance(value, (dict, MappingProxyType)):
        return tuple(sorted((k, normalize_for_comparison(v)) for k, v in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(normalize_for_comparison(v) for v in value)
    return value


@dataclass(frozen=True)
class RegisteredConfigVersion:
    """One domain's own retained identity for one operation: `version`
    is the loader's OWN output, carried forward VERBATIM -- never
    re-derived from `content` by any hash computed here. `content` is
    the fully, recursively frozen structure built from the parsed data
    an INDEPENDENT `reparse_raw_texts()` call produced. `raw_texts` is
    retained alongside them (Section 7's own requirement) so a LATER
    comparison always has the actual source text available, never only
    a derived version/content pair."""
    domain: str
    version: str
    content: Any
    raw_texts: tuple[str, ...]

    def verify(self, candidate_version: str, candidate_content: Any) -> tuple[bool, tuple[str, ...]]:
        """Two SEPARATE checks, each catching a different failure
        mode -- neither substitutes for the other, and both run
        regardless of whether the first already failed, so a caller
        sees every reason at once:

        (a) label check: `candidate_version == self.version`. Catches
            a CORRECT-content-WRONG-label object -- the content is
            actually fine, but the label lies about which version it
            is.
        (b) structural-equality check: `candidate_content`, normalized,
            equals `self.content`, normalized (via
            `normalize_for_comparison()` on BOTH sides, since
            `self.content` is already frozen and `candidate_content`
            generally is not). Catches a CORRECT-label-WRONG-content
            object -- the label is honest, but the underlying data was
            hand-built or mutated before being compared."""
        errors: list[str] = []
        if candidate_version != self.version:
            errors.append(
                f"{self.domain}: candidate config_version={candidate_version!r} does not match the "
                f"version={self.version!r} registered for this operation"
            )
        if normalize_for_comparison(candidate_content) != normalize_for_comparison(self.content):
            errors.append(
                f"{self.domain}: candidate config content does not structurally match the content "
                f"registered under version={self.version!r} for this operation"
            )
        return (not errors, tuple(errors))


def register_config_version(domain: str, version: str, content: Any, raw_texts: tuple[str, ...]) -> RegisteredConfigVersion:
    """Builds a `RegisteredConfigVersion` by freezing `content` --
    `version`/`raw_texts` are retained exactly as given, never
    recomputed. Callers are responsible for sourcing `version`/
    `content` INDEPENDENTLY (via a domain's own `reparse_raw_texts()`)
    -- this function itself does not verify that `version` honestly
    corresponds to `raw_texts`; `ConfigRegistry.register_or_verify()`
    and each call site's own self-consistency check are what enforce
    that (see discovery/engine.py et al.)."""
    return RegisteredConfigVersion(domain=domain, version=version, content=freeze(content), raw_texts=tuple(raw_texts))


class ConfigRegistry:
    """One `RegisteredConfigVersion` per domain for one operation (or
    one multi-step workflow sharing a single `ConfigRegistry`
    instance) -- mirroring this project's own established atomic-gate
    pattern (`AdmissionRegistry`, `CalendarRegistry`): one write path,
    a resolve path that refuses anything not registered through it.

    CORRECTED round 2: the public surface no longer exposes an
    unconditional overwrite. `register_or_verify()` is the ONLY public
    write path: the FIRST call for a domain registers it as this
    operation's own pinned baseline; every SUBSEQUENT call verifies
    its candidate against that SAME baseline and raises
    `ConfigIdentityError` on a mismatch -- it never silently
    re-registers a different one. Within one operation's context, a
    DIFFERENT re-registration for an already-registered domain is
    REJECTED, keeping the original; a genuinely new operation gets a
    new `ConfigRegistry` instance, which starts empty."""

    def __init__(self) -> None:
        self._entries: dict[str, RegisteredConfigVersion] = {}

    def _force_register(self, domain: str, version: str, content: Any, raw_texts: tuple[str, ...]) -> RegisteredConfigVersion:
        """Private: unconditionally (re)writes the domain's entry.
        Used ONLY internally by `register_or_verify()`'s first-call
        branch -- never exposed publicly, so nothing outside this
        class can overwrite an already-registered domain."""
        registered = register_config_version(domain, version, content, raw_texts)
        self._entries[domain] = registered
        return registered

    def try_resolve(self, domain: str) -> Optional[RegisteredConfigVersion]:
        return self._entries.get(domain)

    def resolve(self, domain: str) -> RegisteredConfigVersion:
        entry = self.try_resolve(domain)
        if entry is None:
            raise ConfigIdentityError(f"no RegisteredConfigVersion registered for domain={domain!r}")
        return entry

    def register_or_verify(self, domain: str, version: str, content: Any, raw_texts: tuple[str, ...] = ()) -> RegisteredConfigVersion:
        existing = self.try_resolve(domain)
        if existing is None:
            return self._force_register(domain, version, content, raw_texts)
        ok, errors = existing.verify(version, content)
        if not ok:
            raise ConfigIdentityError("; ".join(errors))
        return existing
