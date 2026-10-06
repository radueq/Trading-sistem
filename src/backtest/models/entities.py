"""Spec #005 v1.0 -- typed contracts owned by #005 (Batch 1 + Batch 2).

Every entity here is frozen and content-addressed the same way #003/#004
already do: an identity field (`*_id`) and a `*_hash` are pure functions
of the entity's own ECONOMIC fields, administrative timestamps/approvers
excluded (Spec #005 SS21: "Exclude created_at and wall-clock performance
from semantic identity"). Nothing in this module reads #001 data or
imports evaluation/discovery/hypothesis internals beyond the two
explicitly-approved reuses (`build_run_id`, `check_provenance_matches_run`)
that live in `backtest.provenance.evaluation_run`, not here --
`HistoricalObservationCache.observations` is typed as a bare `tuple`
(never `tuple[DiscoveryObservation, ...]`) specifically to keep this
rule intact; the real type lives only in `backtest.data.cache`.

This module is CONTRACTS ONLY (Spec #005 SS24): no engine, no execution.
Batch 2 adds `StageAccessBoundary` (the scope contract) but the actual
PIT-touching facade/snapshot/cache logic lives under `backtest.data.*`,
never here. Later batches add the modules that actually replay sessions
and build trades.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date, time
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from evaluation.models.entities import EvaluationRunRegistry

from data_foundation.calendar.entities import (
    CalendarCoverageIncompleteError,
    CalendarNotVerifiedError,
    CalendarSource,
    TradingCalendar,
    build_calendar_id,
    calendar_fingerprint,
    verify_calendar_content_address,
    verify_calendar_structure,
)


def canonical_json(value) -> str:
    """Structured, delimiter-free serialization for #005's OWN new
    fingerprints and canonical records (GPT review, Batch 1 patch:
    hand-rolled `"::"`/`","` string-concatenation delimiters can collide
    -- two structurally different inputs, e.g. differing lists of
    free-text strings containing commas, can serialize to the identical
    string). Public (no leading underscore) because Batch 2's
    `backtest.data.snapshot` reuses this SAME recipe for its own
    streaming content-hash records -- one canonicalization rule, not a
    second divergent copy. Does NOT apply to the legacy #003
    `build_run_id()` or #004 `hypothesis_fingerprint()`/
    `variant_fingerprint()` recipes -- those stay unchanged, out of
    scope."""
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_HH_MM_RE = re.compile(r"^\d{2}:\d{2}$")


def parse_iso_date(value) -> Optional[date]:
    """Strict canonical `YYYY-MM-DD` parsing ONLY. GPT Batch 1 patch
    review (P1 finding, second round): `datetime.date.fromisoformat()`
    alone also accepts ISO week dates ("2024W011") and unpadded basic
    format ("20240101"), which parse to a DIFFERENT calendar date than
    the string suggests and do not sort correctly against canonical
    `YYYY-MM-DD` strings -- e.g. "2024-12-31" < "2024W011" lexically even
    though 2024W011 == 2024-01-01, chronologically BEFORE. That let a
    `validation_start` slip before `formation_end` undetected. The
    regex pre-check closes the loophole; used by every date/period/
    calendar check in this module, `backtest.zones.boundaries`, and
    `backtest.data.calendar` -- ONE recipe, not three divergent ones."""
    if not isinstance(value, str) or not _ISO_DATE_RE.match(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_hh_mm(value) -> Optional[time]:
    if not isinstance(value, str) or not _HH_MM_RE.match(value):
        return None
    try:
        return time.fromisoformat(value)
    except ValueError:
        return None


def _is_valid_timezone(value) -> bool:
    if not isinstance(value, str):
        return False
    try:
        ZoneInfo(value)
        return True
    except (ZoneInfoNotFoundError, ValueError):
        return False


def _is_strict_positive_int(value) -> bool:
    """`bool` is a subclass of `int` in Python -- `isinstance(x, int)`
    alone silently accepts `True`/`False` as if they were valid trade
    counts."""
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


# --------------------------------------------------------------------------
# Calendar (Spec #005 SS11) -- RELOCATED to `data_foundation.calendar.
# entities` (joint remediation design 003+004, section 2; decision
# registry B4, revision 5; authorized 2026-10-06, Stage 2).
# `CalendarSource`, `TradingCalendar`, `calendar_fingerprint`,
# `build_calendar_id`, `verify_calendar_content_address`,
# `verify_calendar_structure`, `CalendarNotVerifiedError`,
# `CalendarCoverageIncompleteError` are imported above and re-exported
# here UNCHANGED, so every existing import site
# (`from backtest.models.entities import ...`) keeps working without
# modification -- a pure relocation, not a behavior change. New code
# (Spec #003 Evaluation) imports directly from `data_foundation.
# calendar.entities` instead, so `evaluation` never needs to import
# `backtest` for this.
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# Execution semantics (Spec #005 SS9)
# --------------------------------------------------------------------------

ENTRY_FILL_V1 = "NEXT_SESSION_OPEN"
INVALIDATION_DETECTION_V1 = "COMPLETED_BAR_CLOSE"
INVALIDATION_FILL_V1 = "NEXT_SESSION_OPEN_AFTER_DETECTION"
TIME_EXIT_FILL_V1 = "SCHEDULED_HOLDING_BAR_CLOSE"
CAP_FILL_V1 = "SCHEDULED_MAX_HOLDING_BAR_CLOSE"
CAP_IS_HARD_V1 = True


@dataclass(frozen=True)
class ExecutionSemanticsProfile:
    """Spec #005 SS9: "Define immutable ExecutionSemanticsProfile v1...
    The profile hash enters run and selection identities. It is common
    to all compared variants and cannot be tuned after results." Binds
    the actual fill timing on top of #004's own frozen `ExitHypothesis`
    fields (`exit_execution_policy="BAR_CLOSE"` stays verbatim on #004's
    side; SS9's confirmed reading is that it denotes scheduled execution
    for TIME_EXIT/cap and detection timing only for reactive
    invalidation -- this profile is what supplies the deferred fill for
    the latter). #004 is never patched for this."""
    profile_id: str
    profile_hash: str

    entry_fill: str
    invalidation_detection: str
    invalidation_fill: str
    time_exit_fill: str
    cap_fill: str
    cap_is_hard: bool


def execution_semantics_fingerprint(
    entry_fill: str, invalidation_detection: str, invalidation_fill: str,
    time_exit_fill: str, cap_fill: str, cap_is_hard: bool,
) -> str:
    payload = {
        "entry_fill": entry_fill,
        "invalidation_detection": invalidation_detection,
        "invalidation_fill": invalidation_fill,
        "time_exit_fill": time_exit_fill,
        "cap_fill": cap_fill,
        "cap_is_hard": cap_is_hard,
    }
    return canonical_json(payload)


def build_execution_semantics_profile_id(fingerprint: str) -> tuple[str, str]:
    digest = hashlib.sha256(fingerprint.encode()).hexdigest()[:16]
    return f"exsem_{digest}", digest


def verify_execution_semantics_profile_v1(profile: ExecutionSemanticsProfile) -> tuple[bool, tuple[str, ...]]:
    """Re-derives the fingerprint/id from the profile's OWN stored
    fields and requires BOTH a content-address match and a literal match
    to the 6 frozen V1 constants -- `frozen=True` blocks in-place
    mutation but not construction of a self-inconsistent or non-V1
    object via `dataclasses.replace()`."""
    errors: list[str] = []
    for name, actual, expected in (
        ("entry_fill", profile.entry_fill, ENTRY_FILL_V1),
        ("invalidation_detection", profile.invalidation_detection, INVALIDATION_DETECTION_V1),
        ("invalidation_fill", profile.invalidation_fill, INVALIDATION_FILL_V1),
        ("time_exit_fill", profile.time_exit_fill, TIME_EXIT_FILL_V1),
        ("cap_fill", profile.cap_fill, CAP_FILL_V1),
        ("cap_is_hard", profile.cap_is_hard, CAP_IS_HARD_V1),
    ):
        if actual != expected:
            errors.append(f"{name} must be {expected!r} in V1, got {actual!r}")

    fp = execution_semantics_fingerprint(
        profile.entry_fill, profile.invalidation_detection, profile.invalidation_fill,
        profile.time_exit_fill, profile.cap_fill, profile.cap_is_hard,
    )
    expected_id, expected_hash = build_execution_semantics_profile_id(fp)
    if profile.profile_id != expected_id or profile.profile_hash != expected_hash:
        errors.append(
            f"profile content-address mismatch: stored profile_id={profile.profile_id!r}/"
            f"profile_hash={profile.profile_hash!r} does not match the id/hash recomputed from "
            f"the profile's own fields ({expected_id!r}/{expected_hash!r})"
        )
    return (not errors, tuple(errors))


def build_execution_semantics_profile_v1() -> ExecutionSemanticsProfile:
    """The ONE profile V1 defines -- not a free parameter, never
    constructed with different field values in application code. Tests
    may construct a deliberately-tampered profile to prove fingerprint
    sensitivity, but no production caller does."""
    fp = execution_semantics_fingerprint(
        ENTRY_FILL_V1, INVALIDATION_DETECTION_V1, INVALIDATION_FILL_V1,
        TIME_EXIT_FILL_V1, CAP_FILL_V1, CAP_IS_HARD_V1,
    )
    profile_id, digest = build_execution_semantics_profile_id(fp)
    return ExecutionSemanticsProfile(
        profile_id=profile_id, profile_hash=digest,
        entry_fill=ENTRY_FILL_V1, invalidation_detection=INVALIDATION_DETECTION_V1,
        invalidation_fill=INVALIDATION_FILL_V1, time_exit_fill=TIME_EXIT_FILL_V1,
        cap_fill=CAP_FILL_V1, cap_is_hard=CAP_IS_HARD_V1,
    )


# --------------------------------------------------------------------------
# Selection rule (Spec #005 SS18)
# --------------------------------------------------------------------------

RANKING_METRIC_V1 = "MEDIAN_NET_RETURN"
# Spec #005 Exit Amendment v1.0 (docs/spec005_exit_amendment_v1.0.md,
# ACCEPTED, section 11) -- additive: a SECOND allowed ranking_metric,
# mandatory (not optional) for any ResearchPlan whose hypothesis cohort
# includes STOP_MANAGED_INVALIDATION variants. RANKING_METRIC_V1 stays
# the only allowed value for a plan composed exclusively of old families
# -- see `backtest.exits.plan_integration.validate_stop_managed_plan_
# requirements()` for the family-aware cross-check this module itself
# deliberately never performs (this file stays family-agnostic).
RANKING_METRIC_STOP_MANAGED_V1 = "MEDIAN_NET_RETURN_TO_EXIT_OR_STAGE_END"
THRESHOLD_OPERATOR_V1 = "STRICTLY_GREATER"
TIE_BREAK_V1 = "LEXICOGRAPHIC_STRATEGY_VARIANT_ID"
MINIMUM_SELECTION_METRIC_V1 = 0.0


@dataclass(frozen=True)
class SelectionRule:
    """Spec #005 SS18: "Freeze SelectionRule before any #005 outcome
    replay... These support thresholds are design inputs, not knobs to
    fit after seeing returns." `ranking_metric`/`threshold_operator`/
    `tie_break`/`minimum_selection_metric` are fixed V1 values (no
    Sharpe/drawdown/win-rate tie-break, ever) -- only the three support
    thresholds are run-specific inputs, and they are REQUIRED (no
    default), mirroring #004's `HorizonCandidateSet.parameter_source`
    discipline: a caller must state them, never rely on a silently
    "reasonable" default."""
    minimum_executed_trades: int
    minimum_evaluable_trades: int
    minimum_evaluable_ratio: float
    ranking_metric: str = RANKING_METRIC_V1
    minimum_selection_metric: float = MINIMUM_SELECTION_METRIC_V1
    threshold_operator: str = THRESHOLD_OPERATOR_V1
    tie_break: str = TIE_BREAK_V1
    # Amendment section 11 (closure verification gap, post-9feb4a5): named
    # explicitly as OPTIONAL on SelectionRule -- "a declared-adequacy
    # requirement... NOT a remedy for selection bias" (the remedy is
    # MEDIAN_NET_RETURN_TO_EXIT_OR_STAGE_END itself, which already
    # includes evaluable censored positions). "Optional" means a plan MAY
    # leave it unset, never that support for the field itself may be
    # missing -- `None` (unset) is the default and produces a
    # byte-identical `research_plan_fingerprint()` to every plan built
    # before this field existed (see the fingerprint function itself:
    # only entered into the payload when not None). Enforcing this ratio
    # against a real cohort at selection time is a SEPARATE, not yet built
    # orchestration step (see backtest.exits.taxonomy's own censored_ratio/
    # evaluable_ratio computation) -- this field only carries the
    # declared threshold and its identity/validation, nothing else.
    maximum_censored_ratio: Optional[float] = None


def validate_selection_rule(rule: SelectionRule) -> tuple[bool, tuple[str, ...]]:
    errors: list[str] = []
    if not _is_strict_positive_int(rule.minimum_executed_trades):
        errors.append(f"minimum_executed_trades must be a positive integer, got {rule.minimum_executed_trades!r}")
    if not _is_strict_positive_int(rule.minimum_evaluable_trades):
        errors.append(f"minimum_evaluable_trades must be a positive integer, got {rule.minimum_evaluable_trades!r}")
    if not (0 < rule.minimum_evaluable_ratio <= 1):
        errors.append(f"minimum_evaluable_ratio must be in (0,1], got {rule.minimum_evaluable_ratio!r}")
    if rule.ranking_metric not in (RANKING_METRIC_V1, RANKING_METRIC_STOP_MANAGED_V1):
        errors.append(
            f"ranking_metric must be {RANKING_METRIC_V1!r} or {RANKING_METRIC_STOP_MANAGED_V1!r}, got "
            f"{rule.ranking_metric!r} (SS18 -- no hidden Sharpe/drawdown/win-rate metric; the second "
            f"value is the Spec #005 Exit Amendment v1.0 addition, mandatory -- not merely allowed -- "
            f"whenever the cohort includes STOP_MANAGED_INVALIDATION variants, see backtest.exits."
            f"plan_integration)"
        )
    if rule.minimum_selection_metric != MINIMUM_SELECTION_METRIC_V1:
        errors.append(f"minimum_selection_metric must be {MINIMUM_SELECTION_METRIC_V1!r} in V1, got {rule.minimum_selection_metric!r}")
    if rule.threshold_operator != THRESHOLD_OPERATOR_V1:
        errors.append(f"threshold_operator must be {THRESHOLD_OPERATOR_V1!r} in V1, got {rule.threshold_operator!r}")
    if rule.tie_break != TIE_BREAK_V1:
        errors.append(f"tie_break must be {TIE_BREAK_V1!r} in V1, got {rule.tie_break!r}")
    if rule.maximum_censored_ratio is not None:
        if not _is_finite_number(rule.maximum_censored_ratio) or not (0 <= rule.maximum_censored_ratio <= 1):
            errors.append(
                f"maximum_censored_ratio must be None (unset) or a finite number in [0,1], got "
                f"{rule.maximum_censored_ratio!r} (amendment section 11 -- optional field, not optional support)"
            )
    return (not errors, tuple(errors))


# --------------------------------------------------------------------------
# Cost assumptions (Spec #005 SS13)
# --------------------------------------------------------------------------

BORROW_ACCRUAL_CONVENTION_V1 = "CALENDAR_DAYS_365"


@dataclass(frozen=True)
class CostAssumptions:
    """Spec #005 SS13: "Base cost assumptions are mandatory frozen
    inputs." `label` distinguishes the one frozen BASE scenario (used
    for selection) from later cost-sensitivity scenarios (SS13/SS23's
    CostSensitivityReport, a later batch) -- sensitivity scenarios reuse
    identical events/trades and are never a selection trial (SS13:
    "Selection always uses the one frozen base scenario")."""
    commission_entry_rate: float
    commission_exit_rate: float
    slippage_entry_bps: float
    slippage_exit_bps: float
    borrow_annual_rate: float
    borrow_accrual_convention: str = BORROW_ACCRUAL_CONVENTION_V1
    label: str = "BASE"


def validate_cost_assumptions(costs: CostAssumptions) -> tuple[bool, tuple[str, ...]]:
    """SS13: "Restrict rates to finite nonnegative values producing
    positive fills." A slippage fraction >= 1.0 (10000 bps) would drive
    `F_e`/`F_x` to zero or negative in the SS13 fill formulas -- rejected
    here, before any fill is ever computed."""
    errors: list[str] = []
    for name, value in (
        ("commission_entry_rate", costs.commission_entry_rate),
        ("commission_exit_rate", costs.commission_exit_rate),
        ("slippage_entry_bps", costs.slippage_entry_bps),
        ("slippage_exit_bps", costs.slippage_exit_bps),
        ("borrow_annual_rate", costs.borrow_annual_rate),
    ):
        if not _is_finite_number(value) or value < 0:
            errors.append(f"{name} must be a finite, nonnegative number, got {value!r}")
    if costs.slippage_entry_bps >= 10000 or costs.slippage_exit_bps >= 10000:
        errors.append("slippage_entry_bps/slippage_exit_bps must be < 10000 (100%) -- a fill must stay positive (SS13)")
    if costs.borrow_accrual_convention != BORROW_ACCRUAL_CONVENTION_V1:
        errors.append(f"borrow_accrual_convention must be {BORROW_ACCRUAL_CONVENTION_V1!r} in V1, got {costs.borrow_accrual_convention!r}")
    return (not errors, tuple(errors))


def _is_finite_number(value: float) -> bool:
    return isinstance(value, (int, float)) and value == value and value not in (float("inf"), float("-inf"))


# --------------------------------------------------------------------------
# Exposure and evidence archival (Spec #005 SS3-4)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ExposureManifest:
    """Spec #005 SS3: "Record other known manual/agent inspection in an
    ExposureManifest. Prior views of validation outcomes invalidate an
    UNSEEN claim." `declared_unseen` is an explicit, positive claim --
    never the default absence of a disclosure -- so a caller must state
    it, not have it inferred from an empty list."""
    declared_unseen: bool
    prior_validation_disclosures: tuple[str, ...] = field(default_factory=tuple)


def validate_exposure_manifest(manifest: ExposureManifest) -> tuple[bool, tuple[str, ...]]:
    if manifest.declared_unseen and manifest.prior_validation_disclosures:
        return False, (
            "declared_unseen=True but prior_validation_disclosures is non-empty -- "
            "a prior disclosure invalidates an UNSEEN claim (Spec #005 SS3)",
        )
    return True, ()


@dataclass(frozen=True)
class DataCapabilityManifest:
    """Spec #005 SS5: "Provider, Level 1/2, survivorship/delisting
    support, knowledge-time quality, return basis, limitations." """
    data_provider: str
    data_level: str  # "LEVEL_1" | "LEVEL_2"
    survivorship_delisting_support: str
    knowledge_time_quality: str
    return_basis: str  # fixed "SPLIT_ADJUSTED_PRICE_RETURN" in V1 (SS12)
    limitations: tuple[str, ...] = field(default_factory=tuple)


RETURN_BASIS_V1 = "SPLIT_ADJUSTED_PRICE_RETURN"


@dataclass(frozen=True)
class EvaluationRunCrossCheckResult:
    """One hypothesis's full provenance guard result (Spec #005 SS4):
    legacy 8-field hash consistency + `check_provenance_matches_run()`
    linkage + `mode` + `benchmark_security_id`. `hash_consistent=True`
    proves only that the supplied `EvaluationRunRegistry` fields
    reproduce its own claimed `evaluation_run_id` -- SS4: "It does not
    authenticate the object, prove that a historical run occurred,
    establish that data were unseen, or detect coordinated replacement
    of both fields and ID. It is not an anti-forgery certificate."""
    hypothesis_id: str
    evaluation_run_id: str
    hash_consistent: bool
    linkage_ok: bool
    mode_ok: bool
    benchmark_ok: bool
    errors: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return self.hash_consistent and self.linkage_ok and self.mode_ok and self.benchmark_ok and not self.errors


@dataclass(frozen=True)
class EvidenceInputBundle:
    """Spec #005 SS4/SS5: "Archive the complete registry and
    configuration artifacts in EvidenceInputBundle... Existing
    config-consistency checks still apply; audit retention is not
    permission to ignore a known inconsistency." `run_registries` stores
    the FULL objects (including fields the 8-field hash and
    `check_provenance_matches_run()` don't cover -- `horizons`,
    `bootstrap_iterations`, `comparison_iterations`,
    `multiple_testing_method`, `created_at` -- for audit, not as a
    substitute for the explicit guards in `cross_check_results`)."""
    hypothesis_ids: tuple[str, ...]
    run_registries: tuple[EvaluationRunRegistry, ...]
    cross_check_results: tuple[EvaluationRunCrossCheckResult, ...]

    @property
    def all_ok(self) -> bool:
        """Vacuous truth guard: `all()` over an empty/incomplete
        `cross_check_results` must never read as "all ok". Requires:
        (1) `hypothesis_ids` itself has no duplicates -- a declared
        cohort cannot list the same hypothesis twice (GPT Batch 1 patch
        review, second round: the old set-based comparison silently
        collapsed this); (2) `run_registries` has no two entries sharing
        an `evaluation_run_id` -- two different archived objects
        claiming the same run id is ambiguous, never valid; (3) EXACTLY
        one cross-check result per declared `hypothesis_id` (no missing,
        no extra, no duplicate); (4) every cross-check result's
        `evaluation_run_id` is actually present in `run_registries` --
        a result marked `ok=True` whose run was never archived is
        incomplete evidence, not verified evidence. Multiple hypotheses
        MAY legitimately share one archived run; no one-to-one
        relationship between hypotheses and registries is imposed."""
        if not self.hypothesis_ids:
            return False
        if len(self.hypothesis_ids) != len(set(self.hypothesis_ids)):
            return False

        registry_ids = [r.evaluation_run_id for r in self.run_registries]
        if len(registry_ids) != len(set(registry_ids)):
            return False
        registry_id_set = set(registry_ids)

        covered_ids = [r.hypothesis_id for r in self.cross_check_results]
        if len(covered_ids) != len(set(covered_ids)):
            return False
        if set(covered_ids) != set(self.hypothesis_ids):
            return False

        if any(r.evaluation_run_id not in registry_id_set for r in self.cross_check_results):
            return False

        return all(r.ok for r in self.cross_check_results)


# --------------------------------------------------------------------------
# ResearchPlan (Spec #005 SS3/SS5)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class SelectionFold:
    """Spec #005 SS16: "SELECTION_DIAGNOSTIC_FOLDS, not independent
    walk-forward validation." 2-3 frozen chronological bins for
    descriptive diagnostics only -- never a per-fold retuning
    mechanism."""
    fold_id: str
    start_date: str
    end_date: str


@dataclass(frozen=True)
class ResearchPlan:
    """Spec #005 SS3: "ResearchPlan is frozen before outcome replay...
    explicit inclusive zone dates, session calendar, hypothesis cohort,
    immutable configuration artifacts, costs, selection rule, fold
    boundaries and approval/provenance metadata." `plan_hash` excludes
    `created_at`/`created_by` (SS21: "Exclude created_at and wall-clock
    performance from semantic identity")."""
    research_plan_id: str
    plan_hash: str

    formation_start: str
    formation_end: str
    validation_start: str
    validation_end: str
    locked_oos_start: str

    selection_folds: tuple[SelectionFold, ...]
    hypothesis_cohort_ids: tuple[str, ...]

    trading_calendar_id: str
    benchmark_security_id: str
    execution_semantics_profile_id: str
    selection_rule: SelectionRule
    cost_assumptions: CostAssumptions
    exposure_manifest: ExposureManifest

    created_at: str
    created_by: str

    # Spec #005 Exit Amendment v1.0 (ACCEPTED, section 7) -- additive,
    # family-conditioned (GPT review round 2, finding #7): required
    # whenever the plan's hypothesis cohort includes STOP_MANAGED_
    # INVALIDATION variants (see `backtest.exits.plan_integration.
    # accept_research_plan()`), left `None` for a plan
    # built exclusively from old families -- and excluded from the
    # fingerprint payload in exactly that case (`research_plan_
    # fingerprint()` below), so an existing plan's identity is
    # byte-for-byte unaffected by this field's mere existence.
    stop_managed_execution_semantics_profile_id: Optional[str] = None


def research_plan_fingerprint(
    formation_start: str, formation_end: str, validation_start: str, validation_end: str, locked_oos_start: str,
    selection_folds: tuple[SelectionFold, ...], hypothesis_cohort_ids: tuple[str, ...],
    trading_calendar_id: str, benchmark_security_id: str, execution_semantics_profile_id: str,
    selection_rule: SelectionRule, cost_assumptions: CostAssumptions, exposure_manifest: ExposureManifest,
    stop_managed_execution_semantics_profile_id: Optional[str] = None,
) -> str:
    payload = {
        "formation_start": formation_start,
        "formation_end": formation_end,
        "validation_start": validation_start,
        "validation_end": validation_end,
        "locked_oos_start": locked_oos_start,
        "selection_folds": sorted([f.fold_id, f.start_date, f.end_date] for f in selection_folds),
        "hypothesis_cohort_ids": sorted(hypothesis_cohort_ids),
        "trading_calendar_id": trading_calendar_id,
        "benchmark_security_id": benchmark_security_id,
        "execution_semantics_profile_id": execution_semantics_profile_id,
        "selection_rule": {
            "minimum_executed_trades": selection_rule.minimum_executed_trades,
            "minimum_evaluable_trades": selection_rule.minimum_evaluable_trades,
            "minimum_evaluable_ratio": selection_rule.minimum_evaluable_ratio,
            "ranking_metric": selection_rule.ranking_metric,
            "minimum_selection_metric": selection_rule.minimum_selection_metric,
            "threshold_operator": selection_rule.threshold_operator,
            "tie_break": selection_rule.tie_break,
            **(
                {"maximum_censored_ratio": selection_rule.maximum_censored_ratio}
                if selection_rule.maximum_censored_ratio is not None else {}
            ),
        },
        "cost_assumptions": {
            "commission_entry_rate": cost_assumptions.commission_entry_rate,
            "commission_exit_rate": cost_assumptions.commission_exit_rate,
            "slippage_entry_bps": cost_assumptions.slippage_entry_bps,
            "slippage_exit_bps": cost_assumptions.slippage_exit_bps,
            "borrow_annual_rate": cost_assumptions.borrow_annual_rate,
            "borrow_accrual_convention": cost_assumptions.borrow_accrual_convention,
            "label": cost_assumptions.label,
        },
        "exposure_manifest": {
            "prior_validation_disclosures": sorted(exposure_manifest.prior_validation_disclosures),
            "declared_unseen": exposure_manifest.declared_unseen,
        },
    }
    if stop_managed_execution_semantics_profile_id is not None:
        payload["stop_managed_execution_semantics_profile_id"] = stop_managed_execution_semantics_profile_id
    return canonical_json(payload)


def build_research_plan_id(fingerprint: str) -> tuple[str, str]:
    digest = hashlib.sha256(fingerprint.encode()).hexdigest()[:16]
    return f"plan_{digest}", digest


def verify_research_plan_identity(plan: ResearchPlan) -> tuple[bool, tuple[str, ...]]:
    """Recomputes `research_plan_fingerprint()` from the plan's OWN
    stored fields and compares it to `plan.research_plan_id`/
    `plan.plan_hash` -- catches a plan modified after freezing (e.g. via
    `dataclasses.replace()`), the same bug class PATCH #004-B fixed for
    StrategyHypothesis/StrategyVariant."""
    fp = research_plan_fingerprint(
        plan.formation_start, plan.formation_end, plan.validation_start, plan.validation_end,
        plan.locked_oos_start, plan.selection_folds, plan.hypothesis_cohort_ids,
        plan.trading_calendar_id, plan.benchmark_security_id, plan.execution_semantics_profile_id,
        plan.selection_rule, plan.cost_assumptions, plan.exposure_manifest,
        plan.stop_managed_execution_semantics_profile_id,
    )
    expected_id, expected_hash = build_research_plan_id(fp)
    if plan.research_plan_id != expected_id or plan.plan_hash != expected_hash:
        return False, (
            f"research plan content-address mismatch: stored research_plan_id={plan.research_plan_id!r}/"
            f"plan_hash={plan.plan_hash!r} does not match the id/hash recomputed from the plan's own "
            f"fields ({expected_id!r}/{expected_hash!r})",
        )
    return True, ()


# --------------------------------------------------------------------------
# Stage access boundary (Spec #005 SS3/SS6, Batch 2): "Selection must not
# inspect or hash validation/OOS price content. A plan can commit future
# window boundaries without opening those data." "LOCKED_OOS: No reads,
# evaluation or release in #005 V1." Because #001's PIT gateway
# (`get_price_series_as_of`) has no LOWER as_of bound -- it always
# returns full history up to `as_of` -- bounding the single upper edge
# (`max_as_of`) is sufficient and necessary to guarantee no fact dated
# after it can ever be read; warm-up before the zone's own start is
# unrestricted by design (SS3: "Warm-up data before a zone may be read
# to compute already-frozen rolling features").
# --------------------------------------------------------------------------

FORMATION_SELECTION = "FORMATION_SELECTION"
DEVELOPMENT_VALIDATION = "DEVELOPMENT_VALIDATION"
LOCKED_OOS = "LOCKED_OOS"
_STAGE_ZONES_V1 = (FORMATION_SELECTION, DEVELOPMENT_VALIDATION, LOCKED_OOS)


class LockedOOSAccessError(ValueError):
    """Raised the instant a LOCKED_OOS boundary is constructed -- never
    deferred to a first query. SS3: "No reads, evaluation or release in
    #005 V1" is not a runtime policy to remember to enforce per-call; it
    is unconditional, so the object that would permit it cannot exist."""
    pass


class OutOfScopeAccessError(ValueError):
    """Raised when a query's `as_of` exceeds a `StageAccessBoundary`'s
    `max_as_of` -- the mechanical enforcement of SS3's "Selection must
    not inspect or hash validation/OOS price content." """
    pass


@dataclass(frozen=True)
class StageAccessBoundary:
    """The zone-scoped upper bound on every #005-initiated PIT/discovery
    read for one stage. `zone` is `FORMATION_SELECTION` or
    `DEVELOPMENT_VALIDATION` only -- constructing one for `LOCKED_OOS`
    raises immediately (see `LockedOOSAccessError`). `max_as_of` is that
    zone's own end date (`formation_end` or `validation_end`); no query
    through this boundary may ever use an `as_of` after it."""
    zone: str
    max_as_of: str

    def __post_init__(self):
        if self.zone == LOCKED_OOS:
            raise LockedOOSAccessError(
                "LOCKED_OOS: no StageAccessBoundary may ever be constructed for this zone -- "
                "Spec #005 V1 permits no reads, evaluation or release of Locked OOS data"
            )
        if self.zone not in _STAGE_ZONES_V1:
            raise ValueError(f"zone must be one of {_STAGE_ZONES_V1!r}, got {self.zone!r}")
        if parse_iso_date(self.max_as_of) is None:
            raise ValueError(f"max_as_of is not a valid ISO date: {self.max_as_of!r}")

    def require_as_of_in_scope(self, as_of: str) -> None:
        if parse_iso_date(as_of) is None:
            raise OutOfScopeAccessError(f"as_of is not a valid ISO date: {as_of!r}")
        if as_of > self.max_as_of:
            raise OutOfScopeAccessError(
                f"OUT_OF_SCOPE_ACCESS: as_of={as_of!r} exceeds this {self.zone} boundary's "
                f"max_as_of={self.max_as_of!r} -- validation/OOS price content may never be "
                f"inspected or hashed from this stage (Spec #005 SS3/SS6)"
            )


class StageBoundaryPlanMismatchError(ValueError):
    """Raised by `backtest.zones.boundaries.build_stage_access_boundary_from_plan()`
    when `zone` is not one that function derives a boundary for, the
    plan fails identity re-verification, or the plan's own zone dates
    fail `verify_zone_ordering()` (Batch 2 patch round-3 review: a plan
    with a self-consistent hash can still have overlapping/invalid zone
    dates -- identity alone was never a substitute for checking that).
    Lives here, not in `zones.boundaries`, purely so
    `StageAccessBoundary`'s own docstring can reference the one error
    type it and its plan-derived factory share; the factory function
    itself lives in `zones.boundaries` because it must call
    `verify_zone_ordering()`, and `boundaries` already imports from
    this module -- importing the other way around would be circular."""
    pass


# --------------------------------------------------------------------------
# Data snapshot identity (Spec #005 SS5/SS6, Batch 2): "Freeze or open a
# consistent read snapshot for the entire run. Hash exactly that
# snapshot... Use streaming SHA-256 over canonical typed records."
# --------------------------------------------------------------------------

CANONICALIZATION_VERSION_V1 = "canon_v1"
SNAPSHOT_FACT_CATEGORIES_V1 = ("PRICE_BARS", "CORPORATE_ACTIONS", "LISTING_STATUS", "SYMBOL_HISTORY", "SECURITY_MASTER")
NOT_REPLAYABLE_FROM_RETAINED_DATA = "NOT_REPLAYABLE_FROM_RETAINED_DATA"


@dataclass(frozen=True)
class DataSnapshotManifest:
    """Spec #005 SS5: "Scope, table/field manifests, canonicalization
    version, content digest, replay artifact reference." `content_digest`
    is the actual streaming SHA-256 over every canonical record read
    through a `StageAccessBoundary`-bounded facade (SS6) -- the "proof"
    value. `snapshot_id`/`snapshot_hash` are this MANIFEST's own
    content-address (SS21 discipline), derived from `content_digest` plus
    the declared scope, so a `dataclasses.replace()`-tampered manifest
    (e.g. widening `security_ids` after the fact while keeping the old
    digest) is detectable the same way as every other #005 entity (see
    `verify_snapshot_content_address()`). `replayable` is fixed to
    `NOT_REPLAYABLE_FROM_RETAINED_DATA` in Batch 2 -- no retained-extract
    storage mechanism exists yet (SS6: "Otherwise label the run
    NOT_REPLAYABLE_FROM_RETAINED_DATA"); `replay_artifact_reference`
    stays unset until a later batch builds one. `min_as_of` (Batch 2
    patch round-4 review, finding #3) is the explicit, caller-declared
    start of the authorized history window (typically the run's own
    warm-up start) -- SYMBOL_HISTORY/LISTING_STATUS are only hashed for
    calendar session dates inside `[min_as_of, max_as_of]`, and the
    observation cache (`backtest.data.cache`) rejects any `as_of`
    outside that same declared window, so the domain of permitted reads
    always matches the domain this manifest actually attests to."""
    snapshot_id: str
    snapshot_hash: str

    stage: str  # FORMATION_SELECTION | DEVELOPMENT_VALIDATION
    security_ids: tuple[str, ...]  # sorted, deduplicated, benchmark included
    benchmark_security_id: str
    min_as_of: str
    max_as_of: str
    trading_calendar_id: str

    table_field_manifest: tuple[str, ...]
    canonicalization_version: str
    content_digest: str

    replayable: str = NOT_REPLAYABLE_FROM_RETAINED_DATA
    replay_artifact_reference: Optional[str] = None


def snapshot_manifest_fingerprint(
    stage: str, security_ids: tuple[str, ...], benchmark_security_id: str, min_as_of: str, max_as_of: str,
    trading_calendar_id: str, table_field_manifest: tuple[str, ...], canonicalization_version: str,
    content_digest: str, replayable: str, replay_artifact_reference: Optional[str],
) -> str:
    payload = {
        "stage": stage,
        "security_ids": sorted(security_ids),
        "benchmark_security_id": benchmark_security_id,
        "min_as_of": min_as_of,
        "max_as_of": max_as_of,
        "trading_calendar_id": trading_calendar_id,
        "table_field_manifest": sorted(table_field_manifest),
        "canonicalization_version": canonicalization_version,
        "content_digest": content_digest,
        "replayable": replayable,
        "replay_artifact_reference": replay_artifact_reference,
    }
    return canonical_json(payload)


def build_snapshot_id(fingerprint: str) -> tuple[str, str]:
    digest = hashlib.sha256(fingerprint.encode()).hexdigest()[:16]
    return f"snap_{digest}", digest


def verify_snapshot_content_address(manifest: DataSnapshotManifest) -> tuple[bool, tuple[str, ...]]:
    """Recomputes the fingerprint from the manifest's OWN stored fields
    and compares it to `manifest.snapshot_id`/`manifest.snapshot_hash` --
    catches a manifest modified after construction (e.g. via
    `dataclasses.replace()` widening `security_ids` or swapping
    `content_digest` while keeping the old id), the same bug class
    PATCH #004-B fixed once for StrategyHypothesis/StrategyVariant."""
    fp = snapshot_manifest_fingerprint(
        manifest.stage, manifest.security_ids, manifest.benchmark_security_id, manifest.min_as_of,
        manifest.max_as_of, manifest.trading_calendar_id, manifest.table_field_manifest,
        manifest.canonicalization_version, manifest.content_digest, manifest.replayable,
        manifest.replay_artifact_reference,
    )
    expected_id, expected_hash = build_snapshot_id(fp)
    if manifest.snapshot_id != expected_id or manifest.snapshot_hash != expected_hash:
        return False, (
            f"snapshot content-address mismatch: stored snapshot_id={manifest.snapshot_id!r}/"
            f"snapshot_hash={manifest.snapshot_hash!r} does not match the id/hash recomputed from "
            f"the manifest's own fields ({expected_id!r}/{expected_hash!r})",
        )
    return True, ()


# --------------------------------------------------------------------------
# Historical observation cache (Spec #005 SS5/SS7, Batch 2): "Compute
# compute_discovery_observations once per session/universe/config/
# snapshot and reuse the PRE-budget output for all relevant variants and
# invalidation checks." "Cache keys bind stage, session, universe/
# benchmark, snapshot, discovery code/config and PIT policy."
# --------------------------------------------------------------------------

PIT_ACCESS_POLICY_V1 = "BOUNDED_PIT_V1"


def historical_observation_cache_fingerprint(
    stage: str, as_of: str, security_ids: tuple[str, ...], benchmark_security_id: str, snapshot_id: str,
    discovery_engine_version: str, discovery_config_version: str, pit_access_policy: str,
) -> str:
    """Key-only fingerprint (mirrors #003's `build_run_id()`'s own
    key-only recipe, not a full-content hash): these 8 fields fully
    determine the reproducible `compute_discovery_observations()` output
    -- SS21's "identical semantic inputs produce identical... content
    and IDs" guarantee rests on #002's OWN already-accepted determinism,
    not a second hash over `DiscoveryObservation` internals here."""
    payload = {
        "stage": stage,
        "as_of": as_of,
        "security_ids": sorted(security_ids),
        "benchmark_security_id": benchmark_security_id,
        "snapshot_id": snapshot_id,
        "discovery_engine_version": discovery_engine_version,
        "discovery_config_version": discovery_config_version,
        "pit_access_policy": pit_access_policy,
    }
    return canonical_json(payload)


def build_historical_observation_cache_id(fingerprint: str) -> tuple[str, str]:
    digest = hashlib.sha256(fingerprint.encode()).hexdigest()[:16]
    return f"obscache_{digest}", digest


@dataclass(frozen=True)
class HistoricalObservationCache:
    """Spec #005 SS5: "Session/security observations and explicit
    missingness, discovery config/code and snapshot scope."
    `missing_security_ids` is the explicit-missingness SS7 requires: a
    security in the requested universe that produced no
    `DiscoveryObservation` (ineligible, or no price history at all) is
    named here, never silently absent -- SS7: "A missing observation is
    UNKNOWN, not automatically a false entry or true invalidation."
    `observations` is the PRE-budget list exactly as
    `discovery.engine.compute_discovery_observations()` returned it --
    this type never accepts `run_discovery()`'s post-budget output."""
    cache_id: str
    cache_hash: str

    stage: str
    as_of: str
    security_ids: tuple[str, ...]  # the requested universe, sorted
    benchmark_security_id: str
    snapshot_id: str
    discovery_engine_version: str
    discovery_config_version: str
    pit_access_policy: str

    observations: tuple  # tuple[discovery.models.entities.DiscoveryObservation, ...]
    missing_security_ids: tuple[str, ...]
    observations_content_hash: str


def verify_historical_observation_cache_identity(cache: HistoricalObservationCache) -> tuple[bool, tuple[str, ...]]:
    """Recomputes the KEY-ONLY fingerprint from the cache entry's OWN
    stored key fields and compares it to `cache.cache_id`/
    `cache.cache_hash` -- catches a cache entry modified after
    construction (e.g. via `dataclasses.replace()` swapping `as_of` or
    `security_ids`). This does NOT verify `observations`/
    `missing_security_ids` content -- deleting or replacing those while
    keeping the key fields unchanged still passes this check (Batch 2
    patch round-2 review, explicit caution: never present this as a
    content-integrity check). See
    `verify_historical_observation_cache_content()` for that."""
    fp = historical_observation_cache_fingerprint(
        cache.stage, cache.as_of, cache.security_ids, cache.benchmark_security_id, cache.snapshot_id,
        cache.discovery_engine_version, cache.discovery_config_version, cache.pit_access_policy,
    )
    expected_id, expected_hash = build_historical_observation_cache_id(fp)
    if cache.cache_id != expected_id or cache.cache_hash != expected_hash:
        return False, (
            f"observation cache content-address mismatch: stored cache_id={cache.cache_id!r}/"
            f"cache_hash={cache.cache_hash!r} does not match the id/hash recomputed from the "
            f"cache entry's own key fields ({expected_id!r}/{expected_hash!r})",
        )
    return True, ()


def historical_observation_cache_content_fingerprint(observations: tuple, missing_security_ids: tuple[str, ...]) -> str:
    """A SEPARATE, genuine content hash over the actual payload --
    `historical_observation_cache_fingerprint()` above is deliberately
    key-only (mirrors #003's `build_run_id()` recipe) and must never be
    presented as verifying `observations`/`missing_security_ids`
    content; this is the function that actually does. Uses
    `dataclasses.asdict()` to canonicalize each `DiscoveryObservation`
    (including its nested `DescriptiveMetrics`/`TransitionEntry`
    dataclasses) generically, without importing the discovery package's
    types into this module."""
    records = [asdict(obs) for obs in observations]
    records.sort(key=lambda r: r["security_id"])
    payload = {"observations": records, "missing_security_ids": sorted(missing_security_ids)}
    return canonical_json(payload)


def build_historical_observation_cache_content_hash(fingerprint: str) -> str:
    """Batch 2 patch round-3 review (naming/implementation bug):
    `observations_content_hash` previously stored the raw canonical-
    JSON FINGERPRINT string directly -- functionally still caught
    tampering (comparing two canonical serializations for equality
    works), but a field named `_hash` holding un-hashed JSON text is
    misleading and needlessly large. This actually hashes it, mirroring
    every other `build_xxx_id()` function in this module (fingerprint
    string in, `sha256` hex digest out) -- full-length, since this is a
    comparison value, never truncated into a short id."""
    return hashlib.sha256(fingerprint.encode()).hexdigest()


def verify_historical_observation_cache_content(cache: HistoricalObservationCache) -> tuple[bool, tuple[str, ...]]:
    """Recomputes the content hash from `cache.observations`/
    `cache.missing_security_ids` and compares it to
    `cache.observations_content_hash` -- unlike
    `verify_historical_observation_cache_identity()` (key-only), THIS
    catches a tampered `observations`/`missing_security_ids` payload
    served under otherwise-identical key fields."""
    fp = historical_observation_cache_content_fingerprint(cache.observations, cache.missing_security_ids)
    expected = build_historical_observation_cache_content_hash(fp)
    if cache.observations_content_hash != expected:
        return False, (
            f"observation cache content mismatch: stored observations_content_hash="
            f"{cache.observations_content_hash!r} does not match the hash recomputed from "
            f"cache.observations/cache.missing_security_ids ({expected!r})",
        )
    return True, ()
