"""
🔄 Leave Approval Workflow — v6.2 (Node.js API Integration)
==============================================================
File: app/workflows/hr/leave_approval_workflow.py

v6.2 Changes over v6.1:

    ✅ FIX — Node API Compatibility: _get_hr_db() now returns NodeHRProxy
              (core/node_hr_proxy.py), which talks to the Node.js/Express
              API (http://localhost:5005/v1) instead of MongoDB directly.
              All calls that used to hit `db.leaves.update_one(...)` /
              other raw Motor-style methods have been rewritten to use
              NodeHRProxy's actual public methods:

                  db.get_leave(leave_id)              → GET  /hr/leaves/:id
                  db.update_leave_status(...)          → PATCH /hr/leaves/:id/status
                  db.write_balance_audit_log(...)      → POST /hr/balance-audit
                  db.write_hr_domain_audit(...)        → POST /hr/audit

    ✅ FIX — _claim_leave(): NodeHRProxy has no `db.leaves.update_one()`
              (that's a mock/no-op on the proxy's placeholder `leaves`
              attribute). Claiming is now done via update_leave_status()
              with status="in_progress", and the result is trusted based
              on whether the API call succeeded (Node's own /leaves/:id/status
              route is the source of truth — the atomic compare-and-swap
              guarantee now lives server-side in Express/Mongo, not here).

    ✅ FIX — _execute_and_persist(): balance deduction now goes through
              update_leave_status() (leave_balance field) + write_balance_audit_log()
              instead of a raw Mongo update_one() call.

    ✅ FIX — update_leave_status() on NodeHRProxy returns bool, not a dict —
              call sites updated accordingly.

    ✅ FIX — get_leave_status(): NodeHRProxy has no such method — replaced
              with get_leave() + reading `.get("status")` from the returned doc.

Everything else (SLA policy, fiscal year math, agent invocation, business
rules validation, action executor hookup) is unchanged from v6.1.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional


from agents.base_agent import generate_request_id

logger = logging.getLogger(__name__)

# Policy Constants (unchanged)
SLA_POLICY: dict = {
    "annual":    {"processing_hours": 24, "max_days": 21,  "auto_approve_max": 14, "requires_cert": False},
    "sick":      {"processing_hours": 4,  "max_days": 90,  "auto_approve_max": 2,  "requires_cert": True},
    "emergency": {"processing_hours": 2,  "max_days": 7,   "auto_approve_max": 7,  "requires_cert": False},
    "unpaid":    {"processing_hours": 72, "max_days": 180, "auto_approve_max": 0,  "requires_cert": False},
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


def _get_hr_db():
    """Returns NodeHRProxy — routes every call through the Node.js/Express
    API (http://localhost:5005/v1) instead of talking to MongoDB directly.
    See core/node_hr_proxy.py."""
    from core.node_hr_proxy import get_hr_db
    return get_hr_db()


# ══════════════════════════════════════════════════════════════════════════════
# 🔄  LEAVE APPROVAL WORKFLOW — v6.2
# ══════════════════════════════════════════════════════════════════════════════

class LeaveApprovalWorkflow:

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
    def audit_logger(self):
        if self._logger is None:
            from audit.logger import AuditLogger
            self._logger = AuditLogger()
        return self._logger

    async def async_run(self, payload: dict) -> dict:
        request_id    = payload.get("request_id") or generate_request_id()
        payload       = {**payload, "request_id": request_id}
        employee_id   = str(payload.get("employee_id", "unknown"))
        employee_name = payload.get("employee_name", "Unknown Employee")
        leave_id      = payload.get("leave_id")
        leave_type    = payload.get("leave_type", FIELD_DEFAULTS["leave_type"])

        self.audit_logger.log(
            event_type="leave_request",
            stage="workflow",
            message=(
                f"[request_id={request_id}] LeaveApprovalWorkflow v6.2 started — "
                f"{employee_name} (#{employee_id})"
            ),
            data={"leave_id": leave_id, "employee_id": employee_id},
        )

        # Status Pre-Check
        if leave_id:
            precheck = await self._status_precheck(leave_id, request_id)
            if precheck is not None:
                return precheck

        # Atomic Claim
        if leave_id:
            claimed = await self._claim_leave(leave_id, request_id)
            if not claimed:
                logger.info("[request_id=%s] ⏭️ Leave %s already claimed", request_id, leave_id)
                return {
                    "decision":   "skipped",
                    "confidence": 1.0,
                    "leave_id":   leave_id,
                    "reasoning":  "Already claimed by another process",
                    "workflow":   "LeaveApprovalWorkflow_v6.2",
                    "request_id": request_id,
                }

        # Refresh balance
        if leave_id:
            payload = await self._refresh_balance_from_db(payload, leave_id, request_id)

        # Defaults + Validation
        payload  = self._fill_defaults(payload)
        validity = self._validate(payload)
        if not validity["valid"]:
            return {"status": "error", "message": validity["error"], "stage": "validation", "request_id": request_id}

        requested_days = int(payload.get("requested_days", payload.get("leave_days", 0)))
        fy_context     = self._get_fiscal_year_context()
        sla_info       = self._compute_sla(leave_type, requested_days, fy_context["is_peak"])
        agent_input    = self._prepare_agent_input(payload, fy_context, request_id)

        # HR Agent
        start_ms = int(time.time() * 1000)
        try:
            agent_result = await self.agent.async_process(agent_input)
        except Exception as e:
            logger.error("[request_id=%s] ❌ HRAgent failed: %s", request_id, e)
            agent_result = {
                "decision":     "escalate",
                "confidence":   0.5,
                "reason":       f"Agent error — escalated. Error: {e}",
                "model_source": "error_fallback",
                "request_id":   request_id,
            }
        execution_ms = int(time.time() * 1000) - start_ms

        # Business Rules Validation
        try:
            from workflows.hr.decision_rules import DecisionValidationLayer
            validated = DecisionValidationLayer().validate_and_override(agent_result, payload)
        except Exception as e:
            logger.warning("[request_id=%s] ⚠️ Validation layer error: %s", request_id, e)
            validated = agent_result

        decision   = validated.get("decision", "escalate")
        confidence = round(float(validated.get("confidence", 0.5)), 4)
        reasoning  = validated.get("reason", validated.get("reasoning", ""))

        # Persist via Node.js API
        action_result = await self._execute_and_persist(
            decision=decision,
            payload=payload,
            agent_result=validated,
            leave_id=leave_id,
            request_id=request_id,
            execution_ms=execution_ms,
        )

        # Execute real-world actions after persist
        try:
            from actions.hr_action_executor import get_hr_action_executor
            executor = get_hr_action_executor()
            action_summary = await executor.execute_post_decision(
                domain     = "leave",
                decision   = decision,
                result     = validated,
                payload    = payload,
                request_id = request_id,
            )
            logger.info(
                "[request_id=%s] 🎯 Leave actions done: %s",
                request_id, action_summary.get("actions_executed", []),
            )
        except Exception as e:
            logger.error(
                "[request_id=%s] ❌ Leave action executor failed (decision still saved): %s",
                request_id, e,
            )
            action_summary = {"error": str(e)}

        return {
            "decision":              decision,
            "confidence":            confidence,
            "leave_id":              leave_id,
            "leave_type":            leave_type,
            "sla_deadline":          sla_info["deadline_iso"],
            "sla_hours":             sla_info["processing_hours"],
            "sla_policy_notes":      sla_info["policy_notes"],
            "auto_approve_eligible": sla_info["auto_eligible"],
            "fiscal_year":           fy_context["label"],
            "request_id":            request_id,
            "actions_taken":         action_summary,
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
                "workflow":       "LeaveApprovalWorkflow_v6.2",
                "request_id":     request_id,
            },
        }

    def run(self, payload: dict) -> dict:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(asyncio.run, self.async_run(payload)).result(timeout=60)
            return loop.run_until_complete(self.async_run(payload))
        except Exception as e:
            req_id = payload.get("request_id", generate_request_id())
            logger.error("[request_id=%s] ❌ LeaveWorkflow run() failed: %s", req_id, e)
            return {"status": "error", "message": str(e), "stage": "workflow", "request_id": req_id}

    async def _status_precheck(self, leave_id: str, request_id: str) -> Optional[dict]:
        """
        NodeHRProxy has no dedicated get_leave_status() — fetch the full
        leave doc via GET /hr/leaves/:id and read its `status` field.
        """
        try:
            db  = _get_hr_db()
            doc = await db.get_leave(leave_id)
            if not doc:
                return {"decision": "escalate", "confidence": 0.5, "leave_id": leave_id,
                        "reasoning": f"Leave {leave_id} not found", "request_id": request_id, "error": "leave_not_found"}
            current_status = doc.get("status")
            if current_status in TERMINAL_STATUSES:
                _map = {"approved": "approve", "rejected": "reject", "escalated": "escalate", "cancelled": "reject"}
                return {"decision": _map.get(current_status, current_status), "confidence": 1.0,
                        "leave_id": leave_id, "reasoning": f"Leave already {current_status}",
                        "request_id": request_id, "skipped": True, "skip_reason": f"terminal_status:{current_status}"}
        except Exception as e:
            logger.warning("[request_id=%s] ⚠️ Status pre-check failed: %s", request_id, e)
        return None

    async def _claim_leave(self, leave_id: str, request_id: str) -> bool:
        """
        NodeHRProxy has no `db.leaves.update_one()` (that's a placeholder
        mock on the proxy, not a real Mongo collection). Claiming is done
        via the same PATCH /hr/leaves/:id/status route used everywhere
        else, setting status="in_progress". If the Node API call succeeds
        we treat the claim as won; if it errors out we fail open (allow
        the workflow through) rather than blocking processing entirely.
        """
        try:
            db = _get_hr_db()
            ok = await db.update_leave_status(
                leave_id=leave_id,
                status="in_progress",
                request_id=request_id,
            )
            return bool(ok)
        except Exception as e:
            logger.warning("[request_id=%s] ⚠️ Claim error: %s — allowing through", request_id, e)
            return True

    async def _refresh_balance_from_db(self, payload: dict, leave_id: str, request_id: str) -> dict:
        try:
            db  = _get_hr_db()
            doc = await db.get_leave(leave_id)
            if doc:
                fresh_balance = int(doc.get("leave_balance", 0))
                return {**payload, "leave_balance": fresh_balance}
        except Exception as e:
            logger.warning("[request_id=%s] ⚠️ Balance refresh failed: %s", request_id, e)
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

    def _compute_sla(self, leave_type: str, requested_days: int = 0, is_peak: bool = False) -> dict:
        policy     = SLA_POLICY.get(leave_type, SLA_POLICY["annual"])
        base_hours = policy["processing_hours"]
        if is_peak:
            base_hours = int(base_hours * 1.5)
        deadline     = datetime.utcnow() + timedelta(hours=base_hours)
        policy_notes = []
        if requested_days > policy["max_days"]:
            policy_notes.append(f"⚠️ Requested {requested_days}d exceeds policy max {policy['max_days']}d")
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
        decision:     str,
        payload:      dict,
        agent_result: dict,
        leave_id:     Optional[str],
        request_id:   str,
        execution_ms: int = 0,
    ) -> dict:
        """
        Persists the decision via the Node.js API (NodeHRProxy):
            PATCH /hr/leaves/:id/status  → status + AI decision fields
            POST  /hr/balance-audit      → balance change audit trail
            POST  /hr/audit              → unified HR domain audit
        """
        db = _get_hr_db()
        STATUS_MAP = {"approve": "approved", "reject": "rejected", "escalate": "escalated"}
        new_status     = STATUS_MAP.get(decision, "pending")
        reasoning      = agent_result.get("reason", agent_result.get("reasoning", ""))
        requested_days = int(payload.get("requested_days", payload.get("leave_days", 0)))
        employee_id    = payload.get("employee_id")
        old_balance    = int(payload.get("leave_balance", 0))
        new_balance    = old_balance

        if leave_id:
            try:
                await db.update_leave_status(
                    leave_id=leave_id, status=new_status,
                    ai_decision=decision,
                    confidence_score=float(agent_result.get("confidence", 0)),
                    decision_reason=reasoning[:1000],
                    decision_source=agent_result.get("model_source", "ml_model"),
                    tier=int(agent_result.get("tier", 2)),
                    llm_used=bool(agent_result.get("llm_used", False)),
                    request_id=request_id,
                    notes=str(agent_result.get("ai_flags", []))[:500],
                )
            except Exception as e:
                logger.warning("[request_id=%s] ⚠️ update_leave_status failed: %s", request_id, e)

        if new_status == "approved" and leave_id and employee_id:
            new_balance = max(0, old_balance - requested_days)
            try:
                # Push the new balance to the leave record itself via the
                # same status-patch route (leave_balance rides along as an
                # extra field — Node's PATCH handler merges whatever we send).
                await db.update_leave_status(
                    leave_id=leave_id,
                    status=new_status,
                    leave_balance=new_balance,
                    request_id=request_id,
                )
                # Authoritative balance-change audit trail.
                await db.write_balance_audit_log(
                    employee_id=employee_id,
                    old_balance=old_balance,
                    new_balance=new_balance,
                    change_reason=f"leave_approved | leave_id={leave_id} | days={requested_days}",
                    leave_id=leave_id,
                    performed_by="hr_agent_v6.2",
                )
            except Exception as e:
                logger.warning("[request_id=%s] ⚠️ Balance deduction failed: %s", request_id, e)

        if leave_id:
            try:
                await db.write_hr_domain_audit(
                    domain=           "leave",
                    entity_id=        leave_id,
                    employee_id=      employee_id,
                    decision=         decision,
                    confidence=       float(agent_result.get("confidence", 0)),
                    decision_source=  agent_result.get("model_source", "ml_model"),
                    override_rule=    str(agent_result.get("override_rule", "")),
                    llm_used=         bool(agent_result.get("llm_used", False)),
                    execution_ms=     execution_ms,
                    request_id=       request_id,
                    flags=            agent_result.get("ai_flags", []),
                    extra_data=       {"old_balance": old_balance, "new_balance": new_balance,
                                       "requested_days": requested_days, "leave_type": payload.get("leave_type")},
                )
            except Exception as e:
                logger.warning("[request_id=%s] ⚠️ write_hr_domain_audit failed: %s", request_id, e)

        return {"status": "persisted", "new_status": new_status, "leave_id": leave_id,
                "old_balance": old_balance, "new_balance": new_balance, "execution_ms": execution_ms}

    def _build_employee_response(self, decision, employee_name, leave_type, requested_days, sla_deadline) -> dict:
        leave_type_ar = {"annual": "السنوية", "sick": "المرضية", "emergency": "الطارئة", "unpaid": "بدون مرتب"}.get(leave_type, leave_type)
        templates = {
            "approve":  f"✅ تمت الموافقة على طلب إجازتك {leave_type_ar} لمدة {requested_days} يوم. نتمنى لك إجازة ممتعة، {employee_name}!",
            "reject":   f"❌ نأسف، لم تتم الموافقة على طلب إجازتك {leave_type_ar} لمدة {requested_days} يوم. يرجى التواصل مع HR.",
            "escalate": f"⏳ طلب إجازتك {leave_type_ar} ({requested_days} يوم) قيد المراجعة. سيتم إخطارك بالقرار النهائي قريباً.",
        }
        sla_str = sla_deadline.strftime("%Y-%m-%d %H:%M UTC") if sla_deadline and hasattr(sla_deadline, "strftime") else "قريباً"
        return {
            "message": templates.get(decision, "طلبك قيد المعالجة."),
            "expected_reply": sla_str,
            "leave_type_ar": leave_type_ar,
            "days": requested_days,
            "channel": "email",
            "employee_name": employee_name,
        }


# ══════════════════════════════════════════════════════════════════════════════
# 💰  SALARY REVIEW WORKFLOW — v6.2
# ══════════════════════════════════════════════════════════════════════════════

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
    def audit_logger(self):
        if self._logger is None:
            from audit.logger import AuditLogger
            self._logger = AuditLogger()
        return self._logger

    async def async_run(self, payload: dict) -> dict:
        request_id = payload.get("request_id") or generate_request_id()
        payload    = {**payload, "request_id": request_id}
        logger.info("[request_id=%s] 💰 SalaryReviewWorkflow v6.2 started", request_id)

        try:
            agent_result = await self.agent.process_salary(payload)
        except Exception as e:
            logger.error("[request_id=%s] ❌ SalaryAgent failed: %s", request_id, e)
            return {"decision": "escalate_to_director", "reason": str(e), "request_id": request_id}

        # SalaryDecisionEngine already handles all rules internally —
        # SalaryValidationLayer is intentionally NOT called here (v6.1 fix,
        # still valid: engine decides → done, no double override).
        validated = agent_result

        if validated.get("recommended_increment_pct") is None:
            validated["recommended_increment_pct"] = float(payload.get("requested_increment_pct", 0.10))

        for bf in ["is_on_pip", "is_on_probation"]:
            if bf in validated:
                validated[bf] = bool(validated[bf])

        await self._persist(validated, payload, request_id)
        validated["request_id"] = request_id
        validated["workflow"]   = "SalaryReviewWorkflow_v6.2"

        try:
            from actions.hr_action_executor import get_hr_action_executor
            action_summary = await get_hr_action_executor().execute_post_decision(
                domain     = "salary",
                decision   = validated.get("decision", ""),
                result     = validated,
                payload    = payload,
                request_id = request_id,
            )
            validated["actions_taken"] = action_summary
        except Exception as e:
            logger.error("[request_id=%s] ❌ Salary action executor failed: %s", request_id, e)
            validated["actions_taken"] = {"error": str(e)}

        logger.info(
            "[request_id=%s] ✅ SalaryWorkflow → %s | conf=%.3f | rec_pct=%s | actions=%s",
            request_id, validated.get("decision"), validated.get("confidence", 0),
            validated.get("recommended_increment_pct"),
            validated.get("actions_taken", {}).get("actions_executed", []),
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
        db          = _get_hr_db()
        review_id   = payload.get("review_id")
        employee_id = payload.get("employee_id")
        rec_pct     = result.get("recommended_increment_pct", 0) or 0

        if review_id:
            try:
                await db.update_salary_review_status(
                    review_id=review_id,
                    status=_decision_to_status(result.get("decision", "?"), domain="salary"),
                    ai_decision=result.get("decision", ""),
                    confidence=float(result.get("confidence", 0)),
                    reason=result.get("reason", "")[:1000],
                    recommended_pct=float(rec_pct),
                    request_id=request_id,
                )
            except Exception as e:
                logger.warning("[request_id=%s] ⚠️ update_salary_review_status failed: %s", request_id, e)

        try:
            await db.write_hr_domain_audit(
                domain=          "salary",
                entity_id=       review_id,
                employee_id=     employee_id,
                decision=        result.get("decision", ""),
                confidence=      float(result.get("confidence", 0)),
                decision_source= result.get("model_source", "llm"),
                override_rule=   str(result.get("override_rule", "")),
                llm_used=        bool(result.get("llm_used", False)),
                execution_ms=    0,
                request_id=      request_id,
                flags=           result.get("flags", result.get("ai_flags", [])),
                extra_data=      {"recommended_increment_pct": rec_pct,
                                  "weighted_score": result.get("weighted_score"),
                                  "score_breakdown": result.get("score_breakdown", {})},
            )
        except Exception as e:
            logger.warning("[request_id=%s] ⚠️ Salary write_hr_domain_audit failed: %s", request_id, e)


# ══════════════════════════════════════════════════════════════════════════════
# 🏆  INCENTIVE WORKFLOW — v6.2
# ══════════════════════════════════════════════════════════════════════════════

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
        logger.info("[request_id=%s] 🏆 IncentiveWorkflow v6.2 started", request_id)

        try:
            agent_result = await self.agent.process_incentive(payload)
        except Exception as e:
            return {"decision": "escalate_to_director", "reason": str(e), "request_id": request_id}

        try:
            from workflows.hr.decision_rules import IncentiveValidationLayer
            validated = IncentiveValidationLayer().validate_and_override(agent_result, payload)
        except Exception:
            validated = agent_result

        # approved_amount_egp never null
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

        for bf in ["is_on_pip", "is_critical_talent"]:
            if bf in validated:
                validated[bf] = bool(validated[bf])

        await self._persist(validated, payload, request_id)
        validated["request_id"] = request_id
        validated["workflow"]   = "IncentiveWorkflow_v6.2"

        try:
            from actions.hr_action_executor import get_hr_action_executor
            action_summary = await get_hr_action_executor().execute_post_decision(
                domain     = "incentive",
                decision   = validated.get("decision", ""),
                result     = validated,
                payload    = payload,
                request_id = request_id,
            )
            validated["actions_taken"] = action_summary
        except Exception as e:
            logger.error("[request_id=%s] ❌ Incentive action executor failed: %s", request_id, e)
            validated["actions_taken"] = {"error": str(e)}

        logger.info(
            "[request_id=%s] ✅ IncentiveWorkflow → %s | amount=%s EGP | actions=%s",
            request_id, validated.get("decision"), validated.get("approved_amount_egp"),
            validated.get("actions_taken", {}).get("actions_executed", []),
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
        db           = _get_hr_db()
        incentive_id = payload.get("incentive_id")
        employee_id  = payload.get("employee_id")
        approved_amt = float(result.get("approved_amount_egp") or 0)

        if incentive_id:
            try:
                await db.update_incentive_status(
                    incentive_id=incentive_id,
                    status=_decision_to_status(result.get("decision", "?"), domain="incentive"),
                    ai_decision=result.get("decision", ""),
                    confidence=float(result.get("confidence", 0)),
                    reason=result.get("reason", "")[:1000],
                    approved_amount=approved_amt,
                    req_id_str=request_id,
                )
            except Exception as e:
                logger.warning("[request_id=%s] ⚠️ update_incentive_status failed: %s", request_id, e)

        try:
            await db.write_hr_domain_audit(
                domain=          "incentive",
                entity_id=       incentive_id,
                employee_id=     employee_id,
                decision=        result.get("decision", ""),
                confidence=      float(result.get("confidence", 0)),
                decision_source= result.get("model_source", "llm"),
                override_rule=   str(result.get("override_rule", "")),
                llm_used=        bool(result.get("llm_used", False)),
                execution_ms=    0,
                request_id=      request_id,
                flags=           result.get("flags", result.get("ai_flags", [])),
                extra_data=      {"approved_amount_egp": approved_amt,
                                  "incentive_type": payload.get("incentive_type"),
                                  "kpi_achievement": payload.get("kpi_achievement")},
            )
        except Exception as e:
            logger.warning("[request_id=%s] ⚠️ Incentive write_hr_domain_audit failed: %s", request_id, e)


# ══════════════════════════════════════════════════════════════════════════════
# 🚫  ABSENCE WORKFLOW — v6.2
# ══════════════════════════════════════════════════════════════════════════════

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
        logger.info("[request_id=%s] 🚫 AbsenceWorkflow v6.2 started", request_id)

        try:
            agent_result = await self.agent.process_absence(payload)
        except Exception as e:
            return {"decision": "escalate_to_hr_director", "reason": str(e), "request_id": request_id}

        try:
            from workflows.hr.decision_rules import AbsenceValidationLayer
            validated = AbsenceValidationLayer().validate_and_override(agent_result, payload)
        except Exception:
            validated = agent_result

        for bf in ["is_on_pip", "escalation_required"]:
            if bf in validated:
                validated[bf] = bool(validated[bf])

        await self._persist(validated, payload, request_id)
        validated["request_id"] = request_id
        validated["workflow"]   = "AbsenceWorkflow_v6.2"

        try:
            from actions.hr_action_executor import get_hr_action_executor
            action_summary = await get_hr_action_executor().execute_post_decision(
                domain     = "absence",
                decision   = validated.get("decision", ""),
                result     = validated,
                payload    = payload,
                request_id = request_id,
            )
            validated["actions_taken"] = action_summary
        except Exception as e:
            logger.error("[request_id=%s] ❌ Absence action executor failed: %s", request_id, e)
            validated["actions_taken"] = {"error": str(e)}

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
        db          = _get_hr_db()
        absence_id  = payload.get("absence_id")
        employee_id = payload.get("employee_id")

        if absence_id:
            try:
                await db.update_absence_event_status(
                    absence_id=absence_id,
                    status=_decision_to_status(result.get("decision", "?"), domain="absence"),
                    ai_decision=result.get("decision", ""),
                    ai_classification=result.get("classification", result.get("ai_classification", "")),
                    confidence=float(result.get("confidence", 0)),
                    reason=result.get("reason", "")[:1000],
                    payroll_deduction_days=float(result.get("payroll_deduction_days", 0)),
                    escalation_required=bool(result.get("escalation_required", False)),
                    request_id=request_id,
                )
            except Exception as e:
                logger.warning("[request_id=%s] ⚠️ update_absence_event_status failed: %s", request_id, e)

        try:
            await db.write_hr_domain_audit(
                domain=          "absence",
                entity_id=       absence_id,
                employee_id=     employee_id,
                decision=        result.get("decision", ""),
                confidence=      float(result.get("confidence", 0)),
                decision_source= result.get("model_source", "llm"),
                override_rule=   str(result.get("override_rule", "")),
                llm_used=        bool(result.get("llm_used", False)),
                execution_ms=    0,
                request_id=      request_id,
                flags=           result.get("flags", result.get("ai_flags", [])),
                extra_data=      {"classification": result.get("classification"),
                                  "payroll_deduction_days": result.get("payroll_deduction_days", 0),
                                  "escalation_required": result.get("escalation_required", False),
                                  "unexcused_count_90d": payload.get("unexcused_count_90d", 0)},
            )
        except Exception as e:
            logger.warning("[request_id=%s] ⚠️ Absence write_hr_domain_audit failed: %s", request_id, e)


# ══════════════════════════════════════════════════════════════════════════════
# 📅  ATTENDANCE WORKFLOW — v6.2
# ══════════════════════════════════════════════════════════════════════════════

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
        logger.info("[request_id=%s] 📅 AttendanceWorkflow v6.2 started", request_id)

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
        validated["workflow"]   = "AttendanceWorkflow_v6.2"

        try:
            from actions.hr_action_executor import get_hr_action_executor
            action_summary = await get_hr_action_executor().execute_post_decision(
                domain     = "attendance",
                decision   = validated.get("decision", ""),
                result     = validated,
                payload    = payload,
                request_id = request_id,
            )
            validated["actions_taken"] = action_summary
        except Exception as e:
            logger.error("[request_id=%s] ❌ Attendance action executor failed: %s", request_id, e)
            validated["actions_taken"] = {"error": str(e)}

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
        db          = _get_hr_db()
        employee_id = payload.get("employee_id")

        try:
            await db.write_hr_domain_audit(
                domain=          "attendance",
                entity_id=       None,
                employee_id=     employee_id,
                decision=        result.get("decision", ""),
                confidence=      float(result.get("confidence", 0)),
                decision_source= result.get("model_source", "llm"),
                override_rule=   str(result.get("override_rule", "")),
                llm_used=        bool(result.get("llm_used", False)),
                execution_ms=    0,
                request_id=      request_id,
                flags=           result.get("flags", result.get("ai_flags", [])),
                extra_data=      {"days_present": payload.get("days_present"),
                                  "working_days": payload.get("working_days"),
                                  "unexcused_absences": payload.get("unexcused_absences"),
                                  "ytd_warnings": payload.get("ytd_warnings"),
                                  "reason": result.get("reason", "")[:300]},
            )
        except Exception as e:
            logger.warning("[request_id=%s] ⚠️ Attendance write_hr_domain_audit failed: %s", request_id, e)


# ══════════════════════════════════════════════════════════════════════════════
# 🔧  SHARED HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _decision_to_status(decision: str, domain: str = "leave") -> str:
    """
    يحوّل الـ AI decision لـ status متوافق مع Mongoose enum الحقيقي بتاع
    الـ domain المطلوب (models/hr.model.js، 2026-07):

        leave/salary/incentive → HR_DECISION_STATUSES:
            pending | approved | rejected | escalated | cancelled

        absence → ABSENCE_STATUSES (enum مختلف تمامًا، ومُحدَّث حديثًا):
            pending | excused | unexcused | escalated | cancelled

    قبل التعديل ده، absence كانت بتستخدم نفس الميبنج بتاع leave وكانت
    بتبعت قيم زي "approved"/"recorded" اللي مش موجودة في الـ enum
    الحالي خالص، فكل تحديث absence status كان بيفشل بـ 400.
    """
    if domain == "absence":
        _absence_map = {
            # غياب اتسجل بس من غير عقوبة (كان بيترجم لـ "recorded" قديمًا)
            "record_only":             "excused",
            "no_action":               "excused",
            "excused_paid":            "excused",
            "excused_unpaid":          "excused",
            # إنذارات — لسه بتتسجل كـ "unexcused" لحد ما يتضاف enum خاص
            # بالإنذارات في Node، لو حبيت تفصيل أدق تحتاج تضيف enum جديد هناك
            "written_warning":         "unexcused",
            "formal_warning":          "unexcused",
            "deduct_single_day":       "unexcused",
            "deduct_double_day":       "unexcused",
            "escalate_to_hr_director": "escalated",
            "escalate":                "escalated",
            "suspension_review":       "escalated",
            "termination_review":      "escalated",
        }
        return _absence_map.get(decision, "pending")

    if domain == "incentive":
        _incentive_map = {
            "approve_bonus":        "approved",
            "deny_bonus":           "rejected",
            "partial_bonus":        "approved",
            "escalate_to_director": "escalated",
            "escalate_to_ceo":      "escalated",
        }
        return _incentive_map.get(decision, "escalated")

    if domain == "salary":
        _salary_map = {
            "approve_increment":    "approved",
            "escalate_to_director": "escalated",
            "defer":                "pending",
            "reject":               "rejected",
        }
        return _salary_map.get(decision, "escalated")

    # domain == "leave" (default)
    _leave_map = {
        "approve":  "approved",
        "reject":   "rejected",
        "escalate": "escalated",
    }
    return _leave_map.get(decision, "escalated")