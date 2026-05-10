"""
🎫 Support Ticket Workflow — v2.0
===================================
Pipeline محسّن لمعالجة ticket_created events.

التحسينات عن v1:
  ✅ Idempotency guard  — مش هيشتغل على نفس الـ ticket مرتين
  ✅ SLA tracking       — كل priority ليه deadline واضح
  ✅ Arabic NLP         — يفهم ويصنّف الـ tickets العربية
  ✅ AI Gemini triage   — للـ tickets المعقدة اللي الـ rules مش كافية فيها
  ✅ Confidence scoring — أدق بناءً على category + priority معاً
  ✅ Customer auto-response payload — جاهز للإرسال
  ✅ Structured logging — كل step متسجّل بوضوح

Pipeline:
    payload → dedup check → categorize (AR/EN) → SLA assign
            → rule decision → [AI triage if needed]
            → persist → return result
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from audit.logger import AuditLogger

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# ⚙️  CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

# Priority score weights
PRIORITY_SCORES = {
    "critical": 1.00,
    "urgent":   1.00,
    "high":     0.75,
    "medium":   0.50,
    "low":      0.25,
}

# SLA response times (بالساعات)
SLA_HOURS = {
    "critical": 1,
    "urgent":   1,
    "high":     4,
    "medium":   24,
    "low":      72,
}

# Keyword → category mapping (English + Arabic)
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "billing": [
        "invoice", "payment", "charge", "refund", "bill", "subscription",
        "pricing", "cost", "fee", "overcharge", "discount",
        # عربي
        "فاتورة", "دفع", "سداد", "رسوم", "استرداد", "اشتراك", "سعر", "تكلفة",
    ],
    "technical": [
        "bug", "error", "crash", "not working", "broken", "slow", "fail",
        "issue", "problem", "glitch", "down", "outage", "timeout",
        # عربي
        "خطأ", "مشكلة", "تعطل", "بطيء", "لا يعمل", "معطل", "انهيار",
    ],
    "account": [
        "login", "password", "access", "account", "lock", "2fa",
        "signup", "register", "blocked", "suspended", "verify",
        # عربي
        "تسجيل", "حساب", "دخول", "كلمة مرور", "محظور", "تحقق", "تعليق",
    ],
    "product": [
        "feature", "how to", "how do i", "question", "instructions",
        "guide", "tutorial", "help", "documentation", "usage",
        # عربي
        "كيف", "تعليمات", "مساعدة", "دليل", "استخدام", "شرح",
    ],
    "shipping": [
        "delivery", "shipping", "track", "arrived", "package", "order",
        "dispatch", "courier", "late", "missing",
        # عربي
        "شحن", "توصيل", "تتبع", "طلب", "وصل", "تأخير", "مفقود",
    ],
}

# Statuses that mean ticket was already processed — prevent double processing
TERMINAL_STATUSES = {"in_progress", "closed", "resolved", "escalated"}

# Use AI triage for these categories when priority is medium+
AI_TRIAGE_CATEGORIES = {"technical", "billing"}


# ═══════════════════════════════════════════════════════════════════════════════
# 🎫  WORKFLOW
# ═══════════════════════════════════════════════════════════════════════════════

class TicketWorkflow:
    """
    Support Ticket Workflow v2.0

    Orchestrator calls: await workflow.async_run(payload) → result
    """

    def __init__(self):
        self.audit = AuditLogger()

    # ── Async entry (primary path) ────────────────────────────────────────────

    async def async_run(self, payload: dict) -> dict:
        ticket_id   = payload.get("ticket_id", 0)
        subject     = payload.get("subject", "")
        description = payload.get("description", "")
        message     = payload.get("message", f"{subject} {description}".strip())
        priority    = payload.get("priority", "medium").lower()
        customer_id = payload.get("customer_id")
        category_hint = payload.get("category")  # قد يكون جاي من الـ webhook

        self.audit.log(
            event_type="ticket_created",
            stage="workflow",
            message=f"🎫 TicketWorkflow started — ticket #{ticket_id}",
            data={"ticket_id": ticket_id, "priority": priority},
        )

        # ── Step 0: Atomic Claim — يحجز الـ ticket فوراً عشان يمنع double processing ──
        # بنعمل UPDATE بشرط status='open' — لو نجح معناها احنا أول حد شغال عليه
        # لو فشل (rowcount=0) معناها حد تاني حجزه قبلنا → skip
        if ticket_id:
            claimed = await self._claim_ticket(ticket_id)
            if not claimed:
                logger.info(
                    f"⏭️ [TicketWorkflow] Ticket #{ticket_id} already claimed — skipping"
                )
                return {
                    "decision":   "skipped",
                    "confidence": 1.0,
                    "ticket_id":  ticket_id,
                    "reasoning":  "Ticket already claimed by another process (idempotency guard)",
                    "agent":      "support_agent",
                    "workflow":   "TicketWorkflow_v2",
                }

        # ── Step 1: Categorize (EN + AR) ──────────────────────────────────────
        category = category_hint or self._categorize(message)

        # ── Step 2: SLA deadline ──────────────────────────────────────────────
        sla_deadline = self._compute_sla(priority)

        # ── Step 3: Priority score ────────────────────────────────────────────
        priority_score = PRIORITY_SCORES.get(priority, 0.50)

        # ── Step 4: Rule-based decision ───────────────────────────────────────
        action, reasoning, confidence = self._decide_action(priority, category, priority_score)

        # ── Step 5: AI triage للحالات المعقدة ────────────────────────────────
        # ⚠️ القاعدة: الـ AI يقدر يصحّح الـ category والـ reasoning بس
        #    الـ action النهائي دايماً بيتقرر من الـ rules — مش من الـ AI
        #    ده بيمنع الـ AI من escalate طلبات low priority بشكل غلط
        ai_analysis = None
        if self._needs_ai_triage(priority, category, confidence):
            ai_analysis = await self._ai_triage(message, category, priority)
            if ai_analysis:
                # ✅ الـ AI يقدر يصحّح الـ category بس
                ai_category = ai_analysis.get("category")
                if ai_category and ai_category != category:
                    logger.info(
                        f"🤖 [AI Triage] Category corrected: {category} → {ai_category}"
                    )
                    category = ai_category
                    # أعد حساب الـ action بناءً على الـ category الجديد
                    action, reasoning, confidence = self._decide_action(
                        priority, category, priority_score
                    )
                # ✅ الـ AI يقدر يضيف reasoning أوضح
                if ai_analysis.get("reasoning"):
                    reasoning = ai_analysis["reasoning"]

        # ── Step 6: Persist ───────────────────────────────────────────────────
        if ticket_id:
            await self._persist(ticket_id, action, reasoning, category, customer_id)

        # ── Step 7: Build response ────────────────────────────────────────────
        result = {
            "decision":        action,
            "confidence":      round(confidence, 2),
            "category":        category,
            "priority":        priority,
            "ticket_id":       ticket_id,
            "reasoning":       reasoning,
            "sla_deadline":    sla_deadline.isoformat() if sla_deadline else None,
            "sla_hours":       SLA_HOURS.get(priority, 24),
            "ai_triage":       bool(ai_analysis),
            "agent":           "support_agent",
            "workflow":        "TicketWorkflow_v2",
            # Auto-response payload جاهز للإرسال للـ customer
            "customer_response": self._build_customer_response(
                action, category, priority, sla_deadline
            ),
        }

        self.audit.log(
            event_type="ticket_created",
            stage="workflow",
            message=f"🏁 TicketWorkflow complete — {action}",
            data={"ticket_id": ticket_id, "category": category, "action": action},
        )

        logger.info(
            f"🎫 Ticket #{ticket_id} → {action} [{category}] "
            f"| conf: {confidence:.0%} | SLA: {SLA_HOURS.get(priority)}h — {reasoning}"
        )
        return result

    # ── Sync fallback ─────────────────────────────────────────────────────────

    def run(self, payload: dict) -> dict:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self.async_run(payload))
                    return future.result()
            return loop.run_until_complete(self.async_run(payload))
        except Exception as e:
            return {"status": "error", "message": str(e), "stage": "ticket_workflow"}

    # ═══════════════════════════════════════════════════════════════════════════
    # 🔒  PRIVATE HELPERS
    # ═══════════════════════════════════════════════════════════════════════════

    async def _claim_ticket(self, ticket_id: int) -> bool:
        """
        Atomic claim — يعمل UPDATE بشرط status=open فقط.
        لو نجح (rowcount=1) → احنا أول حد شغال عليه ✅
        لو فشل (rowcount=0) → حد تاني حجزه قبلنا → skip ⏭️

        ده بيحل مشكلة الـ race condition بين الـ Webhook والـ DBWatcher
        لأن MySQL بيضمن إن الـ UPDATE atomic — مش ممكن اتنين يكسبوا في نفس الوقت.
        """
        try:
            from core.db import get_db
            import importlib
            db_module = importlib.import_module("core.db")
            with db_module.get_db() as (conn, cur):
                cur.execute(
                    "UPDATE tickets SET status = %s WHERE id = %s AND status = %s",
                    ("in_progress", ticket_id, "open")
                )
                conn.commit()
                return cur.rowcount == 1   # 1 = نجح، 0 = حد سبقنا
        except Exception as e:
            logger.warning(f"⚠️ [TicketWorkflow] Claim failed for ticket #{ticket_id}: {e}")
            return True   # في حالة خطأ غريب، خلي الـ workflow يكمل

    def _categorize(self, text: str) -> str:
        """Keyword-based categorization — EN + Arabic."""
        text_lower = text.lower()
        for category, keywords in CATEGORY_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                return category
        return "general"

    def _compute_sla(self, priority: str) -> Optional[datetime]:
        """احسب الـ SLA deadline بناءً على الـ priority."""
        hours = SLA_HOURS.get(priority)
        if hours is None:
            return None
        return datetime.utcnow() + timedelta(hours=hours)

    def _decide_action(
        self, priority: str, category: str, score: float
    ) -> tuple[str, str, float]:
        """
        Rule-based decision engine.
        Returns: (action, reasoning, confidence)
        """
        if priority in ("critical", "urgent") or score >= 0.9:
            return (
                "escalate",
                f"🚨 Urgent [{category}] ticket — escalated to senior support team immediately.",
                0.95,
            )

        if priority == "high" or score >= 0.7:
            return (
                "assign",
                f"⚡ High-priority [{category}] ticket — assigned to first available support agent.",
                0.75,
            )

        if category == "billing":
            return (
                "assign",
                "💳 Billing issue — assigned to billing specialist.",
                0.80,
            )

        if category == "technical":
            return (
                "assign",
                "🔧 Technical issue — assigned to technical support team.",
                0.70,
            )

        if category == "account":
            return (
                "assign",
                "🔐 Account issue — assigned to account management team.",
                0.70,
            )

        return (
            "queue",
            f"📥 [{category.capitalize()}] ticket queued for standard support processing.",
            0.60,
        )

    def _needs_ai_triage(self, priority: str, category: str, confidence: float) -> bool:
        """
        قرر هل محتاجين Gemini يراجع الـ ticket ده.
        بنستخدم AI بس للـ tickets اللي فيها شك أو حساسية.
        """
        if confidence < 0.65:
            return True
        if priority in ("high", "critical", "urgent") and category in AI_TRIAGE_CATEGORIES:
            return True
        return False

    async def _ai_triage(
        self, message: str, category: str, priority: str
    ) -> Optional[dict]:
        """
        اسأل Gemini يحلل الـ ticket ويدي رأيه.
        بيرجع dict فيه: action, reasoning, confidence
        """
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            from config.settings import get_settings
            import json, re

            settings = get_settings()
            llm = ChatGoogleGenerativeAI(
                model=settings.GEMINI_MODEL,
                google_api_key=settings.GOOGLE_API_KEY,
                temperature=0.1,
            )

            prompt = f"""أنت متخصص في دعم العملاء لنظام ERP.

حلّل هذه التذكرة وأعطِ قرارًا:

الرسالة: {message}
الفئة المقترحة: {category}
الأولوية: {priority}

أعد JSON فقط بالشكل التالي (بدون أي نص إضافي):
{{
  "action": "assign" | "escalate" | "queue",
  "category": "billing" | "technical" | "account" | "product" | "shipping" | "general",
  "reasoning": "سبب القرار بإيجاز",
  "confidence": 0.0 إلى 1.0
}}"""

            response = await llm.ainvoke(prompt)
            raw = response.content.strip()

            # Clean JSON
            raw = re.sub(r"```json|```", "", raw).strip()
            data = json.loads(raw)

            logger.info(
                f"🤖 [AI Triage] action={data.get('action')} "
                f"conf={data.get('confidence')} cat={data.get('category')}"
            )
            return data

        except Exception as e:
            logger.warning(f"⚠️ [AI Triage] Failed — falling back to rules: {e}")
            return None

    async def _persist(
        self,
        ticket_id: int,
        action: str,
        reasoning: str,
        category: str,
        customer_id: Optional[int],
    ) -> None:
        """
        احفظ النتيجة في الـ DB.
        بنعمله في try/except عشان مش يوقف الـ pipeline لو فشل.
        """
        try:
            from core.db import update_ticket_status, log_action, write_audit_log

            # map action → ticket status
            status_map = {
                "escalate": "escalated",
                "assign":   "in_progress",
                "queue":    "in_progress",
                "skipped":  "open",
            }
            new_status = status_map.get(action, "in_progress")

            update_ticket_status(ticket_id, new_status, reasoning)

            log_action({
                "action_type":  f"ticket_{action}",
                "entity":       "tickets",
                "entity_id":    ticket_id,
                "performed_by": "support_agent",
                "result":       action,
                "details":      reasoning,
            })

            write_audit_log(
                action=f"ticket_{action}",
                entity="tickets",
                entity_id=ticket_id,
                performed_by="support_agent",
                details=reasoning,
            )

        except Exception as e:
            logger.warning(
                f"⚠️ [TicketWorkflow] DB persist failed for ticket #{ticket_id}: {e}"
            )

    def _build_customer_response(
        self,
        action: str,
        category: str,
        priority: str,
        sla_deadline: Optional[datetime],
    ) -> dict:
        """
        ابني الرسالة الجاهزة للإرسال للـ customer.
        ممكن تتبعت بـ email/SMS في الـ notification service.
        """
        templates = {
            "escalate": (
                "🚨 تذكرتك تم تصعيدها فورًا لفريق الدعم المتخصص. "
                "سيتواصل معك أحد المختصين في أقرب وقت ممكن."
            ),
            "assign": (
                f"✅ تذكرتك استُلمت وجارٍ معالجتها. "
                f"سيتواصل معك فريق {self._category_ar(category)} قريبًا."
            ),
            "queue": (
                "📥 تذكرتك في قائمة الانتظار وستُعالج خلال وقت قصير. شكرًا لصبرك."
            ),
        }

        sla_str = (
            sla_deadline.strftime("%Y-%m-%d %H:%M UTC")
            if sla_deadline else "قريبًا"
        )

        return {
            "message":        templates.get(action, "تذكرتك قيد المعالجة."),
            "expected_reply": sla_str,
            "priority":       priority,
            "channel":        "email",   # email | sms | push
        }

    @staticmethod
    def _category_ar(category: str) -> str:
        """ترجمة اسم الـ category للعربي للـ customer messages."""
        return {
            "billing":   "المالي والفواتير",
            "technical": "الدعم التقني",
            "account":   "إدارة الحسابات",
            "product":   "المنتج",
            "shipping":  "الشحن والتوصيل",
            "general":   "الدعم العام",
        }.get(category, "الدعم")