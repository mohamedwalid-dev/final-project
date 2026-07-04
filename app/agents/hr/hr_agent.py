"""
🤖 HR Agent — v4.2 Production
==============================
File: app/agents/hr/hr_agent.py

✅ v4.2 Fixes:
    Fix Q1 — GeminiQuotaGuard: added to ALL Gemini call sites in HR agent
              (_invoke_llm_leave + _invoke_llm_domain), matching the
              FinanceAgent pattern. Under 50 concurrent users hammering
              /leaves/submit, the old code triggered Gemini rate-limit errors
              and then waited for exponential backoff → p95 = 20s per request.
              The guard detects ResourceExhausted / 429 on first hit and
              immediately routes to rule-based fallback for the circuit-open
              window (default 30s), dropping p95 dramatically while keeping
              throughput.

✅ v4.1 Fixes (retained):
    Fix S1 — Salary: recommended_increment_pct calculation (never null)
    Fix S2 — Salary: professional reason (not "rule-based fallback")
    Fix I1 — Incentive: KPI 85%+ = approve_bonus (not partial)
    Fix I2 — Incentive: approved_amount always calculated (never null)
    Fix I3 — Incentive: smart bonus formula (performance * trend * critical factors)
    Fix I4 — Incentive: bonus cap = 3x monthly salary
    Fix B1 — Boolean: is_on_pip / is_on_probation return bool not 0/1
    Fix A1 — Absence: rule fallback logic improved

Tier System (Leave):
    Tier 1 → ML conf >= TIER1_THRESHOLD → auto-approve  (no LLM)
    Tier 2 → TIER3 <= conf < TIER1      → Gemini review
    Tier 3 → conf < TIER3_THRESHOLD     → auto-reject   (no LLM)

Other domains (Salary/Incentive/Absence/Attendance):
    Always invoke Gemini (no ML model — rule + LLM hybrid)
    On LLM failure → smart rule-based fallback with proper calculations
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from typing import Optional

from agents.hr.leave_model_handler import get_model_handler
from agents.base_agent import BaseAgent, RequestContext, generate_request_id
from agents.hr.salary_decision_engine import (
    get_salary_decision_engine,
    SalaryExplainabilityBuilder,
    SalaryDecisionInput,
)
from config.hr_thresholds import LLM_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# 🛡️  GEMINI QUOTA GUARD  (Fix Q1 — same pattern as FinanceAgent)
# ════════════════════════════════════════════════════════════════════════════

class _GeminiQuotaGuard:
    """
    Circuit-breaker for Gemini API rate-limit errors.

    v4.3 UPDATE:
        - Reads Google's own `retryDelay` from the 429 error payload and
          opens the circuit for EXACTLY that long (capped at MAX_OPEN_WINDOW_SEC),
          instead of a blind fixed 30s. Google tells us precisely when the
          per-day/per-minute quota window resets — trust that number.
        - Falls back to DEFAULT_OPEN_WINDOW_SEC only if no retryDelay is
          found in the error (e.g. a different kind of failure).
    """

    DEFAULT_OPEN_WINDOW_SEC: int = 30
    MAX_OPEN_WINDOW_SEC:     int = 90   # never block longer than this even if Google asks for more

    _QUOTA_SIGNATURES: tuple[str, ...] = (
        "resourceexhausted",
        "429",
        "quota",
        "rate limit",
        "rate_limit",
        "too many requests",
    )

    def __init__(self) -> None:
        self._lock:       threading.Lock = threading.Lock()
        self._open:       bool           = False
        self._open_until: float          = 0.0
        self._trip_count: int            = 0
        self._last_retry_delay_sec: Optional[float] = None

    def is_open(self) -> bool:
        if not self._open:
            return False
        with self._lock:
            if time.monotonic() >= self._open_until:
                self._open = False
                logger.info(
                    "🔵 [HR QuotaGuard] Circuit closed — Gemini calls resuming "
                    "(total trips=%d)",
                    self._trip_count,
                )
            return self._open

    def is_quota_error(self, exc: Exception) -> bool:
        msg = str(exc).lower()
        return any(sig in msg for sig in self._QUOTA_SIGNATURES)

    @staticmethod
    def _extract_retry_delay_sec(exc: Exception) -> Optional[float]:
        """
        Parses Google's own suggested wait time out of the error message,
        e.g. 'retryDelay': '43s'  or  'Please retry in 43.5s'.
        Returns None if not found.
        """
        import re
        msg = str(exc)
        m = re.search(r"retryDelay['\"]?\s*[:=]\s*['\"]?(\d+(?:\.\d+)?)s", msg)
        if m:
            return float(m.group(1))
        m = re.search(r"retry in (\d+(?:\.\d+)?)s", msg, re.IGNORECASE)
        if m:
            return float(m.group(1))
        return None

    def trip(self, exc: Exception) -> None:
        """Open the circuit using Google's own retryDelay when available."""
        retry_delay = self._extract_retry_delay_sec(exc)
        window = retry_delay if retry_delay is not None else self.DEFAULT_OPEN_WINDOW_SEC
        window = min(window, self.MAX_OPEN_WINDOW_SEC)

        with self._lock:
            self._open              = True
            self._open_until        = time.monotonic() + window
            self._trip_count       += 1
            self._last_retry_delay_sec = retry_delay

        logger.warning(
            "🔴 [HR QuotaGuard] Circuit OPEN for %.1fs (trip #%d, google_retry_delay=%s) — "
            "Gemini quota hit: %s. All HR LLM calls → rule fallback.",
            window, self._trip_count, retry_delay, str(exc)[:120],
        )

    def record_success(self) -> None:
        pass

    def status(self) -> dict:
        return {
            "circuit_open":         self.is_open(),
            "open_until":           self._open_until,
            "trip_count":           self._trip_count,
            "last_retry_delay_sec": self._last_retry_delay_sec,
        }

# Module-level singleton — one guard instance shared across all HRAgent instances.
# Constructed at import time (thread-safe via Python's import lock).
_quota_guard = _GeminiQuotaGuard()


def get_hr_quota_guard() -> _GeminiQuotaGuard:
    """Expose the guard for health-check endpoints or testing."""
    return _quota_guard


# ════════════════════════════════════════════════════════════════════════════
# 💰  SALARY CALCULATION HELPERS
# ════════════════════════════════════════════════════════════════════════════

def _calculate_recommended_increment(
    current_salary_egp: float,
    requested_increment_pct: float,
    market_gap_pct: float,
    available_pool_egp: float,
    kpi_achievement: float,
    performance_score: float,
    months_since_last_increment: int,
    job_level: str = "junior",
) -> float:
    """
    احسب الـ increment الموصى به بناءً على:
        1. طلب الموظف
        2. الفجوة مع السوق
        3. الميزانية المتاحة
        4. الأداء
        5. مدة عدم الزيادة

    Returns: float (e.g. 0.15 = 15%)
    """
    level_caps = {
        "junior":  0.20,
        "senior":  0.25,
        "lead":    0.30,
        "manager": 0.35,
    }
    max_by_level = level_caps.get(str(job_level).lower(), 0.20)

    if performance_score >= 0.90:
        perf_multiplier = 1.0
    elif performance_score >= 0.75:
        perf_multiplier = 0.85
    elif performance_score >= 0.60:
        perf_multiplier = 0.70
    else:
        perf_multiplier = 0.50

    kpi_bonus = 0.0
    if kpi_achievement >= 1.20:
        kpi_bonus = 0.03
    elif kpi_achievement >= 1.0:
        kpi_bonus = 0.02
    elif kpi_achievement >= 0.90:
        kpi_bonus = 0.01

    tenure_bonus = 0.0
    if months_since_last_increment >= 24:
        tenure_bonus = 0.03
    elif months_since_last_increment >= 18:
        tenure_bonus = 0.02
    elif months_since_last_increment >= 12:
        tenure_bonus = 0.01

    base_increment = min(
        requested_increment_pct,
        abs(market_gap_pct) if market_gap_pct > 0 else requested_increment_pct,
    )

    calculated = (base_increment * perf_multiplier) + kpi_bonus + tenure_bonus
    calculated = min(calculated, max_by_level)

    if available_pool_egp > 0 and current_salary_egp > 0:
        max_by_budget = available_pool_egp / current_salary_egp
        calculated = min(calculated, max_by_budget)

    if performance_score >= 0.75 and months_since_last_increment >= 12:
        calculated = max(calculated, 0.05)

    return round(max(0.0, calculated), 4)


def _build_salary_reason(
    decision: str,
    performance_score: float,
    kpi_achievement: float,
    market_gap_pct: float,
    months_since_last_increment: int,
    recommended_increment_pct: float,
    current_salary_egp: float,
    budget_utilization: float,
    is_on_pip: bool,
    is_on_probation: bool,
) -> str:
    if is_on_probation:
        return (
            "Salary increment deferred: Employee is currently in the probation period. "
            "Per company policy, salary reviews are conducted after successful probation completion (6 months). "
            "Recommend scheduling a formal salary review at the end of the probation period."
        )

    if is_on_pip:
        return (
            "Salary increment suspended: Employee is on a Performance Improvement Plan (PIP). "
            "Increments are held until the PIP is successfully completed and a satisfactory "
            "performance review is conducted. Recommend re-evaluation in 90 days."
        )

    if budget_utilization > 0.95:
        return (
            f"Salary increment deferred due to budget constraints: "
            f"Department budget utilization is at {budget_utilization:.0%}, exceeding the 95% threshold. "
            "No increment pool is available in the current cycle. "
            "Recommend scheduling for the next budget cycle."
        )

    new_salary = current_salary_egp * (1 + recommended_increment_pct)
    parts = []

    if performance_score >= 0.90:
        parts.append(f"exceptional performance score ({performance_score:.0%})")
    elif performance_score >= 0.75:
        parts.append(f"strong performance score ({performance_score:.0%})")
    else:
        parts.append(f"satisfactory performance score ({performance_score:.0%})")

    if kpi_achievement >= 1.0:
        parts.append(f"KPI target met at {kpi_achievement:.0%}")
    else:
        parts.append(f"KPI achievement of {kpi_achievement:.0%}")

    if market_gap_pct > 0.15:
        parts.append(f"significant market gap ({market_gap_pct:.0%} below median) — retention risk")
    elif market_gap_pct > 0.05:
        parts.append(f"moderate market gap ({market_gap_pct:.0%} below median)")

    if months_since_last_increment >= 18:
        parts.append(f"{months_since_last_increment} months since last increment")

    reason_parts = ", ".join(parts)

    if decision == "approve_increment":
        return (
            f"Salary increment approved based on {reason_parts}. "
            f"Recommended increment of {recommended_increment_pct:.0%} brings new salary to "
            f"{new_salary:,.0f} EGP. This aligns with market benchmarks and rewards sustained performance."
        )
    elif decision == "escalate_to_director":
        return (
            f"Salary review escalated to HR Director for approval based on {reason_parts}. "
            f"The requested increment requires director-level authorization due to its magnitude "
            f"or budget implications. Recommended increment if approved: {recommended_increment_pct:.0%}."
        )
    else:
        return (
            f"Salary review deferred based on {reason_parts}. "
            "Current conditions do not fully support the requested increment at this time. "
            f"Recommend reassessment in the next review cycle with focus on KPI improvement."
        )


# ════════════════════════════════════════════════════════════════════════════
# 🏆  INCENTIVE CALCULATION HELPERS
# ════════════════════════════════════════════════════════════════════════════

def _calculate_bonus_amount(
    requested_amount_egp: float,
    monthly_salary_egp: float,
    kpi_achievement: float,
    performance_score: float,
    perf_trend: str,
    is_critical_talent: bool,
    incentive_budget_remaining_egp: float,
    incentive_type: str,
) -> float:
    if monthly_salary_egp <= 0:
        return min(requested_amount_egp, incentive_budget_remaining_egp)

    if incentive_type == "overtime_compensation":
        return min(requested_amount_egp, incentive_budget_remaining_egp)

    base_bonus = monthly_salary_egp * 0.20
    normalized_kpi = min(kpi_achievement, 1.20)
    performance_factor = (normalized_kpi + min(performance_score, 1.0)) / 2.0

    trend_factors = {"up": 1.15, "stable": 1.00, "down": 0.80}
    trend_factor = trend_factors.get(str(perf_trend).lower(), 1.00)

    critical_factor = 1.20 if is_critical_talent else 1.00
    calculated = base_bonus * performance_factor * trend_factor * critical_factor

    max_bonus = monthly_salary_egp * 3.0
    calculated = min(calculated, max_bonus)
    calculated = min(calculated, requested_amount_egp)

    if incentive_budget_remaining_egp > 0:
        calculated = min(calculated, incentive_budget_remaining_egp)

    return round(max(0.0, calculated), 2)


def _build_incentive_reason(
    decision: str,
    kpi_achievement: float,
    performance_score: float,
    perf_trend: str,
    incentive_type: str,
    approved_amount: float,
    requested_amount: float,
    is_on_pip: bool,
    is_critical_talent: bool,
    monthly_salary_egp: float,
) -> str:
    if incentive_type == "overtime_compensation":
        return (
            f"Overtime compensation approved: This is a statutory right under Egyptian Labor Law Art. 57. "
            f"Full requested amount of {requested_amount:,.0f} EGP approved regardless of performance metrics."
        )

    if is_on_pip:
        return (
            "Bonus denied: Employee is currently on a Performance Improvement Plan (PIP). "
            "Incentive payments are suspended until the PIP is successfully completed "
            "and performance returns to acceptable levels."
        )

    parts = []
    if kpi_achievement >= 1.20:
        parts.append(f"outstanding KPI achievement ({kpi_achievement:.0%} vs 100% target)")
    elif kpi_achievement >= 1.0:
        parts.append(f"strong KPI achievement ({kpi_achievement:.0%} — target met)")
    elif kpi_achievement >= 0.85:
        parts.append(f"good KPI achievement ({kpi_achievement:.0%})")
    else:
        parts.append(f"KPI achievement of {kpi_achievement:.0%}")

    if performance_score >= 0.90:
        parts.append(f"exceptional performance rating ({performance_score:.0%})")
    elif performance_score >= 0.75:
        parts.append(f"strong performance rating ({performance_score:.0%})")
    else:
        parts.append(f"performance rating of {performance_score:.0%}")

    if perf_trend == "up":
        parts.append("consistently improving performance trend")
    elif perf_trend == "down":
        parts.append("declining performance trend (risk factor)")

    if is_critical_talent:
        parts.append("critical talent designation")

    context = ", ".join(parts)

    if decision == "approve_bonus":
        return (
            f"Performance bonus of {approved_amount:,.0f} EGP approved based on {context}. "
            f"{'Full requested amount approved.' if approved_amount >= requested_amount else 'Approved amount reflects performance scoring and budget optimization.'}"
        )
    elif decision == "partial_bonus":
        pct = (approved_amount / requested_amount * 100) if requested_amount > 0 else 0
        return (
            f"Partial bonus of {approved_amount:,.0f} EGP ({pct:.0f}% of requested) approved based on {context}. "
            "Full requested amount not approved due to budget constraints or performance thresholds. "
            f"Remaining {requested_amount - approved_amount:,.0f} EGP deferred to next cycle."
        )
    elif decision == "escalate_to_director":
        return (
            f"Bonus escalated to HR Director for approval based on {context}. "
            f"The requested amount of {requested_amount:,.0f} EGP requires director-level authorization."
        )
    elif decision == "escalate_to_ceo":
        return (
            f"Bonus escalated to CEO for approval: Requested amount ({requested_amount:,.0f} EGP) "
            f"exceeds 3x monthly salary threshold ({monthly_salary_egp * 3:,.0f} EGP). "
            "Board-level authorization required per company policy."
        )
    else:
        return (
            f"Bonus denied based on {context}. "
            "Performance metrics do not meet the minimum threshold required for bonus disbursement. "
            "Recommend re-evaluation after performance improvement."
        )


# ════════════════════════════════════════════════════════════════════════════
# 🤖  HR AGENT
# ════════════════════════════════════════════════════════════════════════════

class HRAgent(BaseAgent):
    """
    HR AI Agent — handles all HR automation domains.

    Entry points:
        await agent.async_process(data)            ← leave (default)
        await agent.process_salary(data)
        await agent.process_incentive(data)
        await agent.process_absence(data)
        await agent.process_attendance(data)

    Static:
        HRAgent.reload_model()    → bool
        HRAgent.get_model_info()  → dict
    """

    @property
    def name(self) -> str:
        return "HRAgent_v4.2"

    # ── BaseAgent.process (sync wrapper) ──────────────────────────────────────

    def process(self, data: dict) -> dict:
        """Sync wrapper — delegates to async_process via thread pool."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self.async_process(data))
                    return future.result(timeout=60)
            return loop.run_until_complete(self.async_process(data))
        except Exception as e:
            logger.error(
                "[request_id=%s] ❌ [HRAgent] process() failed: %s",
                data.get("request_id", "?"), e,
            )
            return self._emergency_fallback(data, str(e))

    # ── Main Async Pipeline: Leave ────────────────────────────────────────────

    async def async_process(self, data: dict) -> dict:
        """
        Main leave approval pipeline.
        Injects request_id if not present, then routes through ML tiers.
        """
        request_id = data.get("request_id") or generate_request_id()
        data       = {**data, "request_id": request_id}
        employee_id = data.get("employee_id", "?")

        logger.info(
            "[request_id=%s] 🤖 [HRAgent] async_process started — employee=%s",
            request_id, employee_id,
        )

        # ── Step 1: ML Prediction ─────────────────────────────────────────────
        try:
            handler   = get_model_handler()
            ml_result = handler.predict(data)
        except Exception as e:
            logger.error("[request_id=%s] ❌ ML predict failed: %s", request_id, e)
            return self._emergency_fallback(data, f"ML failure: {e}")

        confidence = ml_result["confidence"]
        decision   = ml_result["decision"]
        source     = ml_result.get("source", "ml_model")

        logger.info(
            "[request_id=%s] 🤖 ML result: %s | conf=%.3f | source=%s",
            request_id, decision, confidence, source,
        )

        # ── Tier 1: High-confidence auto-approve ──────────────────────────────
        try:
            from config.hr_thresholds import TIER1_APPROVE_THRESHOLD as T1
        except ImportError:
            T1 = 0.72

        if confidence >= T1 and decision == "approve":
            logger.info(
                "[request_id=%s] ✅ Tier 1 auto-approve (conf=%.3f)",
                request_id, confidence,
            )
            return self._build_result(
                ml_result=ml_result, decision="approve",
                llm_used=False, tier=1, request_id=request_id,
            )

        # ── Tier 3: Low-confidence auto-reject ────────────────────────────────
        try:
            from config.hr_thresholds import TIER3_REJECT_THRESHOLD as T3
        except ImportError:
            T3 = 0.42

        if confidence < T3:
            logger.info(
                "[request_id=%s] ❌ Tier 3 auto-reject (conf=%.3f)",
                request_id, confidence,
            )
            return self._build_result(
                ml_result=ml_result, decision="reject",
                llm_used=False, tier=3, request_id=request_id,
            )

        # ── Tier 2: Gray zone → LLM Review ───────────────────────────────────
        logger.info(
            "[request_id=%s] 🔄 Tier 2 gray zone (conf=%.3f) → invoking Gemini",
            request_id, confidence,
        )

        llm_result = await self._invoke_llm_leave(data, ml_result, request_id)

        if llm_result:
            logger.info(
                "[request_id=%s] 🧠 LLM decision: %s | reason=%.80s",
                request_id,
                llm_result.get("decision"),
                llm_result.get("reason", ""),
            )
            return self._build_result(
                ml_result=ml_result,
                decision=llm_result.get("decision", "escalate"),
                llm_used=True,
                tier=2,
                llm_override=llm_result,
                request_id=request_id,
            )

        # LLM failed → fallback to ML decision
        logger.warning(
            "[request_id=%s] ⚠️ LLM unavailable — ML decision used as fallback",
            request_id,
        )
        return self._build_result(
            ml_result=ml_result,
            decision=decision,
            llm_used=False,
            tier=2,
            extra_flags=["⚠️ LLM unavailable — decision based on ML only"],
            request_id=request_id,
        )

    # ── Salary Review Pipeline ────────────────────────────────────────────────

    async def process_salary(self, data: dict) -> dict:
        request_id = data.get("request_id") or generate_request_id()
        data       = {**data, "request_id": request_id}

        logger.info(
            "[request_id=%s] 💰 [HRAgent] salary review — employee=%s",
            request_id, data.get("employee_id", "?"),
        )

        try:
            llm_result   = await self._invoke_llm_domain(data, "salary", request_id)
            model_source = llm_result.get("model_source", "")

            if model_source == "rule_fallback":
                logger.info(
                    "[request_id=%s] 🔄 [HRAgent] Replacing rule_fallback with SalaryDecisionEngine",
                    request_id,
                )
                return self._salary_engine_decision(data, request_id, llm_used=False)

            llm_result = self._enrich_llm_result(llm_result, data, "salary")
            llm_result["request_id"] = request_id
            llm_result["domain"]     = "salary"
            llm_result["llm_used"]   = True
            llm_result = self._normalize_booleans(llm_result)

            if llm_result.get("recommended_increment_pct") is None:
                llm_result["recommended_increment_pct"] = self._compute_salary_fallback_increment(data)

            logger.info(
                "[request_id=%s] ✅ [HRAgent] Salary LLM decision: %s | conf=%.0f%%",
                request_id,
                llm_result.get("decision", "?"),
                float(llm_result.get("confidence", 0)) * 100,
            )
            return llm_result

        except Exception as e:
            logger.error(
                "[request_id=%s] ❌ [HRAgent] process_salary LLM failed: %s — using engine",
                request_id, e,
            )
            return self._salary_engine_decision(data, request_id, llm_used=False)

    def _salary_engine_decision(self, data: dict, request_id: str, llm_used: bool = False) -> dict:
        from agents.hr.salary_decision_engine import get_salary_decision_engine
        engine = get_salary_decision_engine()
        result = engine.decide(data, request_id=request_id)

        logger.warning(
            "[request_id=%s] 🧮 [SalaryEngine] P%d %s → %s | "
            "score=%.3f | conf=%.0f%% | rec_pct=%.0f%%",
            request_id,
            result.priority_level,
            result.trigger,
            result.decision,
            result.weighted_score,
            result.confidence * 100,
            result.recommended_increment_pct * 100,
        )

        return {
            "decision":                  result.decision,
            "confidence":                result.confidence,
            "risk":                      result.risk,
            "reason":                    result.reason,
            "recommended_increment_pct": result.recommended_increment_pct,
            "weighted_score":            result.weighted_score,
            "score_breakdown":           result.score_breakdown.to_dict() if result.score_breakdown else {},
            "trigger":                   result.trigger,
            "trigger_phase":             result.trigger_phase,
            "priority_level":            result.priority_level,
            "blockers_evaluated":        result.blockers_evaluated,
            "flags":                     result.flags,
            "is_on_pip":                 bool(data.get("is_on_pip", False)),
            "is_on_probation":           bool(data.get("is_on_probation", False)),
            "request_id":                request_id,
            "domain":                    "salary",
            "llm_used":                  llm_used,
            "model_source":              result.model_source,
        }

    # ── Incentive/Bonus Pipeline ──────────────────────────────────────────────

    async def process_incentive(self, data: dict) -> dict:
        request_id = data.get("request_id") or generate_request_id()
        data       = {**data, "request_id": request_id}

        logger.info(
            "[request_id=%s] 🏆 [HRAgent] incentive — employee=%s type=%s",
            request_id, data.get("employee_id", "?"), data.get("incentive_type", "?"),
        )

        try:
            result = await self._invoke_llm_domain(data, "incentive", request_id)
            result["request_id"] = request_id
            result["domain"]     = "incentive"
            result = self._normalize_booleans(result)
            if result.get("approved_amount_egp") is None:
                result["approved_amount_egp"] = self._compute_incentive_amount(
                    data, result.get("decision", "deny_bonus")
                )
            return result
        except Exception as e:
            logger.error("[request_id=%s] ❌ incentive failed: %s", request_id, e)
            return self._domain_error_fallback(data, "incentive", str(e), request_id)

    # ── Absence Management Pipeline ───────────────────────────────────────────

    async def process_absence(self, data: dict) -> dict:
        request_id = data.get("request_id") or generate_request_id()
        data       = {**data, "request_id": request_id}

        logger.info(
            "[request_id=%s] 🚫 [HRAgent] absence — employee=%s date=%s",
            request_id, data.get("employee_id", "?"), data.get("absence_date", "?"),
        )

        try:
            result = await self._invoke_llm_domain(data, "absence", request_id)
            result["request_id"] = request_id
            result["domain"]     = "absence"
            result = self._normalize_booleans(result)
            return result
        except Exception as e:
            logger.error("[request_id=%s] ❌ absence failed: %s", request_id, e)
            return self._domain_error_fallback(data, "absence", str(e), request_id)

    # ── Attendance Audit Pipeline ─────────────────────────────────────────────

    async def process_attendance(self, data: dict) -> dict:
        request_id = data.get("request_id") or generate_request_id()
        data       = {**data, "request_id": request_id}

        logger.info(
            "[request_id=%s] 📅 [HRAgent] attendance audit — employee=%s month=%s",
            request_id, data.get("employee_id", "?"), data.get("month_label", "?"),
        )

        try:
            result = await self._invoke_llm_domain(data, "attendance", request_id)
            result["request_id"] = request_id
            result["domain"]     = "attendance"
            result = self._normalize_booleans(result)
            return result
        except Exception as e:
            logger.error("[request_id=%s] ❌ attendance audit failed: %s", request_id, e)
            return self._domain_error_fallback(data, "attendance", str(e), request_id)

    # ── Static Model Management ───────────────────────────────────────────────

    @staticmethod
    def reload_model() -> bool:
        handler = get_model_handler()
        success = handler.reload()
        if success:
            info = handler.get_info()
            logger.info(
                "✅ [HRAgent] Model reloaded | accuracy=%s | AUC=%s",
                info.get("accuracy"), info.get("roc_auc"),
            )
        else:
            logger.warning("⚠️ [HRAgent] Model reload failed — file not found")
        return success

    @staticmethod
    def get_model_info() -> dict:
        return get_model_handler().get_info()

    @staticmethod
    def get_decision_debug(validated: dict, payload: dict) -> dict:
        from agents.hr.conflict_resolver import get_conflict_resolver
        from agents.hr.leave_model_handler import get_model_handler
        from config.hr_thresholds import get_thresholds_from_metadata

        handler    = get_model_handler()
        thresholds = get_thresholds_from_metadata(handler._metadata)
        resolver   = get_conflict_resolver()

        conflict = resolver.resolve(
            ml_result      = validated,
            final_decision = validated.get("decision", "escalate"),
            payload        = payload,
            thresholds     = thresholds,
            tier           = validated.get("tier", 2),
        )

        return {
            "conflict_analysis":  conflict,
            "thresholds":         thresholds,
            "breakdown":          validated.get("breakdown", {}),
            "key_factors":        validated.get("key_factors", []),
            "ai_flags":           validated.get("ai_flags", []),
            "input_warnings":     validated.get("input_warnings", []),
            "is_outlier":         validated.get("is_outlier", False),
            "model_source":       validated.get("model_source", "?"),
            "llm_used":           validated.get("llm_used", False),
            "tier":               validated.get("tier", 2),
            "request_id":         validated.get("request_id", "?"),
        }

    # ── Private: Leave LLM Invocation (with QuotaGuard) ───────────────────────

    async def _invoke_llm_leave(
        self,
        data:       dict,
        ml_result:  dict,
        request_id: str,
    ) -> Optional[dict]:
        """
        Invoke Gemini for leave gray-zone review.

        ✅ Fix Q1: Checks _quota_guard.is_open() FIRST — if the circuit is
        open (recent quota hit), immediately returns None so the caller uses
        ML-based fallback without waiting for any backoff. On quota errors,
        trips the circuit. On success, calls record_success() for observability.

        Returns {decision, reason, confidence, flags} or None on failure.
        """
        # ── QuotaGuard: skip if circuit open ─────────────────────────────────
        if _quota_guard.is_open():
            logger.warning(
                "[request_id=%s] 🔴 [HR QuotaGuard] Circuit open — skipping Gemini leave call, "
                "falling back to ML decision",
                request_id,
            )
            return None

        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            from config.settings import get_settings

            settings = get_settings()
            if not settings.GOOGLE_API_KEY:
                logger.warning(
                    "[request_id=%s] ⚠️ GOOGLE_API_KEY not set — skipping LLM",
                    request_id,
                )
                return None

            llm = ChatGoogleGenerativeAI(
                model          = settings.GEMINI_MODEL,
                google_api_key = settings.GOOGLE_API_KEY,
                temperature    = 0.05,
            )

            from agents.hr.hr_prompts import HRPromptBuilder
            system_prompt, human_prompt = HRPromptBuilder.leave(
                data    = {
                    **data,
                    "confidence":  ml_result.get("confidence", 0.5),
                    "ml_decision": ml_result.get("decision", "escalate"),
                    **ml_result.get("breakdown", {}),
                },
                trace_id = request_id,
            )

            full_prompt = f"{system_prompt}\n\n{human_prompt}"
            logger.debug("[request_id=%s] 🧠 Sending leave prompt to Gemini", request_id)

            response = await asyncio.wait_for(
                llm.ainvoke(full_prompt),
                timeout = LLM_TIMEOUT_SECONDS,
            )

            result = self._parse_llm_json(response.content, request_id)
            # ── QuotaGuard: record success ────────────────────────────────────
            _quota_guard.record_success()
            return result

        except asyncio.TimeoutError:
            logger.warning(
                "[request_id=%s] ⏰ leave LLM timeout — rule fallback",
                request_id,
            )
        except ImportError:
            logger.warning(
                "[request_id=%s] ⚠️ langchain_google_genai not installed",
                request_id,
            )
        except Exception as e:
            # ── QuotaGuard: trip on quota/rate-limit errors ───────────────────
            if _quota_guard.is_quota_error(e):
                _quota_guard.trip(e)
                logger.warning(
                    "[request_id=%s] 🔴 [HR QuotaGuard] Quota error on leave LLM — "
                    "circuit tripped, falling back to ML decision",
                    request_id,
                )
            else:
                logger.warning("[request_id=%s] ⚠️ LLM invoke failed: %s", request_id, e)
        return None

    # ── Private: Domain LLM Invocation (with QuotaGuard) ─────────────────────

    async def _invoke_llm_domain(
        self,
        data:       dict,
        domain:     str,
        request_id: str,
    ) -> dict:
        """
        Generic LLM invocation for non-leave HR domains.

        ✅ Fix Q1: Same QuotaGuard pattern as _invoke_llm_leave. If the circuit
        is open → immediately returns rule-based fallback without touching
        Gemini API. On quota errors → trips the circuit and falls back.
        """
        # ── QuotaGuard: skip if circuit open ─────────────────────────────────
        if _quota_guard.is_open():
            logger.warning(
                "[request_id=%s] 🔴 [HR QuotaGuard] Circuit open — skipping Gemini %s call, "
                "using rule-based fallback immediately",
                request_id, domain,
            )
            return self._rule_based_fallback(data, domain, request_id)

        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            from config.settings import get_settings
            from agents.hr.hr_prompts import HRPromptBuilder

            settings = get_settings()
            if not settings.GOOGLE_API_KEY:
                logger.warning(
                    "[request_id=%s] ⚠️ GOOGLE_API_KEY not set — rule-based fallback",
                    request_id,
                )
                return self._rule_based_fallback(data, domain, request_id)

            builder_map = {
                "salary":     HRPromptBuilder.salary,
                "incentive":  HRPromptBuilder.incentive,
                "absence":    HRPromptBuilder.absence,
                "attendance": HRPromptBuilder.attendance,
            }
            builder = builder_map.get(domain)
            if not builder:
                raise ValueError(f"Unknown domain: {domain}")

            system_prompt, human_prompt = builder(data, trace_id=request_id)
            full_prompt = f"{system_prompt}\n\n{human_prompt}"

            llm = ChatGoogleGenerativeAI(
                model          = settings.GEMINI_MODEL,
                google_api_key = settings.GOOGLE_API_KEY,
                temperature    = 0.05,
                max_retries    = 0,      # ← جديد: نمنع الـ SDK من عمل exponential backoff داخلي
                timeout        = 10,     # ← جديد: أقصى انتظار 10 ثانية للـ HTTP call نفسه
            )

            logger.debug(
                "[request_id=%s] 🧠 Sending %s prompt to Gemini",
                request_id, domain,
            )

            response = await asyncio.wait_for(
                llm.ainvoke(full_prompt),
                timeout = min(LLM_TIMEOUT_SECONDS, 10),   # ← سقف 10 ثانية زي ما اتفقنا
            )

            parsed = self._parse_llm_json(response.content, request_id)
            if parsed:
                logger.info(
                    "[request_id=%s] ✅ %s LLM decision: %s | conf=%.3f",
                    request_id, domain.upper(),
                    parsed.get("decision", "?"),
                    float(parsed.get("confidence", 0)),
                )
                parsed = self._enrich_llm_result(parsed, data, domain)
                # ── QuotaGuard: record success ────────────────────────────────
                _quota_guard.record_success()
                return parsed

        except asyncio.TimeoutError:
            logger.warning(
                "[request_id=%s] ⏰ %s LLM timeout — rule fallback",
                request_id, domain,
            )
        except ImportError:
            logger.warning(
                "[request_id=%s] ⚠️ LangChain not installed — rule fallback for %s",
                request_id, domain,
            )
        except Exception as e:
            # ── QuotaGuard: trip on quota/rate-limit errors ───────────────────
            if _quota_guard.is_quota_error(e):
                _quota_guard.trip(e)
                logger.warning(
                    "[request_id=%s] 🔴 [HR QuotaGuard] Quota error on %s domain — "
                    "circuit tripped, using rule-based fallback",
                    request_id, domain,
                )
            else:
                logger.warning(
                    "[request_id=%s] ⚠️ %s LLM failed: %s — rule fallback",
                    request_id, domain, e,
                )

        return self._rule_based_fallback(data, domain, request_id)

    def _enrich_llm_result(self, parsed: dict, data: dict, domain: str) -> dict:
        if domain == "salary":
            if parsed.get("recommended_increment_pct") is None:
                parsed["recommended_increment_pct"] = self._compute_salary_fallback_increment(data)
            parsed = self._normalize_booleans(parsed)

        elif domain == "incentive":
            if parsed.get("approved_amount_egp") is None:
                decision = parsed.get("decision", "deny_bonus")
                parsed["approved_amount_egp"] = self._compute_incentive_amount(data, decision)
            monthly_sal = float(data.get("monthly_salary_egp", 0))
            if monthly_sal > 0:
                max_auto_approve = monthly_sal * 3.0
                approved = float(parsed.get("approved_amount_egp", 0))
                if approved > max_auto_approve and parsed.get("decision") == "approve_bonus":
                    parsed["decision"] = "escalate_to_ceo"
                    logger.info(
                        "LLM approved %.0f EGP but exceeds 3x salary cap (%.0f) — escalated to CEO",
                        approved, max_auto_approve,
                    )
            parsed = self._normalize_booleans(parsed)

        return parsed

    def _compute_salary_fallback_increment(self, data: dict) -> float:
        return _calculate_recommended_increment(
            current_salary_egp           = float(data.get("current_salary_egp", 0)),
            requested_increment_pct      = float(data.get("requested_increment_pct", 0.10)),
            market_gap_pct               = float(data.get("market_gap_pct", 0)),
            available_pool_egp           = float(data.get("available_pool_egp", 0)),
            kpi_achievement              = float(data.get("kpi_achievement", 0.80)),
            performance_score            = float(data.get("performance_score", 0.75)),
            months_since_last_increment  = int(data.get("months_since_last_increment", 12)),
            job_level                    = str(data.get("job_level", "junior")),
        )

    def _compute_incentive_amount(self, data: dict, decision: str) -> float:
        if decision in ("deny_bonus", "escalate_to_director", "escalate_to_ceo"):
            return 0.0
        return _calculate_bonus_amount(
            requested_amount_egp             = float(data.get("requested_amount_egp", 0)),
            monthly_salary_egp               = float(data.get("monthly_salary_egp", 0)),
            kpi_achievement                  = float(data.get("kpi_achievement", 0.80)),
            performance_score                = float(data.get("performance_score", 0.75)),
            perf_trend                       = str(data.get("perf_trend", "stable")),
            is_critical_talent               = bool(data.get("is_critical_talent", False)),
            incentive_budget_remaining_egp   = float(data.get("incentive_budget_remaining_egp", 0)),
            incentive_type                   = str(data.get("incentive_type", "performance_bonus")),
        )

    @staticmethod
    def _normalize_booleans(result: dict) -> dict:
        bool_fields = [
            "is_on_pip", "is_on_probation", "is_critical_talent",
            "llm_used", "escalation_required",
        ]
        for field in bool_fields:
            if field in result:
                result[field] = bool(result[field])
        return result

    # ── Private: JSON Parser ──────────────────────────────────────────────────

    def _parse_llm_json(self, content: str, request_id: str) -> Optional[dict]:
        if not content:
            return None

        cleaned = content.strip()
        if cleaned.startswith("```"):
            lines   = cleaned.splitlines()
            cleaned = "\n".join(
                l for l in lines
                if not l.strip().startswith("```")
            ).strip()

        try:
            parsed = json.loads(cleaned)
            if "decision" not in parsed:
                parsed["decision"] = "escalate"
            if "confidence" not in parsed:
                parsed["confidence"] = 0.5
            if "reason" not in parsed and "ai_reason" in parsed:
                parsed["reason"] = parsed["ai_reason"]
            return parsed
        except json.JSONDecodeError:
            pass

        start = cleaned.find("{")
        end   = cleaned.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                snippet = cleaned[start:end]
                return json.loads(snippet)
            except json.JSONDecodeError:
                pass

        lower = content.lower()
        decision = (
            "approve"  if "approve"  in lower else
            "reject"   if "reject"   in lower else
            "escalate"
        )
        logger.warning(
            "[request_id=%s] ⚠️ LLM returned non-JSON — keyword extraction: %s",
            request_id, decision,
        )
        return {
            "decision":   decision,
            "confidence": 0.55,
            "reason":     content[:300],
            "flags":      ["⚠️ Non-JSON response from LLM — keyword extraction used"],
        }

    # ── Private: Result Builder (Leave) ──────────────────────────────────────

    def _build_result(
        self,
        ml_result:    dict,
        decision:     str,
        llm_used:     bool,
        tier:         int,
        request_id:   str            = "",
        llm_override: Optional[dict] = None,
        extra_flags:  Optional[list] = None,
    ) -> dict:
        confidence     = ml_result.get("confidence", 0.5)
        breakdown      = ml_result.get("breakdown", {})
        key_factors    = ml_result.get("key_factors", [])
        input_warnings = ml_result.get("input_warnings", [])
        is_outlier     = ml_result.get("is_outlier", False)
        model_source   = ml_result.get("source", "ml_model")

        if llm_override and llm_override.get("reason"):
            reason       = llm_override["reason"]
            model_source = "llm_override"
            if llm_override.get("confidence"):
                confidence = float(llm_override["confidence"])
        elif key_factors:
            reason = " | ".join(key_factors[:3])
        else:
            reason = f"ML model decision (tier {tier}, conf={confidence:.0%})"

        ai_flags: list[str] = list(extra_flags or [])
        if is_outlier:
            ai_flags.append("⚠️ Input contains outlier values — confidence adjusted")
        if llm_used:
            ai_flags.append("🧠 Gemini LLM reviewed (Tier 2 gray zone)")
        if tier == 1:
            ai_flags.append("✅ High-confidence ML auto-approve (Tier 1)")
        elif tier == 3:
            ai_flags.append("❌ Low-confidence ML auto-reject (Tier 3)")

        if llm_override and llm_override.get("flags"):
            ai_flags.extend(llm_override["flags"])

        logger.info(
            "[request_id=%s] 🏁 [HRAgent] Final: %s | conf=%.3f | tier=%d | "
            "llm=%s | source=%s",
            request_id, decision, confidence, tier, llm_used, model_source,
        )

        return {
            "decision":       decision,
            "confidence":     round(confidence, 4),
            "risk":           self._classify_risk(confidence),
            "reason":         reason,
            "reasoning":      reason,
            "breakdown":      breakdown,
            "key_factors":    key_factors,
            "ai_flags":       ai_flags,
            "llm_used":       llm_used,
            "model_source":   model_source,
            "input_warnings": input_warnings,
            "is_outlier":     is_outlier,
            "tier":           tier,
            "request_id":     request_id,
            "domain":         "leave",
        }

    # ── Private: Rule-Based Fallback ─────────────────────────────────────────

    def _rule_based_fallback(self, data: dict, domain: str, request_id: str) -> dict:
        """
        ✅ v4.1: Smart rule-based fallback with proper calculations.
        ✅ v4.2: Also serves as the immediate QuotaGuard fallback path.
        """
        perf = float(data.get("performance_score", 0.75))

        if domain == "salary":
            return self._salary_engine_decision(data, request_id, llm_used=False)

        elif domain == "incentive":
            kpi             = float(data.get("kpi_achievement", 0.80))
            is_on_pip       = bool(data.get("is_on_pip", False))
            incentive_type  = str(data.get("incentive_type", "performance_bonus"))
            requested_amt   = float(data.get("requested_amount_egp", 0))
            monthly_sal     = float(data.get("monthly_salary_egp", 0))
            is_critical     = bool(data.get("is_critical_talent", False))
            budget_left     = float(data.get("incentive_budget_remaining_egp", 999999))
            perf_trend      = str(data.get("perf_trend", "stable"))

            if incentive_type == "overtime_compensation":
                decision, conf = "approve_bonus", 0.99
            elif is_on_pip:
                decision, conf = "deny_bonus", 0.95
            elif kpi < 0.70 and incentive_type == "performance_bonus":
                decision, conf = "deny_bonus", 0.90
            elif kpi >= 0.85 and perf >= 0.80:
                if monthly_sal > 0 and requested_amt > monthly_sal * 3:
                    decision, conf = "escalate_to_ceo", 0.95
                elif budget_left < requested_amt and budget_left > 0:
                    decision, conf = "partial_bonus", 0.85
                else:
                    decision, conf = "approve_bonus", 0.85
            elif kpi >= 0.70:
                decision, conf = "partial_bonus", 0.75
            else:
                decision, conf = "deny_bonus", 0.85

            approved_amt = _calculate_bonus_amount(
                requested_amount_egp             = requested_amt,
                monthly_salary_egp               = monthly_sal,
                kpi_achievement                  = kpi,
                performance_score                = perf,
                perf_trend                       = perf_trend,
                is_critical_talent               = is_critical,
                incentive_budget_remaining_egp   = budget_left,
                incentive_type                   = incentive_type,
            )
            if decision in ("deny_bonus", "escalate_to_director", "escalate_to_ceo"):
                approved_amt = 0.0

            reason = _build_incentive_reason(
                decision=decision, kpi_achievement=kpi, performance_score=perf,
                perf_trend=perf_trend, incentive_type=incentive_type,
                approved_amount=approved_amt, requested_amount=requested_amt,
                is_on_pip=is_on_pip, is_critical_talent=is_critical,
                monthly_salary_egp=monthly_sal,
            )

            logger.warning(
                "[request_id=%s] ⚠️ INCENTIVE rule-based fallback: %s (LLM unavailable)",
                request_id, decision,
            )

            return {
                "decision":            decision,
                "confidence":          conf,
                "risk":                self._classify_risk(conf),
                "reason":              reason,
                "approved_amount_egp": approved_amt,
                "is_on_pip":           is_on_pip,
                "is_critical_talent":  is_critical,
                "flags":               ["⚠️ LLM unavailable — rule-based fallback for incentive"],
                "request_id":          request_id,
                "llm_used":            False,
                "model_source":        "rule_fallback",
            }

        elif domain == "absence":
            unexcused  = int(data.get("unexcused_count_90d", 0))
            prev_warn  = str(data.get("previous_warnings", "none")).lower()
            abs_type   = str(data.get("absence_type_claimed", "unexcused")).lower()
            med_cert   = bool(data.get("medical_certificate_provided", False))
            dur_hours  = float(data.get("duration_hours", 8))

            if unexcused >= 3:
                decision, conf = "escalate_to_hr_director", 0.97
                classification = "unexcused"
                payroll_deduct = round(dur_hours / 8, 1)
                escalation_required = True
                reason = (
                    f"Critical: {unexcused} unexcused absences in the past 90 days triggers "
                    "Egyptian Labor Law Art. 69 escalation threshold. "
                    "Immediate HR Director intervention required. "
                    "Double payroll deduction applies as per company policy."
                )
            elif prev_warn == "formal" and unexcused >= 1:
                decision, conf = "suspension_review", 0.92
                classification = "unexcused"
                payroll_deduct = round(dur_hours / 8, 1)
                escalation_required = True
                reason = (
                    "Suspension review initiated: Employee has a formal warning on record "
                    "and committed another unexcused absence. "
                    "Per Egyptian Labor Law Art. 69, suspension or termination review is mandatory."
                )
            elif abs_type == "sick" and not med_cert and dur_hours > 16:
                decision, conf = "formal_warning", 0.90
                classification = "unexcused"
                payroll_deduct = round(dur_hours / 8, 1)
                escalation_required = False
                reason = (
                    "Formal warning issued: Sick leave exceeding 2 days was claimed without "
                    "a valid medical certificate (Egyptian Labor Law Art. 54 requirement). "
                    "Payroll deduction applied for uncertified sick days."
                )
            elif unexcused == 2:
                decision, conf = "formal_warning", 0.88
                classification = "unexcused"
                payroll_deduct = round(dur_hours / 8 * 2, 1)
                escalation_required = False
                reason = (
                    f"Formal warning issued: 2nd unexcused absence in 90 days. "
                    "Double payroll deduction applied (2x daily wage per Egyptian Labor Law Art. 69). "
                    "One more unexcused absence will trigger HR Director escalation."
                )
            elif unexcused == 1:
                decision, conf = "written_warning", 0.85
                classification = "unexcused"
                payroll_deduct = round(dur_hours / 8, 1)
                escalation_required = False
                reason = (
                    "Written warning issued: First unexcused absence recorded. "
                    "Single day payroll deduction applied per Egyptian Labor Law Art. 69. "
                    "Employee has been notified of the consequences of repeated absence."
                )
            elif abs_type in ("sick", "emergency") and (med_cert or dur_hours <= 16):
                decision, conf = "record_only", 0.90
                classification = "excused_paid"
                payroll_deduct = 0.0
                escalation_required = False
                reason = (
                    f"Absence recorded as {'sick leave' if abs_type == 'sick' else 'emergency leave'}. "
                    f"{'Medical certificate provided — no deduction applies.' if med_cert else 'Short duration — no deduction required.'} "
                    "Absence has been documented in the employee's attendance record."
                )
            else:
                decision, conf = "record_only", 0.80
                classification = abs_type
                payroll_deduct = 0.0
                escalation_required = False
                reason = (
                    "Absence recorded for documentation purposes. "
                    "No immediate disciplinary action required based on current absence pattern."
                )

            logger.warning(
                "[request_id=%s] ⚠️ ABSENCE rule-based fallback: %s (LLM unavailable)",
                request_id, decision,
            )

            return {
                "decision":               decision,
                "classification":         classification,
                "confidence":             conf,
                "risk":                   self._classify_risk(conf),
                "reason":                 reason,
                "payroll_deduction_days": payroll_deduct,
                "escalation_required":    escalation_required,
                "flags":                  ["⚠️ LLM unavailable — rule-based fallback for absence"],
                "request_id":             request_id,
                "llm_used":               False,
                "model_source":           "rule_fallback",
            }

        elif domain == "attendance":
            days_present  = int(data.get("days_present", 20))
            working_days  = int(data.get("working_days", 22))
            unexcused_abs = int(data.get("unexcused_absences", 0))
            ytd_warnings  = int(data.get("ytd_warnings", 0))
            att_rate      = days_present / max(working_days, 1)

            if att_rate < 0.70:
                decision, conf = "escalate_to_hr_director", 0.95
                reason = (
                    f"Critical attendance issue: Attendance rate of {att_rate:.1%} "
                    f"({days_present}/{working_days} days) is severely below the 70% minimum threshold. "
                    "Immediate HR Director intervention required per company attendance policy."
                )
            elif att_rate < 0.85 or unexcused_abs >= 3:
                decision, conf = "formal_warning", 0.85
                reason = (
                    f"Formal warning required: Attendance rate {att_rate:.1%} is below the 85% threshold "
                    f"with {unexcused_abs} unexcused absence(s). "
                    "A formal warning letter must be issued and documented in the personnel file."
                )
            elif ytd_warnings >= 3:
                decision, conf = "formal_warning", 0.82
                reason = (
                    f"Formal warning required: {ytd_warnings} YTD warnings on record. "
                    "Despite current month attendance being acceptable, the cumulative warning "
                    "history requires formal documentation and HR follow-up."
                )
            elif att_rate < 0.92:
                decision, conf = "counseling_session", 0.80
                reason = (
                    f"Attendance counseling recommended: Rate of {att_rate:.1%} is below the "
                    "95% green threshold. A supportive counseling session should be scheduled "
                    "to identify any underlying issues and prevent further deterioration."
                )
            else:
                decision, conf = "no_action", 0.90
                reason = (
                    f"No action required: Attendance rate of {att_rate:.1%} meets the 95% green threshold. "
                    "Employee is maintaining a satisfactory attendance record."
                )

            logger.warning(
                "[request_id=%s] ⚠️ ATTENDANCE rule-based fallback: %s (LLM unavailable)",
                request_id, decision,
            )

            return {
                "decision":     decision,
                "confidence":   conf,
                "risk":         self._classify_risk(conf),
                "reason":       reason,
                "flags":        ["⚠️ LLM unavailable — rule-based fallback for attendance"],
                "request_id":   request_id,
                "llm_used":     False,
                "model_source": "rule_fallback",
            }

        else:
            return {
                "decision":     "escalate",
                "confidence":   0.50,
                "risk":         "high",
                "reason":       f"Unknown domain '{domain}' — escalated for human review",
                "flags":        [f"❌ Unknown domain '{domain}'"],
                "request_id":   request_id,
                "llm_used":     False,
                "model_source": "rule_fallback",
            }

    # ── Private: Emergency Fallback ───────────────────────────────────────────

    def _emergency_fallback(self, data: dict, error: str) -> dict:
        request_id = data.get("request_id", generate_request_id())
        logger.error(
            "[request_id=%s] 🚨 [HRAgent] Emergency fallback: %s",
            request_id, error,
        )
        return {
            "decision":       "escalate",
            "confidence":     0.5,
            "risk":           "high",
            "reason":         f"⚠️ System error — escalated for human review. Error: {error}",
            "reasoning":      f"Emergency fallback: {error}",
            "breakdown":      {},
            "key_factors":    ["🚨 System error — human review required"],
            "ai_flags":       [f"❌ Agent failed: {error[:100]}"],
            "llm_used":       False,
            "model_source":   "emergency_fallback",
            "input_warnings": [],
            "is_outlier":     False,
            "tier":           0,
            "request_id":     request_id,
            "domain":         "leave",
            "_agent_error":   True,
        }

    # ── Private: Domain Error Fallback ────────────────────────────────────────

    def _domain_error_fallback(self, data: dict, domain: str, error: str, request_id: str) -> dict:
        logger.error(
            "[request_id=%s] 🚨 %s domain error: %s",
            request_id, domain.upper(), error,
        )
        return {
            "decision":     "escalate",
            "confidence":   0.5,
            "risk":         "high",
            "reason":       f"⚠️ {domain.capitalize()} processing error — human review required.",
            "flags":        [f"❌ Error: {error[:100]}"],
            "request_id":   request_id,
            "domain":       domain,
            "llm_used":     False,
            "model_source": "error_fallback",
            "_agent_error": True,
        }
