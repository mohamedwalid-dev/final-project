"""
🎯 HR Action Executor — v1.1
==============================
File: app/actions/hr_action_executor.py

الـ fix الأساسي للـ Bug 3:
    بعد كل قرار HR (leave / salary / incentive / absence / attendance)
    المفروض يتعمل action فعلي — email، escalation، payroll deduction، إلخ.

    الكود القديم: _persist() بيحفظ في MongoDB وبس — مفيش action.
    الكود الجديد: execute_post_decision() بيتكال بعد _persist() في كل workflow.

Actions per domain:
    Leave:
        approve   → send approval email + deduct balance (already done in workflow)
        reject    → send rejection email
        escalate  → notify HR manager + create escalation ticket

    Salary:
        approve_increment     → notify employee + notify payroll
        defer                 → send deferral email with next review date
        reject                → send rejection with reason
        escalate_to_director  → create director approval task + notify

    Incentive:
        approve_bonus         → notify employee + trigger payroll bonus run
        partial_bonus         → notify employee of partial amount
        deny_bonus            → send denial email
        escalate_to_ceo       → create CEO approval task

    Absence:
        written_warning       → generate and send warning letter
        formal_warning        → generate formal warning + HR signature flow
        escalate_to_hr_director → create urgent escalation ticket
        suspension_review     → notify legal + HR director

    Attendance:
        formal_warning        → generate warning letter
        escalate_to_hr_director → create urgent ticket
        counseling_session    → schedule counseling meeting

CHANGELOG (v1.1):
    - WARN 1 FIX: get_hr_action_executor() singleton was lazily
      constructed (check-then-create), which is not thread-safe — two
      threads could both see _executor_instance as None and both build a
      new HRActionExecutor. Fixed by constructing the singleton at
      MODULE IMPORT time instead of lazily. Python's import system holds
      a per-module lock during import, guaranteeing the module body runs
      exactly once even under concurrent imports from multiple threads —
      so this sidesteps the race entirely rather than patching it with a
      threading.Lock() double-checked-locking pattern (which is easy to
      get subtly wrong and unnecessary when module-level init is enough).
    - WARN 3 FIX: every handler used to fall back to a fabricated address
      (f"employee_{id}@company.com") when employee_email was missing from
      the payload, silently mailing a non-existent inbox. Replaced with
      _resolve_employee_email(), which returns None and logs a warning
      when the email is missing/blank — callers then skip the email
      action (recorded as a skipped action, not a fake "success") instead
      of pretending it was sent.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# 📬  NOTIFICATION SENDER (pluggable — swap with real email/Slack/Teams)
# ════════════════════════════════════════════════════════════════════════════

class NotificationSender:
    """
    Pluggable notification layer.
    In production: replace _send_email / _send_slack with real integrations.
    For now: logs the notification so the pipeline works end-to-end.
    """

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        cc: Optional[list[str]] = None,
        request_id: str = "",
    ) -> bool:
        logger.info(
            "[request_id=%s] 📧 EMAIL → %s | subject=%s | cc=%s",
            request_id, to, subject, cc or [],
        )
        # TODO: replace with real email sender
        # e.g. await sendgrid_client.send(to, subject, body, cc)
        return True

    async def create_task(
        self,
        assignee: str,
        title: str,
        description: str,
        priority: str = "high",
        due_hours: int = 24,
        request_id: str = "",
    ) -> str:
        task_id = f"task_{request_id[:8]}_{datetime.now().strftime('%H%M%S')}"
        logger.info(
            "[request_id=%s] 📋 TASK created → assignee=%s | title=%s | priority=%s | due=%dh",
            request_id, assignee, title, priority, due_hours,
        )
        # TODO: integrate with Jira / Asana / Monday / internal task system
        return task_id

    async def notify_payroll(
        self,
        employee_id: str,
        action: str,
        amount: float,
        effective_date: str,
        request_id: str = "",
    ) -> bool:
        logger.info(
            "[request_id=%s] 💰 PAYROLL notification → employee=%s | action=%s | amount=%.2f | date=%s",
            request_id, employee_id, action, amount, effective_date,
        )
        # TODO: integrate with payroll system (SAP / Oracle / custom)
        return True


# Module-level singleton — constructed once, at import time.
# See WARN 1 fix note above: this relies on the Python import system's
# per-module lock (CPython guarantees a module's top-level code runs
# exactly once, even if multiple threads import it concurrently) rather
# than a lazy check-then-create pattern.
_notification_sender = NotificationSender()


def get_notification_sender() -> NotificationSender:
    return _notification_sender


# ════════════════════════════════════════════════════════════════════════════
# 🎯  HR ACTION EXECUTOR
# ════════════════════════════════════════════════════════════════════════════

class HRActionExecutor:
    """
    Executes post-decision actions for all HR domains.

    Usage (in workflows after _persist()):
        executor = HRActionExecutor()
        await executor.execute_post_decision(
            domain="leave",
            decision="approve",
            result=validated,
            payload=payload,
            request_id=request_id,
        )
    """

    def __init__(self):
        self.notifier = get_notification_sender()

    # ── Email resolution helper (WARN 3 fix) ────────────────────────────────

    def _resolve_employee_email(
        self, payload: dict, request_id: str, context: str = "",
    ) -> Optional[str]:
        """
        Returns the employee's real email from the payload, or None if it's
        missing/blank.

        Previously, callers fell back to a fabricated address
        (f"employee_{id}@company.com") that almost certainly doesn't exist,
        silently "succeeding" while actually mailing nobody. Now: if the
        email isn't present, we log a warning and let the caller skip the
        email action explicitly, so it shows up in actions_failed/skipped
        instead of a false actions_executed entry.
        """
        email = (payload.get("employee_email") or "").strip()
        if not email:
            logger.warning(
                "[request_id=%s] ⚠️ [HRActionExecutor] No employee_email in "
                "payload for employee_id=%s%s — skipping email send instead "
                "of guessing an address.",
                request_id,
                payload.get("employee_id", "?"),
                f" ({context})" if context else "",
            )
            return None
        return email

    async def execute_post_decision(
        self,
        domain:     str,
        decision:   str,
        result:     dict,
        payload:    dict,
        request_id: str = "",
    ) -> dict:
        """
        Main entry point — routes to the correct domain action handler.

        Returns:
            dict with keys:
                actions_executed: list[str]
                actions_failed:   list[str]
                notifications_sent: int
        """
        logger.info(
            "[request_id=%s] 🎯 [HRActionExecutor] domain=%s | decision=%s",
            request_id, domain, decision,
        )

        actions_executed = []
        actions_failed   = []

        try:
            if domain == "leave":
                executed, failed = await self._handle_leave(decision, result, payload, request_id)
            elif domain == "salary":
                executed, failed = await self._handle_salary(decision, result, payload, request_id)
            elif domain == "incentive":
                executed, failed = await self._handle_incentive(decision, result, payload, request_id)
            elif domain == "absence":
                executed, failed = await self._handle_absence(decision, result, payload, request_id)
            elif domain == "attendance":
                executed, failed = await self._handle_attendance(decision, result, payload, request_id)
            else:
                logger.warning(
                    "[request_id=%s] ⚠️ [HRActionExecutor] Unknown domain: %s",
                    request_id, domain,
                )
                executed, failed = [], [f"unknown_domain:{domain}"]

            actions_executed.extend(executed)
            actions_failed.extend(failed)

        except Exception as e:
            logger.error(
                "[request_id=%s] ❌ [HRActionExecutor] Unhandled error: %s",
                request_id, e,
            )
            actions_failed.append(f"executor_error:{e}")

        summary = {
            "actions_executed":   actions_executed,
            "actions_failed":     actions_failed,
            "notifications_sent": len(actions_executed),
            "domain":             domain,
            "decision":           decision,
            "request_id":         request_id,
            "executed_at":        datetime.now(timezone.utc).isoformat(),
        }

        if actions_failed:
            logger.warning(
                "[request_id=%s] ⚠️ [HRActionExecutor] %d action(s) failed: %s",
                request_id, len(actions_failed), actions_failed,
            )
        else:
            logger.info(
                "[request_id=%s] ✅ [HRActionExecutor] All actions done: %s",
                request_id, actions_executed,
            )

        return summary

    # ── Leave Actions ─────────────────────────────────────────────────────────

    async def _handle_leave(
        self, decision: str, result: dict, payload: dict, request_id: str
    ) -> tuple[list, list]:
        executed, failed = [], []

        employee_name   = payload.get("employee_name", "Employee")
        employee_email  = self._resolve_employee_email(payload, request_id, context="leave")
        leave_type      = payload.get("leave_type", "annual")
        requested_days  = int(payload.get("requested_days", payload.get("leave_days", 0)))
        manager_email   = payload.get("manager_email", "manager@company.com")

        if decision == "approve":
            if employee_email:
                ok = await self.notifier.send_email(
                    to=employee_email,
                    subject=f"✅ Leave Request Approved — {requested_days} Days",
                    body=(
                        f"Dear {employee_name},\n\n"
                        f"Your {leave_type} leave request for {requested_days} day(s) has been approved.\n\n"
                        f"Reason: {result.get('reason', '')}\n\n"
                        "Best regards,\nHR Department"
                    ),
                    cc=[manager_email],
                    request_id=request_id,
                )
                (executed if ok else failed).append("leave_approval_email")
            else:
                failed.append("leave_approval_email:skipped_no_email")

        elif decision == "reject":
            if employee_email:
                ok = await self.notifier.send_email(
                    to=employee_email,
                    subject=f"❌ Leave Request Not Approved",
                    body=(
                        f"Dear {employee_name},\n\n"
                        f"Unfortunately, your {leave_type} leave request for {requested_days} day(s) "
                        "could not be approved at this time.\n\n"
                        f"Reason: {result.get('reason', '')}\n\n"
                        "Please contact HR for further discussion.\n\n"
                        "Best regards,\nHR Department"
                    ),
                    request_id=request_id,
                )
                (executed if ok else failed).append("leave_rejection_email")
            else:
                failed.append("leave_rejection_email:skipped_no_email")

        elif decision == "escalate":
            task_id = await self.notifier.create_task(
                assignee=manager_email,
                title=f"Leave Review Required: {employee_name} — {requested_days} days",
                description=(
                    f"AI confidence too low for auto-decision.\n"
                    f"Employee: {employee_name}\n"
                    f"Type: {leave_type} | Days: {requested_days}\n"
                    f"Reason: {result.get('reason', '')}\n"
                    f"Confidence: {result.get('confidence', 0):.0%}"
                ),
                priority="medium",
                due_hours=24,
                request_id=request_id,
            )
            executed.append(f"leave_escalation_task:{task_id}")

            if employee_email:
                ok = await self.notifier.send_email(
                    to=employee_email,
                    subject="⏳ Leave Request Under Review",
                    body=(
                        f"Dear {employee_name},\n\n"
                        f"Your {leave_type} leave request for {requested_days} day(s) is under review "
                        "by your manager. You will be notified within 24 hours.\n\n"
                        "Best regards,\nHR Department"
                    ),
                    request_id=request_id,
                )
                (executed if ok else failed).append("leave_escalation_email")
            else:
                failed.append("leave_escalation_email:skipped_no_email")

        return executed, failed

    # ── Salary Actions ────────────────────────────────────────────────────────

    async def _handle_salary(
        self, decision: str, result: dict, payload: dict, request_id: str
    ) -> tuple[list, list]:
        executed, failed = [], []

        employee_name    = payload.get("employee_name", "Employee")
        employee_email   = self._resolve_employee_email(payload, request_id, context="salary")
        hr_director_email = "hr.director@company.com"
        payroll_email    = "payroll@company.com"
        current_salary   = float(payload.get("current_salary_egp", 0))
        rec_pct          = float(result.get("recommended_increment_pct", 0) or 0)
        new_salary       = current_salary * (1 + rec_pct)
        effective_date   = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

        if decision == "approve_increment":
            # Notify employee
            if employee_email:
                ok = await self.notifier.send_email(
                    to=employee_email,
                    subject="✅ Salary Increment Approved",
                    body=(
                        f"Dear {employee_name},\n\n"
                        f"We are pleased to inform you that your salary increment of "
                        f"{rec_pct:.0%} has been approved.\n\n"
                        f"New Salary: {new_salary:,.0f} EGP (effective {effective_date})\n\n"
                        f"Details: {result.get('reason', '')}\n\n"
                        "Best regards,\nHR Department"
                    ),
                    cc=[payroll_email],
                    request_id=request_id,
                )
                (executed if ok else failed).append("salary_approval_email")
            else:
                failed.append("salary_approval_email:skipped_no_email")

            # Notify payroll (independent of employee email — payroll system
            # contact is internal, not employee-supplied)
            ok = await self.notifier.notify_payroll(
                employee_id=str(payload.get("employee_id", "")),
                action="salary_increment",
                amount=new_salary,
                effective_date=effective_date,
                request_id=request_id,
            )
            (executed if ok else failed).append("salary_payroll_notification")

        elif decision in ("defer", "reject"):
            if employee_email:
                ok = await self.notifier.send_email(
                    to=employee_email,
                    subject=f"Salary Review Update — {decision.capitalize()}",
                    body=(
                        f"Dear {employee_name},\n\n"
                        f"Your salary review has been {decision}ed.\n\n"
                        f"Details: {result.get('reason', '')}\n\n"
                        "Please contact HR for further information.\n\n"
                        "Best regards,\nHR Department"
                    ),
                    request_id=request_id,
                )
                (executed if ok else failed).append(f"salary_{decision}_email")
            else:
                failed.append(f"salary_{decision}_email:skipped_no_email")

        elif decision == "escalate_to_director":
            task_id = await self.notifier.create_task(
                assignee=hr_director_email,
                title=f"Salary Review Approval Required: {employee_name}",
                description=(
                    f"Increment of {rec_pct:.0%} requires Director approval.\n"
                    f"Employee: {employee_name}\n"
                    f"Current: {current_salary:,.0f} EGP → Proposed: {new_salary:,.0f} EGP\n"
                    f"Reason: {result.get('reason', '')}"
                ),
                priority="high",
                due_hours=48,
                request_id=request_id,
            )
            executed.append(f"salary_director_task:{task_id}")

            if employee_email:
                ok = await self.notifier.send_email(
                    to=employee_email,
                    subject="⏳ Salary Review Escalated to Director",
                    body=(
                        f"Dear {employee_name},\n\n"
                        "Your salary review has been escalated for Director approval. "
                        "You will be notified within 48 hours.\n\n"
                        "Best regards,\nHR Department"
                    ),
                    request_id=request_id,
                )
                (executed if ok else failed).append("salary_escalation_email")
            else:
                failed.append("salary_escalation_email:skipped_no_email")

        return executed, failed

    # ── Incentive Actions ─────────────────────────────────────────────────────

    async def _handle_incentive(
        self, decision: str, result: dict, payload: dict, request_id: str
    ) -> tuple[list, list]:
        executed, failed = [], []

        employee_name  = payload.get("employee_name", "Employee")
        employee_email = self._resolve_employee_email(payload, request_id, context="incentive")
        ceo_email      = "ceo@company.com"
        payroll_email  = "payroll@company.com"
        approved_amount = float(result.get("approved_amount_egp", 0) or 0)
        requested_amount = float(payload.get("requested_amount_egp", 0))
        incentive_type  = payload.get("incentive_type", "performance_bonus")
        effective_date  = datetime.now().strftime("%Y-%m-%d")

        if decision == "approve_bonus":
            if employee_email:
                ok = await self.notifier.send_email(
                    to=employee_email,
                    subject=f"✅ Bonus Approved — {approved_amount:,.0f} EGP",
                    body=(
                        f"Dear {employee_name},\n\n"
                        f"Your {incentive_type.replace('_', ' ').title()} of "
                        f"{approved_amount:,.0f} EGP has been approved.\n\n"
                        f"Details: {result.get('reason', '')}\n\n"
                        "Best regards,\nHR Department"
                    ),
                    cc=[payroll_email],
                    request_id=request_id,
                )
                (executed if ok else failed).append("bonus_approval_email")
            else:
                failed.append("bonus_approval_email:skipped_no_email")

            ok = await self.notifier.notify_payroll(
                employee_id=str(payload.get("employee_id", "")),
                action="bonus_payment",
                amount=approved_amount,
                effective_date=effective_date,
                request_id=request_id,
            )
            (executed if ok else failed).append("bonus_payroll_notification")

        elif decision == "partial_bonus":
            if employee_email:
                ok = await self.notifier.send_email(
                    to=employee_email,
                    subject=f"Partial Bonus Approved — {approved_amount:,.0f} EGP",
                    body=(
                        f"Dear {employee_name},\n\n"
                        f"A partial bonus of {approved_amount:,.0f} EGP "
                        f"(from requested {requested_amount:,.0f} EGP) has been approved.\n\n"
                        f"Details: {result.get('reason', '')}\n\n"
                        "Best regards,\nHR Department"
                    ),
                    cc=[payroll_email],
                    request_id=request_id,
                )
                (executed if ok else failed).append("partial_bonus_email")
            else:
                failed.append("partial_bonus_email:skipped_no_email")

            ok = await self.notifier.notify_payroll(
                employee_id=str(payload.get("employee_id", "")),
                action="partial_bonus_payment",
                amount=approved_amount,
                effective_date=effective_date,
                request_id=request_id,
            )
            (executed if ok else failed).append("partial_bonus_payroll_notification")

        elif decision == "deny_bonus":
            if employee_email:
                ok = await self.notifier.send_email(
                    to=employee_email,
                    subject="Bonus Request Update",
                    body=(
                        f"Dear {employee_name},\n\n"
                        "Your bonus request could not be approved at this time.\n\n"
                        f"Details: {result.get('reason', '')}\n\n"
                        "Best regards,\nHR Department"
                    ),
                    request_id=request_id,
                )
                (executed if ok else failed).append("bonus_denial_email")
            else:
                failed.append("bonus_denial_email:skipped_no_email")

        elif decision == "escalate_to_ceo":
            task_id = await self.notifier.create_task(
                assignee=ceo_email,
                title=f"Bonus Approval Required (CEO Level): {employee_name}",
                description=(
                    f"Requested amount {requested_amount:,.0f} EGP exceeds 3x monthly salary.\n"
                    f"Employee: {employee_name}\n"
                    f"Type: {incentive_type}\n"
                    f"Reason: {result.get('reason', '')}"
                ),
                priority="high",
                due_hours=72,
                request_id=request_id,
            )
            executed.append(f"bonus_ceo_task:{task_id}")

        return executed, failed

    # ── Absence Actions ───────────────────────────────────────────────────────

    async def _handle_absence(
        self, decision: str, result: dict, payload: dict, request_id: str
    ) -> tuple[list, list]:
        executed, failed = [], []

        employee_name    = payload.get("employee_name", "Employee")
        employee_email   = self._resolve_employee_email(payload, request_id, context="absence")
        hr_director_email = "hr.director@company.com"
        deduction_days   = float(result.get("payroll_deduction_days", 0))
        absence_date     = str(payload.get("absence_date", ""))

        if decision in ("written_warning", "formal_warning"):
            warning_type = "Formal" if decision == "formal_warning" else "Written"
            if employee_email:
                ok = await self.notifier.send_email(
                    to=employee_email,
                    subject=f"⚠️ {warning_type} Warning — Absence on {absence_date}",
                    body=(
                        f"Dear {employee_name},\n\n"
                        f"This is a {warning_type.lower()} warning regarding your absence on {absence_date}.\n\n"
                        f"Details: {result.get('reason', '')}\n\n"
                        f"{'Payroll deduction of ' + str(deduction_days) + ' day(s) will be applied.' if deduction_days > 0 else ''}\n\n"
                        "Please ensure compliance with attendance policy going forward.\n\n"
                        "Best regards,\nHR Department"
                    ),
                    cc=[hr_director_email] if decision == "formal_warning" else [],
                    request_id=request_id,
                )
                (executed if ok else failed).append(f"absence_{decision}_email")
            else:
                failed.append(f"absence_{decision}_email:skipped_no_email")

            if deduction_days > 0:
                ok = await self.notifier.notify_payroll(
                    employee_id=str(payload.get("employee_id", "")),
                    action="absence_deduction",
                    amount=deduction_days,
                    effective_date=datetime.now().strftime("%Y-%m-%d"),
                    request_id=request_id,
                )
                (executed if ok else failed).append("absence_payroll_deduction")

        elif decision == "escalate_to_hr_director":
            task_id = await self.notifier.create_task(
                assignee=hr_director_email,
                title=f"🚨 URGENT: Absence Escalation — {employee_name}",
                description=(
                    f"Critical absence pattern detected.\n"
                    f"Employee: {employee_name}\n"
                    f"Date: {absence_date}\n"
                    f"Unexcused (90d): {payload.get('unexcused_count_90d', 0)}\n"
                    f"Details: {result.get('reason', '')}"
                ),
                priority="urgent",
                due_hours=4,
                request_id=request_id,
            )
            executed.append(f"absence_escalation_task:{task_id}")

            # NOTE: this notification goes to hr_director_email (an internal,
            # hardcoded HR address) — not employee_email — so it's unaffected
            # by the employee-email-missing fix above.
            ok = await self.notifier.send_email(
                to=hr_director_email,
                subject=f"🚨 URGENT: Absence Escalation — {employee_name}",
                body=(
                    f"Director,\n\n"
                    f"Immediate attention required for employee {employee_name}.\n\n"
                    f"Details: {result.get('reason', '')}\n\n"
                    f"Task ID: {task_id}\n\n"
                    "HR System"
                ),
                request_id=request_id,
            )
            (executed if ok else failed).append("absence_director_notification")

        elif decision == "suspension_review":
            task_id = await self.notifier.create_task(
                assignee=hr_director_email,
                title=f"Suspension Review Required: {employee_name}",
                description=(
                    f"Employee has formal warning + new unexcused absence.\n"
                    f"Employee: {employee_name}\n"
                    f"Date: {absence_date}\n"
                    f"Reason: {result.get('reason', '')}"
                ),
                priority="high",
                due_hours=24,
                request_id=request_id,
            )
            executed.append(f"suspension_review_task:{task_id}")

        elif decision == "record_only":
            # Just log — no email needed for excused absences
            logger.info(
                "[request_id=%s] 📝 Absence recorded only — no action needed (excused)",
                request_id,
            )
            executed.append("absence_recorded_no_action")

        return executed, failed

    # ── Attendance Actions ────────────────────────────────────────────────────

    async def _handle_attendance(
        self, decision: str, result: dict, payload: dict, request_id: str
    ) -> tuple[list, list]:
        executed, failed = [], []

        employee_name    = payload.get("employee_name", "Employee")
        employee_email   = self._resolve_employee_email(payload, request_id, context="attendance")
        hr_director_email = "hr.director@company.com"
        month_label      = payload.get("month_label", datetime.now().strftime("%B %Y"))
        att_rate         = (
            int(payload.get("days_present", 20)) /
            max(int(payload.get("working_days", 22)), 1)
        )

        if decision == "no_action":
            logger.info("[request_id=%s] ✅ Attendance OK — no action needed", request_id)
            executed.append("attendance_no_action")

        elif decision == "counseling_session":
            task_id = await self.notifier.create_task(
                assignee="hr@company.com",
                title=f"Counseling Session: {employee_name} — {month_label}",
                description=(
                    f"Schedule attendance counseling.\n"
                    f"Employee: {employee_name}\n"
                    f"Attendance: {att_rate:.1%} ({payload.get('days_present')}/{payload.get('working_days')} days)\n"
                    f"Reason: {result.get('reason', '')}"
                ),
                priority="medium",
                due_hours=72,
                request_id=request_id,
            )
            executed.append(f"counseling_task:{task_id}")

            if employee_email:
                ok = await self.notifier.send_email(
                    to=employee_email,
                    subject=f"Attendance Review — {month_label}",
                    body=(
                        f"Dear {employee_name},\n\n"
                        f"Your attendance for {month_label} ({att_rate:.1%}) requires a brief review. "
                        "HR will be in touch to schedule a supportive session.\n\n"
                        "Best regards,\nHR Department"
                    ),
                    request_id=request_id,
                )
                (executed if ok else failed).append("counseling_email")
            else:
                failed.append("counseling_email:skipped_no_email")

        elif decision == "formal_warning":
            if employee_email:
                ok = await self.notifier.send_email(
                    to=employee_email,
                    subject=f"⚠️ Formal Warning — Attendance {month_label}",
                    body=(
                        f"Dear {employee_name},\n\n"
                        f"This is a formal warning regarding your attendance for {month_label} "
                        f"({att_rate:.1%}).\n\n"
                        f"Details: {result.get('reason', '')}\n\n"
                        "Failure to improve attendance may result in further disciplinary action.\n\n"
                        "Best regards,\nHR Department"
                    ),
                    cc=[hr_director_email],
                    request_id=request_id,
                )
                (executed if ok else failed).append("attendance_warning_email")
            else:
                failed.append("attendance_warning_email:skipped_no_email")

        elif decision == "escalate_to_hr_director":
            task_id = await self.notifier.create_task(
                assignee=hr_director_email,
                title=f"🚨 Critical Attendance: {employee_name} — {month_label}",
                description=(
                    f"Attendance rate {att_rate:.1%} is critically low.\n"
                    f"Employee: {employee_name}\n"
                    f"Month: {month_label}\n"
                    f"Present: {payload.get('days_present')}/{payload.get('working_days')} days\n"
                    f"Reason: {result.get('reason', '')}"
                ),
                priority="urgent",
                due_hours=8,
                request_id=request_id,
            )
            executed.append(f"attendance_escalation_task:{task_id}")

            # Internal HR-director address, not employee-supplied — unaffected
            # by the employee email fix.
            ok = await self.notifier.send_email(
                to=hr_director_email,
                subject=f"🚨 URGENT: Critical Attendance — {employee_name}",
                body=f"Director, immediate action needed.\n\nDetails: {result.get('reason', '')}",
                request_id=request_id,
            )
            (executed if ok else failed).append("attendance_director_email")

        return executed, failed


# ── Singleton ─────────────────────────────────────────────────────────────────
#
# WARN 1 FIX: constructed at module import time (not lazily). CPython's
# import machinery serializes execution of a module's top-level code via a
# per-module lock, so even if multiple threads do `import hr_action_executor`
# concurrently, this line runs exactly once. That gives us the same
# guarantee a threading.Lock()-guarded lazy-init would, without the extra
# lock/double-check code to get wrong.
_executor_instance = HRActionExecutor()


def get_hr_action_executor() -> HRActionExecutor:
    return _executor_instance
