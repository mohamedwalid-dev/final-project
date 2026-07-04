"""
💾 Finance MongoDB Models — Python/Motor v1.0
=============================================
File: models/finance_models.py

PyMongo/Motor equivalent of the Mongoose schemas.
Uses Motor for async operations (FastAPI compatible).

Collections:
    - customers
    - invoices
    - finance_decisions
    - finance_audit
    - finance_collection_log
    - legal_cases

✅ v1.1 Fix: Added serialize_doc() utility for FastAPI JSON serialization.
             ObjectId / datetime في MongoDB documents كانت بتسبب 500 errors.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING, IndexModel

from core.mongo_client import create_mongo_client

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
#  VALIDATORS / ENUMS  (بدل SQL ENUM constraints)
# ════════════════════════════════════════════════════════════════════════════

INVOICE_STATUSES = {
    "pending", "overdue", "paid", "suspended",
    "legal", "written_off", "cancelled",
    "payment_plan", "disputed",
}

COLLECTION_STRATEGIES = {"standard", "aggressive", "gentle", "legal", "write_off"}
SERVICE_STATUSES      = {"active", "suspended", "terminated", "on_hold"}
ACTION_TYPES          = {
    "email", "sms", "call_scheduled", "followup_scheduled",
    "legal_escalation", "internal_notification", "system",
    "suspension", "write_off", "payment_plan",
}
PRIORITIES  = {"low", "medium", "high", "critical"}
LOG_STATUSES = {"sent", "delivered", "failed", "pending", "cancelled"}
CASE_STATUSES = {"opened", "in_progress", "on_hold", "resolved", "settled", "closed"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ════════════════════════════════════════════════════════════════════════════
#  SERIALIZATION UTILITY  ✅ v1.1 — حل مشكلة ObjectId/datetime في JSON
# ════════════════════════════════════════════════════════════════════════════

def serialize_doc(doc):
    """
    Recursively convert MongoDB document → JSON-serializable Python types.

    Handles:
        ObjectId  → str          (MongoDB _id و أي ObjectId field)
        datetime  → ISO 8601 str (created_at, updated_at, sent_at, ...)
        dict      → dict         (recursive)
        list      → list         (recursive)
        Other     → as-is        (str, int, float, bool, None)

    Usage في FastAPI routes:
        from models.finance_models import serialize_doc

        logs = await fin_db.get_collection_log(...)
        return {"logs": serialize_doc(logs)}

        case = await fin_db.get_legal_case(case_id)
        return serialize_doc(case)
    """
    from bson import ObjectId

    if isinstance(doc, list):
        return [serialize_doc(item) for item in doc]

    if isinstance(doc, dict):
        return {key: serialize_doc(value) for key, value in doc.items()}

    if isinstance(doc, ObjectId):
        return str(doc)

    if isinstance(doc, datetime):
        return doc.isoformat()

    return doc


# ════════════════════════════════════════════════════════════════════════════
#  DOCUMENT BUILDERS  (بدل Mongoose Schema constructors)
# ════════════════════════════════════════════════════════════════════════════

def build_customer(data: dict) -> dict:
    """Build a customer document ready for insertion."""
    now = utcnow()
    return {
        "name":               str(data.get("name", "")).strip(),
        "email":              str(data.get("email", "")).strip().lower(),
        "phone":              str(data.get("phone", "")).strip(),
        "credit_score":       float(data.get("credit_score", 650)),
        "industry":           str(data.get("industry", "unknown")),
        "account_age_months": int(data.get("account_age_months", 12)),
        "service_status":     data.get("service_status", "active"),
        "suspension_reason":  data.get("suspension_reason", ""),
        "suspended_at":       data.get("suspended_at"),
        "is_blacklisted":     bool(data.get("is_blacklisted", False)),
        "blacklisted_at":     data.get("blacklisted_at"),
        "created_at":         now,
        "updated_at":         now,
    }


def build_invoice(data: dict) -> dict:
    """Build an invoice document ready for insertion."""
    now = utcnow()
    return {
        "customer_id":          data["customer_id"],           # ObjectId
        "amount":               float(data.get("amount", 0)),
        "due_date":             data["due_date"],               # datetime
        "description":          data.get("description", ""),
        "status":               data.get("status", "pending"),

        # AI fields
        "ai_decision":          "",
        "ai_risk_score":        0.0,
        "ai_decision_reason":   "",
        "ai_action_plan":       "",
        "ai_request_id":        "",

        # Collection config
        "collection_strategy":  "standard",
        "first_reminder_days":  7,

        # Timestamps
        "paid_at":              None,
        "written_off_at":       None,
        "overdue_days":         0,
        "created_at":           now,
        "updated_at":           now,
    }


def build_finance_decision(data: dict) -> dict:
    """Build a finance_decision document."""
    return {
        "agent_type":   data.get("agent_type", "finance_agent"),
        "entity":       data.get("entity", "invoices"),
        "entity_id":    data["entity_id"],                     # ObjectId
        "event_id":     data.get("event_id"),
        "decision":     str(data.get("decision", ""))[:100],
        "confidence":   float(data.get("confidence", 0)),
        "risk_score":   float(data.get("risk_score", 0)),
        "reasoning":    str(data.get("reasoning", ""))[:2000],
        "action_plan":  str(data.get("action_plan", ""))[:1000],
        "execution_ms": int(data.get("execution_ms", 0)),
        "request_id":   str(data.get("request_id", ""))[:100],
        "created_at":   utcnow(),
    }


def build_finance_audit(data: dict) -> dict:
    """Build a finance_audit document."""
    return {
        "domain":          str(data.get("domain", ""))[:50],
        "entity_id":       data["entity_id"],
        "customer_id":     data.get("customer_id"),
        "decision":        str(data.get("decision", ""))[:100],
        "risk_score":      round(float(data.get("risk_score", 0)), 4),
        "confidence":      round(float(data.get("confidence", 0)), 4),
        "decision_source": str(data.get("decision_source", "agent"))[:100],
        "override_rule":   str(data.get("override_rule", ""))[:100],
        "llm_used":        bool(data.get("llm_used", False)),
        "execution_ms":    int(data.get("execution_ms", 0)),
        "request_id":      str(data.get("request_id", ""))[:100],
        "action_plan":     list(data.get("action_plan") or []),
        "flags":           list(data.get("flags") or []),
        "created_at":      utcnow(),
    }


def build_collection_log(data: dict) -> dict:
    """Build a finance_collection_log document."""
    return {
        "invoice_id":    data.get("invoice_id"),
        "customer_id":   data.get("customer_id"),
        "action_type":   str(data.get("action_type", "email"))[:100],
        "template_name": str(data.get("template_name", ""))[:100],
        "subject":       str(data.get("subject", ""))[:300],
        "body":          str(data.get("body", ""))[:5000],
        "priority":      data.get("priority", "medium"),
        "status":        data.get("status", "sent"),
        "sent_at":       utcnow(),
    }


def build_legal_case(data: dict, case_ref: str) -> dict:
    """Build a legal_case document."""
    sla_days = int(data.get("sla_days", 7))
    now      = utcnow()
    return {
        "invoice_id":   data["invoice_id"],
        "customer_id":  data.get("customer_id"),
        "case_ref":     case_ref,
        "case_type":    str(data.get("case_type", "debt_collection"))[:100],
        "amount":       float(data.get("amount", 0)),
        "status":       "opened",
        "priority":     str(data.get("priority", "high"))[:50],
        "assigned_to":  "legal_team",
        "description":  str(data.get("description", ""))[:2000],
        "timeline": [
            {
                "event": "case_opened",
                "date":  now,
                "note":  f"Legal case opened for invoice #{data['invoice_id']}",
            }
        ],
        "sla_deadline": datetime.fromtimestamp(
            now.timestamp() + sla_days * 86400, tz=timezone.utc
        ),
        "resolution":   "",
        "resolved_at":  None,
        "created_at":   now,
        "updated_at":   now,
    }


# ════════════════════════════════════════════════════════════════════════════
#  FinanceDB CLASS
# ════════════════════════════════════════════════════════════════════════════

class FinanceDB:
    """
    Async MongoDB wrapper for Synergy ERP Finance module.

    Example:
        db = FinanceDB("mongodb+srv://user:pass@cluster.mongodb.net", "synergy_erp")
        await db.init_indexes()
        invoice = await db.get_invoice("66f1a2b3c4d5e6f7a8b9c0d1")
    """
    def __init__(
        self,
        uri: str,
        db_name: str = "synergy_erp",
        *,
        tls_insecure: bool | None = None,
        client: AsyncIOMotorClient | None = None,
    ):
        self.client = client or create_mongo_client(uri, tls_insecure=tls_insecure)
        self.db = self.client[db_name]

        self.customers = self.db["customers"]
        self.invoices  = self.db["invoices"]
        self.decisions = self.db["finance_decisions"]
        self.audit     = self.db["finance_audit"]
        self.clog      = self.db["finance_collection_log"]
        self.legal     = self.db["legal_cases"]

    # ── Index Creation ────────────────────────────────────────────────────

    async def init_indexes(self) -> None:
        """Create all indexes. Safe to call multiple times."""

        await self.customers.create_indexes([
            IndexModel([("email", ASCENDING)]),
            IndexModel([("service_status", ASCENDING)]),
            IndexModel([("is_blacklisted", ASCENDING)]),
        ])

        await self.invoices.create_indexes([
            IndexModel([("customer_id", ASCENDING)]),
            IndexModel([("status", ASCENDING)]),
            IndexModel([("due_date", ASCENDING)]),
            IndexModel([("ai_risk_score", ASCENDING)]),
            IndexModel([("status", ASCENDING), ("due_date", ASCENDING)]),
            IndexModel([("status", ASCENDING), ("ai_risk_score", ASCENDING)]),
        ])

        await self.decisions.create_indexes([
            IndexModel([("entity", ASCENDING), ("entity_id", ASCENDING)]),
            IndexModel([("decision", ASCENDING)]),
            IndexModel([("created_at", DESCENDING)]),
        ])

        await self.audit.create_indexes([
            IndexModel([("domain", ASCENDING)]),
            IndexModel([("entity_id", ASCENDING)]),
            IndexModel([("customer_id", ASCENDING)]),
            IndexModel([("decision", ASCENDING)]),
            IndexModel([("created_at", DESCENDING)]),
        ])

        await self.clog.create_indexes([
            IndexModel([("invoice_id", ASCENDING)]),
            IndexModel([("customer_id", ASCENDING)]),
            IndexModel([("action_type", ASCENDING)]),
            IndexModel([("sent_at", DESCENDING)]),
        ])

        await self.legal.create_indexes([
            IndexModel([("invoice_id", ASCENDING)]),
            IndexModel([("customer_id", ASCENDING)]),
            IndexModel([("status", ASCENDING)]),
            IndexModel([("case_ref", ASCENDING)], unique=True),
            IndexModel([("created_at", DESCENDING)]),
        ])

        logger.info("✅ Finance MongoDB indexes initialized")

    # ════════════════════════════════════════════════════════════════════════
    #  INVOICES
    # ════════════════════════════════════════════════════════════════════════

    async def get_invoice(self, invoice_id) -> Optional[dict]:
        """Get invoice with customer info joined (lookup)."""
        from bson import ObjectId
        pipeline = [
            {"$match": {"_id": ObjectId(str(invoice_id))}},
            {"$lookup": {
                "from":         "customers",
                "localField":   "customer_id",
                "foreignField": "_id",
                "as":           "_customer",
            }},
            {"$unwind": {"path": "$_customer", "preserveNullAndEmptyArrays": True}},
            {"$addFields": {
                "customer_name":    "$_customer.name",
                "customer_email":   "$_customer.email",
                "customer_phone":   "$_customer.phone",
                "credit_score":     "$_customer.credit_score",
                "industry":         "$_customer.industry",
                "service_status":   "$_customer.service_status",
                "is_blacklisted":   "$_customer.is_blacklisted",
                "overdue_days_calc": {
                    "$toInt": {
                        "$divide": [
                            {"$subtract": [datetime.now(timezone.utc), "$due_date"]},
                            86_400_000,
                        ]
                    }
                },
            }},
            {"$project": {"_customer": 0}},
        ]
        docs = await self.invoices.aggregate(pipeline).to_list(1)
        return docs[0] if docs else None

    async def get_pending_invoices(self) -> list[dict]:
        """All non-terminal invoices past due_date."""
        cursor = self.invoices.find(
            {
                "status":   {"$nin": ["paid", "written_off", "cancelled"]},
                "due_date": {"$lte": utcnow()},
            }
        ).sort([("due_date", ASCENDING), ("amount", DESCENDING)])

        docs = await cursor.to_list(None)
        for d in docs:
            d["overdue_days_calc"] = self._overdue_days(d.get("due_date"))
        return docs

    async def get_overdue_invoices(self, min_days: int = 1, limit: int = 200) -> list[dict]:
        """Invoices overdue by at least min_days."""
        from datetime import timedelta
        cutoff = utcnow() - timedelta(days=min_days)
        cursor = self.invoices.find(
            {
                "status":   {"$nin": ["paid", "written_off", "cancelled"]},
                "due_date": {"$lt": cutoff},
            }
        ).sort("due_date", ASCENDING).limit(limit)

        docs = await cursor.to_list(None)
        for d in docs:
            d["overdue_days_calc"] = self._overdue_days(d.get("due_date"))
        return docs

    async def create_invoice(self, data: dict) -> str:
        """Insert new invoice. Returns inserted _id as string."""
        doc    = build_invoice(data)
        result = await self.invoices.insert_one(doc)
        return str(result.inserted_id)

    async def update_invoice_status(
        self,
        invoice_id,
        status:          str,
        ai_decision:     str   = "",
        risk_score:      float = 0.0,
        decision_reason: str   = "",
        action_plan:     str   = "",
        request_id:      str   = "",
    ) -> bool:
        from bson import ObjectId
        result = await self.invoices.update_one(
            {"_id": ObjectId(str(invoice_id))},
            {"$set": {
                "status":             status,
                "ai_decision":        ai_decision[:100],
                "ai_risk_score":      risk_score,
                "ai_decision_reason": decision_reason[:1000],
                "ai_action_plan":     action_plan[:500],
                "ai_request_id":      request_id[:100],
                "updated_at":         utcnow(),
            }},
        )
        return result.modified_count > 0

    async def update_invoice_collection_strategy(
        self,
        invoice_id,
        risk_score:          float,
        collection_strategy: str,
        first_reminder_days: int,
        request_id:          str = "",
    ) -> bool:
        from bson import ObjectId
        result = await self.invoices.update_one(
            {"_id": ObjectId(str(invoice_id))},
            {"$set": {
                "ai_risk_score":       risk_score,
                "collection_strategy": collection_strategy[:50],
                "first_reminder_days": first_reminder_days,
                "ai_request_id":       request_id[:100],
                "updated_at":          utcnow(),
            }},
        )
        return result.modified_count > 0

    async def get_customer_invoice_summary(self, customer_id) -> dict:
        from bson import ObjectId
        pipeline = [
            {"$match": {"customer_id": ObjectId(str(customer_id))}},
            {"$group": {
                "_id":                None,
                "total":              {"$sum": 1},
                "paid":               {"$sum": {"$cond": [{"$eq": ["$status", "paid"]},         1, 0]}},
                "overdue":            {"$sum": {"$cond": [{"$eq": ["$status", "overdue"]},       1, 0]}},
                "legal":              {"$sum": {"$cond": [{"$eq": ["$status", "legal"]},         1, 0]}},
                "written_off":        {"$sum": {"$cond": [{"$eq": ["$status", "written_off"]},   1, 0]}},
                "total_amount":       {"$sum": "$amount"},
                "paid_amount":        {"$sum": {"$cond": [{"$eq": ["$status", "paid"]}, "$amount", 0]}},
                "outstanding_amount": {"$sum": {
                    "$cond": [{"$in": ["$status", ["overdue", "legal"]]}, "$amount", 0]
                }},
            }},
        ]
        docs = await self.invoices.aggregate(pipeline).to_list(1)
        return docs[0] if docs else {}

    # ════════════════════════════════════════════════════════════════════════
    #  FINANCE DECISIONS
    # ════════════════════════════════════════════════════════════════════════

    async def save_finance_decision(self, data: dict) -> Optional[str]:
        """Save AI decision. Returns inserted _id."""
        try:
            doc    = build_finance_decision(data)
            result = await self.decisions.insert_one(doc)
            _id    = str(result.inserted_id)
            logger.debug("✅ save_finance_decision: id=%s decision=%s", _id, data.get("decision"))
            return _id
        except Exception as e:
            logger.error("save_finance_decision failed: %s", e)
            return None

    async def get_finance_decisions(self, entity_id, entity: str = "invoices") -> list[dict]:
        from bson import ObjectId
        cursor = self.decisions.find(
            {"entity": entity, "entity_id": ObjectId(str(entity_id))}
        ).sort("created_at", DESCENDING)
        return await cursor.to_list(None)

    # ════════════════════════════════════════════════════════════════════════
    #  FINANCE AUDIT
    # ════════════════════════════════════════════════════════════════════════

    async def write_finance_audit(self, **kwargs) -> None:
        try:
            doc = build_finance_audit(kwargs)
            await self.audit.insert_one(doc)
        except Exception as e:
            logger.error("write_finance_audit failed: %s", e)

    async def get_finance_audit(self, domain: str, entity_id) -> list[dict]:
        from bson import ObjectId
        cursor = self.audit.find(
            {"domain": domain, "entity_id": ObjectId(str(entity_id))}
        ).sort("created_at", DESCENDING)
        return await cursor.to_list(None)

    # ════════════════════════════════════════════════════════════════════════
    #  DASHBOARD STATS
    # ════════════════════════════════════════════════════════════════════════

    async def get_finance_dashboard_stats(self) -> dict:
        try:
            # Invoice stats
            inv_pipeline = [
                {"$group": {
                    "_id":               None,
                    "total_invoices":    {"$sum": 1},
                    "paid":              {"$sum": {"$cond": [{"$eq": ["$status", "paid"]},         1, 0]}},
                    "overdue":           {"$sum": {"$cond": [{"$eq": ["$status", "overdue"]},      1, 0]}},
                    "legal":             {"$sum": {"$cond": [{"$eq": ["$status", "legal"]},        1, 0]}},
                    "suspended":         {"$sum": {"$cond": [{"$eq": ["$status", "suspended"]},    1, 0]}},
                    "written_off":       {"$sum": {"$cond": [{"$eq": ["$status", "written_off"]},  1, 0]}},
                    "payment_plan":      {"$sum": {"$cond": [{"$eq": ["$status", "payment_plan"]}, 1, 0]}},
                    "disputed":          {"$sum": {"$cond": [{"$eq": ["$status", "disputed"]},     1, 0]}},
                    "total_amount":      {"$sum": "$amount"},
                    "collected_amount":  {"$sum": {"$cond": [{"$eq": ["$status", "paid"]}, "$amount", 0]}},
                    "outstanding_amount": {"$sum": {
                        "$cond": [{"$in": ["$status", ["overdue", "legal", "suspended"]]}, "$amount", 0]
                    }},
                }}
            ]
            inv_docs = await self.invoices.aggregate(inv_pipeline).to_list(1)

            # High-risk stats
            risk_pipeline = [
                {"$match": {
                    "ai_risk_score": {"$gte": 0.70},
                    "status":        {"$nin": ["paid", "written_off"]},
                }},
                {"$group": {
                    "_id":              None,
                    "high_risk_count":  {"$sum": 1},
                    "high_risk_amount": {"$sum": "$amount"},
                }},
            ]
            risk_docs = await self.invoices.aggregate(risk_pipeline).to_list(1)

            # Decision breakdown (last 30d)
            from datetime import timedelta
            thirty_ago = utcnow() - timedelta(days=30)
            dec_pipeline = [
                {"$match": {"created_at": {"$gte": thirty_ago}}},
                {"$group": {"_id": "$decision", "count": {"$sum": 1}}},
                {"$sort":  {"count": DESCENDING}},
                {"$limit": 10},
                {"$project": {"_id": 0, "decision": "$_id", "count": 1}},
            ]
            decision_breakdown = await self.decisions.aggregate(dec_pipeline).to_list(None)

            # Collection actions (last 7d)
            seven_ago = utcnow() - timedelta(days=7)
            action_pipeline = [
                {"$match": {"sent_at": {"$gte": seven_ago}}},
                {"$group": {"_id": "$action_type", "count": {"$sum": 1}}},
                {"$project": {"_id": 0, "action_type": "$_id", "count": 1}},
            ]
            action_stats = await self.clog.aggregate(action_pipeline).to_list(None)

            return {
                "invoices":      inv_docs[0]  if inv_docs  else {},
                "risk":          risk_docs[0] if risk_docs else {},
                "decisions_30d": decision_breakdown,
                "actions_7d":    action_stats,
                "timestamp":     utcnow().isoformat(),
            }
        except Exception as e:
            logger.error("get_finance_dashboard_stats failed: %s", e)
            return {"error": str(e)}

    async def get_cashflow_forecast(self) -> dict:
        from datetime import timedelta
        now   = utcnow()
        in7d  = now + timedelta(days=7)
        in30d = now + timedelta(days=30)

        pipeline = [
            {"$match": {"status": {"$nin": ["paid", "written_off", "cancelled"]}}},
            {"$group": {
                "_id":                None,
                "due_7_days":         {"$sum": {"$cond": [
                    {"$and": [{"$lte": ["$due_date", in7d]}, {"$eq": ["$status", "pending"]}]},
                    "$amount", 0,
                ]}},
                "due_30_days":        {"$sum": {"$cond": [
                    {"$and": [{"$lte": ["$due_date", in30d]}, {"$eq": ["$status", "pending"]}]},
                    "$amount", 0,
                ]}},
                "overdue_total":      {"$sum": {"$cond": [{"$eq": ["$status", "overdue"]}, "$amount", 0]}},
                "high_risk_overdue":  {"$sum": {"$cond": [
                    {"$and": [{"$eq": ["$status", "overdue"]}, {"$gte": ["$ai_risk_score", 0.70]}]},
                    "$amount", 0,
                ]}},
                "payment_plan_total": {"$sum": {"$cond": [{"$eq": ["$status", "payment_plan"]}, "$amount", 0]}},
            }},
        ]
        docs = await self.invoices.aggregate(pipeline).to_list(1)
        return docs[0] if docs else {}

    # ════════════════════════════════════════════════════════════════════════
    #  CUSTOMERS
    # ════════════════════════════════════════════════════════════════════════

    async def get_customer_email(self, customer_id) -> Optional[str]:
        from bson import ObjectId
        doc = await self.customers.find_one(
            {"_id": ObjectId(str(customer_id))},
            {"email": 1}
        )
        return doc.get("email") if doc else None

    async def get_customer_info(self, customer_id) -> Optional[dict]:
        from bson import ObjectId
        return await self.customers.find_one({"_id": ObjectId(str(customer_id))})

    async def update_customer_status(
        self,
        customer_id,
        service_status: str  = "",
        is_blacklisted: Optional[bool] = None,
        extra_fields:   Optional[dict] = None,
    ) -> bool:
        from bson import ObjectId
        updates = {"updated_at": utcnow()}

        if service_status:
            updates["service_status"] = service_status[:50]
        if is_blacklisted is not None:
            updates["is_blacklisted"] = bool(is_blacklisted)
            if is_blacklisted:
                updates["blacklisted_at"] = utcnow()
        if extra_fields:
            updates.update(extra_fields)

        if len(updates) == 1:   # only updated_at — nothing real changed
            return False

        result = await self.customers.update_one(
            {"_id": ObjectId(str(customer_id))},
            {"$set": updates},
        )
        return result.modified_count > 0

    # ════════════════════════════════════════════════════════════════════════
    #  COLLECTION LOG
    # ════════════════════════════════════════════════════════════════════════

    async def log_collection_action(self, **kwargs) -> Optional[str]:
        try:
            doc    = build_collection_log(kwargs)
            result = await self.clog.insert_one(doc)
            return str(result.inserted_id)
        except Exception as e:
            logger.error("log_collection_action failed: %s", e)
            return None

    async def get_collection_log(
        self,
        invoice_id:  Optional[str] = None,
        customer_id: Optional[str] = None,
        action_type: Optional[str] = None,
        limit:       int = 50,
    ) -> list[dict]:
        from bson import ObjectId
        filt = {}
        if invoice_id:
            try:
                filt["invoice_id"] = ObjectId(str(invoice_id))
            except Exception:
                filt["invoice_id"] = invoice_id
        if customer_id:
            try:
                filt["customer_id"] = ObjectId(str(customer_id))
            except Exception:
                filt["customer_id"] = customer_id
        if action_type:
            filt["action_type"] = action_type

        cursor = self.clog.find(filt).sort("sent_at", DESCENDING).limit(limit)
        return await cursor.to_list(None)

    async def get_collection_action_stats(self, days: int = 7) -> dict:
        from datetime import timedelta
        since = utcnow() - timedelta(days=days)

        breakdown_pipeline = [
            {"$match": {"sent_at": {"$gte": since}}},
            {"$group": {
                "_id":   {"action_type": "$action_type", "status": "$status", "priority": "$priority"},
                "count": {"$sum": 1},
            }},
            {"$sort": {"count": DESCENDING}},
            {"$project": {
                "_id": 0,
                "action_type": "$_id.action_type",
                "status":      "$_id.status",
                "priority":    "$_id.priority",
                "count":       1,
            }},
        ]

        summary_pipeline = [
            {"$match": {"sent_at": {"$gte": since}}},
            {"$group": {
                "_id":             None,
                "emails_sent":     {"$sum": {"$cond": [{"$eq": ["$action_type", "email"]},                1, 0]}},
                "legal_escalations":{"$sum": {"$cond": [{"$eq": ["$action_type", "legal_escalation"]},   1, 0]}},
                "notifications":   {"$sum": {"$cond": [{"$eq": ["$action_type", "internal_notification"]},1, 0]}},
                "system_actions":  {"$sum": {"$cond": [{"$eq": ["$action_type", "system"]},              1, 0]}},
                "calls_scheduled": {"$sum": {"$cond": [{"$eq": ["$action_type", "call_scheduled"]},      1, 0]}},
                "followups":       {"$sum": {"$cond": [{"$eq": ["$action_type", "followup_scheduled"]},  1, 0]}},
                "critical_actions":{"$sum": {"$cond": [{"$eq": ["$priority",   "critical"]},             1, 0]}},
                "total":           {"$sum": 1},
            }},
        ]

        breakdown = await self.clog.aggregate(breakdown_pipeline).to_list(None)
        summary_docs = await self.clog.aggregate(summary_pipeline).to_list(1)
        return {"breakdown": breakdown, "summary": summary_docs[0] if summary_docs else {}}

    # ════════════════════════════════════════════════════════════════════════
    #  LEGAL CASES
    # ════════════════════════════════════════════════════════════════════════

    async def create_legal_case(self, **kwargs) -> dict:
        import uuid
        now    = utcnow()
        yyyymm = now.strftime("%Y%m")
        case_ref = f"LEG-{yyyymm}-{uuid.uuid4().hex[:6].upper()}"
        try:
            doc    = build_legal_case(kwargs, case_ref)
            result = await self.legal.insert_one(doc)
            return {
                "case_id":    str(result.inserted_id),
                "case_ref":   case_ref,
                "status":     "opened",
                "invoice_id": str(kwargs["invoice_id"]),
                "sla_days":   kwargs.get("sla_days", 7),
            }
        except Exception as e:
            logger.error("create_legal_case failed: %s", e)
            return {"error": str(e)}

    async def get_legal_cases(
        self,
        status:      Optional[str] = None,
        customer_id: Optional[str] = None,
        limit:       int = 50,
    ) -> list[dict]:
        from bson import ObjectId
        filt = {}
        if status:
            filt["status"] = status
        if customer_id:
            try:
                filt["customer_id"] = ObjectId(str(customer_id))
            except Exception:
                filt["customer_id"] = customer_id

        cursor = self.legal.find(filt).sort("created_at", DESCENDING).limit(limit)
        return await cursor.to_list(None)

    async def get_legal_case(self, case_id) -> Optional[dict]:
        from bson import ObjectId
        return await self.legal.find_one({"_id": ObjectId(str(case_id))})

    async def update_legal_case_status(
        self,
        case_id,
        status:     str,
        note:       str = "",
        resolution: str = "",
    ) -> bool:
        from bson import ObjectId
        timeline_entry = {
            "event": f"status_changed_to_{status}",
            "date":  utcnow(),
            "note":  note[:500],
        }
        updates = {
            "status":     status[:50],
            "updated_at": utcnow(),
        }
        if resolution:
            updates["resolution"] = resolution[:2000]
        if status in ("resolved", "settled", "closed"):
            updates["resolved_at"] = utcnow()

        result = await self.legal.update_one(
            {"_id": ObjectId(str(case_id))},
            {
                "$set":  updates,
                "$push": {"timeline": timeline_entry},
            },
        )
        return result.modified_count > 0

    # ════════════════════════════════════════════════════════════════════════
    #  ESCALATION TRACKING
    # ════════════════════════════════════════════════════════════════════════

    TIER_MAP = {
        "pending": 1, "overdue": 2,
        "suspended": 3, "legal": 4, "written_off": 5,
    }
    TIER_LABELS = {
        1: "reminder", 2: "follow_up",
        3: "suspension", 4: "legal", 5: "write_off",
    }

    async def get_escalation_status(self, invoice_id) -> dict:
        from bson import ObjectId
        oid = ObjectId(str(invoice_id))

        invoice = await self.invoices.find_one({"_id": oid})
        if not invoice:
            return {"error": "Invoice not found"}

        actions = await self.clog.find(
            {"invoice_id": oid},
            {"action_type": 1, "template_name": 1, "priority": 1, "status": 1, "sent_at": 1}
        ).sort("sent_at", DESCENDING).limit(20).to_list(None)

        legal = await self.legal.find(
            {"invoice_id": oid},
            {"case_ref": 1, "status": 1, "priority": 1, "created_at": 1, "sla_deadline": 1}
        ).sort("created_at", DESCENDING).to_list(None)

        current_tier = self.TIER_MAP.get(invoice.get("status", ""), 1)

        return {
            "invoice":       invoice,
            "current_tier":  current_tier,
            "tier_label":    self.TIER_LABELS.get(current_tier, "unknown"),
            "actions_taken": actions,
            "legal_cases":   legal,
            "action_count":  len(actions),
        }

    async def get_active_escalations(self) -> list[dict]:
        cursor = self.invoices.find(
            {
                "status":   {"$in": ["overdue", "suspended", "legal", "payment_plan"]},
                "due_date": {"$lt": utcnow()},
            }
        ).sort("due_date", ASCENDING).limit(100)
        return await cursor.to_list(None)

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _overdue_days(due_date) -> int:
        if not due_date:
            return 0
        delta = utcnow().replace(tzinfo=None) - due_date.replace(tzinfo=None)
        return max(0, delta.days)