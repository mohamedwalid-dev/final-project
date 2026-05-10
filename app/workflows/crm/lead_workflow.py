"""
💼 CRM Lead Workflow — v3.0  (Senior Edition 😈)
=================================================
التحسينات عن v2:
  🥇 Hybrid Scoring     — Layer 1 (rules) + Layer 2 (AI للـ hot leads بس)
  🥈 AI Rate Limiter    — مش أكتر من 15 call/يوم (يحمي الـ quota)
  🥉 Result Cache       — نفس الـ email → نفس النتيجة بدون AI call تاني
  💀 Deduplication      — lead موجود → update مش create جديد

Architecture:
    payload → dedup check → atomic claim → hybrid score
            → [AI only if score≥60 AND quota available AND not cached]
            → persist → return result
"""

import asyncio
import logging
from datetime import datetime, timedelta, date
from typing import Optional

from audit.logger import AuditLogger

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# ⚙️  CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

SOURCE_SCORES = {
    "referral":  0.90,
    "campaign":  0.70,
    "website":   0.60,
    "webhook":   0.55,
    "manual":    0.40,
    "external":  0.35,
    "unknown":   0.25,
}

FOLLOWUP_HOURS = {
    "hot":  24,
    "warm": 72,
    "cold": 168,
}

HOT_KEYWORDS = [
    "urgent", "asap", "immediately", "budget approved", "ready to buy",
    "demo", "pricing", "quote", "purchase", "contract", "sign",
    "عاجل", "فوراً", "ميزانية", "جاهز للشراء", "عرض سعر", "موافق",
    "عقد", "شراء", "اشتراك", "نريد",
]

COLD_KEYWORDS = [
    "just browsing", "not sure", "maybe", "someday", "no budget",
    "just looking", "research", "comparing",
    "مجرد استفسار", "مش متأكد", "ممكن", "مش عارف", "بدون ميزانية",
    "بس بشوف", "مقارنة",
]

FREE_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "live.com", "icloud.com", "mail.com", "ymail.com",
    "yahoo.com.eg", "hotmail.com.eg",
}

TERMINAL_STATUSES = {"contacted", "qualified", "converted", "in_progress", "lost"}
AI_NOTES_MIN_LENGTH = 30

# 🥈 Rate Limiter config
AI_DAILY_LIMIT = 15          # مش أكتر من 15 AI call في اليوم
AI_MIN_SCORE_FOR_CALL = 0.60 # 🥇 بس للـ leads اللي فوق 60%

# 🥉 Cache config
CACHE_TTL_HOURS = 24         # النتيجة تفضل cached لـ 24 ساعة


# ═══════════════════════════════════════════════════════════════════════════════
# 🥈 AI RATE LIMITER
# ═══════════════════════════════════════════════════════════════════════════════

class AIRateLimiter:
    """
    يتتبع عدد الـ AI calls في اليوم الحالي.
    In-memory لأنه بـ process واحدة — لو محتاج multi-process استخدم Redis.
    """

    def __init__(self, daily_limit: int = AI_DAILY_LIMIT):
        self.daily_limit = daily_limit
        self._count: int = 0
        self._reset_date: date = date.today()

    def _reset_if_new_day(self) -> None:
        today = date.today()
        if today != self._reset_date:
            logger.info(
                f"🔄 [RateLimiter] New day — resetting AI call counter "
                f"(was {self._count}, limit={self.daily_limit})"
            )
            self._count = 0
            self._reset_date = today

    def can_call(self) -> bool:
        self._reset_if_new_day()
        return self._count < self.daily_limit

    def record_call(self) -> None:
        self._reset_if_new_day()
        self._count += 1
        remaining = self.daily_limit - self._count
        logger.info(
            f"📊 [RateLimiter] AI call #{self._count}/{self.daily_limit} "
            f"— {remaining} remaining today"
        )

    def status(self) -> dict:
        self._reset_if_new_day()
        return {
            "calls_today":  self._count,
            "daily_limit":  self.daily_limit,
            "remaining":    self.daily_limit - self._count,
            "reset_date":   self._reset_date.isoformat(),
            "can_call":     self.can_call(),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# 🥉 RESULT CACHE
# ═══════════════════════════════════════════════════════════════════════════════

class LeadResultCache:
    """
    Cache نتيجة الـ AI analysis بالـ email.
    نفس الـ email في نفس اليوم → نفس النتيجة بدون API call.
    """

    def __init__(self, ttl_hours: int = CACHE_TTL_HOURS):
        self.ttl = timedelta(hours=ttl_hours)
        self._store: dict[str, dict] = {}   # email → {result, cached_at}

    def get(self, email: str) -> Optional[dict]:
        entry = self._store.get(email.lower())
        if not entry:
            return None
        if datetime.utcnow() - entry["cached_at"] > self.ttl:
            del self._store[email.lower()]
            return None
        logger.info(f"🎯 [Cache] HIT for {email} — skipping AI call")
        return entry["result"]

    def set(self, email: str, result: dict) -> None:
        self._store[email.lower()] = {
            "result":    result,
            "cached_at": datetime.utcnow(),
        }
        logger.info(f"💾 [Cache] Stored result for {email}")

    def invalidate(self, email: str) -> None:
        self._store.pop(email.lower(), None)

    def stats(self) -> dict:
        return {
            "cached_emails": len(self._store),
            "ttl_hours":     CACHE_TTL_HOURS,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# 💼  WORKFLOW
# ═══════════════════════════════════════════════════════════════════════════════

# Singletons — shared across workflow instances
_rate_limiter = AIRateLimiter(daily_limit=AI_DAILY_LIMIT)
_cache        = LeadResultCache(ttl_hours=CACHE_TTL_HOURS)


class LeadWorkflow:
    """
    CRM Lead Scoring Workflow v3.0 — Hybrid AI + Rules

    Layers:
      Layer 1 (always):  Rule-based scoring (free, fast)
      Layer 2 (smart):   AI analysis (only if score ≥ 60% AND quota available AND not cached)
    """

    def __init__(self):
        self.audit        = AuditLogger()
        self.rate_limiter = _rate_limiter
        self.cache        = _cache

    # ── Async entry ───────────────────────────────────────────────────────────

    async def async_run(self, payload: dict) -> dict:
        lead_id = payload.get("lead_id", 0)
        name    = payload.get("name", "Unknown")
        email   = payload.get("email", "")
        source  = payload.get("source", "unknown").lower()
        notes   = payload.get("notes", "")
        phone   = payload.get("phone", "")

        self.audit.log(
            event_type="lead_added",
            stage="workflow",
            message=f"💼 LeadWorkflow v3 started — lead #{lead_id} | {name}",
            data={"lead_id": lead_id, "source": source},
        )

        # ── Step 0: Deduplication ─────────────────────────────────────────────
        if email:
            existing = await self._find_existing_lead(email, lead_id)
            if existing:
                logger.info(
                    f"♻️  [Dedup] Lead with email {email} already exists "
                    f"(id={existing['id']}, status={existing['status']}) — updating"
                )
                return await self._handle_duplicate(existing, payload)

        # ── Step 1: Atomic Claim ──────────────────────────────────────────────
        if lead_id:
            claimed = await self._claim_lead(lead_id)
            if not claimed:
                logger.info(f"⏭️ [LeadWorkflow] Lead #{lead_id} already claimed — skipping")
                return {
                    "decision":   "skipped",
                    "confidence": 1.0,
                    "lead_id":    lead_id,
                    "reasoning":  "Lead already claimed (idempotency guard)",
                    "workflow":   "LeadWorkflow_v3",
                }

        # ── Step 2: Layer 1 — Rule-based scoring (always runs) ────────────────
        score, classification, reasoning_parts = self._score_lead(
            source, email, phone, notes
        )

        # ── Step 3: Layer 2 — AI analysis (smart gate) ───────────────────────
        ai_insight  = None
        ai_source   = "skipped"

        should_use_ai = self._should_use_ai(score, notes, email)

        if should_use_ai == "cache_hit":
            # نتيجة محفوظة — مفيش API call
            cached = self.cache.get(email)
            if cached:
                ai_insight = cached
                ai_source  = "cache"

        elif should_use_ai == "call_ai":
            # 🥇 Hybrid: بس لو score ≥ 60% + quota available
            ai_insight = await self._ai_analyze(name, email, source, notes, classification)
            if ai_insight:
                self.cache.set(email, ai_insight)
                ai_source = "gemini"

        if ai_insight:
            ai_classification = ai_insight.get("classification")
            if ai_classification and ai_classification != classification:
                logger.info(
                    f"🤖 [AI] Override: {classification} → {ai_classification} "
                    f"(source={ai_source})"
                )
                classification = ai_classification
                score_map = {"hot": 0.80, "warm": 0.55, "cold": 0.25}
                score = score_map.get(classification, score)
            reasoning_parts.append(
                f"AI({ai_source}): {ai_insight.get('reasoning', '')}"
            )

        # ── Step 4: Follow-up schedule ────────────────────────────────────────
        followup_date = self._compute_followup(classification)

        # ── Step 5: DB status mapping ─────────────────────────────────────────
        status_map = {"hot": "contacted", "warm": "qualified", "cold": "new"}
        new_status = status_map.get(classification, "new")

        # ── Step 6: Persist ───────────────────────────────────────────────────
        reasoning = " | ".join(reasoning_parts)
        if lead_id:
            await self._persist(lead_id, new_status, score, reasoning)

        # ── Step 7: Result ────────────────────────────────────────────────────
        result = {
            "decision":       classification,
            "confidence":     round(score, 2),
            "score":          int(score * 100),
            "classification": classification,
            "status":         new_status,
            "lead_id":        lead_id,
            "reasoning":      reasoning,
            "followup_date":  followup_date.isoformat() if followup_date else None,
            "followup_hours": FOLLOWUP_HOURS.get(classification, 72),
            "ai_analyzed":    bool(ai_insight),
            "ai_source":      ai_source,            # gemini / cache / skipped
            "ai_quota":       self.rate_limiter.status(),
            "agent":          "crm_agent",
            "workflow":       "LeadWorkflow_v3",
            "next_action":    self._get_next_action(classification, source),
        }

        self.audit.log(
            event_type="lead_added",
            stage="workflow",
            message=f"🏁 LeadWorkflow v3 complete — {classification} (score={int(score*100)}, ai={ai_source})",
            data={"lead_id": lead_id, "classification": classification},
        )

        logger.info(
            f"💼 Lead #{lead_id} ({name}) → {classification} "
            f"| score={int(score*100)} | ai={ai_source} "
            f"| followup: {FOLLOWUP_HOURS.get(classification)}h"
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
            return {"status": "error", "message": str(e), "stage": "lead_workflow"}

    # ═══════════════════════════════════════════════════════════════════════════
    # 🔒  PRIVATE HELPERS
    # ═══════════════════════════════════════════════════════════════════════════

    # ── 💀 Deduplication ──────────────────────────────────────────────────────

    async def _find_existing_lead(self, email: str, current_lead_id: int) -> Optional[dict]:
        """
        دور على lead بنفس الـ email (غير الـ lead الحالي نفسه).
        لو لقي واحد بـ terminal status → مش duplicate (العميل جه تاني).
        """
        try:
            import importlib
            db_module = importlib.import_module("core.db")
            with db_module.get_db() as (_, cur):
                cur.execute(
                    """
                    SELECT id, status, score, created_at
                    FROM leads
                    WHERE email = %s
                      AND id != %s
                      AND status NOT IN ('converted', 'lost')
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (email, current_lead_id or 0)
                )
                return cur.fetchone()
        except Exception as e:
            logger.warning(f"⚠️ [Dedup] DB check failed: {e}")
            return None

    async def _handle_duplicate(self, existing: dict, payload: dict) -> dict:
        """
        Lead موجود → update بدل ما نعمل processing تاني.
        بنحدث الـ notes بس ومش بنغير الـ status.
        """
        existing_id = existing["id"]
        try:
            import importlib
            db_module = importlib.import_module("core.db")
            with db_module.get_db() as (conn, cur):
                cur.execute(
                    "UPDATE leads SET notes = CONCAT(IFNULL(notes,''), %s), updated_at = NOW() WHERE id = %s",
                    (f"\n[Duplicate webhook {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}]", existing_id)
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"⚠️ [Dedup] Update failed: {e}")

        return {
            "decision":        "duplicate",
            "existing_lead_id": existing_id,
            "existing_status":  existing.get("status"),
            "lead_id":          payload.get("lead_id", 0),
            "reasoning":        f"Duplicate email — existing lead #{existing_id} (status={existing.get('status')})",
            "workflow":         "LeadWorkflow_v3",
            "action":           "merged_with_existing",
        }

    # ── Atomic Claim ──────────────────────────────────────────────────────────

    async def _claim_lead(self, lead_id: int) -> bool:
        if not lead_id:
            return True
        try:
            import importlib
            db_module = importlib.import_module("core.db")
            with db_module.get_db() as (conn, cur):
                cur.execute(
                    "UPDATE leads SET status = %s WHERE id = %s AND status = %s",
                    ("in_progress", lead_id, "new")
                )
                conn.commit()
                return cur.rowcount == 1
        except Exception as e:
            logger.warning(f"⚠️ [LeadWorkflow] Claim failed for lead #{lead_id}: {e}")
            return True

    # ── Layer 1: Rule-based scoring ───────────────────────────────────────────

    def _score_lead(
        self, source: str, email: str, phone: str, notes: str
    ) -> tuple[float, str, list[str]]:
        notes_lower = notes.lower()
        parts = []

        base = SOURCE_SCORES.get(source, 0.30)
        parts.append(f"Source:{source}({base:.0%})")

        phone_bonus = 0.10 if phone and phone.strip() else 0.0
        parts.append(f"Phone:{'✅+10%' if phone_bonus else '❌'}")

        if any(kw in notes_lower for kw in HOT_KEYWORDS):
            intent_bonus = +0.20
            parts.append("Intent:🔥hot-keywords")
        elif any(kw in notes_lower for kw in COLD_KEYWORDS):
            intent_bonus = -0.15
            parts.append("Intent:🧊cold-keywords")
        else:
            intent_bonus = 0.0
            parts.append("Intent:neutral")

        email_domain = email.split("@")[-1].lower() if "@" in email else ""
        email_bonus  = 0.05 if email_domain and email_domain not in FREE_DOMAINS else 0.0
        parts.append(f"Email:{'corporate✅' if email_bonus else 'free'}")

        notes_bonus = 0.05 if len(notes) > 50 else 0.0
        if notes_bonus:
            parts.append("Notes:detailed✅")

        score = min(max(base + phone_bonus + intent_bonus + email_bonus + notes_bonus, 0.0), 1.0)

        if score >= 0.70:
            classification = "hot"
        elif score >= 0.45:
            classification = "warm"
        else:
            classification = "cold"

        parts.append(f"L1:{int(score*100)}/100→{classification.upper()}")
        return score, classification, parts

    # ── 🥇 Smart AI Gate ──────────────────────────────────────────────────────

    def _should_use_ai(self, score: float, notes: str, email: str) -> str:
        """
        Returns:
          'cache_hit' → نتيجة محفوظة موجودة
          'call_ai'   → استخدم الـ API
          'skip'      → مش محتاج
        """
        # Cache check أول (مجاني دايماً)
        if email and self.cache.get(email):
            return "cache_hit"

        # 🥇 Hybrid gate: score ≥ 60% بس
        score_qualifies = score >= AI_MIN_SCORE_FOR_CALL

        # Notes طويلة تستاهل تحليل
        has_rich_notes  = len(notes) >= AI_NOTES_MIN_LENGTH

        if not (score_qualifies or has_rich_notes):
            logger.debug(
                f"⏭️ [AI Gate] Skipping AI — score={int(score*100)}% < {int(AI_MIN_SCORE_FOR_CALL*100)}% "
                f"and notes too short"
            )
            return "skip"

        # 🥈 Rate limit check
        if not self.rate_limiter.can_call():
            logger.warning(
                f"🚫 [AI Gate] Daily quota exhausted "
                f"({self.rate_limiter.status()['calls_today']}/{AI_DAILY_LIMIT}) — using rules only"
            )
            return "skip"

        return "call_ai"

    # ── Layer 2: AI analysis ──────────────────────────────────────────────────

    async def _ai_analyze(
        self,
        name: str,
        email: str,
        source: str,
        notes: str,
        current_classification: str,
    ) -> Optional[dict]:
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

            prompt = f"""أنت خبير CRM متخصص في تقييم العملاء المحتملين لنظام ERP.

بيانات الـ Lead:
- الاسم: {name}
- الإيميل: {email}
- المصدر: {source}
- الملاحظات: {notes}
- التصنيف الحالي: {current_classification}

قيّم هذا الـ lead وأعد JSON فقط (بدون أي نص إضافي):
{{
  "classification": "hot" | "warm" | "cold",
  "reasoning": "سبب التصنيف بجملة واحدة",
  "urgency": "high" | "medium" | "low",
  "recommended_action": "الإجراء الموصى به"
}}"""

            # سجّل الـ call قبل ما نبعته
            self.rate_limiter.record_call()

            response = await llm.ainvoke(prompt)
            raw  = response.content.strip()
            raw  = re.sub(r"```json|```", "", raw).strip()
            data = json.loads(raw)

            logger.info(
                f"🤖 [AI] classification={data.get('classification')} "
                f"urgency={data.get('urgency')} | quota: {self.rate_limiter.status()['remaining']} left"
            )
            return data

        except Exception as e:
            logger.warning(f"⚠️ [AI] Analysis failed — using rule score: {e}")
            return None

    # ── Follow-up schedule ────────────────────────────────────────────────────

    def _compute_followup(self, classification: str) -> Optional[datetime]:
        hours = FOLLOWUP_HOURS.get(classification)
        return datetime.utcnow() + timedelta(hours=hours) if hours else None

    # ── Persist ───────────────────────────────────────────────────────────────

    async def _persist(
        self, lead_id: int, status: str, score: float, reasoning: str
    ) -> None:
        try:
            from core.db import update_lead_status, log_action, write_audit_log
            update_lead_status(
                lead_id, status,
                score=int(score * 100),
                notes=reasoning
            )
            log_action({
                "action_type":  "lead_scored",
                "entity":       "leads",
                "entity_id":    lead_id,
                "performed_by": "crm_agent",
                "result":       status,
                "details":      reasoning,
            })
            write_audit_log(
                action="lead_scored",
                entity="leads",
                entity_id=lead_id,
                performed_by="crm_agent",
                details=reasoning,
            )
        except Exception as e:
            logger.warning(f"⚠️ [LeadWorkflow] DB persist failed for lead #{lead_id}: {e}")

    # ── Next action hint ──────────────────────────────────────────────────────

    def _get_next_action(self, classification: str, source: str) -> str:
        actions = {
            "hot":  "📞 اتصل فوراً — جهّز عرض سعر مخصص وحدد موعد demo خلال 24 ساعة.",
            "warm": "📧 ابعت إيميل ترحيب مخصص مع case study. حدد discovery call خلال 3 أيام.",
            "cold": "📨 أضف للـ nurture sequence. ابعت محتوى تعليمي كل أسبوع.",
        }
        action = actions.get(classification, "📋 راجع البيانات وحدد الخطوة التالية.")
        if source == "referral" and classification != "hot":
            action = "⭐ Referral lead — أعطه أولوية أعلى. " + action
        return action

    # ── Public stats (للـ dashboard) ─────────────────────────────────────────

    @staticmethod
    def get_stats() -> dict:
        return {
            "rate_limiter": _rate_limiter.status(),
            "cache":        _cache.stats(),
        }