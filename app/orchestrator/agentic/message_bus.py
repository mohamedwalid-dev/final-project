"""
📡 Agent Message Bus — Multi-Agent Coordination
================================================
File: app/orchestrator/agentic/message_bus.py

A dedicated in-process bus for AGENT-TO-AGENT messages, separate from the
existing core.event_bus (which carries domain events like leave_requested).

Why a second bus?
    - core.event_bus is for external domain events with idempotency keyed
      on business entities (invoice_id, leave_id, ...).
    - This bus is for INTERNAL agent coordination: HR Agent → Finance Agent
      ("this employee had 6 unexcused absences, compute the payroll
      deduction"), request/response correlation, broadcast, and a full
      conversation trace for observability.

Features:
    - AgentMessage: typed, correlation-tracked envelope.
    - send(): fire-and-forget to a named agent's inbox handler.
    - request(): send + await a correlated reply (with timeout).
    - broadcast(): deliver to all subscribers of a topic.
    - Ring-buffer history for /agentic/messages introspection.
    - Fully async, thread-safe, never crashes the caller.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

# An inbox handler receives an AgentMessage and optionally returns a reply dict.
InboxHandler = Callable[["AgentMessage"], Awaitable[Optional[dict]]]


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _new_id(prefix: str = "msg") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


@dataclass
class AgentMessage:
    """Envelope for one agent-to-agent message."""
    sender:         str
    recipient:      str                      # agent name, or "*" for broadcast topic
    intent:         str                      # e.g. "compute_deduction", "assess_risk"
    payload:        dict          = field(default_factory=dict)
    message_id:     str           = field(default_factory=lambda: _new_id("msg"))
    correlation_id: str           = field(default_factory=lambda: _new_id("corr"))
    reply_to:       Optional[str] = None     # message_id this is replying to
    created_at:     str           = field(default_factory=_now_iso)

    def to_dict(self) -> dict:
        return asdict(self)

    def reply(self, payload: dict, sender: Optional[str] = None) -> "AgentMessage":
        """Build a correlated reply to this message."""
        return AgentMessage(
            sender         = sender or self.recipient,
            recipient      = self.sender,
            intent         = f"{self.intent}.reply",
            payload        = payload,
            correlation_id = self.correlation_id,
            reply_to       = self.message_id,
        )


class AgentMessageBus:
    """In-process async message bus for agent coordination."""

    def __init__(self, max_history: int = 500):
        self._inboxes:    dict[str, InboxHandler]       = {}
        self._topics:     dict[str, list[InboxHandler]] = defaultdict(list)
        self._history:    deque                         = deque(maxlen=max_history)
        self._pending:    dict[str, asyncio.Future]     = {}
        self._lock        = asyncio.Lock()
        self._stats       = defaultdict(int)

    # ── Registration ──────────────────────────────────────────────────────────

    def register_agent(self, name: str, handler: InboxHandler) -> None:
        """Register a named agent's inbox handler (overwrites any existing)."""
        self._inboxes[name] = handler
        logger.info("📡 [MessageBus] Agent registered: '%s'", name)

    def unregister_agent(self, name: str) -> None:
        self._inboxes.pop(name, None)

    def subscribe_topic(self, topic: str, handler: InboxHandler) -> None:
        self._topics[topic].append(handler)
        logger.debug("📡 [MessageBus] subscribed to topic '%s'", topic)

    def registered_agents(self) -> list[str]:
        return sorted(self._inboxes.keys())

    # ── Send (fire-and-forget) ────────────────────────────────────────────────

    async def send(self, message: AgentMessage) -> bool:
        """
        Deliver a message to the recipient's inbox. Returns True if a handler
        ran. Any reply produced by the handler is routed back for correlation.
        """
        self._record(message)
        self._stats["sent"] += 1

        handler = self._inboxes.get(message.recipient)
        if handler is None:
            logger.warning(
                "📡 [MessageBus] No inbox for recipient '%s' (intent=%s)",
                message.recipient, message.intent,
            )
            self._stats["undeliverable"] += 1
            return False

        try:
            reply = await handler(message)
            if reply is not None:
                reply_msg = message.reply(reply)
                self._resolve_pending(reply_msg)
                self._record(reply_msg)
            return True
        except Exception as e:
            logger.error(
                "📡 [MessageBus] handler for '%s' failed (intent=%s): %s",
                message.recipient, message.intent, e, exc_info=True,
            )
            self._stats["handler_errors"] += 1
            return False

    # ── Request / Response (correlated) ───────────────────────────────────────

    async def request(
        self,
        sender:    str,
        recipient: str,
        intent:    str,
        payload:   dict,
        timeout:   float = 30.0,
    ) -> Optional[dict]:
        """
        Send a message and await its correlated reply. Returns the reply
        payload, or None on timeout / no handler / handler error.
        """
        message = AgentMessage(
            sender=sender, recipient=recipient, intent=intent, payload=payload,
        )
        loop   = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        self._pending[message.correlation_id] = future

        self._record(message)
        self._stats["requests"] += 1

        handler = self._inboxes.get(recipient)
        if handler is None:
            self._pending.pop(message.correlation_id, None)
            logger.warning("📡 [MessageBus] request to unknown agent '%s'", recipient)
            return None

        try:
            # Run the handler; its return value is the direct reply.
            reply = await asyncio.wait_for(handler(message), timeout=timeout)
            if reply is not None:
                self._record(message.reply(reply))
                return reply
            # Handler returned None but might resolve the future out-of-band.
            if not future.done():
                reply = await asyncio.wait_for(future, timeout=timeout)
            return reply
        except asyncio.TimeoutError:
            logger.warning(
                "📡 [MessageBus] request timed out: %s → %s (intent=%s)",
                sender, recipient, intent,
            )
            self._stats["request_timeouts"] += 1
            return None
        except Exception as e:
            logger.error("📡 [MessageBus] request failed: %s", e, exc_info=True)
            return None
        finally:
            self._pending.pop(message.correlation_id, None)

    def _resolve_pending(self, reply_msg: AgentMessage) -> None:
        fut = self._pending.get(reply_msg.correlation_id)
        if fut is not None and not fut.done():
            fut.set_result(reply_msg.payload)

    # ── Broadcast ─────────────────────────────────────────────────────────────

    async def broadcast(self, message: AgentMessage) -> int:
        """Deliver to all subscribers of `message.recipient` treated as a topic."""
        self._record(message)
        handlers = list(self._topics.get(message.recipient, []))
        if not handlers:
            return 0
        self._stats["broadcasts"] += 1
        results = await asyncio.gather(
            *[self._safe(h, message) for h in handlers],
            return_exceptions=True,
        )
        return sum(1 for r in results if not isinstance(r, Exception))

    @staticmethod
    async def _safe(handler: InboxHandler, message: AgentMessage):
        try:
            return await handler(message)
        except Exception as e:
            logger.error("📡 [MessageBus] topic handler failed: %s", e)
            raise

    # ── Introspection ─────────────────────────────────────────────────────────

    def _record(self, message: AgentMessage) -> None:
        self._history.append(message.to_dict())

    def get_history(
        self,
        correlation_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        items = list(self._history)
        if correlation_id:
            items = [m for m in items if m.get("correlation_id") == correlation_id]
        return list(reversed(items))[:limit]

    def get_stats(self) -> dict:
        return {
            "registered_agents": self.registered_agents(),
            "topics":            sorted(self._topics.keys()),
            "history_size":      len(self._history),
            "counters":          dict(self._stats),
        }


# ── Singleton ───────────────────────────────────────────────────────────────
_bus: Optional[AgentMessageBus] = None


def get_agent_message_bus() -> AgentMessageBus:
    global _bus
    if _bus is None:
        _bus = AgentMessageBus()
    return _bus
