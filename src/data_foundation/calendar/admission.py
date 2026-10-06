"""Calendar source ADMISSION -- Step 0 of the admission/verification/
registration contract (joint remediation design 003+004, 2026-10-04,
section 2; decision registry B1/B3, revision 5-6; authorized 2026-10-06
as part of Stage 2).

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
from dataclasses import dataclass
from typing import Optional

ADMISSION_METHOD_APPROVED_PROVIDER = "APPROVED_PROVIDER"
ADMISSION_METHOD_OPERATOR_ATTESTATION = "OPERATOR_ATTESTATION"

# Deliberately empty in V1 (decision registry B3) -- no real provider is
# integrated by this stage. A real deployment populates this separately.
APPROVED_PROVIDERS_V1: frozenset[str] = frozenset()


class CalendarSourceNotAdmittedError(ValueError):
    pass


@dataclass(frozen=True)
class AdmittedCalendarSource:
    """The retained record of ONE admission decision: the source's own
    identifier, version/publication date, declared coverage interval,
    market/timezone, the RAW artifact content (verbatim, for later
    audit/re-derivation), and the artifact's own content digest
    (`sha256`, computed HERE from `raw_content`, never caller-supplied --
    so the digest always genuinely corresponds to what was retained)."""
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
    attested_by: Optional[str] = None
    attested_at: Optional[str] = None


def _digest(raw_content: str) -> str:
    return hashlib.sha256(raw_content.encode()).hexdigest()


def admit_source_via_approved_provider(
    *, source_identifier: str, approved_providers: frozenset[str], version: str,
    publication_date: str, coverage_start: str, coverage_end: str,
    market: str, timezone: str, raw_content: str,
) -> AdmittedCalendarSource:
    """`approved_providers` is passed explicitly by the caller (never
    read from a hidden global) so a test can supply its own allow-list
    without touching `APPROVED_PROVIDERS_V1`. Rejects outright, before
    any comparison, if `source_identifier` is not on that list --
    admission failure is its own, separate rejection reason from a later
    verification mismatch."""
    if source_identifier not in approved_providers:
        raise CalendarSourceNotAdmittedError(
            f"source_identifier={source_identifier!r} is not on the approved-provider allow-list "
            f"-- admission refused before any session-date comparison is attempted"
        )
    return AdmittedCalendarSource(
        source_identifier=source_identifier, admission_method=ADMISSION_METHOD_APPROVED_PROVIDER,
        version=version, publication_date=publication_date,
        coverage_start=coverage_start, coverage_end=coverage_end,
        market=market, timezone=timezone, raw_content=raw_content, artifact_digest=_digest(raw_content),
        attested_by=None, attested_at=None,
    )


def admit_source_via_operator_attestation(
    *, source_identifier: str, operator_name: str, attested_at: str, version: str,
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
    return AdmittedCalendarSource(
        source_identifier=source_identifier, admission_method=ADMISSION_METHOD_OPERATOR_ATTESTATION,
        version=version, publication_date=publication_date,
        coverage_start=coverage_start, coverage_end=coverage_end,
        market=market, timezone=timezone, raw_content=raw_content, artifact_digest=_digest(raw_content),
        attested_by=operator_name, attested_at=attested_at,
    )
