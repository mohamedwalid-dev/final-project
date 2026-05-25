"""
⏱️ Finance Trigger Jobs — v3.0 (MongoDB/Motor)
===============================================
File: app/core/finance_trigger.py

v3.0 Changes (Migration: MySQL → MongoDB):
    ✅ job_scan_overdue_invoices()  ← FinanceDB.get_overdue_invoices() بدل core.finance_db SQL
    ✅ job_scan_new_invoices()      ← FinanceDB.invoices.find() aggregate بدل raw SQL JOIN
    ✅ _build_invoice_overdue_handler() ← FinanceDB.save_finance_decision() + write_finance_audit()
    ✅ _build_new_invoice_handler() ← نفس النهج
    ✅ _build_payment_handler()     ← نفس النهج
    ✅ start_execution/finish_execution ← hr_domain_audit بدل MySQL exec log
    ✅ كل import لـ core.db / core.finance_db اتشال تماماً
    ✅ invoice_id الآن ObjectId string (MongoDB _id) مش int

v2.1 Features (unchanged):
    ✅ save_finance_decision() بعد AI decision حقيقي فقط
    ✅ لو event_bus.publish() رجع -1 (duplicate) → مفيش DB write
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


# ══════════════════════════════════════════════════════════════════════════════
# 🔌  DB helpers
# ══════════════════════════════════════════════════════════════════════════════

def _get_db():
    """Return shared FinanceDB instance (Motor async)."""
    from core.mongo_connect import get_finance_db
    return get_finance_db()


async def _write_audit(db, action: str, invoice_id, request_id: str, details: str) -> None:
    """
    Unified audit writer → FinanceDB.write_finance_audit().
    بدل write_audit_log() من core.db.
    """
    try:
        from bson import ObjectId
        entity_oid = ObjectId(str(invoice_id)) if invoice_id else None
        await db.write_finance_audit(
            domain          = "invoice",
            entity_id       = entity_oid,
            customer_id     = None,
            decision        = action,
            risk_score      = 0.0,
            confidence      = 0.0,
            decision_source = "finance_trigger_v3.0",
            llm_used        = False,
            request_id      = request_id,
            execution_ms    = 0,
            action_plan     = [],
            flags           = [details[:300]],
        )
    except Exception as e:
        logger.debug("_write_audit failed: %s", e)


# ══════════════════════════════════════════════════════════════════════════════
# ⏰  SCHEDULED JOBS
# ══════════════════════════════════════════════════════════════════════════════

async def job_scan_overdue_invoices() -> None:
    """
    Scan overdue invoices → publish invoice_overdue events.
    MongoDB: بيستخدم FinanceDB.get_overdue_invoices() بدل SQL query.
    """
    from core.event_bus import event_bus

    logger.info("⏰ [Finance Scheduler] Scanning overdue invoices...")

    db             = _get_db()
    invoices_found = 0
    invoices_fired = 0

    try:
        # FinanceDB.get_overdue_invoices() بيرجع list[dict] مع overdue_days_calc
        invoices       = await db.get_overdue_invoices(min_days=1, limit=200)
        invoices_found = len(invoices)

        if not invoices:
            logger.info("   ✅ No overdue invoices found.")
            return

        logger.info("   💰 Found %d overdue invoice(s)", invoices_found)

        for invoice in invoices:
            # في MongoDB الـ _id هو ObjectId → بنحوله لـ string
            invoice_id   = str(invoice.get("_id", ""))
            customer_id  = str(invoice.get("customer_id", ""))
            overdue_days = int(invoice.get("overdue_days_calc") or 0)

            result = await event_bus.publish("invoice_overdue", {
                "invoice_id":       invoice_id,
                "customer_id":      customer_id,
                "customer_name":    invoice.get("customer_name", ""),
                "amount":           float(invoice.get("amount", 0)),
                "due_date":         str(invoice.get("due_date", "")),
                "overdue_days":     overdue_days,
                "credit_score":     float(invoice.get("credit_score") or 650),
                "industry":         invoice.get("industry", "unknown"),
                "service_status":   invoice.get("service_status", "active"),
                "is_disputed":      bool(invoice.get("is_disputed", False)),
                "has_payment_plan": bool(
                    invoice.get("collection_strategy") == "payment_plan"
                ),
                "collection_notes": invoice.get("ai_decision_reason", ""),
                "source":           "scheduler",
            })

            if result == -1:
                # ✅ Duplicate suppressed — NO DB write
                logger.debug(
                    "   ⏭️ Invoice %s duplicate suppressed — no DB write", invoice_id
                )
            else:
                invoices_fired += 1
                logger.info(
                    "   📤 Event fired → invoice_overdue %s (%d days, %.0f EGP)",
                    invoice_id, overdue_days, invoice.get("amount", 0),
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

    except Exception as e:
        logger.error(
            "❌ [Finance Scheduler] Overdue scan failed: %s", e, exc_info=True
        )


async def job_scan_new_invoices() -> None:
    """
    Scan new invoices that haven't been risk-assessed yet.

    MongoDB: بنستخدم FinanceDB.invoices aggregate بدل SQL JOIN مع customers.
    Criteria: status='pending' AND (ai_risk_score == 0 OR لا يوجد) AND created خلال 24 ساعة.
    """
    from core.event_bus import event_bus
    from datetime import datetime, timezone, timedelta
    from bson import ObjectId

    logger.info("⏰ [Finance Scheduler] Scanning new invoices...")

    db             = _get_db()
    invoices_found = 0
    invoices_fired = 0

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

        # Aggregate: join customers لجيب customer_name + credit_score + industry
        pipeline = [
            {
                "$match": {
                    "status":        "pending",
                    "created_at":    {"$gte": cutoff},
                    "$or": [
                        {"ai_risk_score": {"$exists": False}},
                        {"ai_risk_score": 0},
                        {"ai_risk_score": None},
                    ],
                }
            },
            {
                "$lookup": {
                    "from":         "customers",
                    "localField":   "customer_id",
                    "foreignField": "_id",
                    "as":           "_customer",
                }
            },
            {
                "$unwind": {
                    "path":                       "$_customer",
                    "preserveNullAndEmptyArrays": True,
                }
            },
            {
                "$addFields": {
                    "customer_name": "$_customer.name",
                    "credit_score":  "$_customer.credit_score",
                    "industry":      "$_customer.industry",
                }
            },
            {"$project": {"_customer": 0}},
            {"$sort":  {"created_at": -1}},
            {"$limit": 50},
        ]

        invoices       = await db.invoices.aggregate(pipeline).to_list(50)
        invoices_found = len(invoices)

        if not invoices:
            logger.info("   ✅ No new unassessed invoices.")
            return

        logger.info("   🧾 Found %d new invoice(s) to assess", invoices_found)

        for invoice in invoices:
            invoice_id  = str(invoice.get("_id", ""))
            customer_id = str(invoice.get("customer_id", ""))

            result = await event_bus.publish("invoice_created", {
                "invoice_id":    invoice_id,
                "customer_id":   customer_id,
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

    except Exception as e:
        logger.error(
            "❌ [Finance Scheduler] New invoice scan failed: %s", e, exc_info=True
        )


# ══════════════════════════════════════════════════════════════════════════════
# 🎛️  HANDLER REGISTRATION
# ══════════════════════════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════════════════════════
# 🤖  EVENT HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

def _build_invoice_overdue_handler(orchestrator):
    """
    ✅ v3.0: save_finance_decision() → FinanceDB.save_finance_decision()
    Sequence: AI → MongoDB save → audit → metrics_bridge
    """
    async def _handle_overdue(event: dict) -> None:
        db = _get_db()

        payload     = event["payload"]
        invoice_id  = payload.get("invoice_id")   # MongoDB ObjectId string
        event_id    = payload.get("event_id")
        customer_id = payload.get("customer_id", "?")

        logger.info(
            "🤖 [Finance Bridge] invoice_overdue %s → Orchestrator | customer=%s",
            invoice_id, customer_id,
        )

        # ── 0. AI Decision ────────────────────────────────────────────────────
        t_start      = time.perf_counter()
        result       = await orchestrator.async_handle({
            "type":    "invoice_overdue",
            "payload": payload,
        })
        execution_ms = int((time.perf_counter() - t_start) * 1000)

        decision    = result.get("decision", "soft_follow_up")
        confidence  = float(result.get("confidence", 0.5))
        risk_score  = float(result.get("risk_score", 0.5))
        reasoning   = result.get("reason", result.get("reasoning", ""))
        request_id  = result.get("request_id", "")
        action_plan = result.get("action_plan", [])

        logger.info(
            "   ✅ %s → %s | risk=%.0f%% | action=%s | %dms",
            invoice_id, decision, risk_score * 100,
            result.get("primary_action"), execution_ms,
        )

        # ── 1. Save to MongoDB ────────────────────────────────────────────────
        try:
            from bson import ObjectId
            saved_id = await db.save_finance_decision({
                "agent_type":   "finance_agent_v3.0",
                "entity":       "invoices",
                "entity_id":    ObjectId(str(invoice_id)) if invoice_id else None,
                "event_id":     event_id,
                "decision":     decision,
                "confidence":   confidence,
                "risk_score":   risk_score,
                "reasoning":    reasoning,
                "action_plan":  str(action_plan),
                "execution_ms": execution_ms,
                "request_id":   request_id,
            })
            logger.info("   💾 Saved → finance_decisions %s", saved_id or "?")
        except Exception as e:
            logger.error("   ❌ save_finance_decision failed: %s", e)

        # ── 2. Finance Audit ──────────────────────────────────────────────────
        try:
            from bson import ObjectId
            await db.write_finance_audit(
                domain          = "invoice",
                entity_id       = ObjectId(str(invoice_id)) if invoice_id else None,
                customer_id     = ObjectId(str(customer_id)) if customer_id and customer_id != "?" else None,
                decision        = decision,
                risk_score      = risk_score,
                confidence      = confidence,
                decision_source = result.get("model_source", "agent"),
                llm_used        = bool(result.get("llm_used", False)),
                request_id      = request_id,
                execution_ms    = execution_ms,
                action_plan     = action_plan,
                flags           = [
                    f"risk={risk_score:.0%}",
                    f"action={result.get('primary_action')}",
                    reasoning[:150],
                ],
            )
        except Exception as e:
            logger.debug("write_finance_audit failed: %s", e)

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
    """
    ✅ v3.0: MongoDB save بدل core.finance_db SQL.
    """
    async def _handle_new(event: dict) -> None:
        db = _get_db()

        payload    = event["payload"]
        invoice_id = payload.get("invoice_id")
        event_id   = payload.get("event_id")

        logger.info("🤖 [Finance Bridge] invoice_created %s → Orchestrator", invoice_id)

        t_start      = time.perf_counter()
        result       = await orchestrator.async_handle({
            "type":    "invoice_created",
            "payload": payload,
        })
        execution_ms = int((time.perf_counter() - t_start) * 1000)

        decision    = result.get("decision", "invoice_registered")
        confidence  = float(result.get("confidence", 0.9))
        risk_score  = float(result.get("risk_score", 0.0))
        reasoning   = result.get("reason", "")
        request_id  = result.get("request_id", "")
        action_plan = result.get("action_plan", [])

        logger.info(
            "   ✅ %s assessed | strategy=%s | risk=%.0f%% | %dms",
            invoice_id, result.get("collection_strategy"), risk_score * 100, execution_ms,
        )

        # Save to MongoDB
        try:
            from bson import ObjectId
            saved_id = await db.save_finance_decision({
                "agent_type":   "finance_agent_v3.0",
                "entity":       "invoices",
                "entity_id":    ObjectId(str(invoice_id)) if invoice_id else None,
                "event_id":     event_id,
                "decision":     decision,
                "confidence":   confidence,
                "risk_score":   risk_score,
                "reasoning":    reasoning,
                "action_plan":  str(action_plan),
                "execution_ms": execution_ms,
                "request_id":   request_id,
            })
            logger.info("   💾 Saved → finance_decisions %s", saved_id or "?")
        except Exception as e:
            logger.error("   ❌ save_finance_decision failed: %s", e)

        # Finance audit
        try:
            from bson import ObjectId
            await db.write_finance_audit(
                domain          = "invoice",
                entity_id       = ObjectId(str(invoice_id)) if invoice_id else None,
                customer_id     = None,
                decision        = decision,
                risk_score      = risk_score,
                confidence      = confidence,
                decision_source = result.get("model_source", "agent"),
                llm_used        = bool(result.get("llm_used", False)),
                request_id      = request_id,
                execution_ms    = execution_ms,
                action_plan     = action_plan,
                flags           = [
                    f"strategy={result.get('collection_strategy')}",
                    f"risk={risk_score:.0%}",
                ],
            )
        except Exception as e:
            logger.debug("write_finance_audit (new) failed: %s", e)

        # Metrics bridge
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
    """
    ✅ v3.0: MongoDB save بدل core.finance_db SQL.
    """
    async def _handle_payment(event: dict) -> None:
        db = _get_db()

        payload     = event["payload"]
        invoice_id  = payload.get("invoice_id")
        event_id    = payload.get("event_id")
        amount_paid = float(payload.get("amount_paid", 0))

        logger.info(
            "🤖 [Finance Bridge] payment_received %s (%.2f EGP) → Orchestrator",
            invoice_id, amount_paid,
        )

        t_start      = time.perf_counter()
        result       = await orchestrator.async_handle({
            "type":    "payment_received",
            "payload": payload,
        })
        execution_ms = int((time.perf_counter() - t_start) * 1000)

        decision    = result.get("decision", "payment_received")
        confidence  = float(result.get("confidence", 0.99))
        risk_score  = float(result.get("risk_score", 0.1))
        reasoning   = result.get("reason", "")
        request_id  = result.get("request_id", "")
        action_plan = result.get("action_plan", [])

        # Save to MongoDB
        try:
            from bson import ObjectId
            saved_id = await db.save_finance_decision({
                "agent_type":   "finance_agent_v3.0",
                "entity":       "invoices",
                "entity_id":    ObjectId(str(invoice_id)) if invoice_id else None,
                "event_id":     event_id,
                "decision":     decision,
                "confidence":   confidence,
                "risk_score":   risk_score,
                "reasoning":    reasoning,
                "action_plan":  str(action_plan),
                "execution_ms": execution_ms,
                "request_id":   request_id,
            })
            logger.info("   💾 Payment decision saved → %s", saved_id or "?")
        except Exception as e:
            logger.error("   ❌ save_finance_decision (payment) failed: %s", e)

        # Finance audit
        try:
            from bson import ObjectId
            await db.write_finance_audit(
                domain          = "invoice",
                entity_id       = ObjectId(str(invoice_id)) if invoice_id else None,
                customer_id     = None,
                decision        = decision,
                risk_score      = risk_score,
                confidence      = confidence,
                decision_source = result.get("model_source", "agent"),
                llm_used        = bool(result.get("llm_used", False)),
                request_id      = request_id,
                execution_ms    = execution_ms,
                action_plan     = action_plan,
                flags           = [f"amount_paid={amount_paid:,.2f} EGP"],
            )
        except Exception as e:
            logger.debug("write_finance_audit (payment) failed: %s", e)

        # Metrics bridge
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