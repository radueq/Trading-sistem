# Spec #001 -- Acceptance Record

**Status: ACCEPTED**
**Baseline commit: `918f3f7`**
**Branch: `claude/dazzling-cori-kbgf23`**
**Accepted by: Radu**
**Date: 2026-09-21**

## Result

```
23 PASS / 1 SKIPPED (PENDING_LEVEL_2_DATA) / 0 FAIL
```

Full breakdown: `docs/test_report.md`.

## Review chain (Spec #001 SS29)

1. Claude Code implementation -- `6e456ca` (initial), `8492ade` (knowledge-time patch), `bc4c914` (PATCH A/B), `918f3f7` (persistence lifecycle fix).
2. Claude review (inline, throughout).
3. GPT architecture / data-leakage review -- three rounds:
   - Review #001 on `6e456ca`: corporate action status materialization corrected to query-time derivation (Radu, 2026-09-20) before GPT review; knowledge-time (`available_at`) correction requested (Radu, 2026-09-21) and applied at `8492ade`.
   - Review #001 on `8492ade`: PATCH A (cancelled actions could leak into the adjusted series) and PATCH B (listing_status knowledge-time gap) found and fixed at `bc4c914`.
   - Final Review #001 on `bc4c914`: persistence-lifecycle bug found (`INSERT OR IGNORE` could silently drop a real re-ingested revision) and fixed at `918f3f7`.
4. Radu sign-off: **ACCEPTED** at `918f3f7`, this record.

## Scope going forward

Per Radu's acceptance note (2026-09-21): no further patches are requested
against Spec #001. Next step is Spec #002. **Data Foundation (this
module) should not be modified in parallel with Spec #002 work unless
#002 discovers a missing interface or a real defect** -- not for
speculative improvement. The items in `docs/known_limitations.md` remain
accepted, documented gaps, not open work items, unless and until a
concrete downstream need forces one of them.
