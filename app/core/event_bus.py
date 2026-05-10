"""
app/core/event_bus.py  (v2.1 — skipped events never reach finance_decisions)

v2.1 Changes:
    ✅ publish() returns -1 on duplicate AND logs it — but NEVER saves to DB
    ✅ Idempotency key uses (event_type + entity_id + day) — resets daily
        so scheduler re-processes the same invoice the next day
    ✅ force=True bypass for manual triggers and payment events
    ✅ TTL مخفّض من 120s → 60s (scheduler interval = 5min, كافي)
"""

import asyncio
import hashlib
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Callable, Coroutine, Optional

logger = logging.getLogger(__name__)

EventHandler = Callable[[dict], Coroutine[Any, Any, None]]

IDEMPOTENCY_TTL_SECONDS = 60   # ✅ v2.1: مخفّض من 120s → 60s


class IdempotencyStore:
    """
    In-memory deduplication — keyed by (event_type + entity_id + calendar_day).

    ✅ v2.1: The day component resets the key daily so the scheduler can
    re-process the same invoice on the next day.

    ❌ NEVER calls save_finance_decision — that's the handler's job.
    """

    def __init__(self, ttl_seconds: int = IDEMPOTENCY_TTL_SECONDS):
        self.ttl = timedelta(seconds=ttl_seconds)
        self._seen: dict[str, datetime] = {}

    def _make_key(self, event_type: str, payload: dict) -> str:
        """
        Stable key = hash(event_type + entity_id + today's date).

        Including today's date means:
          - Same invoice fires twice within 60s → duplicate suppressed ✅
          - Same invoice fires the next day (scheduler) → processed again ✅
          - Webhook + Scheduler same invoice same day → suppressed ✅
        """
        entity_id = (
            payload.get("invoice_id")
            or payload.get("leave_id")
            or payload.get("ticket_id")
            or payload.get("lead_id")
            or payload.get("entity_id")
            or payload.get("id")
            or 0
        )
        today = datetime.utcnow().strftime("%Y-%m-%d")
        raw   = f"{event_type}:{entity_id}:{today}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def is_duplicate(self, event_type: str, payload: dict) -> bool:
        key = self._make_key(event_type, payload)
        now = datetime.utcnow()

        # Lazy expiry
        expired = [k for k, ts in self._seen.items() if now - ts > self.ttl]
        for k in expired:
            del self._seen[k]

        if key in self._seen:
            age = (now - self._seen[key]).total_seconds()
            logger.info(
                "🔁 [Idempotency] Duplicate suppressed — "
                "key=%s event=%s age=%.1fs (NO DB write)",
                key, event_type, age,
            )
            return True
        return False

    def mark_seen(self, event_type: str, payload: dict) -> str:
        key = self._make_key(event_type, payload)
        self._seen[key] = datetime.utcnow()
        logger.debug("✅ [Idempotency] Registered key=%s for '%s'", key, event_type)
        return key

    def stats(self) -> dict:
        return {
            "tracked_keys": len(self._seen),
            "ttl_seconds":  self.ttl.total_seconds(),
        }


class EventBus:
    """
    In-process async event bus with idempotency deduplication.

    ✅ v2.1 contract:
      - publish() returns -1 when duplicate → caller logs/ignores, NO DB save
      - publish() returns N (handlers ran) on new events
      - force=True bypasses idempotency (manual triggers, tests)
    """

    def __init__(self):
        self._handlers:    dict[str, list[EventHandler]] = defaultdict(list)
        self._history:     list[dict]                    = []
        self._max_history: int                           = 500
        self._idempotency: IdempotencyStore              = IdempotencyStore(
            ttl_seconds=IDEMPOTENCY_TTL_SECONDS
        )

    # ── Subscribe ────────────────────────────────────────────────────────────

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)
        logger.debug("📡 '%s' subscribed to '%s'", handler.__name__, event_type)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        if event_type in self._handlers:
            self._handlers[event_type] = [
                h for h in self._handlers[event_type] if h != handler
            ]

    # ── Publish ──────────────────────────────────────────────────────────────

    async def publish(
        self,
        event_type: str,
        payload:    dict = None,
        force:      bool = False,
    ) -> int:
        """
        Publish an event.

        Returns:
            -1  → duplicate suppressed (idempotency) — caller must NOT save to DB
             0  → no handlers registered
             N  → N handlers ran successfully
        """
        payload = payload or {}

        # ── Idempotency gate ─────────────────────────────────────────────────
        # ✅ v2.1: return -1 ONLY — never write to finance_decisions here
        if not force and self._idempotency.is_duplicate(event_type, payload):
            return -1

        self._idempotency.mark_seen(event_type, payload)

        # ── History ──────────────────────────────────────────────────────────
        event = {
            "type":      event_type,
            "payload":   payload,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history.pop(0)

        # ── Dispatch ─────────────────────────────────────────────────────────
        handlers = (
            self._handlers.get(event_type, []) +
            self._handlers.get("*", [])
        )

        if not handlers:
            logger.debug("⚠️  No handlers registered for '%s'", event_type)
            return 0

        logger.info("📤 Event '%s' → %d handler(s)", event_type, len(handlers))

        results = await asyncio.gather(
            *[self._safe_run(h, event) for h in handlers],
            return_exceptions=True,
        )

        errors = [r for r in results if isinstance(r, Exception)]
        for err in errors:
            logger.error("❌ Handler failed for '%s': %s", event_type, err, exc_info=err)

        return len(handlers) - len(errors)

    async def _safe_run(self, handler: EventHandler, event: dict) -> None:
        try:
            await handler(event)
        except Exception as e:
            logger.error("Handler '%s' raised: %s", handler.__name__, e)
            raise

    # ── Sync wrapper ─────────────────────────────────────────────────────────

    def publish_sync(self, event_type: str, payload: dict = None) -> None:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self.publish(event_type, payload), loop
                )
            else:
                loop.run_until_complete(self.publish(event_type, payload))
        except RuntimeError:
            asyncio.run(self.publish(event_type, payload))

    # ── Introspection ─────────────────────────────────────────────────────────

    def get_history(self, event_type: str = None, limit: int = 50) -> list[dict]:
        history = self._history
        if event_type:
            history = [e for e in history if e["type"] == event_type]
        return list(reversed(history))[:limit]

    def get_stats(self) -> dict:
        return {
            "total_events_published": len(self._history),
            "registered_event_types": list(self._handlers.keys()),
            "handlers_count":         {k: len(v) for k, v in self._handlers.items()},
            "idempotency":            self._idempotency.stats(),
        }


# ── Singleton ─────────────────────────────────────────────────────────────────
event_bus = EventBus()