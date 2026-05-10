"""
📊 Audit Logger
يسجل كل خطوة في الـ pipeline.

كل قرار → متسجل بـ:
    - timestamp
    - stage (orchestrator / workflow / agent / action)
    - event_type
    - message
    - data

ده اللي يخلي السيستم trustworthy ويقدر يتراجع فيه.
"""

from datetime import datetime
from typing import Optional

# ── In-memory log store (يتبدل بـ DB أو ELK Stack لاحقًا) ────────────────────
_logs: list[dict] = []


class AuditLogger:
    """
    Append-only audit log.
    
    Usage:
        logger = AuditLogger()
        logger.log(event_type="leave_request", stage="agent", message="Decision made")
    """

    def log(
        self,
        event_type: str,
        stage: str,
        message: str,
        data: Optional[dict] = None,
        level: str = "INFO",
    ) -> dict:
        """
        Append a log entry.

        Args:
            event_type: "leave_request" | "invoice_overdue" | ...
            stage:      "orchestrator" | "workflow" | "agent" | "action"
            message:    human-readable description
            data:       optional extra context
            level:      INFO | WARNING | ERROR

        Returns:
            The log entry dict
        """
        import uuid
        entry = {
            "id":         f"LOG-{uuid.uuid4().hex[:8].upper()}",
            "timestamp":  datetime.utcnow().isoformat() + "Z",
            "level":      level,
            "event_type": event_type,
            "stage":      stage,
            "message":    message,
            "data":       data or {},
        }

        try:
            # Use the MySQL write_audit_log helper from core.db (pool-based)
            from core.db import write_audit_log as _db_write_audit
            _db_write_audit(
                action=entry["message"],
                entity=entry["stage"],
                entity_id=0,
                performed_by=entry["event_type"],
                details=str(entry.get("data", {})),
                status=entry["level"],
            )
        except Exception as e:
            # Fallback to in-memory store — never crashes the pipeline
            print(f"⚠️ DB Error in logger: {e}. Falling back to memory log.")
            _logs.append(entry)

        self._print(entry)
        return entry

    def get_all(self) -> list[dict]:
        """Return full audit trail (DB + in-memory fallback)."""
        logs = []
        try:
            from core.db import get_db
            with get_db() as (_, cur):
                cur.execute(
                    "SELECT action, entity, entity_id, performed_by, details, status, created_at "
                    "FROM audit_logs ORDER BY created_at DESC LIMIT 500"
                )
                for row in cur.fetchall():
                    logs.append({
                        "timestamp":   str(row.get("created_at", "")),
                        "level":       row.get("status", "INFO"),
                        "event_type":  row.get("performed_by", ""),
                        "stage":       row.get("entity", ""),
                        "message":     row.get("action", ""),
                        "data":        {"details": row.get("details", ""), "entity_id": row.get("entity_id")},
                    })
        except Exception as e:
            print(f"⚠️ DB Read Error: {e}")

        # Combine with in-memory fallback entries
        return logs + _logs

    def get_by_event(self, event_type: str) -> list[dict]:
        """Filter logs by event type."""
        return [l for l in _logs if l["event_type"] == event_type]

    def get_by_stage(self, stage: str) -> list[dict]:
        """Filter logs by pipeline stage."""
        return [l for l in _logs if l["stage"] == stage]

    def clear(self):
        """Clear all logs (useful for testing)."""
        _logs.clear()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _print(self, entry: dict):
        """Pretty-print to console during development."""
        icon = {"INFO": "[i]", "WARNING": "[!]", "ERROR": "[x]"}.get(entry["level"], "[.]")
        ts   = entry["timestamp"][11:19]  # HH:MM:SS
        print(
            f"[{ts}] {icon} [{entry['stage'].upper():12s}] "
            f"{entry['event_type']} -> {entry['message']}"
        )
