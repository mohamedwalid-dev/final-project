"""
core/node_hr_proxy.py — HRDB Drop-in Replacement (Node.js API)
================================================================
Provides get_hr_db() that returns a NodeHRProxy instance.

Every method mirrors the old HRDB (Motor) interface but routes
through NodeAPIClient → Node.js Express API → MongoDB.

v3 — متزامن مع node_api_client.py بعد تأكيد شكل الـ routes الحقيقي
     (hr.routes.js):
    ✅ get_leave_decision (GET /hr/leaves/:id/decision — كانت ناقصة)
    ✅ create_leave / delete_* لكل الـ 4 domains (leave/salary/absence/incentive)
    ✅ get_employee_leaves / get_employee_absences (routes بـ /employee/:id)
    ✅ write_hr_audit (POST /hr/audit) — alias واضح بدل write_hr_domain_audit بس

v4 — main.py alignment (2026-07):
    main.py يستدعي عدد من الميثودز اللي معندهاش endpoint خاص بيها في
    hr.routes.js المؤكد (لا يوجد /hr/employees، ولا /hr/events، ولا
    /hr/decisions عام، ولا /hr/memory). بدل ما main.py يفشل بـ
    AttributeError، الميثودز دي بقت موجودة هنا صراحة: يا إما aliases
    حقيقية فوق endpoints موجودة فعلاً (get_leave_status, get_balance_history,
    create_leave_request)، يا إما تجميع N+1 من endpoints موجودة
    (get_employee_salary_reviews, get_employee_incentives) لحد ما يتعمل
    endpoint مخصص في Node، يا إما no-op صريح مع تحذير في اللوج (الحالات
    اللي مفيش وراها أي route في Node خالص — راجع node_api_client.py
    docstring / hr.routes.js: مفيش /hr/employees, /hr/events, /hr/decisions
    عام, /hr/memory).
"""

from __future__ import annotations

import logging
from typing import Optional, List

logger = logging.getLogger(__name__)

def _extract_created_id(res, nested_key: str) -> str:
    """
    استخراج الـ id بعد إنشاء resource جديد، بشكل يتحمل أكتر من شكل رد
    محتمل من الـ Node controller:
      - dict فيه {nested_key: {"_id": ...}}   (الشكل القديم المتوقع)
      - dict فيه {"{nested_key}_id": ...} مباشرة (مثلاً "absence_id",
        "review_id", "incentive_id") — الشكل اللي hr.controller.js
        بيرجعه دلوقتي بعد ما بقى بيخزن محليًا بس من غير AI-agent loopback
      - dict فيه {"_id": ...} أو {"id": ...} مباشرة
      - list فيها dict واحد أو أكتر (بعض استجابات sendSuccess بترجع
        الـ data ملفوفة في array حتى لو هي object منطقيًا)
      - أي شكل تاني غير متوقع → "mock_id" بدل ما تنهار بـ AttributeError
    """
    if isinstance(res, list):
        res = res[0] if res else {}
    if not isinstance(res, dict):
        return "mock_id"

    nested = res.get(nested_key)
    if isinstance(nested, dict):
        _id = nested.get("_id") or nested.get("id")
        if _id:
            return str(_id)

    flat_id_key = f"{nested_key}_id"
    _id = res.get(flat_id_key)
    if _id:
        return str(_id)

    _id = res.get("_id") or res.get("id")
    if _id:
        return str(_id)

    return "mock_id"


def _normalize_decision_source(value: str) -> str:
    """
    الـ Node-side HRDomainAudit.decision_source عنده enum ضيق جدًا:
    ["ml", "llm", "rule"] فقط. الـ Python side بيستخدم أسماء أوصف
    وأدق بكتير (rule_fallback, ml_model, error_fallback, llm_agent,
    bg_workflow_v6.5, ...) عشان تبقى مفيدة في اللوج والـ debugging.
    الدالة دي بتـ map أي قيمة زي دي لأقرب قيمة من الـ enum المسموح،
    بدل ما تفشل الـ audit write بالكامل بـ 400 وتضيع الـ trail كله.
    القيمة التفصيلية الأصلية متسجلة برضو في اللوج (logger.info قبل
    الاستدعاء) فمفيش فقدان معلومة حقيقي، بس الـ Node schema مبيقبلش
    غير القيمة المطبّعة.
    """
    if not value:
        return "rule"
    v = str(value).lower()
    if "llm" in v:
        return "llm"
    if v in ("ml", "ml_model") or "ml_model" in v:
        return "ml"
    # كل حاجة تانية (rule_fallback, error_fallback, bg_workflow_*,
    # async_bg_*, on_demand, scheduler, ...) بترجع "rule" كـ default آمن
    return "rule"

def _normalize_single_record(res):
    """
    بعض ردود Node بتاعة GET .../:id بترجع list فيها عنصر واحد بدل dict
    مباشر (نفس الشكل الغريب اللي شفناه في create-endpoint responses).
    الدالة دي بتوحّد الشكل: لو list، ترجع أول عنصر (أو {} لو فاضية)؛
    لو مش dict خالص، ترجع {} بدل ما تسيب .get() تفشل بـ AttributeError
    في main.py.
    """
    if isinstance(res, list):
        return res[0] if res and isinstance(res[0], dict) else {}
    if isinstance(res, dict):
        return res
    return {}

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

class NodeHRProxy:
    db = MockDB()
    leaves = MockCollection()

    """
    Drop-in replacement for HRDB (Motor).
    Every method maps to a NodeAPIClient call.
    """

    def __init__(self):
        from core.node_api_client import get_node_api_client
        self._client = get_node_api_client()

    # ── Leaves ───────────────────────────────────────────────────────────

    async def create_leave(self, leave_data: dict) -> dict:
        """POST /hr/leaves — ملحوظة: الـ controller الحقيقي بيرجّع 202
        + agent_ref_id (بيبعت الطلب لـ Python AI Agent الأول). لو الطلب
        جاي من Python نفسه (loopback)، فكر تتجنب استخدام الـ method دي
        وتستخدم create_resource مباشرة على endpoint تاني لو موجود، عشان
        تتفادى submit مزدوج لنفس الـ AI Agent."""
        return await self._client.create_resource("/hr/leaves", leave_data)

    async def create_leave_request(self, leave_data: dict) -> str:
        """Alias — main.py (submit_leave_sync / submit_leave_async) بينادي
        create_leave_request() ومتوقع يرجع الـ leave_id (str) مباشرة، مش
        الـ dict الكامل زي create_leave(). نفس الـ endpoint (POST /hr/leaves)،
        بس بنستخرج الـ id من الـ response هنا عشان main.py يفضل شغال من
        غير ما يتلمس.

        ⚠️ FIX: كانت بتفترض إن res دايمًا dict، فلو Node رجّع list (نفس
        الحالة اللي واجهناها مع absence/salary/incentive) كان بيتنفذ
        `return str(res)` ويحوّل الـ LIST الكاملة لـ string ويرجعها كـ
        "id" — فطلعت #[{'leave_id': '...', 'agent_status': ...}] بدل
        ID حقيقي، وده كسّر كل حاجة بعدها (audit logging, get_leave
        بالـ id الغلط, إلخ)."""
        res = await self.create_leave(leave_data)
        return _extract_created_id(res, "leave")

    async def get_leaves(self, status: Optional[str] = None, limit: int = 50) -> list:
        return await self._client.get_leaves(status=status, limit=limit)

    async def get_pending_leaves(self) -> list:
        return await self._client.get_pending_leaves()

    async def get_leave(self, leave_id: str) -> dict:
        return _normalize_single_record(await self._client.get_leave(leave_id))

    async def get_leave_status(self, leave_id: str) -> Optional[str]:
        """Alias — main.py's poll_leave_decision() بيستخدمها عشان يجيب
        الـ status بس من غير ما يجيب الـ leave كله. مفيش endpoint مخصص
        لده في Node، فبنعمل get_leave() عادي ونطلع منها status بس.
        ⚠️ ده بيبقى extra round-trip مقارنة بالـ Motor الأصلي (اللي كان
        بيعمل projection على status بس) — مقبول للحجم الحالي، لو الحمل
        زاد فكر في endpoint مخصص GET /hr/leaves/:id?fields=status."""
        try:
            leave = await self.get_leave(leave_id)
            return (leave or {}).get("status")
        except Exception as e:
            logger.warning("⚠️ get_leave_status failed for #%s: %s", leave_id, e)
            return None

    async def get_leave_decision(self, leave_id: str) -> dict:
        """GET /hr/leaves/:id/decision — الـ AI decision/explainability
        record الخاص بطلب إجازة معيّن (منفصل عن get_leave اللي بيرجّع
        بيانات الطلب نفسه)."""
        return await self._client.get_leave_decision(leave_id)

    async def get_employee_leaves(self, employee_id: str, limit: int = 50) -> list:
        """GET /hr/leaves/employee/:employee_id"""
        data = await self._client._request(
            "GET", f"/hr/leaves/employee/{employee_id}",
            params={"limit": limit}, use_cache=True,
        )
        from core.node_api_client import _unwrap_list
        return _unwrap_list(data, "leaves")

    async def update_leave_status(self, leave_id: str, status: str, **kwargs) -> bool:
        try:
            payload = {"status": status, **kwargs}
            await self._client.update_resource(f"/hr/leaves/{leave_id}/status", payload)
            return True
        except Exception as e:
            logger.warning("⚠️ update_leave_status failed: %s", e)
            return False

    async def delete_leave(self, leave_id: str) -> bool:
        """DELETE /hr/leaves/:id"""
        try:
            await self._client.delete_resource(f"/hr/leaves/{leave_id}")
            return True
        except Exception as e:
            logger.warning("⚠️ delete_leave failed: %s", e)
            return False

    # ── Salary Reviews ───────────────────────────────────────────────────

    async def get_salary_reviews(self, status: Optional[str] = None, limit: int = 50) -> list:
        return await self._client.get_salary_reviews(status=status, limit=limit)

    async def get_pending_salary_reviews(self) -> list:
        return await self._client.get_pending_salary_reviews()

    async def get_salary_review(self, review_id: str) -> dict:
        return _normalize_single_record(await self._client.get_salary_review(review_id))

    async def get_employee_salary_reviews(self, employee_id: str, limit: int = 100) -> list:
        """⚠️ مؤقت — مفيش GET /hr/salary-reviews/employee/:id في hr.routes.js
        (بعكس /hr/leaves/employee/:id و /hr/absence-events/employee/:id
        اللي فعلاً موجودين). بنجيب GET /hr/salary-reviews عادي (بيرجّع كل
        الـ reviews، مش بس بتاعة الموظف ده) وبنفلتر employee_id محليًا في
        بايثون. أبطأ وأتقل من endpoint مخصص، وهيجيب بس أول `limit` review
        بشكل عام قبل الفلترة — يعني ممكن يفوت reviews قديمة لو العدد الكلي
        كبير. لو الحجم زاد، لازم يتعمل route مخصص في hr.routes.js زي
        الموجود للـ leaves/absences."""
        try:
            all_reviews = await self._client.get_salary_reviews(limit=max(limit, 200))
            return [
                r for r in all_reviews
                if str(r.get("employee_id", "")) == str(employee_id)
            ][:limit]
        except Exception as e:
            logger.warning("⚠️ get_employee_salary_reviews failed for employee %s: %s", employee_id, e)
            return []

    async def update_salary_review_status(self, review_id: str, status: str, **kwargs) -> bool:
        try:
            payload = {"status": status, **kwargs}
            await self._client.update_resource(f"/hr/salary-reviews/{review_id}/status", payload)
            return True
        except Exception as e:
            logger.warning("⚠️ update_salary_review_status failed: %s", e)
            return False

    async def delete_salary_review(self, review_id: str) -> bool:
        """DELETE /hr/salary-reviews/:id"""
        try:
            await self._client.delete_resource(f"/hr/salary-reviews/{review_id}")
            return True
        except Exception as e:
            logger.warning("⚠️ delete_salary_review failed: %s", e)
            return False

    # ── Absence Events ───────────────────────────────────────────────────

    async def get_absence_events(self, status: Optional[str] = None, limit: int = 50) -> list:
        return await self._client.get_absence_events(status=status, limit=limit)

    async def get_pending_absence_events(self) -> list:
        return await self._client.get_pending_absence_events()

    async def get_absence_event(self, absence_id: str) -> dict:
        return _normalize_single_record(await self._client.get_absence_event(absence_id))
    async def get_employee_absences(self, employee_id: str, limit: int = 50) -> dict:
        """GET /hr/absence-events/employee/:employee_id — الـ controller بيرجّع
        { absences: [...], unexcused_count_90d: N } (object مش list صريح)."""
        return await self._client.get_employee_absences(employee_id, limit=limit)

    async def update_absence_event_status(self, absence_id: str, status: str, **kwargs) -> bool:
        try:
            payload = {"status": status, **kwargs}
            await self._client.update_resource(f"/hr/absence-events/{absence_id}/status", payload)
            return True
        except Exception as e:
            logger.warning("⚠️ update_absence_event_status failed: %s", e)
            return False

    async def delete_absence_event(self, absence_id: str) -> bool:
        """DELETE /hr/absence-events/:id"""
        try:
            await self._client.delete_resource(f"/hr/absence-events/{absence_id}")
            return True
        except Exception as e:
            logger.warning("⚠️ delete_absence_event failed: %s", e)
            return False

    # ── Incentive Requests ───────────────────────────────────────────────

    async def get_incentive_requests(self, status: Optional[str] = None, limit: int = 50) -> list:
        return await self._client.get_incentive_requests(status=status, limit=limit)

    async def get_pending_incentive_requests(self) -> list:
        return await self._client.get_pending_incentive_requests()

    async def get_incentive_request(self, incentive_id: str) -> dict:
        return _normalize_single_record(await self._client.get_incentive_request(incentive_id))

    async def get_employee_incentives(self, employee_id: str, limit: int = 100) -> list:
        """⚠️ مؤقت — نفس وضع get_employee_salary_reviews: مفيش
        GET /hr/incentive-requests/employee/:id في hr.routes.js. بنجيب
        GET /hr/incentive-requests عادي ونفلتر employee_id محليًا.
        نفس التحذير: أبطأ من endpoint مخصص ومحدود بـ `limit` قبل الفلترة."""
        try:
            all_incentives = await self._client.get_incentive_requests(limit=max(limit, 200))
            return [
                i for i in all_incentives
                if str(i.get("employee_id", "")) == str(employee_id)
            ][:limit]
        except Exception as e:
            logger.warning("⚠️ get_employee_incentives failed for employee %s: %s", employee_id, e)
            return []

    async def update_incentive_status(self, incentive_id: str, status: str, **kwargs) -> bool:
        try:
            payload = {"status": status, **kwargs}
            await self._client.update_resource(f"/hr/incentive-requests/{incentive_id}/status", payload)
            return True
        except Exception as e:
            logger.warning("⚠️ update_incentive_status failed: %s", e)
            return False

    async def delete_incentive_request(self, incentive_id: str) -> bool:
        """DELETE /hr/incentive-requests/:id"""
        try:
            await self._client.delete_resource(f"/hr/incentive-requests/{incentive_id}")
            return True
        except Exception as e:
            logger.warning("⚠️ delete_incentive_request failed: %s", e)
            return False

    # ── Audit ────────────────────────────────────────────────────────────

    async def write_hr_domain_audit(self, **kwargs) -> dict:
        """Route to /hr/audit endpoint. Alias kept for backward compat —
        prefer write_hr_audit() in new code, same underlying call."""
        if "decision_source" in kwargs:
            kwargs["decision_source"] = _normalize_decision_source(kwargs["decision_source"])
        return await self._client.write_hr_audit(**kwargs)

    async def write_hr_audit(self, **kwargs) -> dict:
        """POST /hr/audit"""
        if "decision_source" in kwargs:
            kwargs["decision_source"] = _normalize_decision_source(kwargs["decision_source"])
        return await self._client.write_hr_audit(**kwargs)
    async def get_hr_audit(self, entity_id: str, domain: str) -> list:
        return await self._client.get_hr_audit(entity_id, domain)

    async def write_balance_audit(self, **kwargs) -> dict:
        return await self._client.write_balance_audit(**kwargs)

    async def write_balance_audit_log(self, employee_id=None, old_balance=None,
                                       new_balance=None, change_reason=None,
                                       leave_id=None, performed_by=None, **kwargs) -> dict:
        """Alias — trigger.py بينادي write_balance_audit_log (اسم قديم من الـ Motor HRDB)."""
        payload = {
            "employee_id":   employee_id,
            "old_balance":   old_balance,
            "new_balance":   new_balance,
            "change_reason": change_reason,
            "leave_id":      leave_id,
            "performed_by":  performed_by,
            **kwargs,
        }
        return await self.write_balance_audit(**payload)

    async def get_balance_audit_history(self, employee_id: str) -> list:
        return await self._client.get_balance_audit_history(employee_id)

    async def get_balance_history(self, employee_id: str, limit: int = 20) -> list:
        """Alias — main.py's /employees/{id}/balance-history و
        get_leave_decision_audit() بينادوا get_balance_history() (اسم
        قديم من الـ Motor HRDB). GET /hr/balance-audit/:employee_id مفيهوش
        `limit` param فعلي في hr.routes.js، فبنطبّق الـ limit هنا في بايثون
        بعد الجلب."""
        history = await self.get_balance_audit_history(employee_id)
        if isinstance(history, list) and limit:
            return history[:limit]
        return history or []

    # ── Dashboard ────────────────────────────────────────────────────────

    async def get_hr_dashboard_stats(self) -> dict:
        return await self._client.get_hr_dashboard()

    async def get_dashboard_kpis(self) -> dict:
        return await self.get_hr_dashboard_stats()

    async def save_dashboard_kpis(self, kpis: dict) -> bool:
        """مفيش endpoint مخصص لحفظ KPIs في Node دلوقتي، فبنرجّع True عشان
        الـ caller (job_calculate_dashboard_kpis) مايعتبرهاش فشل ويكتب error زيادة.
        ⚠️ مؤقت: الـ KPIs بتتحسب لكن مش بتتخزن — /hr/dashboard بيرجّع الداتا الحية
        من get_hr_dashboard_stats() لحد ما تتعمل endpoint تخزين حقيقية."""
        logger.debug("save_dashboard_kpis: no-op (Node endpoint not available yet)")
        return True

    async def get_employee_unexcused_count_90d(self, employee_id: str) -> int:
        """⚠️ مؤقت: مفيش endpoint مخصص للعدد ده لوحده. لو محتاجه فعلي دلوقتي
        استخدم get_employee_absences(employee_id) اللي بيرجّع
        unexcused_count_90d جوه الـ response بتاعه، بدل ما تعتمد على القيمة
        الثابتة صفر هنا."""
        try:
            data = await self.get_employee_absences(employee_id, limit=1)
            if isinstance(data, dict):
                return int(data.get("unexcused_count_90d", 0) or 0)
        except Exception as e:
            logger.debug("get_employee_unexcused_count_90d fallback failed: %s", e)
        return 0

    async def get_hr_domain_audit(self, domain: str, entity_id: str) -> list:
        return await self.get_hr_audit(entity_id, domain)

    async def create_salary_review(self, data: dict) -> str:
        res = await self._client.create_resource("/hr/salary-reviews", data)
        return _extract_created_id(res, "review")

    async def create_incentive_request(self, data: dict) -> str:
        res = await self._client.create_resource("/hr/incentive-requests", data)
        return _extract_created_id(res, "incentive")

    async def create_absence_event(self, data: dict) -> str:
        res = await self._client.create_resource("/hr/absence-events", data)
        return _extract_created_id(res, "absence")

    # ── Utils ────────────────────────────────────────────────────────────
    
    def _serialize(self, doc: dict) -> dict:
        from utils.serialize_utils import serialize_doc
        return serialize_doc(doc)



# ─────────────────────────────────────────────────────────────────────────────
# Singleton accessor — same calling convention as the old get_hr_db()
# ─────────────────────────────────────────────────────────────────────────────

_proxy: Optional[NodeHRProxy] = None


def get_hr_db() -> NodeHRProxy:
    """Drop-in replacement for core.mongo_connect.get_hr_db()."""
    global _proxy
    if _proxy is None:
        _proxy = NodeHRProxy()
        logger.info("✅ NodeHRProxy initialized (replaces HRDB/Motor)")
    return _proxy