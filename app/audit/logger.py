"""
📊 Audit Logger — v2.0 (MongoDB)
==================================
File: app/audit/logger.py

يسجل كل خطوة في الـ pipeline.

كل قرار → متسجل بـ:
    - timestamp
    - stage (orchestrator / workflow / agent / action)
    - event_type
    - message
    - data

Collections used:
    - hr_domain_audit   → HR events  (via HRDB)
    - finance_audit     → Finance events (via FinanceDB)
    - audit_generic     → fallback for other stages
"""

from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

_py_logger = logging.getLogger(__name__)

# ── In-memory fallback (لو MongoDB مش متاح) ───────────────────────────────────
_logs: list[dict] = []


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditLogger:
    """
    Append-only async audit logger backed by MongoDB.

    Sync wrapper (log) — fires async write in background via asyncio.
    Async version (alog) — awaitable, preferred inside async routes/agents.

    Usage (sync — inside sync code or agents):
        logger = AuditLogger()
        logger.log(event_type="leave_request", stage="agent", message="Decision made")

    Usage (async — inside FastAPI routes / workflows):
        logger = AuditLogger()
        await logger.alog(event_type="invoice_overdue", stage="workflow", message="Escalated")
    """

    # ── Core log builders ─────────────────────────────────────────────────────

    def _build_entry(
        self,
        event_type: str,
        stage:      str,
        message:    str,
        data:       Optional[dict] = None,
        level:      str = "INFO",
    ) -> dict:
        return {
            "id":         f"LOG-{uuid.uuid4().hex[:8].upper()}",
            "timestamp":  _utcnow(),
            "level":      level,
            "event_type": event_type,
            "stage":      stage,
            "message":    message,
            "data":       data or {},
        }

    # ── Async write ───────────────────────────────────────────────────────────

    async def alog(
        self,
        event_type: str,
        stage:      str,
        message:    str,
        data:       Optional[dict] = None,
        level:      str = "INFO",
        # optional FK helpers
        entity_id:   Optional[str] = None,
        employee_id: Optional[int] = None,
        domain:      Optional[str] = None,
    ) -> dict:
        """
        Async audit log — preferred inside FastAPI routes and async workflows.
        Writes to MongoDB; falls back to in-memory on failure.
        """
        entry = self._build_entry(event_type, stage, message, data, level)

        try:
            await self._write_to_mongo(entry, entity_id=entity_id,
                                       employee_id=employee_id, domain=domain)
        except Exception as e:
            _py_logger.warning("⚠️ [AuditLogger] MongoDB write failed: %s — in-memory fallback", e)
            _logs.append(self._serialise(entry))

        self._print(entry)
        return self._serialise(entry)

    # ── Sync write (fire-and-forget) ──────────────────────────────────────────

    def log(
        self,
        event_type: str,
        stage:      str,
        message:    str,
        data:       Optional[dict] = None,
        level:      str = "INFO",
        entity_id:   Optional[str] = None,
        employee_id: Optional[int] = None,
        domain:      Optional[str] = None,
    ) -> dict:
        """
        Sync audit log — safe to call from non-async code.
        Schedules the MongoDB write as a background asyncio task when possible;
        otherwise falls back to in-memory store.
        """
        entry = self._build_entry(event_type, stage, message, data, level)
        serialised = self._serialise(entry)

        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(
                    self._write_to_mongo(entry, entity_id=entity_id,
                                         employee_id=employee_id, domain=domain)
                )
            else:
                loop.run_until_complete(
                    self._write_to_mongo(entry, entity_id=entity_id,
                                         employee_id=employee_id, domain=domain)
                )
        except Exception as e:
            _py_logger.warning("⚠️ [AuditLogger] Sync log fallback: %s", e)
            _logs.append(serialised)

        self._print(entry)
        return serialised

    # ── MongoDB write ─────────────────────────────────────────────────────────

    async def _write_to_mongo(
        self,
        entry:       dict,
        entity_id:   Optional[str] = None,
        employee_id: Optional[int] = None,
        domain:      Optional[str] = None,
    ) -> None:
        """Route the entry to the right MongoDB collection."""
        stage = entry.get("stage", "")

        if stage in ("agent", "workflow", "orchestrator") and employee_id is not None:
            # HR audit via HRDB
            from core.mongo_connect import get_hr_db
            db = get_hr_db()
            await db.write_hr_domain_audit(
                domain=domain or entry.get("event_type", "general"),
                entity_id=entity_id,
                employee_id=employee_id,
                decision=entry.get("message", "")[:100],
                confidence=entry.get("data", {}).get("confidence", 0.0),
                decision_source=stage,
                llm_used=entry.get("data", {}).get("llm_used", False),
                execution_ms=entry.get("data", {}).get("execution_ms", 0),
                request_id=entry.get("id", ""),
                flags=entry.get("data", {}).get("flags", []),
                extra_data=entry.get("data", {}),
            )

        elif stage in ("agent", "workflow", "action") and domain == "finance":
            # Finance audit via FinanceDB
            from core.mongo_connect import get_finance_db
            db = get_finance_db()
            await db.write_finance_audit(
                domain=entry.get("event_type", "general"),
                entity_id=entity_id,
                customer_id=entry.get("data", {}).get("customer_id"),
                decision=entry.get("message", "")[:100],
                risk_score=entry.get("data", {}).get("risk_score", 0.0),
                confidence=entry.get("data", {}).get("confidence", 0.0),
                decision_source=stage,
                llm_used=entry.get("data", {}).get("llm_used", False),
                execution_ms=entry.get("data", {}).get("execution_ms", 0),
                request_id=entry.get("id", ""),
                flags=entry.get("data", {}).get("flags", []),
            )

        else:
            # Generic fallback collection
            from core.mongo_connect import get_hr_db
            db = get_hr_db()
            col = db.db["audit_generic"]
            doc = {**self._serialise(entry)}
            if entity_id:   doc["entity_id"]   = entity_id
            if employee_id: doc["employee_id"]  = employee_id
            if domain:      doc["domain"]       = domain
            await col.insert_one(doc)

    # ── Read ──────────────────────────────────────────────────────────────────

    async def aget_all(self, limit: int = 500) -> list[dict]:
        """Return full audit trail from MongoDB (newest first) + in-memory fallback."""
        logs = []
        try:
            from core.mongo_connect import get_hr_db
            db  = get_hr_db()
            col = db.db["audit_generic"]
            cursor = col.find({}).sort("timestamp", -1).limit(limit)
            docs = await cursor.to_list(None)
            for d in docs:
                d.pop("_id", None)
                if isinstance(d.get("timestamp"), datetime):
                    d["timestamp"] = d["timestamp"].isoformat()
                logs.append(d)
        except Exception as e:
            _py_logger.warning("⚠️ [AuditLogger] aget_all failed: %s", e)

        return logs + _logs

    def get_all(self) -> list[dict]:
        """Sync — returns in-memory fallback only. Use aget_all() in async context."""
        return list(_logs)

    def get_by_event(self, event_type: str) -> list[dict]:
        return [l for l in _logs if l["event_type"] == event_type]

    def get_by_stage(self, stage: str) -> list[dict]:
        return [l for l in _logs if l["stage"] == stage]

    def clear(self):
        """Clear in-memory fallback store (useful for testing)."""
        _logs.clear()

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _serialise(entry: dict) -> dict:
        """Make entry JSON-safe (convert datetime → isoformat)."""
        out = {}
        for k, v in entry.items():
            out[k] = v.isoformat() if isinstance(v, datetime) else v
        return out

    def _print(self, entry: dict) -> None:
        """Pretty-print to console during development."""
        icon = {"INFO": "[i]", "WARNING": "[!]", "ERROR": "[x]"}.get(entry["level"], "[.]")
        ts   = entry["timestamp"].strftime("%H:%M:%S") if isinstance(entry["timestamp"], datetime) \
               else str(entry["timestamp"])[11:19]
        print(
            f"[{ts}] {icon} [{entry['stage'].upper():12s}] "
            f"{entry['event_type']} -> {entry['message']}"
        )