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
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from core.db import create_event, create_ticket, create_lead, create_leave_request, write_audit_log

from core.event_bus import event_bus

logger = logging.getLogger(__name__)

# ─── Webhook Secret (لـ signature verification) ───────────────────────────────
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "change-me-in-production")

async def check_webhook_signature(
    request: Request,
    x_webhook_signature: Optional[str] = Header(None, alias="X-Webhook-Signature"),
    x_webhook_timestamp: Optional[str] = Header(None, alias="X-Webhook-Timestamp"),
):
    """Dependency to verify the HMAC signature for all webhooks."""
    if WEBHOOK_SECRET != "change-me-in-production":
        raw_body = await request.body()
        if not verify_signature(raw_body, x_webhook_signature or "", x_webhook_timestamp or ""):
            logger.warning(f"🔐 [Webhook] Invalid signature/timestamp from {request.client.host}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature or timestamp. Check X-Webhook-Signature and X-Webhook-Timestamp headers.",
            )

from fastapi import Depends
webhook_router = APIRouter(dependencies=[Depends(check_webhook_signature)])


# ═════════════════════════════════════════════════════════════════════════════
# 🔐  Signature Verification
# ═════════════════════════════════════════════════════════════════════════════

import time

def verify_signature(body: bytes, signature: str, timestamp_str: str) -> bool:
    """
    تحقق من الـ Signature مع حماية ضد هجمات إعادة الإرسال (Replay Attacks).
    الـ payload الجديد بيبقى: timestamp + "." + body
    """
    if not signature or not timestamp_str:
        return False
        
    try:
        timestamp = int(timestamp_str)
    except ValueError:
        return False

    # 1. Replay Attack Prevention (5 دقائق)
    current_time = int(time.time())
    if abs(current_time - timestamp) > 300:
        logger.warning(f"⏰ [Webhook] Signature expired or too far in the future. ts={timestamp}")
        return False

    # 2. بناء النص اللي هيتعمله Hash بنفس طريقة Stripe
    signed_payload = f"{timestamp}.".encode() + body

    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()
    
    return hmac.compare_digest(expected, signature)


# ═════════════════════════════════════════════════════════════════════════════
# 🧠  AI Category Derivation (lightweight heuristic — AI agent يكمّل بعدين)
# ═════════════════════════════════════════════════════════════════════════════

_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "billing":      ["invoice", "payment", "charge", "refund", "فاتورة", "دفع", "سداد"],
    "technical":    ["error", "bug", "crash", "slow", "خطأ", "مشكلة", "تعطل"],
    "account":      ["login", "password", "access", "تسجيل", "حساب", "دخول"],
    "shipping":     ["delivery", "shipment", "order", "شحن", "توصيل", "طلب"],
    "general":      [],   # fallback
}

def derive_category(text: str) -> str:
    """
    يشتق الـ category من نص الـ message.
    هيورجع واحدة من: billing / technical / account / shipping / general
    الـ AI agent بعدين ممكن يعيد التصنيف بدقة أكبر.
    """
    lower = text.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return category
    return "general"


# ═════════════════════════════════════════════════════════════════════════════
# 📦  Request Schemas
# ═════════════════════════════════════════════════════════════════════════════

class WebhookLeavePayload(BaseModel):
    employee_id:    str = Field(..., description="ID الموظف")
    requested_days: int = Field(..., gt=0)
    leave_type:     str = Field("annual")
    reason:         str = Field("")
    leave_balance:  int = Field(0, ge=0)
    employee_name:  Optional[str] = None
    department:     Optional[str] = None


class WebhookTicketPayload(BaseModel):
    """
    ✅ Updated schema — يتطابق مع tickets table:
        tickets(customer_id, message, category, priority, status)

    subject + description → message (AI يفهم الكل من الـ message)
    category → derived automatically أو manual override
    """
    customer_id:    Optional[int]  = None
    customer_name:  Optional[str]  = None
    subject:        str            = Field(..., min_length=5,  description="موضوع التذكرة")
    description:    str            = Field(..., min_length=10, description="تفاصيل المشكلة")
    priority:       str            = Field("medium",           description="low|medium|high|critical")
    # category اختياري — لو مش موجود بيتحسب automatically
    category:       Optional[str]  = Field(None,              description="billing|technical|account|shipping|general")


class WebhookLeadPayload(BaseModel):
    name:   str
    email:  str
    phone:  Optional[str] = None
    source: str = Field("webhook")
    notes:  str = Field("")


class GenericWebhookPayload(BaseModel):
    """للـ events الـ custom من أنظمة خارجية."""
    event_type: str  = Field(..., description="نوع الـ event")
    payload:    dict = Field(default_factory=dict)
    source:     str  = Field("external", description="مصدر الـ webhook")


# ═════════════════════════════════════════════════════════════════════════════
# 🌐  WEBHOOK ENDPOINTS
# ═════════════════════════════════════════════════════════════════════════════

@webhook_router.post(
    "/leave",
    status_code=status.HTTP_202_ACCEPTED,
    summary="🏖️ Trigger: Leave Request",
    description="Frontend/HR system بيبعت طلب إجازة → Orchestrator يشتغل فورًا",
)
async def webhook_leave_request(
    body:             WebhookLeavePayload,
    background_tasks: BackgroundTasks,
):
    payload = body.dict()
    payload["source"] = "webhook"

    # ✅ احفظ الـ leave في DB الأول عشان تاخد ID حقيقي
    leave_db_data = {
        "employee_id": body.employee_id,
        "leave_days":  body.requested_days,  # ✅ الاسم الصح للـ DB column
        "leave_type":  body.leave_type,
        "reason":      body.reason,
        # ✅ خلاص — بس الـ 4 دول اللي الـ INSERT محتاجهم
    }


    try:
        leave_id = create_leave_request(leave_db_data)    # ✅ ID حقيقي من DB
    except Exception as e:
        logger.warning(f"⚠️ [Webhook] Could not save leave to DB: {e}. Continuing without DB ID.")
        leave_id = 0

    payload["leave_id"] = leave_id               # ✅ بيتبعت في الـ event

    # حفظ في event queue كـ backup
    event_id = create_event(
        event_type="leave_requested",
        entity="leaves",
        entity_id=leave_id,                      # ✅ ID حقيقي بدل 0
        payload=payload,
    )

    background_tasks.add_task(
        event_bus.publish,
        "leave_requested",
        {**payload, "webhook_event_id": event_id},
    )

    background_tasks.add_task(
        write_audit_log,
        action="webhook_leave_received",
        entity="leaves",
        entity_id=leave_id,                      # ✅ ID حقيقي
        performed_by=f"webhook_employee_{body.employee_id}",
        details=f"{body.requested_days} days — {body.leave_type}",
    )

    logger.info(f"🌐 [Webhook] Leave #{leave_id} request received — employee {body.employee_id}")

    return {
        "accepted":   True,
        "leave_id":   leave_id,                  # ✅ في الـ response كمان
        "event_id":   event_id,
        "event_type": "leave_requested",
        "processing": "async — AI agent will evaluate shortly",
        "timestamp":  datetime.utcnow().isoformat() + "Z",
    }


@webhook_router.post(
    "/ticket",
    status_code=status.HTTP_202_ACCEPTED,
    summary="🎫 Trigger: Support Ticket",
    description="Customer يفتح ticket من الـ frontend → Support Agent يشتغل فورًا",
)
async def webhook_ticket_created(
    body:             WebhookTicketPayload,
    background_tasks: BackgroundTasks,
):
    """
    🌐 Webhook Trigger — ticket جديد من customer.

    ✅ subject + description → message واحدة
    ✅ category → derived automatically لو مش موجود
    ✅ AI agent يكمّل التصنيف الدقيق بعدين
    """
    # ── 1. بناء الـ message من subject + description ──────────────────────────
    ticket_message = f"{body.subject} - {body.description}"

    # ── 2. category: manual override أو auto-derived ─────────────────────────
    category = body.category or derive_category(ticket_message)

    # ── 3. حفظ في DB بالـ schema الصح ─────────────────────────────────────────
    ticket_db_data = {
        "customer_id": body.customer_id,
        "message":     ticket_message,   # ✅ message بدل subject/description
        "category":    category,         # ✅ derived or manual
        "priority":    body.priority,
        # status بيبدأ "open" تلقائيًا من الـ DB default
    }

    try:
        ticket_id = create_ticket(ticket_db_data)
    except Exception as e:
        logger.warning(f"⚠️ [Webhook] Could not save ticket to DB: {e}. Continuing without DB ID.")
        ticket_id = 0

    # ── 4. Event payload — بيتبعت للـ AI Agent ───────────────────────────────
    # بنحط subject و description لأن الـ AI ممكن يحتاجهم للفهم الكامل
    payload = {
        "customer_id":   body.customer_id,
        "customer_name": body.customer_name,
        "subject":       body.subject,
        "description":   body.description,
        "message":       ticket_message,   # الـ combined message
        "category":      category,
        "priority":      body.priority,
        "ticket_id":     ticket_id,
        "source":        "webhook",
    }

    event_id = create_event(
        event_type="ticket_created",
        entity="tickets",
        entity_id=ticket_id,
        payload=payload,
    )

    background_tasks.add_task(
        event_bus.publish,
        "ticket_created",
        {**payload, "webhook_event_id": event_id},
    )

    logger.info(
        f"🌐 [Webhook] Ticket #{ticket_id} received — "
        f"category: {category} | priority: {body.priority}"
    )

    return {
        "accepted":   True,
        "ticket_id":  ticket_id,
        "event_id":   event_id,
        "event_type": "ticket_created",
        "category":   category,
        "priority":   body.priority,
        "processing": "async — support agent notified",
        "timestamp":  datetime.utcnow().isoformat() + "Z",
    }


@webhook_router.post(
    "/lead",
    status_code=status.HTTP_202_ACCEPTED,
    summary="💼 Trigger: New Lead",
    description="CRM أو landing page بيبعت lead جديد → CRM Agent يصنفه فورًا",
)
async def webhook_lead_added(
    body:             WebhookLeadPayload,
    background_tasks: BackgroundTasks,
):
    """🌐 Webhook Trigger — lead جديد من CRM أو landing page."""
    payload = body.dict()
    payload["source"] = "webhook"

    lead_db_data = {
        "name":   body.name,
        "email":  body.email,
        "phone":  body.phone or "",
        "source": body.source,
        "notes":  body.notes,
    }

    try:
        lead_id = create_lead(lead_db_data)
    except Exception as e:
        logger.warning(f"⚠️ [Webhook] Could not save lead to DB: {e}. Continuing without DB ID.")
        lead_id = 0

    payload["lead_id"] = lead_id

    event_id = create_event(
        event_type="lead_added",
        entity="leads",
        entity_id=lead_id,
        payload=payload,
    )

    background_tasks.add_task(
        event_bus.publish,
        "lead_added",
        {**payload, "webhook_event_id": event_id},
    )

    logger.info(f"🌐 [Webhook] Lead #{lead_id} received — {body.name} ({body.email})")

    return {
        "accepted":   True,
        "lead_id":    lead_id,
        "event_id":   event_id,
        "event_type": "lead_added",
        "processing": "async — CRM agent will score lead shortly",
        "timestamp":  datetime.utcnow().isoformat() + "Z",
    }


@webhook_router.post(
    "/generic",
    status_code=status.HTTP_202_ACCEPTED,
    summary="⚡ Generic Webhook",
    description="أي event من أي نظام خارجي (Zapier, Make, N8N, ...)",
)
async def webhook_generic(
    body:             GenericWebhookPayload,
    background_tasks: BackgroundTasks,
):
    """
    🌐 Generic Webhook — يقبل أي event من أي مصدر.
    """
    payload = {**body.payload, "source": body.source}

    event_id = create_event(
        event_type=body.event_type,
        entity="webhook",
        entity_id=0,
        payload=payload,
    )

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
        "timestamp":  datetime.utcnow().isoformat() + "Z",
    }


# ═════════════════════════════════════════════════════════════════════════════
# 📊  WEBHOOK STATUS
# ═════════════════════════════════════════════════════════════════════════════

@webhook_router.get(
    "/status",
    summary="📊 Webhook System Status",
)
async def webhook_status():
    """إرجع status الـ Webhook system والـ EventBus stats."""
    return {
        "webhook_system": "active",
        "endpoints": [
            "POST /webhooks/leave    — Leave request trigger",
            "POST /webhooks/ticket   — Support ticket trigger",
            "POST /webhooks/lead     — CRM lead trigger",
            "POST /webhooks/generic  — Custom event trigger",
        ],
        "signature_verification": WEBHOOK_SECRET != "change-me-in-production",
        "event_bus_stats": event_bus.get_stats(),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@webhook_router.get(    
    "/history",
    summary="📜 Recent Events History",
)
async def webhook_history(event_type: Optional[str] = None, limit: int = 20):
    """اجيب آخر الـ events اللي اتبعتت عبر الـ EventBus."""
    history = event_bus.get_history(event_type=event_type, limit=limit)
    return {
        "count":      len(history),
        "event_type": event_type or "all",
        "events":     history,
    }