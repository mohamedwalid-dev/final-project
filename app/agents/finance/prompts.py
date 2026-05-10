"""
💬 Finance Agent Prompts — v1.0
=================================
File: app/agents/finance/prompts.py

LLM prompt templates for invoice risk reasoning.
Using Gemini for nuanced collection strategy decisions.
"""

from __future__ import annotations


class FinancePromptBuilder:
    """Builds structured prompts for the Finance AI Agent."""

    @staticmethod
    def invoice_risk(data: dict, trace_id: str = "") -> str:
        """
        Prompt for overdue invoice risk assessment and collection decision.
        Returns a single combined prompt string.
        """
        invoice_id       = data.get("invoice_id", "N/A")
        customer_id      = data.get("customer_id", "N/A")
        customer_name    = data.get("customer_name", "Unknown Customer")
        amount           = float(data.get("amount", 0))
        overdue_days     = int(data.get("overdue_days", 0))
        risk_score       = float(data.get("risk_score", 0.5))
        payment_count    = int(data.get("payment_history_count", 0))
        paid_count       = int(data.get("payment_history_paid", 0))
        late_count       = int(data.get("payment_history_late", 0))
        customer_age_mo  = int(data.get("customer_age_months", 12))
        credit_score     = int(data.get("credit_score", 650))
        industry         = data.get("industry", "unknown")
        last_contact     = data.get("last_contact_date", "Never")
        has_dispute      = bool(data.get("is_disputed", False))
        payment_plan     = bool(data.get("has_payment_plan", False))
        notes            = data.get("collection_notes", "")
        currency         = "EGP"

        paid_ratio       = f"{paid_count}/{payment_count}" if payment_count else "No history"
        late_rate        = (
            f"{late_count/payment_count:.0%}"
            if payment_count else "N/A"
        )

        system_prompt = """أنت خبير مالي متخصص في إدارة المديونيات وتحصيل الفواتير لنظام ERP.

مهمتك: تحليل بيانات الفاتورة المتأخرة واتخاذ قرار تحصيل ذكي ومبرر.

القرارات المتاحة:
- safe_to_collect: العميل موثوق — متابعة عادية
- soft_follow_up: تذكير لطيف بالبريد الإلكتروني
- hard_follow_up: ضغط مباشر + تصعيد لمدير الحساب
- payment_plan: عرض خطة تقسيط مناسبة
- suspend_service: إيقاف الخدمة حتى السداد
- legal_escalation: تصعيد للفريق القانوني
- write_off: شطب الدين كديون معدومة

خطوات العمل المتاحة (action_plan):
- send_polite_reminder, send_friendly_reminder, send_payment_reminder
- send_urgent_notice, send_legal_warning_letter, send_suspension_notice
- call_customer, notify_account_manager, notify_collections_team
- propose_payment_plan, send_payment_plan_offer
- suspend_service, escalate_to_legal
- schedule_followup_3_days, schedule_followup_7_days, schedule_followup_14_days
- write_off_invoice, update_bad_debt_report

أعد JSON فقط بدون أي نص إضافي أو markdown."""

        human_prompt = f"""[Trace ID: {trace_id}]

بيانات الفاتورة:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• رقم الفاتورة:     {invoice_id}
• العميل:           {customer_name} (ID: {customer_id})
• المبلغ:           {amount:,.2f} {currency}
• أيام التأخير:     {overdue_days} يوم
• درجة المخاطرة (ML): {risk_score:.0%}

تاريخ الدفع:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• سجل الدفع:        {paid_ratio} فواتير مسددة
• معدل التأخير:     {late_rate}
• التواصل الأخير:   {last_contact}
• نزاع قائم:        {"نعم ⚠️" if has_dispute else "لا"}
• خطة تقسيط:        {"قائمة بالفعل" if payment_plan else "لا"}

بيانات العميل:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• عمر الحساب:       {customer_age_mo} شهر
• درجة الائتمان:    {credit_score}/850
• القطاع:           {industry}
• ملاحظات التحصيل:  {notes or "لا توجد"}

القرار المطلوب:
بناءً على هذه البيانات، ما هو أفضل إجراء للتحصيل؟

أعد JSON بالشكل التالي ONLY:
{{
  "decision": "<أحد القرارات المذكورة أعلاه>",
  "confidence": <0.0 - 1.0>,
  "risk_assessment": "<high|medium|low>",
  "reason": "<سبب مفصل للقرار بالعربي أو الإنجليزي>",
  "action_plan": ["<action1>", "<action2>", "<action3>"],
  "payment_plan_terms": {{
    "installments": <عدد الأقساط أو null>,
    "monthly_amount": <قيمة القسط أو null>,
    "first_payment_days": <أيام للقسط الأول أو null>
  }},
  "urgency": "<immediate|high|medium|low>",
  "flags": ["<ملاحظات مهمة>"]
}}"""

        return f"{system_prompt}\n\n{human_prompt}"

    @staticmethod
    def cashflow_forecast(data: dict, trace_id: str = "") -> str:
        """Prompt for cashflow forecasting analysis."""
        total_outstanding = float(data.get("total_outstanding", 0))
        invoices_due_7d   = float(data.get("invoices_due_7_days", 0))
        invoices_due_30d  = float(data.get("invoices_due_30_days", 0))
        high_risk_amount  = float(data.get("high_risk_amount", 0))
        month             = data.get("month", "current month")

        return f"""[Trace ID: {trace_id}]

أنت محلل مالي خبير. حلل وضع التدفق النقدي وقدم توقعات.

البيانات:
- إجمالي المستحقات: {total_outstanding:,.2f} EGP
- مستحق خلال 7 أيام: {invoices_due_7d:,.2f} EGP
- مستحق خلال 30 يوم: {invoices_due_30d:,.2f} EGP
- مبالغ عالية المخاطر: {high_risk_amount:,.2f} EGP
- الشهر: {month}

أعد JSON فقط:
{{
  "expected_collection_7d": <مبلغ متوقع التحصيل خلال 7 أيام>,
  "expected_collection_30d": <مبلغ متوقع التحصيل خلال 30 يوم>,
  "at_risk_amount": <مبلغ في خطر>,
  "collection_rate_forecast": <نسبة التحصيل المتوقعة 0-1>,
  "key_risks": ["<مخاطر>"],
  "recommendations": ["<توصيات>"],
  "urgency": "high|medium|low"
}}"""