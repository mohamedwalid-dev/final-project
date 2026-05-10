"""
⚙️ Database Action Layer
"""

from datetime import datetime
from audit.logger import AuditLogger

_leave_records: list[dict]      = []
_escalation_tickets: list[dict] = []


class DatabaseAction:

    def __init__(self):
        self.logger = AuditLogger()

    def update_leave_status(self, employee_id: str, status: str, days: int, agent_result: dict) -> dict:
        import uuid
        record = {
            "id":           f"LEAVE-{uuid.uuid4().hex[:8].upper()}",
            "employee_id":  employee_id,
            "status":       status,
            "days_granted": days,
            "confidence":   agent_result.get("confidence"),
            "reason":       agent_result.get("reason"),
            "timestamp":    datetime.utcnow().isoformat(),
        }

        try:
            from core.db import get_db          # ✅ get_db بدل get_db_connection
            with get_db() as (conn, cur):
                cur.execute(
                    """
                    INSERT INTO leave_records
                        (id, employee_id, status, days_granted, confidence, reason, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,                         # ✅ %s بدل ?  (MySQL مش SQLite)
                    (record["id"], record["employee_id"], record["status"],
                     record["days_granted"], record["confidence"],
                     record["reason"], record["timestamp"])
                )
        except Exception as e:
            print(f"⚠️ DB Error in database action: {e}. Falling back to memory cache.")
            _leave_records.append(record)

        notification = self._send_notification(
            employee_id=employee_id,
            message=self._build_message(status, days, agent_result)
        )

        self.logger.log(
            event_type="leave_request",
            stage="action",
            message=f"💾 DB updated: {status} for {employee_id}",
            data={"record_id": record["id"]}
        )

        return {
            "action":       "db_update",
            "record_id":    record["id"],
            "status":       status,
            "notification": notification,
        }

    def create_escalation_ticket(self, employee_id: str, payload: dict, agent_result: dict) -> dict:
        import uuid, json
        ticket = {
            "id":          f"ESC-{uuid.uuid4().hex[:8].upper()}",
            "employee_id": employee_id,
            "type":        "leave_approval",
            "priority":    "normal",
            "status":      "pending_review",
            "confidence":  agent_result.get("confidence"),
            "risk":        agent_result.get("risk"),
            "reason":      agent_result.get("reason"),
            "payload":     payload,
            "created_at":  datetime.utcnow().isoformat(),
        }

        try:
            from core.db import get_db          # ✅
            with get_db() as (conn, cur):
                cur.execute(
                    """
                    INSERT INTO escalation_tickets
                        (id, employee_id, type, priority, status,
                         confidence, risk, reason, payload, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,                         # ✅ %s بدل ?
                    (ticket["id"], ticket["employee_id"], ticket["type"],
                     ticket["priority"], ticket["status"], ticket["confidence"],
                     ticket["risk"], ticket["reason"],
                     json.dumps(ticket["payload"]), ticket["created_at"])
                )
        except Exception as e:
            print(f"⚠️ DB Error in database action: {e}. Falling back to memory cache.")
            _escalation_tickets.append(ticket)

        self.logger.log(
            event_type="leave_request",
            stage="action",
            message=f"⚠️ Escalation ticket created: {ticket['id']}",
            data={"employee_id": employee_id}
        )

        return {
            "action":    "escalation_created",
            "ticket_id": ticket["id"],
            "status":    "pending_human_review",
            "message":   "Request sent to HR Manager for manual review.",
        }

    def _send_notification(self, employee_id: str, message: str) -> dict:
        return {
            "channel":   "email",
            "recipient": employee_id,
            "message":   message,
            "sent":      True,
            "simulated": True,
        }

    def _build_message(self, status: str, days: int, agent_result: dict) -> str:
        if status == "approved":
            return (f"✅ Your leave request for {days} day(s) has been APPROVED. "
                    f"Confidence: {agent_result.get('confidence', 0):.0%}")
        return (f"❌ Your leave request has been REJECTED. "
                f"Reason: {agent_result.get('reason', 'Insufficient balance or low performance.')}")

    def get_leave_records(self) -> list[dict]:
        records = []
        try:
            from core.db import get_db          # ✅
            with get_db() as (_, cur):
                cur.execute("SELECT * FROM leave_records ORDER BY timestamp DESC")
                records = [dict(row) for row in cur.fetchall()]
        except Exception as e:
            print(f"⚠️ DB Read Error: {e}")
        return records + _leave_records

    def get_escalation_tickets(self) -> list[dict]:
        tickets = []
        try:
            import json
            from core.db import get_db          # ✅
            with get_db() as (_, cur):
                cur.execute("SELECT * FROM escalation_tickets ORDER BY created_at DESC")
                for row in cur.fetchall():
                    ticket = dict(row)
                    ticket["payload"] = json.loads(ticket["payload"]) if ticket["payload"] else {}
                    tickets.append(ticket)
        except Exception as e:
            print(f"⚠️ DB Read Error: {e}")
        return tickets + _escalation_tickets