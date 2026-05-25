"""
📊 Metrics Collector — v3.0 Production (MongoDB/Motor)
========================================================
File: app/core/metrics_collector.py

v3.0 Changes (Migration: MySQL → MongoDB):
    ✅ MetricsStorage        → Motor async (بدل pymysql sync)
    ✅ metrics_events table  → MongoDB collection "metrics_events"
    ✅ metrics_snapshots     → MongoDB collection "metrics_snapshots"
    ✅ _build_snapshot()     → Motor aggregation pipelines بدل raw SQL
    ✅ كل import لـ core.db اتشال تماماً
    ✅ get_finance_db() singleton من core.mongo_connect
    ✅ كل SQL queries اتحولت لـ Motor aggregation

v2.2 logic (unchanged):
    ✅ EXCLUDED_DECISIONS — real decisions only (no skipped/duplicate)
    ✅ avg_confidence / avg_risk_score / avg_decision_ms — real decisions فقط
    ✅ decisions_today = real decisions today only
    ✅ actions_executed من finance_collection_log (MongoDB clog collection)
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

from pymongo import ASCENDING, DESCENDING, IndexModel

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
    from core.mongo_connect import get_finance_db
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
# 💾  METRICS STORAGE — Motor async
# ══════════════════════════════════════════════════════════════════════════════

class MetricsStorage:

    async def _ensure_indexes(self) -> None:
        """
        بدل CREATE TABLE IF NOT EXISTS — نعمل indexes على الـ collections.
        """
        try:
            db = _get_db()

            await db.db["metrics_events"].create_indexes([
                IndexModel([("event_id", ASCENDING)], unique=True),
                IndexModel([("metric_type", ASCENDING)]),
                IndexModel([("category", ASCENDING)]),
                IndexModel([("ts", DESCENDING)]),
                IndexModel([("entity_type", ASCENDING), ("entity_id", ASCENDING)]),
                # TTL: حذف events قديمة بعد 30 يوم
                IndexModel(
                    [("ts", ASCENDING)],
                    expireAfterSeconds=30 * 86400,
                    name="ttl_events",
                ),
            ])

            await db.db["metrics_snapshots"].create_indexes([
                IndexModel([("window_type", ASCENDING)]),
                IndexModel([("created_at", DESCENDING)]),
                # TTL: حذف snapshots قديمة بعد 7 أيام
                IndexModel(
                    [("created_at", ASCENDING)],
                    expireAfterSeconds=7 * 86400,
                    name="ttl_snapshots",
                ),
            ])
        except Exception as e:
            logger.warning("⚠️ MetricsStorage index init failed: %s", e)

    async def store_event(self, event: MetricEvent) -> None:
        """
        بدل INSERT IGNORE INTO metrics_events:
        upsert=True + event_id كـ unique key.
        """
        try:
            db  = _get_db()
            doc = event.to_dict()
            # نحول ts من string لـ datetime للـ TTL index
            doc["ts_dt"] = _utcnow()

            await db.db["metrics_events"].update_one(
                {"event_id": event.event_id},
                {"$setOnInsert": doc},
                upsert=True,
            )
        except Exception as e:
            logger.debug("MetricsStorage store_event failed: %s", e)

    async def store_snapshot(self, snapshot: MetricsSnapshot) -> None:
        """
        بدل INSERT INTO metrics_snapshots:
        insert_one مع datetime field للـ TTL.
        """
        try:
            db  = _get_db()
            doc = snapshot.to_dict()
            doc["window_type"] = snapshot.window
            doc["created_at"]  = _utcnow()

            await db.db["metrics_snapshots"].insert_one(doc)
        except Exception as e:
            logger.debug("MetricsStorage store_snapshot failed: %s", e)

    async def get_latest_snapshot(self, window: str = "realtime") -> Optional[dict]:
        """
        بدل SELECT snapshot FROM metrics_snapshots ORDER BY created_at DESC LIMIT 1:
        Motor find_one مع sort.
        """
        try:
            db  = _get_db()
            doc = await db.db["metrics_snapshots"].find_one(
                {"window_type": window},
                sort=[("created_at", DESCENDING)],
            )
            if doc:
                doc.pop("_id", None)
            return doc
        except Exception as e:
            logger.debug("get_latest_snapshot failed: %s", e)
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
        logger.info("✅ MetricsCollector v3.0 started (snap_ttl=%.1fs) | id=%s",
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
        ✅ v3.0 (MongoDB):
        كل الـ SQL queries اتحولت لـ Motor aggregation pipelines.
        EXCLUDED_DECISIONS بتتفلتر في الـ $match بدل SQL NOT IN.
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

        # ── Finance Stats ─────────────────────────────────────────────────────
        try:
            db = _get_db()

            inv_pipeline = [
                {
                    "$group": {
                        "_id":               None,
                        "total_invoices":    {"$sum": 1},
                        "overdue":           {"$sum": {"$cond": [{"$eq": ["$status", "overdue"]},      1, 0]}},
                        "legal":             {"$sum": {"$cond": [{"$eq": ["$status", "legal"]},        1, 0]}},
                        "paid":              {"$sum": {"$cond": [{"$eq": ["$status", "paid"]},         1, 0]}},
                        "outstanding_amount":{"$sum": {
                            "$cond": [
                                {"$in": ["$status", ["overdue", "legal", "suspended"]]},
                                "$amount", 0,
                            ]
                        }},
                        "collected_amount":  {"$sum": {"$cond": [{"$eq": ["$status", "paid"]}, "$amount", 0]}},
                        # avg overdue days للـ overdue فقط
                        "avg_overdue_ms":    {"$avg": {
                            "$cond": [
                                {"$eq": ["$status", "overdue"]},
                                {"$subtract": [_utcnow(), "$due_date"]},
                                None,
                            ]
                        }},
                    }
                },
            ]
            inv_docs = await db.invoices.aggregate(inv_pipeline).to_list(1)
            inv      = inv_docs[0] if inv_docs else {}

            snap.total_invoices   = int(inv.get("total_invoices") or 0)
            snap.overdue_invoices = int(inv.get("overdue") or 0)
            snap.legal_invoices   = int(inv.get("legal") or 0)
            snap.paid_invoices    = int(inv.get("paid") or 0)
            snap.outstanding_egp  = float(inv.get("outstanding_amount") or 0)
            snap.collected_egp    = float(inv.get("collected_amount") or 0)
            snap.avg_overdue_days = round(
                float(inv.get("avg_overdue_ms") or 0) / 86_400_000, 1
            )

            total_rev = snap.outstanding_egp + snap.collected_egp
            snap.collection_rate_pct = round(
                snap.collected_egp / total_rev * 100, 1
            ) if total_rev > 0 else 0.0

            # High-risk count
            snap.high_risk_count = await db.invoices.count_documents({
                "ai_risk_score": {"$gte": 0.70},
                "status":        {"$nin": ["paid", "written_off"]},
            })

        except Exception as e:
            logger.debug("Snapshot finance stats failed: %s", e)

        # ── Action Stats (last 24h) ───────────────────────────────────────────
        try:
            db      = _get_db()
            since1d = _utcnow() - timedelta(days=1)

            action_pipeline = [
                {"$match": {"sent_at": {"$gte": since1d}}},
                {
                    "$group": {
                        "_id":                 None,
                        "emails_sent":         {"$sum": {"$cond": [{"$eq": ["$action_type", "email"]},                1, 0]}},
                        "legal_escalations":   {"$sum": {"$cond": [{"$eq": ["$action_type", "legal_escalation"]},    1, 0]}},
                        "calls_scheduled":     {"$sum": {"$cond": [{"$eq": ["$action_type", "call_scheduled"]},      1, 0]}},
                        "system_actions":      {"$sum": {"$cond": [{"$eq": ["$action_type", "system"]},              1, 0]}},
                        "total":               {"$sum": 1},
                    }
                },
            ]
            action_docs = await db.clog.aggregate(action_pipeline).to_list(1)
            summary     = action_docs[0] if action_docs else {}

            snap.emails_sent      = int(summary.get("emails_sent") or 0)
            snap.escalations      = int(summary.get("legal_escalations") or 0)
            snap.calls_scheduled  = int(summary.get("calls_scheduled") or 0)
            snap.payment_plans    = int(summary.get("system_actions") or 0)
            snap.actions_executed = int(summary.get("total") or 0)

        except Exception as e:
            logger.debug("Snapshot action stats failed: %s", e)

        # ── AI Decision Stats — real decisions only ───────────────────────────
        #
        # EXCLUDED: skipped / duplicate / already_claimed / …
        # INCLUDED: soft_follow_up / hard_follow_up / legal_escalation / …
        #
        try:
            db = _get_db()

            since24h   = _utcnow() - timedelta(hours=24)
            today_start = _utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

            # ── 24h real decisions ────────────────────────────────────────────
            pipeline_24h = [
                {
                    "$match": {
                        "created_at": {"$gte": since24h},
                        "decision":   {"$nin": EXCLUDED_DECISIONS},
                    }
                },
                {
                    "$group": {
                        "_id":        None,
                        "total_24h":  {"$sum": 1},
                        "avg_conf":   {"$avg": "$confidence"},
                        "avg_risk":   {"$avg": "$risk_score"},
                        "avg_ms":     {"$avg": "$execution_ms"},
                    }
                },
            ]
            docs_24h  = await db.decisions.aggregate(pipeline_24h).to_list(1)
            row_24h   = docs_24h[0] if docs_24h else {}

            # ── Today's real decisions ────────────────────────────────────────
            pipeline_today = [
                {
                    "$match": {
                        "created_at": {"$gte": today_start},
                        "decision":   {"$nin": EXCLUDED_DECISIONS},
                    }
                },
                {"$count": "today_count"},
            ]
            docs_today      = await db.decisions.aggregate(pipeline_today).to_list(1)
            decisions_today = int(docs_today[0]["today_count"]) if docs_today else 0

            # ── Decision breakdown (today) ────────────────────────────────────
            pipeline_breakdown = [
                {
                    "$match": {
                        "created_at": {"$gte": today_start},
                        "decision":   {"$nin": EXCLUDED_DECISIONS},
                    }
                },
                {
                    "$group": {
                        "_id":   "$decision",
                        "count": {"$sum": 1},
                    }
                },
            ]
            breakdown_rows = await db.decisions.aggregate(pipeline_breakdown).to_list(None)

            snap.ai_decisions_made = int(row_24h.get("total_24h") or 0)
            snap.decisions_today   = decisions_today
            snap.avg_confidence    = round(float(row_24h.get("avg_conf") or 0), 3)
            snap.avg_risk_score    = round(float(row_24h.get("avg_risk") or 0), 3)
            snap.avg_decision_ms   = round(float(row_24h.get("avg_ms") or 0), 1)

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
            for row in breakdown_rows:
                dec        = str(row.get("_id") or "")
                cnt        = int(row.get("count") or 0)
                field_name = _decision_map.get(dec)
                if field_name and hasattr(snap, field_name):
                    setattr(snap, field_name, getattr(snap, field_name) + cnt)

            logger.debug(
                "📊 AI decisions — 24h=%d today=%d "
                "(approve=%d soft=%d hard=%d plan=%d suspend=%d escalate=%d reject=%d)",
                snap.ai_decisions_made, snap.decisions_today,
                snap.decisions_approve, snap.decisions_soft, snap.decisions_hard,
                snap.decisions_plan, snap.decisions_suspend,
                snap.decisions_escalate, snap.decisions_reject,
            )

        except Exception as e:
            logger.debug("Snapshot AI stats failed: %s", e)

        return snap

    # ── Background Loops ──────────────────────────────────────────────────────

    async def _process_loop(self) -> None:
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=2.0)
                self._event_count += 1
                # ✅ store_event async مباشرة (Motor) بدل run_in_executor
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
    logger.info("✅ MetricsCollector v3.0 ready | id=%s", id(collector))