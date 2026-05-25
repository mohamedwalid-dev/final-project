"""
trigger.py — Trigger Engine v6.0 (MongoDB/Motor)
==================================================
File: app/core/trigger.py

v6.0 Changes (Migration: MySQL → MongoDB):
    ✅ job_scan_pending_leaves()         ← HRDB.get_pending_leaves()     بدل SQL
    ✅ job_scan_pending_tickets()        ← FinanceDB / direct Motor query بدل SQL
    ✅ job_scan_new_leads()              ← direct Motor query             بدل SQL
    ✅ job_process_event_queue()         ← MongoEventQueue.claim_batch()  بدل SQL
    ✅ job_scan_pending_salary_reviews() ← HRDB.get_pending_salary_reviews()
    ✅ job_scan_pending_incentives()     ← HRDB.get_pending_incentive_requests()
    ✅ job_scan_pending_absences()       ← HRDB.get_pending_absence_events()
    ✅ start_execution() / finish_execution() → MongoDB "agent_executions" collection
    ✅ كل import لـ core.db اتشال تماماً
    ✅ get_finance_db() + get_hr_db() singletons من core.mongo_connect

ARCHITECTURE RULE (unchanged):
    Bridge  = routing only   → NO claim here
    Workflow = claim + decide → claim lives inside each Workflow
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from core.event_bus import event_bus

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Scan intervals (seconds) ──────────────────────────────────────────────────
LEAVE_SCAN_SEC     = int(os.getenv("LEAVE_SCAN_INTERVAL_SEC",    30))
TICKET_SCAN_SEC    = int(os.getenv("TICKET_SCAN_INTERVAL_SEC",   60))
LEAD_SCAN_SEC      = int(os.getenv("LEAD_SCAN_INTERVAL_SEC",    120))
EVENT_QUEUE_SEC    = int(os.getenv("EVENT_QUEUE_INTERVAL_SEC",   15))
SALARY_SCAN_SEC    = int(os.getenv("SALARY_SCAN_INTERVAL_SEC",  600))
INCENTIVE_SCAN_SEC = int(os.getenv("INCENTIVE_SCAN_INTERVAL_SEC", 600))
ABSENCE_SCAN_SEC   = int(os.getenv("ABSENCE_SCAN_INTERVAL_SEC", 300))

_scheduler: Optional[AsyncIOScheduler] = None


# ════════════════════════════════════════════════════════════════════════════
# 🛠  EXECUTION TRACKING (MongoDB بدل MySQL)
# ════════════════════════════════════════════════════════════════════════════

async def _start_execution(job_name: str, triggered_by: str, entity_id: int = 0) -> str:
    """
    بدل start_execution() من core.db (MySQL):
    بنعمل insert في "agent_executions" collection.
    بيرجع exec_id (string).
    """
    exec_id = f"exec-{uuid.uuid4().hex[:12]}"
    try:
        from core.mongo_connect import get_finance_db
        db = get_finance_db()
        await db.db["agent_executions"].insert_one({
            "exec_id":      exec_id,
            "job_name":     job_name,
            "triggered_by": triggered_by,
            "entity_id":    entity_id,
            "status":       "running",
            "started_at":   _utcnow(),
            "finished_at":  None,
            "error":        None,
        })
    except Exception as e:
        logger.debug("_start_execution failed (non-critical): %s", e)
    return exec_id


async def _finish_execution(exec_id: str, status: str, error: str = "") -> None:
    """
    بدل finish_execution() من core.db:
    update_one على "agent_executions".
    """
    try:
        from core.mongo_connect import get_finance_db
        db = get_finance_db()
        await db.db["agent_executions"].update_one(
            {"exec_id": exec_id},
            {
                "$set": {
                    "status":      status,
                    "finished_at": _utcnow(),
                    "error":       error[:500] if error else None,
                }
            },
        )
    except Exception as e:
        logger.debug("_finish_execution failed (non-critical): %s", e)


# ════════════════════════════════════════════════════════════════════════════
#  SCHEDULER CONTROL
# ════════════════════════════════════════════════════════════════════════════

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

    jobs = [
        (job_scan_pending_leaves,        LEAVE_SCAN_SEC,     "scan_leaves",          "[HR] Scan pending leaves",             60),
        (job_scan_pending_tickets,       TICKET_SCAN_SEC,    "scan_tickets",         "[Support] Scan pending tickets",       60),
        (job_scan_new_leads,             LEAD_SCAN_SEC,      "scan_leads",           "[CRM] Scan new leads",                120),
        (job_process_event_queue,        EVENT_QUEUE_SEC,    "process_event_queue",  "[System] Process event queue",         30),
        (job_scan_pending_salary_reviews,SALARY_SCAN_SEC,    "scan_salary_reviews",  "[HR] Scan pending salary reviews",    120),
        (job_scan_pending_incentives,    INCENTIVE_SCAN_SEC, "scan_incentives",      "[HR] Scan pending incentive requests",120),
        (job_scan_pending_absences,      ABSENCE_SCAN_SEC,   "scan_absences",        "[HR] Scan pending absence events",     60),
        (job_scan_overdue_invoices,      INVOICE_SCAN_SEC,   "scan_overdue_invoices","[Finance] Scan overdue invoices",     120),
        (job_scan_new_invoices,          NEW_INVOICE_SCAN_SEC,"scan_new_invoices",   "[Finance] Scan new invoices",         120),
    ]

    for func, interval, job_id, name, grace in jobs:
        _scheduler.add_job(
            func,
            trigger            = IntervalTrigger(seconds=interval),
            id                 = job_id,
            name               = name,
            max_instances      = 1,
            coalesce           = True,
            misfire_grace_time = grace,
        )

    _scheduler.start()
    logger.info(
        "✅ Trigger Engine v6.0 started — %d jobs scheduled",
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


# ════════════════════════════════════════════════════════════════════════════
#  EVENT BUS HANDLER REGISTRATION
# ════════════════════════════════════════════════════════════════════════════

def register_orchestrator_handlers(orchestrator) -> None:
    event_bus.subscribe("leave_requested",   _build_leave_handler(orchestrator))
    event_bus.subscribe("ticket_created",    _build_ticket_handler(orchestrator))
    event_bus.subscribe("lead_added",        _build_lead_handler(orchestrator))
    event_bus.subscribe("salary_review",     _build_salary_handler(orchestrator))
    event_bus.subscribe("incentive_request", _build_incentive_handler(orchestrator))
    event_bus.subscribe("absence_event",     _build_absence_handler(orchestrator))

    logger.info(
        "✅ [Bridge] All handlers registered — "
        "leaves / tickets / leads / salary / incentive / absence"
    )


# ════════════════════════════════════════════════════════════════════════════
# ⏰  SCHEDULER JOBS — MONGODB VERSIONS
# ════════════════════════════════════════════════════════════════════════════

async def job_scan_pending_leaves() -> None:
    """
    بدل: from core.db import get_pending_leaves
    دلوقتي: HRDB.get_pending_leaves() (Motor async)
    """
    logger.info("⏰ [Scheduler] Scanning pending leaves...")
    exec_id = await _start_execution("leave_scan", "scheduler", 0)
    try:
        from core.mongo_connect import get_hr_db
        hr_db  = get_hr_db()
        leaves = await hr_db.get_pending_leaves()

        if not leaves:
            logger.info("   ✅ No pending leaves.")
            await _finish_execution(exec_id, "completed")
            return

        logger.info("   📋 Found %d pending leave(s)", len(leaves))
        for leave in leaves:
            result = await event_bus.publish("leave_requested", {
                "leave_id":      str(leave.get("_id", leave.get("id", ""))),
                "employee_id":   str(leave.get("employee_id", "")),
                "employee_name": leave.get("employee_name", ""),
                "leave_days":    leave.get("leave_days", 1),
                "leave_type":    leave.get("leave_type", "annual"),
                "leave_balance": int(leave.get("leave_balance") or 0),
                "reason":        leave.get("reason", ""),
                "source":        "scheduler",
            })
            if result == -1:
                logger.info("   ⏭️ Leave already processing — skipped")

        await _finish_execution(exec_id, "completed")
    except Exception as e:
        logger.error("❌ [Scheduler] Leave scan failed: %s", e, exc_info=True)
        await _finish_execution(exec_id, "failed", str(e))


async def job_scan_pending_tickets() -> None:
    """
    بدل: from core.db import get_pending_tickets
    دلوقتي: Motor query على "support_tickets" collection مباشرةً.
    """
    logger.info("⏰ [Scheduler] Scanning pending tickets...")
    exec_id = await _start_execution("ticket_scan", "scheduler", 0)
    try:
        from core.mongo_connect import get_finance_db
        db      = get_finance_db()
        cursor  = db.db["support_tickets"].find({"status": "open"}).sort("created_at", 1).limit(200)
        tickets = await cursor.to_list(None)

        if not tickets:
            await _finish_execution(exec_id, "completed")
            return

        logger.info("   🎫 Found %d pending ticket(s)", len(tickets))
        for ticket in tickets:
            await event_bus.publish("ticket_created", {
                "ticket_id":     str(ticket.get("_id")),
                "customer_id":   str(ticket.get("customer_id", "")),
                "customer_name": ticket.get("customer_name", ""),
                "priority":      ticket.get("priority", "medium"),
                "category":      ticket.get("category", "general"),
                "message":       ticket.get("message", ""),
                "source":        "scheduler",
            })

        await _finish_execution(exec_id, "completed")
    except Exception as e:
        logger.error("❌ [Scheduler] Ticket scan failed: %s", e, exc_info=True)
        await _finish_execution(exec_id, "failed", str(e))


async def job_scan_new_leads() -> None:
    """
    بدل: from core.db import get_new_leads
    دلوقتي: Motor query على "leads" collection.
    """
    logger.info("⏰ [Scheduler] Scanning new leads...")
    exec_id = await _start_execution("lead_scan", "scheduler", 0)
    try:
        from core.mongo_connect import get_finance_db
        db     = get_finance_db()
        cursor = db.db["leads"].find({"status": "new"}).sort("created_at", 1).limit(200)
        leads  = await cursor.to_list(None)

        if not leads:
            await _finish_execution(exec_id, "completed")
            return

        logger.info("   💼 Found %d new lead(s)", len(leads))
        for lead in leads:
            await event_bus.publish("lead_added", {
                "lead_id": str(lead.get("_id")),
                "name":    lead.get("name", ""),
                "email":   lead.get("email", ""),
                "source":  lead.get("source", "unknown"),
                "notes":   lead.get("notes", ""),
            })

        await _finish_execution(exec_id, "completed")
    except Exception as e:
        logger.error("❌ [Scheduler] Lead scan failed: %s", e, exc_info=True)
        await _finish_execution(exec_id, "failed", str(e))


async def job_process_event_queue() -> None:
    """
    بدل: from core.db import get_pending_events, mark_event_done
    دلوقتي: MongoEventQueue.claim_batch() + ack()
    """
    logger.debug("⏰ [Scheduler] Processing event queue...")
    try:
        from core.event_bus_persistent import MongoEventQueue
        queue  = MongoEventQueue()
        rows   = await queue.claim_batch(batch_size=20)

        if not rows:
            return

        import json
        logger.info("   📥 Processing %d event(s) from queue", len(rows))
        for row in rows:
            event_type  = row.get("event_type", "")
            doc_id      = row.get("_id")
            raw_payload = row.get("payload", "{}")

            try:
                payload = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
            except Exception:
                payload = {}

            result = await event_bus.publish(event_type, payload)
            if result == -1:
                logger.debug("   ⏭️ Event (%s) already in cache — skipped", event_type)
            else:
                logger.info("   📤 Event (%s) → published", event_type)
                await queue.ack(doc_id)

    except Exception as e:
        logger.error("❌ [Scheduler] Event queue processing failed: %s", e, exc_info=True)


async def job_scan_pending_salary_reviews() -> None:
    """
    بدل: from core.db import get_pending_salary_reviews
    دلوقتي: HRDB.get_pending_salary_reviews()
    """
    logger.info("⏰ [Scheduler] Scanning pending salary reviews...")
    exec_id = await _start_execution("salary_review_scan", "scheduler", 0)
    try:
        from core.mongo_connect import get_hr_db
        hr_db   = get_hr_db()
        reviews = await hr_db.get_pending_salary_reviews()

        if not reviews:
            logger.info("   ✅ No pending salary reviews.")
            await _finish_execution(exec_id, "completed")
            return

        logger.info("   💰 Found %d pending salary review(s)", len(reviews))
        for review in reviews:
            result = await event_bus.publish("salary_review", {
                "review_id":                   str(review.get("_id", "")),
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
                logger.info("   ⏭️ Review already processing — skipped")
            else:
                logger.info("   📤 Event fired → salary_review %s", review.get("_id"))

        await _finish_execution(exec_id, "completed")
    except Exception as e:
        logger.error("❌ [Scheduler] Salary review scan failed: %s", e, exc_info=True)
        await _finish_execution(exec_id, "failed", str(e))


async def job_scan_pending_incentives() -> None:
    """
    بدل: from core.db import get_pending_incentive_requests
    دلوقتي: HRDB.get_pending_incentive_requests()
    overtime_compensation يجي أول (statutory right).
    """
    logger.info("⏰ [Scheduler] Scanning pending incentive requests...")
    exec_id = await _start_execution("incentive_scan", "scheduler", 0)
    try:
        from core.mongo_connect import get_hr_db
        hr_db    = get_hr_db()
        requests = await hr_db.get_pending_incentive_requests()

        if not requests:
            logger.info("   ✅ No pending incentive requests.")
            await _finish_execution(exec_id, "completed")
            return

        logger.info("   🏆 Found %d pending incentive request(s)", len(requests))

        # overtime_compensation first
        sorted_requests = sorted(
            requests,
            key=lambda r: (0 if r.get("incentive_type") == "overtime_compensation" else 1),
        )

        for req in sorted_requests:
            result = await event_bus.publish("incentive_request", {
                "incentive_id":                  str(req.get("_id", "")),
                "employee_id":                   str(req.get("employee_id", "")),
                "employee_name":                 req.get("employee_name", ""),
                "incentive_type":                req.get("incentive_type", "performance_bonus"),
                "requested_amount_egp":          float(req.get("requested_amount_egp", 0)),
                "kpi_achievement":               float(req.get("kpi_achievement", 0.80)),
                "performance_score":             float(req.get("performance_score", 0.75)),
                "monthly_salary_egp":            float(req.get("monthly_salary_egp", 0)),
                "tenure_months":                 int(req.get("tenure_months", 0)),
                "is_on_pip":                     bool(req.get("is_on_pip", False)),
                "is_critical_talent":            bool(req.get("is_critical_talent", False)),
                "incentive_budget_remaining_egp": float(req.get("incentive_budget_remaining_egp", 0)),
                "perf_trend":                    req.get("perf_trend", "stable"),
                "reason":                        req.get("reason", ""),
                "job_level":                     req.get("job_level", "junior"),
                "salary_grade":                  req.get("salary_grade", "C"),
                "department":                    req.get("department", "General"),
                "source":                        "scheduler",
            })
            if result == -1:
                logger.info("   ⏭️ Incentive already processing — skipped")
            else:
                logger.info(
                    "   📤 Event fired → incentive_request %s (%s)",
                    req.get("_id"), req.get("incentive_type"),
                )

        await _finish_execution(exec_id, "completed")
    except Exception as e:
        logger.error("❌ [Scheduler] Incentive scan failed: %s", e, exc_info=True)
        await _finish_execution(exec_id, "failed", str(e))


async def job_scan_pending_absences() -> None:
    """
    بدل: from core.db import get_pending_absence_events
    دلوقتي: HRDB.get_pending_absence_events()
    """
    logger.info("⏰ [Scheduler] Scanning pending absence events...")
    exec_id = await _start_execution("absence_scan", "scheduler", 0)
    try:
        from core.mongo_connect import get_hr_db
        hr_db  = get_hr_db()
        events = await hr_db.get_pending_absence_events()

        if not events:
            logger.info("   ✅ No pending absence events.")
            await _finish_execution(exec_id, "completed")
            return

        logger.info("   🚫 Found %d pending absence event(s)", len(events))
        for event in events:
            result = await event_bus.publish("absence_event", {
                "absence_id":                   str(event.get("_id", "")),
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
                "is_on_pip":                    bool(event.get("is_on_pip", False)),
                "job_level":                    event.get("job_level", "junior"),
                "salary_grade":                 event.get("salary_grade", "C"),
                "department":                   event.get("department", "General"),
                "source":                       "scheduler",
            })
            if result == -1:
                logger.info("   ⏭️ Absence already processing — skipped")
            else:
                logger.info(
                    "   📤 Event fired → absence_event %s (employee=%s, type=%s)",
                    event.get("_id"), event.get("employee_id"),
                    event.get("absence_type_claimed"),
                )

        await _finish_execution(exec_id, "completed")
    except Exception as e:
        logger.error("❌ [Scheduler] Absence scan failed: %s", e, exc_info=True)
        await _finish_execution(exec_id, "failed", str(e))


# ════════════════════════════════════════════════════════════════════════════
#  HANDLER FACTORIES
#  ✅ Bridge handlers: routing only — NO claim, NO core.db imports
#  ✅ DB persistence ← HRDB / FinanceDB Motor methods بدل SQL functions
# ════════════════════════════════════════════════════════════════════════════

def _build_leave_handler(orchestrator):
    async def _handle_leave(event: dict) -> None:
        payload         = event["payload"]
        leave_id        = payload.get("leave_id")
        employee_id_raw = payload.get("employee_id", "?")

        logger.info(
            "🤖 [Bridge] Routing leave_requested #%s → Orchestrator | employee=%s",
            leave_id, employee_id_raw,
        )

        ai_event = {"type": "leave_requested", "payload": payload}
        result   = await orchestrator.async_handle(ai_event)

        decision   = result.get("decision", "escalated")
        confidence = float(result.get("confidence", 0.5))
        reasoning  = result.get("reason", result.get("reasoning", ""))
        leave_days = int(payload.get("leave_days", 0))
        request_id = result.get("request_id", "")

        logger.info("   ✅ leave #%s → %s | conf=%.0f%%", leave_id, decision, confidence * 100)

        if leave_id:
            try:
                from core.mongo_connect import get_hr_db
                hr_db = get_hr_db()

                # Update leave status ← HRDB.update_leave_status()
                await hr_db.update_leave_status(
                    leave_id        = leave_id,
                    status          = decision,
                    ai_decision     = decision,
                    confidence      = confidence,
                    reason          = reasoning[:1000],
                    decision_source = result.get("model_source", "llm"),
                    tier            = result.get("tier", 2),
                    llm_used        = bool(result.get("llm_used", True)),
                    request_id      = request_id[:100],
                    notes           = reasoning[:500],
                )

                # Write HR audit ← HRDB.write_hr_domain_audit()
                await hr_db.write_hr_domain_audit(
                    domain          = "leave",
                    entity_id       = leave_id,
                    employee_id     = employee_id_raw,
                    decision        = decision,
                    confidence      = confidence,
                    decision_source = result.get("model_source", "llm"),
                    override_rule   = result.get("override_rule", ""),
                    llm_used        = bool(result.get("llm_used", True)),
                    execution_ms    = result.get("execution_ms", 0),
                    request_id      = request_id,
                    flags           = result.get("ai_flags", []),
                )

                # Balance audit if approved
                if decision == "approved" and leave_days > 0:
                    old_balance = int(payload.get("leave_balance", 0))
                    new_balance = max(0, old_balance - leave_days)
                    await hr_db.write_balance_audit_log(
                        employee_id    = employee_id_raw,
                        old_balance    = old_balance,
                        new_balance    = new_balance,
                        change_reason  = f"leave_approved leave_id={leave_id}",
                        leave_id       = leave_id,
                        performed_by   = "leave_agent_v6.0",
                    )

            except Exception as e:
                logger.error("❌ [Bridge] leave persist failed: %s", e)

    return _handle_leave


def _build_ticket_handler(orchestrator):
    async def _handle_ticket(event: dict) -> None:
        payload   = event["payload"]
        ticket_id = payload.get("ticket_id")

        logger.info("🤖 [Bridge] Routing ticket_created #%s → Orchestrator", ticket_id)

        ai_event = {"type": "ticket_created", "payload": payload}
        result   = await orchestrator.async_handle(ai_event)

        decision  = result.get("decision", "escalate")
        reasoning = result.get("reason", result.get("reasoning", ""))

        logger.info("   ✅ ticket #%s → %s", ticket_id, decision)

        if ticket_id:
            try:
                from core.mongo_connect import get_finance_db
                db = get_finance_db()
                from bson import ObjectId
                await db.db["support_tickets"].update_one(
                    {"_id": ObjectId(str(ticket_id))},
                    {
                        "$set": {
                            "status":      decision,
                            "ai_decision": decision,
                            "ai_reason":   reasoning[:500],
                            "updated_at":  _utcnow(),
                        }
                    },
                )
            except Exception as e:
                logger.error("❌ [Bridge] ticket persist failed: %s", e)

    return _handle_ticket


def _build_lead_handler(orchestrator):
    async def _handle_lead(event: dict) -> None:
        payload = event["payload"]
        lead_id = payload.get("lead_id")

        logger.info("🤖 [Bridge] Routing lead_added #%s → Orchestrator", lead_id)

        ai_event = {"type": "lead_added", "payload": payload}
        result   = await orchestrator.async_handle(ai_event)

        decision  = result.get("decision", "follow_up")
        reasoning = result.get("reason", result.get("reasoning", ""))
        score     = int(result.get("score", 50))

        logger.info("   ✅ lead #%s → %s (score=%d)", lead_id, decision, score)

        if lead_id:
            try:
                from core.mongo_connect import get_finance_db
                db = get_finance_db()
                from bson import ObjectId
                await db.db["leads"].update_one(
                    {"_id": ObjectId(str(lead_id))},
                    {
                        "$set": {
                            "status":      decision,
                            "ai_score":    score,
                            "ai_reason":   reasoning[:500],
                            "updated_at":  _utcnow(),
                        }
                    },
                )
            except Exception as e:
                logger.error("❌ [Bridge] lead persist failed: %s", e)

    return _handle_lead


def _build_salary_handler(orchestrator):
    async def _handle_salary(event: dict) -> None:
        payload         = event["payload"]
        review_id       = payload.get("review_id")
        employee_id_raw = payload.get("employee_id", "?")

        logger.info(
            "🤖 [Bridge] Routing salary_review #%s → Orchestrator | employee=%s",
            review_id, employee_id_raw,
        )

        ai_event = {"type": "salary_review", "payload": payload}
        result   = await orchestrator.async_handle(ai_event)

        decision   = result.get("decision", "escalate_to_director")
        confidence = float(result.get("confidence", 0.5))
        reasoning  = result.get("reason", result.get("reasoning", ""))
        request_id = result.get("request_id", payload.get("request_id", ""))
        rec_pct    = result.get("recommended_increment_pct")

        logger.info(
            "   ✅ salary_review #%s → %s | conf=%.0f%%",
            review_id, decision, confidence * 100,
        )

        if not review_id:
            return

        status_map = {
            "approve_increment":    "approved",
            "escalate_to_director": "escalated",
            "defer":                "deferred",
        }

        try:
            from core.mongo_connect import get_hr_db
            hr_db = get_hr_db()

            await hr_db.update_salary_review_status(
                review_id       = review_id,
                status          = status_map.get(decision, "escalated"),
                ai_decision     = decision,
                confidence      = confidence,
                reason          = reasoning[:1000],
                recommended_pct = rec_pct,
                request_id      = request_id,
            )

            await hr_db.write_hr_domain_audit(
                domain          = "salary",
                entity_id       = review_id,
                employee_id     = employee_id_raw,
                decision        = decision,
                confidence      = confidence,
                decision_source = result.get("model_source", "llm"),
                override_rule   = result.get("override_rule", ""),
                llm_used        = bool(result.get("llm_used", True)),
                request_id      = request_id,
                flags           = result.get("flags", result.get("ai_flags", [])),
                extra_data      = {"recommended_pct": rec_pct},
            )
        except Exception as e:
            logger.error("❌ [Bridge] salary persist failed: %s", e)

    return _handle_salary


def _build_incentive_handler(orchestrator):
    async def _handle_incentive(event: dict) -> None:
        payload         = event["payload"]
        incentive_id    = payload.get("incentive_id")
        employee_id_raw = payload.get("employee_id", "?")
        incentive_type  = payload.get("incentive_type", "performance_bonus")

        logger.info(
            "🤖 [Bridge] Routing incentive_request #%s (%s) → Orchestrator | employee=%s",
            incentive_id, incentive_type, employee_id_raw,
        )

        ai_event = {"type": "incentive_request", "payload": payload}
        result   = await orchestrator.async_handle(ai_event)

        decision     = result.get("decision", "deny_bonus")
        confidence   = float(result.get("confidence", 0.5))
        reasoning    = result.get("reason", result.get("reasoning", ""))
        request_id   = result.get("request_id", payload.get("request_id", ""))
        approved_amt = result.get("approved_amount_egp")

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

        try:
            from core.mongo_connect import get_hr_db
            hr_db = get_hr_db()

            await hr_db.update_incentive_status(
                request_id      = incentive_id,
                status          = status_map.get(decision, "escalated"),
                ai_decision     = decision,
                confidence      = confidence,
                reason          = reasoning[:1000],
                approved_amount = approved_amt,
                req_id_str      = request_id,
            )

            await hr_db.write_hr_domain_audit(
                domain          = "incentive",
                entity_id       = incentive_id,
                employee_id     = employee_id_raw,
                decision        = decision,
                confidence      = confidence,
                decision_source = result.get("model_source", "llm"),
                override_rule   = result.get("override_rule", ""),
                llm_used        = bool(result.get("llm_used", True)),
                request_id      = request_id,
                flags           = result.get("flags", result.get("ai_flags", [])),
                extra_data      = {
                    "incentive_type":  incentive_type,
                    "approved_amount": approved_amt,
                },
            )
        except Exception as e:
            logger.error("❌ [Bridge] incentive persist failed: %s", e)

    return _handle_incentive


def _build_absence_handler(orchestrator):
    async def _handle_absence(event: dict) -> None:
        payload         = event["payload"]
        absence_id      = payload.get("absence_id")
        employee_id_raw = payload.get("employee_id", "?")
        absence_type    = payload.get("absence_type_claimed", "unexcused")

        logger.info(
            "🤖 [Bridge] Routing absence_event #%s (%s) → Orchestrator | employee=%s",
            absence_id, absence_type, employee_id_raw,
        )

        ai_event = {"type": "absence_event", "payload": payload}
        result   = await orchestrator.async_handle(ai_event)

        decision            = result.get("decision", "record_only")
        classification      = result.get("classification", absence_type)
        confidence          = float(result.get("confidence", 0.5))
        reasoning           = result.get("reason", result.get("reasoning", ""))
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

        try:
            from core.mongo_connect import get_hr_db
            hr_db = get_hr_db()

            await hr_db.update_absence_event_status(
                event_id               = absence_id,
                status                 = status_map.get(decision, "recorded"),
                ai_decision            = decision,
                ai_classification      = classification,
                confidence             = confidence,
                reason                 = reasoning[:1000],
                payroll_deduction_days = payroll_deduct,
                escalation_required    = escalation_required,
                request_id             = request_id,
            )

            await hr_db.write_hr_domain_audit(
                domain          = "absence",
                entity_id       = absence_id,
                employee_id     = employee_id_raw,
                decision        = decision,
                confidence      = confidence,
                decision_source = result.get("model_source", "llm"),
                override_rule   = result.get("override_rule", ""),
                llm_used        = bool(result.get("llm_used", True)),
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
            logger.error("❌ [Bridge] absence persist failed: %s", e)

    return _handle_absence