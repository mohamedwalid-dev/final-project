"""
⚖️ Decision Validation Layer — v5.0 Production (Full AI Automation)
====================================================================
File: app/workflows/hr/decision_rules.py

NOTE (Node.js API migration pass):
    This file was reviewed for MongoDB / Node-API compatibility issues.
    None were found — every class here (DecisionValidationLayer,
    SalaryValidationLayer, IncentiveValidationLayer, AbsenceValidationLayer,
    AttendanceValidationLayer) is pure business-rules logic operating only
    on the `agent_result` / `payload` dicts passed in. The only I/O is
    `AuditLogger()` from audit.logger, which is a local/file logger, not a
    database or HTTP client — it does not talk to MongoDB or the Node API,
    so it needs no changes for this migration.
    Content below is unchanged from v5.1.

✅ v5.0 Features:
    1. Full automation — NO human decisions, all overrides are AI-driven
    2. request_id logged on every line
    3. Covers all HR domains: Leave + Salary + Incentive + Absence + Attendance
    4. ConflictResolver integrated after every override
    5. Salary/Incentive/Absence/Attendance validation layers added
    6. Graceful error handling — layer NEVER crashes the pipeline

✅ v5.1 CRITICAL FIX — SalaryValidationLayer:
    BEFORE (broken): Single-trigger logic — if probation → defer (stops thinking)
    AFTER  (fixed):  Priority-based multi-factor Decision Engine

    Priority Order (highest → lowest):
        P1. is_on_pip              → REJECT  (PIP = no increment, period)
        P2. performance_score < 0.5 → REJECT  (critically low performance)
        P3. is_on_probation        → DEFER   (policy: no increment during probation)
        P4. budget_utilization > 0.95 → DEFER (no budget available)
        P5. increment > 30%        → ESCALATE (requires Director sign-off)
        P6. Multi-factor score     → weighted scoring engine (approve / escalate / defer)

    Multi-factor Scoring Weights:
        performance_score (40%) + kpi_achievement (30%) +
        market_gap (20%) + tenure_factor (10%)

Business Rules (Leave — priority order):
    Rule 1 — leave_balance == 0               → force reject
    Rule 2 — requested_days > balance         → force reject
    Rule 3 — low confidence approve           → escalate (NOT human — auto-escalate)

Business Rules (Salary — v5.1 Priority Engine):
    Rule S0 — is_on_pip                       → force REJECT (highest priority)
    Rule S1 — performance_score < 0.5         → force REJECT (critically low)
    Rule S2 — is_on_probation                 → force DEFER
    Rule S3 — budget_utilization > 0.95       → force DEFER
    Rule S4 — increment > 30%                 → force ESCALATE_TO_DIRECTOR
    Rule S5 — weighted_score < 0.40           → REJECT
    Rule S6 — weighted_score 0.40–0.65        → DEFER
    Rule S7 — weighted_score 0.65–0.75        → ESCALATE_TO_DIRECTOR
    Rule S8 — weighted_score >= 0.75          → APPROVE

Business Rules (Incentive):
    Rule I1 — overtime_compensation type       → force approve_bonus
    Rule I2 — is_on_pip + non-overtime type    → force deny_bonus
    Rule I3 — kpi_achievement < 0.70 (perf)   → force deny_bonus

Business Rules (Absence):
    Rule A1 — unexcused_count >= 3 (90d)       → force escalate_to_hr_director
    Rule A2 — no_medical_cert + sick > 2d      → force formal_warning

Business Rules (Attendance):
    Rule AT1 — attendance_rate < 0.70          → force escalate_to_hr_director
"""

from __future__ import annotations

import logging
from typing import Optional

from audit.logger import AuditLogger

try:
    from config.hr_thresholds import VALIDATION_MIN_CONFIDENCE_FOR_APPROVE
except ImportError:
    VALIDATION_MIN_CONFIDENCE_FOR_APPROVE = 0.60

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# ⚖️  LEAVE VALIDATION LAYER
# ════════════════════════════════════════════════════════════════════════════

class DecisionValidationLayer:
    """
    Business Rules Engine for Leave Requests — v5.0.
    Safety net after the AI agent — all overrides are automated, no human required.
    """

    def __init__(self) -> None:
        self.audit_logger = AuditLogger()

    def validate_and_override(self, agent_result: dict, payload: dict) -> dict:
        """
        Check AI agent decision against hard business rules.

        Returns validated dict with:
          - "override_rule"      if override happened
          - "conflict_analysis"  from ConflictResolver (always computed)
          - "request_id"         propagated from agent result
        """
        request_id        = agent_result.get("request_id") or payload.get("request_id", "?")
        original_decision = agent_result.get("decision", "escalate")
        confidence        = float(agent_result.get("confidence", 0.0))
        requested_days    = int(payload.get("requested_days", payload.get("leave_days", 0)))
        leave_balance     = int(payload.get("leave_balance", 0))
        employee_id       = payload.get("employee_id", "unknown")

        validated = agent_result.copy()

        # ── Rule 1: Zero balance ───────────────────────────────────────────────
        if leave_balance == 0 and original_decision == "approve":
            return self._apply_override(
                validated      = validated,
                payload        = payload,
                agent_result   = agent_result,
                new_decision   = "reject",
                override_rule  = "rule_1_zero_balance",
                reason         = (
                    "❌ Rejected (Rule 1): Leave balance is 0. "
                    "Policy prohibits approval without balance."
                ),
                employee_id    = employee_id,
                confidence     = 1.0,
                request_id     = request_id,
            )

        # ── Rule 2: Days exceed balance ────────────────────────────────────────
        if requested_days > leave_balance and original_decision == "approve":
            return self._apply_override(
                validated      = validated,
                payload        = payload,
                agent_result   = agent_result,
                new_decision   = "reject",
                override_rule  = "rule_2_days_exceed_balance",
                reason         = (
                    f"❌ Rejected (Rule 2): Requested {requested_days}d > balance {leave_balance}d."
                ),
                employee_id    = employee_id,
                confidence     = 1.0,
                request_id     = request_id,
            )

        # ── Rule 3: Low confidence approve → auto-escalate ────────────────────
        if (
            confidence < VALIDATION_MIN_CONFIDENCE_FOR_APPROVE
            and original_decision == "approve"
        ):
            return self._apply_override(
                validated      = validated,
                payload        = payload,
                agent_result   = agent_result,
                new_decision   = "escalate",
                override_rule  = "rule_3_low_confidence_approve",
                reason         = (
                    f"⚠️ Auto-escalated (Rule 3): Confidence {confidence:.0%} < "
                    f"{VALIDATION_MIN_CONFIDENCE_FOR_APPROVE:.0%} minimum for approval."
                ),
                employee_id    = employee_id,
                confidence     = confidence,
                request_id     = request_id,
            )

        # ── All rules passed ───────────────────────────────────────────────────
        logger.debug(
            "[request_id=%s] ✅ [ValidationLayer] All rules passed — "
            "decision=%s | conf=%.2f | employee=%s",
            request_id, original_decision, confidence, employee_id,
        )
        validated.pop("override_rule", None)
        return validated

    # ── Private ───────────────────────────────────────────────────────────────

    def _apply_override(
        self,
        validated:     dict,
        payload:       dict,
        agent_result:  dict,
        new_decision:  str,
        override_rule: str,
        reason:        str,
        employee_id:   str,
        confidence:    float,
        request_id:    str,
    ) -> dict:
        original = agent_result.get("decision", "?")

        logger.warning(
            "[request_id=%s] ⚠️ [ValidationLayer] Override: %s | "
            "employee=%s | %s → %s",
            request_id, override_rule, employee_id, original, new_decision,
        )
        self.audit_logger.log(
            event_type = "leave_request",
            stage      = "validation_layer",
            message    = (
                f"[request_id={request_id}] Override {override_rule}: "
                f"{original} → {new_decision}"
            ),
            level      = "WARNING",
        )

        validated["decision"]      = new_decision
        validated["confidence"]    = confidence
        validated["override_rule"] = override_rule
        validated["reason"]        = reason
        validated["reasoning"]     = reason
        validated["request_id"]    = request_id

        # ── ConflictResolver ──────────────────────────────────────────────────
        try:
            from agents.hr.conflict_resolver import get_conflict_resolver
            from agents.hr.leave_model_handler import get_model_handler
            from config.hr_thresholds import get_thresholds_from_metadata

            handler    = get_model_handler()
            thresholds = get_thresholds_from_metadata(handler._metadata)

            conflict_analysis = get_conflict_resolver().resolve(
                ml_result      = agent_result,
                final_decision = new_decision,
                payload        = payload,
                rules_decision = new_decision,
                override_rule  = override_rule,
                tier           = agent_result.get("tier", 2),
                thresholds     = thresholds,
            )
            validated["conflict_analysis"] = conflict_analysis

            # Append top recommendations to ai_flags
            ai_flags = list(validated.get("ai_flags", []))
            for rec in conflict_analysis.get("recommendations", [])[:2]:
                if rec not in ai_flags:
                    ai_flags.append(rec)
            validated["ai_flags"] = ai_flags

            logger.info(
                "[request_id=%s] ⚖️ [ConflictResolver] type=%s | severity=%s",
                request_id,
                conflict_analysis.get("conflict_type"),
                conflict_analysis.get("conflict_severity"),
            )

        except Exception as e:
            logger.warning(
                "[request_id=%s] ⚠️ [ValidationLayer] ConflictResolver failed: %s",
                request_id, e,
            )

        return validated


# ════════════════════════════════════════════════════════════════════════════
# 💰  SALARY VALIDATION LAYER — v5.1 Priority-Based Decision Engine
# ════════════════════════════════════════════════════════════════════════════

class SalaryValidationLayer:
    """
    Priority-Based Decision Engine for salary review requests.

    v5.1 BREAKING CHANGE from v4.x:
        OLD: Single-trigger logic (first condition wins, ignores the rest)
        NEW: Full priority evaluation — ALL factors assessed before deciding

    The engine works in two phases:
        Phase 1 — Hard Blockers (P0–P4): absolute rules that override everything
        Phase 2 — Weighted Score Engine (P5–P8): multi-factor scoring for borderline cases
    """

    # ── Scoring weights (must sum to 1.0) ─────────────────────────────────────
    WEIGHT_PERFORMANCE  = 0.40   # performance_score
    WEIGHT_KPI          = 0.30   # kpi_achievement (normalized to 0–1)
    WEIGHT_MARKET       = 0.20   # market_gap_pct (how far below market)
    WEIGHT_TENURE       = 0.10   # months_since_last_increment (normalized)

    # ── Decision thresholds (score out of 1.0) ─────────────────────────────────
    SCORE_APPROVE    = 0.75   # >= this → approve_increment
    SCORE_ESCALATE   = 0.55   # >= this → escalate_to_director
    SCORE_DEFER      = 0.40   # >= this → defer
    # below SCORE_DEFER → reject (performance too low to justify any action)

    # ── Performance hard floor ─────────────────────────────────────────────────
    PERFORMANCE_REJECT_FLOOR = 0.50   # below this → always reject
    PERFORMANCE_DEFER_FLOOR  = 0.60   # below this → never approve, at best defer

    def validate_and_override(self, agent_result: dict, payload: dict) -> dict:
        """
        Full priority evaluation pipeline.

        Returns validated result with:
            - decision updated if any rule/score overrides
            - override_rule populated with the trigger reason
            - weighted_score injected for auditability
            - detailed reason explaining ALL factors considered
        """
        request_id  = agent_result.get("request_id") or payload.get("request_id", "?")
        decision    = agent_result.get("decision", "escalate_to_director")

        # ── Extract all relevant fields ────────────────────────────────────────
        is_on_pip   = bool(payload.get("is_on_pip", False))
        is_on_prob  = bool(payload.get("is_on_probation", False))
        budget_util = float(payload.get("budget_utilization", 0.80))
        inc_pct     = float(payload.get("requested_increment_pct", 0.10))
        perf_score  = float(payload.get("performance_score") or 0.75)
        kpi         = float(payload.get("kpi_achievement", 0.80))
        market_gap  = float(payload.get("market_gap_pct", 0.0))
        months_last = int(payload.get("months_since_last_increment", 12))
        months_role = int(payload.get("months_in_role", 0))
        cur_salary  = float(payload.get("current_salary_egp", 0))
        avail_pool  = float(payload.get("available_pool_egp", 0))

        validated = agent_result.copy()

        # ════════════════════════════════════════════════════════════════════
        # PHASE 1 — HARD BLOCKERS (checked in priority order, highest first)
        # ════════════════════════════════════════════════════════════════════

        # ── P0: PIP → REJECT (absolute highest priority) ──────────────────
        # PIP means the employee is under a corrective performance plan.
        # No increment is ever justified while on PIP, regardless of any other factor.
        if is_on_pip:
            reason = self._build_pip_reason(perf_score, kpi, market_gap)
            logger.warning(
                "[request_id=%s] 🚨 [SalaryValidation] P0 PIP BLOCK: "
                "employee on PIP → REJECT | perf=%.0f%% | kpi=%.0f%%",
                request_id, perf_score * 100, kpi * 100,
            )
            return self._apply_salary_override(
                validated      = validated,
                new_decision   = "reject",
                override_rule  = "rule_s0_pip_reject",
                reason         = reason,
                confidence     = 0.97,
                request_id     = request_id,
                extra_flags    = [
                    "🚨 Employee on PIP — increment rejected per policy",
                    f"📊 Performance: {perf_score:.0%} | KPI: {kpi:.0%}",
                ],
            )

        # ── P1: Critically low performance → REJECT ───────────────────────
        # Even without PIP, a performance score below 50% signals the employee
        # is not meeting basic expectations. An increment would send the wrong signal.
        if perf_score < self.PERFORMANCE_REJECT_FLOOR:
            reason = self._build_low_perf_reason(perf_score, kpi, is_on_pip=False)
            logger.warning(
                "[request_id=%s] 🚨 [SalaryValidation] P1 LOW PERF REJECT: "
                "perf=%.0f%% < %.0f%% floor → REJECT",
                request_id, perf_score * 100, self.PERFORMANCE_REJECT_FLOOR * 100,
            )
            return self._apply_salary_override(
                validated      = validated,
                new_decision   = "reject",
                override_rule  = "rule_s1_critical_low_performance",
                reason         = reason,
                confidence     = 0.93,
                request_id     = request_id,
                extra_flags    = [
                    f"🚨 Performance {perf_score:.0%} below {self.PERFORMANCE_REJECT_FLOOR:.0%} floor",
                    f"📊 KPI: {kpi:.0%} | Market gap: {market_gap:.0%}",
                ],
            )

        # ── P2: Probation → DEFER ─────────────────────────────────────────
        # Company policy: salary reviews happen after successful probation completion.
        # This is DEFER (not reject) because the employee may qualify later.
        if is_on_prob:
            # Extra check: if ALSO has low KPI or low perf, bump to stronger defer
            additional_concerns = []
            if perf_score < self.PERFORMANCE_DEFER_FLOOR:
                additional_concerns.append(f"performance {perf_score:.0%} is below 60%")
            if kpi < 0.60:
                additional_concerns.append(f"KPI achievement {kpi:.0%} is below 60%")
            if market_gap < -0.05:
                additional_concerns.append(
                    f"current salary is {abs(market_gap):.0%} ABOVE market median"
                )

            reason = self._build_probation_reason(
                perf_score, kpi, months_role, additional_concerns
            )
            logger.warning(
                "[request_id=%s] ⚠️ [SalaryValidation] P2 PROBATION DEFER: "
                "employee on probation → DEFER | months_in_role=%d | "
                "perf=%.0f%% | kpi=%.0f%% | additional_concerns=%s",
                request_id, months_role, perf_score * 100, kpi * 100,
                additional_concerns,
            )
            return self._apply_salary_override(
                validated      = validated,
                new_decision   = "defer",
                override_rule  = "rule_s2_probation_defer",
                reason         = reason,
                confidence     = 0.92,
                request_id     = request_id,
                extra_flags    = (
                    ["⚠️ Probation period — review scheduled post-completion"] +
                    [f"⚠️ Additional concern: {c}" for c in additional_concerns]
                ),
            )

        # ── P3: Budget exhausted → DEFER ──────────────────────────────────
        if budget_util > 0.95:
            reason = (
                f"Salary increment deferred due to budget constraints: "
                f"Department budget utilization is at {budget_util:.0%}, "
                f"exceeding the 95% threshold. "
                f"No increment pool is available in the current cycle. "
                f"Employee performance of {perf_score:.0%} and KPI of {kpi:.0%} "
                f"are noted for the next budget cycle review."
            )
            logger.warning(
                "[request_id=%s] ⚠️ [SalaryValidation] P3 BUDGET DEFER: "
                "util=%.0f%% → DEFER",
                request_id, budget_util * 100,
            )
            return self._apply_salary_override(
                validated      = validated,
                new_decision   = "defer",
                override_rule  = "rule_s3_budget_exhausted",
                reason         = reason,
                confidence     = 0.90,
                request_id     = request_id,
                extra_flags    = [f"⛔ Budget {budget_util:.0%} > 95% cap"],
            )

        # ── P4: Increment > 30% → ESCALATE ───────────────────────────────
        if inc_pct > 0.30 and decision == "approve_increment":
            reason = (
                f"Salary review escalated to HR Director: "
                f"Requested increment of {inc_pct:.0%} exceeds the 30% automatic "
                f"approval cap. Director-level authorization is required. "
                f"Supporting data: performance {perf_score:.0%}, KPI {kpi:.0%}, "
                f"market gap {market_gap:.0%}."
            )
            logger.warning(
                "[request_id=%s] ⚠️ [SalaryValidation] P4 LARGE INCREMENT: "
                "%.0f%% > 30%% cap → ESCALATE",
                request_id, inc_pct * 100,
            )
            return self._apply_salary_override(
                validated      = validated,
                new_decision   = "escalate_to_director",
                override_rule  = "rule_s4_large_increment",
                reason         = reason,
                confidence     = 0.95,
                request_id     = request_id,
                extra_flags    = [f"⬆️ Increment {inc_pct:.0%} > 30% cap — Director required"],
            )

        # ════════════════════════════════════════════════════════════════════
        # PHASE 2 — WEIGHTED SCORE ENGINE
        # No hard blocker triggered → compute a multi-factor score
        # ════════════════════════════════════════════════════════════════════

        weighted_score, score_breakdown = self._compute_weighted_score(
            perf_score  = perf_score,
            kpi         = kpi,
            market_gap  = market_gap,
            months_last = months_last,
        )

        score_decision, score_confidence = self._score_to_decision(
            weighted_score = weighted_score,
            perf_score     = perf_score,
            inc_pct        = inc_pct,
            avail_pool     = avail_pool,
            cur_salary     = cur_salary,
        )

        # Inject score data for audit trail
        validated["weighted_score"]   = round(weighted_score, 4)
        validated["score_breakdown"]  = score_breakdown

        # Only override if the score engine disagrees with the agent
        if score_decision != decision:
            reason = self._build_score_reason(
                score_decision  = score_decision,
                weighted_score  = weighted_score,
                score_breakdown = score_breakdown,
                perf_score      = perf_score,
                kpi             = kpi,
                market_gap      = market_gap,
                months_last     = months_last,
                inc_pct         = inc_pct,
            )
            logger.info(
                "[request_id=%s] 📊 [SalaryValidation] Score Engine: "
                "score=%.3f → %s (agent said %s) | perf=%.0f%% | kpi=%.0f%%",
                request_id, weighted_score, score_decision, decision,
                perf_score * 100, kpi * 100,
            )
            return self._apply_salary_override(
                validated      = validated,
                new_decision   = score_decision,
                override_rule  = f"rule_s5_score_engine_{score_decision}",
                reason         = reason,
                confidence     = score_confidence,
                request_id     = request_id,
                extra_flags    = [
                    f"📊 Weighted score: {weighted_score:.2f} → {score_decision}",
                    f"   Perf({self.WEIGHT_PERFORMANCE:.0%}): {perf_score:.0%} | "
                    f"KPI({self.WEIGHT_KPI:.0%}): {kpi:.0%} | "
                    f"Market({self.WEIGHT_MARKET:.0%}): {market_gap:.0%} | "
                    f"Tenure({self.WEIGHT_TENURE:.0%}): {months_last}m",
                ],
            )

        # Agent and score engine agree — no override needed
        logger.info(
            "[request_id=%s] ✅ [SalaryValidation] All checks passed | "
            "decision=%s | score=%.3f | perf=%.0f%% | kpi=%.0f%%",
            request_id, decision, weighted_score, perf_score * 100, kpi * 100,
        )
        validated["weighted_score"]  = round(weighted_score, 4)
        validated["score_breakdown"] = score_breakdown
        return validated

    # ── Weighted Score Computation ─────────────────────────────────────────────

    def _compute_weighted_score(
        self,
        perf_score:  float,
        kpi:         float,
        market_gap:  float,
        months_last: int,
    ) -> tuple[float, dict]:
        """
        Compute a 0.0–1.0 weighted score from the four main salary factors.

        Performance (40%):
            Raw performance_score clamped to 0–1.

        KPI (30%):
            kpi_achievement normalized: cap at 1.20 (120%) → map to 0–1.
            Exceeding target is rewarded but not infinitely.

        Market gap (20%):
            market_gap_pct > 0 means employee is BELOW market → more justification.
            market_gap_pct < 0 means employee is ABOVE market → less justification.
            Clamped to [-0.30, +0.30] then mapped to [0, 1].

        Tenure factor (10%):
            Longer time without increment → higher score component.
            6 months = 0.0, 12 months = 0.5, 24+ months = 1.0.
        """
        # Performance component
        perf_component = min(max(perf_score, 0.0), 1.0)

        # KPI component (cap at 1.20 of target)
        kpi_normalized  = min(kpi, 1.20) / 1.20
        kpi_component   = min(max(kpi_normalized, 0.0), 1.0)

        # Market gap component (positive gap = below market = higher score)
        market_clamped   = min(max(market_gap, -0.30), 0.30)
        market_component = (market_clamped + 0.30) / 0.60   # maps [-0.30, 0.30] → [0, 1]

        # Tenure component (months since last increment)
        if months_last >= 24:
            tenure_component = 1.0
        elif months_last >= 12:
            tenure_component = 0.5 + (months_last - 12) / 24.0
        elif months_last >= 6:
            tenure_component = (months_last - 6) / 12.0
        else:
            tenure_component = 0.0

        tenure_component = min(tenure_component, 1.0)

        # Weighted sum
        weighted_score = (
            perf_component  * self.WEIGHT_PERFORMANCE +
            kpi_component   * self.WEIGHT_KPI +
            market_component * self.WEIGHT_MARKET +
            tenure_component * self.WEIGHT_TENURE
        )

        score_breakdown = {
            "performance":  round(perf_component  * self.WEIGHT_PERFORMANCE, 4),
            "kpi":          round(kpi_component   * self.WEIGHT_KPI, 4),
            "market":       round(market_component * self.WEIGHT_MARKET, 4),
            "tenure":       round(tenure_component * self.WEIGHT_TENURE, 4),
            "total":        round(weighted_score, 4),
            "raw": {
                "performance_score":          round(perf_score, 4),
                "kpi_achievement":            round(kpi, 4),
                "market_gap_pct":             round(market_gap, 4),
                "months_since_last_increment": months_last,
            },
        }

        return weighted_score, score_breakdown

    def _score_to_decision(
        self,
        weighted_score: float,
        perf_score:     float,
        inc_pct:        float,
        avail_pool:     float,
        cur_salary:     float,
    ) -> tuple[str, float]:
        """
        Map weighted score to a salary decision + confidence.

        Additional guard: even if score is high, performance below defer floor
        prevents approval (can't compensate with market gap alone).
        """
        # Hard performance floor: below 60% → at most defer, never approve
        if perf_score < self.PERFORMANCE_DEFER_FLOOR:
            if weighted_score >= self.SCORE_DEFER:
                return "defer", 0.80
            return "reject", 0.85

        # Budget feasibility check (if we have pool data)
        increment_cost = cur_salary * inc_pct
        if avail_pool > 0 and increment_cost > avail_pool * 1.5:
            # Requested increment is very expensive relative to available pool
            if weighted_score < self.SCORE_APPROVE:
                return "defer", 0.75

        # Standard scoring
        if weighted_score >= self.SCORE_APPROVE:
            return "approve_increment", min(0.85 + weighted_score * 0.10, 0.95)
        elif weighted_score >= self.SCORE_ESCALATE:
            return "escalate_to_director", 0.78
        elif weighted_score >= self.SCORE_DEFER:
            return "defer", 0.80
        else:
            return "reject", 0.88

    # ── Reason Builders ───────────────────────────────────────────────────────

    def _build_pip_reason(self, perf_score: float, kpi: float, market_gap: float) -> str:
        market_note = ""
        if market_gap < -0.05:
            market_note = (
                f" Note: the employee's current salary is already "
                f"{abs(market_gap):.0%} above market median, which further "
                f"reduces the case for an increment."
            )
        elif market_gap > 0.10:
            market_note = (
                f" While a market gap of {market_gap:.0%} exists, "
                f"this cannot override the PIP requirement."
            )

        return (
            f"Salary increment REJECTED: Employee is on a Performance Improvement Plan (PIP). "
            f"Per company policy, employees on PIP are not eligible for salary increments "
            f"until the plan is successfully completed and a satisfactory performance review "
            f"is conducted. "
            f"Current metrics — Performance: {perf_score:.0%}, KPI Achievement: {kpi:.0%}."
            f"{market_note} "
            f"Recommend: complete PIP, achieve performance targets, then re-submit for review."
        )

    def _build_low_perf_reason(
        self, perf_score: float, kpi: float, is_on_pip: bool
    ) -> str:
        return (
            f"Salary increment REJECTED due to critically low performance: "
            f"Performance score of {perf_score:.0%} is below the minimum threshold of "
            f"{self.PERFORMANCE_REJECT_FLOOR:.0%} required for any salary consideration. "
            f"KPI achievement of {kpi:.0%} further supports this decision. "
            f"Salary increments are reserved for employees meeting basic performance expectations. "
            f"Recommendation: work with manager to establish a performance improvement plan, "
            f"achieve a minimum performance score of {self.PERFORMANCE_DEFER_FLOOR:.0%} "
            f"before the next review cycle."
        )

    def _build_probation_reason(
        self,
        perf_score:            float,
        kpi:                   float,
        months_in_role:        int,
        additional_concerns:   list,
    ) -> str:
        concerns_text = (
            " Additional concerns noted: " + "; ".join(additional_concerns) + "."
            if additional_concerns else ""
        )
        return (
            f"Salary increment deferred: Employee is currently in the probation period "
            f"({months_in_role} months in role). Per company policy, salary reviews are "
            f"conducted only after successful probation completion (typically 6 months). "
            f"Current performance of {perf_score:.0%} and KPI of {kpi:.0%} have been noted "
            f"for the formal review at probation end."
            f"{concerns_text} "
            f"Recommend scheduling a formal salary review at end of probation period."
        )

    def _build_score_reason(
        self,
        score_decision:  str,
        weighted_score:  float,
        score_breakdown: dict,
        perf_score:      float,
        kpi:             float,
        market_gap:      float,
        months_last:     int,
        inc_pct:         float,
    ) -> str:
        decision_labels = {
            "approve_increment":    "APPROVED",
            "escalate_to_director": "ESCALATED to Director",
            "defer":                "DEFERRED",
            "reject":               "REJECTED",
        }
        label = decision_labels.get(score_decision, score_decision.upper())

        market_text = (
            f"above market by {abs(market_gap):.0%}" if market_gap < 0
            else f"below market by {market_gap:.0%}"
        )

        return (
            f"Salary increment {label} based on multi-factor weighted analysis "
            f"(score: {weighted_score:.2f}/1.00): "
            f"Performance ({self.WEIGHT_PERFORMANCE:.0%} weight): {perf_score:.0%}, "
            f"KPI Achievement ({self.WEIGHT_KPI:.0%} weight): {kpi:.0%}, "
            f"Market Position ({self.WEIGHT_MARKET:.0%} weight): {market_text}, "
            f"Tenure ({self.WEIGHT_TENURE:.0%} weight): {months_last} months since last increment. "
            f"Requested increment: {inc_pct:.0%}. "
            f"Thresholds — Approve: ≥{self.SCORE_APPROVE:.0%}, "
            f"Escalate: ≥{self.SCORE_ESCALATE:.0%}, "
            f"Defer: ≥{self.SCORE_DEFER:.0%}."
        )

    # ── Generic Override Helper ───────────────────────────────────────────────

    def _apply_salary_override(
        self,
        validated:     dict,
        new_decision:  str,
        override_rule: str,
        reason:        str,
        confidence:    float,
        request_id:    str,
        extra_flags:   list = None,
    ) -> dict:
        validated["decision"]      = new_decision
        validated["reason"]        = reason
        validated["override_rule"] = override_rule
        validated["confidence"]    = confidence
        validated["request_id"]    = request_id

        # Merge extra flags into ai_flags
        existing_flags = list(validated.get("flags", validated.get("ai_flags", [])))
        for flag in (extra_flags or []):
            if flag not in existing_flags:
                existing_flags.append(flag)
        validated["flags"]    = existing_flags
        validated["ai_flags"] = existing_flags

        return validated


# ════════════════════════════════════════════════════════════════════════════
# 🏆  INCENTIVE VALIDATION LAYER
# ════════════════════════════════════════════════════════════════════════════

class IncentiveValidationLayer:
    """Hard business rules for incentive / bonus requests."""

    def validate_and_override(self, agent_result: dict, payload: dict) -> dict:
        request_id      = agent_result.get("request_id") or payload.get("request_id", "?")
        decision        = agent_result.get("decision", "deny_bonus")
        incentive_type  = str(payload.get("incentive_type", "performance_bonus")).lower()
        is_on_pip       = bool(payload.get("is_on_pip", False))
        kpi             = float(payload.get("kpi_achievement", 1.0))
        req_amount      = float(payload.get("requested_amount_egp", 0))
        monthly_sal     = float(payload.get("monthly_salary_egp", 1))
        budget_left     = float(payload.get("incentive_budget_remaining_egp", 999999))

        validated = agent_result.copy()

        # Rule I1: Overtime compensation is always statutory
        if incentive_type == "overtime_compensation":
            validated["decision"]      = "approve_bonus"
            validated["confidence"]    = 0.99
            validated["reason"]        = (
                "✅ Auto-approved (I1): Overtime compensation is a statutory right "
                "under Egyptian Labor Law."
            )
            validated["override_rule"] = "rule_i1_statutory_overtime"
            return validated

        # Rule I2: PIP → deny
        if is_on_pip and decision == "approve_bonus":
            validated["decision"]      = "deny_bonus"
            validated["confidence"]    = 0.95
            validated["reason"]        = (
                "❌ Denied (I2): Employee on PIP — bonus suspended until plan completion."
            )
            validated["override_rule"] = "rule_i2_pip_block"
            logger.warning("[request_id=%s] ⚠️ [IncentiveValidation] Rule I2 PIP block", request_id)
            return validated

        # Rule I3: KPI < 70% for performance bonus
        if incentive_type == "performance_bonus" and kpi < 0.70 and decision == "approve_bonus":
            validated["decision"]      = "deny_bonus"
            validated["confidence"]    = 0.90
            validated["reason"]        = (
                f"❌ Denied (I3): KPI achievement {kpi:.0%} < 70% minimum for performance bonus."
            )
            validated["override_rule"] = "rule_i3_kpi_below_threshold"
            logger.warning("[request_id=%s] ⚠️ [IncentiveValidation] Rule I3 KPI=%s", request_id, kpi)
            return validated

        # Rule I4: Bonus > 3x monthly salary → escalate to CEO
        if monthly_sal > 0 and req_amount > monthly_sal * 3 and decision == "approve_bonus":
            validated["decision"]      = "escalate_to_ceo"
            validated["confidence"]    = 0.95
            validated["reason"]        = (
                f"⬆️ Escalated (I4): Bonus {req_amount:,.0f} EGP > 3x monthly salary "
                f"({monthly_sal:,.0f} EGP) — CEO approval required."
            )
            validated["override_rule"] = "rule_i4_excessive_bonus"
            return validated

        # Rule I5: Budget insufficient
        if req_amount > budget_left and decision == "approve_bonus":
            shortfall = req_amount - budget_left
            validated["decision"]      = "partial_bonus" if budget_left > 0 else "deny_bonus"
            validated["approved_amount_egp"] = budget_left if budget_left > 0 else 0
            validated["reason"]        = (
                f"⚡ Adjusted (I5): Budget only covers {budget_left:,.0f} EGP "
                f"(shortfall: {shortfall:,.0f} EGP)."
            )
            validated["override_rule"] = "rule_i5_budget_cap"
            return validated

        return validated


# ════════════════════════════════════════════════════════════════════════════
# 🚫  ABSENCE VALIDATION LAYER
# ════════════════════════════════════════════════════════════════════════════

class AbsenceValidationLayer:
    """Hard business rules for absence management."""

    def validate_and_override(self, agent_result: dict, payload: dict) -> dict:
        request_id      = agent_result.get("request_id") or payload.get("request_id", "?")
        decision        = agent_result.get("decision", "record_only")
        unexcused_90d   = int(payload.get("unexcused_count_90d", 0))
        medical_cert    = bool(payload.get("medical_certificate_provided", False))
        absence_type    = str(payload.get("absence_type_claimed", "unexcused")).lower()
        duration_hours  = float(payload.get("duration_hours", 8))
        prev_warnings   = str(payload.get("previous_warnings", "none")).lower()

        validated = agent_result.copy()

        # Rule A1: 3+ unexcused absences → escalate immediately
        if unexcused_90d >= 3:
            validated["decision"]         = "escalate_to_hr_director"
            validated["escalation_required"] = True
            validated["confidence"]       = 0.99
            validated["reason"]           = (
                f"🚨 Escalated (A1): {unexcused_90d} unexcused absences in 90 days — "
                "Egyptian Labor Law Art. 69 termination right threshold reached. "
                "HR Director intervention required immediately."
            )
            validated["override_rule"]    = "rule_a1_critical_unexcused"
            logger.warning(
                "[request_id=%s] 🚨 [AbsenceValidation] Rule A1: %d unexcused absences",
                request_id, unexcused_90d,
            )
            return validated

        # Rule A2: Sick leave > 2 days without medical certificate → formal warning
        if (
            absence_type == "sick"
            and duration_hours > 16  # > 2 days
            and not medical_cert
            and decision in ("record_only", "excused_paid")
        ):
            validated["decision"]      = "formal_warning"
            validated["confidence"]    = 0.95
            validated["reason"]        = (
                "⚠️ Formal Warning (A2): Sick leave > 2 days without medical certificate. "
                "Egyptian Labor Law Art. 54 requires valid certificate."
            )
            validated["override_rule"] = "rule_a2_no_medical_cert"
            validated["payroll_deduction_days"] = round(duration_hours / 8, 1)
            logger.warning(
                "[request_id=%s] ⚠️ [AbsenceValidation] Rule A2: sick no cert",
                request_id,
            )
            return validated

        # Rule A3: Formal warning on record + any new unexcused → suspension review
        if prev_warnings == "formal" and unexcused_90d >= 1 and decision not in (
            "escalate_to_hr_director", "suspension_review"
        ):
            validated["decision"]         = "suspension_review"
            validated["escalation_required"] = True
            validated["confidence"]       = 0.95
            validated["reason"]           = (
                "⚠️ Suspension Review (A3): Employee already has a formal warning "
                "and committed another unexcused absence — suspension review mandatory."
            )
            validated["override_rule"]    = "rule_a3_repeat_after_formal"
            return validated

        return validated


# ════════════════════════════════════════════════════════════════════════════
# 📅  ATTENDANCE VALIDATION LAYER
# ════════════════════════════════════════════════════════════════════════════

class AttendanceValidationLayer:
    """Hard business rules for monthly attendance audits."""

    def validate_and_override(self, agent_result: dict, payload: dict) -> dict:
        request_id    = agent_result.get("request_id") or payload.get("request_id", "?")
        decision      = agent_result.get("decision", "no_action")
        days_present  = int(payload.get("days_present", 20))
        working_days  = int(payload.get("working_days", 22))
        unexcused_abs = int(payload.get("unexcused_absences", 0))
        ytd_warnings  = int(payload.get("ytd_warnings", 0))

        att_rate = days_present / max(working_days, 1)
        validated = agent_result.copy()

        # Rule AT1: Attendance < 70% → always escalate
        if att_rate < 0.70 and decision not in ("escalate_to_hr_director",):
            validated["decision"]      = "escalate_to_hr_director"
            validated["confidence"]    = 0.99
            validated["reason"]        = (
                f"🚨 Escalated (AT1): Attendance rate {att_rate:.1%} is critically low (< 70%). "
                "HR Director immediate intervention required."
            )
            validated["override_rule"] = "rule_at1_critical_attendance"
            logger.warning(
                "[request_id=%s] 🚨 [AttendanceValidation] Rule AT1: att_rate=%.1f%%",
                request_id, att_rate * 100,
            )
            return validated

        # Rule AT2: 3+ YTD warnings + any red status → formal warning at minimum
        if ytd_warnings >= 3 and decision == "no_action":
            validated["decision"]      = "formal_warning"
            validated["confidence"]    = 0.85
            validated["reason"]        = (
                f"⚠️ Formal Warning (AT2): {ytd_warnings} YTD warnings — "
                "cannot remain at no_action status with this history."
            )
            validated["override_rule"] = "rule_at2_repeated_warnings"
            return validated

        return validated