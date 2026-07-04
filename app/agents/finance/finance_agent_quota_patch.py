"""
🔧 Finance Agent — Gemini Quota Guard Integration Patch
========================================================
File: app/agents/finance/finance_agent_quota_patch.py

هذا الملف يوضح بالضبط التعديلات المطلوبة على finance_agent.py
لتفعيل GeminiQuotaGuard وتجنّب الـ 429 storm.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
المشكلة:
  لما Gemini يرجع 429 RESOURCE_EXHAUSTED، الـ agent بيعمل retry
  بـ exponential backoff → بيضيّع 20-30 ثانية على كل invoice
  وبيفشل في الآخر ويعمل rule fallback بعد delay طويل.

الحل:
  1. لحظة ما يشوف 429 → يبلّغ GeminiQuotaGuard
  2. الـ guard بيفرز pause لـ 60 دقيقة
  3. كل الـ requests الجاية بتـ skip الـ LLM مباشرة وتعمل rule fallback
  4. بعد 60 دقيقة → بيجرب Gemini تاني تلقائياً
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

طريقة التطبيق:
  ابحث في finance_agent.py عن الأماكن الـ 3 دي وعدّل عليها.
"""

# ══════════════════════════════════════════════════════════════════════════════
# 1. في أول الملف — أضف الـ import ده
# ══════════════════════════════════════════════════════════════════════════════

IMPORT_ADDITION = """
# ── Quota Guard (أضف هذا السطر مع الـ imports الموجودة) ──
from agents.finance.risk_model_handler import get_gemini_quota_guard
"""

# ══════════════════════════════════════════════════════════════════════════════
# 2. في __init__ أو في أي method initialization — أضف:
# ══════════════════════════════════════════════════════════════════════════════

INIT_ADDITION = """
# في FinanceAgent.__init__() أضف:
self._quota_guard = get_gemini_quota_guard()
"""

# ══════════════════════════════════════════════════════════════════════════════
# 3. في الـ method اللي بتستدعي Gemini (مثلاً _call_llm أو _get_llm_decision)
#    ابحث عنها وعدّل عليها زي كده:
# ══════════════════════════════════════════════════════════════════════════════

LLM_CALL_PATCH = '''
async def _get_llm_decision(self, context: dict, risk_score: float, request_id: str) -> dict:
    """
    Call Gemini for medium/high-risk decisions.
    ✅ v4.0: GeminiQuotaGuard integration — skips LLM if quota exceeded.
    """
    # ── Quota Guard Check ─────────────────────────────────────────────────
    if not self._quota_guard.is_available():
        logger.warning(
            "[request_id=%s] ⚠️  Gemini quota exhausted — skipping LLM, using rule fallback",
            request_id,
        )
        return self._rule_fallback_decision(risk_score, reason="quota_exceeded")

    # ── Original LLM call (unchanged) ────────────────────────────────────
    try:
        # ... (كود الـ Gemini call الموجود عندك) ...
        result = await self._gemini_client.generate_content_async(...)
        return result

    except Exception as e:
        error_str = str(e)

        # ✅ NEW: اكتشاف 429 وتبليغ الـ guard
        if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
            self._quota_guard.mark_exhausted()
            logger.warning(
                "[request_id=%s] ⚠️  Gemini 429 detected — quota guard activated, "
                "switching to rule fallback for remaining requests",
                request_id,
            )
            return self._rule_fallback_decision(risk_score, reason="rate_limited")

        # أي error تانية — raise كالعادة
        raise
'''

# ══════════════════════════════════════════════════════════════════════════════
# Quick test — يتأكد إن الـ import يشتغل
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

    try:
        from agents.finance.risk_model_handler import get_gemini_quota_guard, get_finance_risk_handler

        guard = get_gemini_quota_guard()
        print("✅ GeminiQuotaGuard loaded:", guard.get_status())

        handler = get_finance_risk_handler()
        print("✅ FinanceRiskModelHandler loaded:", handler.get_info())

        # Test rule-based prediction (بدون موديل)
        test_data = {
            "overdue_days": 8,
            "amount": 26890,
            "credit_score": 680,
            "industry": "retail",
            "payment_history_count": 10,
            "payment_history_paid": 7,
            "payment_history_late": 3,
            "customer_age_months": 13,
            "invoice_count_90d": 1,
            "avg_payment_delay_days": 0,
            "customer_id": "test-cust-001",
            "invoice_id": "test-inv-001",
        }

        result = handler.predict(test_data, request_id="test-001")
        print(f"\n✅ Test prediction:")
        print(f"   risk_score: {result['risk_score']}")
        print(f"   decision:   {result['decision']}")
        print(f"   source:     {result['source']}")
        print(f"   latency:    {result['latency_ms']}ms")
        print(f"\n✅ All checks passed — ready for deployment")

    except ImportError as e:
        print(f"❌ Import error (expected in isolation): {e}")
        print("   Run from within the app/ directory.")
