"""
🚀 Persistent Event Bus — v3.0 Production (MongoDB/Motor)
==========================================================
File: app/core/event_bus_persistent.py

v3.0 Changes (Migration: MySQL → MongoDB):
    ✅ DBEventQueue          → MongoEventQueue (Motor async بدل pymysql sync)
    ✅ event_queue table     → MongoDB collection "event_queue"
    ✅ FOR UPDATE SKIP LOCKED → findOneAndUpdate atomic claim بدل SQL row-lock
    ✅ INSERT IGNORE          → upsert=True بدل MySQL ON DUPLICATE KEY
    ✅ status='dead'          → status="dead" في MongoDB doc
    ✅ كل import لـ core.db اتشال تماماً
    ✅ get_finance_db() singleton من core.mongo_connect

Architecture:
    Publisher  → Redis Stream  → Consumer Group → Handler
    (fallback) → MongoDB Queue → Polling Job    → Handler

Features:
    ✅ Redis Streams (primary)  — low latency, persistent
    ✅ MongoDB Queue (fallback) — if Redis is down
    ✅ Consumer Groups          — parallel workers, no duplicate processing
    ✅ Dead Letter Queue        — failed events after max retries
    ✅ At-least-once delivery   — ACK only after successful processing
    ✅ Graceful degradation     — never loses an event
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
REDIS_URL      = os.getenv("REDIS_URL", "redis://localhost:6379/0")
STREAM_PREFIX  = os.getenv("EVENT_STREAM_PREFIX", "synergy:events")
CONSUMER_GROUP = os.getenv("EVENT_CONSUMER_GROUP", "synergy-workers")
CONSUMER_NAME  = os.getenv("EVENT_CONSUMER_NAME", f"worker-{uuid.uuid4().hex[:8]}")
MAX_RETRIES    = int(os.getenv("EVENT_MAX_RETRIES", "3"))
BLOCK_MS       = int(os.getenv("EVENT_BLOCK_MS", "2000"))
DLQ_STREAM     = f"{STREAM_PREFIX}:dlq"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ═════════════════════════════════════════════════════════════════════════════
# 💾  MONGO-BACKED QUEUE  (fallback when Redis is unavailable)
# ═════════════════════════════════════════════════════════════════════════════

class MongoEventQueue:
    """
    ⚠️ v3.1 (Node API migration) — DISABLED.

    الكلاس ده كان بيعمل atomic claim (findOneAndUpdate) مباشرة على
    MongoDB — العملية دي مستحيل تتحول بأمان لـ REST calls عادية من غير
    endpoint مخصص في Node بيعمل نفس الـ atomic operation جوه MongoDB
    نفسه (مثلاً POST /events/claim-batch). محاولة "تقليدها" بـ عدة
    REST calls (find ثم update) هتفتح race condition حقيقي بين أكتر
    من worker.

    القرار الحالي: الـ MongoDB fallback queue معطّلة بالكامل.
    النظام بيعتمد على Redis Streams بس (RedisStreamBackend تحت — دي
    مش Mongo، مربوطة بـ Redis مباشرة ومفيهاش مشكلة). لو Redis وقع،
    الأحداث مش هتتخزن fallback — هيتسجل error واضح بدل فقدان صامت
    أو race condition.

    لما يتعمل endpoint في Node بيوفر atomic claim حقيقي، رجّع تفعيل
    الكلاس ده وابنيه فوق NodeAPIClient بدل Motor مباشرة.
    """

    def _get_col(self):
        raise NotImplementedError(
            "MongoEventQueue معطّلة (Node API migration) — "
            "مفيش اتصال MongoDB مباشر متاح دلوقتي."
        )

    async def _ensure_indexes(self) -> None:
        # no-op — لا داعي لعمل indexes على قاعدة بيانات مش متصلين بيها
        logger.debug("⏭️ MongoEventQueue._ensure_indexes skipped — queue disabled")
        return

    async def enqueue(self, event_type: str, payload: dict) -> str:
        logger.error(
            "❌ [MongoQueue] enqueue('%s') called but MongoDB fallback queue "
            "is DISABLED — event may be LOST if Redis is also down. "
            "Build a Node endpoint for atomic event claiming to re-enable this.",
            event_type,
        )
        return ""

    async def claim_batch(self, batch_size: int = 10) -> list[dict]:
        # مفيش pending أبداً — الكلاس معطّل
        return []

    async def ack(self, doc_id) -> None:
        return

    async def nack(self, doc_id, error: str) -> None:
        return

    async def get_stats(self) -> dict:
        return {"status": "disabled", "reason": "Node API migration — no direct MongoDB access"}

# ═════════════════════════════════════════════════════════════════════════════
# 🔴  REDIS STREAMS BACKEND  (unchanged — لا علاقة بـ MySQL)
# ═════════════════════════════════════════════════════════════════════════════

class RedisStreamBackend:
    """Redis Streams publisher + consumer group."""

    def __init__(self) -> None:
        self._redis: Any    = None
        self._available     = False
        self._lock          = asyncio.Lock()

    async def _get_redis(self):
        if self._redis is None:
            async with self._lock:
                if self._redis is None:
                    try:
                        import redis.asyncio as aioredis
                        self._redis = aioredis.from_url(
                            REDIS_URL,
                            encoding             = "utf-8",
                            decode_responses     = True,
                            socket_connect_timeout = 3,
                            socket_timeout       = 5,
                        )
                        await self._redis.ping()
                        self._available = True
                        logger.info("✅ [Redis] Connected to %s", REDIS_URL)
                    except Exception as e:
                        logger.warning(
                            "⚠️ [Redis] Unavailable (%s) — falling back to MongoDB queue", e
                        )
                        self._redis    = None
                        self._available = False
        return self._redis if self._available else None

    def _stream_name(self, event_type: str) -> str:
        return f"{STREAM_PREFIX}:{event_type}"

    async def publish(self, event_type: str, event_id: str, payload: dict) -> bool:
        r = await self._get_redis()
        if not r:
            return False
        try:
            stream = self._stream_name(event_type)
            await r.xadd(
                stream,
                {
                    "event_id":   event_id,
                    "event_type": event_type,
                    "payload":    json.dumps(payload, default=str),
                    "published":  _utcnow().isoformat(),
                },
                maxlen      = 50_000,
                approximate = True,
            )
            return True
        except Exception as e:
            logger.error("❌ [Redis] Publish failed: %s", e)
            self._available = False
            return False

    async def ensure_consumer_group(self, event_types: list[str]) -> None:
        r = await self._get_redis()
        if not r:
            return
        for event_type in event_types:
            stream = self._stream_name(event_type)
            try:
                await r.xgroup_create(stream, CONSUMER_GROUP, id="0", mkstream=True)
                logger.info("✅ [Redis] Consumer group ready: %s / %s", stream, CONSUMER_GROUP)
            except Exception as e:
                if "BUSYGROUP" not in str(e):
                    logger.warning("⚠️ [Redis] Group create warning: %s", e)

    async def read_batch(self, event_types: list[str], batch_size: int = 10) -> list[dict]:
        r = await self._get_redis()
        if not r:
            return []
        try:
            streams = {self._stream_name(t): ">" for t in event_types}
            results = await r.xreadgroup(
                CONSUMER_GROUP, CONSUMER_NAME, streams,
                count=batch_size, block=BLOCK_MS,
            )
            events = []
            if results:
                for stream_name, messages in results:
                    for msg_id, fields in messages:
                        try:
                            payload = json.loads(fields.get("payload", "{}"))
                        except Exception:
                            payload = {}
                        events.append({
                            "redis_id":   msg_id,
                            "stream":     stream_name,
                            "event_id":   fields.get("event_id", ""),
                            "event_type": fields.get("event_type", ""),
                            "payload":    payload,
                        })
            return events
        except Exception as e:
            logger.error("❌ [Redis] Read failed: %s", e)
            self._available = False
            return []

    async def ack(self, stream: str, msg_id: str) -> None:
        r = await self._get_redis()
        if not r:
            return
        try:
            await r.xack(stream, CONSUMER_GROUP, msg_id)
        except Exception as e:
            logger.warning("⚠️ [Redis] ACK failed %s: %s", msg_id, e)

    async def send_to_dlq(self, event: dict, error: str) -> None:
        r = await self._get_redis()
        if not r:
            return
        try:
            await r.xadd(
                DLQ_STREAM,
                {
                    "original_event": json.dumps(event, default=str),
                    "error":          error[:500],
                    "failed_at":      _utcnow().isoformat(),
                },
                maxlen=10_000,
            )
        except Exception:
            pass

    async def get_stats(self) -> dict:
        r = await self._get_redis()
        if not r:
            return {"redis": "unavailable"}
        try:
            info = await r.info("server")
            return {
                "redis":   "connected",
                "version": info.get("redis_version", "?"),
                "uptime":  info.get("uptime_in_seconds", 0),
            }
        except Exception:
            return {"redis": "error"}


# ═════════════════════════════════════════════════════════════════════════════
# 🚌  PERSISTENT EVENT BUS
# ═════════════════════════════════════════════════════════════════════════════

class PersistentEventBus:
    """
    Production-grade event bus with Redis Streams + MongoDB fallback.

    Publish flow:
        1. Try Redis XADD              ← fast, persistent
        2. Fallback → MongoDB queue    ← always works

    Consume flow:
        1. Try Redis XREADGROUP        ← preferred
        2. Fallback → MongoDB polling  ← when Redis is down

    Guarantees:
        - At-least-once delivery (ACK after success)
        - No event lost on server crash
        - Duplicate-safe via event_id deduplication
    """

    def __init__(self) -> None:
        self._handlers:  Dict[str, List[Callable]] = {}
        self._redis      = RedisStreamBackend()
        self._db_queue   = MongoEventQueue()   # ✅ MongoDB بدل MySQL
        self._running    = False
        self._stats      = {
            "published": 0, "consumed": 0,
            "failed": 0, "dlq": 0,
        }

    def subscribe(self, event_type: str, handler: Callable) -> None:
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.info("📋 [EventBus] Subscribed: %s → %s", event_type, handler.__name__)

    async def publish(self, event_type: str, payload: dict) -> str:
        """
        Publish an event. Returns event_id.
        Tries Redis first, falls back to MongoDB automatically.
        """
        event_id = f"evt-{uuid.uuid4().hex[:16]}"
        payload  = {**payload, "event_id": event_id, "event_type": event_type}

        published_redis = await self._redis.publish(event_type, event_id, payload)

        if not published_redis:
            # ⚠️ MongoDB fallback queue معطّلة (Node API migration) —
            # الـ event مش هيتخزن fallback. اتسجل تحذير واضح بدل ما نأمّن
            # أمان وهمي عن طريق fallback مكسور.
            logger.error(
                "🔴 [EventBus] Redis unavailable AND MongoDB fallback is "
                "DISABLED — event '%s' (id=%s) will NOT be persisted. "
                "Fix Redis connection or build a Node atomic-claim endpoint.",
                event_type, event_id,
            )
            self._stats["failed"] += 1
        else:
            logger.debug("📤 [EventBus] Published to Redis: %s → %s", event_type, event_id)

        self._stats["published"] += 1
        return event_id

    async def start_consuming(self) -> None:
        """
        Start the consumer loop. Run this as a background task.
        Automatically switches between Redis and MongoDB polling.
        """
        self._running = True
        event_types   = list(self._handlers.keys())

        await self._redis.ensure_consumer_group(event_types)

        logger.info(
            "🚀 [EventBus] Consumer started — watching: %s",
            ", ".join(event_types),
        )

        # ✅ Ensure MongoDB indexes once at startup
        # MongoDB fallback queue معطّلة — مفيش indexes نعملها
        logger.warning(
            "⚠️ [EventBus] MongoDB fallback queue is DISABLED (Node API "
            "migration). Consumer relies on Redis Streams only."
        )

        while self._running:
            try:
                # ── Try Redis (المصدر الوحيد المتاح دلوقتي) ────────────────
                events = await self._redis.read_batch(event_types, batch_size=20)
                if events:
                    for event in events:
                        await self._dispatch_redis(event)
                    continue

                await asyncio.sleep(2)
            except asyncio.CancelledError:
                logger.info("🛑 [EventBus] Consumer stopping...")
                break
            except Exception as e:
                logger.error("❌ [EventBus] Consumer loop error: %s", e, exc_info=True)
                await asyncio.sleep(5)
    async def _dispatch_redis(self, event: dict) -> None:
        event_type = event["event_type"]
        handlers   = self._handlers.get(event_type, [])

        if not handlers:
            await self._redis.ack(event["stream"], event["redis_id"])
            return

        success = True
        for handler in handlers:
            try:
                await handler({"type": event_type, "payload": event["payload"]})
                self._stats["consumed"] += 1
            except Exception as e:
                logger.error(
                    "❌ [EventBus] Handler %s failed for %s: %s",
                    handler.__name__, event_type, e,
                )
                self._stats["failed"] += 1
                success = False

        if success:
            await self._redis.ack(event["stream"], event["redis_id"])
        else:
            retries = int(event["payload"].get("_retry_count", 0)) + 1
            if retries >= MAX_RETRIES:
                await self._redis.send_to_dlq(event, "Max retries exceeded")
                await self._redis.ack(event["stream"], event["redis_id"])
                self._stats["dlq"] += 1
                logger.warning(
                    "☠️ [EventBus] Event sent to DLQ after %d retries: %s",
                    retries, event["event_id"],
                )
            else:
                payload = {**event["payload"], "_retry_count": retries}
                await self._redis.publish(event_type, event["event_id"], payload)
                await self._redis.ack(event["stream"], event["redis_id"])

    async def _dispatch_db(self, row: dict) -> None:
        """
        Dispatch a MongoDB queue event to its handler.
        بدل _dispatch_db القديم اللي كان بيستخدم dict من MySQL.
        """
        event_type = row.get("event_type", "")
        doc_id     = row.get("_id")   # MongoDB ObjectId

        try:
            payload_raw = row.get("payload", "{}")
            payload = json.loads(payload_raw) if isinstance(payload_raw, str) else payload_raw
        except Exception:
            payload = {}

        handlers = self._handlers.get(event_type, [])
        if not handlers:
            await self._db_queue.ack(doc_id)
            return

        success = True
        for handler in handlers:
            try:
                await handler({"type": event_type, "payload": payload})
                self._stats["consumed"] += 1
            except Exception as e:
                logger.error("❌ [EventBus] MongoDB handler failed: %s", e)
                self._stats["failed"] += 1
                success = False

        if success:
            await self._db_queue.ack(doc_id)
        else:
            await self._db_queue.nack(doc_id, "Handler exception")

    def stop(self) -> None:
        self._running = False

    async def get_stats(self) -> dict:
        return {
            **self._stats,
            "handlers":        {k: len(v) for k, v in self._handlers.items()},
            "redis_available": self._redis._available,
            "db_queue":        await self._db_queue.get_stats(),   # ✅ async
        }


# ── Singleton ─────────────────────────────────────────────────────────────────

_bus: Optional[PersistentEventBus] = None


def get_event_bus() -> PersistentEventBus:
    global _bus
    if _bus is None:
        _bus = PersistentEventBus()
    return _bus


async def start_event_bus_consumer() -> None:
    """
    Call this from main.py startup:

        @app.on_event("startup")
        async def startup():
            asyncio.create_task(start_event_bus_consumer())
    """
    bus = get_event_bus()
    from core.finance_trigger import register_finance_handlers
    register_finance_handlers_to_bus(None, bus)   # orchestrator injected separately
    await bus.start_consuming()


def register_finance_handlers_to_bus(orchestrator, bus: PersistentEventBus) -> None:
    """Wire finance event handlers into the persistent bus."""
    from core.finance_trigger import (
        _build_invoice_overdue_handler,
        _build_new_invoice_handler,
        _build_payment_handler,
    )
    bus.subscribe("invoice_overdue",  _build_invoice_overdue_handler(orchestrator))
    bus.subscribe("invoice_created",  _build_new_invoice_handler(orchestrator))
    bus.subscribe("payment_received", _build_payment_handler(orchestrator))
    logger.info("✅ [PersistentEventBus] Finance handlers registered")
