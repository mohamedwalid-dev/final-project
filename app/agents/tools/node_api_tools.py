"""
agents/tools/node_api_tools.py — LangChain Tools over the Node.js ERP API
============================================================================
Wraps core.node_api_client.NodeAPIClient as @tool-decorated async functions
so the HR / Finance / Coordinator agents can call the Node.js REST API the
same way they already call any other LangChain tool.

This is the "AI talks to APIs only" pattern:

    LLM (Gemini) → picks a tool → this file → NodeAPIClient → Node.js/Express → MongoDB

Design notes:
    - Every tool returns a JSON *string* (via json.dumps), not a Python
      dict/list. LangChain tool outputs get interpolated into the LLM's
      context as text, so returning a string avoids an implicit
      str(dict) call that produces single-quoted, non-JSON output the
      model then has to unlearn.
    - Every tool is wrapped in try/except NodeAPIError so a Node.js
      outage becomes a normal, LLM-readable tool result ({"error": ...})
      instead of an unhandled exception that kills the agent's run.
      This matters especially inside a LangGraph ReAct loop (Supervisor/
      Finance/HR sub-agents) — an uncaught exception there aborts the
      whole graph run, not just the one tool call.
    - Tools are intentionally thin. Business logic (thresholds, decision
      rules) stays in the workflows / decision-engines that already own
      it (SalaryReviewWorkflow, agents/hr/salary_decision_engine.py,
      etc.) — these tools only fetch data.
    - Register the constant NODE_API_TOOLS list wherever your agents
      currently assemble their tool list. Example:

          from agents.tools.node_api_tools import NODE_API_TOOLS
          finance_agent_tools = [*existing_finance_tools, *NODE_API_TOOLS]
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from langchain_core.tools import tool

from core.node_api_client import NodeAPIError, get_node_api_client

logger = logging.getLogger(__name__)


def _ok(data) -> str:
    return json.dumps({"ok": True, "data": data}, default=str, ensure_ascii=False)


def _err(e: Exception, tool_name: str) -> str:
    logger.warning("⚠️ [node_api_tool:%s] %s", tool_name, e)
    payload = {"ok": False, "error": str(e)}
    if isinstance(e, NodeAPIError) and e.status_code:
        payload["status_code"] = e.status_code
    return json.dumps(payload, ensure_ascii=False)


# ── Finance ─────────────────────────────────────────────────────────────

@tool
async def get_customers(status: Optional[str] = None, limit: int = 20) -> str:
    """Get customer profiles from the Finance module (credit score, industry,
    account age, service status, blacklist flag). Use `status` to filter by
    service_status (active | suspended | terminated | on_hold). Use this
    before assessing a customer's payment risk or drafting a collections
    action, to ground the response in their real account state."""
    try:
        return _ok(await get_node_api_client().get_customers(status=status, limit=limit))
    except NodeAPIError as e:
        return _err(e, "get_customers")


@tool
async def get_invoices(status: Optional[str] = None, limit: int = 20) -> str:
    """Get invoices from the Finance module. Filter by `status` (pending |
    overdue | paid | suspended | legal | written_off | cancelled |
    payment_plan | disputed). Use this to check an invoice's amount, due
    date, AI risk score, and collection strategy before recommending a next
    action."""
    try:
        return _ok(await get_node_api_client().get_invoices(status=status, limit=limit))
    except NodeAPIError as e:
        return _err(e, "get_invoices")


@tool
async def get_overdue_invoices() -> str:
    """Get all currently overdue invoices. Use this to build a collections
    priority list or answer 'which customers are overdue right now'."""
    try:
        return _ok(await get_node_api_client().get_overdue_invoices())
    except NodeAPIError as e:
        return _err(e, "get_overdue_invoices")


@tool
async def get_invoice_by_id(invoice_id: str) -> str:
    """Get a single invoice by its MongoDB id, including AI risk score,
    decision reason, and collection strategy."""
    try:
        return _ok(await get_node_api_client().get_invoice(invoice_id))
    except NodeAPIError as e:
        return _err(e, "get_invoice_by_id")


@tool
async def get_legal_cases(status: Optional[str] = None, limit: int = 20) -> str:
    """Get legal escalation cases for unpaid invoices. Filter by `status`
    (opened | in_progress | on_hold | resolved | settled | closed). Use
    this to check whether a customer already has an active legal case
    before recommending escalation."""
    try:
        return _ok(await get_node_api_client().get_legal_cases(status=status, limit=limit))
    except NodeAPIError as e:
        return _err(e, "get_legal_cases")


@tool
async def get_legal_case_by_id(case_id: str) -> str:
    """Get full detail (timeline, SLA deadline, resolution) for one legal
    case by its MongoDB id."""
    try:
        return _ok(await get_node_api_client().get_legal_case(case_id))
    except NodeAPIError as e:
        return _err(e, "get_legal_case_by_id")


@tool
async def get_collection_log(invoice_id: Optional[str] = None,
                              customer_id: Optional[str] = None, limit: int = 20) -> str:
    """Get the collections action log (reminders, calls, escalations sent
    for invoices/customers). Filter by invoice_id or customer_id to see
    what's already been tried before recommending the next collections
    action, so the same reminder isn't sent twice."""
    try:
        return _ok(await get_node_api_client().get_collection_log(
            invoice_id=invoice_id, customer_id=customer_id, limit=limit))
    except NodeAPIError as e:
        return _err(e, "get_collection_log")


@tool
async def get_finance_audit_trail(entity_id: str, domain: str = "invoice") -> str:
    """Get the finance audit trail for one entity (AI decisions, confidence,
    execution time). `domain` is usually 'invoice'."""
    try:
        return _ok(await get_node_api_client().get_finance_audit(entity_id, domain=domain))
    except NodeAPIError as e:
        return _err(e, "get_finance_audit_trail")


@tool
async def get_finance_decisions(entity_id: str) -> str:
    """Get the history of AI decisions (risk scores, confidence, action
    plans) previously made for one finance entity (e.g. an invoice id)."""
    try:
        return _ok(await get_node_api_client().get_finance_decisions(entity_id))
    except NodeAPIError as e:
        return _err(e, "get_finance_decisions")


@tool
async def get_active_escalations() -> str:
    """Get all currently active finance escalations across all customers.
    Use this to answer 'what needs urgent finance attention right now'."""
    try:
        return _ok(await get_node_api_client().get_active_escalations())
    except NodeAPIError as e:
        return _err(e, "get_active_escalations")


@tool
async def get_finance_dashboard_stats() -> str:
    """Get aggregate Finance KPIs (totals, overdue amounts, collection
    rates) for the dashboard. Use this for high-level 'how is finance
    doing overall' questions rather than fetching every invoice."""
    try:
        return _ok(await get_node_api_client().get_finance_dashboard())
    except NodeAPIError as e:
        return _err(e, "get_finance_dashboard_stats")


# ── HR ──────────────────────────────────────────────────────────────────

@tool
async def get_leave_requests(status: Optional[str] = None, limit: int = 20) -> str:
    """Get leave requests. Filter by `status` (pending | approved | rejected
    | escalated | cancelled)."""
    try:
        return _ok(await get_node_api_client().get_leaves(status=status, limit=limit))
    except NodeAPIError as e:
        return _err(e, "get_leave_requests")


@tool
async def get_leave_by_id(leave_id: str) -> str:
    """Get one leave request by id, including its AI decision, confidence
    score, and decision reason."""
    try:
        return _ok(await get_node_api_client().get_leave(leave_id))
    except NodeAPIError as e:
        return _err(e, "get_leave_by_id")


@tool
async def get_salary_reviews(status: Optional[str] = None, limit: int = 20) -> str:
    """Get salary review requests. Filter by `status` (pending | approved |
    rejected | escalated | cancelled). Includes current salary, requested
    increment, market gap, and the AI's recommended increment."""
    try:
        return _ok(await get_node_api_client().get_salary_reviews(status=status, limit=limit))
    except NodeAPIError as e:
        return _err(e, "get_salary_reviews")


@tool
async def get_salary_review_by_id(review_id: str) -> str:
    """Get one salary review by id, including the AI's decision and
    recommended_increment_pct."""
    try:
        return _ok(await get_node_api_client().get_salary_review(review_id))
    except NodeAPIError as e:
        return _err(e, "get_salary_review_by_id")


@tool
async def get_absence_events(status: Optional[str] = None, limit: int = 20) -> str:
    """Get absence events. Filter by `status` (pending | excused | unexcused
    | escalated | cancelled). Includes AI classification and payroll
    deduction days."""
    try:
        return _ok(await get_node_api_client().get_absence_events(status=status, limit=limit))
    except NodeAPIError as e:
        return _err(e, "get_absence_events")


@tool
async def get_absence_event_by_id(absence_id: str) -> str:
    """Get one absence event by id, including AI classification and whether
    escalation is required."""
    try:
        return _ok(await get_node_api_client().get_absence_event(absence_id))
    except NodeAPIError as e:
        return _err(e, "get_absence_event_by_id")


@tool
async def get_incentive_requests(status: Optional[str] = None, limit: int = 20) -> str:
    """Get incentive/bonus requests. Filter by `status` (pending | approved
    | rejected | escalated | cancelled)."""
    try:
        return _ok(await get_node_api_client().get_incentive_requests(status=status, limit=limit))
    except NodeAPIError as e:
        return _err(e, "get_incentive_requests")


@tool
async def get_incentive_request_by_id(incentive_id: str) -> str:
    """Get one incentive request by id, including requested vs approved
    amount and the AI decision."""
    try:
        return _ok(await get_node_api_client().get_incentive_request(incentive_id))
    except NodeAPIError as e:
        return _err(e, "get_incentive_request_by_id")


@tool
async def get_employee_balance_history(employee_id: str) -> str:
    """Get an employee's leave-balance change history (old/new balance,
    delta, reason, who performed it). Requires the employee's MongoDB id.
    Use this to answer 'show employee balance history' / 'why did this
    employee's leave balance change'."""
    try:
        return _ok(await get_node_api_client().get_balance_audit_history(employee_id))
    except NodeAPIError as e:
        return _err(e, "get_employee_balance_history")


@tool
async def get_hr_audit_trail(entity_id: str, domain: str) -> str:
    """Get the HR audit trail for one entity. `domain` must be one of:
    leave | salary | absence | incentive."""
    try:
        return _ok(await get_node_api_client().get_hr_audit(entity_id, domain=domain))
    except NodeAPIError as e:
        return _err(e, "get_hr_audit_trail")


@tool
async def get_hr_dashboard_stats() -> str:
    """Get aggregate HR KPIs (headcount, pending requests, approval rates)
    for the dashboard. Use this for high-level 'how is HR doing overall'
    questions rather than fetching every record."""
    try:
        return _ok(await get_node_api_client().get_hr_dashboard())
    except NodeAPIError as e:
        return _err(e, "get_hr_dashboard_stats")


# ── Registration list ──────────────────────────────────────────────────

NODE_API_TOOLS = [
    # Finance
    get_customers,
    get_invoices,
    get_overdue_invoices,
    get_invoice_by_id,
    get_legal_cases,
    get_legal_case_by_id,
    get_collection_log,
    get_finance_audit_trail,
    get_finance_decisions,
    get_active_escalations,
    get_finance_dashboard_stats,
    # HR
    get_leave_requests,
    get_leave_by_id,
    get_salary_reviews,
    get_salary_review_by_id,
    get_absence_events,
    get_absence_event_by_id,
    get_incentive_requests,
    get_incentive_request_by_id,
    get_employee_balance_history,
    get_hr_audit_trail,
    get_hr_dashboard_stats,
]
