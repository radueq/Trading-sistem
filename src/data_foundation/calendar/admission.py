"""Calendar source ADMISSION -- Step 0 of the admission/verification/
registration contract (joint remediation design 003+004, 2026-10-04,
section 2; decision registry B1/B3, revision 5-6; authorized 2026-10-06
as part of Stage 2).

`admission_id` vs. `artifact_digest` (GPT review, Stage 2 THIRD
changes-required round): `artifact_digest` identifies ONLY the raw
text. The SAME text can be legitimately admitted more than once, under
different metadata -- a different source, operator, coverage window --
and `artifact_digest` alone cannot tell those decisions apart. GPT's
own reproduction: admission A (text X, source A, coverage to
2024-01-31) and admission B (the SAME text X, source B, coverage to
2024-12-31) both succeeded, but because `AdmissionRegistry` keyed its
entries by `artifact_digest` alone, admission B silently overwrote
admission A's own retained snapshot -- resolving A's own identity
returned B's metadata instead. `admission_id` (`_compute_admission_id()`
below) binds the digest to every field that distinguishes one admission
DECISION from another -- source, method, version, publication,
coverage, market, timezone, attestation -- so two admissions of the
same text with different metadata get different identities, both
retained, while the exact same admission repeated is idempotent.

The gap this closes: comparing a calendar candidate against an artifact
supplied by the SAME caller only proves the two agree with each other,
never that the artifact itself is an authentic source. Before any
artifact may be used by `registry.verify_calendar_against_source()`,
Data Foundation must ADMIT it via exactly one of two named paths:

- an APPROVED PROVIDER -- a source identifier on a maintained, explicit
  allow-list;
- an explicit OPERATOR ATTESTATION -- a named human records that they
  are vouching for this specific artifact, as themselves the trust
  boundary (stated plainly as such, not disguised as an automated
  check).

V1 scope, stated precisely (decision registry B3): this module
implements the ADMISSION MECHANISM only, fully testable with fixture
artifacts. No real commercial calendar provider is integrated, and no
cost or external service commitment is made here -- `APPROVED_
PROVIDERS_V1` is deliberately empty; a real deployment populates it
separately, out of this stage's authorized scope. Admitting a fixture
artifact through this mechanism does NOT make a real, usable calendar
available for an actual formal run -- that remains blocked on a real
source being identified and genuinely admitted, a separate, still-open
piece of work.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Optional

ADMISSION_METHOD_APPROVED_PROVIDER = "APPROVED_PROVIDER"
ADMISSION_METHOD_OPERATOR_ATTESTATION = "OPERATOR_ATTESTATION"

# Deliberately empty in V1 (decision registry B3) -- no real provider is
# integrated by this stage. A real deployment populates this separately.
APPROVED_PROVIDERS_V1: frozenset[str] = frozenset()


class CalendarSourceNotAdmittedError(ValueError):
    pass


class AdmissionIdentityCollisionError(ValueError):
    """Raised only if two DIFFERENT admitted payloads ever compute the
    SAME `admission_id` (an sha256 collision across full admission
    metadata) -- expected never to actually happen; this is a refusal
    to silently overwrite, not a real operational path."""
    pass


@dataclass(frozen=True)
class AdmittedCalendarSource:
    """The retained record of ONE admission decision: the source's own
    identifier, version/publication date, declared coverage interval,
    market/timezone, the RAW artifact content (verbatim, for later
    audit/re-derivation), the artifact's own content digest (`sha256`,
    computed HERE from `raw_content`, never caller-supplied -- so the
    digest always genuinely corresponds to what was retained), and
    `admission_id` -- the identity of THIS admission decision, distinct
    from `artifact_digest` (see module docstring): two admissions of
    the identical text under different metadata get different
    `admission_id`s."""
    source_identifier: str
    admission_method: str  # ADMISSION_METHOD_APPROVED_PROVIDER | ADMISSION_METHOD_OPERATOR_ATTESTATION
    version: str
    publication_date: str
    coverage_start: str
    coverage_end: str
    market: str
    timezone: str
    raw_content: str
    artifact_digest: str
    admission_id: str
    attested_by: Optional[str] = None
    attested_at: Optional[str] = None


def _digest(raw_content: str) -> str:
    return hashlib.sha256(raw_content.encode()).hexdigest()


def _compute_admission_id(
    *, artifact_digest: str, source_identifier: str, admission_method: str, version: str,
    publication_date: str, coverage_start: str, coverage_end: str, market: str, timezone: str,
    attested_by: Optional[str], attested_at: Optional[str],
) -> str:
    """The admission DECISION's own identity -- the digest plus every
    field that distinguishes one admission from another. Computed here,
    the same way every other identity in this project is (content-
    addressed, never caller-supplied), so the exact same admission
    repeated is idempotent (same inputs -> same id), while a different
    admission of the same text is a different id.

    Serialized as CANONICAL JSON (sorted keys, no extra whitespace) --
    never raw string concatenation (GPT review, Stage 2 non-blocking
    follow-up on commit `fd992db`, fixed under the separately-authorized
    #003 v2 -> #005 compatibility delta): a plain `"\\x1f".join()` of
    the same fields let a value CONTAINING that separator produce the
    SAME preimage for two DIFFERENT field splits (reproduced:
    `version="v1\\x1fextra", publication_date="2024-01-01"` vs.
    `version="v1", publication_date="extra\\x1f2024-01-01"`) -- not an
    sha256 collision, a serialization ambiguity. `AdmissionRegistry.
    _record()`'s own equality check already refused to let the second
    admission silently overwrite the first when this happened, so it
    was never a live bypass -- but the prior claim that any id conflict
    would require an sha256 collision was too strong, and is corrected
    by this fix, not merely restated. JSON with sorted keys gives each
    field its own delimited, escaped slot, so no field's own content
    can be mistaken for a boundary between fields.

    `attested_by`/`attested_at` serialize as JSON `null` when `None`,
    never the string `""` -- distinguishing "no attestation" from "an
    empty attestation" (the prior `\\x1f`-join scheme conflated the
    two, via `attested_by or ""`).

    Effect on existing identities, declared explicitly, not silently
    reinterpreted: EVERY `admission_id` this function computes changes
    value versus the prior `\\x1f`-join scheme, for every input, not
    only the colliding ones -- the preimage format itself changed.
    `AdmissionRegistry` is in-memory, per-run only, never persisted
    anywhere outside a single process's lifetime, so no existing,
    stored `admission_id` anywhere is invalidated by this change."""
    canonical = json.dumps(
        {
            "artifact_digest": artifact_digest, "source_identifier": source_identifier,
            "admission_method": admission_method, "version": version, "publication_date": publication_date,
            "coverage_start": coverage_start, "coverage_end": coverage_end, "market": market,
            "timezone": timezone, "attested_by": attested_by, "attested_at": attested_at,
        },
        sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


class AdmissionRegistry:
    """Step 0's own atomic gate (GPT review, Stage 2 second
    changes-required round): the ONLY place `registry.
    CalendarRegistry.register_verified()` may obtain an
    `AdmittedCalendarSource` from. A caller can no longer hand
    `register_verified()` a directly-constructed `AdmittedCalendarSource`
    object (GPT's own reproduction: a hand-built object with
    `admission_method="APPROVED_PROVIDER"` and a source NOT on the
    allow-list, never passed through either admit_* function, was
    accepted and later resolved through the calendar gate -- digest
    self-consistency proves the OBJECT agrees with itself, never that
    it was actually admitted).

    Written to ONLY by `admit_source_via_approved_provider()`/
    `admit_source_via_operator_attestation()` below, each of which
    enforces its own admission rule BEFORE the artifact is ever
    retained here. Resolved by `admission_id` -- NOT the artifact's
    bare `sha256` digest (GPT review, Stage 2 THIRD changes-required
    round: keying by the raw-text digest alone let a second,
    differently-admitted use of the SAME text silently replace an
    earlier admission's retained snapshot; see module docstring).
    `admission_id` binds the digest to the full admission metadata, so
    a `register_verified()` caller supplying it gets back exactly the
    admission decision it names, never a different one that happens to
    share the same underlying text; and there is still no path into
    the calendar gate for an artifact that did not actually pass
    through admission."""

    def __init__(self) -> None:
        self._entries: dict[str, AdmittedCalendarSource] = {}

    def resolve(self, admission_id: str) -> AdmittedCalendarSource:
        entry = self._entries.get(admission_id)
        if entry is None:
            raise CalendarSourceNotAdmittedError(
                f"admission_id={admission_id!r} has no linked admission in this registry -- an "
                f"AdmittedCalendarSource is never trusted unless it was actually produced by "
                f"admit_source_via_approved_provider()/admit_source_via_operator_attestation(), "
                f"never by direct construction"
            )
        return entry

    def _record(self, admitted: AdmittedCalendarSource) -> str:
        """Internal -- called only by the two admit_* functions below,
        each of which has already enforced its own admission rule and
        computed `admitted.admission_id` from the full admission
        metadata, not merely the artifact's own digest. Two admissions
        that land on the SAME `admission_id` are, by construction,
        admissions of identical content under identical metadata --
        recording the same one twice is a harmless no-op (idempotent).
        Two DIFFERENT payloads landing on the same id would be an
        sha256 collision across that full metadata, never expected in
        practice; refused outright rather than silently overwritten,
        since this registry's whole purpose is to never let one
        admission's retained snapshot replace another's."""
        existing = self._entries.get(admitted.admission_id)
        if existing is not None and existing != admitted:
            raise AdmissionIdentityCollisionError(
                f"admission_id={admitted.admission_id!r} already holds a DIFFERENT admitted "
                f"snapshot -- refusing to overwrite it"
            )
        self._entries[admitted.admission_id] = admitted
        return admitted.admission_id


def admit_source_via_approved_provider(
    *, registry: AdmissionRegistry, source_identifier: str, version: str,
    publication_date: str, coverage_start: str, coverage_end: str,
    market: str, timezone: str, raw_content: str,
) -> AdmittedCalendarSource:
    """Checked ONLY against the module-level `APPROVED_PROVIDERS_V1`
    constant -- NEVER a caller-supplied allow-list (GPT review, Stage 2
    changes-required round: a trust-config value a caller can freely
    pass in is candidate DATA, not admission AUTHORITY; a test wanting
    to exercise the success path monkeypatches `APPROVED_PROVIDERS_V1`
    itself, which is an explicit, visible override of the mechanism's
    own trust config, never a parameter an ordinary caller controls).
    Rejects outright, before any comparison, if `source_identifier` is
    not on that list -- admission failure is its own, separate
    rejection reason from a later verification mismatch. In V1,
    `APPROVED_PROVIDERS_V1` is deliberately empty, so this path always
    rejects until a real deployment populates it."""
    if source_identifier not in APPROVED_PROVIDERS_V1:
        raise CalendarSourceNotAdmittedError(
            f"source_identifier={source_identifier!r} is not on the approved-provider allow-list "
            f"-- admission refused before any session-date comparison is attempted"
        )
    digest = _digest(raw_content)
    admission_id = _compute_admission_id(
        artifact_digest=digest, source_identifier=source_identifier,
        admission_method=ADMISSION_METHOD_APPROVED_PROVIDER, version=version,
        publication_date=publication_date, coverage_start=coverage_start, coverage_end=coverage_end,
        market=market, timezone=timezone, attested_by=None, attested_at=None,
    )
    admitted = AdmittedCalendarSource(
        source_identifier=source_identifier, admission_method=ADMISSION_METHOD_APPROVED_PROVIDER,
        version=version, publication_date=publication_date,
        coverage_start=coverage_start, coverage_end=coverage_end,
        market=market, timezone=timezone, raw_content=raw_content, artifact_digest=digest,
        admission_id=admission_id, attested_by=None, attested_at=None,
    )
    registry._record(admitted)
    return admitted


def admit_source_via_operator_attestation(
    *, registry: AdmissionRegistry, source_identifier: str, operator_name: str, attested_at: str, version: str,
    publication_date: str, coverage_start: str, coverage_end: str,
    market: str, timezone: str, raw_content: str,
) -> AdmittedCalendarSource:
    """The named human IS the trust boundary when verification is
    manual -- stated plainly, not disguised as an automated check.
    `operator_name` must be a real, non-blank name; a blank attester
    would silently defeat the entire point of this path."""
    if not operator_name or not operator_name.strip():
        raise CalendarSourceNotAdmittedError(
            "operator attestation requires a named human operator -- admission refused "
            "(the operator is the trust boundary for a manual admission; it cannot be blank)"
        )
    if not attested_at or not attested_at.strip():
        raise CalendarSourceNotAdmittedError(
            "operator attestation requires an explicit attestation timestamp -- admission refused"
        )
    digest = _digest(raw_content)
    admission_id = _compute_admission_id(
        artifact_digest=digest, source_identifier=source_identifier,
        admission_method=ADMISSION_METHOD_OPERATOR_ATTESTATION, version=version,
        publication_date=publication_date, coverage_start=coverage_start, coverage_end=coverage_end,
        market=market, timezone=timezone, attested_by=operator_name, attested_at=attested_at,
    )
    admitted = AdmittedCalendarSource(
        source_identifier=source_identifier, admission_method=ADMISSION_METHOD_OPERATOR_ATTESTATION,
        version=version, publication_date=publication_date,
        coverage_start=coverage_start, coverage_end=coverage_end,
        market=market, timezone=timezone, raw_content=raw_content, artifact_digest=digest,
        admission_id=admission_id, attested_by=operator_name, attested_at=attested_at,
    )
    registry._record(admitted)
    return admitted
