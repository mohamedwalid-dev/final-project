"""
🔍 HR Debug Endpoints — v3.2
==============================
File: app/routers/hr_debug.py

أضف دي في main.py:
    from routers.hr_debug import debug_router
    app.include_router(debug_router, prefix="", tags=["🔍 Debug"])

أو الصق الـ endpoints مباشرة في main.py.

Endpoints:
    POST /leaves/debug         ← simulate + full debug panel (بدون حفظ في DB)
    GET  /leaves/{id}/debug    ← debug panel لإجازة موجودة
    POST /model/analyze        ← تحليل input بدون تسجيل في DB
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, validator

debug_router = APIRouter()


class LeaveDebugRequest(BaseModel):
    """نفس الـ LeaveApprovalRequest + debug mode."""
    employee_id:         str           = Field(..., description="ID الموظف")
    employee_name:       str           = Field("Debug User")
    requested_days:      int           = Field(..., gt=0)
    leave_balance:       int           = Field(0, ge=0)
    leave_type:          str           = Field("annual")
    reason:              str           = Field("")
    performance_score:   Optional[float] = Field(None, ge=0.0, le=1.0)
    attendance_rate:     Optional[float] = Field(None, ge=0.0, le=1.0)
    absence_count:       Optional[int]   = Field(None, ge=0)
    team_workload:       str             = Field("medium")
    job_level:           Optional[str]   = Field(None)
    years_of_experience: Optional[int]   = Field(None, ge=0)
    salary_grade:        Optional[str]   = Field(None)
    overtime_hours:      Optional[int]   = Field(None, ge=0)
    department:          Optional[str]   = Field(None)

    @validator("employee_id", pre=True)
    def coerce_id(cls, v):
        return str(v)


@debug_router.post("/leaves/debug", tags=["🔍 Debug"])
async def debug_leave_decision(body: LeaveDebugRequest):
    """
    🔍 Debug Mode — يشغّل كل الـ pipeline بدون حفظ في DB.

    بيرجع:
      - القرار النهائي
      - conflict_analysis (ML vs Rules)
      - feature_importance
      - data_trace (raw input vs model features)
      - confidence_breakdown
      - كل الـ layers بالتفصيل
    """
    from agents.hr.hr_agent import HRAgent
    from workflows.hr.decision_rules import DecisionValidationLayer

    payload = body.dict()

    # Run ML + LLM (Tier logic)
    agent   = HRAgent()
    result  = await agent.async_process(payload)

    # Run Validation Layer
    validated = DecisionValidationLayer().validate_and_override(result, payload)

    # Build full debug panel
    debug_data = HRAgent.get_decision_debug(validated, payload)

    return {
        "mode":            "debug_only — no DB changes",
        "timestamp":       datetime.utcnow().isoformat() + "Z",
        "final_decision":  validated.get("decision"),
        "confidence":      validated.get("confidence"),
        "tier":            validated.get("tier"),
        "override_applied": "override_rule" in validated,
        "override_rule":   validated.get("override_rule"),
        "debug_panel":     debug_data,
        "employee_response": _build_quick_response(validated, body),
    }


@debug_router.get("/leaves/{leave_id}/debug", tags=["🔍 Debug"])
async def debug_existing_leave(leave_id: int):
    """
    🔍 Debug panel لإجازة موجودة في DB.
    بيعيد تشغيل الـ pipeline على نفس البيانات.
    """
    from core.db import get_leave
    from agents.hr.hr_agent import HRAgent
    from workflows.hr.decision_rules import DecisionValidationLayer

    leave = get_leave(leave_id)
    if not leave:
        raise HTTPException(status_code=404, detail=f"Leave #{leave_id} not found")

    payload = {
        **leave,
        "leave_id":       leave_id,
        "requested_days": leave.get("leave_days", leave.get("requested_days", 1)),
    }

    agent     = HRAgent()
    result    = await agent.async_process(payload)
    validated = DecisionValidationLayer().validate_and_override(result, payload)
    debug_data = HRAgent.get_decision_debug(validated, payload)

    return {
        "leave_id":        leave_id,
        "stored_status":   leave.get("status"),
        "rerun_decision":  validated.get("decision"),
        "timestamp":       datetime.utcnow().isoformat() + "Z",
        "note":            "Re-run only — no DB changes made",
        "debug_panel":     debug_data,
    }


@debug_router.post("/model/analyze", tags=["🔍 Debug"])
async def analyze_request(body: LeaveDebugRequest):
    """
    🧪 ML-only analysis — يشغّل الـ ML model بس (بدون LLM، بدون DB).

    مفيد لـ:
      - اختبار feature engineering
      - تتبع الـ balance bug
      - فهم ليه confidence معينة
    """
    from agents.hr.leave_model_handler import get_model_handler
    from agents.hr.conflict_resolver import get_conflict_resolver
    from config.hr_thresholds import get_thresholds_from_metadata

    payload = body.dict()
    handler = get_model_handler()
    result  = handler.predict(payload)

    thresholds = get_thresholds_from_metadata(handler._metadata)
    resolver   = get_conflict_resolver()

    conflict_analysis = resolver.resolve(
        ml_result=result,
        final_decision=result["decision"],
        payload=payload,
        thresholds=thresholds,
        tier=result.get("tier", 2),
    )

    return {
        "ml_only":              True,
        "decision":             result["decision"],
        "confidence":           result["confidence"],
        "tier":                 result["tier"],
        "source":               result["source"],
        "is_outlier":           result["is_outlier"],
        "breakdown":            result["breakdown"],
        "key_factors":          result["key_factors"],
        "input_warnings":       result["input_warnings"],
        "conflict_analysis":    conflict_analysis,
        "thresholds":           thresholds,
        "raw_input_balance":    payload.get("leave_balance"),
        "model_balance":        result["breakdown"].get("leave_balance"),
        "balance_match":        (
            payload.get("leave_balance") == result["breakdown"].get("leave_balance")
        ),
    }


def _build_quick_response(validated: dict, body) -> dict:
    decision = validated.get("decision", "escalate")
    templates = {
        "approve":  f"✅ موافقة على {body.requested_days} يوم",
        "reject":   f"❌ رفض طلب {body.requested_days} يوم — {validated.get('reason', '')[:80]}",
        "escalate": f"⏳ محول للمراجعة البشرية ({body.requested_days} يوم)",
    }
    return {"message": templates.get(decision, "?"), "decision": decision}