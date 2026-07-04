"""
💰 Salary Decision Engine — v6.0 Production
============================================
File: app/agents/hr/salary_decision_engine.py

ℹ️ NODE.JS / DB NOTE:
    This file has no MongoDB/Motor dependency and makes no HTTP calls to
    the Node.js API. It is a pure rule + weighted-scoring engine: it takes
    a plain dict payload (e.g. from POST /hr/salary-reviews after the Node
    controller hands it to the AI agent) and returns a SalaryDecisionResult
    — no database or network I/O happens inside this module. There is
    nothing here to repoint at core.node_api_client / core.node_hr_proxy —
    no changes were needed for the Node.js migration. Left otherwise
    identical to v6.0. (Persisting the resulting decision — e.g. via
    POST /hr/salary-reviews/:id/status or /hr/audit — happens in the
    calling layer, not in this engine.)

🎯 المشكلة اللي بيحلها:
    BEFORE (broken flow):
        hr_agent._rule_based_fallback() → "defer"    ← قرار أول
            ↓
        SalaryValidationLayer.validate_and_override() → "reject"  ← overwrite!
        
    AFTER (clean single flow):
        SalaryDecisionEngine.decide()  →  Final Decision  ← قرار واحد بس

✅ v6.0 Features:
    1. Single Decision Engine — no double-decision, no overwrite
    2. Priority-based hard blockers (P0–P4)
    3. Weighted multi-factor scoring engine (P5)
    4. Full explainability — every decision comes with detailed reasoning
    5. Audit-ready output — weighted_score + score_breakdown + all factors
    6. /salary-reviews/{id}/explain endpoint support

Priority Order:
    P0 — is_on_pip                    → REJECT  (hardest block)
    P1 — performance_score < 0.50     → REJECT  (critically low)
    P2 — is_on_probation              → DEFER
    P3 — budget_utilization > 0.95    → DEFER
    P4 — increment > 30%              → ESCALATE_TO_DIRECTOR
    P5 — weighted score engine        → approve / escalate / defer / reject

Weighted Score Formula (sums to 1.0):
    performance_score (40%) + kpi_achievement (30%) +
    market_gap (20%)        + tenure_factor (10%)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from typing import Optional

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# 📦  DATA CLASSES
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class SalaryDecisionInput:
    """Typed input for the decision engine — no dict key typos possible."""
    employee_id:                 str   = ""
    employee_name:               str   = ""
    current_salary_egp:          float = 0.0
    requested_increment_pct:     float = 0.10
    market_median_egp:           float = 0.0
    market_gap_pct:              float = 0.0
    months_since_last_increment: int   = 12
    months_in_role:              int   = 0
    kpi_achievement:             float = 0.80
    budget_utilization:          float = 0.80
    available_pool_egp:          float = 0.0
    is_on_pip:                   bool  = False
    is_on_probation:             bool  = False
    performance_score:           float = 0.75
    job_level:                   str   = "junior"
    department:                  str   = "General"
    salary_grade:                str   = "C"
    appraisal_cycle:             str   = "Annual"
    request_id:                  str   = ""

    @classmethod
    def from_dict(cls, data: dict) -> "SalaryDecisionInput":
        """Build from raw dict — handles None values and type coercion safely."""
        return cls(
            employee_id                 = str(data.get("employee_id", "")),
            employee_name               = str(data.get("employee_name", "")),
            current_salary_egp          = float(data.get("current_salary_egp", 0) or 0),
            requested_increment_pct     = float(data.get("requested_increment_pct", 0.10) or 0.10),
            market_median_egp           = float(data.get("market_median_egp", 0) or 0),
            market_gap_pct              = float(data.get("market_gap_pct", 0) or 0),
            months_since_last_increment = int(data.get("months_since_last_increment", 12) or 12),
            months_in_role              = int(data.get("months_in_role", 0) or 0),
            kpi_achievement             = float(data.get("kpi_achievement", 0.80) or 0.80),
            budget_utilization          = float(data.get("budget_utilization", 0.80) or 0.80),
            available_pool_egp          = float(data.get("available_pool_egp", 0) or 0),
            is_on_pip                   = bool(data.get("is_on_pip", False)),
            is_on_probation             = bool(data.get("is_on_probation", False)),
            performance_score           = float(data.get("performance_score", 0.75) or 0.75),
            job_level                   = str(data.get("job_level", "junior") or "junior").lower(),
            department                  = str(data.get("department", "General") or "General"),
            salary_grade                = str(data.get("salary_grade", "C") or "C").upper(),
            appraisal_cycle             = str(data.get("appraisal_cycle", "Annual") or "Annual"),
            request_id                  = str(data.get("request_id", "") or ""),
        )


@dataclass
class ScoreBreakdown:
    """Detailed breakdown of the weighted score components."""
    performance_contribution: float = 0.0   # perf_score × 0.40
    kpi_contribution:         float = 0.0   # kpi_normalized × 0.30
    market_contribution:      float = 0.0   # market_normalized × 0.20
    tenure_contribution:      float = 0.0   # tenure_normalized × 0.10
    total_score:              float = 0.0

    # Raw values (for transparency)
    raw_performance_score:           float = 0.0
    raw_kpi_achievement:             float = 0.0
    raw_market_gap_pct:              float = 0.0
    raw_months_since_last_increment: int   = 0

    # Normalized values (what actually fed into the score)
    normalized_performance: float = 0.0
    normalized_kpi:         float = 0.0
    normalized_market:      float = 0.0
    normalized_tenure:      float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SalaryDecisionResult:
    """
    Complete, audit-ready output from the decision engine.
    This is the ONLY result — no overwriting, no double-decision.
    """
    # Core decision
    decision:                  str   = "defer"
    confidence:                float = 0.70
    recommended_increment_pct: float = 0.0

    # Explainability
    reason:                    str   = ""
    trigger:                   str   = ""     # which rule/engine made the decision
    trigger_phase:             str   = ""     # "hard_blocker" | "score_engine" | "llm"
    priority_level:            int   = 5      # P0–P5 — which priority fired

    # Flags
    flags:                     list  = field(default_factory=list)
    risk:                      str   = "medium"

    # Score engine output (populated even for hard blockers — shows what score would have been)
    weighted_score:            float = 0.0
    score_breakdown:           Optional[ScoreBreakdown] = None

    # Blockers that were checked (audit trail)
    blockers_evaluated:        list  = field(default_factory=list)

    # Meta
    request_id:                str   = ""
    decision_source:           str   = "salary_decision_engine_v6"
    llm_used:                  bool  = False
    model_source:              str   = "rule_engine"

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.score_breakdown:
            d["score_breakdown"] = self.score_breakdown.to_dict()
        return d


# ════════════════════════════════════════════════════════════════════════════
# ⚙️  CONSTANTS
# ════════════════════════════════════════════════════════════════════════════

# Weighted score thresholds
SCORE_APPROVE    = 0.75
SCORE_ESCALATE   = 0.55
SCORE_DEFER      = 0.40
# below SCORE_DEFER → reject

# Performance floors
PERF_REJECT_FLOOR = 0.50   # below → reject regardless of anything else
PERF_DEFER_FLOOR  = 0.60   # below → never approve, best is defer

# Weights (must sum to 1.0)
WEIGHT_PERFORMANCE = 0.40
WEIGHT_KPI         = 0.30
WEIGHT_MARKET      = 0.20
WEIGHT_TENURE      = 0.10

# Level-based increment caps (Egyptian market benchmarks)
LEVEL_INCREMENT_CAPS = {
    "junior":  0.20,
    "senior":  0.25,
    "lead":    0.30,
    "manager": 0.35,
}


# ════════════════════════════════════════════════════════════════════════════
# 🧠  SALARY DECISION ENGINE
# ════════════════════════════════════════════════════════════════════════════

class SalaryDecisionEngine:
    """
    Single-pass decision engine for salary reviews.

    Usage:
        engine = SalaryDecisionEngine()
        result = engine.decide(payload_dict, request_id="abc123")
        # result is a SalaryDecisionResult — always complete, never partial

    Integration:
        Called from hr_agent.process_salary() instead of:
            1. _rule_based_fallback()   ← REMOVED
            2. SalaryValidationLayer    ← MERGED INTO HERE
    """

    def decide(
        self,
        payload:    dict,
        request_id: str = "",
    ) -> SalaryDecisionResult:
        """
        Main entry point — produces one final decision with full explainability.

        No overwriting. No double-decision. One pass through priority rules,
        then score engine if no hard blocker fires.
        """
        inp = SalaryDecisionInput.from_dict({**payload, "request_id": request_id})
        blockers_evaluated = []

        # Always compute weighted score upfront — used in reasons even for blockers
        score, breakdown = self._compute_score(inp)

        # ════════════════════════════════════════════════════════════════════
        # PHASE 1 — HARD BLOCKERS (P0 → P4)
        # First blocker that fires wins. Lower priority numbers = higher priority.
        # ════════════════════════════════════════════════════════════════════

        # ── P0: PIP → REJECT ──────────────────────────────────────────────
        blockers_evaluated.append("P0_pip_check")
        if inp.is_on_pip:
            rec_pct = self._calculate_recommended_increment(inp)
            result  = SalaryDecisionResult(
                decision                  = "reject",
                confidence                = 0.97,
                recommended_increment_pct = 0.0,  # no increment on PIP
                reason                    = self._reason_pip(inp),
                trigger                   = "rule_s0_pip_reject",
                trigger_phase             = "hard_blocker",
                priority_level            = 0,
                flags                     = self._build_flags(inp, "pip"),
                risk                      = "high",
                weighted_score            = round(score, 4),
                score_breakdown           = breakdown,
                blockers_evaluated        = blockers_evaluated,
                request_id                = request_id,
                decision_source           = "salary_decision_engine_v6",
                model_source              = "rule_engine_p0",
            )
            self._log_decision(result, inp)
            return result

        # ── P1: Critically low performance → REJECT ──────────────────────
        blockers_evaluated.append("P1_performance_floor_check")
        if inp.performance_score < PERF_REJECT_FLOOR:
            result = SalaryDecisionResult(
                decision                  = "reject",
                confidence                = 0.93,
                recommended_increment_pct = 0.0,
                reason                    = self._reason_low_performance(inp),
                trigger                   = "rule_s1_critical_low_performance",
                trigger_phase             = "hard_blocker",
                priority_level            = 1,
                flags                     = self._build_flags(inp, "low_perf"),
                risk                      = "high",
                weighted_score            = round(score, 4),
                score_breakdown           = breakdown,
                blockers_evaluated        = blockers_evaluated,
                request_id                = request_id,
                decision_source           = "salary_decision_engine_v6",
                model_source              = "rule_engine_p1",
            )
            self._log_decision(result, inp)
            return result

        # ── P2: Probation → DEFER ─────────────────────────────────────────
        blockers_evaluated.append("P2_probation_check")
        if inp.is_on_probation:
            additional = self._get_additional_concerns(inp)
            rec_pct    = self._calculate_recommended_increment(inp)
            result     = SalaryDecisionResult(
                decision                  = "defer",
                confidence                = 0.92,
                recommended_increment_pct = rec_pct,  # noted for future review
                reason                    = self._reason_probation(inp, additional),
                trigger                   = "rule_s2_probation_defer",
                trigger_phase             = "hard_blocker",
                priority_level            = 2,
                flags                     = self._build_flags(inp, "probation", additional),
                risk                      = "medium",
                weighted_score            = round(score, 4),
                score_breakdown           = breakdown,
                blockers_evaluated        = blockers_evaluated,
                request_id                = request_id,
                decision_source           = "salary_decision_engine_v6",
                model_source              = "rule_engine_p2",
            )
            self._log_decision(result, inp)
            return result

        # ── P3: Budget exhausted → DEFER ─────────────────────────────────
        blockers_evaluated.append("P3_budget_check")
        if inp.budget_utilization > 0.95:
            rec_pct = self._calculate_recommended_increment(inp)
            result  = SalaryDecisionResult(
                decision                  = "defer",
                confidence                = 0.90,
                recommended_increment_pct = rec_pct,
                reason                    = self._reason_budget(inp),
                trigger                   = "rule_s3_budget_exhausted",
                trigger_phase             = "hard_blocker",
                priority_level            = 3,
                flags                     = [
                    f"⛔ Budget {inp.budget_utilization:.0%} > 95% cap",
                    f"📊 Performance {inp.performance_score:.0%} noted for next cycle",
                ],
                risk                      = "medium",
                weighted_score            = round(score, 4),
                score_breakdown           = breakdown,
                blockers_evaluated        = blockers_evaluated,
                request_id                = request_id,
                decision_source           = "salary_decision_engine_v6",
                model_source              = "rule_engine_p3",
            )
            self._log_decision(result, inp)
            return result

        # ── P4: Increment > 30% → ESCALATE ───────────────────────────────
        blockers_evaluated.append("P4_increment_cap_check")
        if inp.requested_increment_pct > 0.30:
            rec_pct = min(
                self._calculate_recommended_increment(inp),
                LEVEL_INCREMENT_CAPS.get(inp.job_level, 0.25),
            )
            result = SalaryDecisionResult(
                decision                  = "escalate_to_director",
                confidence                = 0.95,
                recommended_increment_pct = rec_pct,
                reason                    = self._reason_large_increment(inp),
                trigger                   = "rule_s4_large_increment",
                trigger_phase             = "hard_blocker",
                priority_level            = 4,
                flags                     = [
                    f"⬆️ Increment {inp.requested_increment_pct:.0%} > 30% cap",
                    "📋 Director authorization required",
                    f"📊 Recommended increment if approved: {rec_pct:.0%}",
                ],
                risk                      = "medium",
                weighted_score            = round(score, 4),
                score_breakdown           = breakdown,
                blockers_evaluated        = blockers_evaluated,
                request_id                = request_id,
                decision_source           = "salary_decision_engine_v6",
                model_source              = "rule_engine_p4",
            )
            self._log_decision(result, inp)
            return result

        # ════════════════════════════════════════════════════════════════════
        # PHASE 2 — WEIGHTED SCORE ENGINE (no hard blocker fired)
        # ════════════════════════════════════════════════════════════════════
        blockers_evaluated.append("P5_score_engine")

        decision, confidence = self._score_to_decision(score, inp)
        rec_pct = self._calculate_recommended_increment(inp)

        result = SalaryDecisionResult(
            decision                  = decision,
            confidence                = confidence,
            recommended_increment_pct = rec_pct if decision != "reject" else 0.0,
            reason                    = self._reason_score_engine(decision, score, breakdown, inp),
            trigger                   = f"score_engine_{decision}",
            trigger_phase             = "score_engine",
            priority_level            = 5,
            flags                     = self._build_score_flags(score, inp),
            risk                      = self._classify_risk(confidence),
            weighted_score            = round(score, 4),
            score_breakdown           = breakdown,
            blockers_evaluated        = blockers_evaluated,
            request_id                = request_id,
            decision_source           = "salary_decision_engine_v6",
            model_source              = "score_engine",
        )
        self._log_decision(result, inp)
        return result

    # ════════════════════════════════════════════════════════════════════════
    # 📊  SCORE COMPUTATION
    # ════════════════════════════════════════════════════════════════════════

    def _compute_score(self, inp: SalaryDecisionInput) -> tuple[float, ScoreBreakdown]:
        """
        Weighted multi-factor score (0.0 → 1.0).

        Each component is normalized to 0–1 before applying its weight,
        so no single factor can dominate just because of its raw scale.
        """
        # Performance (40%) — raw score already 0–1
        norm_perf = min(max(inp.performance_score, 0.0), 1.0)

        # KPI (30%) — cap at 120% of target, map to 0–1
        norm_kpi = min(inp.kpi_achievement, 1.20) / 1.20

        # Market gap (20%)
        #   market_gap_pct > 0  = employee is BELOW market  → higher urgency → higher score
        #   market_gap_pct < 0  = employee is ABOVE market  → lower urgency  → lower score
        #   clamped to [-0.30, +0.30] then mapped to [0, 1]
        market_clamped = min(max(inp.market_gap_pct, -0.30), 0.30)
        norm_market    = (market_clamped + 0.30) / 0.60

        # Tenure (10%)
        #   6 months  → 0.0
        #   12 months → 0.5
        #   24+ months → 1.0
        m = inp.months_since_last_increment
        if m >= 24:
            norm_tenure = 1.0
        elif m >= 12:
            norm_tenure = 0.50 + (m - 12) / 24.0
        elif m >= 6:
            norm_tenure = (m - 6) / 12.0
        else:
            norm_tenure = 0.0
        norm_tenure = min(norm_tenure, 1.0)

        # Weighted sum
        p_contrib = norm_perf   * WEIGHT_PERFORMANCE
        k_contrib = norm_kpi    * WEIGHT_KPI
        m_contrib = norm_market * WEIGHT_MARKET
        t_contrib = norm_tenure * WEIGHT_TENURE
        total     = p_contrib + k_contrib + m_contrib + t_contrib

        breakdown = ScoreBreakdown(
            performance_contribution          = round(p_contrib, 4),
            kpi_contribution                  = round(k_contrib, 4),
            market_contribution               = round(m_contrib, 4),
            tenure_contribution               = round(t_contrib, 4),
            total_score                       = round(total, 4),
            raw_performance_score             = round(inp.performance_score, 4),
            raw_kpi_achievement               = round(inp.kpi_achievement, 4),
            raw_market_gap_pct                = round(inp.market_gap_pct, 4),
            raw_months_since_last_increment   = inp.months_since_last_increment,
            normalized_performance            = round(norm_perf, 4),
            normalized_kpi                    = round(norm_kpi, 4),
            normalized_market                 = round(norm_market, 4),
            normalized_tenure                 = round(norm_tenure, 4),
        )
        return total, breakdown

    def _score_to_decision(
        self,
        score: float,
        inp:   SalaryDecisionInput,
    ) -> tuple[str, float]:
        """Map weighted score → (decision, confidence)."""

        # Even if score is high, performance below defer floor blocks approval
        if inp.performance_score < PERF_DEFER_FLOOR:
            if score >= SCORE_DEFER:
                return "defer", 0.80
            return "reject", 0.85

        # Check budget feasibility for approval
        if score >= SCORE_APPROVE:
            if inp.available_pool_egp > 0:
                increment_cost = inp.current_salary_egp * inp.requested_increment_pct
                if increment_cost > inp.available_pool_egp * 1.5:
                    # Expensive increment relative to pool → escalate instead
                    return "escalate_to_director", 0.78
            return "approve_increment", round(min(0.82 + score * 0.10, 0.95), 3)
        elif score >= SCORE_ESCALATE:
            return "escalate_to_director", 0.78
        elif score >= SCORE_DEFER:
            return "defer", 0.80
        else:
            return "reject", 0.88

    # ════════════════════════════════════════════════════════════════════════
    # 💡  RECOMMENDED INCREMENT CALCULATION
    # ════════════════════════════════════════════════════════════════════════

    def _calculate_recommended_increment(self, inp: SalaryDecisionInput) -> float:
        """
        Compute a fair recommended increment based on all factors.
        Used for audit trail even when the decision is defer/reject.
        """
        max_by_level = LEVEL_INCREMENT_CAPS.get(inp.job_level, 0.20)

        # Performance multiplier
        if inp.performance_score >= 0.90:
            perf_mult = 1.00
        elif inp.performance_score >= 0.75:
            perf_mult = 0.85
        elif inp.performance_score >= 0.60:
            perf_mult = 0.70
        else:
            perf_mult = 0.50

        # KPI bonus
        kpi_bonus = 0.0
        if inp.kpi_achievement >= 1.20:
            kpi_bonus = 0.03
        elif inp.kpi_achievement >= 1.0:
            kpi_bonus = 0.02
        elif inp.kpi_achievement >= 0.90:
            kpi_bonus = 0.01

        # Tenure bonus
        tenure_bonus = 0.0
        m = inp.months_since_last_increment
        if m >= 24:
            tenure_bonus = 0.03
        elif m >= 18:
            tenure_bonus = 0.02
        elif m >= 12:
            tenure_bonus = 0.01

        # Base from requested vs market gap
        base = min(
            inp.requested_increment_pct,
            abs(inp.market_gap_pct) if inp.market_gap_pct > 0 else inp.requested_increment_pct,
        )

        calculated = (base * perf_mult) + kpi_bonus + tenure_bonus
        calculated = min(calculated, max_by_level)

        # Budget cap
        if inp.available_pool_egp > 0 and inp.current_salary_egp > 0:
            max_by_budget = inp.available_pool_egp / inp.current_salary_egp
            calculated    = min(calculated, max_by_budget)

        # Minimum if performance warrants
        if inp.performance_score >= 0.75 and inp.months_since_last_increment >= 12:
            calculated = max(calculated, 0.05)

        return round(max(0.0, calculated), 4)

    # ════════════════════════════════════════════════════════════════════════
    # 📝  REASON BUILDERS
    # ════════════════════════════════════════════════════════════════════════

    def _reason_pip(self, inp: SalaryDecisionInput) -> str:
        market_note = ""
        if inp.market_gap_pct < -0.05:
            market_note = (
                f" Additionally, the employee's salary is already "
                f"{abs(inp.market_gap_pct):.0%} above market median, "
                f"further reducing justification for an increment."
            )

        return (
            f"Salary increment REJECTED: Employee {inp.employee_name} is currently on a "
            f"Performance Improvement Plan (PIP). Company policy prohibits salary increments "
            f"for employees on PIP, regardless of tenure or market position. "
            f"Current metrics — Performance: {inp.performance_score:.0%}, "
            f"KPI: {inp.kpi_achievement:.0%}."
            f"{market_note} "
            f"Recommend: complete PIP successfully, achieve minimum performance targets, "
            f"then re-submit for the next review cycle."
        )

    def _reason_low_performance(self, inp: SalaryDecisionInput) -> str:
        return (
            f"Salary increment REJECTED due to critically low performance: "
            f"Performance score of {inp.performance_score:.0%} is below the minimum "
            f"threshold of {PERF_REJECT_FLOOR:.0%} required for any salary consideration. "
            f"KPI achievement of {inp.kpi_achievement:.0%} reinforces this assessment. "
            f"Salary increments signal recognition of contribution — the current performance "
            f"level does not justify this signal. "
            f"Recommendation: establish clear performance goals with manager, "
            f"reach at least {PERF_DEFER_FLOOR:.0%} performance score before next review."
        )

    def _reason_probation(
        self,
        inp:         SalaryDecisionInput,
        additional:  list,
    ) -> str:
        concerns_text = ""
        if additional:
            concerns_text = " Additional factors noted: " + "; ".join(additional) + "."

        return (
            f"Salary increment DEFERRED: Employee {inp.employee_name} is in the probation period "
            f"({inp.months_in_role} months in role). Company policy requires successful "
            f"probation completion before salary reviews are conducted. "
            f"Performance of {inp.performance_score:.0%} and KPI of {inp.kpi_achievement:.0%} "
            f"have been recorded and will inform the post-probation review."
            f"{concerns_text} "
            f"Recommended increment for post-probation review: "
            f"{self._calculate_recommended_increment(inp):.0%}. "
            f"Please schedule a formal salary review upon probation completion."
        )

    def _reason_budget(self, inp: SalaryDecisionInput) -> str:
        return (
            f"Salary increment DEFERRED due to budget constraints: "
            f"Department budget utilization is at {inp.budget_utilization:.0%}, "
            f"exceeding the 95% threshold. No increment pool is available this cycle. "
            f"Employee performance of {inp.performance_score:.0%} and KPI of "
            f"{inp.kpi_achievement:.0%} are noted and will carry forward to the next "
            f"budget cycle. Available pool: {inp.available_pool_egp:,.0f} EGP."
        )

    def _reason_large_increment(self, inp: SalaryDecisionInput) -> str:
        return (
            f"Salary review ESCALATED to HR Director: "
            f"Requested increment of {inp.requested_increment_pct:.0%} exceeds the 30% "
            f"automatic approval ceiling. Director-level authorization is required per policy. "
            f"Supporting data — Performance: {inp.performance_score:.0%}, "
            f"KPI: {inp.kpi_achievement:.0%}, "
            f"Market gap: {inp.market_gap_pct:.0%}. "
            f"Recommended increment if approved: "
            f"{self._calculate_recommended_increment(inp):.0%}."
        )

    def _reason_score_engine(
        self,
        decision:   str,
        score:      float,
        breakdown:  ScoreBreakdown,
        inp:        SalaryDecisionInput,
    ) -> str:
        labels = {
            "approve_increment":    "APPROVED",
            "escalate_to_director": "ESCALATED to Director",
            "defer":                "DEFERRED",
            "reject":               "REJECTED",
        }
        label = labels.get(decision, decision.upper())

        market_text = (
            f"above market by {abs(inp.market_gap_pct):.0%}"
            if inp.market_gap_pct < 0
            else f"below market by {inp.market_gap_pct:.0%}"
        )

        return (
            f"Salary increment {label} based on weighted multi-factor analysis "
            f"(score: {score:.2f}/1.00). "
            f"Breakdown — "
            f"Performance ({WEIGHT_PERFORMANCE:.0%} weight): {inp.performance_score:.0%} "
            f"→ contributes {breakdown.performance_contribution:.2f}; "
            f"KPI ({WEIGHT_KPI:.0%} weight): {inp.kpi_achievement:.0%} "
            f"→ contributes {breakdown.kpi_contribution:.2f}; "
            f"Market position ({WEIGHT_MARKET:.0%} weight): {market_text} "
            f"→ contributes {breakdown.market_contribution:.2f}; "
            f"Tenure ({WEIGHT_TENURE:.0%} weight): {inp.months_since_last_increment} months "
            f"→ contributes {breakdown.tenure_contribution:.2f}. "
            f"Thresholds: Approve ≥{SCORE_APPROVE:.0%}, "
            f"Escalate ≥{SCORE_ESCALATE:.0%}, "
            f"Defer ≥{SCORE_DEFER:.0%}."
        )

    # ════════════════════════════════════════════════════════════════════════
    # 🏷️  FLAGS & RISK
    # ════════════════════════════════════════════════════════════════════════

    def _build_flags(
        self,
        inp:         SalaryDecisionInput,
        trigger:     str,
        additional:  list = None,
    ) -> list:
        flags = []

        if trigger == "pip":
            flags.append("🚨 Employee on PIP — increment rejected per policy")
            flags.append(f"📊 Performance: {inp.performance_score:.0%} | KPI: {inp.kpi_achievement:.0%}")
            if inp.market_gap_pct < -0.05:
                flags.append(f"📈 Salary {abs(inp.market_gap_pct):.0%} above market — no market pressure")

        elif trigger == "low_perf":
            flags.append(f"🚨 Performance {inp.performance_score:.0%} below {PERF_REJECT_FLOOR:.0%} floor")
            flags.append(f"📊 KPI: {inp.kpi_achievement:.0%} | Market gap: {inp.market_gap_pct:.0%}")

        elif trigger == "probation":
            flags.append(f"⚠️ Probation period — {inp.months_in_role} months in role")
            flags.append("📋 Review scheduled post-probation completion")
            for concern in (additional or []):
                flags.append(f"⚠️ Additional: {concern}")

        return flags

    def _build_score_flags(self, score: float, inp: SalaryDecisionInput) -> list:
        flags = [f"📊 Weighted score: {score:.3f}/1.00"]

        if inp.performance_score >= 0.85:
            flags.append(f"✅ Strong performance: {inp.performance_score:.0%}")
        elif inp.performance_score < 0.65:
            flags.append(f"⚠️ Below-average performance: {inp.performance_score:.0%}")

        if inp.kpi_achievement >= 1.0:
            flags.append(f"✅ KPI target met: {inp.kpi_achievement:.0%}")
        elif inp.kpi_achievement < 0.70:
            flags.append(f"⚠️ Low KPI: {inp.kpi_achievement:.0%}")

        if inp.market_gap_pct > 0.15:
            flags.append(f"🔴 Significant market gap: {inp.market_gap_pct:.0%} below median")
        elif inp.market_gap_pct < -0.10:
            flags.append(f"📈 Above market: {abs(inp.market_gap_pct):.0%} above median")

        if inp.months_since_last_increment >= 24:
            flags.append(f"⏰ {inp.months_since_last_increment} months without increment")

        return flags

    def _get_additional_concerns(self, inp: SalaryDecisionInput) -> list:
        concerns = []
        if inp.performance_score < PERF_DEFER_FLOOR:
            concerns.append(f"performance {inp.performance_score:.0%} is below 60%")
        if inp.kpi_achievement < 0.60:
            concerns.append(f"KPI achievement {inp.kpi_achievement:.0%} is below 60%")
        if inp.market_gap_pct < -0.05:
            concerns.append(
                f"salary is {abs(inp.market_gap_pct):.0%} above market median — "
                "no market pressure justification"
            )
        return concerns

    def _classify_risk(self, confidence: float) -> str:
        if confidence >= 0.85:
            return "low"
        elif confidence >= 0.65:
            return "medium"
        return "high"

    # ════════════════════════════════════════════════════════════════════════
    # 📋  LOGGING
    # ════════════════════════════════════════════════════════════════════════

    def _log_decision(
        self,
        result: SalaryDecisionResult,
        inp:    SalaryDecisionInput,
    ) -> None:
        phase_icon = {"hard_blocker": "🛑", "score_engine": "📊"}.get(
            result.trigger_phase, "🔄"
        )
        logger.info(
            "[request_id=%s] %s [SalaryDecisionEngine] P%d %s → %s | "
            "conf=%.0f%% | score=%.3f | perf=%.0f%% | kpi=%.0f%% | "
            "pip=%s | prob=%s | rec_pct=%.0f%%",
            result.request_id,
            phase_icon,
            result.priority_level,
            result.trigger,
            result.decision,
            result.confidence * 100,
            result.weighted_score,
            inp.performance_score * 100,
            inp.kpi_achievement * 100,
            inp.is_on_pip,
            inp.is_on_probation,
            result.recommended_increment_pct * 100,
        )


# ════════════════════════════════════════════════════════════════════════════
# 🌐  EXPLAINABILITY API HELPER
# ════════════════════════════════════════════════════════════════════════════

class SalaryExplainabilityBuilder:
    """
    Builds the response payload for GET /salary-reviews/{id}/explain endpoint.
    Turns a SalaryDecisionResult into a human-readable structured explanation.
    """

    @staticmethod
    def build(result: SalaryDecisionResult, inp: SalaryDecisionInput) -> dict:
        bd = result.score_breakdown

        # Decision label mapping
        labels = {
            "approve_increment":    {"label": "✅ Approved",             "color": "green"},
            "escalate_to_director": {"label": "⬆️ Escalated to Director", "color": "orange"},
            "defer":                {"label": "⏳ Deferred",              "color": "yellow"},
            "reject":               {"label": "❌ Rejected",              "color": "red"},
        }
        decision_display = labels.get(result.decision, {"label": result.decision, "color": "gray"})

        # Factor cards
        factors = []
        if bd:
            factors = [
                {
                    "factor":       "Performance Score",
                    "weight":       f"{WEIGHT_PERFORMANCE:.0%}",
                    "raw_value":    f"{bd.raw_performance_score:.0%}",
                    "normalized":   f"{bd.normalized_performance:.2f}",
                    "contribution": f"{bd.performance_contribution:.3f}",
                    "impact":       (
                        "positive" if bd.raw_performance_score >= 0.75
                        else "negative" if bd.raw_performance_score < 0.60
                        else "neutral"
                    ),
                },
                {
                    "factor":       "KPI Achievement",
                    "weight":       f"{WEIGHT_KPI:.0%}",
                    "raw_value":    f"{bd.raw_kpi_achievement:.0%}",
                    "normalized":   f"{bd.normalized_kpi:.2f}",
                    "contribution": f"{bd.kpi_contribution:.3f}",
                    "impact":       (
                        "positive" if bd.raw_kpi_achievement >= 1.0
                        else "negative" if bd.raw_kpi_achievement < 0.70
                        else "neutral"
                    ),
                },
                {
                    "factor":       "Market Position",
                    "weight":       f"{WEIGHT_MARKET:.0%}",
                    "raw_value":    (
                        f"{bd.raw_market_gap_pct:.0%} below market"
                        if bd.raw_market_gap_pct >= 0
                        else f"{abs(bd.raw_market_gap_pct):.0%} above market"
                    ),
                    "normalized":   f"{bd.normalized_market:.2f}",
                    "contribution": f"{bd.market_contribution:.3f}",
                    "impact":       (
                        "positive" if bd.raw_market_gap_pct > 0.10
                        else "negative" if bd.raw_market_gap_pct < -0.05
                        else "neutral"
                    ),
                },
                {
                    "factor":       "Time Since Last Increment",
                    "weight":       f"{WEIGHT_TENURE:.0%}",
                    "raw_value":    f"{bd.raw_months_since_last_increment} months",
                    "normalized":   f"{bd.normalized_tenure:.2f}",
                    "contribution": f"{bd.tenure_contribution:.3f}",
                    "impact":       (
                        "positive" if bd.raw_months_since_last_increment >= 18
                        else "neutral"
                    ),
                },
            ]

        # Threshold ladder
        thresholds = [
            {
                "threshold": SCORE_APPROVE,
                "decision":  "approve_increment",
                "label":     f"≥ {SCORE_APPROVE:.0%} → Approve",
                "reached":   result.weighted_score >= SCORE_APPROVE,
            },
            {
                "threshold": SCORE_ESCALATE,
                "decision":  "escalate_to_director",
                "label":     f"≥ {SCORE_ESCALATE:.0%} → Escalate",
                "reached":   result.weighted_score >= SCORE_ESCALATE,
            },
            {
                "threshold": SCORE_DEFER,
                "decision":  "defer",
                "label":     f"≥ {SCORE_DEFER:.0%} → Defer",
                "reached":   result.weighted_score >= SCORE_DEFER,
            },
            {
                "threshold": 0.0,
                "decision":  "reject",
                "label":     f"< {SCORE_DEFER:.0%} → Reject",
                "reached":   result.weighted_score < SCORE_DEFER,
            },
        ]

        return {
            "decision_display":        decision_display,
            "decision":                result.decision,
            "confidence":              f"{result.confidence:.0%}",
            "trigger":                 result.trigger,
            "trigger_phase":           result.trigger_phase,
            "priority_level":          f"P{result.priority_level}",
            "weighted_score":          result.weighted_score,
            "recommended_increment":   f"{result.recommended_increment_pct:.0%}",
            "reason":                  result.reason,
            "flags":                   result.flags,
            "factors":                 factors,
            "threshold_ladder":        thresholds,
            "blockers_evaluated":      result.blockers_evaluated,
            "hard_blocker_fired":      result.trigger_phase == "hard_blocker",
            "employee": {
                "id":         inp.employee_id,
                "name":       inp.employee_name,
                "job_level":  inp.job_level,
                "department": inp.department,
                "is_on_pip":  inp.is_on_pip,
                "is_on_prob": inp.is_on_probation,
            },
        }


# ── Singleton ─────────────────────────────────────────────────────────────────
_engine_instance: Optional[SalaryDecisionEngine] = None


def get_salary_decision_engine() -> SalaryDecisionEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = SalaryDecisionEngine()
    return _engine_instance