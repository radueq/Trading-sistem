"""Config identity infrastructure -- Section 7 of the joint remediation
design (003+004, 2026-10-04, revision 11); decision registry, Stage 3;
Radu's explicit authorization, 2026-10-07, applied to Discovery,
Evaluation, Hypothesis, and Research Queue.

One `load_config()` call per operation, a full recursive freeze (never
`MappingProxyType` alone -- a list nested inside a dict-of-dicts is
still a plain, mutable list through a bare `MappingProxyType` wrapper),
and a two-part verification (declared label + structurally-normalized
content, each catching a DIFFERENT failure mode) for any config object
not sourced directly from the registered snapshot.

`config_version` itself is NEVER touched or re-derived here -- it
remains EXACTLY what each domain's own, unchanged loader computes
(`sha256(raw_text)[:12]` for hypothesis/evaluation;
`sha256("".join(raw_texts))[:12]` for discovery, preserving its own
multi-source-combination rule byte-for-byte). This module only (a)
retains that version verbatim, (b) builds an immutable, recursively-
frozen snapshot of the already-parsed content for safe reuse, and (c)
compares a CANDIDATE object against an EARLIER-REGISTERED one.
Historical identities computed under the unchanged loaders are
preserved exactly; nothing here reinterprets them.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Optional


class ConfigIdentityError(ValueError):
    pass


def freeze(value: Any) -> Any:
    """Full recursive freeze: dict -> `MappingProxyType` of
    recursively-frozen values; list/tuple -> tuple of recursively-
    frozen elements; every other value (str/int/float/bool/None)
    returned as-is (already immutable). Built from a fresh,
    independent traversal -- never aliases the original dict/list
    objects anywhere in the result, so mutating the SOURCE after
    freezing can never reach the frozen snapshot."""
    if isinstance(value, dict):
        return MappingProxyType({k: freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze(v) for v in value)
    return value


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
    """One `load_config()` call's own retained identity for one
    operation (or one domain within an operation): `version` is the
    loader's OWN output, carried forward VERBATIM -- never re-derived
    from `content` by any hash computed here. `content` is the fully,
    recursively frozen structure built from the SAME parsed data the
    loader produced."""
    domain: str
    version: str
    content: Any

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


def register_config_version(domain: str, version: str, content: Any) -> RegisteredConfigVersion:
    """Builds a `RegisteredConfigVersion` by freezing `content` --
    `version` is retained exactly as given, never recomputed."""
    return RegisteredConfigVersion(domain=domain, version=version, content=freeze(content))


class ConfigRegistry:
    """One `RegisteredConfigVersion` per domain for one operation (or
    one multi-step workflow sharing a single `ConfigRegistry`
    instance) -- mirroring this project's own established atomic-gate
    pattern (`AdmissionRegistry`, `CalendarRegistry`): one write path,
    a resolve path that refuses anything not registered through it.

    `register()` is unconditional -- it always (re)writes the domain's
    entry, used for the FIRST, authoritative registration.
    `register_or_verify()` is what most callers actually want: the
    FIRST call for a domain registers it as this operation's own
    pinned baseline; every SUBSEQUENT call verifies its candidate
    against that SAME baseline, raising on a mismatch rather than
    silently re-registering a different one -- this is what makes
    'the operation consumes exclusively the verified snapshot'
    enforceable across multiple internal read points within one
    operation, or across a multi-step workflow."""

    def __init__(self) -> None:
        self._entries: dict[str, RegisteredConfigVersion] = {}

    def register(self, domain: str, version: str, content: Any) -> RegisteredConfigVersion:
        registered = register_config_version(domain, version, content)
        self._entries[domain] = registered
        return registered

    def try_resolve(self, domain: str) -> Optional[RegisteredConfigVersion]:
        return self._entries.get(domain)

    def resolve(self, domain: str) -> RegisteredConfigVersion:
        entry = self.try_resolve(domain)
        if entry is None:
            raise ConfigIdentityError(f"no RegisteredConfigVersion registered for domain={domain!r}")
        return entry

    def register_or_verify(self, domain: str, version: str, content: Any) -> RegisteredConfigVersion:
        existing = self.try_resolve(domain)
        if existing is None:
            return self.register(domain, version, content)
        ok, errors = existing.verify(version, content)
        if not ok:
            raise ConfigIdentityError("; ".join(errors))
        return existing
