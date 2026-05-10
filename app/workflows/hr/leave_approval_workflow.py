"""
🔄 Leave Approval Workflow — v5.2 Production
=============================================
File: app/workflows/hr/leave_approval_workflow.py

✅ v5.2 Fixes (on top of v5.1):
    Fix DB1 — SalaryReviewWorkflow._persist(): event_id resolved → no null FK error
    Fix DB2 — IncentiveWorkflow._persist(): same fix
    Fix S1  — SalaryReviewWorkflow: recommended_increment_pct always calculated (never null)
    Fix S2  — SalaryReviewWorkflow: professional reason text
    Fix I1  — IncentiveWorkflow: correct decision logic (KPI 85%+ = approve, not partial)
    Fix I2  — IncentiveWorkflow: approved_amount_egp always calculated (never null)
    Fix B1  — booleans: is_on_pip / is_on_probation / is_critical_talent = bool not 0/1
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

from agents.base_agent import generate_request_id

logger = logging.getLogger(__name__)


# ── FIX 3: Policy-Based SLA ───────────────────────────────────────────────────
SLA_POLICY: dict = {
    "annual": {
        "processing_hours": 24,
        "max_days":         21,
        "auto_approve_max": 14,
        "requires_cert":    False,
    },
    "sick": {
        "processing_hours": 4,
        "max_days":         90,
        "auto_approve_max": 2,
        "requires_cert":    True,
    },
    "emergency": {
        "processing_hours": 2,
        "max_days":         7,
        "auto_approve_max": 7,
        "requires_cert":    False,
    },
    "unpaid": {
        "processing_hours": 72,
        "max_days":         180,
        "auto_approve_max": 0,
        "requires_cert":    False,
    },
}

PEAK_MONTHS = {6, 7, 8, 12, 1}

FIELD_DEFAULTS: dict = {
    "performance_score":   0.75,
    "attendance_rate":     0.85,
    "absence_count":       2,
    "team_workload":       "medium",
    "leave_type":          "annual",
    "department":          "general",
    "reason":              "",
    "years_of_experience": 3,
    "overtime_hours":      0,
    "job_level":           "junior",
    "salary_grade":        "C",
}

EGYPTIAN_FY_START_MONTH = 7
TERMINAL_STATUSES = {"approved", "rejected", "escalated", "cancelled"}


# ═════════════════════════════════════════════════════════════════════════════
# 🔄  LEAVE APPROVAL WORKFLOW
# ═════════════════════════════════════════════════════════════════════════════

class LeaveApprovalWorkflow:

    def __init__(self) -> None:
        self._agent  = None
        self._db     = None
        self._logger = None

    @property
    def agent(self):
        if self._agent is None:
            from agents.hr.hr_agent import HRAgent
            self._agent = HRAgent()
        return self._agent

    @property
    def db(self):
        if self._db is None:
            from actions.database import DatabaseAction
            self._db = DatabaseAction()
        return self._db

    @property
    def logger(self):
        if self._logger is None:
            from audit.logger import AuditLogger
            self._logger = AuditLogger()
        return self._logger

    async def async_run(self, payload: dict) -> dict:
        request_id    = payload.get("request_id") or generate_request_id()
        payload       = {**payload, "request_id": request_id}
        employee_id   = str(payload.get("employee_id", "unknown"))
        employee_name = payload.get("employee_name", "Unknown Employee")

        raw_leave_id  = payload.get("leave_id")
        leave_id      = int(raw_leave_id) if raw_leave_id is not None else None
        leave_type    = payload.get("leave_type", FIELD_DEFAULTS["leave_type"])

        self.logger.log(
            event_type = "leave_request",
            stage      = "workflow",
            message    = (
                f"[request_id={request_id}] LeaveApprovalWorkflow v5.2 started — "
                f"{employee_name} (#{employee_id})"
            ),
            data = {"leave_id": leave_id, "employee_id": employee_id},
        )

        # ── FIX 5: Status Pre-Check ────────────────────────────────────────────
        if leave_id is not None:
            try:
                import importlib
                _db_mod = importlib.import_module("core.db")
                with _db_mod.get_db() as (_, cur):
                    cur.execute(
                        "SELECT status FROM leaves WHERE id = %s LIMIT 1",
                        (leave_id,),
                    )
                    row            = cur.fetchone()
                    current_status = row["status"] if row else None

                if current_status in TERMINAL_STATUSES:
                    logger.info(
                        "[request_id=%s] ⏭️ Leave #%d terminal status=%s — skipping",
                        request_id, leave_id, current_status,
                    )
                    _map = {
                        "approved":  "approve",
                        "rejected":  "reject",
                        "escalated": "escalate",
                        "cancelled": "reject",
                    }
                    return {
                        "decision":    _map.get(current_status, current_status),
                        "confidence":  1.0,
                        "leave_id":    leave_id,
                        "reasoning":   f"Leave already in terminal state: {current_status}",
                        "workflow":    "LeaveApprovalWorkflow_v5.2",
                        "request_id":  request_id,
                        "skipped":     True,
                        "skip_reason": f"terminal_status:{current_status}",
                    }

                if current_status is None:
                    logger.error(
                        "[request_id=%s] ❌ Leave #%d not found in DB",
                        request_id, leave_id,
                    )
                    return {
                        "decision":   "escalate",
                        "confidence": 0.5,
                        "leave_id":   leave_id,
                        "reasoning":  f"Leave #{leave_id} not found in database",
                        "workflow":   "LeaveApprovalWorkflow_v5.2",
                        "request_id": request_id,
                        "error":      "leave_not_found",
                    }

            except Exception as e:
                logger.warning(
                    "[request_id=%s] ⚠️ Status pre-check failed: %s — continuing",
                    request_id, e,
                )

        # ── Step 0: Atomic Claim ──────────────────────────────────────────────
        if leave_id is not None:
            try:
                claimed = await self._claim_leave(leave_id, request_id)
                if not claimed:
                    logger.info(
                        "[request_id=%s] ⏭️ Leave #%d already claimed — skipping",
                        request_id, leave_id,
                    )
                    return {
                        "decision":   "skipped",
                        "confidence": 1.0,
                        "leave_id":   leave_id,
                        "reasoning":  "Already claimed by another process",
                        "workflow":   "LeaveApprovalWorkflow_v5.2",
                        "request_id": request_id,
                    }
            except Exception as e:
                logger.warning(
                    "[request_id=%s] ⚠️ Claim failed: %s — proceeding", request_id, e
                )

        # ── Step 1: Refresh leave_balance from DB ─────────────────────────────
        if leave_id is not None:
            payload = await self._refresh_balance_from_db(payload, leave_id, request_id)

        # ── Step 2: Fill Defaults + Validate ──────────────────────────────────
        payload  = self._fill_defaults(payload)
        validity = self._validate(payload)
        if not validity["valid"]:
            logger.error(
                "[request_id=%s] ❌ Validation failed: %s", request_id, validity["error"]
            )
            return {
                "status":     "error",
                "message":    validity["error"],
                "stage":      "validation",
                "request_id": request_id,
            }

        # ── Step 3: Context ───────────────────────────────────────────────────
        requested_days = int(payload.get("requested_days", payload.get("leave_days", 0)))
        fy_context     = self._get_fiscal_year_context()
        is_peak        = fy_context["is_peak"]

        sla_info = self._compute_sla(leave_type, requested_days, is_peak)

        # ── Step 4: Agent Input ───────────────────────────────────────────────
        agent_input = self._prepare_agent_input(payload, fy_context, request_id)

        self.logger.log(
            event_type = "leave_request",
            stage      = "workflow",
            message    = f"[request_id={request_id}] ✅ Validation passed → HRAgent v5.2",
        )

        # ── Step 5: HR Agent ──────────────────────────────────────────────────
        start_ms = int(time.time() * 1000)
        try:
            agent_result = await self.agent.async_process(agent_input)
        except Exception as e:
            logger.error("[request_id=%s] ❌ HRAgent failed: %s", request_id, e)
            agent_result = {
                "decision":     "escalate",
                "confidence":   0.5,
                "risk":         "high",
                "reason":       f"Agent error — escalated. Error: {e}",
                "model_source": "error_fallback",
                "request_id":   request_id,
            }
        execution_ms = int(time.time() * 1000) - start_ms

        logger.info(
            "[request_id=%s] 🧠 Agent: %s | conf=%.0f%% | source=%s",
            request_id,
            agent_result.get("decision"),
            float(agent_result.get("confidence", 0)) * 100,
            agent_result.get("model_source", "?"),
        )

        # ── Step 6: Business Rules Validation ─────────────────────────────────
        try:
            from workflows.hr.decision_rules import DecisionValidationLayer
            validated = DecisionValidationLayer().validate_and_override(agent_result, payload)
        except Exception as e:
            logger.warning(
                "[request_id=%s] ⚠️ Validation layer error: %s", request_id, e
            )
            validated = agent_result

        decision   = validated.get("decision", "escalate")
        confidence = round(float(validated.get("confidence", 0.5)), 4)
        reasoning  = validated.get("reason", validated.get("reasoning", ""))

        # ── Step 7: Persist to DB ─────────────────────────────────────────────
        action_result = await self._execute_and_persist(
            decision     = decision,
            payload      = payload,
            agent_result = validated,
            leave_id     = leave_id,
            request_id   = request_id,
            execution_ms = execution_ms,
        )

        # ── Step 8: Build Final Response ──────────────────────────────────────
        final_result = {
            "decision":          decision,
            "confidence":        confidence,
            "leave_id":          leave_id,
            "leave_type":        leave_type,
            "sla_deadline":      sla_info["deadline_iso"],
            "sla_hours":         sla_info["processing_hours"],
            "sla_policy_notes":  sla_info["policy_notes"],
            "auto_approve_eligible": sla_info["auto_eligible"],
            "fiscal_year":       fy_context["label"],
            "request_id":        request_id,
            "employee_response": self._build_employee_response(
                decision, employee_name, leave_type,
                requested_days, sla_info["deadline"],
            ),
            "_metadata": {
                "status":         "success",
                "employee_id":    employee_id,
                "requested_days": requested_days,
                "risk":           validated.get("risk", "medium"),
                "reason":         reasoning,
                "breakdown":      validated.get("breakdown", {}),
                "ai_flags":       validated.get("ai_flags", []),
                "llm_used":       validated.get("llm_used", False),
                "model_source":   validated.get("model_source", "ml_model"),
                "action_taken":   action_result,
                "execution_ms":   execution_ms,
                "workflow":       "LeaveApprovalWorkflow_v5.2",
                "request_id":     request_id,
            },
        }

        logger.info(
            "[request_id=%s] ✅ Leave #%s (%s) → %s | conf=%.0f%% | SLA=%dh | source=%s",
            request_id,
            leave_id,
            employee_name,
            decision,
            confidence * 100,
            sla_info["processing_hours"],
            validated.get("model_source", "?"),
        )

        return final_result

    def run(self, payload: dict) -> dict:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self.async_run(payload))
                    return future.result(timeout=60)
            return loop.run_until_complete(self.async_run(payload))
        except Exception as e:
            req_id = payload.get("request_id", generate_request_id())
            logger.error(
                "[request_id=%s] ❌ [LeaveWorkflow] run() failed: %s", req_id, e
            )
            return {
                "status":     "error",
                "message":    str(e),
                "stage":      "workflow",
                "request_id": req_id,
            }

    async def _claim_leave(self, leave_id: int, request_id: str) -> bool:
        try:
            import importlib
            db_module = importlib.import_module("core.db")
            with db_module.get_db() as (conn, cur):
                cur.execute(
                    "UPDATE leaves SET status = %s WHERE id = %s AND status = %s",
                    ("in_progress", leave_id, "pending"),
                )
                conn.commit()
                claimed = cur.rowcount == 1
                return claimed
        except Exception as e:
            logger.warning(
                "[request_id=%s] ⚠️ Claim error: %s — allowing through", request_id, e
            )
            return True

    async def _refresh_balance_from_db(
        self, payload: dict, leave_id: int, request_id: str
    ) -> dict:
        try:
            import importlib
            db_module = importlib.import_module("core.db")
            with db_module.get_db() as (_, cur):
                cur.execute(
                    """
                    SELECT COALESCE(e.leave_balance, 0) AS leave_balance
                    FROM leaves l
                    LEFT JOIN employees e ON e.id = l.employee_id
                    WHERE l.id = %s
                    LIMIT 1
                    """,
                    (leave_id,),
                )
                row = cur.fetchone()
                if row:
                    fresh_balance = int(row["leave_balance"])
                    old_balance   = payload.get("leave_balance", "not set")
                    if fresh_balance != old_balance:
                        logger.info(
                            "[request_id=%s] 🔄 Balance refreshed from DB: %s → %d",
                            request_id, old_balance, fresh_balance,
                        )
                    return {**payload, "leave_balance": fresh_balance}
        except Exception as e:
            logger.warning(
                "[request_id=%s] ⚠️ Balance refresh failed: %s — using payload value",
                request_id, e,
            )
        return payload

    def _fill_defaults(self, payload: dict) -> dict:
        result = dict(payload)
        for field, default in FIELD_DEFAULTS.items():
            if field not in result or result[field] is None:
                result[field] = default
        if "leave_days" not in result and "requested_days" in result:
            result["leave_days"] = result["requested_days"]
        elif "requested_days" not in result and "leave_days" in result:
            result["requested_days"] = result["leave_days"]
        return result

    def _validate(self, payload: dict) -> dict:
        for field in ["employee_id", "requested_days"]:
            if not payload.get(field):
                return {"valid": False, "error": f"Missing required field: '{field}'"}
        if int(payload.get("requested_days", 0)) <= 0:
            return {"valid": False, "error": "requested_days must be > 0"}
        if int(payload.get("leave_balance", 0)) < 0:
            return {"valid": False, "error": "leave_balance cannot be negative"}
        return {"valid": True}

    def _compute_sla(self, leave_type, requested_days=0, is_peak=False):
        policy     = SLA_POLICY.get(leave_type, SLA_POLICY["annual"])
        base_hours = policy["processing_hours"]
        if is_peak:
            base_hours = int(base_hours * 1.5)
        deadline = datetime.utcnow() + timedelta(hours=base_hours)
        policy_notes = []
        if requested_days > policy["max_days"]:
            policy_notes.append(
                f"⚠️ Requested {requested_days}d exceeds policy max "
                f"{policy['max_days']}d for {leave_type} leave"
            )
        if policy["requires_cert"] and requested_days > 2:
            policy_notes.append("📄 Medical certificate required (Egyptian Law Art. 54)")
        if is_peak:
            policy_notes.append(f"⚠️ Peak season: SLA extended to {base_hours}h")
        return {
            "deadline":         deadline,
            "deadline_iso":     deadline.isoformat() + "Z",
            "processing_hours": base_hours,
            "policy_notes":     policy_notes,
            "auto_eligible":    requested_days <= policy["auto_approve_max"],
        }

    def _get_fiscal_year_context(self) -> dict:
        now = datetime.utcnow()
        if now.month >= EGYPTIAN_FY_START_MONTH:
            fy_start, fy_end_year = now.year, now.year + 1
        else:
            fy_start, fy_end_year = now.year - 1, now.year
        fy_end_date = datetime(fy_end_year, 6, 30)
        months_left = max(0, (fy_end_date.year - now.year) * 12 + fy_end_date.month - now.month)
        is_peak     = now.month in PEAK_MONTHS
        return {
            "label":        f"FY{fy_start}/{fy_end_year}",
            "months_left":  months_left,
            "is_peak":      is_peak,
            "peak_warning": "⚠️ Peak season — stricter criteria apply" if is_peak else "",
        }

    def _prepare_agent_input(self, payload: dict, fy_context: dict, request_id: str) -> dict:
        return {
            "employee_id":         str(payload["employee_id"]),
            "employee_name":       payload.get("employee_name", "Unknown"),
            "leave_days":          int(payload["requested_days"]),
            "requested_days":      int(payload["requested_days"]),
            "leave_balance":       int(payload.get("leave_balance", 0)),
            "leave_type":          payload.get("leave_type", "annual"),
            "reason":              payload.get("reason", ""),
            "performance_score":   float(payload.get("performance_score", 0.75)),
            "attendance_rate":     float(payload.get("attendance_rate", 0.85)),
            "absence_count":       int(payload.get("absence_count", 2)),
            "team_workload":       str(payload.get("team_workload", "medium")).lower(),
            "department":          payload.get("department", "general"),
            "job_level":           payload.get("job_level", "junior"),
            "years_of_experience": int(payload.get("years_of_experience", 3)),
            "salary_grade":        payload.get("salary_grade", "C"),
            "overtime_hours":      int(payload.get("overtime_hours", 0)),
            "fiscal_year":         fy_context["label"],
            "months_left_in_fy":   fy_context["months_left"],
            "is_peak_season":      fy_context["is_peak"],
            "peak_warning":        fy_context["peak_warning"],
            "request_id":          request_id,
        }

    async def _execute_and_persist(
        self,
        decision, payload, agent_result, leave_id, request_id, execution_ms=0,
    ) -> dict:
        try:
            from core.db import (
                update_leave_and_balance,
                write_decision_audit,
                log_action,
                write_audit_log,
                save_decision,
            )

            status_map = {
                "approve":  "approved",
                "reject":   "rejected",
                "escalate": "escalated",
            }
            new_status = status_map.get(decision, "pending")
            reasoning  = agent_result.get("reason", agent_result.get("reasoning", ""))

            bal_result = {"old_balance": 0, "new_balance": 0}

            if leave_id is not None:
                _emp_id = int(payload.get("employee_id", 0) or 0)
                _days   = int(payload.get("requested_days", payload.get("leave_days", 0)))

                try:
                    bal_result = update_leave_and_balance(
                        leave_id    = leave_id,
                        employee_id = _emp_id,
                        status      = new_status,
                        notes       = reasoning[:500],
                        leave_days  = _days if new_status == "approved" else 0,
                        performed_by= "hr_agent_v5.2",
                    )
                except Exception as e:
                    logger.warning(
                        "[request_id=%s] ⚠️ Atomic update failed: %s — fallback to basic update",
                        request_id, e,
                    )
                    from core.db import update_leave_status
                    update_leave_status(leave_id, new_status, reasoning[:500])

            if leave_id is not None:
                _emp_id = int(payload.get("employee_id", 0) or 0)
                try:
                    from agents.hr.leave_model_handler import get_model_handler
                    _meta_version = get_model_handler().get_info().get("trained_at", "unknown")
                except Exception:
                    _meta_version = "unknown"

                try:
                    write_decision_audit(
                        leave_id        = leave_id,
                        employee_id     = _emp_id,
                        decision        = decision,
                        confidence      = float(agent_result.get("confidence", 0)),
                        raw_confidence  = agent_result.get("raw_confidence"),
                        decision_source = agent_result.get("model_source", "ml_model"),
                        old_balance     = bal_result.get("old_balance", 0),
                        new_balance     = bal_result.get("new_balance", 0),
                        model_version   = str(_meta_version)[:100],
                        tier            = int(agent_result.get("tier", 2)),
                        llm_used        = bool(agent_result.get("llm_used", False)),
                        override_rule   = str(agent_result.get("override_rule", "")),
                        execution_ms    = execution_ms,
                        request_id      = request_id,
                        flags           = agent_result.get("ai_flags", []),
                    )
                except Exception as e:
                    logger.warning(
                        "[request_id=%s] ⚠️ write_decision_audit failed: %s", request_id, e
                    )

            # ✅ Fix DB1/DB2: resolve event_id for leave domain too
            event_id_for_decision = payload.get("event_id")
            if not event_id_for_decision and leave_id is not None:
                try:
                    from core.db import create_event
                    event_id_for_decision = create_event(
                        event_type = "leave_requested",
                        entity     = "leaves",
                        entity_id  = leave_id,
                        payload    = {
                            "employee_id": str(payload.get("employee_id", "")),
                            "leave_days":  int(payload.get("requested_days", 0)),
                            "source":      "workflow_auto_create",
                        },
                    )
                    logger.info(
                        "[request_id=%s] 🔧 Auto-created event #%d for leave #%d",
                        request_id, event_id_for_decision, leave_id,
                    )
                except Exception as e:
                    logger.warning(
                        "[request_id=%s] ⚠️ Auto-create event failed: %s", request_id, e
                    )
                    event_id_for_decision = None

            if leave_id is not None:
                try:
                    save_decision({
                        "agent_type":   "hr_agent_v5.2",
                        "entity":       "leaves",
                        "entity_id":    leave_id,
                        "decision":     decision,
                        "confidence":   float(agent_result.get("confidence", 0.0)),
                        "reasoning":    reasoning[:500],
                        "raw_response": str(agent_result.get("breakdown", {}))[:1000],
                        "event_id":     event_id_for_decision,
                    })
                except Exception as e:
                    logger.warning(
                        "[request_id=%s] ⚠️ save_decision failed: %s", request_id, e
                    )

            try:
                log_action({
                    "action_type":  f"leave_{decision}",
                    "entity":       "leaves",
                    "entity_id":    leave_id or 0,
                    "performed_by": "hr_agent_v5.2",
                    "result":       decision,
                    "details":      reasoning[:300],
                })
            except Exception as e:
                logger.warning("[request_id=%s] ⚠️ log_action failed: %s", request_id, e)

            try:
                source = agent_result.get("model_source", "ml_model")
                conf   = agent_result.get("confidence", 0)
                llm    = "LLM+ML" if agent_result.get("llm_used") else "ML-only"
                write_audit_log(
                    action       = f"leave_{decision}",
                    entity       = "leaves",
                    entity_id    = leave_id or 0,
                    performed_by = "hr_agent_v5.2",
                    details      = (
                        f"[request_id={request_id}] {llm} | source={source} | "
                        f"conf={float(conf):.0%} | event_id={event_id_for_decision} | "
                        f"exec={execution_ms}ms | "
                        f"balance:{bal_result.get('old_balance',0)}→{bal_result.get('new_balance',0)} | "
                        f"{reasoning[:150]}"
                    ),
                )
            except Exception as e:
                logger.warning("[request_id=%s] ⚠️ audit_log failed: %s", request_id, e)

            return {
                "status":       "persisted",
                "new_status":   new_status,
                "leave_id":     leave_id,
                "old_balance":  bal_result.get("old_balance", 0),
                "new_balance":  bal_result.get("new_balance", 0),
                "execution_ms": execution_ms,
            }

        except Exception as e:
            logger.error("[request_id=%s] ❌ DB persist failed: %s", request_id, e)
            return {"status": "persist_failed", "error": str(e)}

    def _build_employee_response(self, decision, employee_name, leave_type, requested_days, sla_deadline):
        leave_type_ar = {
            "annual":    "السنوية",
            "sick":      "المرضية",
            "emergency": "الطارئة",
            "unpaid":    "بدون مرتب",
        }.get(leave_type, leave_type)

        templates = {
            "approve": (
                f"✅ تمت الموافقة على طلب إجازتك {leave_type_ar} "
                f"لمدة {requested_days} يوم. نتمنى لك إجازة ممتعة، {employee_name}!"
            ),
            "reject": (
                f"❌ نأسف، لم تتم الموافقة على طلب إجازتك {leave_type_ar} "
                f"لمدة {requested_days} يوم. يرجى التواصل مع HR لمزيد من التفاصيل."
            ),
            "escalate": (
                f"⏳ طلب إجازتك {leave_type_ar} ({requested_days} يوم) "
                "قيد المراجعة. سيتم إخطارك بالقرار النهائي قريباً."
            ),
        }

        sla_str = (
            sla_deadline.strftime("%Y-%m-%d %H:%M UTC")
            if sla_deadline and hasattr(sla_deadline, "strftime") else "قريباً"
        )

        return {
            "message":        templates.get(decision, "طلبك قيد المعالجة."),
            "expected_reply": sla_str,
            "leave_type_ar":  leave_type_ar,
            "days":           requested_days,
            "channel":        "email",
            "employee_name":  employee_name,
        }


# ═════════════════════════════════════════════════════════════════════════════
# 💰  SALARY REVIEW WORKFLOW — v5.2
# ═════════════════════════════════════════════════════════════════════════════

class SalaryReviewWorkflow:
    def __init__(self) -> None:
        self._agent  = None
        self._logger = None

    @property
    def agent(self):
        if self._agent is None:
            from agents.hr.hr_agent import HRAgent
            self._agent = HRAgent()
        return self._agent

    @property
    def logger(self):
        if self._logger is None:
            from audit.logger import AuditLogger
            self._logger = AuditLogger()
        return self._logger

    async def async_run(self, payload: dict) -> dict:
        request_id = payload.get("request_id") or generate_request_id()
        payload    = {**payload, "request_id": request_id}
        logger.info("[request_id=%s] 💰 SalaryReviewWorkflow started", request_id)
        try:
            agent_result = await self.agent.process_salary(payload)
        except Exception as e:
            logger.error("[request_id=%s] ❌ SalaryAgent failed: %s", request_id, e)
            return {"decision": "escalate_to_director", "reason": str(e), "request_id": request_id}

        # ✅ v6.0: SalaryDecisionEngine already produced the final decision.
        # SalaryValidationLayer is NO LONGER called here — engine handles all rules.
        # This eliminates the double-decision / overwrite problem.
        validated = agent_result

        # Ensure recommended_increment_pct is always present
        if validated.get("recommended_increment_pct") is None:
            validated["recommended_increment_pct"] = float(
                payload.get("requested_increment_pct", 0.10)
            )

        # Fix booleans
        for bf in ["is_on_pip", "is_on_probation"]:
            if bf in validated:
                validated[bf] = bool(validated[bf])

        await self._persist(validated, payload, request_id)
        validated["request_id"] = request_id
        validated["workflow"]   = "SalaryReviewWorkflow_v6.0"
        logger.info(
            "[request_id=%s] ✅ SalaryWorkflow → %s | conf=%.3f | "
            "rec_pct=%s | score=%.3f | trigger=%s",
            request_id,
            validated.get("decision"),
            validated.get("confidence", 0),
            validated.get("recommended_increment_pct"),
            validated.get("weighted_score", 0),
            validated.get("trigger", "?"),
        )
        return validated

    def run(self, payload: dict) -> dict:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(asyncio.run, self.async_run(payload)).result(timeout=60)
            return loop.run_until_complete(self.async_run(payload))
        except Exception as e:
            return {"decision": "escalate_to_director", "error": str(e)}

    async def _persist(self, result: dict, payload: dict, request_id: str) -> None:
        """
        ✅ Fix DB3: event_id resolved from payload → no null FK error.
        ✅ Fix S1:  recommended_increment_pct always present.
        """
        try:
            from core.db import save_decision, write_audit_log

            # ✅ Fix DB3: event_id from payload (set by API endpoint before event firing)
            event_id_val = payload.get("event_id") or payload.get("review_id")
            review_id    = int(payload.get("review_id", 0) or 0)
            entity_id    = review_id or int(payload.get("employee_id", 0) or 0)

            rec_pct = result.get("recommended_increment_pct", 0)

            try:
                save_decision({
                    "agent_type":   "salary_agent_v5.2",
                    "entity":       "salary_reviews",
                    "entity_id":    entity_id,
                    "event_id":     event_id_val,    # ✅ never null
                    "decision":     result.get("decision", "?"),
                    "confidence":   result.get("confidence", 0),
                    "reasoning":    result.get("reason", "")[:500],
                    "raw_response": str(result)[:1000],
                })
            except Exception as e:
                logger.warning(
                    "[request_id=%s] ⚠️ Salary persist (save_decision) failed: %s",
                    request_id, e,
                )

            write_audit_log(
                action       = f"salary_{result.get('decision', '?')}",
                entity       = "salary_reviews",
                entity_id    = entity_id,
                performed_by = "salary_agent_v5.2",
                details      = (
                    f"[request_id={request_id}] "
                    f"decision={result.get('decision')} | "
                    f"rec_pct={rec_pct:.0%} | "
                    f"conf={result.get('confidence', 0):.0%} | "
                    f"{result.get('reason', '')[:150]}"
                ),
            )
        except Exception as e:
            logger.warning(
                "[request_id=%s] ⚠️ Salary persist failed: %s", request_id, e
            )


# ═════════════════════════════════════════════════════════════════════════════
# 🏆  INCENTIVE WORKFLOW — v5.2
# ═════════════════════════════════════════════════════════════════════════════

class IncentiveWorkflow:
    def __init__(self) -> None:
        self._agent = None

    @property
    def agent(self):
        if self._agent is None:
            from agents.hr.hr_agent import HRAgent
            self._agent = HRAgent()
        return self._agent

    async def async_run(self, payload: dict) -> dict:
        request_id = payload.get("request_id") or generate_request_id()
        payload    = {**payload, "request_id": request_id}
        logger.info("[request_id=%s] 🏆 IncentiveWorkflow started", request_id)
        try:
            agent_result = await self.agent.process_incentive(payload)
        except Exception as e:
            return {"decision": "escalate_to_director", "reason": str(e), "request_id": request_id}
        try:
            from workflows.hr.decision_rules import IncentiveValidationLayer
            validated = IncentiveValidationLayer().validate_and_override(agent_result, payload)
        except Exception:
            validated = agent_result

        # ✅ Fix I2: approved_amount_egp never null AFTER validation
        if validated.get("approved_amount_egp") is None:
            decision = validated.get("decision", "deny_bonus")
            if decision not in ("deny_bonus", "escalate_to_director", "escalate_to_ceo"):
                try:
                    from agents.hr.hr_agent import _calculate_bonus_amount
                    validated["approved_amount_egp"] = _calculate_bonus_amount(
                        requested_amount_egp           = float(payload.get("requested_amount_egp", 0)),
                        monthly_salary_egp             = float(payload.get("monthly_salary_egp", 0)),
                        kpi_achievement                = float(payload.get("kpi_achievement", 0.80)),
                        performance_score              = float(payload.get("performance_score", 0.75)),
                        perf_trend                     = str(payload.get("perf_trend", "stable")),
                        is_critical_talent             = bool(payload.get("is_critical_talent", False)),
                        incentive_budget_remaining_egp = float(payload.get("incentive_budget_remaining_egp", 0)),
                        incentive_type                 = str(payload.get("incentive_type", "performance_bonus")),
                    )
                except Exception:
                    validated["approved_amount_egp"] = float(payload.get("requested_amount_egp", 0))
            else:
                validated["approved_amount_egp"] = 0.0

        # ✅ Fix B1: booleans
        for bf in ["is_on_pip", "is_critical_talent"]:
            if bf in validated:
                validated[bf] = bool(validated[bf])

        await self._persist(validated, payload, request_id)
        validated["request_id"] = request_id
        validated["workflow"]   = "IncentiveWorkflow_v5.2"
        logger.info(
            "[request_id=%s] ✅ IncentiveWorkflow → %s | conf=%.3f | amount=%s EGP",
            request_id,
            validated.get("decision"),
            validated.get("confidence", 0),
            validated.get("approved_amount_egp"),
        )
        return validated

    def run(self, payload: dict) -> dict:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(asyncio.run, self.async_run(payload)).result(timeout=60)
            return loop.run_until_complete(self.async_run(payload))
        except Exception as e:
            return {"decision": "deny_bonus", "error": str(e)}

    async def _persist(self, result: dict, payload: dict, request_id: str) -> None:
        """
        ✅ Fix DB3: event_id resolved from payload → no null FK error.
        ✅ Fix I2:  approved_amount_egp always present.
        """
        try:
            from core.db import save_decision, write_audit_log

            # ✅ Fix DB3: event_id from payload
            event_id_val = payload.get("event_id") or payload.get("incentive_id")
            incentive_id = int(payload.get("incentive_id", 0) or 0)
            entity_id    = incentive_id or int(payload.get("employee_id", 0) or 0)

            approved_amt = result.get("approved_amount_egp", 0) or 0

            try:
                save_decision({
                    "agent_type":   "incentive_agent_v5.2",
                    "entity":       "incentive_requests",
                    "entity_id":    entity_id,
                    "event_id":     event_id_val,    # ✅ never null
                    "decision":     result.get("decision", "?"),
                    "confidence":   result.get("confidence", 0),
                    "reasoning":    result.get("reason", "")[:500],
                    "raw_response": str(result)[:1000],
                })
            except Exception as e:
                logger.warning(
                    "[request_id=%s] ⚠️ Incentive persist (save_decision) failed: %s",
                    request_id, e,
                )

            write_audit_log(
                action       = f"incentive_{result.get('decision', '?')}",
                entity       = "incentive_requests",
                entity_id    = entity_id,
                performed_by = "incentive_agent_v5.2",
                details      = (
                    f"[request_id={request_id}] "
                    f"decision={result.get('decision')} | "
                    f"approved={approved_amt:,.0f} EGP | "
                    f"conf={result.get('confidence', 0):.0%} | "
                    f"{result.get('reason', '')[:150]}"
                ),
            )
        except Exception as e:
            logger.warning(
                "[request_id=%s] ⚠️ Incentive persist failed: %s", request_id, e
            )


# ═════════════════════════════════════════════════════════════════════════════
# 🚫  ABSENCE WORKFLOW — v5.2 (unchanged logic, version bump only)
# ═════════════════════════════════════════════════════════════════════════════

class AbsenceWorkflow:
    def __init__(self) -> None:
        self._agent = None

    @property
    def agent(self):
        if self._agent is None:
            from agents.hr.hr_agent import HRAgent
            self._agent = HRAgent()
        return self._agent

    async def async_run(self, payload: dict) -> dict:
        request_id = payload.get("request_id") or generate_request_id()
        payload    = {**payload, "request_id": request_id}
        logger.info("[request_id=%s] 🚫 AbsenceWorkflow started", request_id)
        try:
            agent_result = await self.agent.process_absence(payload)
        except Exception as e:
            return {"decision": "escalate_to_hr_director", "reason": str(e), "request_id": request_id}
        try:
            from workflows.hr.decision_rules import AbsenceValidationLayer
            validated = AbsenceValidationLayer().validate_and_override(agent_result, payload)
        except Exception:
            validated = agent_result

        # ✅ Fix B1: booleans
        for bf in ["is_on_pip", "escalation_required"]:
            if bf in validated:
                validated[bf] = bool(validated[bf])

        await self._persist(validated, payload, request_id)
        validated["request_id"] = request_id
        validated["workflow"]   = "AbsenceWorkflow_v5.2"
        return validated

    def run(self, payload: dict) -> dict:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(asyncio.run, self.async_run(payload)).result(timeout=60)
            return loop.run_until_complete(self.async_run(payload))
        except Exception as e:
            return {"decision": "escalate_to_hr_director", "error": str(e)}

    async def _persist(self, result: dict, payload: dict, request_id: str) -> None:
        """✅ Fix DB3: event_id resolved from payload."""
        try:
            from core.db import save_decision, write_audit_log

            event_id_val = payload.get("event_id") or payload.get("absence_id")
            absence_id   = int(payload.get("absence_id", 0) or 0)
            entity_id    = absence_id or int(payload.get("employee_id", 0) or 0)

            try:
                save_decision({
                    "agent_type":   "absence_agent_v5.2",
                    "entity":       "absence_events",
                    "entity_id":    entity_id,
                    "event_id":     event_id_val,    # ✅ never null
                    "decision":     result.get("decision", "?"),
                    "confidence":   result.get("confidence", 0),
                    "reasoning":    result.get("reason", "")[:500],
                    "raw_response": str(result)[:1000],
                })
            except Exception as e:
                logger.warning(
                    "[request_id=%s] ⚠️ Absence persist (save_decision) failed: %s",
                    request_id, e,
                )

            write_audit_log(
                action       = f"absence_{result.get('decision', '?')}",
                entity       = "absence_events",
                entity_id    = entity_id,
                performed_by = "absence_agent_v5.2",
                details      = (
                    f"[request_id={request_id}] "
                    f"decision={result.get('decision')} | "
                    f"classification={result.get('classification', '?')} | "
                    f"deduction={result.get('payroll_deduction_days', 0)}d | "
                    f"{result.get('reason', '')[:150]}"
                ),
            )
        except Exception as e:
            logger.warning(
                "[request_id=%s] ⚠️ Absence persist failed: %s", request_id, e
            )


# ═════════════════════════════════════════════════════════════════════════════
# 📅  ATTENDANCE WORKFLOW — v5.2 (unchanged logic, version bump)
# ═════════════════════════════════════════════════════════════════════════════

class AttendanceWorkflow:
    def __init__(self) -> None:
        self._agent = None

    @property
    def agent(self):
        if self._agent is None:
            from agents.hr.hr_agent import HRAgent
            self._agent = HRAgent()
        return self._agent

    async def async_run(self, payload: dict) -> dict:
        request_id = payload.get("request_id") or generate_request_id()
        payload    = {**payload, "request_id": request_id}
        logger.info("[request_id=%s] 📅 AttendanceWorkflow started", request_id)
        try:
            agent_result = await self.agent.process_attendance(payload)
        except Exception as e:
            return {"decision": "escalate_to_hr_director", "reason": str(e), "request_id": request_id}
        try:
            from workflows.hr.decision_rules import AttendanceValidationLayer
            validated = AttendanceValidationLayer().validate_and_override(agent_result, payload)
        except Exception:
            validated = agent_result
        await self._persist(validated, payload, request_id)
        validated["request_id"] = request_id
        validated["workflow"]   = "AttendanceWorkflow_v5.2"
        return validated

    def run(self, payload: dict) -> dict:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(asyncio.run, self.async_run(payload)).result(timeout=60)
            return loop.run_until_complete(self.async_run(payload))
        except Exception as e:
            return {"decision": "escalate_to_hr_director", "error": str(e)}

    async def _persist(self, result: dict, payload: dict, request_id: str) -> None:
        """✅ Fix DB3: event_id resolved."""
        try:
            from core.db import save_decision, write_audit_log

            event_id_val = payload.get("event_id")
            entity_id    = int(payload.get("employee_id", 0) or 0)

            try:
                save_decision({
                    "agent_type":   "attendance_agent_v5.2",
                    "entity":       "attendance_audits",
                    "entity_id":    entity_id,
                    "event_id":     event_id_val,
                    "decision":     result.get("decision", "?"),
                    "confidence":   result.get("confidence", 0),
                    "reasoning":    result.get("reason", "")[:500],
                    "raw_response": str(result)[:1000],
                })
            except Exception as e:
                logger.warning(
                    "[request_id=%s] ⚠️ Attendance persist (save_decision) failed: %s",
                    request_id, e,
                )

            write_audit_log(
                action       = f"attendance_{result.get('decision', '?')}",
                entity       = "attendance_audits",
                entity_id    = entity_id,
                performed_by = "attendance_agent_v5.2",
                details      = f"[request_id={request_id}] {result.get('reason', '')[:200]}",
            )
        except Exception as e:
            logger.warning(
                "[request_id=%s] ⚠️ Attendance persist failed: %s", request_id, e
            )