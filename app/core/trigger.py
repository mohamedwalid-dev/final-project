"""
trigger.py — Trigger Engine v5.1
==================================
File: app/core/trigger.py

Handles:
    - APScheduler jobs (scan DB every N seconds)
    - EventBus handler registration
    - Orchestrator bridge for all HR domains

Domains:
    ✅ Leaves      — existing
    ✅ Tickets     — existing
    ✅ Leads       — existing
    ✅ Salary Reviews   — v5.1 new
    ✅ Incentives       — v5.1 new
    ✅ Absence Events   — v5.1 new

ENV vars for scan intervals:
    LEAVE_SCAN_INTERVAL_SEC    (default: 30)
    TICKET_SCAN_INTERVAL_SEC   (defaul.t: 60)
    LEAD_SCAN_INTERVAL_SEC     (default: 120)
    SALARY_SCAN_INTERVAL_SEC   (default: 600)
    INCENTIVE_SCAN_INTERVAL_SEC (default: 600)
  
ARCHITECTURE RULE (v5.1+):
    Bridge  = routing only   → NO claim here
    Workflow = claim + decide → claim lives inside each Workflow
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import os
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from core.finance_trigger import (
    job_scan_overdue_invoices,
    job_scan_new_invoices,
    register_finance_handlers,
    INVOICE_SCAN_SEC,
    NEW_INVOICE_SCAN_SEC,
)


from core.event_bus import event_bus

logger = logging.getLogger(__name__)

# ── Scan intervals (seconds) — configurable via ENV ──────────────────────────
LEAVE_SCAN_SEC     = int(os.getenv("LEAVE_SCAN_INTERVAL_SEC",    30))
TICKET_SCAN_SEC    = int(os.getenv("TICKET_SCAN_INTERVAL_SEC",   60))
LEAD_SCAN_SEC      = int(os.getenv("LEAD_SCAN_INTERVAL_SEC",    120))
EVENT_QUEUE_SEC    = int(os.getenv("EVENT_QUEUE_INTERVAL_SEC",   15))
SALARY_SCAN_SEC    = int(os.getenv("SALARY_SCAN_INTERVAL_SEC",  600))
INCENTIVE_SCAN_SEC = int(os.getenv("INCENTIVE_SCAN_INTERVAL_SEC", 600))
ABSENCE_SCAN_SEC   = int(os.getenv("ABSENCE_SCAN_INTERVAL_SEC", 300))

_scheduler: Optional[AsyncIOScheduler] = None




# ════════════════════════════════════════════════════════
#  SCHEDULER CONTROL
# ════════════════════════════════════════════════════════

async def start_trigger_engine(orchestrator) -> None:
    """Start APScheduler + register all EventBus handlers."""
    global _scheduler

    from core.finance_trigger import (
        job_scan_overdue_invoices,
        job_scan_new_invoices,
        register_finance_handlers,
        INVOICE_SCAN_SEC,
        NEW_INVOICE_SCAN_SEC,
    )

    register_orchestrator_handlers(orchestrator)
    register_finance_handlers(orchestrator)

    _scheduler = AsyncIOScheduler(timezone="UTC")

    _scheduler.add_job(
        job_scan_pending_leaves,
        trigger=IntervalTrigger(seconds=LEAVE_SCAN_SEC),
        id="scan_leaves",
        name="[HR] Scan pending leaves",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
    )
    _scheduler.add_job(
        job_scan_pending_tickets,
        trigger=IntervalTrigger(seconds=TICKET_SCAN_SEC),
        id="scan_tickets",
        name="[Support] Scan pending tickets",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
    )
    _scheduler.add_job(
        job_scan_new_leads,
        trigger=IntervalTrigger(seconds=LEAD_SCAN_SEC),
        id="scan_leads",
        name="[CRM] Scan new leads",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=120,
    )
    _scheduler.add_job(
        job_process_event_queue,
        trigger=IntervalTrigger(seconds=EVENT_QUEUE_SEC),
        id="process_event_queue",
        name="[System] Process event queue",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=30,
    )
    _scheduler.add_job(
        job_scan_pending_salary_reviews,
        trigger=IntervalTrigger(seconds=SALARY_SCAN_SEC),
        id="scan_salary_reviews",
        name="[HR] Scan pending salary reviews",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=120,
    )
    _scheduler.add_job(
        job_scan_pending_incentives,
        trigger=IntervalTrigger(seconds=INCENTIVE_SCAN_SEC),
        id="scan_incentives",
        name="[HR] Scan pending incentive requests",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=120,
    )
    _scheduler.add_job(
        job_scan_pending_absences,
        trigger=IntervalTrigger(seconds=ABSENCE_SCAN_SEC),
        id="scan_absences",
        name="[HR] Scan pending absence events",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
    )

    _scheduler.add_job(
        job_scan_overdue_invoices,
        trigger=IntervalTrigger(seconds=INVOICE_SCAN_SEC),
        id="scan_overdue_invoices",
        name="[Finance] Scan overdue invoices",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=120,
    )
    _scheduler.add_job(
        job_scan_new_invoices,
        trigger=IntervalTrigger(seconds=NEW_INVOICE_SCAN_SEC),
        id="scan_new_invoices",
        name="[Finance] Scan new invoices",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=120,
    )


    

    _scheduler.start()
    logger.info(
        "✅ Trigger Engine started — %d jobs scheduled",
        len(_scheduler.get_jobs()),
    )


def stop_trigger_engine() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("🔴 Trigger Engine stopped")


def get_scheduler_status() -> dict:
    if not _scheduler:
        return {"running": False, "jobs_count": 0, "jobs": []}
    return {
        "running":    _scheduler.running,
        "jobs_count": len(_scheduler.get_jobs()),
        "jobs": [
            {
                "id":       job.id,
                "name":     job.name,
                "next_run": str(job.next_run_time),
            }
            for job in _scheduler.get_jobs()
        ],
    }


# ════════════════════════════════════════════════════════
#  EVENT BUS HANDLER REGISTRATION
# ════════════════════════════════════════════════════════

def register_orchestrator_handlers(orchestrator) -> None:
    """Subscribe all domain handlers to the EventBus."""

    # ── Existing domains ─────────────────────────────────────────────────────
    event_bus.subscribe("leave_requested", _build_leave_handler(orchestrator))
    event_bus.subscribe("ticket_created",  _build_ticket_handler(orchestrator))
    event_bus.subscribe("lead_added",      _build_lead_handler(orchestrator))

    # ── HR Domain v5.1 ───────────────────────────────────────────────────────
    event_bus.subscribe("salary_review",     _build_salary_handler(orchestrator))
    event_bus.subscribe("incentive_request", _build_incentive_handler(orchestrator))
    event_bus.subscribe("absence_event",     _build_absence_handler(orchestrator))

    logger.info(
        "✅ [Bridge] All handlers registered — "
        "leaves / tickets / leads / salary / incentive / absence"
    )


# ════════════════════════════════════════════════════════
#  ATOMIC CLAIM HELPER
#  ⚠️  Use ONLY inside Workflows — NOT in Bridge handlers
# ════════════════════════════════════════════════════════

async def _claim_entity(
    table: str,
    entity_id: int,
    from_status: str = "pending",
    to_status: str = "in_progress",
) -> bool:
    """
    Atomic claim — marks an entity as in_progress to prevent duplicate processing.
    Returns True if claim succeeded, False if already claimed by another worker.

    ⚠️  ARCHITECTURE RULE: Call this inside the Workflow, NOT in the Bridge handler.
        Bridge = routing only. Workflow = claim + decision.
    """
    try:
        db_module = importlib.import_module("core.db")
        with db_module.get_db() as (conn, cur):
            cur.execute(
                f"UPDATE {table} SET status = %s WHERE id = %s AND status = %s",
                (to_status, entity_id, from_status),
            )
            conn.commit()
            return cur.rowcount == 1
    except Exception as e:
        logger.warning(
            "⚠️ [Claim] Failed to claim %s #%s: %s — allowing through",
            table, entity_id, e,
        )
        return True  # on unexpected DB error, allow through (non-fatal)


# ════════════════════════════════════════════════════════
#  SCHEDULER JOBS — Existing
# ════════════════════════════════════════════════════════

async def job_scan_pending_leaves() -> None:
    """⏰ Scan leave_requests with status=pending → publish to EventBus."""
    from core.db import get_pending_leaves, start_execution, finish_execution

    logger.info("⏰ [Scheduler] Scanning pending leaves...")
    exec_id = start_execution("leave_scan", "scheduler", 0)
    try:
        leaves = get_pending_leaves()
        if not leaves:
            logger.info("   ✅ No pending leaves.")
            finish_execution(exec_id, "completed")
            return

        logger.info("   📋 Found %d pending leave(s)", len(leaves))
        for leave in leaves:
            result = await event_bus.publish("leave_requested", {
                "leave_id":      leave.get("id"),
                "employee_id":   str(leave.get("employee_id", "")),
                "employee_name": leave.get("employee_name", ""),
                "leave_days":    leave.get("leave_days", 1),
                "leave_type":    leave.get("leave_type", "annual"),
                "leave_balance": int(leave.get("leave_balance") or 0),
                "reason":        leave.get("reason", ""),
                "source":        "scheduler",
            })
            if result == -1:
                logger.info("   ⏭️ Leave #%s already processing — skipped", leave.get("id"))

        finish_execution(exec_id, "completed")
    except Exception as e:
        logger.error("❌ [Scheduler] Leave scan failed: %s", e, exc_info=True)
        finish_execution(exec_id, "failed", str(e))


async def job_scan_pending_tickets() -> None:
    """⏰ Scan tickets with status=open → publish to EventBus."""
    from core.db import get_pending_tickets, start_execution, finish_execution

    logger.info("⏰ [Scheduler] Scanning pending tickets...")
    exec_id = start_execution("ticket_scan", "scheduler", 0)
    try:
        tickets = get_pending_tickets()
        if not tickets:
            finish_execution(exec_id, "completed")
            return

        logger.info("   🎫 Found %d pending ticket(s)", len(tickets))
        for ticket in tickets:
            await event_bus.publish("ticket_created", {
                "ticket_id":     ticket.get("id"),
                "customer_id":   ticket.get("customer_id"),
                "customer_name": ticket.get("customer_name", ""),
                "priority":      ticket.get("priority", "medium"),
                "category":      ticket.get("category", "general"),
                "message":       ticket.get("message", ""),
                "source":        "scheduler",
            })

        finish_execution(exec_id, "completed")
    except Exception as e:
        logger.error("❌ [Scheduler] Ticket scan failed: %s", e, exc_info=True)
        finish_execution(exec_id, "failed", str(e))


async def job_scan_new_leads() -> None:
    """⏰ Scan leads with status=new → publish to EventBus."""
    from core.db import get_new_leads, start_execution, finish_execution

    logger.info("⏰ [Scheduler] Scanning new leads...")
    exec_id = start_execution("lead_scan", "scheduler", 0)
    try:
        leads = get_new_leads()
        if not leads:
            finish_execution(exec_id, "completed")
            return

        logger.info("   💼 Found %d new lead(s)", len(leads))
        for lead in leads:
            await event_bus.publish("lead_added", {
                "lead_id": lead.get("id"),
                "name":    lead.get("name", ""),
                "email":   lead.get("email", ""),
                "source":  lead.get("source", "unknown"),
                "notes":   lead.get("notes", ""),
            })

        finish_execution(exec_id, "completed")
    except Exception as e:
        logger.error("❌ [Scheduler] Lead scan failed: %s", e, exc_info=True)
        finish_execution(exec_id, "failed", str(e))


async def job_process_event_queue() -> None:
    """⏰ Process events table with status=pending → publish each to EventBus."""
    import json
    from core.db import get_pending_events, mark_event_done

    logger.debug("⏰ [Scheduler] Processing event queue...")
    try:
        events = get_pending_events()
        if not events:
            return

        logger.info("   📥 Processing %d event(s) from queue", len(events))
        for event in events:
            event_type = event.get("event_type", "")
            entity_id  = event.get("entity_id", 0)
            raw_payload = event.get("payload", "{}")

            try:
                payload = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
            except Exception:
                payload = {}

            payload["event_id"] = event.get("id")

            result = await event_bus.publish(event_type, payload)
            if result == -1:
                logger.debug("   ⏭️ Event #%s (%s) already in cache — skipped", event.get("id"), event_type)
            else:
                logger.info("   📤 Event #%s (%s) entity=%s → published", event.get("id"), event_type, entity_id)
                mark_event_done(event.get("id"), "published")

    except Exception as e:
        logger.error("❌ [Scheduler] Event queue processing failed: %s", e, exc_info=True)


# ════════════════════════════════════════════════════════
#  SCHEDULER JOBS — HR Domain v5.1
# ════════════════════════════════════════════════════════

async def job_scan_pending_salary_reviews() -> None:
    """⏰ Scan salary_reviews with status=pending → publish to EventBus."""
    from core.db import get_pending_salary_reviews, start_execution, finish_execution

    logger.info("⏰ [Scheduler] Scanning pending salary reviews...")
    exec_id = start_execution("salary_review_scan", "scheduler", 0)
    try:
        reviews = get_pending_salary_reviews()
        if not reviews:
            logger.info("   ✅ No pending salary reviews.")
            finish_execution(exec_id, "completed")
            return

        logger.info("   💰 Found %d pending salary review(s)", len(reviews))
        for review in reviews:
            result = await event_bus.publish("salary_review", {
                "review_id":                   review.get("id"),
                "employee_id":                 str(review.get("employee_id", "")),
                "employee_name":               review.get("employee_name", ""),
                "current_salary_egp":          float(review.get("current_salary_egp", 0)),
                "requested_increment_pct":     float(review.get("requested_increment_pct", 0.10)),
                "market_median_egp":           float(review.get("market_median_egp", 0)),
                "market_gap_pct":              float(review.get("market_gap_pct", 0)),
                "months_since_last_increment": int(review.get("months_since_last_increment", 12)),
                "months_in_role":              int(review.get("months_in_role", 0)),
                "kpi_achievement":             float(review.get("kpi_achievement", 0.80)),
                "budget_utilization":          float(review.get("budget_utilization", 0.80)),
                "available_pool_egp":          float(review.get("available_pool_egp", 0)),
                "is_on_pip":                   bool(review.get("is_on_pip", False)),
                "is_on_probation":             bool(review.get("is_on_probation", False)),
                "appraisal_cycle":             review.get("appraisal_cycle", "Annual"),
                "job_level":                   review.get("job_level", "junior"),
                "salary_grade":                review.get("salary_grade", "C"),
                "department":                  review.get("department", "General"),
                "performance_score":           float(review.get("performance_score") or 0.75),
                "source":                      "scheduler",
            })
            if result == -1:
                logger.info("   ⏭️ Review #%s already processing — skipped", review.get("id"))
            else:
                logger.info("   📤 Event fired → salary_review #%s", review.get("id"))

        finish_execution(exec_id, "completed")
    except Exception as e:
        logger.error("❌ [Scheduler] Salary review scan failed: %s", e, exc_info=True)
        finish_execution(exec_id, "failed", str(e))


async def job_scan_pending_incentives() -> None:
    """⏰ Scan incentive_requests with status=pending → publish to EventBus.
    Sorts overtime_compensation first (statutory right — shortest SLA).
    """
    from core.db import get_pending_incentive_requests, start_execution, finish_execution

    logger.info("⏰ [Scheduler] Scanning pending incentive requests...")
    exec_id = start_execution("incentive_scan", "scheduler", 0)
    try:
        requests = get_pending_incentive_requests()
        if not requests:
            logger.info("   ✅ No pending incentive requests.")
            finish_execution(exec_id, "completed")
            return

        logger.info("   🏆 Found %d pending incentive request(s)", len(requests))

        # overtime_compensation first (statutory right)
        sorted_requests = sorted(
            requests,
            key=lambda r: (0 if r.get("incentive_type") == "overtime_compensation" else 1),
        )

        for req in sorted_requests:
            result = await event_bus.publish("incentive_request", {
                "incentive_id":                 req.get("id"),
                "employee_id":                  str(req.get("employee_id", "")),
                "employee_name":                req.get("employee_name", ""),
                "incentive_type":               req.get("incentive_type", "performance_bonus"),
                "requested_amount_egp":         float(req.get("requested_amount_egp", 0)),
                "kpi_achievement":              float(req.get("kpi_achievement", 0.80)),
                "performance_score":            float(req.get("performance_score", 0.75)),
                "monthly_salary_egp":           float(req.get("monthly_salary_egp", 0)),
                "tenure_months":                int(req.get("tenure_months", 0)),
                "is_on_pip":                    bool(req.get("is_on_pip", False)),
                "is_critical_talent":           bool(req.get("is_critical_talent", False)),
                "incentive_budget_remaining_egp":
                    float(req.get("incentive_budget_remaining_egp", 0)),
                "perf_trend":                   req.get("perf_trend", "stable"),
                "reason":                       req.get("reason", ""),
                "job_level":                    req.get("job_level", "junior"),
                "salary_grade":                 req.get("salary_grade", "C"),
                "department":                   req.get("department", "General"),
                "source":                       "scheduler",
            })
            if result == -1:
                logger.info("   ⏭️ Incentive #%s already processing — skipped", req.get("id"))
            else:
                logger.info(
                    "   📤 Event fired → incentive_request #%s (%s)",
                    req.get("id"), req.get("incentive_type"),
                )

        finish_execution(exec_id, "completed")
    except Exception as e:
        logger.error("❌ [Scheduler] Incentive scan failed: %s", e, exc_info=True)
        finish_execution(exec_id, "failed", str(e))


async def job_scan_pending_absences() -> None:
    """⏰ Scan absence_events with status=pending → publish to EventBus.
    Higher unexcused_count_90d = higher priority.
    """
    from core.db import get_pending_absence_events, start_execution, finish_execution

    logger.info("⏰ [Scheduler] Scanning pending absence events...")
    exec_id = start_execution("absence_scan", "scheduler", 0)
    try:
        events = get_pending_absence_events()  # already ordered by unexcused_count DESC
        if not events:
            logger.info("   ✅ No pending absence events.")
            finish_execution(exec_id, "completed")
            return

        logger.info("   🚫 Found %d pending absence event(s)", len(events))
        for event in events:
            result = await event_bus.publish("absence_event", {
                "absence_id":                   event.get("id"),
                "employee_id":                  str(event.get("employee_id", "")),
                "employee_name":                event.get("employee_name", ""),
                "absence_date":                 str(event.get("absence_date", "")),
                "absence_type_claimed":         event.get("absence_type_claimed", "unexcused"),
                "duration_hours":               float(event.get("duration_hours", 8)),
                "medical_certificate_provided": bool(event.get("medical_certificate_provided", False)),
                "prior_approval_obtained":      bool(event.get("prior_approval_obtained", False)),
                "reason":                       event.get("reason", ""),
                "total_absences_90d":           int(event.get("total_absences_90d", 0)),
                "unexcused_count_90d":          int(event.get("unexcused_count_90d", 0)),
                "late_arrivals_90d":            int(event.get("late_arrivals_90d", 0)),
                "previous_warnings":            event.get("previous_warnings", "none"),
                "performance_score":            float(event.get("performance_score") or 0.75),
                "is_on_pip":                    False,
                "job_level":                    event.get("job_level", "junior"),
                "salary_grade":                 event.get("salary_grade", "C"),
                "department":                   event.get("department", "General"),
                "source":                       "scheduler",
            })
            if result == -1:
                logger.info("   ⏭️ Absence #%s already processing — skipped", event.get("id"))
            else:
                logger.info(
                    "   📤 Event fired → absence_event #%s (employee=%s, type=%s)",
                    event.get("id"), event.get("employee_id"),
                    event.get("absence_type_claimed"),
                )

        finish_execution(exec_id, "completed")
    except Exception as e:
        logger.error("❌ [Scheduler] Absence scan failed: %s", e, exc_info=True)
        finish_execution(exec_id, "failed", str(e))


# ════════════════════════════════════════════════════════
#  HANDLER FACTORIES — Existing Domains
#
#  ✅ FIXED v5.1: Claim removed from ALL Bridge handlers.
#     Claim now belongs exclusively inside each Workflow.
#     Bridge responsibility = routing only.
# ════════════════════════════════════════════════════════

def _build_leave_handler(orchestrator):
    async def _handle_leave(event: dict) -> None:
        from core.db import (
            update_leave_and_balance,
            write_decision_audit,
            write_audit_log,
            save_decision,
            log_action,
        )

        payload    = event["payload"]
        leave_id   = payload.get("leave_id")
        event_id   = payload.get("event_id")
        employee_id_raw = payload.get("employee_id", "?")

        logger.info(
            "🤖 [Bridge] Routing leave_requested #%s → Orchestrator | employee=%s",
            leave_id, employee_id_raw,
        )

        # ✅ NO claim here — claim happens inside LeaveApprovalWorkflow
        ai_event = {"type": "leave_requested", "payload": payload}
        result   = await orchestrator.async_handle(ai_event)

        decision    = result.get("decision", "escalated")
        confidence  = float(result.get("confidence", 0.5))
        reasoning   = result.get("reason", result.get("reasoning", ""))
        leave_days  = int(payload.get("leave_days", 0))
        request_id  = result.get("request_id", "")

        logger.info(
            "   ✅ leave #%s → %s | conf=%.0f%%",
            leave_id, decision, confidence * 100,
        )

        if leave_id:
            try:
                employee_id = int(employee_id_raw) if str(employee_id_raw).isdigit() else 0
                balance_result = update_leave_and_balance(
                    leave_id    = leave_id,
                    employee_id = employee_id,
                    status      = decision,
                    notes       = reasoning[:500],
                    leave_days  = leave_days if decision == "approved" else 0,
                    performed_by = "leave_agent_v5.1",
                )
                write_decision_audit(
                    leave_id        = leave_id,
                    employee_id     = employee_id,
                    decision        = decision,
                    confidence      = confidence,
                    decision_source = result.get("model_source", "llm"),
                    old_balance     = balance_result.get("old_balance", 0),
                    new_balance     = balance_result.get("new_balance", 0),
                    model_version   = result.get("model_version", "unknown"),
                    tier            = result.get("tier", 2),
                    llm_used        = bool(result.get("llm_used", True)),
                    override_rule   = result.get("override_rule", ""),
                    request_id      = request_id,
                    flags           = result.get("ai_flags", []),
                )
            except Exception as e:
                logger.error("❌ [Bridge] leave persist failed: %s", e)

        write_audit_log(
            action       = f"leave_{decision}",
            entity       = "leaves",
            entity_id    = int(leave_id) if leave_id else 0,
            performed_by = "leave_agent_v5.1",
            details      = f"[request_id={request_id}] conf={confidence:.0%} | {reasoning[:150]}",
        )

    return _handle_leave


def _build_ticket_handler(orchestrator):
    async def _handle_ticket(event: dict) -> None:
        from core.db import update_ticket_status, write_audit_log, save_decision

        payload   = event["payload"]
        ticket_id = payload.get("ticket_id")

        logger.info("🤖 [Bridge] Routing ticket_created #%s → Orchestrator", ticket_id)

        # ✅ NO claim here — claim happens inside TicketWorkflow
        ai_event = {"type": "ticket_created", "payload": payload}
        result   = await orchestrator.async_handle(ai_event)

        decision   = result.get("decision", "escalate")
        confidence = float(result.get("confidence", 0.5))
        reasoning  = result.get("reason", result.get("reasoning", ""))

        logger.info("   ✅ ticket #%s → %s", ticket_id, decision)

        if ticket_id:
            try:
                update_ticket_status(ticket_id, decision, reasoning[:500])
            except Exception as e:
                logger.error("❌ [Bridge] ticket persist failed: %s", e)

        write_audit_log(
            action       = f"ticket_{decision}",
            entity       = "tickets",
            entity_id    = int(ticket_id) if ticket_id else 0,
            performed_by = "support_agent_v5.1",
            details      = reasoning[:300],
        )

    return _handle_ticket


def _build_lead_handler(orchestrator):
    async def _handle_lead(event: dict) -> None:
        from core.db import update_lead_status, write_audit_log, save_decision

        payload = event["payload"]
        lead_id = payload.get("lead_id")

        logger.info("🤖 [Bridge] Routing lead_added #%s → Orchestrator", lead_id)

        # ✅ NO claim here — claim happens inside LeadWorkflow
        ai_event = {"type": "lead_added", "payload": payload}
        result   = await orchestrator.async_handle(ai_event)

        decision   = result.get("decision", "follow_up")
        confidence = float(result.get("confidence", 0.5))
        reasoning  = result.get("reason", result.get("reasoning", ""))
        score      = int(result.get("score", 50))

        logger.info("   ✅ lead #%s → %s (score=%d)", lead_id, decision, score)

        if lead_id:
            try:
                update_lead_status(lead_id, decision, score, reasoning[:500])
            except Exception as e:
                logger.error("❌ [Bridge] lead persist failed: %s", e)

        write_audit_log(
            action       = f"lead_{decision}",
            entity       = "leads",
            entity_id    = int(lead_id) if lead_id else 0,
            performed_by = "crm_agent_v5.1",
            details      = reasoning[:300],
        )

    return _handle_lead


# ════════════════════════════════════════════════════════
#  HANDLER FACTORIES — HR Domain v5.1
# ════════════════════════════════════════════════════════

def _build_salary_handler(orchestrator):
    """Factory → async handler for salary_review events."""

    async def _handle_salary(event: dict) -> None:
        from core.db import (
            update_salary_review_status,
            write_hr_domain_audit,
            write_audit_log,
            save_decision,
            log_action,
        )

        payload         = event["payload"]
        review_id       = payload.get("review_id")
        event_id        = payload.get("event_id")
        employee_id_raw = payload.get("employee_id", "?")

        logger.info(
            "🤖 [Bridge] Routing salary_review #%s → Orchestrator | employee=%s",
            review_id, employee_id_raw,
        )

        # ✅ NO claim here — claim happens inside SalaryReviewWorkflow
        ai_event = {"type": "salary_review", "payload": payload}
        result   = await orchestrator.async_handle(ai_event)

        decision    = result.get("decision", "escalate_to_director")
        confidence  = float(result.get("confidence", 0.5))
        reasoning   = result.get("reason", result.get("reasoning", ""))
        llm_used    = bool(result.get("llm_used", True))
        source      = result.get("model_source", "llm")
        request_id  = result.get("request_id", payload.get("request_id", ""))
        rec_pct     = result.get("recommended_increment_pct")

        logger.info(
            "   ✅ salary_review #%s → %s | conf=%.0f%% | source=%s",
            review_id, decision, confidence * 100, source,
        )

        if not review_id:
            return

        status_map = {
            "approve_increment":    "approved",
            "escalate_to_director": "escalated",
            "defer":                "deferred",
        }
        new_status = status_map.get(decision, "escalated")

        try:
            update_salary_review_status(
                review_id       = review_id,
                status          = new_status,
                ai_decision     = decision,
                confidence      = confidence,
                reason          = reasoning[:1000],
                recommended_pct = rec_pct,
                request_id      = request_id,
            )
        except Exception as e:
            logger.error("❌ [Bridge] update_salary_review_status failed: %s", e)

        try:
            write_hr_domain_audit(
                domain          = "salary",
                entity_id       = review_id,
                employee_id     = int(employee_id_raw) if str(employee_id_raw).isdigit() else 0,
                decision        = decision,
                confidence      = confidence,
                decision_source = source,
                override_rule   = result.get("override_rule", ""),
                llm_used        = llm_used,
                request_id      = request_id,
                flags           = result.get("flags", result.get("ai_flags", [])),
                extra_data      = {"recommended_pct": rec_pct},
            )
        except Exception as e:
            logger.warning("   ⚠️ write_hr_domain_audit (salary) failed: %s", e)

        try:
            save_decision({
                "agent_type":   "salary_agent_v5.1",
                "entity":       "salary_reviews",
                "entity_id":    int(review_id),
                "event_id":     event_id,
                "decision":     decision,
                "confidence":   confidence,
                "reasoning":    reasoning[:500],
                "raw_response": str(result)[:1000],
            })
        except Exception as e:
            logger.warning("   ⚠️ save_decision (salary) failed: %s", e)

        write_audit_log(
            action       = f"salary_{decision}",
            entity       = "salary_reviews",
            entity_id    = int(review_id),
            performed_by = "salary_agent_v5.1",
            details      = (
                f"[request_id={request_id}] source={source} | "
                f"conf={confidence:.0%} | rec_pct={rec_pct} | {reasoning[:150]}"
            ),
        )

    return _handle_salary


def _build_incentive_handler(orchestrator):
    """Factory → async handler for incentive_request events."""

    async def _handle_incentive(event: dict) -> None:
        from core.db import (
            update_incentive_status,
            write_hr_domain_audit,
            write_audit_log,
            save_decision,
        )

        payload         = event["payload"]
        incentive_id    = payload.get("incentive_id")
        event_id        = payload.get("event_id")
        employee_id_raw = payload.get("employee_id", "?")
        incentive_type  = payload.get("incentive_type", "performance_bonus")

        logger.info(
            "🤖 [Bridge] Routing incentive_request #%s (%s) → Orchestrator | employee=%s",
            incentive_id, incentive_type, employee_id_raw,
        )

        # ✅ NO claim here — claim happens inside IncentiveWorkflow
        ai_event = {"type": "incentive_request", "payload": payload}
        result   = await orchestrator.async_handle(ai_event)

        decision      = result.get("decision", "deny_bonus")
        confidence    = float(result.get("confidence", 0.5))
        reasoning     = result.get("reason", result.get("reasoning", ""))
        llm_used      = bool(result.get("llm_used", True))
        source        = result.get("model_source", "llm")
        request_id    = result.get("request_id", payload.get("request_id", ""))
        approved_amt  = result.get("approved_amount_egp")

        logger.info(
            "   ✅ incentive #%s (%s) → %s | conf=%.0f%%",
            incentive_id, incentive_type, decision, confidence * 100,
        )

        if not incentive_id:
            return

        status_map = {
            "approve_bonus":        "approved",
            "deny_bonus":           "rejected",
            "partial_bonus":        "partial",
            "escalate_to_director": "escalated",
            "escalate_to_ceo":      "escalated_ceo",
        }
        new_status = status_map.get(decision, "escalated")

        try:
            update_incentive_status(
                request_id_int  = incentive_id,
                status          = new_status,
                ai_decision     = decision,
                confidence      = confidence,
                reason          = reasoning[:1000],
                approved_amount = approved_amt,
                request_id      = request_id,
            )
        except Exception as e:
            logger.error("❌ [Bridge] update_incentive_status failed: %s", e)

        try:
            write_hr_domain_audit(
                domain          = "incentive",
                entity_id       = incentive_id,
                employee_id     = int(employee_id_raw) if str(employee_id_raw).isdigit() else 0,
                decision        = decision,
                confidence      = confidence,
                decision_source = source,
                override_rule   = result.get("override_rule", ""),
                llm_used        = llm_used,
                request_id      = request_id,
                flags           = result.get("flags", result.get("ai_flags", [])),
                extra_data      = {
                    "incentive_type":  incentive_type,
                    "approved_amount": approved_amt,
                },
            )
        except Exception as e:
            logger.warning("   ⚠️ write_hr_domain_audit (incentive) failed: %s", e)

        try:
            save_decision({
                "agent_type":   "incentive_agent_v5.1",
                "entity":       "incentive_requests",
                "entity_id":    int(incentive_id),
                "event_id":     event_id,
                "decision":     decision,
                "confidence":   confidence,
                "reasoning":    reasoning[:500],
                "raw_response": str(result)[:1000],
            })
        except Exception as e:
            logger.warning("   ⚠️ save_decision (incentive) failed: %s", e)

        write_audit_log(
            action       = f"incentive_{decision}",
            entity       = "incentive_requests",
            entity_id    = int(incentive_id),
            performed_by = "incentive_agent_v5.1",
            details      = (
                f"[request_id={request_id}] type={incentive_type} | "
                f"conf={confidence:.0%} | approved={approved_amt} | {reasoning[:150]}"
            ),
        )

    return _handle_incentive


def _build_absence_handler(orchestrator):
    """Factory → async handler for absence_event events."""

    async def _handle_absence(event: dict) -> None:
        from core.db import (
            update_absence_event_status,
            write_hr_domain_audit,
            write_audit_log,
            save_decision,
            log_action,
        )

        payload         = event["payload"]
        absence_id      = payload.get("absence_id")
        event_id        = payload.get("event_id")
        employee_id_raw = payload.get("employee_id", "?")
        absence_type    = payload.get("absence_type_claimed", "unexcused")

        logger.info(
            "🤖 [Bridge] Routing absence_event #%s (%s) → Orchestrator | employee=%s",
            absence_id, absence_type, employee_id_raw,
        )

        # ✅ NO claim here — claim happens inside AbsenceWorkflow
        ai_event = {"type": "absence_event", "payload": payload}
        result   = await orchestrator.async_handle(ai_event)

        decision            = result.get("decision", "record_only")
        classification      = result.get("classification", absence_type)
        confidence          = float(result.get("confidence", 0.5))
        reasoning           = result.get("reason", result.get("reasoning", ""))
        llm_used            = bool(result.get("llm_used", True))
        source              = result.get("model_source", "llm")
        request_id          = result.get("request_id", payload.get("request_id", ""))
        payroll_deduct      = float(result.get("payroll_deduction_days", 0))
        escalation_required = bool(result.get("escalation_required", False))

        logger.info(
            "   ✅ absence #%s (%s) → %s | class=%s | conf=%.0f%%",
            absence_id, absence_type, decision, classification, confidence * 100,
        )

        if not absence_id:
            return

        status_map = {
            "record_only":             "recorded",
            "written_warning":         "warned_written",
            "formal_warning":          "warned_formal",
            "deduct_single_day":       "deducted",
            "deduct_double_day":       "deducted_double",
            "escalate_to_hr_director": "escalated",
            "suspension_review":       "suspension_review",
            "termination_review":      "termination_review",
        }
        new_status = status_map.get(decision, "recorded")

        try:
            update_absence_event_status(
                event_id               = absence_id,
                status                 = new_status,
                ai_decision            = decision,
                ai_classification      = classification,
                confidence             = confidence,
                reason                 = reasoning[:1000],
                payroll_deduction_days = payroll_deduct,
                escalation_required    = escalation_required,
                request_id             = request_id,
            )
        except Exception as e:
            logger.error("❌ [Bridge] update_absence_event_status failed: %s", e)

        try:
            write_hr_domain_audit(
                domain          = "absence",
                entity_id       = absence_id,
                employee_id     = int(employee_id_raw) if str(employee_id_raw).isdigit() else 0,
                decision        = decision,
                confidence      = confidence,
                decision_source = source,
                override_rule   = result.get("override_rule", ""),
                llm_used        = llm_used,
                request_id      = request_id,
                flags           = result.get("flags", result.get("ai_flags", [])),
                extra_data      = {
                    "classification":      classification,
                    "payroll_deduction":   payroll_deduct,
                    "escalation_required": escalation_required,
                    "absence_date":        payload.get("absence_date"),
                },
            )
        except Exception as e:
            logger.warning("   ⚠️ write_hr_domain_audit (absence) failed: %s", e)

        try:
            save_decision({
                "agent_type":   "absence_agent_v5.1",
                "entity":       "absence_events",
                "entity_id":    int(absence_id),
                "event_id":     event_id,
                "decision":     decision,
                "confidence":   confidence,
                "reasoning":    reasoning[:500],
                "raw_response": str(result)[:1000],
            })
        except Exception as e:
            logger.warning("   ⚠️ save_decision (absence) failed: %s", e)

        try:
            log_action({
                "action_type":  f"absence_{decision}",
                "entity":       "absence_events",
                "entity_id":    int(absence_id),
                "performed_by": "absence_agent_v5.1",
                "result":       decision,
                "details":      reasoning[:300],
            })
        except Exception as e:
            logger.warning("   ⚠️ log_action (absence) failed: %s", e)

        write_audit_log(
            action       = f"absence_{decision}",
            entity       = "absence_events",
            entity_id    = int(absence_id),
            performed_by = "absence_agent_v5.1",
            details      = (
                f"[request_id={request_id}] class={classification} | "
                f"conf={confidence:.0%} | deduct={payroll_deduct}d | "
                f"escalate={escalation_required} | {reasoning[:150]}"
            ),
        )

    return _handle_absence