"""
🔄 Finance Feedback Loop — v2.1 (Node API migration — DISABLED)
===================================================================
File: app/core/feedback_loop.py

⚠️ الملف ده بالكامل معطّل مؤقتاً (no-op) بعد التحول من MongoDB مباشر
لـ Node.js API. كل الدوال هنا كانت مبنية على:
    - db.db["ai_feedback"] / db.db["ai_accuracy_metrics"]  (Motor collections مباشرة)
    - db.decisions.aggregate(pipeline)  مع $lookup على invoices

الحاجات دي مفيهاش endpoint مكافئ في Node API دلوقتي (مفيش
/finance/feedback ولا /finance/accuracy-metrics). محاولة تشغيلها زي
ما هي هترمي AttributeError فوراً لأن NodeFinanceProxy معندهاش .db[...]
ولا .decisions كـ Motor collections حقيقية.

القرار الحالي: كل الدوال بترجع قيم فاضية/آمنة (no-op) بدل ما تكسر.
job_run_feedback_loop() لسه ممكن تتسجل في الـ scheduler من غير خطر —
هتعمل log بسيط وترجع فوراً.

لما تتعمل endpoints في Node تغطي:
    - POST/GET /finance/feedback         (ai_feedback collection)
    - POST/GET /finance/accuracy-metrics (ai_accuracy_metrics collection)
ارجع فعّل المنطق الأصلي (OUTCOME_MATRIX + _classify_outcome لسه محفوظين
تحت) وابنيه فوق NodeAPIClient بدل Motor مباشرة.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional


logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Outcome Rules — لسه محفوظة للرجوع ليها لما نفعّل المنطق تاني ─────────────

OUTCOME_MATRIX: dict[str, dict[str, str]] = {
    "safe_to_collect": {
        "paid":        "correct",
        "overdue":     "wrong",
        "legal":       "wrong",
        "written_off": "wrong",
        "partial":     "partial",
    },
    "soft_follow_up": {
        "paid":         "correct",
        "partial":      "partial",
        "overdue":      "wrong",
        "legal":        "wrong",
        "written_off":  "wrong",
        "payment_plan": "partial",
        "suspended":    "neutral",
    },
    "hard_follow_up": {
        "paid":         "correct",
        "payment_plan": "correct",
        "partial":      "partial",
        "legal":        "neutral",
        "suspended":    "neutral",
        "overdue":      "wrong",
        "written_off":  "wrong",
    },
    "payment_plan": {
        "paid":         "correct",
        "payment_plan": "correct",
        "partial":      "partial",
        "overdue":      "wrong",
        "legal":        "wrong",
        "written_off":  "wrong",
    },
    "suspend_service": {
        "paid":         "correct",
        "payment_plan": "correct",
        "legal":        "neutral",
        "suspended":    "neutral",
        "written_off":  "wrong",
        "overdue":      "wrong",
    },
    "legal_escalation": {
        "legal":       "neutral",
        "paid":        "correct",
        "written_off": "neutral",
        "overdue":     "wrong",
        "suspended":   "neutral",
    },
    "write_off": {
        "written_off": "correct",
        "paid":        "wrong",
        "legal":       "neutral",
        "overdue":     "neutral",
    },
    "on_hold_disputed": {
        "disputed": "correct",
        "paid":     "correct",
        "overdue":  "neutral",
        "legal":    "neutral",
    },
}


def _classify_outcome(decision: str, actual_status: str, days_elapsed: int) -> str:
    matrix  = OUTCOME_MATRIX.get(decision, {})
    outcome = matrix.get(actual_status, "unknown")
    if outcome == "neutral" and actual_status == "overdue" and days_elapsed >= 30:
        outcome = "wrong"
    return outcome


# ═════════════════════════════════════════════════════════════════════════════
# ⏰  SCHEDULER JOB — no-op (Node API migration)
# ═════════════════════════════════════════════════════════════════════════════

async def job_run_feedback_loop() -> None:
    """
    ⚠️ معطّلة مؤقتاً (Node API migration) — مفيش endpoint في Node يوفّر
    قراءة/كتابة ai_feedback أو ai_accuracy_metrics. الجوب ده no-op دلوقتي.
    آمن تسيبه مسجّل في الـ scheduler — مش هيعمل أي حاجة غير log.
    """
    logger.debug("⏭️ [FeedbackLoop] job_run_feedback_loop skipped — no Node endpoint yet")
    return


# ═════════════════════════════════════════════════════════════════════════════
# 📊  ACCURACY SUMMARY — for dashboard/API — no-op (Node API migration)
# ═════════════════════════════════════════════════════════════════════════════

async def get_accuracy_summary(days: int = 30) -> dict:
    """
    ⚠️ معطّلة مؤقتاً (Node API migration) — مفيش endpoint في Node يوفّر
    ai_accuracy_metrics. بترجع structure فاضية بنفس الشكل المتوقع من
    الـ caller (عشان أي كود بيقرا .get("overall")/.get("by_decision")
    مايكسرش).
    """
    logger.debug("⏭️ [FeedbackLoop] get_accuracy_summary skipped — no Node endpoint yet")
    return {
        "period_days": days,
        "overall":     {},
        "by_decision": [],
        "as_of":       _utcnow().isoformat() + "Z",
        "status":      "disabled",
        "reason":      "Node API migration — /finance/feedback endpoint not available yet",
    }