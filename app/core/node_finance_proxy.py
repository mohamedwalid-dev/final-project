"""
core/node_finance_proxy.py — FinanceDB Drop-in Replacement (Node.js API)
=========================================================================
Provides get_finance_db() that returns a NodeFinanceProxy instance.

Every method mirrors the old FinanceDB (Motor) interface but routes
through NodeAPIClient → Node.js Express API → MongoDB.

v2 — توسيع شامل ليغطي كل الـ routes الموجودة في finance.routes.js:
    ✅ Customer CRUD كامل (create/update/delete)
    ✅ Invoice CRUD كامل (create/delete بالإضافة لـ read/update)
    ✅ get_customer بترجع invoice_summary زي ما الـ controller بيعملها
    ✅ Legal case create/read/update (مفيش delete route في Node)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional, List

logger = logging.getLogger(__name__)


class MockCursor:
    def __init__(self, items=None): self.items = items or []
    def sort(self, *args, **kwargs): return self
    def limit(self, *args, **kwargs): return self
    def __aiter__(self): self.iter = iter(self.items); return self
    async def __anext__(self):
        try: return next(self.iter)
        except StopIteration: raise StopAsyncIteration

class MockCollection:
    def find(self, *args, **kwargs): return MockCursor()
    async def find_one(self, *args, **kwargs): return None
    async def insert_one(self, *args, **kwargs): 
        class MockResult: inserted_id = "mock"
        return MockResult()
    async def update_one(self, *args, **kwargs):
        class MockResult: modified_count = 1
        return MockResult()

class MockDB:
    def __getitem__(self, name): return MockCollection()

class NodeFinanceProxy:
    db = MockDB()
    invoices = MockCollection()
    customers = MockCollection()

    """
    Drop-in replacement for FinanceDB (Motor).
    Every method maps to a NodeAPIClient call.
    """

    def __init__(self):
        from core.node_api_client import get_node_api_client
        self._client = get_node_api_client()

    # ── Invoices ─────────────────────────────────────────────────────────

    async def create_invoice(self, invoice_data: dict) -> dict:
        """POST /finance/invoices"""
        return await self._client.create_resource("/finance/invoices", invoice_data)

    async def get_invoices(self, status: Optional[str] = None, limit: int = 50, skip: int = 0) -> list:
        return await self._client.get_invoices(status=status, limit=limit, skip=skip)

    async def get_pending_invoices(self) -> list:
        return await self._client.get_pending_invoices()

    async def get_overdue_invoices(self, min_days: int = 1, limit: int = 200) -> list:
        """min_days مش مدعوم من الـ Node endpoint حالياً (بيرجّع كل الـ overdue) —
        بنفلتر overdue_days محلياً في بايثون، وبنحترم الـ limit بعد الفلترة."""
        invoices = await self._client.get_overdue_invoices()
        if min_days > 1:
            invoices = [
                inv for inv in invoices
                if int(inv.get("overdue_days_calc") or inv.get("overdue_days") or 0) >= min_days
            ]
        return invoices[:limit] if limit else invoices

    async def get_pending_unassessed_invoices(self, hours: int = 24, limit: int = 50) -> list:
        """بديل الـ Mongo aggregate القديم (status=pending + customer join + ai_risk_score فاضي).
        بيستخدم GET /finance/invoices?status=pending العادي، وبيفلتر ai_risk_score
        + created_at محلياً في بايثون لحد ما يتعمل endpoint مخصص في Node.
        ⚠️ مؤقت: مفيش customer_name/credit_score/industry هنا لو الـ Node endpoint
        مش بيرجّعهم مضمّنين مع الـ invoice — الـ caller لازم يتعامل مع القيم الافتراضية."""
        from datetime import datetime, timezone, timedelta

        raw = await self._client.get_invoices(status="pending", limit=500, skip=0)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        def _is_unassessed(inv: dict) -> bool:
            score = inv.get("ai_risk_score")
            return score in (None, 0, "0")

        def _is_recent(inv: dict) -> bool:
            created = inv.get("created_at")
            if not created:
                return True  # مفيش تاريخ → منسيبهاش تتفلتر بره غلط
            try:
                if isinstance(created, str):
                    created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                else:
                    created_dt = created
                if created_dt.tzinfo is None:
                    created_dt = created_dt.replace(tzinfo=timezone.utc)
                return created_dt >= cutoff
            except Exception:
                return True

        filtered = [inv for inv in raw if _is_unassessed(inv) and _is_recent(inv)]
        filtered.sort(key=lambda i: i.get("created_at", ""), reverse=True)
        return filtered[:limit]

    async def get_invoice(self, invoice_id: str) -> dict:
        return await self._client.get_invoice(invoice_id)

    async def update_invoice_status(self, invoice_id: str, status: str, **kwargs) -> bool:
        try:
            payload = {"status": status, **kwargs}
            await self._client.update_resource(
                f"/finance/invoices/{invoice_id}/status", payload
            )
            return True
        except Exception as e:
            logger.warning("⚠️ update_invoice_status failed: %s", e)
            return False

    async def update_invoice_collection_strategy(self, invoice_id: str, strategy: str, **kwargs) -> bool:
        try:
            payload = {"strategy": strategy, **kwargs}
            await self._client.update_resource(
                f"/finance/invoices/{invoice_id}/strategy", payload
            )
            return True
        except Exception as e:
            logger.warning("⚠️ update_invoice_collection_strategy failed: %s", e)
            return False

    async def delete_invoice(self, invoice_id: str) -> bool:
        """DELETE /finance/invoices/:id"""
        try:
            await self._client.delete_resource(f"/finance/invoices/{invoice_id}")
            return True
        except Exception as e:
            logger.warning("⚠️ delete_invoice failed: %s", e)
            return False

    # ── Customers ────────────────────────────────────────────────────────

    async def create_customer(self, customer_data: dict) -> dict:
        """POST /finance/customers"""
        return await self._client.create_resource("/finance/customers", customer_data)

    async def get_customers(self, status: Optional[str] = None, limit: int = 50) -> list:
        return await self._client.get_customers(status=status, limit=limit)

    async def get_customer(self, customer_id: str) -> dict:
        """GET /finance/customers/:id — الـ controller بيرجّع { ...customer,
        invoice_summary: {...} } جواها، فبتيجي هنا زي ما هي من غير تعديل إضافي."""
        return await self._client.get_customer(customer_id)

    async def get_customer_email(self, customer_id: str) -> Optional[str]:
        try:
            customer = await self._client.get_customer(customer_id)
            return customer.get("email") or customer.get("contact_email")
        except Exception:
            return None

    async def update_customer(self, customer_id: str, **kwargs) -> bool:
        """PATCH /finance/customers/:id"""
        try:
            await self._client.update_resource(f"/finance/customers/{customer_id}", kwargs)
            return True
        except Exception as e:
            logger.warning("⚠️ update_customer failed: %s", e)
            return False

    async def delete_customer(self, customer_id: str) -> bool:
        """DELETE /finance/customers/:id"""
        try:
            await self._client.delete_resource(f"/finance/customers/{customer_id}")
            return True
        except Exception as e:
            logger.warning("⚠️ delete_customer failed: %s", e)
            return False

    # ── Legal Cases ──────────────────────────────────────────────────────

    async def get_legal_cases(self, status: Optional[str] = None,
                               customer_id: Optional[str] = None,
                               limit: int = 50) -> list:
        return await self._client.get_legal_cases(status=status, limit=limit)

    async def get_legal_case(self, case_id: str) -> Optional[dict]:
        try:
            return await self._client.get_legal_case(case_id)
        except Exception:
            return None

    async def create_legal_case(self, case_data: dict) -> dict:
        return await self._client.create_resource("/finance/legal-cases", case_data)

    async def update_legal_case_status(self, case_id: str, status: str,
                                        note: Optional[str] = None,
                                        resolution: Optional[str] = None) -> bool:
        try:
            payload = {"status": status}
            if note:
                payload["note"] = note
            if resolution:
                payload["resolution"] = resolution
            await self._client.update_resource(
                f"/finance/legal-cases/{case_id}/status", payload
            )
            return True
        except Exception as e:
            logger.warning("⚠️ update_legal_case_status failed: %s", e)
            return False

    # ⚠️ مفيش DELETE /finance/legal-cases/:id في finance.routes.js —
    # لو محتاجها لاحقاً، ضيف الـ route في Node الأول.

    # ── Escalations ──────────────────────────────────────────────────────

    async def get_active_escalations(self) -> list:
        return await self._client.get_active_escalations()

    async def get_escalation_status(self, invoice_id: str) -> dict:
        return await self._client.get_escalation_status(invoice_id)

    # ── Collections ──────────────────────────────────────────────────────

    async def get_collection_log(self, invoice_id: Optional[str] = None,
                                  customer_id: Optional[str] = None,
                                  action_type: Optional[str] = None,
                                  limit: int = 100) -> list:
        return await self._client.get_collection_log(
            invoice_id=invoice_id, customer_id=customer_id, limit=limit
        )

    async def get_collection_action_stats(self, days: int = 7) -> dict:
        return await self._client.get_collection_stats(days=days)

    async def log_collection_action(self, action_data: dict) -> dict:
        return await self._client.create_resource("/finance/collections/log", action_data)

    # ── Audit ────────────────────────────────────────────────────────────

    async def write_finance_audit(self, **kwargs) -> dict:
        return await self._client.create_resource("/finance/audit", kwargs)

    async def get_finance_audit(self, entity_id: str, domain: str = "invoice") -> list:
        return await self._client.get_finance_audit(entity_id, domain=domain)

    # ── Decisions ────────────────────────────────────────────────────────

    async def save_finance_decision(self, decision: dict) -> dict:
        return await self._client.create_resource("/finance/decisions", decision)

    async def get_finance_decisions(self, entity_id: str) -> list:
        return await self._client.get_finance_decisions(entity_id)

    async def get_recent_decisions(self, days: int = 7, max_invoices: int = 100) -> list:
        """
        ⚠️ بديل بايثون-فقط (مفيش endpoint list-all لـ /finance/decisions في Node) —
        بيجيب أحدث الـ invoices (overdue + pending) الأول، وبعدين بينادي
        GET /finance/decisions/{invoice_id} لكل واحدة على حدة ويجمع النتايج.

        ده أبطأ من endpoint واحد (N+1 calls) وبيغطي بس الـ invoices اللي
        جايه في get_overdue_invoices/get_invoices، مش كل decision في النظام.
        كافي لعمل decision-history chart تقريبي، مش مصدر حقيقة دقيق 100%.
        """
        try:
            overdue = await self.get_overdue_invoices(min_days=1, limit=max_invoices // 2)
            pending = await self.get_invoices(status="pending", limit=max_invoices // 2, skip=0)

            seen_ids = set()
            invoice_ids = []
            for inv in (overdue + pending):
                inv_id = str(inv.get("_id") or inv.get("id") or "")
                if inv_id and inv_id not in seen_ids:
                    seen_ids.add(inv_id)
                    invoice_ids.append(inv_id)

            all_decisions = []
            for inv_id in invoice_ids[:max_invoices]:
                try:
                    decisions = await self._client.get_finance_decisions(inv_id)
                    if isinstance(decisions, list):
                        all_decisions.extend(decisions)
                except Exception as e:
                    logger.debug("get_recent_decisions: skip invoice %s (%s)", inv_id, e)
                    continue

            return all_decisions

        except Exception as e:
            logger.warning("⚠️ get_recent_decisions failed: %s", e)
            return []

    # ── Dashboard ────────────────────────────────────────────────────────

    async def get_finance_dashboard_stats(self) -> dict:
        return await self._client.get_finance_dashboard()

    async def get_cashflow_forecast(self) -> dict:
        return await self._client.get_cashflow_forecast()


# ─────────────────────────────────────────────────────────────────────────────
# Singleton accessor — same calling convention as the old get_finance_db()
# ─────────────────────────────────────────────────────────────────────────────

_proxy: Optional[NodeFinanceProxy] = None


def get_finance_db() -> NodeFinanceProxy:
    """Drop-in replacement for core.mongo_connect.get_finance_db()."""
    global _proxy
    if _proxy is None:
        _proxy = NodeFinanceProxy()
        logger.info("✅ NodeFinanceProxy initialized (replaces FinanceDB/Motor)")
    return _proxy