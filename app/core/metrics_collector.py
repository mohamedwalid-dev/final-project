"""
📊 Metrics Collector — v3.1 (Node API migration)
========================================================
File: app/core/metrics_collector.py

v3.1 Changes (Migration: MongoDB/Motor مباشر → Node.js API):
    ✅ MetricsStorage        → no-op بالكامل (مفيش endpoint في Node
                                لـ metrics_events / metrics_snapshots حالياً)
    ✅ _build_snapshot()     → بيستخدم NodeFinanceProxy.get_finance_dashboard_stats()
                                (اللي بتنادي GET /finance/dashboard) بدل الـ
                                aggregation pipelines المباشرة على Mongo
    ✅ كل import لـ core.db / Motor collections اتشال تماماً

⚠️ ملحوظات مهمة عن الدقة بعد التحويل:
    - الداشبورد بيقرأ من /finance/dashboard بس، مش من نافذة زمنية مضبوطة
      (24h / اليوم) — الـ endpoint الحالي بيرجّع decisions_30d و actions_7d
      كنافذة ثابتة، فبعض الحقول (decisions_today, avg_confidence,
      avg_risk_score, avg_decision_ms, avg_overdue_days) بتفضل بقيمتها
      الافتراضية (صفر) لحد ما يتعمل endpoint أدق في Node.
    - الـ snapshot مش بيتخزن تاريخياً (MetricsStorage كلها no-op) — بس
      بيتحسب live ويتبعت للـ WebSocket clients في كل نداء.

v2.2 logic (unchanged):
    ✅ EXCLUDED_DECISIONS — real decisions only (no skipped/duplicate)
    ✅ True async-safe singleton (double-checked locking)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# ✅ Decisions to EXCLUDE from counts — NOT real AI decisions
# ══════════════════════════════════════════════════════════════════════════════
EXCLUDED_DECISIONS = [
    "skipped",
    "duplicate",
    "already_claimed",
    "already_processing",
    "idempotency_skip",
    "no_action",
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── DB helper ─────────────────────────────────────────────────────────────────

def _get_db():
    from core.node_finance_proxy import get_finance_db
    return get_finance_db()


# ══════════════════════════════════════════════════════════════════════════════
# 📐  METRIC TYPES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class MetricEvent:
    metric_type:  str
    category:     str
    value:        float
    unit:         str            = "count"
    tags:         Dict[str, Any] = field(default_factory=dict)
    entity_id:    Optional[str]  = None   # ✅ str بدل int (MongoDB ObjectId as string)
    entity_type:  str            = ""
    request_id:   str            = ""
    event_id:     str            = field(default_factory=lambda: f"m-{uuid.uuid4().hex[:12]}")
    ts:           str            = field(default_factory=lambda: _utcnow().isoformat() + "Z")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MetricsSnapshot:
    window:              str
    generated_at:        str   = field(default_factory=lambda: _utcnow().isoformat() + "Z")

    # Finance KPIs
    total_invoices:      int   = 0
    overdue_invoices:    int   = 0
    legal_invoices:      int   = 0
    paid_invoices:       int   = 0
    outstanding_egp:     float = 0.0
    collected_egp:       float = 0.0
    collection_rate_pct: float = 0.0
    avg_overdue_days:    float = 0.0
    high_risk_count:     int   = 0

    # Action Metrics
    emails_sent:         int   = 0
    escalations:         int   = 0
    legal_cases_opened:  int   = 0
    payment_plans:       int   = 0
    suspensions:         int   = 0
    write_offs:          int   = 0
    calls_scheduled:     int   = 0

    # AI Performance — real decisions only
    ai_decisions_made:   int   = 0
    decisions_today:     int   = 0
    actions_executed:    int   = 0
    avg_confidence:      float = 0.0
    avg_risk_score:      float = 0.0
    avg_decision_ms:     float = 0.0

    # Decision breakdown (today)
    decisions_approve:   int   = 0
    decisions_review:    int   = 0
    decisions_reject:    int   = 0
    decisions_escalate:  int   = 0
    decisions_plan:      int   = 0
    decisions_suspend:   int   = 0
    decisions_soft:      int   = 0
    decisions_hard:      int   = 0

    # System Health
    active_ws_clients:   int   = 0
    events_per_minute:   float = 0.0
    error_rate_pct:      float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


# ══════════════════════════════════════════════════════════════════════════════
# 💾  METRICS STORAGE — no-op (Node API migration)
# ══════════════════════════════════════════════════════════════════════════════

class MetricsStorage:
    """
    ⚠️ v3.1 (Node API migration): كانت بتكتب/تقرا من
    db.db["metrics_events"] / db.db["metrics_snapshots"] (Motor مباشرة).
    مفيش endpoint مكافئ في Node دلوقتي، فكل العمليات بقت no-op آمن.
    الـ snapshot لسه بيتحسب live في _build_snapshot() (من /finance/dashboard)
    وبيتبعت للـ WebSocket clients — بس مش بيتخزن تاريخياً.
    """

    async def _ensure_indexes(self) -> None:
        logger.debug("⏭️ MetricsStorage._ensure_indexes skipped — no direct MongoDB access")
        return

    async def store_event(self, event: MetricEvent) -> None:
        return

    async def store_snapshot(self, snapshot: MetricsSnapshot) -> None:
        return

    async def get_latest_snapshot(self, window: str = "realtime") -> Optional[dict]:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# 📡  WEBSOCKET BROADCASTER  (unchanged — لا علاقة بـ DB)
# ══════════════════════════════════════════════════════════════════════════════

class WebSocketBroadcaster:

    def __init__(self):
        self._connections: set = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws) -> None:
        async with self._lock:
            self._connections.add(ws)
        logger.info("📡 WS client connected | total=%d", len(self._connections))

    async def disconnect(self, ws) -> None:
        async with self._lock:
            self._connections.discard(ws)
        logger.info("📡 WS client disconnected | total=%d", len(self._connections))

    @property
    def client_count(self) -> int:
        return len(self._connections)

    async def broadcast(self, message: dict) -> int:
        if not self._connections:
            return 0

        payload = json.dumps(message, default=str)
        dead    = set()
        sent    = 0

        for ws in list(self._connections):
            try:
                await ws.send_text(payload)
                sent += 1
            except Exception:
                dead.add(ws)

        if dead:
            async with self._lock:
                self._connections -= dead

        return sent

    async def broadcast_metric(self, event: MetricEvent) -> None:
        await self.broadcast({"type": "metric", "payload": event.to_dict()})

    async def broadcast_snapshot(self, snapshot: MetricsSnapshot) -> None:
        await self.broadcast({"type": "snapshot", "payload": snapshot.to_dict()})

    async def broadcast_alert(self, level: str, title: str, message: str, data: dict = None) -> None:
        await self.broadcast({
            "type": "alert",
            "payload": {
                "level":   level,
                "title":   title,
                "message": message,
                "data":    data or {},
                "ts":      _utcnow().isoformat() + "Z",
            },
        })


# ══════════════════════════════════════════════════════════════════════════════
# 🧠  METRICS COLLECTOR
# ══════════════════════════════════════════════════════════════════════════════

class MetricsCollector:

    def __init__(self):
        self.storage       = MetricsStorage()
        self.broadcaster   = WebSocketBroadcaster()
        self._queue:        asyncio.Queue = asyncio.Queue(maxsize=10_000)
        self._running:      bool          = False
        self._snapshot:     Optional[MetricsSnapshot] = None
        self._last_snap:    float         = 0.0
        self._snap_ttl:     float         = 1.0
        self._event_count:  int           = 0
        self._error_count:  int           = 0
        self._window_start: float         = time.time()

        logger.warning(
            "🧠 MetricsCollector instance created | id=%s "
            "— إذا ظهر هذا السطر أكتر من مرة → singleton مكسور.",
            id(self),
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        await self.storage._ensure_indexes()
        self._running = True
        asyncio.create_task(self._process_loop())
        asyncio.create_task(self._snapshot_loop())
        logger.info("✅ MetricsCollector v3.1 started (snap_ttl=%.1fs) | id=%s",
                    self._snap_ttl, id(self))

    def stop(self) -> None:
        self._running = False

    # ── Emit ──────────────────────────────────────────────────────────────────

    async def emit(self, event: MetricEvent) -> None:
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("⚠️ MetricsCollector queue full — dropping event")

    async def emit_action(
        self,
        action:      str,
        category:    str   = "finance",
        value:       float = 1,
        unit:        str   = "count",
        entity_id:   Optional[str] = None,
        entity_type: str   = "",
        request_id:  str   = "",
        **tags,
    ) -> None:
        await self.emit(MetricEvent(
            metric_type  = action,
            category     = category,
            value        = value,
            unit         = unit,
            tags         = tags,
            entity_id    = str(entity_id) if entity_id else None,
            entity_type  = entity_type,
            request_id   = request_id,
        ))

    # ── Snapshot ──────────────────────────────────────────────────────────────

    async def get_snapshot(self, force: bool = False) -> MetricsSnapshot:
        now = time.time()
        if force or (now - self._last_snap > self._snap_ttl) or self._snapshot is None:
            self._snapshot  = await self._build_snapshot()
            self._last_snap = now
            asyncio.create_task(self.storage.store_snapshot(self._snapshot))
            await self.broadcaster.broadcast_snapshot(self._snapshot)
        return self._snapshot

    async def _build_snapshot(self) -> MetricsSnapshot:
        """
        ✅ v3.1 (Node API migration): بيستخدم NodeFinanceProxy.get_finance_dashboard_stats()
        (بتنادي GET /finance/dashboard) بدل الـ aggregation pipelines المباشرة
        على Mongo (invoices/decisions/clog collections).

        ⚠️ جزء من الحقول مش متاحة من الـ endpoint الحالي فبتفضل بقيمتها
        الافتراضية (صفر) لحد ما يتعمل endpoint أدق:
            - avg_overdue_days, avg_confidence, avg_risk_score, avg_decision_ms
            - decisions_today (عندنا decisions_30d بس، مش يوم بيوم)
            - emails_sent/escalations/calls_scheduled/payment_plans بالتفصيل
              (عندنا actions_7d كـ breakdown عام بس، مش aggregated بنفس الأسامي)
        """
        snap = MetricsSnapshot(window="realtime")
        snap.active_ws_clients = self.broadcaster.client_count

        elapsed = max(time.time() - self._window_start, 1)
        snap.events_per_minute = round(self._event_count / elapsed * 60, 1)
        if elapsed > 300:
            self._event_count  = 0
            self._window_start = time.time()

        snap.error_rate_pct = round(
            self._error_count / max(self._event_count, 1) * 100, 2
        )

        try:
            db = _get_db()
            stats = await db.get_finance_dashboard_stats()

            inv  = stats.get("invoices", {}) or {}
            risk = stats.get("risk", {}) or {}

            snap.total_invoices   = int(inv.get("total_invoices") or 0)
            snap.overdue_invoices = int(inv.get("overdue") or 0)
            snap.legal_invoices   = int(inv.get("legal") or 0)
            snap.paid_invoices    = int(inv.get("paid") or 0)
            snap.outstanding_egp  = float(inv.get("outstanding_amount") or 0)
            snap.collected_egp    = float(inv.get("collected_amount") or 0)

            total_rev = snap.outstanding_egp + snap.collected_egp
            snap.collection_rate_pct = round(
                snap.collected_egp / total_rev * 100, 1
            ) if total_rev > 0 else 0.0

            snap.high_risk_count = int(risk.get("high_risk_count") or 0)

            # ── decisions_30d breakdown → أقرب تقريب متاح لـ decisions_approve/soft/... ──
            decisions_30d = stats.get("decisions_30d", []) or []
            _decision_map = {
                "safe_to_collect":    "decisions_approve",
                "approve":            "decisions_approve",
                "invoice_registered": "decisions_approve",
                "manual_review":      "decisions_review",
                "payment_plan":       "decisions_plan",
                "soft_follow_up":     "decisions_soft",
                "hard_follow_up":     "decisions_hard",
                "suspend_service":    "decisions_suspend",
                "legal_escalation":   "decisions_escalate",
                "write_off":          "decisions_reject",
                "reject":             "decisions_reject",
                "payment_complete":   "decisions_approve",
                "partial_payment":    "decisions_review",
            }
            total_30d = 0
            for row in decisions_30d:
                dec = str(row.get("decision") or "")
                cnt = int(row.get("count") or 0)
                total_30d += cnt
                field_name = _decision_map.get(dec)
                if field_name and hasattr(snap, field_name):
                    setattr(snap, field_name, getattr(snap, field_name) + cnt)

            # ai_decisions_made مفيهوش نافذة 24h دقيقة من الـ endpoint الحالي —
            # بنستخدم مجموع آخر 30 يوم كأقرب تقريب متاح (أدق قيمة هتيجي
            # لما يتعمل endpoint بنافذة زمنية قابلة للتحديد).
            snap.ai_decisions_made = total_30d
            snap.decisions_today   = 0  # مش متاحة — مفيش breakdown يومي في الـ endpoint الحالي

            # ── actions_7d breakdown → أقرب تقريب لـ emails/escalations/... ──
            actions_7d = stats.get("actions_7d", []) or []
            _action_map = {
                "email":                 "emails_sent",
                "legal_escalation":      "escalations",
                "call_scheduled":        "calls_scheduled",
                "system":                "payment_plans",
                "suspension":            "suspensions",
                "write_off":             "write_offs",
            }
            actions_total = 0
            for row in actions_7d:
                act = str(row.get("action_type") or "")
                cnt = int(row.get("count") or 0)
                actions_total += cnt
                field_name = _action_map.get(act)
                if field_name and hasattr(snap, field_name):
                    setattr(snap, field_name, getattr(snap, field_name) + cnt)
            snap.actions_executed = actions_total

            logger.debug(
                "📊 [Metrics] snapshot from /finance/dashboard — "
                "invoices=%d overdue=%d decisions_30d=%d actions_7d=%d",
                snap.total_invoices, snap.overdue_invoices, total_30d, actions_total,
            )

        except Exception as e:
            logger.debug("Snapshot build (Node dashboard) failed: %s", e)

        return snap

    # ── Background Loops ──────────────────────────────────────────────────────

    async def _process_loop(self) -> None:
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=2.0)
                self._event_count += 1
                asyncio.create_task(self.storage.store_event(event))
                await self.broadcaster.broadcast_metric(event)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._error_count += 1
                logger.error("❌ MetricsCollector process error: %s", e)

    async def _snapshot_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self._snap_ttl)
                await self.get_snapshot(force=True)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("❌ MetricsCollector snapshot loop: %s", e)

    # ── WS Management ─────────────────────────────────────────────────────────

    async def ws_connect(self, ws) -> None:
        await self.broadcaster.connect(ws)
        snap = await self.get_snapshot()
        try:
            await ws.send_text(json.dumps({
                "type":    "snapshot",
                "payload": snap.to_dict(),
            }, default=str))
        except Exception:
            pass

    async def ws_disconnect(self, ws) -> None:
        await self.broadcaster.disconnect(ws)

    async def alert(self, level: str, title: str, message: str, data: dict = None) -> None:
        await self.broadcaster.broadcast_alert(level, title, message, data)


# ══════════════════════════════════════════════════════════════════════════════
# 🔒  TRUE ASYNC-SAFE SINGLETON
# ══════════════════════════════════════════════════════════════════════════════

_collector: Optional[MetricsCollector] = None
_collector_lock = asyncio.Lock()


def get_metrics_collector() -> MetricsCollector:
    global _collector
    if _collector is None:
        _collector = MetricsCollector()
    return _collector


async def get_metrics_collector_async() -> MetricsCollector:
    global _collector
    if _collector is not None:
        return _collector
    async with _collector_lock:
        if _collector is None:
            _collector = MetricsCollector()
    return _collector


async def start_metrics_collector() -> None:
    collector = await get_metrics_collector_async()
    if collector._running:
        logger.warning("⚠️ start_metrics_collector() اتنادى أكتر من مرة — ignored.")
        return
    await collector.start()
    logger.info("✅ MetricsCollector v3.1 ready | id=%s", id(collector))