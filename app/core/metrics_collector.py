"""
📊 Metrics Collector — v2.2 Production
========================================
File: app/core/metrics_collector.py

v2.2 Changes (over v2.1):
    ✅ FIX: ai_decisions_made يعد فقط الـ decisions الحقيقية (مش skipped/duplicate)
    ✅ FIX: decisions_today نفس الـ filter — يستثني skipped و duplicate و already_claimed
    ✅ EXCLUDED_DECISIONS list واضحة وسهل تعدل عليها
    ✅ avg_confidence / avg_risk_score / avg_decision_ms تتحسب من decisions حقيقية

v2.1 Changes (unchanged):
    ✅ FIX: ai_decisions_made يعد من finance_decisions (24h window)
    ✅ FIX: _build_snapshot() يعد من invoices.ai_decision كـ fallback لو finance_decisions فاضية
    ✅ FIX: decisions_today = COUNT من finance_decisions + COUNT من invoices اللي اتحدثت النهاردة
    ✅ actions_executed يعد من finance_collection_log بدقة
    ✅ _snap_ttl مخفّض من 2s → 1s (استجابة أسرع)
    ✅ force=True يتجاهل TTL تمامًا (للـ bridge)
    ✅ broadcast_snapshot() بعد كل force rebuild
    ✅ FIX: True async-safe singleton (double-checked locking)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# ✅ v2.2: Decisions to EXCLUDE from counts — these are NOT real AI decisions
# ══════════════════════════════════════════════════════════════════════════════
EXCLUDED_DECISIONS = (
    "skipped",
    "duplicate",
    "already_claimed",
    "already_processing",
    "idempotency_skip",
    "no_action",
)

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
    entity_id:    Optional[int]  = None
    entity_type:  str            = ""
    request_id:   str            = ""
    event_id:     str            = field(default_factory=lambda: f"m-{uuid.uuid4().hex[:12]}")
    ts:           str            = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MetricsSnapshot:
    window:              str
    generated_at:        str   = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

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

    # ✅ AI Performance — real decisions only (no skipped/duplicate)
    ai_decisions_made:   int   = 0   # real AI decisions in last 24h
    decisions_today:     int   = 0   # real AI decisions today only
    actions_executed:    int   = 0   # from finance_collection_log (today)
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
# 💾  METRICS STORAGE
# ══════════════════════════════════════════════════════════════════════════════

class MetricsStorage:

    def _ensure_table(self) -> None:
        try:
            from core.db import get_db
            with get_db() as (conn, cur):
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS metrics_events (
                        id           BIGINT AUTO_INCREMENT PRIMARY KEY,
                        event_id     VARCHAR(64)  NOT NULL UNIQUE,
                        metric_type  VARCHAR(100) NOT NULL,
                        category     VARCHAR(50)  NOT NULL,
                        value        DOUBLE       NOT NULL DEFAULT 0,
                        unit         VARCHAR(20)  DEFAULT 'count',
                        tags         JSON,
                        entity_id    INT          DEFAULT NULL,
                        entity_type  VARCHAR(50)  DEFAULT '',
                        request_id   VARCHAR(100) DEFAULT '',
                        ts           DATETIME     DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_type     (metric_type),
                        INDEX idx_cat      (category),
                        INDEX idx_ts       (ts),
                        INDEX idx_entity   (entity_type, entity_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS metrics_snapshots (
                        id           BIGINT AUTO_INCREMENT PRIMARY KEY,
                        window_type  VARCHAR(20)  NOT NULL,
                        snapshot     JSON         NOT NULL,
                        created_at   DATETIME     DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_window (window_type),
                        INDEX idx_ts     (created_at)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)
                conn.commit()
        except Exception as e:
            logger.warning("⚠️ MetricsStorage table init failed: %s", e)

    def store_event(self, event: MetricEvent) -> None:
        try:
            from core.db import get_db
            with get_db() as (conn, cur):
                cur.execute("""
                    INSERT IGNORE INTO metrics_events
                        (event_id, metric_type, category, value, unit,
                         tags, entity_id, entity_type, request_id, ts)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    event.event_id, event.metric_type, event.category,
                    event.value, event.unit,
                    json.dumps(event.tags), event.entity_id,
                    event.entity_type, event.request_id, event.ts,
                ))
                conn.commit()
        except Exception as e:
            logger.debug("MetricsStorage store_event failed: %s", e)

    def store_snapshot(self, snapshot: MetricsSnapshot) -> None:
        try:
            from core.db import get_db
            with get_db() as (conn, cur):
                cur.execute("""
                    INSERT INTO metrics_snapshots (window_type, snapshot)
                    VALUES (%s, %s)
                """, (snapshot.window, json.dumps(snapshot.to_dict())))
                conn.commit()
        except Exception as e:
            logger.debug("MetricsStorage store_snapshot failed: %s", e)

    def get_latest_snapshot(self, window: str = "realtime") -> Optional[dict]:
        try:
            from core.db import get_db
            with get_db() as (_, cur):
                cur.execute("""
                    SELECT snapshot FROM metrics_snapshots
                    WHERE window_type = %s
                    ORDER BY created_at DESC LIMIT 1
                """, (window,))
                row = cur.fetchone()
                if row:
                    snap = row.get("snapshot") if isinstance(row, dict) else row[0]
                    return json.loads(snap) if isinstance(snap, str) else snap
                return None
        except Exception as e:
            logger.debug("get_latest_snapshot failed: %s", e)
            return None


# ══════════════════════════════════════════════════════════════════════════════
# 📡  WEBSOCKET BROADCASTER
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
                "ts":      datetime.utcnow().isoformat() + "Z",
            },
        })


# ══════════════════════════════════════════════════════════════════════════════
# 🧠  METRICS COLLECTOR
# ══════════════════════════════════════════════════════════════════════════════

class MetricsCollector:

    def __init__(self):
        self.storage      = MetricsStorage()
        self.broadcaster  = WebSocketBroadcaster()
        self._queue:       asyncio.Queue = asyncio.Queue(maxsize=10_000)
        self._running:     bool          = False
        self._snapshot:    Optional[MetricsSnapshot] = None
        self._last_snap:   float         = 0.0
        self._snap_ttl:    float         = 1.0
        self._event_count: int           = 0
        self._error_count: int           = 0
        self._window_start: float        = time.time()

        logger.warning(
            "🧠 MetricsCollector instance created | id=%s "
            "— إذا ظهر هذا السطر أكتر من مرة → singleton مكسور.",
            id(self),
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        self.storage._ensure_table()
        self._running = True
        asyncio.create_task(self._process_loop())
        asyncio.create_task(self._snapshot_loop())
        logger.info("✅ MetricsCollector v2.2 started (snap_ttl=%.1fs) | id=%s",
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
        category:    str    = "finance",
        value:       float  = 1,
        unit:        str    = "count",
        entity_id:   Optional[int] = None,
        entity_type: str    = "",
        request_id:  str    = "",
        **tags,
    ) -> None:
        await self.emit(MetricEvent(
            metric_type  = action,
            category     = category,
            value        = value,
            unit         = unit,
            tags         = tags,
            entity_id    = entity_id,
            entity_type  = entity_type,
            request_id   = request_id,
        ))

    # ── Snapshot ──────────────────────────────────────────────────────────────

    async def get_snapshot(self, force: bool = False) -> MetricsSnapshot:
        now = time.time()
        if force or (now - self._last_snap > self._snap_ttl) or self._snapshot is None:
            self._snapshot  = await self._build_snapshot()
            self._last_snap = now
            asyncio.create_task(self._async_store_snapshot(self._snapshot))
            await self.broadcaster.broadcast_snapshot(self._snapshot)
        return self._snapshot

    async def _async_store_snapshot(self, snapshot: MetricsSnapshot) -> None:
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.storage.store_snapshot, snapshot)
        except Exception as e:
            logger.debug("_async_store_snapshot failed: %s", e)

    async def _build_snapshot(self) -> MetricsSnapshot:
        """
        ✅ v2.2: AI decision counts exclude skipped/duplicate entries.

        The WHERE clause filters EXCLUDED_DECISIONS so only real AI decisions
        (soft_follow_up, hard_follow_up, legal_escalation, payment_plan,
        suspend_service, write_off, safe_to_collect, invoice_registered, …)
        are counted.
        """
        snap = MetricsSnapshot(window="realtime")
        snap.active_ws_clients = self.broadcaster.client_count

        elapsed = max(time.time() - self._window_start, 1)
        snap.events_per_minute = round(self._event_count / elapsed * 60, 1)
        if elapsed > 300:
            self._event_count   = 0
            self._window_start  = time.time()

        snap.error_rate_pct = round(
            self._error_count / max(self._event_count, 1) * 100, 2
        )

        # ── Finance Stats ─────────────────────────────────────────────────────
        try:
            from core.finance_db import get_finance_dashboard_stats
            stats = get_finance_dashboard_stats()
            inv   = stats.get("invoices", {})
            risk  = stats.get("risk", {})

            snap.total_invoices   = int(inv.get("total_invoices") or 0)
            snap.overdue_invoices = int(inv.get("overdue") or 0)
            snap.legal_invoices   = int(inv.get("legal") or 0)
            snap.paid_invoices    = int(inv.get("paid") or 0)
            snap.outstanding_egp  = float(inv.get("outstanding_amount") or 0)
            snap.collected_egp    = float(inv.get("collected_amount") or 0)
            snap.avg_overdue_days = float(inv.get("avg_overdue_days") or 0)
            snap.high_risk_count  = int(risk.get("high_risk_count") or 0)

            total_rev = snap.outstanding_egp + snap.collected_egp
            snap.collection_rate_pct = round(
                snap.collected_egp / total_rev * 100, 1
            ) if total_rev > 0 else 0.0

        except Exception as e:
            logger.debug("Snapshot finance stats failed: %s", e)

        # ── Action Stats ──────────────────────────────────────────────────────
        try:
            from core.finance_db import get_collection_action_stats
            action_stats = get_collection_action_stats(days=1)
            summary      = action_stats.get("summary", {})

            snap.emails_sent      = int(summary.get("emails_sent") or 0)
            snap.escalations      = int(summary.get("legal_escalations") or 0)
            snap.calls_scheduled  = int(summary.get("calls_scheduled") or 0)
            snap.payment_plans    = int(summary.get("system_actions") or 0)
            snap.actions_executed = int(summary.get("total") or 0)

        except Exception as e:
            logger.debug("Snapshot action stats failed: %s", e)

        # ── ✅ v2.2: AI Decision Stats — real decisions only ──────────────────
        #
        # EXCLUDED: skipped / duplicate / already_claimed / already_processing
        # INCLUDED: soft_follow_up / hard_follow_up / legal_escalation /
        #           payment_plan / suspend_service / write_off /
        #           safe_to_collect / invoice_registered / payment_complete / …
        #
        try:
            from core.db import get_db

            # Build NOT IN clause from EXCLUDED_DECISIONS
            placeholders = ", ".join(["%s"] * len(EXCLUDED_DECISIONS))

            with get_db() as (_, cur):

                # ── 24h real decisions ────────────────────────────────────────
                cur.execute(f"""
                    SELECT
                        COUNT(*)          AS total_24h,
                        AVG(confidence)   AS avg_conf,
                        AVG(risk_score)   AS avg_risk,
                        AVG(execution_ms) AS avg_ms
                    FROM finance_decisions
                    WHERE created_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
                      AND decision NOT IN ({placeholders})
                """, EXCLUDED_DECISIONS)
                row_24h   = cur.fetchone() or {}
                total_24h = int(row_24h.get("total_24h") or 0)

                # ── Today's real decisions ────────────────────────────────────
                cur.execute(f"""
                    SELECT COUNT(*) AS today_count
                    FROM finance_decisions
                    WHERE DATE(created_at) = CURDATE()
                      AND decision NOT IN ({placeholders})
                """, EXCLUDED_DECISIONS)
                row_today         = cur.fetchone() or {}
                decisions_today   = int(row_today.get("today_count") or 0)

                # ── Decision breakdown (today) ─────────────────────────────────
                cur.execute(f"""
                    SELECT
                        decision,
                        COUNT(*) AS cnt
                    FROM finance_decisions
                    WHERE DATE(created_at) = CURDATE()
                      AND decision NOT IN ({placeholders})
                    GROUP BY decision
                """, EXCLUDED_DECISIONS)
                breakdown_rows = cur.fetchall() or []

            snap.ai_decisions_made = total_24h
            snap.decisions_today   = decisions_today
            snap.avg_confidence    = round(float(row_24h.get("avg_conf") or 0), 3)
            snap.avg_risk_score    = round(float(row_24h.get("avg_risk") or 0), 3)
            snap.avg_decision_ms   = round(float(row_24h.get("avg_ms") or 0), 1)

            # Map breakdown rows to snapshot fields
            _decision_map = {
                "safe_to_collect":   "decisions_approve",
                "approve":           "decisions_approve",
                "invoice_registered":"decisions_approve",
                "manual_review":     "decisions_review",
                "payment_plan":      "decisions_plan",
                "soft_follow_up":    "decisions_soft",
                "hard_follow_up":    "decisions_hard",
                "suspend_service":   "decisions_suspend",
                "legal_escalation":  "decisions_escalate",
                "write_off":         "decisions_reject",
                "reject":            "decisions_reject",
                "payment_complete":  "decisions_approve",
                "partial_payment":   "decisions_review",
            }
            for row in breakdown_rows:
                dec = str(row.get("decision") or "")
                cnt = int(row.get("cnt") or 0)
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
                loop = asyncio.get_event_loop()
                loop.run_in_executor(None, self.storage.store_event, event)
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
    logger.info("✅ MetricsCollector v2.2 ready | id=%s", id(collector))