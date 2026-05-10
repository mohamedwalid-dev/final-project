"""
📋 Workflow Registry — v5.0
============================
File: app/orchestrator/workflow_registry.py

Registered Workflows:
    ✅ leave_request / leave_requested  → LeaveApprovalWorkflow
    ✅ salary_review                    → SalaryReviewWorkflow
    ✅ incentive_request                → IncentiveWorkflow
    ✅ absence_event                    → AbsenceWorkflow
    ✅ attendance_audit                 → AttendanceWorkflow
    ✅ ticket_created                   → TicketWorkflow
    ✅ lead_added                       → LeadWorkflow
    ✅ invoice_overdue                  → OverdueInvoiceWorkflow    (NEW Finance v1)
    ✅ invoice_created                  → NewInvoiceWorkflow        (NEW Finance v1)
    ✅ payment_received                 → PaymentReceivedWorkflow   (NEW Finance v1)
"""

from __future__ import annotations

from workflows.hr.leave_approval_workflow import (
    LeaveApprovalWorkflow,
    SalaryReviewWorkflow,
    IncentiveWorkflow,
    AbsenceWorkflow,
    AttendanceWorkflow,
)
from workflows.support.ticket_workflow import TicketWorkflow
from workflows.crm.lead_workflow import LeadWorkflow

# ── Finance Workflows (NEW) ───────────────────────────────────────────────────
from workflows.finance.invoice_workflow import (
    OverdueInvoiceWorkflow,
    NewInvoiceWorkflow,
    PaymentReceivedWorkflow,
)


class WorkflowRegistry:
    """
    Registry pattern: event_type → Workflow instance.

    To add a new workflow:
        1. Create the workflow class
        2. Import it here
        3. Add it to self._workflows
        That's it ✅
    """

    def __init__(self) -> None:
        self._workflows: dict = {
            # ── HR — Leave ────────────────────────────────────────────────────
            "leave_request":   LeaveApprovalWorkflow(),
            "leave_requested": LeaveApprovalWorkflow(),   # EventBus alias

            # ── HR — Salary ───────────────────────────────────────────────────
            "salary_review":   SalaryReviewWorkflow(),

            # ── HR — Incentive ────────────────────────────────────────────────
            "incentive_request": IncentiveWorkflow(),

            # ── HR — Absence ──────────────────────────────────────────────────
            "absence_event":   AbsenceWorkflow(),

            # ── HR — Attendance ───────────────────────────────────────────────
            "attendance_audit": AttendanceWorkflow(),

            # ── Support ───────────────────────────────────────────────────────
            "ticket_created":  TicketWorkflow(),

            # ── CRM ───────────────────────────────────────────────────────────
            "lead_added":      LeadWorkflow(),

            # ── Finance (NEW v1) ──────────────────────────────────────────────
            "invoice_overdue":  OverdueInvoiceWorkflow(),
            "invoice_created":  NewInvoiceWorkflow(),
            "payment_received": PaymentReceivedWorkflow(),
        }

    def get_workflow(self, event_type: str):
        """Returns the workflow for an event type, or None if not registered."""
        return self._workflows.get(event_type)

    def list_workflows(self) -> list[str]:
        """Returns all registered event types."""
        return list(self._workflows.keys())

    def register(self, event_type: str, workflow) -> None:
        """Dynamically register a new workflow at runtime."""
        self._workflows[event_type] = workflow