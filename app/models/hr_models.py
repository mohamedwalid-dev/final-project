"""
models/hr_models.py — HR MongoDB Models
=========================================
Collections:
    • leaves              — Leave requests + AI decisions
    • salary_reviews      — Salary review requests + AI decisions
    • absence_events      — Absence records + AI classification
    • incentive_requests  — Incentive/bonus requests + AI decisions
    • hr_domain_audit     — Unified HR audit trail (all 4 domains)
    • balance_audit_log   — Leave balance change history

Driver: Motor (async)
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from core.mongo_client import create_mongo_client

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _oid(val) -> ObjectId:
    return val if isinstance(val, ObjectId) else ObjectId(str(val))


# ══════════════════════════════════════════════════════════════════════════════
#  SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

def leave_schema(data: dict) -> dict:
    now = _now()
    return {
        # Core
        "employee_id":      data.get("employee_id"),          # int (MySQL FK) or ObjectId
        "employee_name":    data.get("employee_name", ""),
        "department":       data.get("department", ""),
        "leave_type":       data.get("leave_type", "annual"),
        "leave_days":       int(data.get("leave_days", 1)),
        "reason":           data.get("reason", ""),
        "leave_balance":    int(data.get("leave_balance", 0)),

        # Status
        "status":           data.get("status", "pending"),    # pending|approved|rejected|escalated

        # AI Decision
        "ai_decision":      data.get("ai_decision", ""),
        "confidence_score": float(data.get("confidence_score", 0.0)),
        "decision_reason":  data.get("decision_reason", ""),
        "decision_source":  data.get("decision_source", ""),  # ml|llm|rule
        "tier":             int(data.get("tier", 2)),
        "llm_used":         bool(data.get("llm_used", False)),
        "request_id":       data.get("request_id", ""),
        "notes":            data.get("notes", ""),

        # Timestamps
        "created_at":       data.get("created_at", now),
        "updated_at":       now,
    }


def salary_review_schema(data: dict) -> dict:
    now = _now()
    return {
        # Employee context
        "employee_id":                  data.get("employee_id"),
        "employee_name":                data.get("employee_name", ""),
        "department":                   data.get("department", ""),
        "job_level":                    data.get("job_level", "junior"),
        "salary_grade":                 data.get("salary_grade", "C"),

        # Review data
        "current_salary_egp":           float(data.get("current_salary_egp", 0)),
        "requested_increment_pct":      float(data.get("requested_increment_pct", 0.10)),
        "market_median_egp":            float(data.get("market_median_egp", 0)),
        "market_gap_pct":               float(data.get("market_gap_pct", 0)),
        "months_since_last_increment":  int(data.get("months_since_last_increment", 12)),
        "months_in_role":               int(data.get("months_in_role", 0)),
        "appraisal_cycle":              data.get("appraisal_cycle", "Annual"),
        "kpi_achievement":              float(data.get("kpi_achievement", 0.80)),
        "budget_utilization":           float(data.get("budget_utilization", 0.80)),
        "available_pool_egp":           float(data.get("available_pool_egp", 0)),
        "is_on_pip":                    bool(data.get("is_on_pip", False)),
        "is_on_probation":              bool(data.get("is_on_probation", False)),

        # Status
        "status":                       data.get("status", "pending"),

        # AI Decision
        "ai_decision":                  data.get("ai_decision", ""),
        "confidence_score":             float(data.get("confidence_score", 0.0)),
        "decision_reason":              data.get("decision_reason", ""),
        "recommended_increment_pct":    data.get("recommended_increment_pct"),
        "request_id":                   data.get("request_id", ""),
        "notes":                        data.get("notes", ""),

        # Timestamps
        "created_at":                   data.get("created_at", now),
        "updated_at":                   now,
    }


def absence_event_schema(data: dict) -> dict:
    now = _now()
    return {
        # Employee context
        "employee_id":                   data.get("employee_id"),
        "employee_name":                 data.get("employee_name", ""),
        "department":                    data.get("department", ""),
        "job_level":                     data.get("job_level", "junior"),
        "leave_balance":                 int(data.get("leave_balance", 0)),

        # Absence data
        "absence_date":                  data.get("absence_date"),
        "absence_type_claimed":          data.get("absence_type_claimed", "unexcused"),
        "duration_hours":                float(data.get("duration_hours", 8)),
        "medical_certificate_provided":  bool(data.get("medical_certificate_provided", False)),
        "prior_approval_obtained":       bool(data.get("prior_approval_obtained", False)),
        "reason":                        data.get("reason", ""),

        # History context
        "total_absences_90d":            int(data.get("total_absences_90d", 0)),
        "unexcused_count_90d":           int(data.get("unexcused_count_90d", 0)),
        "late_arrivals_90d":             int(data.get("late_arrivals_90d", 0)),
        "previous_warnings":             data.get("previous_warnings", "none"),
        "performance_score":             float(data.get("performance_score", 0.75)),
        "is_on_pip":                     bool(data.get("is_on_pip", False)),

        # Status
        "status":                        data.get("status", "pending"),

        # AI Decision
        "ai_decision":                   data.get("ai_decision", ""),
        "ai_classification":             data.get("ai_classification", ""),
        "confidence_score":              float(data.get("confidence_score", 0.0)),
        "decision_reason":               data.get("decision_reason", ""),
        "payroll_deduction_days":        float(data.get("payroll_deduction_days", 0.0)),
        "escalation_required":           bool(data.get("escalation_required", False)),
        "request_id":                    data.get("request_id", ""),
        "notes":                         data.get("notes", ""),

        # Timestamps
        "created_at":                    data.get("created_at", now),
        "updated_at":                    now,
    }


def incentive_schema(data: dict) -> dict:
    now = _now()
    return {
        # Employee context
        "employee_id":                      data.get("employee_id"),
        "employee_name":                    data.get("employee_name", ""),
        "department":                       data.get("department", ""),
        "job_level":                        data.get("job_level", "junior"),

        # Incentive data
        "incentive_type":                   data.get("incentive_type", "performance_bonus"),
        "requested_amount_egp":             float(data.get("requested_amount_egp", 0)),
        "approved_amount_egp":              data.get("approved_amount_egp"),
        "kpi_achievement":                  float(data.get("kpi_achievement", 0.80)),
        "performance_score":                float(data.get("performance_score", 0.75)),
        "monthly_salary_egp":               float(data.get("monthly_salary_egp", 0)),
        "tenure_months":                    int(data.get("tenure_months", 0)),
        "is_on_pip":                        bool(data.get("is_on_pip", False)),
        "is_critical_talent":               bool(data.get("is_critical_talent", False)),
        "incentive_budget_remaining_egp":   float(data.get("incentive_budget_remaining_egp", 0)),
        "perf_trend":                       data.get("perf_trend", "stable"),
        "reason":                           data.get("reason", ""),

        # Status
        "status":                           data.get("status", "pending"),

        # AI Decision
        "ai_decision":                      data.get("ai_decision", ""),
        "confidence_score":                 float(data.get("confidence_score", 0.0)),
        "decision_reason":                  data.get("decision_reason", ""),
        "request_id":                       data.get("request_id", ""),
        "notes":                            data.get("notes", ""),

        # Timestamps
        "created_at":                       data.get("created_at", now),
        "updated_at":                       now,
    }


def hr_audit_schema(data: dict) -> dict:
    now = _now()
    return {
        "domain":           data.get("domain", ""),       # leave|salary|absence|incentive
        "entity_id":        data.get("entity_id"),        # ObjectId of the entity
        "employee_id":      data.get("employee_id"),
        "decision":         data.get("decision", ""),
        "confidence":       float(data.get("confidence", 0.0)),
        "decision_source":  data.get("decision_source", "llm"),
        "override_rule":    data.get("override_rule", ""),
        "llm_used":         bool(data.get("llm_used", False)),
        "execution_ms":     int(data.get("execution_ms", 0)),
        "request_id":       data.get("request_id", ""),
        "flags":            data.get("flags", []),
        "extra_data":       data.get("extra_data", {}),
        "created_at":       now,
    }


def balance_audit_schema(data: dict) -> dict:
    now = _now()
    old = int(data.get("old_balance", 0))
    new = int(data.get("new_balance", 0))
    return {
        "employee_id":   data.get("employee_id"),
        "leave_id":      data.get("leave_id"),   # ObjectId of leave or 0
        "old_balance":   old,
        "new_balance":   new,
        "delta":         new - old,
        "change_reason": data.get("change_reason", ""),
        "performed_by":  data.get("performed_by", "hr_agent"),
        "created_at":    now,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  HRDB CLASS
# ══════════════════════════════════════════════════════════════════════════════

class HRDB:
    """
    Async MongoDB layer for the HR domain.

    Usage:
        db = HRDB(uri="mongodb+srv://...", db_name="synergy_erp")
        await db.init_indexes()

        leave_id = await db.create_leave_request({...})
        leave    = await db.get_leave(leave_id)
    """

    def __init__(
        self,
        uri: str,
        db_name: str = "synergy_erp",
        *,
        tls_insecure: bool | None = None,
        client: AsyncIOMotorClient | None = None,
    ):
        self.client: AsyncIOMotorClient = client or create_mongo_client(
            uri, tls_insecure=tls_insecure
        )
        self.db: AsyncIOMotorDatabase = self.client[db_name]

        self.leaves        = self.db["leaves"]
        self.salary        = self.db["salary_reviews"]
        self.absences      = self.db["absence_events"]
        self.incentives    = self.db["incentive_requests"]
        self.hr_audit      = self.db["hr_domain_audit"]
        self.balance_audit = self.db["balance_audit_log"]

    # ─────────────────────────────────────────────────────────
    #  INDEXES
    # ─────────────────────────────────────────────────────────

    async def init_indexes(self) -> None:
        """Call once at app startup (idempotent)."""

        # leaves
        await self.leaves.create_index("employee_id")
        await self.leaves.create_index("status")
        await self.leaves.create_index("leave_type")
        await self.leaves.create_index("request_id", sparse=True)
        await self.leaves.create_index([("status", 1), ("created_at", 1)])
        await self.leaves.create_index("created_at")

        # salary_reviews
        await self.salary.create_index("employee_id")
        await self.salary.create_index("status")
        await self.salary.create_index("created_at")
        await self.salary.create_index("request_id", sparse=True)

        # absence_events
        await self.absences.create_index("employee_id")
        await self.absences.create_index("status")
        await self.absences.create_index("absence_date")
        await self.absences.create_index([("employee_id", 1), ("absence_date", -1)])
        await self.absences.create_index("unexcused_count_90d")
        await self.absences.create_index("created_at")

        # incentive_requests
        await self.incentives.create_index("employee_id")
        await self.incentives.create_index("status")
        await self.incentives.create_index("incentive_type")
        await self.incentives.create_index("created_at")

        # hr_domain_audit
        await self.hr_audit.create_index("domain")
        await self.hr_audit.create_index("entity_id")
        await self.hr_audit.create_index([("domain", 1), ("entity_id", 1)])
        await self.hr_audit.create_index("employee_id")
        await self.hr_audit.create_index("created_at")

        # balance_audit_log
        await self.balance_audit.create_index("employee_id")
        await self.balance_audit.create_index("leave_id", sparse=True)
        await self.balance_audit.create_index("created_at")

        logger.info("✅ HRDB indexes ready")

    # ─────────────────────────────────────────────────────────
    #  LEAVES
    # ─────────────────────────────────────────────────────────

    async def create_leave_request(self, data: dict) -> str:
        doc    = leave_schema(data)
        result = await self.leaves.insert_one(doc)
        return str(result.inserted_id)

    async def get_leave(self, leave_id) -> Optional[dict]:
        doc = await self.leaves.find_one({"_id": _oid(leave_id)})
        return self._serialize(doc)

    async def get_pending_leaves(self) -> list[dict]:
        cursor = self.leaves.find({"status": "pending"}).sort("created_at", 1)
        return [self._serialize(d) async for d in cursor]

    async def get_employee_leaves(self, employee_id, limit: int = 50) -> list[dict]:
        cursor = (
            self.leaves
            .find({"employee_id": employee_id})
            .sort("created_at", -1)
            .limit(limit)
        )
        return [self._serialize(d) async for d in cursor]

    async def update_leave_status(
        self,
        leave_id,
        status:          str,
        ai_decision:     str   = "",
        confidence:      float = 0.0,
        reason:          str   = "",
        decision_source: str   = "",
        tier:            int   = 2,
        llm_used:        bool  = False,
        request_id:      str   = "",
        notes:           str   = "",
    ) -> bool:
        result = await self.leaves.update_one(
            {"_id": _oid(leave_id)},
            {"$set": {
                "status":          status,
                "ai_decision":     ai_decision[:100],
                "confidence_score":confidence,
                "decision_reason": reason[:1000],
                "decision_source": decision_source,
                "tier":            tier,
                "llm_used":        llm_used,
                "request_id":      request_id[:100],
                "notes":           notes[:500],
                "updated_at":      _now(),
            }},
        )
        return result.modified_count > 0

    async def get_leave_status(self, leave_id) -> Optional[str]:
        doc = await self.leaves.find_one({"_id": _oid(leave_id)}, {"status": 1})
        return doc["status"] if doc else None

    # ─────────────────────────────────────────────────────────
    #  SALARY REVIEWS
    # ─────────────────────────────────────────────────────────

    async def create_salary_review(self, data: dict) -> str:
        doc    = salary_review_schema(data)
        result = await self.salary.insert_one(doc)
        return str(result.inserted_id)

    async def get_salary_review(self, review_id) -> Optional[dict]:
        doc = await self.salary.find_one({"_id": _oid(review_id)})
        return self._serialize(doc)

    async def get_pending_salary_reviews(self) -> list[dict]:
        cursor = self.salary.find({"status": "pending"}).sort("created_at", 1)
        return [self._serialize(d) async for d in cursor]

    async def get_employee_salary_reviews(self, employee_id, limit: int = 20) -> list[dict]:
        cursor = (
            self.salary
            .find({"employee_id": employee_id})
            .sort("created_at", -1)
            .limit(limit)
        )
        return [self._serialize(d) async for d in cursor]

    async def update_salary_review_status(
        self,
        review_id,
        status:          str,
        ai_decision:     str   = "",
        confidence:      float = 0.0,
        reason:          str   = "",
        recommended_pct: float = None,
        request_id:      str   = "",
    ) -> bool:
        result = await self.salary.update_one(
            {"_id": _oid(review_id)},
            {"$set": {
                "status":                    status,
                "ai_decision":               ai_decision[:100],
                "confidence_score":          confidence,
                "decision_reason":           reason[:1000],
                "recommended_increment_pct": recommended_pct,
                "request_id":                request_id[:100],
                "updated_at":                _now(),
            }},
        )
        return result.modified_count > 0

    # ─────────────────────────────────────────────────────────
    #  ABSENCE EVENTS
    # ─────────────────────────────────────────────────────────

    async def create_absence_event(self, data: dict) -> str:
        doc    = absence_event_schema(data)
        result = await self.absences.insert_one(doc)
        return str(result.inserted_id)

    async def get_absence_event(self, event_id) -> Optional[dict]:
        doc = await self.absences.find_one({"_id": _oid(event_id)})
        return self._serialize(doc)

    async def get_pending_absence_events(self) -> list[dict]:
        cursor = (
            self.absences
            .find({"status": "pending"})
            .sort([("unexcused_count_90d", -1), ("created_at", 1)])
        )
        return [self._serialize(d) async for d in cursor]

    async def get_employee_absences(self, employee_id, limit: int = 50) -> list[dict]:
        cursor = (
            self.absences
            .find({"employee_id": employee_id})
            .sort("absence_date", -1)
            .limit(limit)
        )
        return [self._serialize(d) async for d in cursor]

    async def get_employee_unexcused_count_90d(self, employee_id) -> int:
        from datetime import timedelta
        cutoff = _now() - timedelta(days=90)
        count  = await self.absences.count_documents({
            "employee_id":          employee_id,
            "absence_type_claimed": {"$in": ["unexcused", "غياب بدون إذن"]},
            "created_at":           {"$gte": cutoff},
            "status":               {"$nin": ["pending", "cancelled"]},
        })
        return count

    async def update_absence_event_status(
        self,
        event_id,
        status:                  str,
        ai_decision:             str   = "",
        ai_classification:       str   = "",
        confidence:              float = 0.0,
        reason:                  str   = "",
        payroll_deduction_days:  float = 0.0,
        escalation_required:     bool  = False,
        request_id:              str   = "",
    ) -> bool:
        result = await self.absences.update_one(
            {"_id": _oid(event_id)},
            {"$set": {
                "status":                  status,
                "ai_decision":             ai_decision[:100],
                "ai_classification":       ai_classification[:100],
                "confidence_score":        confidence,
                "decision_reason":         reason[:1000],
                "payroll_deduction_days":  payroll_deduction_days,
                "escalation_required":     escalation_required,
                "request_id":              request_id[:100],
                "updated_at":              _now(),
            }},
        )
        return result.modified_count > 0

    # ─────────────────────────────────────────────────────────
    #  INCENTIVE REQUESTS
    # ─────────────────────────────────────────────────────────

    async def create_incentive_request(self, data: dict) -> str:
        doc    = incentive_schema(data)
        result = await self.incentives.insert_one(doc)
        return str(result.inserted_id)

    async def get_incentive_request(self, request_id) -> Optional[dict]:
        doc = await self.incentives.find_one({"_id": _oid(request_id)})
        return self._serialize(doc)

    async def get_pending_incentive_requests(self) -> list[dict]:
        cursor = (
            self.incentives
            .find({"status": "pending"})
            .sort([("incentive_type", 1), ("created_at", 1)])
        )
        return [self._serialize(d) async for d in cursor]

    async def get_employee_incentives(self, employee_id, limit: int = 20) -> list[dict]:
        cursor = (
            self.incentives
            .find({"employee_id": employee_id})
            .sort("created_at", -1)
            .limit(limit)
        )
        return [self._serialize(d) async for d in cursor]

    async def update_incentive_status(
        self,
        request_id,
        status:          str,
        ai_decision:     str   = "",
        confidence:      float = 0.0,
        reason:          str   = "",
        approved_amount: float = None,
        req_id_str:      str   = "",
    ) -> bool:
        result = await self.incentives.update_one(
            {"_id": _oid(request_id)},
            {"$set": {
                "status":              status,
                "ai_decision":         ai_decision[:100],
                "confidence_score":    confidence,
                "decision_reason":     reason[:1000],
                "approved_amount_egp": approved_amount,
                "request_id":          req_id_str[:100],
                "updated_at":          _now(),
            }},
        )
        return result.modified_count > 0

    # ─────────────────────────────────────────────────────────
    #  HR DOMAIN AUDIT
    # ─────────────────────────────────────────────────────────

    async def write_hr_domain_audit(
        self,
        domain:          str,
        entity_id,
        employee_id,
        decision:        str   = "",
        confidence:      float = 0.0,
        decision_source: str   = "llm",
        override_rule:   str   = "",
        llm_used:        bool  = True,
        execution_ms:    int   = 0,
        request_id:      str   = "",
        flags:           list  = None,
        extra_data:      dict  = None,
    ) -> None:
        doc = hr_audit_schema({
            "domain":           domain,
            "entity_id":        _oid(entity_id) if entity_id else None,
            "employee_id":      employee_id,
            "decision":         decision,
            "confidence":       confidence,
            "decision_source":  decision_source,
            "override_rule":    override_rule,
            "llm_used":         llm_used,
            "execution_ms":     execution_ms,
            "request_id":       request_id,
            "flags":            flags or [],
            "extra_data":       extra_data or {},
        })
        try:
            await self.hr_audit.insert_one(doc)
        except Exception as e:
            logger.error("write_hr_domain_audit failed: %s", e)

    async def get_hr_domain_audit(
        self,
        domain:    str,
        entity_id,
        limit:     int = 50,
    ) -> list[dict]:
        cursor = (
            self.hr_audit
            .find({"domain": domain, "entity_id": _oid(entity_id)})
            .sort("created_at", -1)
            .limit(limit)
        )
        return [self._serialize(d) async for d in cursor]

    # ─────────────────────────────────────────────────────────
    #  BALANCE AUDIT LOG
    # ─────────────────────────────────────────────────────────

    async def write_balance_audit_log(
        self,
        employee_id,
        old_balance:   int,
        new_balance:   int,
        change_reason: str,
        leave_id=None,
        performed_by:  str = "hr_agent",
    ) -> None:
        delta = new_balance - old_balance
        if (delta > 0
                and "reset" not in change_reason
                and "correction" not in change_reason
                and "carryover" not in change_reason):
            logger.warning(
                "⚠️ [BalanceAudit] Unexpected INCREASE: employee=%s | %d→%d (+%d) | reason=%s",
                employee_id, old_balance, new_balance, delta, change_reason,
            )

        doc = balance_audit_schema({
            "employee_id":   employee_id,
            "leave_id":      _oid(leave_id) if leave_id else None,
            "old_balance":   old_balance,
            "new_balance":   new_balance,
            "change_reason": change_reason[:300],
            "performed_by":  performed_by,
        })
        try:
            await self.balance_audit.insert_one(doc)
        except Exception as e:
            logger.error("write_balance_audit_log failed: %s", e)

    async def get_balance_history(self, employee_id, limit: int = 20) -> list[dict]:
        cursor = (
            self.balance_audit
            .find({"employee_id": employee_id})
            .sort("created_at", -1)
            .limit(limit)
        )
        return [self._serialize(d) async for d in cursor]

    # ─────────────────────────────────────────────────────────
    #  HR DASHBOARD STATS
    # ─────────────────────────────────────────────────────────

    async def get_hr_dashboard_stats(self) -> dict:
        """Aggregated stats across all HR domains."""

        async def _count_by_status(col) -> dict:
            pipeline = [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
            return {d["_id"]: d["count"] async for d in col.aggregate(pipeline)}

        leave_stats    = await _count_by_status(self.leaves)
        salary_stats   = await _count_by_status(self.salary)
        absence_stats  = await _count_by_status(self.absences)
        incentive_stats= await _count_by_status(self.incentives)

        escalated = await self.absences.count_documents({"escalation_required": True})
        pip_count  = await self.absences.count_documents({"is_on_pip": True, "status": "pending"})

        return {
            "leaves":           leave_stats,
            "salary_reviews":   salary_stats,
            "absence_events":   absence_stats,
            "incentives":       incentive_stats,
            "alerts": {
                "escalation_required":  escalated,
                "pip_employees_pending":pip_count,
            },
            "generated_at":     _now().isoformat(),
        }

    # ─────────────────────────────────────────────────────────
    #  INTERNAL HELPERS
    # ─────────────────────────────────────────────────────────

    @staticmethod
    def _serialize(doc: Optional[dict]) -> Optional[dict]:
        """Convert ObjectId + datetime → JSON-safe strings."""
        if doc is None:
            return None
        out = {}
        for k, v in doc.items():
            if isinstance(v, ObjectId):
                out[k] = str(v)
            elif isinstance(v, datetime):
                out[k] = v.isoformat()
            elif isinstance(v, dict):
                out[k] = HRDB._serialize(v)
            elif isinstance(v, list):
                out[k] = [
                    HRDB._serialize(i) if isinstance(i, dict)
                    else (str(i) if isinstance(i, ObjectId) else i)
                    for i in v
                ]
            else:
                out[k] = v
        return out