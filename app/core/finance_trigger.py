"""
⏱️ Finance Trigger Jobs — v2.1 Production
==========================================
File: app/core/finance_trigger.py

v2.1 Changes:
    ✅ save_finance_decision() بعد AI decision حقيقي فقط
    ✅ لو event_bus.publish() رجع -1 (duplicate) → مفيش DB write خالص
    ✅ execution_ms محسوب بدقة لكل handler
    ✅ Sequence: AI → DB save → audit → metrics_bridge
    ✅ "skipped" لا يدخل finance_decisions أبداً
"""

from __future__ import annotations

import logging
import os
import time

logger = logging.getLogger(__name__)

INVOICE_SCAN_SEC     = int(os.getenv("INVOICE_SCAN_INTERVAL_SEC", 300))
NEW_INVOICE_SCAN_SEC = int(os.getenv("NEW_INVOICE_SCAN_INTERVAL_SEC", 600))


async def job_scan_overdue_invoices() -> None:
    """Scan overdue invoices → publish invoice_overdue events."""
    from core.db import start_execution, finish_execution
    from core.finance_db import get_overdue_invoices
    from core.event_bus import event_bus

    logger.info("⏰ [Finance Scheduler] Scanning overdue invoices...")
    exec_id        = start_execution("invoice_overdue_scan", "scheduler", 0)
    invoices_found = 0
    invoices_fired = 0

    try:
        invoices       = get_overdue_invoices(min_days=1)
        invoices_found = len(invoices)

        if not invoices:
            logger.info("   ✅ No overdue invoices found.")
            finish_execution(exec_id, "completed")
            return

        logger.info("   💰 Found %d overdue invoice(s)", invoices_found)

        for invoice in invoices:
            overdue_days = int(invoice.get("overdue_days_calc") or 0)
            result = await event_bus.publish("invoice_overdue", {
                "invoice_id":       invoice.get("id"),
                "customer_id":      invoice.get("customer_id"),
                "customer_name":    invoice.get("customer_name", ""),
                "amount":           float(invoice.get("amount", 0)),
                "due_date":         str(invoice.get("due_date", "")),
                "overdue_days":     overdue_days,
                "credit_score":     float(invoice.get("credit_score") or 650),
                "industry":         invoice.get("industry", "unknown"),
                "service_status":   invoice.get("service_status", "active"),
                "is_disputed":      bool(invoice.get("is_disputed", False)),
                "has_payment_plan": bool(invoice.get("collection_strategy") == "payment_plan"),
                "collection_notes": invoice.get("ai_decision_reason", ""),
                "source":           "scheduler",
            })

            if result == -1:
                # ✅ v2.1: Duplicate suppressed — NO DB write
                logger.debug(
                    "   ⏭️ Invoice #%s duplicate suppressed — no DB write",
                    invoice.get("id"),
                )
            else:
                invoices_fired += 1
                logger.info(
                    "   📤 Event fired → invoice_overdue #%s (%d days, %s EGP)",
                    invoice.get("id"), overdue_days, invoice.get("amount"),
                )

        try:
            from core.finance_metrics_bridge import metrics_bridge
            await metrics_bridge.on_scheduler_scan(
                scan_type      = "overdue",
                invoices_found = invoices_found,
                invoices_fired = invoices_fired,
            )
        except Exception as e:
            logger.debug("metrics_bridge scheduler scan push failed: %s", e)

        finish_execution(exec_id, "completed")

    except Exception as e:
        logger.error("❌ [Finance Scheduler] Overdue scan failed: %s", e, exc_info=True)
        finish_execution(exec_id, "failed", str(e))


async def job_scan_new_invoices() -> None:
    """Scan new invoices that haven't been risk-assessed yet."""
    from core.finance_db import start_execution, finish_execution, get_db
    from core.event_bus import event_bus
    from core.finance_db import (                  # Finance-specific functions
    update_invoice_status,
    save_finance_decision,
    write_finance_audit,
)

    logger.info("⏰ [Finance Scheduler] Scanning new invoices...")
    exec_id        = start_execution("new_invoice_scan", "scheduler", 0)
    invoices_found = 0
    invoices_fired = 0

    try:
        with get_db() as (_, cur):
            cur.execute("""
                SELECT i.*,
                       c.name AS customer_name,
                       c.credit_score,
                       c.industry
                FROM invoices i
                LEFT JOIN customers c ON c.id = i.customer_id
                WHERE i.status = 'pending'
                  AND (i.ai_risk_score IS NULL OR i.ai_risk_score = 0)
                  AND i.created_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
                ORDER BY i.created_at DESC
                LIMIT 50
            """)
            invoices = cur.fetchall()

        invoices_found = len(invoices)
        if not invoices:
            logger.info("   ✅ No new unassessed invoices.")
            finish_execution(exec_id, "completed")
            return

        logger.info("   🧾 Found %d new invoice(s) to assess", invoices_found)

        for invoice in invoices:
            result = await event_bus.publish("invoice_created", {
                "invoice_id":    invoice.get("id"),
                "customer_id":   invoice.get("customer_id"),
                "customer_name": invoice.get("customer_name", ""),
                "amount":        float(invoice.get("amount", 0)),
                "due_date":      str(invoice.get("due_date", "")),
                "overdue_days":  0,
                "credit_score":  float(invoice.get("credit_score") or 650),
                "industry":      invoice.get("industry", "unknown"),
                "source":        "scheduler",
            })
            if result != -1:
                invoices_fired += 1

        try:
            from core.finance_metrics_bridge import metrics_bridge
            await metrics_bridge.on_scheduler_scan(
                scan_type      = "new_invoices",
                invoices_found = invoices_found,
                invoices_fired = invoices_fired,
            )
        except Exception as e:
            logger.debug("metrics_bridge new invoice scan push failed: %s", e)

        finish_execution(exec_id, "completed")

    except Exception as e:
        logger.error("❌ [Finance Scheduler] New invoice scan failed: %s", e, exc_info=True)
        finish_execution(exec_id, "failed", str(e))


def register_finance_handlers(orchestrator) -> None:
    """Register all finance event handlers to EventBus."""
    from core.event_bus import event_bus

    event_bus.subscribe("invoice_overdue",  _build_invoice_overdue_handler(orchestrator))
    event_bus.subscribe("invoice_created",  _build_new_invoice_handler(orchestrator))
    event_bus.subscribe("payment_received", _build_payment_handler(orchestrator))

    logger.info(
        "✅ [Finance Bridge] Handlers registered — "
        "invoice_overdue / invoice_created / payment_received"
    )


def _build_invoice_overdue_handler(orchestrator):
    """
    ✅ v2.1: save_finance_decision() called only after real AI decision.
    Sequence: AI → DB save → audit → metrics_bridge
    """
    async def _handle_overdue(event: dict) -> None:
        from core.db import write_audit_log
        from core.finance_db import save_finance_decision

        payload     = event["payload"]
        invoice_id  = payload.get("invoice_id")
        event_id    = payload.get("event_id")
        customer_id = payload.get("customer_id", "?")

        logger.info(
            "🤖 [Finance Bridge] invoice_overdue #%s → Orchestrator | customer=%s",
            invoice_id, customer_id,
        )

        # ── 0. AI Decision ────────────────────────────────────────────────────
        t_start      = time.perf_counter()
        result       = await orchestrator.async_handle({"type": "invoice_overdue", "payload": payload})
        execution_ms = int((time.perf_counter() - t_start) * 1000)

        decision    = result.get("decision", "soft_follow_up")
        confidence  = float(result.get("confidence", 0.5))
        risk_score  = float(result.get("risk_score", 0.5))
        reasoning   = result.get("reason", result.get("reasoning", ""))
        request_id  = result.get("request_id", "")
        action_plan = result.get("action_plan", [])

        logger.info(
            "   ✅ #%s → %s | risk=%.0f%% | action=%s | %dms",
            invoice_id, decision, risk_score * 100,
            result.get("primary_action"), execution_ms,
        )

        # ── 1. Save to DB ─────────────────────────────────────────────────────
        try:
            saved_id = save_finance_decision({
                "agent_type":   "finance_agent_v2.1",
                "entity":       "invoices",
                "entity_id":    int(invoice_id) if invoice_id else 0,
                "event_id":     event_id,
                "decision":     decision,
                "confidence":   confidence,
                "risk_score":   risk_score,
                "reasoning":    reasoning,
                "action_plan":  str(action_plan),
                "execution_ms": execution_ms,
                "request_id":   request_id,
            })
            logger.info("   💾 Saved → finance_decisions #%d", saved_id or 0)
        except Exception as e:
            logger.error("   ❌ save_finance_decision failed: %s", e)

        # ── 2. Audit ──────────────────────────────────────────────────────────
        try:
            write_audit_log(
                action       = f"invoice_{decision}",
                entity       = "invoices",
                entity_id    = int(invoice_id) if invoice_id else 0,
                performed_by = "finance_agent_v2.1",
                details      = (
                    f"[request_id={request_id}] risk={risk_score:.0%} | "
                    f"action={result.get('primary_action')} | {reasoning[:150]}"
                ),
            )
        except Exception as e:
            logger.debug("write_audit_log failed: %s", e)

        # ── 3. Metrics bridge ─────────────────────────────────────────────────
        try:
            from core.finance_metrics_bridge import metrics_bridge
            await metrics_bridge.on_invoice_decision(
                invoice_id   = invoice_id,
                decision     = decision,
                risk_score   = risk_score,
                confidence   = confidence,
                execution_ms = execution_ms,
            )
        except Exception as e:
            logger.debug("metrics_bridge.on_invoice_decision failed: %s", e)

    return _handle_overdue


def _build_new_invoice_handler(orchestrator):
    async def _handle_new(event: dict) -> None:
        from core.db import write_audit_log
        from core.finance_db import save_finance_decision

        payload    = event["payload"]
        invoice_id = payload.get("invoice_id")
        event_id   = payload.get("event_id")

        logger.info("🤖 [Finance Bridge] invoice_created #%s → Orchestrator", invoice_id)

        t_start      = time.perf_counter()
        result       = await orchestrator.async_handle({"type": "invoice_created", "payload": payload})
        execution_ms = int((time.perf_counter() - t_start) * 1000)

        decision    = result.get("decision", "invoice_registered")
        confidence  = float(result.get("confidence", 0.9))
        risk_score  = float(result.get("risk_score", 0.0))
        reasoning   = result.get("reason", "")
        request_id  = result.get("request_id", "")
        action_plan = result.get("action_plan", [])

        logger.info(
            "   ✅ #%s assessed | strategy=%s | risk=%.0f%% | %dms",
            invoice_id, result.get("collection_strategy"), risk_score * 100, execution_ms,
        )

        try:
            saved_id = save_finance_decision({
                "agent_type":   "finance_agent_v2.1",
                "entity":       "invoices",
                "entity_id":    int(invoice_id) if invoice_id else 0,
                "event_id":     event_id,
                "decision":     decision,
                "confidence":   confidence,
                "risk_score":   risk_score,
                "reasoning":    reasoning,
                "action_plan":  str(action_plan),
                "execution_ms": execution_ms,
                "request_id":   request_id,
            })
            logger.info("   💾 Saved → finance_decisions #%d", saved_id or 0)
        except Exception as e:
            logger.error("   ❌ save_finance_decision failed: %s", e)

        try:
            write_audit_log(
                action       = "invoice_risk_assessed",
                entity       = "invoices",
                entity_id    = int(invoice_id) if invoice_id else 0,
                performed_by = "finance_agent_v2.1",
                details      = (
                    f"strategy={result.get('collection_strategy')} | "
                    f"risk={risk_score:.0%} | [request_id={request_id}]"
                ),
            )
        except Exception as e:
            logger.debug("write_audit_log failed: %s", e)

        try:
            from core.finance_metrics_bridge import metrics_bridge
            await metrics_bridge.on_invoice_decision(
                invoice_id   = invoice_id,
                decision     = decision,
                risk_score   = risk_score,
                confidence   = confidence,
                execution_ms = execution_ms,
            )
        except Exception as e:
            logger.debug("metrics_bridge.on_invoice_decision (new) failed: %s", e)

    return _handle_new


def _build_payment_handler(orchestrator):
    async def _handle_payment(event: dict) -> None:
        from core.db import write_audit_log
        from core.finance_db import save_finance_decision

        payload     = event["payload"]
        invoice_id  = payload.get("invoice_id")
        event_id    = payload.get("event_id")
        amount_paid = float(payload.get("amount_paid", 0))

        logger.info(
            "🤖 [Finance Bridge] payment_received #%s (%s EGP) → Orchestrator",
            invoice_id, amount_paid,
        )

        t_start      = time.perf_counter()
        result       = await orchestrator.async_handle({"type": "payment_received", "payload": payload})
        execution_ms = int((time.perf_counter() - t_start) * 1000)

        decision    = result.get("decision", "payment_received")
        confidence  = float(result.get("confidence", 0.99))
        risk_score  = float(result.get("risk_score", 0.1))
        reasoning   = result.get("reason", "")
        request_id  = result.get("request_id", "")
        action_plan = result.get("action_plan", [])

        try:
            saved_id = save_finance_decision({
                "agent_type":   "finance_agent_v2.1",
                "entity":       "invoices",
                "entity_id":    int(invoice_id) if invoice_id else 0,
                "event_id":     event_id,
                "decision":     decision,
                "confidence":   confidence,
                "risk_score":   risk_score,
                "reasoning":    reasoning,
                "action_plan":  str(action_plan),
                "execution_ms": execution_ms,
                "request_id":   request_id,
            })
            logger.info("   💾 Payment decision saved → #%d", saved_id or 0)
        except Exception as e:
            logger.error("   ❌ save_finance_decision (payment) failed: %s", e)

        try:
            write_audit_log(
                action       = f"payment_{decision}",
                entity       = "invoices",
                entity_id    = int(invoice_id) if invoice_id else 0,
                performed_by = "finance_agent_v2.1",
                details      = f"amount_paid={amount_paid:,.2f} EGP | [request_id={request_id}]",
            )
        except Exception as e:
            logger.debug("write_audit_log failed: %s", e)

        try:
            from core.finance_metrics_bridge import metrics_bridge
            await metrics_bridge.on_invoice_decision(
                invoice_id   = invoice_id,
                decision     = decision,
                risk_score   = risk_score,
                confidence   = confidence,
                execution_ms = execution_ms,
            )
        except Exception as e:
            logger.debug("metrics_bridge.on_invoice_decision (payment) failed: %s", e)

    return _handle_payment