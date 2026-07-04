"""
🌉 Finance Metrics Bridge — v2.1 Production
=============================================
File: app/core/finance_metrics_bridge.py

v2.1 Changes (over v2.0):
    ✅ on_scheduler_scan()  — ناقصة في v2.0، موجودة في finance_trigger لكن مش معرّفة
    ✅ on_invoice_decision() بتعمل force snapshot بعد كل decision فورًا
    ✅ decisions_today يتحدث DB-driven مش memory-driven
    ✅ Error isolation — أي فشل في الـ bridge لا يوقف الـ workflow

v2.0 Design (unchanged):
    ✅ on_invoice_decision()  → بعد كل AI decision
    ✅ on_payment_received()  → بعد استلام دفعة
    ✅ on_action_executed()   → بعد كل action
    ✅ on_workflow_completed() → completion signal
    ✅ force=True على الـ snapshot بعد كل event مهم
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# 🗺️  DECISION → READABLE STATUS MAPPING
# ══════════════════════════════════════════════════════════════════════════════

_DECISION_DISPLAY: dict[str, str] = {
    "safe_to_collect":    "✅ Safe — Reminder Sent",
    "soft_follow_up":     "📩 Soft Follow-up",
    "hard_follow_up":     "🔔 Hard Follow-up",
    "payment_plan":       "💳 Payment Plan Offered",
    "suspend_service":    "🚫 Service Suspended",
    "legal_escalation":   "⚖️ Legal Escalation",
    "write_off":          "❌ Written Off",
    "on_hold_disputed":   "⏸️ On Hold — Disputed",
    "payment_complete":   "✅ Paid — Complete",
    "partial_payment":    "🔄 Partial Payment",
    "invoice_registered": "📋 Registered",
    "skipped":            "⏭️ Skipped",
    "unknown":            "❓ Unknown",
}

# Actions اللي تستحق force snapshot rebuild
_HIGH_IMPACT_ACTIONS = {
    "escalate_to_legal",
    "suspend_service",
    "write_off_invoice",
    "propose_payment_plan",
    "send_legal_warning_letter",
    "blacklist_customer",
    "mark_invoice_paid",
}


# ══════════════════════════════════════════════════════════════════════════════
# 🌉  BRIDGE CLASS
# ══════════════════════════════════════════════════════════════════════════════

class FinanceMetricsBridge:
    """
    يربط Finance Workflow events بالـ MetricsCollector.

    الاستخدام:
        from core.finance_metrics_bridge import metrics_bridge

        await metrics_bridge.on_invoice_decision(result, payload)
        await metrics_bridge.on_payment_received(invoice_id, customer_id, amount, decision)
        await metrics_bridge.on_action_executed(action, invoice_id, ...)
        await metrics_bridge.on_workflow_completed(workflow_name, result, payload)
        await metrics_bridge.on_scheduler_scan(scan_type, invoices_found, invoices_fired)
    """

    def __init__(self) -> None:
        logger.info("🌉 FinanceMetricsBridge v2.1 initialized")

    # ── Lazy collector getter ──────────────────────────────────────────────────

    def _collector(self):
        from core.metrics_collector import get_metrics_collector
        return get_metrics_collector()

    def _emitter(self):
        from core.metrics_collector import get_metrics_collector, MetricEvent
        return get_metrics_collector(), MetricEvent

    # ══════════════════════════════════════════════════════════════════════════
    # 📊  on_invoice_decision — بعد كل AI decision
    # ══════════════════════════════════════════════════════════════════════════

    async def on_invoice_decision(self, result: dict, payload: dict) -> None:
        """
        يُستدعى بعد كل AI decision على invoice.
        يبعت 2 metrics:
            1. finance.decision         — نوع الـ decision
            2. finance.risk_score       — قيمة الـ risk

        ثم يعمل force snapshot rebuild → decisions_today يتحدث فورًا.
        """
        try:
            collector, MetricEvent = self._emitter()

            decision    = result.get("decision", "unknown")
            risk_score  = float(result.get("risk_score", 0))
            confidence  = float(result.get("confidence", 0))
            invoice_id  = payload.get("invoice_id")
            customer_id = payload.get("customer_id")
            amount      = float(payload.get("amount", 0))
            request_id  = result.get("request_id", "")

            # Metric 1: Decision type
            await collector.emit(MetricEvent(
                metric_type = f"finance.decision.{decision}",
                category    = "finance",
                value       = 1,
                unit        = "count",
                tags        = {
                    "decision":     decision,
                    "display":      _DECISION_DISPLAY.get(decision, decision),
                    "model_source": result.get("model_source", "unknown"),
                    "llm_used":     result.get("llm_used", False),
                    "rule":         result.get("override_rule"),
                },
                entity_id   = invoice_id,
                entity_type = "invoice",
                request_id  = request_id,
            ))

            # Metric 2: Risk score
            await collector.emit(MetricEvent(
                metric_type = "finance.risk_score",
                category    = "finance",
                value       = round(risk_score, 4),
                unit        = "ratio",
                tags        = {
                    "decision":    decision,
                    "confidence":  round(confidence, 4),
                    "amount_egp":  amount,
                    "customer_id": customer_id,
                },
                entity_id   = invoice_id,
                entity_type = "invoice",
                request_id  = request_id,
            ))

            # ✅ v2.1: force snapshot → decisions_today يتحدث فورًا من DB
            await collector.get_snapshot(force=True)

            logger.debug(
                "🌉 [Bridge] on_invoice_decision — invoice=%s decision=%s risk=%.2f",
                invoice_id, decision, risk_score,
            )

        except Exception as e:
            logger.warning("⚠️ [Bridge] on_invoice_decision failed (non-critical): %s", e)

    # ══════════════════════════════════════════════════════════════════════════
    # 💳  on_payment_received
    # ══════════════════════════════════════════════════════════════════════════

    async def on_payment_received(
        self,
        invoice_id:  Optional[int],
        customer_id: Optional[int],
        amount_paid: float,
        decision:    str = "payment_complete",
    ) -> None:
        try:
            collector, MetricEvent = self._emitter()

            await collector.emit(MetricEvent(
                metric_type = f"finance.payment.{decision}",
                category    = "finance",
                value       = round(amount_paid, 2),
                unit        = "EGP",
                tags        = {
                    "decision":    decision,
                    "customer_id": customer_id,
                    "display":     _DECISION_DISPLAY.get(decision, decision),
                },
                entity_id   = invoice_id,
                entity_type = "invoice",
            ))

            await collector.get_snapshot(force=True)

            logger.debug(
                "🌉 [Bridge] on_payment_received — invoice=%s amount=%.2f EGP decision=%s",
                invoice_id, amount_paid, decision,
            )

        except Exception as e:
            logger.warning("⚠️ [Bridge] on_payment_received failed (non-critical): %s", e)

    # ══════════════════════════════════════════════════════════════════════════
    # ⚡  on_action_executed
    # ══════════════════════════════════════════════════════════════════════════

    async def on_action_executed(
        self,
        action:      str,
        invoice_id:  Optional[int] = None,
        customer_id: Optional[int] = None,
        amount:      float         = 0.0,
        result:      Optional[dict] = None,
    ) -> None:
        try:
            collector, MetricEvent = self._emitter()

            status = "success"
            if result and result.get("error"):
                status = "failed"

            await collector.emit(MetricEvent(
                metric_type = f"finance.action.{action}",
                category    = "finance",
                value       = 1,
                unit        = "count",
                tags        = {
                    "action":      action,
                    "status":      status,
                    "customer_id": customer_id,
                    "amount_egp":  round(amount, 2),
                },
                entity_id   = invoice_id,
                entity_type = "invoice",
            ))

            if action in _HIGH_IMPACT_ACTIONS:
                await collector.get_snapshot(force=True)
                logger.info(
                    "🌉 [Bridge] High-impact action '%s' — forced snapshot rebuild",
                    action,
                )
            else:
                logger.debug("🌉 [Bridge] on_action_executed — action=%s status=%s", action, status)

        except Exception as e:
            logger.warning("⚠️ [Bridge] on_action_executed failed (non-critical): %s", e)

    # ══════════════════════════════════════════════════════════════════════════
    # 🏁  on_workflow_completed — completion signal
    # ══════════════════════════════════════════════════════════════════════════

    async def on_workflow_completed(
        self,
        workflow_name: str,
        result:        dict,
        payload:       dict,
        execution_ms:  int = 0,
    ) -> None:
        try:
            collector, MetricEvent = self._emitter()

            decision   = result.get("decision", "unknown")
            invoice_id = payload.get("invoice_id")
            skipped    = result.get("skipped", False)

            await collector.emit(MetricEvent(
                metric_type = "finance.workflow.completed",
                category    = "finance",
                value       = 1,
                unit        = "count",
                tags        = {
                    "workflow":      workflow_name,
                    "decision":      decision,
                    "display":       _DECISION_DISPLAY.get(decision, decision),
                    "skipped":       skipped,
                    "execution_ms":  execution_ms,
                    "actions_count": len(result.get("actions_taken", [])),
                    "llm_used":      result.get("llm_used", False),
                    "model_source":  result.get("model_source", "unknown"),
                },
                entity_id   = invoice_id,
                entity_type = "invoice",
                request_id  = result.get("request_id", ""),
            ))

            # Final snapshot — يضمن إن الـ Dashboard يعكس الحالة الكاملة
            await collector.get_snapshot(force=True)

            logger.info(
                "🏁 [Bridge] Workflow completed — %s | invoice=%s | decision=%s | %dms",
                workflow_name, invoice_id, decision, execution_ms,
            )

        except Exception as e:
            logger.warning("⚠️ [Bridge] on_workflow_completed failed (non-critical): %s", e)

    # ══════════════════════════════════════════════════════════════════════════
    # 🔍  on_scheduler_scan — ✅ v2.1 NEW (كانت ناقصة!)
    # ══════════════════════════════════════════════════════════════════════════

    async def on_scheduler_scan(
        self,
        scan_type:      str,
        invoices_found: int,
        invoices_fired: int,
    ) -> None:
        """
        يُستدعى بعد كل scheduler scan (overdue أو new_invoices).
        كان بيتنادى في finance_trigger.py لكن الـ method مش معرّفة في v2.0.

        يبعت:
            finance.scheduler.scan  → عدد الفواتير اللي اتلقت + اتبعتلها events
        ثم force snapshot.
        """
        try:
            collector, MetricEvent = self._emitter()

            await collector.emit(MetricEvent(
                metric_type = f"finance.scheduler.{scan_type}",
                category    = "finance",
                value       = invoices_found,
                unit        = "count",
                tags        = {
                    "scan_type":      scan_type,
                    "invoices_found": invoices_found,
                    "invoices_fired": invoices_fired,
                    "skip_ratio":     round(
                        (invoices_found - invoices_fired) / max(invoices_found, 1), 2
                    ),
                },
                entity_type = "scheduler",
            ))

            # Force snapshot بعد كل scan — dashboard يتحدث
            if invoices_fired > 0:
                await collector.get_snapshot(force=True)

            logger.info(
                "🔍 [Bridge] Scheduler scan '%s' — found=%d fired=%d",
                scan_type, invoices_found, invoices_fired,
            )

        except Exception as e:
            logger.warning("⚠️ [Bridge] on_scheduler_scan failed (non-critical): %s", e)

    # ══════════════════════════════════════════════════════════════════════════
    # 📣  on_alert
    # ══════════════════════════════════════════════════════════════════════════

    async def on_alert(
        self,
        level:   str,
        title:   str,
        message: str,
        data:    Optional[dict] = None,
    ) -> None:
        try:
            collector = self._collector()
            await collector.alert(level, title, message, data or {})
        except Exception as e:
            logger.warning("⚠️ [Bridge] on_alert failed (non-critical): %s", e)


# ══════════════════════════════════════════════════════════════════════════════
# 🔒  SINGLETON
# ══════════════════════════════════════════════════════════════════════════════

metrics_bridge = FinanceMetricsBridge()
