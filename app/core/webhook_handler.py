"""
app/core/webhook_handler.py
============================
🌐 Webhook Trigger — النوع التالت من الـ Triggers.

User بيعمل request من frontend
    ↓
FastAPI endpoint يستقبل
    ↓
EventBus.publish(event)
    ↓
Orchestrator يشتغل فورًا

الفرق بين الـ Webhook والـ Scheduler:
  - Scheduler: بيشتغل كل X دقايق بغض النظر
  - Webhook:   بيشتغل فورًا لما حد يعمل request ← أسرع وأكفأ

ده FastAPI Router بيتعمل include في main.py:
    app.include_router(webhook_router, prefix="/webhooks", tags=["Webhooks"])
"""

import hashlib
import hmac
import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional


from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from core.event_bus import event_bus
from core.node_hr_proxy import get_hr_db
from core.node_finance_proxy import get_finance_db

logger = logging.getLogger(__name__)

# ── MongoDB DB name ────────────────────────────────────────────────────────
_MONGO_DB = os.getenv("MONGO_DB", "synergy_erp").strip()


# ═════════════════════════════════════════════════════════════════════════════
# 🔐  Signature Verification
# ═════════════════════════════════════════════════════════════════════════════

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "change-me-in-production")


def verify_signature(body: bytes, signature: str, timestamp_str: str) -> bool:
    """
    تحقق من الـ Signature مع حماية ضد Replay Attacks (نافذة 5 دقائق).
    الـ signed payload: timestamp + "." + body  (نفس طريقة Stripe)
    """
    if not signature or not timestamp_str:
        return False

    try:
        timestamp = int(timestamp_str)
    except ValueError:
        return False

    if abs(int(time.time()) - timestamp) > 300:
        logger.warning(f"⏰ [Webhook] Signature expired. ts={timestamp}")
        return False

    signed_payload = f"{timestamp}.".encode() + body
    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


async def check_webhook_signature(
    request: Request,
    x_webhook_signature: Optional[str] = Header(None, alias="X-Webhook-Signature"),
    x_webhook_timestamp: Optional[str] = Header(None, alias="X-Webhook-Timestamp"),
):
    """Dependency — يتحقق من HMAC signature لكل الـ webhooks."""
    if WEBHOOK_SECRET != "change-me-in-production":
        raw_body = await request.body()
        if not verify_signature(raw_body, x_webhook_signature or "", x_webhook_timestamp or ""):
            logger.warning(f"🔐 [Webhook] Invalid signature from {request.client.host}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature or timestamp.",
            )


webhook_router = APIRouter(dependencies=[Depends(check_webhook_signature)])


# ═════════════════════════════════════════════════════════════════════════════
# 🧠  Category Derivation
# ═════════════════════════════════════════════════════════════════════════════

_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "billing":   ["invoice", "payment", "charge", "refund", "فاتورة", "دفع", "سداد"],
    "technical": ["error", "bug", "crash", "slow", "خطأ", "مشكلة", "تعطل"],
    "account":   ["login", "password", "access", "تسجيل", "حساب", "دخول"],
    "shipping":  ["delivery", "shipment", "order", "شحن", "توصيل", "طلب"],
    "general":   [],
}


def derive_category(text: str) -> str:
    lower = text.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return category
    return "general"


# ═════════════════════════════════════════════════════════════════════════════
# 🗄️  MongoDB Helpers  (بيحلوا محل core.db القديمة)
# ═════════════════════════════════════════════════════════════════════════════

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _save_event(
    event_type: str,
    entity: str,
    entity_id: str,
    payload: dict,
) -> str:
    """يحفظ event في events_queue collection ويرجع string ID."""
    try:
        client  = get_shared_mongo_client()
        col     = client[_MONGO_DB]["events_queue"]
        result  = await col.insert_one({
            "event_type": event_type,
            "entity":     entity,
            "entity_id":  str(entity_id),
            "payload":    payload,
            "status":     "pending",
            "created_at": _utcnow(),
        })
        return str(result.inserted_id)
    except Exception as e:
        logger.error(f"[Webhook] _save_event failed: {e}")
        return "0"


async def _save_ticket(data: dict) -> str:
    """يحفظ support ticket في tickets collection ويرجع string ID."""
    try:
        client = get_shared_mongo_client()
        col    = client[_MONGO_DB]["tickets"]
        result = await col.insert_one({
            "customer_id": data.get("customer_id"),
            "message":     data.get("message", ""),
            "category":    data.get("category", "general"),
            "priority":    data.get("priority", "medium"),
            "status":      "open",
            "created_at":  _utcnow(),
            "updated_at":  _utcnow(),
        })
        return str(result.inserted_id)
    except Exception as e:
        logger.error(f"[Webhook] _save_ticket failed: {e}")
        return "0"


async def _save_lead(data: dict) -> str:
    """يحفظ CRM lead في leads collection ويرجع string ID."""
    try:
        client = get_shared_mongo_client()
        col    = client[_MONGO_DB]["leads"]
        result = await col.insert_one({
            "name":       data.get("name", ""),
            "email":      data.get("email", ""),
            "phone":      data.get("phone", ""),
            "source":     data.get("source", "webhook"),
            "notes":      data.get("notes", ""),
            "status":     "new",
            "score":      None,
            "created_at": _utcnow(),
            "updated_at": _utcnow(),
        })
        return str(result.inserted_id)
    except Exception as e:
        logger.error(f"[Webhook] _save_lead failed: {e}")
        return "0"


async def _save_audit_log(
    action: str,
    entity: str,
    entity_id: str,
    performed_by: str,
    details: str = "",
) -> None:
    """يكتب audit log entry في audit_log collection."""
    try:
        client = get_shared_mongo_client()
        col    = client[_MONGO_DB]["audit_log"]
        await col.insert_one({
            "action":       action,
            "entity":       entity,
            "entity_id":    str(entity_id),
            "performed_by": performed_by,
            "details":      details,
            "created_at":   _utcnow(),
        })
    except Exception as e:
        logger.error(f"[Webhook] _save_audit_log failed: {e}")


# ═════════════════════════════════════════════════════════════════════════════
# 📦  Request Schemas
# ═════════════════════════════════════════════════════════════════════════════

class WebhookLeavePayload(BaseModel):
    employee_id:    str            = Field(..., description="ID الموظف")
    requested_days: int            = Field(..., gt=0)
    leave_type:     str            = Field("annual")
    reason:         str            = Field("")
    leave_balance:  int            = Field(0, ge=0)
    employee_name:  Optional[str]  = None
    department:     Optional[str]  = None


class WebhookTicketPayload(BaseModel):
    customer_id:   Optional[int]  = None
    customer_name: Optional[str]  = None
    subject:       str            = Field(..., min_length=5)
    description:   str            = Field(..., min_length=10)
    priority:      str            = Field("medium")
    category:      Optional[str]  = Field(None)


class WebhookLeadPayload(BaseModel):
    name:   str
    email:  str
    phone:  Optional[str] = None
    source: str           = Field("webhook")
    notes:  str           = Field("")


class GenericWebhookPayload(BaseModel):
    event_type: str  = Field(..., description="نوع الـ event")
    payload:    dict = Field(default_factory=dict)
    source:     str  = Field("external")


# ═════════════════════════════════════════════════════════════════════════════
# 🌐  WEBHOOK ENDPOINTS
# ═════════════════════════════════════════════════════════════════════════════

@webhook_router.post(
    "/leave",
    status_code=status.HTTP_202_ACCEPTED,
    summary="🏖️ Trigger: Leave Request",
)
async def webhook_leave_request(
    body:             WebhookLeavePayload,
    background_tasks: BackgroundTasks,
):
    """
    Frontend/HR system بيبعت طلب إجازة → HR Agent يشتغل فورًا.

    ✅ يحفظ في hr_db.leaves (HRDB.create_leave_request)
    ✅ يحفظ في events_queue كـ backup
    ✅ يكتب audit log
    ✅ يبعت event للـ EventBus async
    """
    hr_db = get_hr_db()

    # ── 1. حفظ في HR MongoDB (leaves collection) ──────────────────────────
    leave_data = {
        "employee_id":   body.employee_id,
        "employee_name": body.employee_name or "",
        "department":    body.department or "",
        "leave_type":    body.leave_type,
        "leave_days":    body.requested_days,
        "reason":        body.reason,
        "leave_balance": body.leave_balance,
        "status":        "pending",
    }

    try:
        leave_id = await hr_db.create_leave_request(leave_data)
    except Exception as e:
        logger.warning(f"⚠️ [Webhook] Could not save leave to DB: {e}")
        leave_id = "0"

    # ── 2. Event payload للـ AI Agent ──────────────────────────────────────
    payload = {
        **leave_data,
        "leave_id":  leave_id,
        "source":    "webhook",
    }

    # ── 3. حفظ في events_queue + audit ────────────────────────────────────
    event_id = await _save_event("leave_requested", "leaves", leave_id, payload)

    await _save_audit_log(
        action       = "webhook_leave_received",
        entity       = "leaves",
        entity_id    = leave_id,
        performed_by = f"webhook_employee_{body.employee_id}",
        details      = f"{body.requested_days} days — {body.leave_type}",
    )

    # ── 4. Publish للـ EventBus في الـ background ──────────────────────────
    background_tasks.add_task(
        event_bus.publish,
        "leave_requested",
        {**payload, "webhook_event_id": event_id},
    )

    logger.info(f"🌐 [Webhook] Leave #{leave_id} — employee {body.employee_id}")

    return {
        "accepted":   True,
        "leave_id":   leave_id,
        "event_id":   event_id,
        "event_type": "leave_requested",
        "processing": "async — AI agent will evaluate shortly",
        "timestamp":  _utcnow().isoformat(),
    }


@webhook_router.post(
    "/ticket",
    status_code=status.HTTP_202_ACCEPTED,
    summary="🎫 Trigger: Support Ticket",
)
async def webhook_ticket_created(
    body:             WebhookTicketPayload,
    background_tasks: BackgroundTasks,
):
    """
    Customer يفتح ticket من الـ frontend → Support Agent يشتغل فورًا.

    ✅ يحفظ في tickets collection
    ✅ category بيتحسب تلقائيًا لو مش موجود
    ✅ يبعت event للـ EventBus async
    """
    # ── 1. بناء الـ message + category ────────────────────────────────────
    ticket_message = f"{body.subject} - {body.description}"
    category       = body.category or derive_category(ticket_message)

    # ── 2. حفظ في MongoDB tickets collection ──────────────────────────────
    ticket_data = {
        "customer_id": body.customer_id,
        "message":     ticket_message,
        "category":    category,
        "priority":    body.priority,
    }

    try:
        ticket_id = await _save_ticket(ticket_data)
    except Exception as e:
        logger.warning(f"⚠️ [Webhook] Could not save ticket to DB: {e}")
        ticket_id = "0"

    # ── 3. Event payload ───────────────────────────────────────────────────
    payload = {
        "customer_id":   body.customer_id,
        "customer_name": body.customer_name,
        "subject":       body.subject,
        "description":   body.description,
        "message":       ticket_message,
        "category":      category,
        "priority":      body.priority,
        "ticket_id":     ticket_id,
        "source":        "webhook",
    }

    event_id = await _save_event("ticket_created", "tickets", ticket_id, payload)

    background_tasks.add_task(
        event_bus.publish,
        "ticket_created",
        {**payload, "webhook_event_id": event_id},
    )

    logger.info(f"🌐 [Webhook] Ticket #{ticket_id} — category: {category} | priority: {body.priority}")

    return {
        "accepted":   True,
        "ticket_id":  ticket_id,
        "event_id":   event_id,
        "event_type": "ticket_created",
        "category":   category,
        "priority":   body.priority,
        "processing": "async — support agent notified",
        "timestamp":  _utcnow().isoformat(),
    }


@webhook_router.post(
    "/lead",
    status_code=status.HTTP_202_ACCEPTED,
    summary="💼 Trigger: New Lead",
)
async def webhook_lead_added(
    body:             WebhookLeadPayload,
    background_tasks: BackgroundTasks,
):
    """
    CRM أو landing page بيبعت lead جديد → CRM Agent يصنفه فورًا.

    ✅ يحفظ في leads collection
    ✅ يبعت event للـ EventBus async
    """
    lead_data = {
        "name":   body.name,
        "email":  body.email,
        "phone":  body.phone or "",
        "source": body.source,
        "notes":  body.notes,
    }

    try:
        lead_id = await _save_lead(lead_data)
    except Exception as e:
        logger.warning(f"⚠️ [Webhook] Could not save lead to DB: {e}")
        lead_id = "0"

    payload = {**lead_data, "lead_id": lead_id, "source": "webhook"}

    event_id = await _save_event("lead_added", "leads", lead_id, payload)

    background_tasks.add_task(
        event_bus.publish,
        "lead_added",
        {**payload, "webhook_event_id": event_id},
    )

    logger.info(f"🌐 [Webhook] Lead #{lead_id} — {body.name} ({body.email})")

    return {
        "accepted":   True,
        "lead_id":    lead_id,
        "event_id":   event_id,
        "event_type": "lead_added",
        "processing": "async — CRM agent will score lead shortly",
        "timestamp":  _utcnow().isoformat(),
    }


@webhook_router.post(
    "/generic",
    status_code=status.HTTP_202_ACCEPTED,
    summary="⚡ Generic Webhook",
)
async def webhook_generic(
    body:             GenericWebhookPayload,
    background_tasks: BackgroundTasks,
):
    """
    أي event من أي نظام خارجي (Zapier, Make, N8N, ...).
    """
    payload  = {**body.payload, "source": body.source}
    event_id = await _save_event(body.event_type, "webhook", "0", payload)

    background_tasks.add_task(
        event_bus.publish,
        body.event_type,
        {**payload, "webhook_event_id": event_id},
    )

    logger.info(f"🌐 [Webhook] Generic event '{body.event_type}' from '{body.source}'")

    return {
        "accepted":   True,
        "event_id":   event_id,
        "event_type": body.event_type,
        "source":     body.source,
        "timestamp":  _utcnow().isoformat(),
    }


# ═════════════════════════════════════════════════════════════════════════════
# 📊  STATUS & HISTORY
# ═════════════════════════════════════════════════════════════════════════════

@webhook_router.get("/status", summary="📊 Webhook System Status")
async def webhook_status():
    return {
        "webhook_system": "active",
        "endpoints": [
            "POST /webhooks/leave    — Leave request trigger",
            "POST /webhooks/ticket   — Support ticket trigger",
            "POST /webhooks/lead     — CRM lead trigger",
            "POST /webhooks/generic  — Custom event trigger",
        ],
        "signature_verification": WEBHOOK_SECRET != "change-me-in-production",
        "event_bus_stats":        event_bus.get_stats(),
        "timestamp":              _utcnow().isoformat(),
    }


@webhook_router.get("/history", summary="📜 Recent Events History")
async def webhook_history(event_type: Optional[str] = None, limit: int = 20):
    history = event_bus.get_history(event_type=event_type, limit=limit)
    return {
        "count":      len(history),
        "event_type": event_type or "all",
        "events":     history,
    }
