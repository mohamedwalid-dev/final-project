"""
🔄 Finance Invoice Workflow — v2.1 Production
===============================================
File: app/workflows/finance/invoice_workflow.py

v2.1 Changes (over v2.0):
    ✅ on_workflow_completed() في نهاية OverdueInvoiceWorkflow  ← الـ "completion signal" المفقود
    ✅ on_workflow_completed() في نهاية NewInvoiceWorkflow
    ✅ on_workflow_completed() في نهاية PaymentReceivedWorkflow
    ✅ execution_ms يتحسب بدقة وبيتبعت للـ bridge
    ✅ Dashboard يعكس "Processed/Done" فورًا بعد كل workflow

v2.0 Changes (unchanged):
    ✅ FinanceMetricsBridge integrated
    ✅ on_invoice_decision() بعد _persist()
    ✅ on_payment_received() في PaymentReceivedWorkflow
    ✅ on_action_executed() في _execute_actions()
    ✅ Error handling محسّن
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from agents.base_agent import generate_request_id

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {
    "paid", "settled", "written_off", "cancelled",
    "disputed", "in_progress_collection",
}


# ═════════════════════════════════════════════════════════════════════════════
# 🔄  OVERDUE INVOICE WORKFLOW
# ═════════════════════════════════════════════════════════════════════════════

class OverdueInvoiceWorkflow:

    def __init__(self) -> None:
        self._agent  = None
        self._logger = None

    @property
    def agent(self):
        if self._agent is None:
            from agents.finance.finance_agent import FinanceAgent
            self._agent = FinanceAgent()
        return self._agent

    @property
    def audit_logger(self):
        if self._logger is None:
            from audit.logger import AuditLogger
            self._logger = AuditLogger()
        return self._logger

    async def async_run(self, payload: dict) -> dict:
        request_id  = payload.get("request_id") or generate_request_id()
        payload     = {**payload, "request_id": request_id}
        invoice_id  = payload.get("invoice_id")
        customer_id = payload.get("customer_id", "?")

        # ⏱️ نبدأ العداد هنا عشان نحسب الـ execution_ms الكامل للـ workflow
        workflow_start_ms = int(time.time() * 1000)

        self.audit_logger.log(
            event_type = "invoice_overdue",
            stage      = "workflow",
            message    = (
                f"[request_id={request_id}] OverdueInvoiceWorkflow started — "
                f"invoice={invoice_id} customer={customer_id}"
            ),
        )

        # ── Step 0: Status Pre-Check ──────────────────────────────────────────
        if invoice_id:
            current_status = await self._get_invoice_status(invoice_id)
            if current_status in TERMINAL_STATUSES:
                logger.info(
                    "[request_id=%s] ⏭️ Invoice #%s terminal status=%s — skipping",
                    request_id, invoice_id, current_status,
                )
                result = {
                    "decision":    "skipped",
                    "confidence":  1.0,
                    "invoice_id":  invoice_id,
                    "reasoning":   f"Invoice already in terminal state: {current_status}",
                    "workflow":    "OverdueInvoiceWorkflow_v2.1",
                    "request_id":  request_id,
                    "skipped":     True,
                }
                # ✅ v2.1: completion signal حتى للـ skipped
                await self._emit_completion(result, payload, workflow_start_ms)
                return result

        # ── Step 1: Atomic Claim ──────────────────────────────────────────────
        if invoice_id:
            claimed = await self._claim_invoice(invoice_id, request_id)
            if not claimed:
                logger.info(
                    "[request_id=%s] ⏭️ Invoice #%s already claimed — skipping",
                    request_id, invoice_id,
                )
                result = {
                    "decision":   "skipped",
                    "confidence": 1.0,
                    "invoice_id": invoice_id,
                    "reasoning":  "Already claimed by another process",
                    "workflow":   "OverdueInvoiceWorkflow_v2.1",
                    "request_id": request_id,
                }
                await self._emit_completion(result, payload, workflow_start_ms)
                return result

        # ── Step 2: Enrich payload ────────────────────────────────────────────
        payload = await self._enrich_with_customer_data(payload, request_id)

        # ── Step 3: Finance Agent Decision ───────────────────────────────────
        start_ms = int(time.time() * 1000)
        try:
            agent_result = await self.agent.process_invoice(payload)
        except Exception as e:
            logger.error("[request_id=%s] ❌ FinanceAgent failed: %s", request_id, e)
            agent_result = {
                "decision":       "hard_follow_up",
                "confidence":     0.5,
                "risk":           "high",
                "reason":         f"Agent error — manual review needed. Error: {e}",
                "primary_action": "manual_review",
                "action_plan":    ["manual_review"],
                "model_source":   "error_fallback",
                "request_id":     request_id,
            }
        execution_ms = int(time.time() * 1000) - start_ms

        logger.info(
            "[request_id=%s] 🧠 Agent decision: %s | risk=%.0f%% | "
            "action=%s | elapsed=%dms",
            request_id,
            agent_result.get("decision"),
            float(agent_result.get("risk_score", 0)) * 100,
            agent_result.get("primary_action"),
            execution_ms,
        )

        # ── Step 4: Persist to DB ─────────────────────────────────────────────
        await self._persist(agent_result, payload, request_id, execution_ms)

        # ── Step 5: Execute Actions ───────────────────────────────────────────
        actions_taken = await self._execute_actions(agent_result, payload, request_id)

        # ── Step 6: Build Final Result ────────────────────────────────────────
        result = {
            **agent_result,
            "workflow":      "OverdueInvoiceWorkflow_v2.1",
            "execution_ms":  execution_ms,
            "actions_taken": actions_taken,
        }

        self.audit_logger.log(
            event_type = "invoice_overdue",
            stage      = "workflow",
            message    = (
                f"[request_id={request_id}] OverdueInvoiceWorkflow complete — "
                f"invoice={invoice_id} decision={agent_result.get('decision')}"
            ),
            data = {
                "decision":       agent_result.get("decision"),
                "risk_score":     agent_result.get("risk_score"),
                "execution_ms":   execution_ms,
                "actions_taken":  actions_taken,
            },
        )

        # ── Step 7: ✅ v2.1 — Completion Signal (الـ "Done" metric المفقود) ──
        await self._emit_completion(result, payload, workflow_start_ms)

        return result

    # ══════════════════════════════════════════════════════════════════════════
    # 🏁  _emit_completion — الـ completion signal
    # ══════════════════════════════════════════════════════════════════════════

    async def _emit_completion(
        self, result: dict, payload: dict, workflow_start_ms: int
    ) -> None:
        """
        ✅ الـ "invoice_completed" signal.

        ده اللي كان ناقص — بدونه الـ Dashboard بيشوف:
            ❌ "started" بس مفيش "done"

        بعده:
            ✅ "Processed / Decided / Escalated" يظهر فورًا
        """
        try:
            total_ms = int(time.time() * 1000) - workflow_start_ms
            from core.finance_metrics_bridge import metrics_bridge
            await metrics_bridge.on_workflow_completed(
                workflow_name = "OverdueInvoiceWorkflow",
                result        = result,
                payload       = payload,
                execution_ms  = total_ms,
            )
        except Exception as e:
            logger.warning(
                "[request_id=%s] ⚠️ completion signal failed (non-critical): %s",
                result.get("request_id", "?"), e,
            )

    def run(self, payload: dict) -> dict:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self.async_run(payload))
                    return future.result(timeout=60)
            return loop.run_until_complete(self.async_run(payload))
        except Exception as e:
            req_id = payload.get("request_id", generate_request_id())
            logger.error("[request_id=%s] ❌ OverdueInvoiceWorkflow run() failed: %s", req_id, e)
            return {
                "status":     "error",
                "message":    str(e),
                "stage":      "workflow",
                "request_id": req_id,
            }

    # ── Private Helpers ───────────────────────────────────────────────────────

    async def _get_invoice_status(self, invoice_id: int) -> Optional[str]:
        try:
            import importlib
            db_module = importlib.import_module("core.db")
            with db_module.get_db() as (_, cur):
                cur.execute(
                    "SELECT status FROM invoices WHERE id = %s LIMIT 1",
                    (invoice_id,),
                )
                row = cur.fetchone()
                return row["status"] if row else None
        except Exception as e:
            logger.warning("⚠️ Could not check invoice status: %s", e)
            return None

    async def _claim_invoice(self, invoice_id: int, request_id: str) -> bool:
        try:
            import importlib
            db_module = importlib.import_module("core.db")
            with db_module.get_db() as (conn, cur):
                cur.execute(
                    "UPDATE invoices SET status = %s "
                    "WHERE id = %s AND status NOT IN ('paid', 'written_off', 'cancelled', 'in_progress_collection')",
                    ("in_progress_collection", invoice_id),
                )
                conn.commit()
                return cur.rowcount >= 1
        except Exception as e:
            logger.warning(
                "[request_id=%s] ⚠️ Invoice claim failed: %s — allowing through",
                request_id, e,
            )
            return True

    async def _enrich_with_customer_data(self, payload: dict, request_id: str) -> dict:
        customer_id = payload.get("customer_id")
        if not customer_id:
            return payload
        try:
            import importlib
            db_module = importlib.import_module("core.db")
            with db_module.get_db() as (_, cur):
                cur.execute(
                    """
                    SELECT
                        COUNT(*)                                       AS total_invoices,
                        SUM(CASE WHEN status='paid' THEN 1 ELSE 0 END) AS paid_count,
                        SUM(CASE WHEN status='overdue' THEN 1 ELSE 0 END) AS overdue_count,
                        AVG(DATEDIFF(updated_at, due_date))            AS avg_delay_days
                    FROM invoices
                    WHERE customer_id = %s AND status != 'draft'
                      AND created_at >= DATE_SUB(NOW(), INTERVAL 12 MONTH)
                    """,
                    (customer_id,),
                )
                history = cur.fetchone() or {}

                enriched = {
                    **payload,
                    "payment_history_count": int(history.get("total_invoices") or 0),
                    "payment_history_paid":  int(history.get("paid_count") or 0),
                    "payment_history_late":  int(history.get("overdue_count") or 0),
                    "avg_payment_delay_days": float(history.get("avg_delay_days") or 0),
                }

                cur.execute(
                    "SELECT * FROM customers WHERE id = %s LIMIT 1",
                    (customer_id,),
                )
                customer = cur.fetchone()
                if customer:
                    enriched["customer_name"]       = customer.get("name", "Unknown")
                    enriched["credit_score"]        = float(customer.get("credit_score") or 650)
                    enriched["industry"]            = customer.get("industry", "unknown")
                    enriched["customer_age_months"] = int(
                        customer.get("account_age_months") or 12
                    )

                return enriched
        except Exception as e:
            logger.warning(
                "[request_id=%s] ⚠️ Customer data enrichment failed: %s",
                request_id, e,
            )
            return payload

    async def _persist(
        self,
        result:       dict,
        payload:      dict,
        request_id:   str,
        execution_ms: int,
    ) -> None:
        """Save decision to DB + push to metrics bridge immediately."""
        try:
            from core.db import (
                update_invoice_status,
                save_finance_decision,
                write_audit_log,
                write_finance_audit,
            )

            invoice_id = payload.get("invoice_id")
            decision   = result.get("decision", "unknown")

            status_map = {
                "safe_to_collect":  "overdue",
                "soft_follow_up":   "overdue",
                "hard_follow_up":   "overdue",
                "payment_plan":     "payment_plan",
                "suspend_service":  "suspended",
                "legal_escalation": "legal",
                "write_off":        "written_off",
                "on_hold_disputed": "disputed",
                "payment_complete": "paid",
                "partial_payment":  "partial",
            }
            new_status = status_map.get(decision, "overdue")

            if invoice_id:
                try:
                    update_invoice_status(
                        invoice_id      = invoice_id,
                        status          = new_status,
                        ai_decision     = decision,
                        risk_score      = float(result.get("risk_score", 0)),
                        decision_reason = result.get("reason", "")[:1000],
                        action_plan     = str(result.get("action_plan", [])),
                        request_id      = request_id,
                    )
                except Exception as e:
                    logger.warning(
                        "[request_id=%s] ⚠️ update_invoice_status failed: %s",
                        request_id, e,
                    )

            try:
                save_finance_decision({
                    "agent_type":   "finance_agent_v2.1",
                    "entity":       "invoices",
                    "entity_id":    int(invoice_id or 0),
                    "event_id":     payload.get("event_id"),
                    "decision":     decision,
                    "confidence":   float(result.get("confidence", 0)),
                    "risk_score":   float(result.get("risk_score", 0)),
                    "reasoning":    result.get("reason", "")[:500],
                    "action_plan":  str(result.get("action_plan", [])),
                    "execution_ms": execution_ms,
                    "request_id":   request_id,
                })
            except Exception as e:
                logger.warning(
                    "[request_id=%s] ⚠️ save_finance_decision failed: %s",
                    request_id, e,
                )

            try:
                write_finance_audit(
                    domain          = "invoice",
                    entity_id       = int(invoice_id or 0),
                    customer_id     = int(payload.get("customer_id", 0) or 0),
                    decision        = decision,
                    risk_score      = float(result.get("risk_score", 0)),
                    confidence      = float(result.get("confidence", 0)),
                    decision_source = result.get("model_source", "agent"),
                    llm_used        = bool(result.get("llm_used", False)),
                    request_id      = request_id,
                    execution_ms    = execution_ms,
                    action_plan     = result.get("action_plan", []),
                )
            except Exception as e:
                logger.warning(
                    "[request_id=%s] ⚠️ write_finance_audit failed: %s",
                    request_id, e,
                )

            write_audit_log(
                action       = f"invoice_{decision}",
                entity       = "invoices",
                entity_id    = int(invoice_id or 0),
                performed_by = "finance_agent_v2.1",
                details      = (
                    f"[request_id={request_id}] "
                    f"risk={result.get('risk_score', 0):.0%} | "
                    f"action={result.get('primary_action')} | "
                    f"exec={execution_ms}ms | "
                    f"{result.get('reason', '')[:150]}"
                ),
            )

            # ── v2.0: Push to Metrics Bridge immediately after persist ──────
            try:
                from core.finance_metrics_bridge import metrics_bridge
                await metrics_bridge.on_invoice_decision(result, {
                    **payload,
                    "new_status": new_status,
                })
            except Exception as e:
                logger.warning("[request_id=%s] ⚠️ metrics_bridge.on_invoice_decision failed (non-critical): %s", request_id, e)

        except Exception as e:
            logger.error(
                "[request_id=%s] ❌ Finance persist failed: %s",
                request_id, e,
            )

    async def _execute_actions(
        self, result: dict, payload: dict, request_id: str
    ) -> list:
        from actions.finance_actions import FinanceActionExecutor

        executor     = FinanceActionExecutor()
        action_plan  = result.get("action_plan", [])
        actions_done = []

        for action in action_plan:
            try:
                action_result = await executor.execute(
                    action      = action,
                    invoice_id  = payload.get("invoice_id"),
                    customer_id = payload.get("customer_id"),
                    amount      = float(payload.get("amount", 0)),
                    decision    = result.get("decision"),
                    reason      = result.get("reason", ""),
                    request_id  = request_id,
                    extra_data  = result.get("payment_plan_terms"),
                )
                actions_done.append({
                    "action": action,
                    "status": "executed",
                    "result": action_result,
                })
                logger.info(
                    "[request_id=%s] ✅ Action executed: %s",
                    request_id, action,
                )

                # ── v2.0: Push action metric ─────────────────────────────────
                try:
                    from core.finance_metrics_bridge import metrics_bridge
                    await metrics_bridge.on_action_executed(
                        action      = action,
                        invoice_id  = payload.get("invoice_id"),
                        customer_id = payload.get("customer_id"),
                        amount      = float(payload.get("amount", 0)),
                        result      = action_result,
                    )
                except Exception:
                    pass

            except Exception as e:
                logger.warning(
                    "[request_id=%s] ⚠️ Action failed: %s — %s",
                    request_id, action, e,
                )
                actions_done.append({
                    "action": action,
                    "status": "failed",
                    "error":  str(e),
                })

        return actions_done


# ═════════════════════════════════════════════════════════════════════════════
# 🧾  NEW INVOICE WORKFLOW
# ═════════════════════════════════════════════════════════════════════════════

class NewInvoiceWorkflow:

    def __init__(self) -> None:
        self._agent = None

    @property
    def agent(self):
        if self._agent is None:
            from agents.finance.finance_agent import FinanceAgent
            self._agent = FinanceAgent()
        return self._agent

    async def async_run(self, payload: dict) -> dict:
        request_id        = payload.get("request_id") or generate_request_id()
        payload           = {**payload, "request_id": request_id}
        invoice_id        = payload.get("invoice_id")
        workflow_start_ms = int(time.time() * 1000)   # ✅ v2.1: track full time

        logger.info(
            "[request_id=%s] 🧾 NewInvoiceWorkflow started — invoice=%s",
            request_id, invoice_id,
        )

        try:
            result = await self.agent.process_new_invoice(payload)
        except Exception as e:
            logger.error("[request_id=%s] ❌ NewInvoiceWorkflow failed: %s", request_id, e)
            result = {
                "decision":            "invoice_registered",
                "collection_strategy": "standard",
                "reason":              f"Registration error: {e}",
                "request_id":          request_id,
            }

        await self._persist(result, payload, request_id)
        result["workflow"] = "NewInvoiceWorkflow_v2.1"

        # ✅ v2.1: Completion signal
        try:
            total_ms = int(time.time() * 1000) - workflow_start_ms
            from core.finance_metrics_bridge import metrics_bridge
            await metrics_bridge.on_workflow_completed(
                workflow_name = "NewInvoiceWorkflow",
                result        = result,
                payload       = payload,
                execution_ms  = total_ms,
            )
        except Exception as e:
            logger.warning("[request_id=%s] ⚠️ completion signal failed: %s", request_id, e)

        return result

    def run(self, payload: dict) -> dict:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(asyncio.run, self.async_run(payload)).result(timeout=60)
            return loop.run_until_complete(self.async_run(payload))
        except Exception as e:
            return {"decision": "invoice_registered", "error": str(e)}

    async def _persist(self, result: dict, payload: dict, request_id: str) -> None:
        try:
            from core.db import write_audit_log, update_invoice_collection_strategy
            invoice_id = payload.get("invoice_id")
            if invoice_id:
                try:
                    update_invoice_collection_strategy(
                        invoice_id           = invoice_id,
                        risk_score           = float(result.get("risk_score", 0)),
                        collection_strategy  = result.get("collection_strategy", "standard"),
                        first_reminder_days  = int(result.get("first_reminder_days", 7)),
                        request_id           = request_id,
                    )
                except Exception as e:
                    logger.warning("[request_id=%s] ⚠️ update_invoice_collection_strategy failed: %s", request_id, e)

            write_audit_log(
                action       = "invoice_risk_assessed",
                entity       = "invoices",
                entity_id    = int(invoice_id or 0),
                performed_by = "finance_agent_v2.1",
                details      = (
                    f"[request_id={request_id}] strategy={result.get('collection_strategy')} | "
                    f"risk={result.get('risk_score', 0):.0%}"
                ),
            )

            # ── v2.0: Push new invoice metric ────────────────────────────────
            try:
                from core.finance_metrics_bridge import metrics_bridge
                await metrics_bridge.on_invoice_decision(result, payload)
            except Exception:
                pass

        except Exception as e:
            logger.warning("[request_id=%s] ⚠️ NewInvoice persist failed: %s", request_id, e)


# ═════════════════════════════════════════════════════════════════════════════
# 💳  PAYMENT RECEIVED WORKFLOW
# ═════════════════════════════════════════════════════════════════════════════

class PaymentReceivedWorkflow:

    def __init__(self) -> None:
        self._agent = None

    @property
    def agent(self):
        if self._agent is None:
            from agents.finance.finance_agent import FinanceAgent
            self._agent = FinanceAgent()
        return self._agent

    async def async_run(self, payload: dict) -> dict:
        request_id        = payload.get("request_id") or generate_request_id()
        payload           = {**payload, "request_id": request_id}
        invoice_id        = payload.get("invoice_id")
        amount_paid       = float(payload.get("amount_paid", 0))
        workflow_start_ms = int(time.time() * 1000)   # ✅ v2.1: track full time

        logger.info(
            "[request_id=%s] 💳 PaymentReceivedWorkflow started — "
            "invoice=%s amount=%s",
            request_id, invoice_id, amount_paid,
        )

        try:
            result = await self.agent.process_payment_received(payload)
        except Exception as e:
            logger.error("[request_id=%s] ❌ PaymentReceivedWorkflow failed: %s", request_id, e)
            result = {"decision": "payment_complete", "error": str(e), "request_id": request_id}

        await self._persist(result, payload, request_id)
        result["workflow"] = "PaymentReceivedWorkflow_v2.1"

        # ✅ v2.1: Completion signal
        try:
            total_ms = int(time.time() * 1000) - workflow_start_ms
            from core.finance_metrics_bridge import metrics_bridge
            await metrics_bridge.on_workflow_completed(
                workflow_name = "PaymentReceivedWorkflow",
                result        = result,
                payload       = payload,
                execution_ms  = total_ms,
            )
        except Exception as e:
            logger.warning("[request_id=%s] ⚠️ completion signal failed: %s", request_id, e)

        return result

    def run(self, payload: dict) -> dict:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(asyncio.run, self.async_run(payload)).result(timeout=60)
            return loop.run_until_complete(self.async_run(payload))
        except Exception as e:
            return {"decision": "payment_complete", "error": str(e)}

    async def _persist(self, result: dict, payload: dict, request_id: str) -> None:
        try:
            from core.db import write_audit_log
            invoice_id  = payload.get("invoice_id")
            amount_paid = float(payload.get("amount_paid", 0))
            decision    = result.get("decision", "payment_complete")

            if invoice_id and decision == "payment_complete":
                try:
                    import importlib
                    db_module = importlib.import_module("core.db")
                    with db_module.get_db() as (conn, cur):
                        cur.execute(
                            "UPDATE invoices SET status='paid', paid_at=NOW() WHERE id=%s",
                            (invoice_id,),
                        )
                        conn.commit()
                except Exception as e:
                    logger.warning("[request_id=%s] ⚠️ Invoice update failed: %s", request_id, e)

            write_audit_log(
                action       = f"payment_{decision}",
                entity       = "invoices",
                entity_id    = int(invoice_id or 0),
                performed_by = "finance_agent_v2.1",
                details      = (
                    f"[request_id={request_id}] "
                    f"amount_paid={amount_paid:,.2f} EGP | decision={decision}"
                ),
            )

            # ── v2.0: Push payment metric → Dashboard يتحدّث فورًا ──────────
            try:
                from core.finance_metrics_bridge import metrics_bridge
                await metrics_bridge.on_payment_received(
                    invoice_id  = invoice_id,
                    customer_id = payload.get("customer_id"),
                    amount_paid = amount_paid,
                    decision    = decision,
                )
            except Exception as e:
                logger.warning("[request_id=%s] ⚠️ metrics_bridge.on_payment_received failed (non-critical): %s", request_id, e)

        except Exception as e:
            logger.warning("[request_id=%s] ⚠️ PaymentReceived persist failed: %s", request_id, e)