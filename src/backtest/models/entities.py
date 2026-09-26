"""Spec #005 v1.0 -- typed contracts owned by #005 (Batch 1).

Every entity here is frozen and content-addressed the same way #003/#004
already do: an identity field (`*_id`) and a `*_hash` are pure functions
of the entity's own ECONOMIC fields, administrative timestamps/approvers
excluded (Spec #005 SS21: "Exclude created_at and wall-clock performance
from semantic identity"). Nothing in this module reads #001 data or
imports evaluation/discovery/hypothesis internals beyond the two
explicitly-approved reuses (`build_run_id`, `check_provenance_matches_run`)
that live in `backtest.provenance.evaluation_run`, not here.

This module is CONTRACTS ONLY (Batch 1, Spec #005 SS24): no engine, no
execution, no PIT access. Later batches add the modules that actually
replay sessions and build trades.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional

from evaluation.models.entities import EvaluationRunRegistry


def _canonical_json(value) -> str:
    """Structured, delimiter-free serialization for #005's OWN new
    fingerprints (GPT review, Batch 1 patch: hand-rolled `"::"`/`","`
    string-concatenation delimiters can collide -- two structurally
    different inputs, e.g. differing lists of free-text strings
    containing commas, can serialize to the identical string). Does NOT
    apply to the legacy #003 `build_run_id()` or #004
    `hypothesis_fingerprint()`/`variant_fingerprint()` recipes -- those
    stay unchanged, out of scope."""
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _is_valid_iso_date(value) -> bool:
    if not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def _is_strict_positive_int(value) -> bool:
    """`bool` is a subclass of `int` in Python -- `isinstance(x, int)`
    alone silently accepts `True`/`False` as if they were valid trade
    counts."""
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


# --------------------------------------------------------------------------
# Calendar (Spec #005 SS11: "a separate, verified, versioned input, not
# inferred from benchmark bars or a vote/union of security series")
# --------------------------------------------------------------------------

class CalendarSource(str, Enum):
    """A formal run requires OFFICIAL_VERIFIED (SS11/SS24: "Without a
    verified calendar covering the stage and required warm-up, fail
    closed"). SYNTHETIC_TEST_FIXTURE exists so infrastructure tests can
    supply a trivial calendar of their own -- SS11 is explicit that such
    a fixture "cannot label it a verified real-market calendar", so it
    must never satisfy the formal-run gate."""
    OFFICIAL_VERIFIED = "OFFICIAL_VERIFIED"
    SYNTHETIC_TEST_FIXTURE = "SYNTHETIC_TEST_FIXTURE"


@dataclass(frozen=True)
class TradingCalendar:
    """Spec #005 SS11: "Record its source, calendar identifier, version,
    covered dates, timezone, session open/close times (including
    holidays, early closes and exceptional closures), verification
    provenance and content hash." `session_dates` is the ground truth of
    which dates ARE trading sessions -- a date's absence from every price
    series does NOT make it a non-session (SS11: "An expected session
    without a bar is a data gap and remains a session for
    NEXT_SESSION_OPEN and holding counts, even if the date is absent
    from every series"). Reconciling this calendar against actual price
    series (detecting a genuine gap vs. an unexpected bar on a
    non-session) is engine work for a later batch -- this type is the
    contract only."""
    calendar_id: str
    calendar_hash: str

    source: str  # CalendarSource
    calendar_identifier: str  # human-assigned name, e.g. "NYSE_NASDAQ_COMPOSITE"
    calendar_version: str
    market: str  # e.g. "US_EQUITIES", mirrors StrategyDefinition.market (Spec #004)
    timezone: str  # e.g. "America/New_York"

    coverage_start: str
    coverage_end: str

    session_dates: tuple[str, ...]  # sorted, deduplicated ISO dates
    session_open_time: str  # e.g. "09:30"
    session_close_time: str  # e.g. "16:00"
    early_close_dates: tuple[tuple[str, str], ...] = field(default_factory=tuple)  # (date, close_time)

    verified_by: Optional[str] = None
    verified_at: Optional[str] = None


def calendar_fingerprint(
    source: str, calendar_identifier: str, calendar_version: str, market: str, timezone: str,
    coverage_start: str, coverage_end: str, session_dates: tuple[str, ...],
    session_open_time: str, session_close_time: str, early_close_dates: tuple[tuple[str, str], ...],
) -> str:
    """`source` is part of the fingerprint on purpose (same discipline as
    Spec #004 PATCH #004-A's `HorizonCandidateSet.parameter_source`): a
    synthetic fixture with the exact same dates as a real calendar must
    still be a DIFFERENT calendar identity, never interchangeable with
    it. `verified_by`/`verified_at` are excluded -- administrative
    provenance, not economic identity, same convention as
    `hypothesis_fingerprint()` excluding `approved_by`/`approved_at`."""
    payload = {
        "source": source,
        "calendar_identifier": calendar_identifier,
        "calendar_version": calendar_version,
        "market": market,
        "timezone": timezone,
        "coverage_start": coverage_start,
        "coverage_end": coverage_end,
        "session_dates": sorted(session_dates),
        "session_open_time": session_open_time,
        "session_close_time": session_close_time,
        "early_close_dates": sorted([list(pair) for pair in early_close_dates]),
    }
    return _canonical_json(payload)


def build_calendar_id(fingerprint: str) -> tuple[str, str]:
    digest = hashlib.sha256(fingerprint.encode()).hexdigest()[:16]
    return f"cal_{digest}", digest


def verify_calendar_content_address(calendar: TradingCalendar) -> tuple[bool, tuple[str, ...]]:
    """Recomputes the fingerprint from the calendar's OWN stored fields
    and compares it to the stored `calendar_id`/`calendar_hash`. `frozen=
    True` blocks in-place mutation but not construction of a
    self-inconsistent object via `dataclasses.replace()` (e.g. dropping a
    session date while keeping the old id) -- same bug class PATCH
    #004-B already fixed once for StrategyHypothesis/StrategyVariant."""
    fp = calendar_fingerprint(
        calendar.source, calendar.calendar_identifier, calendar.calendar_version, calendar.market,
        calendar.timezone, calendar.coverage_start, calendar.coverage_end, calendar.session_dates,
        calendar.session_open_time, calendar.session_close_time, calendar.early_close_dates,
    )
    expected_id, expected_hash = build_calendar_id(fp)
    if calendar.calendar_id != expected_id or calendar.calendar_hash != expected_hash:
        return False, (
            f"calendar content-address mismatch: stored calendar_id={calendar.calendar_id!r}/"
            f"calendar_hash={calendar.calendar_hash!r} does not match the id/hash recomputed from "
            f"the calendar's own fields ({expected_id!r}/{expected_hash!r}) -- the object was "
            f"modified after construction (e.g. via dataclasses.replace())",
        )
    return True, ()


def verify_calendar_structure(calendar: TradingCalendar) -> tuple[bool, tuple[str, ...]]:
    """Validates the calendar's declared SHAPE, independent of its
    content address: `coverage_start`/`coverage_end` and every
    session/early-close date must be genuine ISO dates, coverage must
    not be reversed, every `session_date` must fall within the declared
    coverage, and there must be no duplicate `session_dates`."""
    errors: list[str] = []
    coverage_start_valid = _is_valid_iso_date(calendar.coverage_start)
    coverage_end_valid = _is_valid_iso_date(calendar.coverage_end)
    if not coverage_start_valid:
        errors.append(f"coverage_start is not a valid ISO date: {calendar.coverage_start!r}")
    if not coverage_end_valid:
        errors.append(f"coverage_end is not a valid ISO date: {calendar.coverage_end!r}")
    coverage_known = coverage_start_valid and coverage_end_valid and calendar.coverage_start <= calendar.coverage_end
    if coverage_start_valid and coverage_end_valid and not coverage_known:
        errors.append(f"coverage_start={calendar.coverage_start!r} is after coverage_end={calendar.coverage_end!r}")

    if len(calendar.session_dates) != len(set(calendar.session_dates)):
        errors.append("session_dates contains duplicate entries")

    for d in calendar.session_dates:
        if not _is_valid_iso_date(d):
            errors.append(f"session_dates contains a non-ISO-date value: {d!r}")
        elif coverage_known and not (calendar.coverage_start <= d <= calendar.coverage_end):
            errors.append(f"session_date {d!r} falls outside declared coverage [{calendar.coverage_start!r}, {calendar.coverage_end!r}]")

    for entry_date, _close_time in calendar.early_close_dates:
        if not _is_valid_iso_date(entry_date):
            errors.append(f"early_close_dates contains a non-ISO-date value: {entry_date!r}")
        elif coverage_known and not (calendar.coverage_start <= entry_date <= calendar.coverage_end):
            errors.append(f"early_close_date {entry_date!r} falls outside declared coverage [{calendar.coverage_start!r}, {calendar.coverage_end!r}]")

    return (not errors, tuple(errors))


class CalendarNotVerifiedError(ValueError):
    pass


class CalendarCoverageIncompleteError(ValueError):
    pass


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
    return _canonical_json(payload)


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


def validate_selection_rule(rule: SelectionRule) -> tuple[bool, tuple[str, ...]]:
    errors: list[str] = []
    if not _is_strict_positive_int(rule.minimum_executed_trades):
        errors.append(f"minimum_executed_trades must be a positive integer, got {rule.minimum_executed_trades!r}")
    if not _is_strict_positive_int(rule.minimum_evaluable_trades):
        errors.append(f"minimum_evaluable_trades must be a positive integer, got {rule.minimum_evaluable_trades!r}")
    if not (0 < rule.minimum_evaluable_ratio <= 1):
        errors.append(f"minimum_evaluable_ratio must be in (0,1], got {rule.minimum_evaluable_ratio!r}")
    if rule.ranking_metric != RANKING_METRIC_V1:
        errors.append(f"ranking_metric must be {RANKING_METRIC_V1!r} in V1, got {rule.ranking_metric!r} (SS18 -- no hidden Sharpe/drawdown/win-rate metric)")
    if rule.minimum_selection_metric != MINIMUM_SELECTION_METRIC_V1:
        errors.append(f"minimum_selection_metric must be {MINIMUM_SELECTION_METRIC_V1!r} in V1, got {rule.minimum_selection_metric!r}")
    if rule.threshold_operator != THRESHOLD_OPERATOR_V1:
        errors.append(f"threshold_operator must be {THRESHOLD_OPERATOR_V1!r} in V1, got {rule.threshold_operator!r}")
    if rule.tie_break != TIE_BREAK_V1:
        errors.append(f"tie_break must be {TIE_BREAK_V1!r} in V1, got {rule.tie_break!r}")
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
        `cross_check_results` must never read as "all ok". Requires
        EXACTLY one cross-check result per declared `hypothesis_id`
        (no missing, no extra, no duplicate) before checking each
        result's own `.ok`."""
        if not self.hypothesis_ids:
            return False
        covered_ids = [r.hypothesis_id for r in self.cross_check_results]
        if len(covered_ids) != len(set(covered_ids)):
            return False
        if set(covered_ids) != set(self.hypothesis_ids):
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


def research_plan_fingerprint(
    formation_start: str, formation_end: str, validation_start: str, validation_end: str, locked_oos_start: str,
    selection_folds: tuple[SelectionFold, ...], hypothesis_cohort_ids: tuple[str, ...],
    trading_calendar_id: str, benchmark_security_id: str, execution_semantics_profile_id: str,
    selection_rule: SelectionRule, cost_assumptions: CostAssumptions, exposure_manifest: ExposureManifest,
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
    return _canonical_json(payload)


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
    )
    expected_id, expected_hash = build_research_plan_id(fp)
    if plan.research_plan_id != expected_id or plan.plan_hash != expected_hash:
        return False, (
            f"research plan content-address mismatch: stored research_plan_id={plan.research_plan_id!r}/"
            f"plan_hash={plan.plan_hash!r} does not match the id/hash recomputed from the plan's own "
            f"fields ({expected_id!r}/{expected_hash!r})",
        )
    return True, ()
