"""
📊 Audit Logger — v2.1 (MongoDB via Node API)
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

v2.1 Changes:
    🔧 FIX — _write_to_mongo()'s generic fallback branch (the one that
       POSTs to plain "/audit") used to let NodeAPIError bubble straight
       up out of a fire-and-forget asyncio.create_task() in log(), which
       showed up in logs as:
           ERROR | asyncio | Task exception was never retrieved
           core.node_api_client.NodeAPIError: [NodeAPI:/audit] 404 Not Found
       There is no generic POST /audit route in the Node.js API today
       (only /hr/audit and /finance/audit are real routes — see
       main.py's docstring). A 404 here is therefore an EXPECTED,
       recurring condition, not a crash. The fallback branch now catches
       NodeAPIError specifically:
         - status_code == 404  → log once at DEBUG and fall back to the
           in-memory store (_logs), same as the outer except already
           does for every other exception type.
         - anything else (timeout, 5xx, 401, ...) → re-raised, so alog()
           / the outer except in log()'s background task still see it
           and fall back to in-memory too — behavior for real failures
           is unchanged.
       This does not fix *why* an entry ends up in the generic fallback
       branch in the first place (i.e. being logged with a stage/domain
       combination that isn't "hr" or "finance" shaped) — it just stops
       that already-known, already-documented gap from crashing an
       untracked background task. If entries are landing here that you
       expected to go to /hr/audit or /finance/audit, check the
       stage/employee_id/domain kwargs passed into log()/alog() at the
       call site.
"""

from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from core.node_api_client import get_node_api_client, NodeAPIError

_py_logger = logging.getLogger(__name__)

# ── In-memory fallback (لو MongoDB مش متاح) ───────────────────────────────────
_logs: list[dict] = []

# One-shot warning flag so a missing generic /audit route doesn't spam
# the log every single time an entry falls into that branch.
_generic_audit_route_missing_warned = False


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
                    self._write_to_mongo_safe(entry, entity_id=entity_id,
                                              employee_id=employee_id, domain=domain)
                )
            else:
                loop.run_until_complete(
                    self._write_to_mongo_safe(entry, entity_id=entity_id,
                                              employee_id=employee_id, domain=domain)
                )
        except Exception as e:
            _py_logger.warning("⚠️ [AuditLogger] Sync log fallback: %s", e)
            _logs.append(serialised)

        self._print(entry)
        return serialised

    async def _write_to_mongo_safe(
        self,
        entry:       dict,
        entity_id:   Optional[str] = None,
        employee_id: Optional[int] = None,
        domain:      Optional[str] = None,
    ) -> None:
        """
        Wrapper around _write_to_mongo() used ONLY by the fire-and-forget
        asyncio.create_task() path in log(). Since nothing ever awaits or
        retrieves that task's result, any exception that escapes it would
        otherwise surface as an untracked "Task exception was never
        retrieved" error in the logs instead of the normal
        in-memory-fallback behavior alog()/log() give you everywhere else.
        This mirrors the except block in alog() so both entry points
        degrade the same way.
        """
        try:
            await self._write_to_mongo(entry, entity_id=entity_id,
                                       employee_id=employee_id, domain=domain)
        except Exception as e:
            _py_logger.warning(
                "⚠️ [AuditLogger] Background MongoDB write failed: %s — in-memory fallback", e
            )
            _logs.append(self._serialise(entry))

    # ── API write ─────────────────────────────────────────────────────────

    async def _write_to_mongo(
        self,
        entry:       dict,
        entity_id:   Optional[str] = None,
        employee_id: Optional[int] = None,
        domain:      Optional[str] = None,
    ) -> None:
        """Route the entry to the right Node.js API endpoint."""
        global _generic_audit_route_missing_warned
        stage = entry.get("stage", "")

        client = get_node_api_client()

        if stage in ("agent", "workflow", "orchestrator") and employee_id is not None:
            # HR audit via Node API
            await client.create_resource("/hr/audit", {
                "domain": domain or entry.get("event_type", "general"),
                "entity_id": entity_id,
                "employee_id": employee_id,
                "decision": entry.get("message", "")[:100],
                "confidence": entry.get("data", {}).get("confidence", 0.0),
                "decision_source": stage,
                "llm_used": entry.get("data", {}).get("llm_used", False),
                "execution_ms": entry.get("data", {}).get("execution_ms", 0),
                "request_id": entry.get("id", ""),
                "flags": entry.get("data", {}).get("flags", []),
                "extra_data": entry.get("data", {}),
            })

        elif stage in ("agent", "workflow", "action") and domain == "finance":
            # Finance audit via Node API
            await client.create_resource("/finance/audit", {
                "domain": entry.get("event_type", "general"),
                "entity_id": entity_id,
                "customer_id": entry.get("data", {}).get("customer_id"),
                "decision": entry.get("message", "")[:100],
                "risk_score": entry.get("data", {}).get("risk_score", 0.0),
                "confidence": entry.get("data", {}).get("confidence", 0.0),
                "decision_source": stage,
                "llm_used": entry.get("data", {}).get("llm_used", False),
                "execution_ms": entry.get("data", {}).get("execution_ms", 0),
                "request_id": entry.get("id", ""),
                "flags": entry.get("data", {}).get("flags", []),
            })

        else:
            # ─────────────────────────────────────────────────────────────
            # Generic fallback endpoint — ⚠️ there is NO generic POST
            # /audit route in the Node.js API today (only /hr/audit and
            # /finance/audit are real, domain-scoped routes — see
            # main.py's module docstring / _AUDIT_LOGS_DISABLED_DETAIL).
            # Any entry that lands here (stage not in
            # agent/workflow/orchestrator/action, or missing
            # employee_id/domain="finance") will reliably 404. That's
            # expected today, not a crash — catch it specifically and
            # fall back to the in-memory store, same as every other
            # write failure in this class already does. Anything other
            # than a 404 (timeout, 5xx, auth, etc.) is a real failure and
            # still propagates so the caller's except block handles it.
            # ─────────────────────────────────────────────────────────────
            doc = {**self._serialise(entry)}
            if entity_id:   doc["entity_id"]   = entity_id
            if employee_id: doc["employee_id"] = employee_id
            if domain:      doc["domain"]      = domain

            try:
                await client.create_resource("/audit", doc)
            except NodeAPIError as e:
                if e.status_code == 404:
                    if not _generic_audit_route_missing_warned:
                        _py_logger.warning(
                            "⚠️ [AuditLogger] Generic POST /audit route not "
                            "implemented on the Node side — entries that don't "
                            "match the HR (stage in agent/workflow/orchestrator "
                            "+ employee_id) or Finance (stage in "
                            "agent/workflow/action + domain='finance') shape "
                            "will fall back to in-memory logging. "
                            "(this warning only shows once per process)"
                        )
                        _generic_audit_route_missing_warned = True
                    _logs.append(self._serialise(entry))
                else:
                    # Real failure (timeout, 5xx, 401, circuit open, ...) —
                    # let it propagate so alog()/_write_to_mongo_safe()'s
                    # own except block logs it and falls back too.
                    raise

    # ── Read ──────────────────────────────────────────────────────────────────

    async def aget_all(self, limit: int = 500) -> list[dict]:
        """Return full audit trail from Node.js API (newest first) + in-memory fallback."""
        logs = []
        try:
            client = get_node_api_client()
            # Try to get generic logs from API
            api_logs = await client._request("GET", f"/audit?limit={limit}")
            if isinstance(api_logs, list):
                for d in api_logs:
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