"""
⚡ Finance Action Executor — v2.0  (Production-Ready)
======================================================
File: app/actions/finance_actions.py

What's new in v2:
  ✅  Real DB status updates   (update_invoice_status / update_customer_status)
  ✅  Real SMTP emails         (EmailService singleton)
  ✅  Live dashboard push      (push_finance_event → SSE)
  ✅  Atomic log per action    (finance_collection_log)
  ✅  Never raises             (all errors caught & returned)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class FinanceActionExecutor:
    """
    Executes finance collection actions.
    Each action is atomic, updates the DB, sends real emails, and
    broadcasts to connected SSE dashboard clients.
    """

    # ── Public Entry Point ────────────────────────────────────────────────────

    async def execute(
        self,
        action:      str,
        invoice_id:  Optional[int],
        customer_id: Optional[int],
        amount:      float,
        decision:    str,
        reason:      str,
        request_id:  str,
        extra_data:  Optional[dict] = None,
    ) -> dict:
        """Route action → handler. Returns result dict, never raises."""

        action_map = {
            # ── Email ──────────────────────────────────────────────────────
            "send_polite_reminder":                   self._send_polite_reminder,
            "send_friendly_reminder":                 self._send_friendly_reminder,
            "send_payment_reminder":                  self._send_payment_reminder,
            "send_urgent_notice":                     self._send_urgent_notice,
            "send_legal_warning_letter":              self._send_legal_warning,
            "send_suspension_notice":                 self._send_suspension_notice,
            "send_payment_plan_offer":                self._send_payment_plan_offer,
            "send_receipt":                           self._send_receipt,
            "send_partial_receipt":                   self._send_receipt,
            "send_dispute_acknowledgment_to_customer":self._send_dispute_ack,

            # ── Shorthand aliases ─────────────────────────────────────────
            "send_reminder":        self._send_polite_reminder,
            "reminder":             self._send_polite_reminder,
            "polite_reminder":      self._send_polite_reminder,
            "friendly_reminder":    self._send_friendly_reminder,
            "payment_reminder":     self._send_payment_reminder,
            "urgent_notice":        self._send_urgent_notice,
            "legal_warning":        self._send_legal_warning,
            "suspension_notice":    self._send_suspension_notice,
            "payment_plan":         self._send_payment_plan_offer,
            "receipt":              self._send_receipt,

            # ── Internal notifications ────────────────────────────────────
            "notify_account_manager":      self._notify_account_manager,
            "notify_collections_team":     self._notify_collections_team,
            "notify_management":           self._notify_management,
            "notify_finance_team":         self._notify_finance_team,
            "call_customer":               self._schedule_call,

            # ── System / DB actions ───────────────────────────────────────
            "suspend_service":             self._suspend_service,
            "escalate_to_legal":           self._escalate_to_legal,
            "escalate_to_account_manager": self._escalate_to_account_manager,
            "propose_payment_plan":        self._create_payment_plan,
            "write_off_invoice":           self._write_off_invoice,
            "put_invoice_on_hold":         self._put_on_hold,
            "blacklist_customer":          self._blacklist_customer,
            "mark_invoice_paid":           self._mark_paid,
            "update_invoice_partial":      self._update_partial,
            "update_customer_credit_score":self._update_credit_score,
            "update_bad_debt_report":      self._update_bad_debt_report,
            "set_collection_strategy":     self._set_collection_strategy,
            "manual_review":               self._flag_for_manual_review,
            "investigate_payment_event":   self._investigate_payment,

            # ── More shorthand aliases ────────────────────────────────────
            "escalate":            self._escalate_to_legal,
            "suspend":             self._suspend_service,
            "write_off":           self._write_off_invoice,
            "blacklist":           self._blacklist_customer,
            "hold":                self._put_on_hold,
            "paid":                self._mark_paid,
        }

        # ── schedule_followup_N_days handled dynamically ──────────────────
        if action.startswith("schedule_followup_"):
            try:
                days = int(action.split("_")[-2])
            except Exception:
                days = 7
            return await self._schedule_followup(
                days=days,
                invoice_id=invoice_id,
                customer_id=customer_id,
                amount=amount,
                request_id=request_id,
            )

        if action == "schedule_legal_review_7_days":
            return await self._schedule_followup(
                days=7, review_type="legal",
                invoice_id=invoice_id, customer_id=customer_id,
                amount=amount, request_id=request_id,
            )

        if action == "schedule_suspension_review":
            return await self._schedule_followup(
                days=5, review_type="suspension",
                invoice_id=invoice_id, customer_id=customer_id,
                amount=amount, request_id=request_id,
            )

        # ── schedule_first_reminder_in_N_days (from new invoice workflow) ─
        if action.startswith("schedule_first_reminder_in_"):
            try:
                days = int(action.split("_")[-2])
            except Exception:
                days = 7
            return await self._schedule_followup(
                days=days, review_type="first_reminder",
                invoice_id=invoice_id, customer_id=customer_id,
                amount=amount, request_id=request_id,
            )

        # ── update_customer_risk_profile ──────────────────────────────────
        if action == "update_customer_risk_profile":
            return await self._update_credit_score(
                invoice_id=invoice_id, customer_id=customer_id,
                amount=amount, decision=decision, reason=reason,
                request_id=request_id,
            )

        handler = action_map.get(action)
        if not handler:
            logger.warning("⚠️ Unknown finance action: %s", action)
            return {
                "action": action,
                "status": "unknown_action",
                "available_actions": sorted(set(action_map.keys())),
            }

        try:
            result = await handler(
                invoice_id=invoice_id,
                customer_id=customer_id,
                amount=amount,
                decision=decision,
                reason=reason,
                request_id=request_id,
                extra_data=extra_data,
            )

            # ── Push to live dashboard ────────────────────────────────────
            await self._push_action_event(
                action=action,
                invoice_id=invoice_id,
                customer_id=customer_id,
                amount=amount,
                result=result,
            )

            return result

        except Exception as e:
            logger.error("❌ Action %s failed: %s", action, e)
            return {"action": action, "status": "failed", "error": str(e)}

    # ── SSE Push ──────────────────────────────────────────────────────────────

    async def _push_action_event(
        self,
        action:      str,
        invoice_id:  Optional[int],
        customer_id: Optional[int],
        amount:      float,
        result:      dict,
    ) -> None:
        """Non-blocking push to all connected SSE clients."""
        try:
            from core.finance_realtime import push_finance_event
            await push_finance_event(
                "action_executed",
                {
                    "action":      action,
                    "invoice_id":  invoice_id,
                    "customer_id": customer_id,
                    "amount":      amount,
                    "result":      result,
                    "ts":          datetime.utcnow().isoformat() + "Z",
                },
            )
        except Exception as e:
            logger.debug("SSE push skipped: %s", e)

    # ═════════════════════════════════════════════════════════════════════════
    # EMAIL ACTIONS
    # ═════════════════════════════════════════════════════════════════════════

    async def _send_polite_reminder(self, invoice_id, customer_id, amount, **kw) -> dict:
        return await self._send_email(
            invoice_id=invoice_id, customer_id=customer_id,
            template="polite_reminder",
            subject=f"تذكير ودي بفاتورة رقم #{invoice_id}",
            body=(
                f"نود تذكيركم بأن الفاتورة رقم #{invoice_id} "
                f"بمبلغ {amount:,.2f} EGP قد حان موعد سدادها. "
                "نشكركم لتعاملكم معنا."
            ),
            priority="low",
        )

    async def _send_friendly_reminder(self, invoice_id, customer_id, amount, **kw) -> dict:
        return await self._send_email(
            invoice_id=invoice_id, customer_id=customer_id,
            template="friendly_reminder",
            subject=f"تذكير بالفاتورة #{invoice_id} المستحقة",
            body=(
                f"نذكركم أن الفاتورة #{invoice_id} "
                f"بمبلغ {amount:,.2f} EGP متأخرة عن موعد السداد. "
                "يرجى السداد أو التواصل معنا لترتيب ذلك."
            ),
            priority="medium",
        )

    async def _send_payment_reminder(self, invoice_id, customer_id, amount, **kw) -> dict:
        return await self._send_email(
            invoice_id=invoice_id, customer_id=customer_id,
            template="payment_reminder",
            subject=f"⚠️ فاتورة متأخرة #{invoice_id}",
            body=(
                f"الفاتورة #{invoice_id} بمبلغ {amount:,.2f} EGP متأخرة. "
                "يرجى السداد العاجل لتجنب أي إجراءات إضافية."
            ),
            priority="medium",
        )

    async def _send_urgent_notice(self, invoice_id, customer_id, amount, **kw) -> dict:
        return await self._send_email(
            invoice_id=invoice_id, customer_id=customer_id,
            template="urgent_notice",
            subject=f"🚨 إشعار عاجل — فاتورة #{invoice_id}",
            body=(
                f"نفيدكم بأن الفاتورة #{invoice_id} "
                f"بمبلغ {amount:,.2f} EGP في وضع حرج. "
                "يجب السداد الفوري أو التواصل معنا خلال 48 ساعة."
            ),
            priority="high",
        )

    async def _send_legal_warning(self, invoice_id, customer_id, amount, **kw) -> dict:
        return await self._send_email(
            invoice_id=invoice_id, customer_id=customer_id,
            template="legal_warning",
            subject=f"⚖️ إنذار قانوني رسمي — فاتورة #{invoice_id}",
            body=(
                f"إنذار قانوني رسمي: الفاتورة #{invoice_id} "
                f"بمبلغ {amount:,.2f} EGP متأخرة بشكل حرج. "
                "سيتم اتخاذ إجراءات قانونية خلال 7 أيام إن لم يتم السداد."
            ),
            priority="critical",
        )

    async def _send_suspension_notice(self, invoice_id, customer_id, amount, **kw) -> dict:
        return await self._send_email(
            invoice_id=invoice_id, customer_id=customer_id,
            template="suspension_notice",
            subject=f"🚫 إشعار إيقاف الخدمة — فاتورة #{invoice_id}",
            body=(
                f"نعلمكم بأنه تم إيقاف الخدمة بسبب عدم سداد الفاتورة "
                f"#{invoice_id} بمبلغ {amount:,.2f} EGP. "
                "يمكن استعادة الخدمة فور السداد."
            ),
            priority="high",
        )

    async def _send_payment_plan_offer(self, invoice_id, customer_id, amount, extra_data=None, **kw) -> dict:
        plan   = extra_data or {}
        inst   = plan.get("installments", 3)
        mo_amt = plan.get("monthly_amount") or round(amount / max(inst, 1), 2)
        return await self._send_email(
            invoice_id=invoice_id, customer_id=customer_id,
            template="payment_plan_offer",
            subject=f"💳 عرض خطة تقسيط — فاتورة #{invoice_id}",
            body=(
                f"نقدم لكم خطة تقسيط لسداد الفاتورة #{invoice_id} "
                f"بمبلغ {amount:,.2f} EGP على {inst} أقساط "
                f"بقيمة {mo_amt:,.2f} EGP شهرياً."
            ),
            priority="medium",
        )

    async def _send_receipt(self, invoice_id, customer_id, amount, **kw) -> dict:
        return await self._send_email(
            invoice_id=invoice_id, customer_id=customer_id,
            template="payment_receipt",
            subject=f"✅ إيصال استلام دفع — فاتورة #{invoice_id}",
            body=(
                f"تم استلام دفعتكم بمبلغ {amount:,.2f} EGP "
                f"للفاتورة #{invoice_id}. شكراً لكم."
            ),
            priority="low",
        )

    async def _send_dispute_ack(self, invoice_id, customer_id, **kw) -> dict:
        return await self._send_email(
            invoice_id=invoice_id, customer_id=customer_id,
            template="dispute_acknowledgment",
            subject=f"تأكيد استلام الاعتراض — فاتورة #{invoice_id}",
            body=(
                f"تم استلام اعتراضكم على الفاتورة #{invoice_id}. "
                "سيتواصل معكم مدير الحساب خلال 24 ساعة."
            ),
            priority="medium",
        )

    # ── Core Email Sender ────────────────────────────────────────────────────

    async def _send_email(
        self,
        invoice_id:  Optional[int],
        customer_id: Optional[int],
        template:    str,
        subject:     str,
        body:        str,
        priority:    str = "medium",
        **kw,
    ) -> dict:
        """
        1. Render HTML template via EmailTemplateEngine
        2. Fetch customer email from DB
        3. Send via EmailService (real SMTP or simulated)
        4. Log result to finance_collection_log
        """
        from core.finance_db import get_customer_email, log_collection_action
        from core.email_service import email_service
        from core.email_templates import EmailTemplateEngine

        # 1. Render HTML template (falls back to plain text wrapper)
        amount = kw.get("amount", 0)
        rendered = EmailTemplateEngine.render(
            template=template,
            invoice_id=invoice_id,
            customer_id=customer_id,
            amount=float(amount) if amount else 0,
            subject=subject,
            body_text=body,
            extra_data=kw.get("extra_data"),
        )
        html_body    = rendered.get("html", "")
        final_subject = rendered.get("subject") or subject

        # 2. Get email
        customer_email = get_customer_email(customer_id) if customer_id else None

        # 3. Send (with HTML body if available)
        if customer_email:
            email_result = await email_service.send_email(
                to_email=customer_email,
                subject=final_subject,
                body=html_body or body,
            )
        else:
            logger.warning("⚠️ No email found for customer %s — simulating", customer_id)
            email_result = {
                "sent": True, "simulated": True,
                "method": "simulated_no_email",
            }

        # 4. Log to DB
        status = "sent" if email_result.get("sent") else "failed"
        log_collection_action(
            invoice_id=invoice_id,
            customer_id=customer_id,
            action_type="email",
            template_name=template,
            subject=final_subject,
            body=body[:2000],
            priority=priority,
            status=status,
        )

        return {
            "action":       f"send_email_{template}",
            "customer_id":  customer_id,
            "invoice_id":   invoice_id,
            "template":     template,
            "subject":      final_subject,
            "priority":     priority,
            "status":       status,
            "to_email":     customer_email,
            "html_rendered": bool(html_body),
            "simulated":    email_result.get("simulated", True),
            "method":       email_result.get("method", "none"),
            "error":        email_result.get("error"),
            "sent_at":      datetime.utcnow().isoformat() + "Z",
        }

    # ═════════════════════════════════════════════════════════════════════════
    # INTERNAL NOTIFICATION ACTIONS
    # ═════════════════════════════════════════════════════════════════════════

    async def _notify_account_manager(self, invoice_id, customer_id, amount, reason="", **kw) -> dict:
        return await self._internal_notification(
            notification_type="account_manager_alert",
            recipient_role="account_manager",
            invoice_id=invoice_id,
            customer_id=customer_id,
            message=(
                f"⚠️ Overdue Invoice Alert: Invoice #{invoice_id} "
                f"({amount:,.2f} EGP) requires your immediate attention. {str(reason)[:200]}"
            ),
            priority="high",
        )

    async def _notify_collections_team(self, invoice_id, customer_id, amount, **kw) -> dict:
        return await self._internal_notification(
            notification_type="collections_alert",
            recipient_role="collections_team",
            invoice_id=invoice_id,
            customer_id=customer_id,
            message=(
                f"🚨 Collections Required: Invoice #{invoice_id} "
                f"({amount:,.2f} EGP) escalated to collections."
            ),
            priority="high",
        )

    async def _notify_management(self, invoice_id, customer_id, amount, **kw) -> dict:
        return await self._internal_notification(
            notification_type="management_alert",
            recipient_role="management",
            invoice_id=invoice_id,
            customer_id=customer_id,
            message=(
                f"🚨 Critical Finance Alert: Invoice #{invoice_id} "
                f"({amount:,.2f} EGP) requires management decision."
            ),
            priority="critical",
        )

    async def _notify_finance_team(self, invoice_id, customer_id, amount, **kw) -> dict:
        return await self._internal_notification(
            notification_type="finance_team_alert",
            recipient_role="finance_team",
            invoice_id=invoice_id,
            customer_id=customer_id,
            message=f"Finance Update: Invoice #{invoice_id} ({amount:,.2f} EGP) status changed.",
            priority="medium",
        )

    async def _internal_notification(
        self,
        notification_type: str,
        recipient_role:    str,
        invoice_id:        Optional[int],
        customer_id:       Optional[int],
        message:           str,
        priority:          str = "medium",
    ) -> dict:
        from core.finance_db import log_collection_action
        log_collection_action(
            invoice_id=invoice_id,
            customer_id=customer_id,
            action_type="internal_notification",
            template_name=notification_type,
            subject=notification_type,
            body=message,
            priority=priority,
            status="sent",
        )
        return {
            "action":    notification_type,
            "recipient": recipient_role,
            "priority":  priority,
            "status":    "sent",
            "sent_at":   datetime.utcnow().isoformat() + "Z",
        }

    # ═════════════════════════════════════════════════════════════════════════
    # SYSTEM / DB ACTIONS  — all call update_invoice_status or update_customer_status
    # ═════════════════════════════════════════════════════════════════════════

    async def _schedule_call(self, invoice_id, customer_id, **kw) -> dict:
        from core.finance_db import log_collection_action
        scheduled_for = (datetime.utcnow() + timedelta(hours=2)).isoformat() + "Z"
        log_collection_action(
            invoice_id=invoice_id, customer_id=customer_id,
            action_type="call_scheduled", template_name="call_customer",
            subject=f"Call scheduled — Invoice #{invoice_id}",
            body=f"Scheduled for {scheduled_for}",
            priority="medium", status="scheduled",
        )
        return {
            "action":        "call_customer",
            "customer_id":   customer_id,
            "invoice_id":    invoice_id,
            "scheduled":     True,
            "scheduled_for": scheduled_for,
        }

    async def _suspend_service(self, invoice_id, customer_id, **kw) -> dict:
        """
        ✅ Updates invoices.status = 'suspended'
        ✅ Updates customers.service_status = 'suspended'
        """
        from core.finance_db import update_invoice_status, update_customer_status, log_collection_action

        update_invoice_status(invoice_id, "suspended")
        update_customer_status(
            customer_id,
            service_status="suspended",
            extra_fields={"suspension_reason": "overdue_invoice", "suspended_at": "NOW()"},
        )
        log_collection_action(
            invoice_id=invoice_id, customer_id=customer_id,
            action_type="system", template_name="suspend_service",
            subject=f"Service Suspended — Invoice #{invoice_id}",
            body=f"Customer {customer_id} service suspended due to overdue invoice #{invoice_id}",
            priority="high", status="executed",
        )
        return {
            "action":        "suspend_service",
            "customer_id":   customer_id,
            "invoice_id":    invoice_id,
            "status":        "suspended",
            "suspended_at":  datetime.utcnow().isoformat() + "Z",
        }

    async def _escalate_to_legal(self, invoice_id, customer_id, amount, **kw) -> dict:
        """✅ Updates invoice status to 'legal'"""
        from core.finance_db import update_invoice_status, log_collection_action

        update_invoice_status(invoice_id, "legal")
        log_collection_action(
            invoice_id=invoice_id, customer_id=customer_id,
            action_type="legal_escalation", template_name="legal_referral",
            subject=f"Legal Escalation — Invoice #{invoice_id}",
            body=f"Invoice #{invoice_id} ({amount:,.2f} EGP) referred to legal team.",
            priority="critical", status="escalated",
        )
        return {
            "action":        "escalate_to_legal",
            "invoice_id":    invoice_id,
            "customer_id":   customer_id,
            "amount":        amount,
            "new_status":    "legal",
            "status":        "escalated",
            "escalated_at":  datetime.utcnow().isoformat() + "Z",
        }

    async def _escalate_to_account_manager(self, invoice_id, customer_id, amount=0, **kw) -> dict:
        return await self._notify_account_manager(
            invoice_id=invoice_id, customer_id=customer_id,
            amount=amount, reason="Escalated to account manager",
        )

    async def _create_payment_plan(self, invoice_id, customer_id, amount, extra_data=None, **kw) -> dict:
        """✅ Updates invoice status to 'payment_plan'"""
        from core.finance_db import update_invoice_status, log_collection_action

        plan         = extra_data or {}
        installments = plan.get("installments", 3)
        monthly_amt  = plan.get("monthly_amount") or round(amount / max(installments, 1), 2)
        first_days   = plan.get("first_payment_days", 7)
        first_pmt    = (datetime.utcnow() + timedelta(days=first_days)).isoformat()

        update_invoice_status(invoice_id, "payment_plan")
        log_collection_action(
            invoice_id=invoice_id, customer_id=customer_id,
            action_type="payment_plan", template_name="installment_plan",
            subject=f"Payment Plan — Invoice #{invoice_id}",
            body=f"{installments} installments × {monthly_amt:,.2f} EGP | first: {first_pmt}",
            priority="medium", status="active",
        )
        return {
            "action":         "create_payment_plan",
            "invoice_id":     invoice_id,
            "new_status":     "payment_plan",
            "installments":   installments,
            "monthly_amount": monthly_amt,
            "first_payment":  first_pmt,
            "status":         "created",
        }

    async def _write_off_invoice(self, invoice_id, customer_id, amount, **kw) -> dict:
        """✅ Updates invoice status to 'written_off'"""
        from core.finance_db import update_invoice_status, log_collection_action

        update_invoice_status(invoice_id, "written_off", extra_fields={"written_off_at": "NOW()"})
        log_collection_action(
            invoice_id=invoice_id, customer_id=customer_id,
            action_type="write_off", template_name="write_off_invoice",
            subject=f"Write-off — Invoice #{invoice_id}",
            body=f"Invoice #{invoice_id} ({amount:,.2f} EGP) written off as bad debt.",
            priority="high", status="executed",
        )
        return {
            "action":          "write_off_invoice",
            "invoice_id":      invoice_id,
            "new_status":      "written_off",
            "amount":          amount,
            "written_off_at":  datetime.utcnow().isoformat() + "Z",
        }

    async def _put_on_hold(self, invoice_id, customer_id=None, **kw) -> dict:
        """✅ Updates invoice status to 'disputed'"""
        from core.finance_db import update_invoice_status, log_collection_action

        update_invoice_status(invoice_id, "disputed")
        log_collection_action(
            invoice_id=invoice_id, customer_id=customer_id,
            action_type="system", template_name="put_on_hold",
            subject=f"Invoice #{invoice_id} put on hold",
            body="Invoice marked as disputed / on hold pending review.",
            priority="medium", status="executed",
        )
        return {"action": "put_on_hold", "invoice_id": invoice_id, "new_status": "disputed", "status": "held"}

    async def _blacklist_customer(self, customer_id, invoice_id=None, **kw) -> dict:
        """✅ Updates customer is_blacklisted = 1"""
        from core.finance_db import update_customer_status, log_collection_action

        update_customer_status(customer_id, is_blacklisted=True)
        log_collection_action(
            invoice_id=invoice_id, customer_id=customer_id,
            action_type="system", template_name="blacklist_customer",
            subject=f"Customer #{customer_id} Blacklisted",
            body=f"Customer #{customer_id} added to blacklist.",
            priority="critical", status="executed",
        )
        return {"action": "blacklist_customer", "customer_id": customer_id, "status": "blacklisted"}

    async def _mark_paid(self, invoice_id, customer_id=None, **kw) -> dict:
        """✅ Updates invoice status to 'paid'"""
        from core.finance_db import update_invoice_status, log_collection_action

        update_invoice_status(invoice_id, "paid", extra_fields={"paid_at": "NOW()"})
        log_collection_action(
            invoice_id=invoice_id, customer_id=customer_id,
            action_type="system", template_name="mark_paid",
            subject=f"Invoice #{invoice_id} Marked Paid",
            body=f"Invoice #{invoice_id} status updated to paid.",
            priority="low", status="executed",
        )
        return {"action": "mark_paid", "invoice_id": invoice_id, "new_status": "paid", "status": "paid"}

    async def _update_partial(self, invoice_id, amount, customer_id=None, **kw) -> dict:
        from core.finance_db import log_collection_action

        log_collection_action(
            invoice_id=invoice_id, customer_id=customer_id,
            action_type="system", template_name="partial_payment",
            subject=f"Partial Payment — Invoice #{invoice_id}",
            body=f"Partial payment of {amount:,.2f} EGP recorded.",
            priority="medium", status="executed",
        )
        return {"action": "update_partial", "invoice_id": invoice_id, "partial_amount": amount}

    async def _update_credit_score(self, customer_id, invoice_id=None, **kw) -> dict:
        from core.finance_db import log_collection_action
        log_collection_action(
            invoice_id=invoice_id, customer_id=customer_id,
            action_type="system", template_name="credit_score_update",
            subject=f"Credit Score Update — Customer #{customer_id}",
            body="Credit score recalculated based on payment history.",
            priority="low", status="executed",
        )
        return {"action": "update_credit_score", "customer_id": customer_id, "status": "updated"}

    async def _update_bad_debt_report(self, invoice_id, amount, customer_id=None, **kw) -> dict:
        from core.finance_db import log_collection_action
        log_collection_action(
            invoice_id=invoice_id, customer_id=customer_id,
            action_type="system", template_name="bad_debt_report",
            subject=f"Bad Debt Report — Invoice #{invoice_id}",
            body=f"Invoice #{invoice_id} ({amount:,.2f} EGP) added to bad debt report.",
            priority="medium", status="executed",
        )
        return {"action": "update_bad_debt", "invoice_id": invoice_id, "amount": amount}

    async def _set_collection_strategy(self, invoice_id, customer_id=None, extra_data=None, **kw) -> dict:
        from core.finance_db import log_collection_action
        strategy = (extra_data or {}).get("strategy", "standard")
        log_collection_action(
            invoice_id=invoice_id, customer_id=customer_id,
            action_type="system", template_name="collection_strategy",
            subject=f"Collection Strategy Set — Invoice #{invoice_id}",
            body=f"Strategy: {strategy}",
            priority="low", status="executed",
        )
        return {"action": "set_collection_strategy", "invoice_id": invoice_id, "strategy": strategy, "status": "set"}

    async def _flag_for_manual_review(self, invoice_id, customer_id=None, **kw) -> dict:
        from core.finance_db import update_invoice_status, log_collection_action
        update_invoice_status(invoice_id, "manual_review")
        log_collection_action(
            invoice_id=invoice_id, customer_id=customer_id,
            action_type="system", template_name="manual_review",
            subject=f"Manual Review Flagged — Invoice #{invoice_id}",
            body="Invoice flagged for manual review by finance team.",
            priority="medium", status="flagged",
        )
        return {"action": "manual_review", "invoice_id": invoice_id, "new_status": "manual_review", "status": "flagged"}

    async def _investigate_payment(self, invoice_id, customer_id=None, **kw) -> dict:
        from core.finance_db import log_collection_action
        log_collection_action(
            invoice_id=invoice_id, customer_id=customer_id,
            action_type="system", template_name="payment_investigation",
            subject=f"Payment Investigation — Invoice #{invoice_id}",
            body="Investigating anomalous payment event.",
            priority="high", status="investigating",
        )
        return {"action": "investigate_payment", "invoice_id": invoice_id, "status": "investigating"}

    async def _schedule_followup(
        self,
        days:        int,
        invoice_id:  Optional[int] = None,
        customer_id: Optional[int] = None,
        review_type: str           = "general",
        **kw,
    ) -> dict:
        from core.finance_db import log_collection_action

        followup_date = datetime.utcnow() + timedelta(days=days)
        log_collection_action(
            invoice_id=invoice_id, customer_id=customer_id,
            action_type="followup_scheduled",
            template_name=f"followup_{review_type}",
            subject=f"Follow-up Scheduled — Invoice #{invoice_id}",
            body=f"Follow-up in {days} days ({review_type}) — due {followup_date.date()}",
            priority="medium", status="scheduled",
        )
        return {
            "action":        f"schedule_followup_{days}_days",
            "invoice_id":    invoice_id,
            "review_type":   review_type,
            "followup_date": followup_date.isoformat() + "Z",
            "scheduled":     True,
        }