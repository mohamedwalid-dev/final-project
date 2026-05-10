"""
📧 Email Template Engine — v1.0 Production
=============================================
File: app/core/email_templates.py

Professional HTML email templates for finance collection actions.
RTL Arabic layout with company branding.
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional


def _base_html(content: str, subject: str = "") -> str:
    """Wrap content in the base HTML email shell."""
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{subject}</title>
<style>
  body {{ margin:0; padding:0; background:#f4f6f9; font-family: 'Segoe UI', Tahoma, Arial, sans-serif; direction:rtl; }}
  .wrapper {{ max-width:600px; margin:0 auto; background:#ffffff; border-radius:12px; overflow:hidden; box-shadow:0 4px 24px rgba(0,0,0,0.08); }}
  .header {{ background:linear-gradient(135deg, #1e293b 0%, #0f172a 100%); padding:28px 32px; text-align:center; }}
  .header h1 {{ color:#ffffff; font-size:20px; margin:0 0 4px; font-weight:700; }}
  .header p {{ color:#94a3b8; font-size:12px; margin:0; }}
  .body {{ padding:32px; color:#1e293b; line-height:1.8; font-size:15px; }}
  .body h2 {{ font-size:18px; color:#0f172a; margin:0 0 16px; border-bottom:2px solid #e2e8f0; padding-bottom:8px; }}
  .highlight-box {{ background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:16px 20px; margin:16px 0; }}
  .highlight-box.urgent {{ background:#fef2f2; border-color:#fecaca; }}
  .highlight-box.legal {{ background:#fef2f2; border-color:#f87171; border-right:4px solid #ef4444; }}
  .highlight-box.success {{ background:#f0fdf4; border-color:#bbf7d0; }}
  .highlight-box.plan {{ background:#eff6ff; border-color:#bfdbfe; }}
  .amount {{ font-size:24px; font-weight:700; color:#0f172a; }}
  .amount span {{ font-size:14px; color:#64748b; font-weight:400; }}
  .cta-btn {{ display:inline-block; background:linear-gradient(135deg, #3b82f6, #2563eb); color:#ffffff !important; text-decoration:none; padding:12px 32px; border-radius:8px; font-weight:600; font-size:14px; margin:16px 0; }}
  .cta-btn.danger {{ background:linear-gradient(135deg, #ef4444, #dc2626); }}
  .footer {{ background:#f8fafc; padding:20px 32px; text-align:center; border-top:1px solid #e2e8f0; }}
  .footer p {{ color:#94a3b8; font-size:11px; margin:4px 0; line-height:1.6; }}
  .badge {{ display:inline-block; padding:4px 12px; border-radius:20px; font-size:12px; font-weight:600; }}
  .badge-danger {{ background:#fef2f2; color:#dc2626; }}
  .badge-warning {{ background:#fffbeb; color:#d97706; }}
  .badge-info {{ background:#eff6ff; color:#2563eb; }}
  .badge-success {{ background:#f0fdf4; color:#16a34a; }}
  .divider {{ height:1px; background:#e2e8f0; margin:20px 0; }}
  table.info {{ width:100%; border-collapse:collapse; margin:12px 0; }}
  table.info td {{ padding:8px 0; border-bottom:1px solid #f1f5f9; font-size:14px; }}
  table.info td:first-child {{ color:#64748b; width:40%; }}
  table.info td:last-child {{ font-weight:600; color:#0f172a; }}
</style>
</head>
<body>
<div class="wrapper">
  <div class="header">
    <h1>⚡ النظام المالي الذكي</h1>
    <p>AI Enterprise ERP — Finance Module</p>
  </div>
  <div class="body">
    {content}
  </div>
  <div class="footer">
    <p>هذا البريد تم إرساله تلقائياً من النظام المالي الذكي</p>
    <p>AI Enterprise ERP &copy; {datetime.utcnow().year} — جميع الحقوق محفوظة</p>
    <p style="color:#cbd5e1; font-size:10px; margin-top:8px;">
      إذا كنت تعتقد أنك تلقيت هذا البريد بالخطأ، يرجى التواصل مع إدارة الحسابات.
    </p>
  </div>
</div>
</body>
</html>"""


class EmailTemplateEngine:
    """Render HTML email templates for finance collection actions."""

    @staticmethod
    def render(
        template:    str,
        invoice_id:  Optional[int] = None,
        customer_id: Optional[int] = None,
        amount:      float         = 0,
        subject:     str           = "",
        body_text:   str           = "",
        extra_data:  Optional[dict] = None,
    ) -> dict:
        """
        Render a template → returns {"subject": str, "html": str, "text": str}.
        Falls back to plain text wrapper if template not found.
        """
        renderer = _TEMPLATES.get(template)
        if renderer:
            return renderer(
                invoice_id=invoice_id,
                customer_id=customer_id,
                amount=amount,
                subject=subject,
                body_text=body_text,
                extra_data=extra_data or {},
            )
        # Fallback: wrap plain text in HTML
        return {
            "subject": subject,
            "html": _base_html(f"<p>{body_text}</p>", subject),
            "text": body_text,
        }


def _fmt_amount(amount: float) -> str:
    """Format amount with commas."""
    return f"{amount:,.2f}"


def _render_polite_reminder(**kw) -> dict:
    inv = kw.get("invoice_id", "")
    amt = kw.get("amount", 0)
    content = f"""
    <h2>تذكير ودي بالسداد 💙</h2>
    <p>عميلنا العزيز،</p>
    <p>نود تذكيركم بأن الفاتورة التالية قد حان موعد سدادها:</p>
    <div class="highlight-box">
      <table class="info">
        <tr><td>رقم الفاتورة</td><td>#{inv}</td></tr>
        <tr><td>المبلغ المستحق</td><td><span class="amount">{_fmt_amount(amt)} <span>ج.م</span></span></td></tr>
      </table>
    </div>
    <p>نقدّر تعاملكم معنا ونأمل السداد في أقرب وقت ممكن.</p>
    <a href="#" class="cta-btn">💳 ادفع الآن</a>
    <div class="divider"></div>
    <p style="color:#94a3b8; font-size:13px;">إذا كنتم قد سددتم بالفعل، يرجى تجاهل هذا البريد.</p>
    """
    subj = f"تذكير ودي بفاتورة رقم #{inv}"
    return {"subject": subj, "html": _base_html(content, subj), "text": kw.get("body_text", "")}


def _render_friendly_reminder(**kw) -> dict:
    inv = kw.get("invoice_id", "")
    amt = kw.get("amount", 0)
    content = f"""
    <h2>تذكير بالفاتورة المستحقة ⏰</h2>
    <p>عميلنا الكريم،</p>
    <p>نذكركم بأن الفاتورة رقم <strong>#{inv}</strong> بمبلغ <strong>{_fmt_amount(amt)} ج.م</strong>
    متأخرة عن موعد السداد المحدد.</p>
    <div class="highlight-box">
      <p>يرجى السداد في أقرب فرصة أو التواصل معنا لترتيب ذلك.</p>
    </div>
    <a href="#" class="cta-btn">💳 ادفع الآن</a>
    <p style="color:#94a3b8; font-size:13px;">لأي استفسار، لا تترددوا في التواصل مع مدير حسابكم.</p>
    """
    subj = f"تذكير بالفاتورة #{inv} المستحقة"
    return {"subject": subj, "html": _base_html(content, subj), "text": kw.get("body_text", "")}


def _render_payment_reminder(**kw) -> dict:
    inv = kw.get("invoice_id", "")
    amt = kw.get("amount", 0)
    content = f"""
    <h2>⚠️ فاتورة متأخرة — يرجى السداد العاجل</h2>
    <p>عميلنا الكريم،</p>
    <div class="highlight-box urgent">
      <table class="info">
        <tr><td>رقم الفاتورة</td><td>#{inv}</td></tr>
        <tr><td>المبلغ المتأخر</td><td><span class="amount">{_fmt_amount(amt)} <span>ج.م</span></span></td></tr>
        <tr><td>الحالة</td><td><span class="badge badge-warning">متأخرة</span></td></tr>
      </table>
    </div>
    <p>يرجى السداد العاجل لتجنب أي إجراءات إضافية قد تشمل تعليق الخدمة.</p>
    <a href="#" class="cta-btn">💳 ادفع الآن</a>
    """
    subj = f"⚠️ فاتورة متأخرة #{inv}"
    return {"subject": subj, "html": _base_html(content, subj), "text": kw.get("body_text", "")}


def _render_urgent_notice(**kw) -> dict:
    inv = kw.get("invoice_id", "")
    amt = kw.get("amount", 0)
    content = f"""
    <h2>🚨 إشعار عاجل — مطلوب إجراء فوري</h2>
    <p>عميلنا الكريم،</p>
    <div class="highlight-box urgent">
      <p style="font-weight:700; color:#dc2626; font-size:16px;">هذا إشعار عاجل بخصوص فاتورتكم المتأخرة</p>
      <table class="info">
        <tr><td>رقم الفاتورة</td><td>#{inv}</td></tr>
        <tr><td>المبلغ المستحق</td><td><span class="amount">{_fmt_amount(amt)} <span>ج.م</span></span></td></tr>
        <tr><td>الحالة</td><td><span class="badge badge-danger">حرج</span></td></tr>
      </table>
    </div>
    <p><strong>يجب السداد الفوري أو التواصل معنا خلال 48 ساعة</strong> لتجنب إجراءات التحصيل الإلزامية
    والتي قد تشمل تعليق الخدمة والإحالة للشؤون القانونية.</p>
    <a href="#" class="cta-btn danger">⚡ ادفع فوراً</a>
    """
    subj = f"🚨 إشعار عاجل — فاتورة #{inv}"
    return {"subject": subj, "html": _base_html(content, subj), "text": kw.get("body_text", "")}


def _render_legal_warning(**kw) -> dict:
    inv = kw.get("invoice_id", "")
    amt = kw.get("amount", 0)
    content = f"""
    <h2>⚖️ إنذار قانوني رسمي</h2>
    <p>السيد / السيدة العميل،</p>
    <div class="highlight-box legal">
      <p style="font-weight:700; color:#dc2626;">إنذار قانوني — آخر فرصة للسداد</p>
      <table class="info">
        <tr><td>رقم الفاتورة</td><td>#{inv}</td></tr>
        <tr><td>المبلغ المستحق</td><td><span class="amount">{_fmt_amount(amt)} <span>ج.م</span></span></td></tr>
        <tr><td>الحالة</td><td><span class="badge badge-danger">إنذار قانوني</span></td></tr>
        <tr><td>المهلة المتبقية</td><td><strong>7 أيام عمل</strong></td></tr>
      </table>
    </div>
    <p>نعلمكم رسمياً بأنه في حالة عدم السداد خلال <strong>7 أيام عمل</strong> من تاريخ هذا الإنذار،
    سيتم اتخاذ الإجراءات القانونية اللازمة والتي تشمل:</p>
    <ul style="color:#64748b; padding-right:20px;">
      <li>رفع دعوى قضائية لتحصيل المبلغ المستحق</li>
      <li>المطالبة بالتعويض عن التأخير</li>
      <li>تحمّلكم كافة المصاريف القانونية</li>
    </ul>
    <a href="#" class="cta-btn danger">⚡ ادفع فوراً لتجنب الإجراءات القانونية</a>
    <div class="divider"></div>
    <p style="color:#94a3b8; font-size:12px;">
      هذا الإنذار يعتبر وثيقة رسمية ويمكن الاستناد إليه أمام الجهات القضائية.
    </p>
    """
    subj = f"⚖️ إنذار قانوني رسمي — فاتورة #{inv}"
    return {"subject": subj, "html": _base_html(content, subj), "text": kw.get("body_text", "")}


def _render_suspension_notice(**kw) -> dict:
    inv = kw.get("invoice_id", "")
    amt = kw.get("amount", 0)
    content = f"""
    <h2>🚫 إشعار إيقاف الخدمة</h2>
    <p>عميلنا الكريم،</p>
    <div class="highlight-box urgent">
      <p style="font-weight:700; color:#dc2626;">تم إيقاف خدمتكم بسبب عدم السداد</p>
      <table class="info">
        <tr><td>رقم الفاتورة</td><td>#{inv}</td></tr>
        <tr><td>المبلغ المستحق</td><td><span class="amount">{_fmt_amount(amt)} <span>ج.م</span></span></td></tr>
        <tr><td>الحالة</td><td><span class="badge badge-danger">موقوفة</span></td></tr>
      </table>
    </div>
    <p>نعلمكم بأنه تم إيقاف الخدمة المقدمة لكم نظراً لعدم سداد المبلغ المستحق.</p>
    <p><strong>يمكن استعادة الخدمة فور إتمام عملية السداد.</strong></p>
    <a href="#" class="cta-btn danger">💳 ادفع الآن لاستعادة الخدمة</a>
    """
    subj = f"🚫 إشعار إيقاف الخدمة — فاتورة #{inv}"
    return {"subject": subj, "html": _base_html(content, subj), "text": kw.get("body_text", "")}


def _render_payment_plan_offer(**kw) -> dict:
    inv = kw.get("invoice_id", "")
    amt = kw.get("amount", 0)
    extra = kw.get("extra_data", {})
    installments = extra.get("installments", 3)
    monthly = extra.get("monthly_amount") or round(amt / max(installments, 1), 2)
    content = f"""
    <h2>💳 عرض خطة تقسيط مخصصة</h2>
    <p>عميلنا العزيز،</p>
    <p>نقدم لكم خطة تقسيط مرنة لتسهيل سداد المبلغ المستحق:</p>
    <div class="highlight-box plan">
      <table class="info">
        <tr><td>رقم الفاتورة</td><td>#{inv}</td></tr>
        <tr><td>إجمالي المبلغ</td><td><span class="amount">{_fmt_amount(amt)} <span>ج.م</span></span></td></tr>
        <tr><td>عدد الأقساط</td><td><strong>{installments} أقساط شهرية</strong></td></tr>
        <tr><td>قيمة القسط</td><td><strong>{_fmt_amount(monthly)} ج.م / شهر</strong></td></tr>
      </table>
    </div>
    <p>للموافقة على خطة التقسيط، يرجى التواصل مع مدير حسابكم أو الضغط على الزر أدناه.</p>
    <a href="#" class="cta-btn">✅ أوافق على خطة التقسيط</a>
    """
    subj = f"💳 عرض خطة تقسيط — فاتورة #{inv}"
    return {"subject": subj, "html": _base_html(content, subj), "text": kw.get("body_text", "")}


def _render_payment_receipt(**kw) -> dict:
    inv = kw.get("invoice_id", "")
    amt = kw.get("amount", 0)
    content = f"""
    <h2>✅ إيصال استلام الدفع</h2>
    <p>عميلنا العزيز،</p>
    <div class="highlight-box success">
      <p style="font-weight:700; color:#16a34a; font-size:16px;">تم استلام دفعتكم بنجاح ✓</p>
      <table class="info">
        <tr><td>رقم الفاتورة</td><td>#{inv}</td></tr>
        <tr><td>المبلغ المستلم</td><td><span class="amount">{_fmt_amount(amt)} <span>ج.م</span></span></td></tr>
        <tr><td>التاريخ</td><td>{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}</td></tr>
        <tr><td>الحالة</td><td><span class="badge badge-success">مسدد ✓</span></td></tr>
      </table>
    </div>
    <p>شكراً لالتزامكم بالسداد. نقدّر تعاملكم معنا.</p>
    """
    subj = f"✅ إيصال استلام دفع — فاتورة #{inv}"
    return {"subject": subj, "html": _base_html(content, subj), "text": kw.get("body_text", "")}


def _render_dispute_ack(**kw) -> dict:
    inv = kw.get("invoice_id", "")
    content = f"""
    <h2>📋 تأكيد استلام الاعتراض</h2>
    <p>عميلنا الكريم،</p>
    <div class="highlight-box">
      <p>تم استلام اعتراضكم على الفاتورة رقم <strong>#{inv}</strong> بنجاح.</p>
      <table class="info">
        <tr><td>رقم الفاتورة</td><td>#{inv}</td></tr>
        <tr><td>الحالة</td><td><span class="badge badge-info">قيد المراجعة</span></td></tr>
      </table>
    </div>
    <p>سيتواصل معكم مدير الحساب المختص خلال <strong>24 ساعة عمل</strong> لمناقشة الاعتراض وتقديم الحل المناسب.</p>
    <p>خلال فترة المراجعة، تم تعليق جميع إجراءات التحصيل المتعلقة بهذه الفاتورة.</p>
    """
    subj = f"تأكيد استلام الاعتراض — فاتورة #{inv}"
    return {"subject": subj, "html": _base_html(content, subj), "text": kw.get("body_text", "")}


# Template registry
_TEMPLATES = {
    "polite_reminder":        _render_polite_reminder,
    "friendly_reminder":      _render_friendly_reminder,
    "payment_reminder":       _render_payment_reminder,
    "urgent_notice":          _render_urgent_notice,
    "legal_warning":          _render_legal_warning,
    "suspension_notice":      _render_suspension_notice,
    "payment_plan_offer":     _render_payment_plan_offer,
    "payment_receipt":        _render_payment_receipt,
    "dispute_acknowledgment": _render_dispute_ack,
}
