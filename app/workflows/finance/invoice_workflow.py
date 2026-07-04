"""
🔄 Finance Invoice Workflow — v3.1 (Node.js API)
====================================================
File: app/workflows/finance/invoice_workflow.py

v3.1 Changes (Migration: MongoDB مباشر → Node.js API عبر NodeFinanceProxy):
    ✅ اتشال الـ InvoiceDBProxy المحلي (كان بيحاكي Motor بشكل جزئي وناقص
       ومكسور runtime — db.update_invoice_status() كانت بتتنادى بباراميترز
       أكتر من اللي الـ proxy المحلي كان بيقبلها).
    ✅ استخدام core.node_finance_proxy.get_finance_db() الموحّد بدل proxy
       منفصل — نفس الـ instance اللي باقي الملفات (finance_trigger.py,
       trigger.py, finance_realtime.py, metrics_collector.py) بتستخدمه.
    ✅ _get_invoice_status()        ← NodeFinanceProxy.get_invoice()
    ✅ _claim_invoice()             ← اتحول من atomic Mongo update_one
       (بشرط $nin على status) لـ read-then-write بسيط عبر REST، لأن
       الـ Node API مفيهوش endpoint claim ذري. انظر التحذير في الدالة.
    ✅ _enrich_with_customer_data() ← get_overdue_invoices()/get_invoices()
       + get_customer() بدل aggregation pipeline (مفيش endpoint
       /finance/customers/:id/metrics في Node أصلاً — كان بيرجع 404 دايماً).
    ✅ _persist()                   ← NodeFinanceProxy.update_invoice_status()
       بالتوقيع الصحيح (ai_decision/risk_score/... كـ **kwargs زي
       باقي الملفات).

⚠️ فقدان الذرية (atomicity) في _claim_invoice():
    الكود القديم كان بيعتمد على MongoDB atomic update_one($nin) عشان
    يمنع اتنين workers ياخدوا نفس الـ invoice في نفس اللحظة. الـ Node
    REST API الحالي مفيهوش endpoint بيعمل نفس الحركة الذرية، فالكود
    هنا بيعمل read-then-write (يقرا الحالة، لو مش terminal يكتب
    "in_progress_collection"). ده فيه احتمال ضئيل لـ race condition
    لو اتنين instances نادوا في نفس اللحظة بالظبط. لو محتاج ضمان ذري
    حقيقي، لازم يتعمل endpoint في Node بيعمل findOneAndUpdate مع شرط
    status، وترجع فيه نجح الـ claim ولا لأ.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional


from agents.base_agent import generate_request_id

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {
    "paid", "settled", "written_off", "cancelled",
    "disputed", "in_progress_collection",
}


# ══════════════════════════════════════════════════════════════════════════════
# 🔌  DB helper — نفس الـ NodeFinanceProxy الموحّد المستخدم في كل الملفات التانية
# ══════════════════════════════════════════════════════════════════════════════

def _get_db():
    """Return shared NodeFinanceProxy instance (نفس اللي finance_trigger.py,
    trigger.py, finance_realtime.py, metrics_collector.py بيستخدموه)."""
    from core.node_finance_proxy import get_finance_db
    return get_finance_db()


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

        workflow_start_ms = int(time.time() * 1000)

        self.audit_logger.log(
            event_type="invoice_overdue",
            stage="workflow",
            message=(
                f"[request_id={request_id}] OverdueInvoiceWorkflow started — "
                f"invoice={invoice_id} customer={customer_id}"
            ),
        )

        # ── Step 0: Status Pre-Check ──────────────────────────────────────
        if invoice_id:
            current_status = await self._get_invoice_status(invoice_id)
            if current_status in TERMINAL_STATUSES:
                logger.info(
                    "[request_id=%s] ⏭️ Invoice #%s terminal status=%s — skipping",
                    request_id, invoice_id, current_status,
                )
                result = {
                    "decision":   "skipped",
                    "confidence": 1.0,
                    "invoice_id": invoice_id,
                    "reasoning":  f"Invoice already in terminal state: {current_status}",
                    "workflow":   "OverdueInvoiceWorkflow_v3.1",
                    "request_id": request_id,
                    "skipped":    True,
                }
                await self._emit_completion(result, payload, workflow_start_ms)
                return result

        # ── Step 1: Claim (best-effort, non-atomic — see module docstring) ─
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
                    "workflow":   "OverdueInvoiceWorkflow_v3.1",
                    "request_id": request_id,
                }
                await self._emit_completion(result, payload, workflow_start_ms)
                return result

        # ── Step 2: Enrich payload ────────────────────────────────────────
        payload = await self._enrich_with_customer_data(payload, request_id)

        # ── Step 3: Finance Agent Decision ───────────────────────────────
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

        # ── Step 4: Persist to DB ─────────────────────────────────────────
        await self._persist(agent_result, payload, request_id, execution_ms)

        # ── Step 5: Execute Actions ───────────────────────────────────────
        actions_taken = await self._execute_actions(agent_result, payload, request_id)

        # ── Step 6: Build Final Result ────────────────────────────────────
        result = {
            **agent_result,
            "workflow":      "OverdueInvoiceWorkflow_v3.1",
            "execution_ms":  execution_ms,
            "actions_taken": actions_taken,
        }

        self.audit_logger.log(
            event_type="invoice_overdue",
            stage="workflow",
            message=(
                f"[request_id={request_id}] OverdueInvoiceWorkflow complete — "
                f"invoice={invoice_id} decision={agent_result.get('decision')}"
            ),
            data={
                "decision":      agent_result.get("decision"),
                "risk_score":    agent_result.get("risk_score"),
                "execution_ms":  execution_ms,
                "actions_taken": actions_taken,
            },
        )

        # ── Step 7: Completion Signal ─────────────────────────────────────
        await self._emit_completion(result, payload, workflow_start_ms)
        return result

    # ── _emit_completion ──────────────────────────────────────────────────

    async def _emit_completion(
        self, result: dict, payload: dict, workflow_start_ms: int
    ) -> None:
        try:
            total_ms = int(time.time() * 1000) - workflow_start_ms
            from core.finance_metrics_bridge import metrics_bridge
            await metrics_bridge.on_workflow_completed(
                workflow_name="OverdueInvoiceWorkflow",
                result=result,
                payload=payload,
                execution_ms=total_ms,
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

    # ── Private Helpers ───────────────────────────────────────────────────

    async def _get_invoice_status(self, invoice_id) -> Optional[str]:
        """✅ v3.1: NodeFinanceProxy.get_invoice() بدل db.invoices.find_one()."""
        try:
            db  = _get_db()
            inv = await db.get_invoice(str(invoice_id))
            return inv.get("status") if inv else None
        except Exception as e:
            logger.warning("⚠️ Could not check invoice status: %s", e)
            return None

    async def _claim_invoice(self, invoice_id, request_id: str) -> bool:
        """
        ⚠️ v3.1: مش atomic حقيقي — انظر التحذير في docstring الملف.
        بنعمل read-then-write: نقرا الحالة الحالية، لو مش terminal
        نكتب "in_progress_collection". فيه نافذة زمنية صغيرة لسباق
        بين قراءتين متزامنتين، لكن ده أقصى ما يمكن عمله عبر REST
        عادي من غير endpoint claim ذري في Node.
        """
        try:
            db  = _get_db()
            oid = str(invoice_id)

            current = await db.get_invoice(oid)
            current_status = current.get("status") if current else None
            if current_status in TERMINAL_STATUSES:
                return False

            ok = await db.update_invoice_status(
                invoice_id=oid,
                status="in_progress_collection",
            )
            return bool(ok)
        except Exception as e:
            logger.warning(
                "[request_id=%s] ⚠️ Invoice claim failed: %s — allowing through",
                request_id, e,
            )
            return True   # fail-open: نخلي الـ workflow يكمل

    async def _enrich_with_customer_data(self, payload: dict, request_id: str) -> dict:
        """
        ✅ v3.1: بدل aggregation pipeline (كان بينادي endpoint وهمي
        /finance/customers/:id/metrics مش موجود أصلاً في Node) —
        بنستخدم get_invoices(customer-side filtering غير مدعوم من
        الـ endpoint، فبنحسب من get_overdue_invoices + get_invoices
        العامة) + get_customer() العادية.

        ⚠️ ملحوظة دقة: الـ Node API الحالي مفيهوش endpoint بيرجّع
        invoice history *لعميل معين* بشكل مباشر (GET /finance/invoices
        بيقبل customer_id كـ query param حسب finance.controller.js —
        فده بالفعل بيشتغل صح ودقيق، مش تقريبي).
        """
        customer_id = payload.get("customer_id")
        if not customer_id:
            return payload

        try:
            db  = _get_db()
            cid = str(customer_id)

            # ── Payment history (كل invoices العميل ده، آخر 12 شهر) ───────
            from datetime import datetime, timezone, timedelta
            cutoff = datetime.now(timezone.utc) - timedelta(days=365)

            # GET /finance/invoices?customer_id=... — مدعومة فعلياً في
            # finance.controller.js (getAllInvoices بتفلتر بـ customer_id)
            customer_invoices = await db._client.get_invoices(
                status=None, limit=500, skip=0
            )
            # الـ Node endpoint العام مش بيفلتر بـ customer_id مباشرة عبر
            # NodeAPIClient.get_invoices() الحالية (params: status/limit/skip
            # بس) — بنفلتر هنا في بايثون على customer_id + التاريخ.
            relevant = [
                inv for inv in customer_invoices
                if str(inv.get("customer_id", "")) == cid
                and inv.get("status") != "draft"
            ]

            def _parse_dt(v):
                if not v:
                    return None
                try:
                    if isinstance(v, str):
                        return datetime.fromisoformat(v.replace("Z", "+00:00"))
                    return v
                except Exception:
                    return None

            recent = []
            for inv in relevant:
                created = _parse_dt(inv.get("created_at"))
                if created and created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                if created is None or created >= cutoff:
                    recent.append(inv)

            total_invoices = len(recent)
            paid_count     = sum(1 for i in recent if i.get("status") == "paid")
            overdue_count  = sum(1 for i in recent if i.get("status") == "overdue")

            delays = []
            for inv in recent:
                if inv.get("status") != "paid":
                    continue
                due  = _parse_dt(inv.get("due_date"))
                upd  = _parse_dt(inv.get("updated_at"))
                if due and upd:
                    if due.tzinfo is None:
                        due = due.replace(tzinfo=timezone.utc)
                    if upd.tzinfo is None:
                        upd = upd.replace(tzinfo=timezone.utc)
                    delays.append((upd - due).total_seconds() / 86400.0)

            avg_delay_days = round(sum(delays) / len(delays), 2) if delays else 0.0

            enriched = {
                **payload,
                "payment_history_count":  total_invoices,
                "payment_history_paid":   paid_count,
                "payment_history_late":   overdue_count,
                "avg_payment_delay_days": avg_delay_days,
            }

            # ── Customer info ─────────────────────────────────────────────
            customer = await db.get_customer(cid)
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
        """
        ✅ v3.1: NodeFinanceProxy methods بدل InvoiceDBProxy المحلي.
        update_invoice_status() هنا بتقبل **kwargs زي باقي الملفات
        (finance_trigger.py, trigger.py) — التوقيع اتصحح.
        """
        db         = _get_db()
        invoice_id = payload.get("invoice_id")
        decision   = result.get("decision", "unknown")

        STATUS_MAP = {
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
        new_status = STATUS_MAP.get(decision, "overdue")

        # 1. Update invoice status ─────────────────────────────────────────
        if invoice_id:
            try:
                await db.update_invoice_status(
                    invoice_id      = str(invoice_id),
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

        # 2. Save AI decision ──────────────────────────────────────────────
        try:
            await db.save_finance_decision({
                "agent_type":   "finance_agent_v3.1",
                "entity":       "invoices",
                "entity_id":    str(invoice_id) if invoice_id else None,
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

        # 3. Finance audit ─────────────────────────────────────────────────
        try:
            await db.write_finance_audit(
                domain          = "invoice",
                entity_id       = str(invoice_id) if invoice_id else None,
                customer_id     = str(payload["customer_id"]) if payload.get("customer_id") else None,
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

        # 4. Metrics bridge ────────────────────────────────────────────────
        try:
            from core.finance_metrics_bridge import metrics_bridge
            await metrics_bridge.on_invoice_decision(result, {
                **payload,
                "new_status": new_status,
            })
        except Exception as e:
            logger.warning(
                "[request_id=%s] ⚠️ metrics_bridge.on_invoice_decision failed: %s",
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
                logger.info("[request_id=%s] ✅ Action executed: %s", request_id, action)

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
        workflow_start_ms = int(time.time() * 1000)

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
        result["workflow"] = "NewInvoiceWorkflow_v3.1"

        # Completion signal
        try:
            total_ms = int(time.time() * 1000) - workflow_start_ms
            from core.finance_metrics_bridge import metrics_bridge
            await metrics_bridge.on_workflow_completed(
                workflow_name="NewInvoiceWorkflow",
                result=result,
                payload=payload,
                execution_ms=total_ms,
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
        """✅ v3.1: NodeFinanceProxy.update_invoice_collection_strategy()."""
        db         = _get_db()
        invoice_id = payload.get("invoice_id")

        if invoice_id:
            try:
                await db.update_invoice_collection_strategy(
                    invoice_id           = str(invoice_id),
                    strategy             = result.get("collection_strategy", "standard"),
                    risk_score           = float(result.get("risk_score", 0)),
                    first_reminder_days  = int(result.get("first_reminder_days", 7)),
                    request_id           = request_id,
                )
            except Exception as e:
                logger.warning(
                    "[request_id=%s] ⚠️ update_invoice_collection_strategy failed: %s",
                    request_id, e,
                )

        # Metrics bridge
        try:
            from core.finance_metrics_bridge import metrics_bridge
            await metrics_bridge.on_invoice_decision(result, payload)
        except Exception:
            pass


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
        workflow_start_ms = int(time.time() * 1000)

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
        result["workflow"] = "PaymentReceivedWorkflow_v3.1"

        # Completion signal
        try:
            total_ms = int(time.time() * 1000) - workflow_start_ms
            from core.finance_metrics_bridge import metrics_bridge
            await metrics_bridge.on_workflow_completed(
                workflow_name="PaymentReceivedWorkflow",
                result=result,
                payload=payload,
                execution_ms=total_ms,
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
        """✅ v3.1: NodeFinanceProxy.update_invoice_status() بالتوقيع الصحيح."""
        db          = _get_db()
        invoice_id  = payload.get("invoice_id")
        amount_paid = float(payload.get("amount_paid", 0))
        decision    = result.get("decision", "payment_complete")

        if invoice_id and decision == "payment_complete":
            try:
                await db.update_invoice_status(
                    invoice_id  = str(invoice_id),
                    status      = "paid",
                    ai_decision = "payment_complete",
                    request_id  = request_id,
                )
            except Exception as e:
                logger.warning(
                    "[request_id=%s] ⚠️ Invoice paid update failed: %s",
                    request_id, e,
                )

        # Metrics bridge
        try:
            from core.finance_metrics_bridge import metrics_bridge
            await metrics_bridge.on_payment_received(
                invoice_id  = invoice_id,
                customer_id = payload.get("customer_id"),
                amount_paid = amount_paid,
                decision    = decision,
            )
        except Exception as e:
            logger.warning(
                "[request_id=%s] ⚠️ metrics_bridge.on_payment_received failed: %s",
                request_id, e,
            )