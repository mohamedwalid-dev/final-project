"""
💾 Finance Database Functions — v1.0
======================================
File: app/core/finance_db.py

All DB operations for the Finance AI Agent.
Add these functions to your existing core/db.py

Tables Used:
    - invoices                (existing — enhanced)
    - payments                (existing)
    - customers               (existing — enhanced)
    - finance_decisions       (NEW — AI decision log)
    - finance_audit           (NEW — full audit trail)
    - finance_collection_log  (NEW — all collection actions)

How to use:
    Import these functions in your core/db.py:
        from core.finance_db import (
            update_invoice_status,
            save_finance_decision,
            write_finance_audit,
            ...
        )
    OR just copy-paste into db.py
"""

import json
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
#  TABLE AUTO-CREATE
# ════════════════════════════════════════════════════════════════════════════

def _ensure_finance_tables() -> None:
    """Auto-create finance tables if they don't exist."""
    from core.db import get_db

    tables = [
        # ── Finance Decisions (AI decision log) ───────────────────────────────
        """
        CREATE TABLE IF NOT EXISTS finance_decisions (
            id              INT AUTO_INCREMENT PRIMARY KEY,
            agent_type      VARCHAR(100) NOT NULL,
            entity          VARCHAR(100) NOT NULL,
            entity_id       INT NOT NULL,
            event_id        INT DEFAULT NULL,
            decision        VARCHAR(100) NOT NULL,
            confidence      FLOAT DEFAULT 0,
            risk_score      FLOAT DEFAULT 0,
            reasoning       TEXT,
            action_plan     TEXT,
            execution_ms    INT DEFAULT 0,
            request_id      VARCHAR(100),
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_entity    (entity, entity_id),
            INDEX idx_decision  (decision),
            INDEX idx_created   (created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,

        # ── Finance Audit Trail ───────────────────────────────────────────────
        """
        CREATE TABLE IF NOT EXISTS finance_audit (
            id              INT AUTO_INCREMENT PRIMARY KEY,
            domain          VARCHAR(50)  NOT NULL,
            entity_id       INT          NOT NULL,
            customer_id     INT          DEFAULT 0,
            decision        VARCHAR(100) NOT NULL,
            risk_score      FLOAT        DEFAULT 0,
            confidence      FLOAT        DEFAULT 0,
            decision_source VARCHAR(100),
            override_rule   VARCHAR(100),
            llm_used        TINYINT(1)   DEFAULT 0,
            execution_ms    INT          DEFAULT 0,
            request_id      VARCHAR(100),
            action_plan     TEXT,
            flags_json      TEXT,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_domain    (domain),
            INDEX idx_entity    (entity_id),
            INDEX idx_customer  (customer_id),
            INDEX idx_decision  (decision),
            INDEX idx_created   (created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,

        # ── Finance Collection Log (all actions taken) ────────────────────────
        """
        CREATE TABLE IF NOT EXISTS finance_collection_log (
            id              INT AUTO_INCREMENT PRIMARY KEY,
            invoice_id      INT          DEFAULT NULL,
            customer_id     INT          DEFAULT NULL,
            action_type     VARCHAR(100) NOT NULL,
            template_name   VARCHAR(100),
            subject         VARCHAR(300),
            body            TEXT,
            priority        VARCHAR(50)  DEFAULT 'medium',
            status          VARCHAR(50)  DEFAULT 'sent',
            sent_at         DATETIME     DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_invoice   (invoice_id),
            INDEX idx_customer  (customer_id),
            INDEX idx_action    (action_type),
            INDEX idx_created   (sent_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
    ]

    try:
        with get_db() as (conn, cur):
            for sql in tables:
                try:
                    cur.execute(sql)
                except Exception as e:
                    logger.warning("⚠️ Table create warning: %s", e)
    except Exception as e:
        logger.warning("⚠️ _ensure_finance_tables failed: %s", e)


def _ensure_invoice_columns() -> None:
    """
    Enhance the existing invoices table with AI-specific columns.
    Safe to run multiple times — uses IF NOT EXISTS approach.
    """
    from core.db import get_db

    columns_to_add = [
        "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS ai_decision VARCHAR(100)",
        "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS ai_risk_score FLOAT DEFAULT 0",
        "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS ai_decision_reason TEXT",
        "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS ai_action_plan TEXT",
        "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS collection_strategy VARCHAR(50) DEFAULT 'standard'",
        "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS first_reminder_days INT DEFAULT 7",
        "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS ai_request_id VARCHAR(100)",
        "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS paid_at DATETIME DEFAULT NULL",
        "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS written_off_at DATETIME DEFAULT NULL",
        "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS overdue_days INT DEFAULT 0",
    ]

    column_checks = [
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS credit_score FLOAT DEFAULT 650",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS industry VARCHAR(100) DEFAULT 'unknown'",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS account_age_months INT DEFAULT 12",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS service_status VARCHAR(50) DEFAULT 'active'",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS suspension_reason VARCHAR(200)",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS suspended_at DATETIME",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS is_blacklisted TINYINT(1) DEFAULT 0",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS blacklisted_at DATETIME",
    ]

    try:
        with get_db() as (conn, cur):
            for sql in columns_to_add + column_checks:
                try:
                    cur.execute(sql)
                except Exception:
                    pass   # Column might already exist
    except Exception as e:
        logger.warning("⚠️ _ensure_invoice_columns failed: %s", e)


def init_finance_db() -> None:
    """Initialize all finance tables. Call this at app startup."""
    _ensure_finance_tables()
    _ensure_invoice_columns()
    logger.info("✅ Finance DB tables initialized")


# ════════════════════════════════════════════════════════════════════════════
#  INVOICES
# ════════════════════════════════════════════════════════════════════════════

def get_invoice(invoice_id: int) -> Optional[dict]:
    """Get invoice with customer info joined."""
    from core.db import get_db
    with get_db() as (_, cur):
        cur.execute(
            """
            SELECT
                i.*,
                c.name          AS customer_name,
                c.email         AS customer_email,
                c.phone         AS customer_phone,
                c.credit_score  AS credit_score,
                c.industry      AS industry,
                c.service_status AS service_status,
                c.is_blacklisted AS is_blacklisted,
                DATEDIFF(NOW(), i.due_date) AS overdue_days_calc
            FROM invoices i
            LEFT JOIN customers c ON c.id = i.customer_id
            WHERE i.id = %s LIMIT 1
            """,
            (invoice_id,),
        )
        return cur.fetchone()


def get_pending_invoices() -> list[dict]:
    """Get all invoices pending AI collection decision.

    Includes all non-terminal statuses (overdue, pending, suspended, legal)
    where the due_date has passed. Excludes paid / written_off / cancelled.
    """
    from core.db import get_db
    with get_db() as (_, cur):
        cur.execute(
            """
            SELECT
                i.*,
                c.name           AS customer_name,
                c.email          AS customer_email,
                c.credit_score   AS credit_score,
                c.industry       AS industry,
                c.service_status AS service_status,
                DATEDIFF(NOW(), i.due_date) AS overdue_days_calc
            FROM invoices i
            LEFT JOIN customers c ON c.id = i.customer_id
            WHERE i.status NOT IN ('paid', 'written_off', 'cancelled')
              AND i.due_date <= NOW()
            ORDER BY DATEDIFF(NOW(), i.due_date) DESC, i.amount DESC
            """
        )
        return cur.fetchall()


def get_overdue_invoices(min_days: int = 1, limit: int = 200) -> list[dict]:
    """Get invoices overdue by at least min_days."""
    from core.db import get_db
    with get_db() as (_, cur):
        cur.execute(
            """
            SELECT
                i.*,
                c.name           AS customer_name,
                c.email          AS customer_email,
                c.credit_score   AS credit_score,
                c.industry       AS industry,
                c.service_status AS service_status,
                DATEDIFF(NOW(), i.due_date) AS overdue_days_calc
            FROM invoices i
            LEFT JOIN customers c ON c.id = i.customer_id
            WHERE i.status NOT IN ('paid', 'written_off', 'cancelled')
              AND i.due_date < NOW()
              AND DATEDIFF(NOW(), i.due_date) >= %s
            ORDER BY DATEDIFF(NOW(), i.due_date) DESC
            LIMIT %s
            """,
            (min_days, limit),
        )
        return cur.fetchall()

def create_invoice(data: dict) -> int:
    """Create a new invoice."""
    from core.db import get_db
    with get_db() as (conn, cur):
        cur.execute(
            """
            INSERT INTO invoices
                (customer_id, amount, due_date, status, description, created_at)
            VALUES
                (%(customer_id)s, %(amount)s, %(due_date)s,
                 %(status)s, %(description)s, NOW())
            """,
            {
                "customer_id": data.get("customer_id"),
                "amount":      data.get("amount", 0),
                "due_date":    data.get("due_date"),
                "status":      data.get("status", "pending"),
                "description": data.get("description", ""),
            },
        )
        return cur.lastrowid


def update_invoice_status(
    invoice_id:      int,
    status:          str,
    ai_decision:     str   = "",
    risk_score:      float = 0.0,
    decision_reason: str   = "",
    action_plan:     str   = "",
    request_id:      str   = "",
) -> bool:
    """Update invoice status with AI decision info."""
    from core.db import get_db
    _ensure_finance_tables()
    try:
        with get_db() as (conn, cur):
            cur.execute(
                """
                UPDATE invoices
                SET status           = %s,
                    ai_decision      = %s,
                    ai_risk_score    = %s,
                    ai_decision_reason = %s,
                    ai_action_plan   = %s,
                    ai_request_id    = %s,
                    updated_at       = NOW()
                WHERE id = %s
                """,
                (
                    status, ai_decision[:100], risk_score,
                    decision_reason[:1000], action_plan[:500],
                    request_id[:100], invoice_id,
                ),
            )
            return cur.rowcount > 0
    except Exception as e:
        logger.error("update_invoice_status failed: %s", e)
        return False


def update_invoice_collection_strategy(
    invoice_id:          int,
    risk_score:          float,
    collection_strategy: str,
    first_reminder_days: int,
    request_id:          str = "",
) -> bool:
    """Set collection strategy on a new invoice."""
    from core.db import get_db
    try:
        with get_db() as (conn, cur):
            cur.execute(
                """
                UPDATE invoices
                SET ai_risk_score        = %s,
                    collection_strategy  = %s,
                    first_reminder_days  = %s,
                    ai_request_id        = %s,
                    updated_at           = NOW()
                WHERE id = %s
                """,
                (risk_score, collection_strategy[:50],
                 first_reminder_days, request_id[:100], invoice_id),
            )
            return cur.rowcount > 0
    except Exception as e:
        logger.warning("update_invoice_collection_strategy failed: %s", e)
        return False


def get_customer_invoice_summary(customer_id: int) -> dict:
    """Get aggregated invoice stats for a customer."""
    from core.db import get_db
    try:
        with get_db() as (_, cur):
            cur.execute(
                """
                SELECT
                    COUNT(*)                                           AS total,
                    SUM(CASE WHEN status='paid' THEN 1 ELSE 0 END)    AS paid,
                    SUM(CASE WHEN status='overdue' THEN 1 ELSE 0 END)  AS overdue,
                    SUM(CASE WHEN status='legal' THEN 1 ELSE 0 END)    AS legal,
                    SUM(CASE WHEN status='written_off' THEN 1 ELSE 0 END) AS written_off,
                    SUM(amount)                                        AS total_amount,
                    SUM(CASE WHEN status='paid' THEN amount ELSE 0 END) AS paid_amount,
                    SUM(CASE WHEN status IN ('overdue','legal') THEN amount ELSE 0 END) AS outstanding_amount,
                    AVG(CASE WHEN status='paid' THEN DATEDIFF(updated_at, due_date) END) AS avg_payment_delay
                FROM invoices
                WHERE customer_id = %s
                """,
                (customer_id,),
            )
            return cur.fetchone() or {}
    except Exception as e:
        logger.warning("get_customer_invoice_summary failed: %s", e)
        return {}


# ════════════════════════════════════════════════════════════════════════════
#  FINANCE DECISIONS
# ════════════════════════════════════════════════════════════════════════════

def save_finance_decision(data: dict) -> int:
    """
    Save AI finance decision to log.
 
    ✅ v2.1 FIX: created_at يتسجل دايمًا بـ NOW()
    ده بيضمن إن decisions_today query تشتغل صح.
    """
    import logging
    import json
    logger = logging.getLogger(__name__)
 
    from core.db import get_db
    _ensure_finance_tables()
    try:
        with get_db() as (conn, cur):
            cur.execute(
                """
                INSERT INTO finance_decisions
                    (agent_type, entity, entity_id, event_id,
                     decision, confidence, risk_score,
                     reasoning, action_plan, execution_ms, request_id,
                     created_at)
                VALUES
                    (%(agent_type)s, %(entity)s, %(entity_id)s, %(event_id)s,
                     %(decision)s, %(confidence)s, %(risk_score)s,
                     %(reasoning)s, %(action_plan)s, %(execution_ms)s, %(request_id)s,
                     NOW())
                """,
                {
                    "agent_type":  data.get("agent_type", "finance_agent"),
                    "entity":      data.get("entity", "invoices"),
                    "entity_id":   int(data.get("entity_id", 0)),
                    "event_id":    data.get("event_id"),
                    "decision":    data.get("decision", "")[:100],
                    "confidence":  float(data.get("confidence", 0)),
                    "risk_score":  float(data.get("risk_score", 0)),
                    "reasoning":   data.get("reasoning", "")[:1000],
                    "action_plan": data.get("action_plan", "")[:500],
                    "execution_ms": int(data.get("execution_ms", 0)),
                    "request_id":  data.get("request_id", "")[:100],
                },
            )
            inserted_id = cur.lastrowid
            # conn.commit() — يتعمل automatically في context manager
 
            logger.debug(
                "✅ save_finance_decision: id=%d decision=%s invoice=%s",
                inserted_id,
                data.get("decision"),
                data.get("entity_id"),
            )
            return inserted_id
 
    except Exception as e:
        logger.error("save_finance_decision failed: %s", e)
        return 0
 

def get_finance_decisions(entity_id: int, entity: str = "invoices") -> list[dict]:
    """Get all AI decisions for an entity."""
    from core.db import get_db
    _ensure_finance_tables()
    try:
        with get_db() as (_, cur):
            cur.execute(
                """
                SELECT * FROM finance_decisions
                WHERE entity = %s AND entity_id = %s
                ORDER BY created_at DESC
                """,
                (entity, entity_id),
            )
            return cur.fetchall()
    except Exception:
        return []


# ════════════════════════════════════════════════════════════════════════════
#  FINANCE AUDIT
# ════════════════════════════════════════════════════════════════════════════

def write_finance_audit(
    domain:          str,
    entity_id:       int,
    customer_id:     int   = 0,
    decision:        str   = "",
    risk_score:      float = 0.0,
    confidence:      float = 0.0,
    decision_source: str   = "agent",
    override_rule:   str   = "",
    llm_used:        bool  = False,
    execution_ms:    int   = 0,
    request_id:      str   = "",
    action_plan:     list  = None,
    flags:           list  = None,
) -> None:
    """Write to the finance audit trail."""
    from core.db import get_db
    _ensure_finance_tables()
    try:
        with get_db() as (conn, cur):
            cur.execute(
                """
                INSERT INTO finance_audit
                    (domain, entity_id, customer_id, decision,
                     risk_score, confidence, decision_source,
                     override_rule, llm_used, execution_ms,
                     request_id, action_plan, flags_json)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    domain[:50], entity_id, customer_id,
                    decision[:100], round(risk_score, 4),
                    round(confidence, 4), decision_source[:100],
                    (override_rule or "")[:100], int(llm_used),
                    execution_ms, (request_id or "")[:100],
                    json.dumps(action_plan or []),
                    json.dumps(flags or []),
                ),
            )
    except Exception as e:
        logger.error("write_finance_audit failed: %s", e)


def get_finance_audit(domain: str, entity_id: int) -> list[dict]:
    """Get finance audit trail for an entity."""
    from core.db import get_db
    _ensure_finance_tables()
    try:
        with get_db() as (_, cur):
            cur.execute(
                """
                SELECT * FROM finance_audit
                WHERE domain = %s AND entity_id = %s
                ORDER BY created_at DESC
                """,
                (domain, entity_id),
            )
            return cur.fetchall()
    except Exception:
        return []


# ════════════════════════════════════════════════════════════════════════════
#  DASHBOARD STATS
# ════════════════════════════════════════════════════════════════════════════

def get_finance_dashboard_stats() -> dict:
    """Get aggregated finance stats for dashboard."""
    from core.db import get_db
    try:
        with get_db() as (_, cur):
            # Invoice stats
            cur.execute(
                """
                SELECT
                    COUNT(*)                                              AS total_invoices,
                    SUM(CASE WHEN status='paid' THEN 1 ELSE 0 END)        AS paid,
                    SUM(CASE WHEN status='overdue' THEN 1 ELSE 0 END)      AS overdue,
                    SUM(CASE WHEN status='legal' THEN 1 ELSE 0 END)        AS legal,
                    SUM(CASE WHEN status='suspended' THEN 1 ELSE 0 END)    AS suspended,
                    SUM(CASE WHEN status='written_off' THEN 1 ELSE 0 END)  AS written_off,
                    SUM(CASE WHEN status='payment_plan' THEN 1 ELSE 0 END) AS payment_plan,
                    SUM(CASE WHEN status='disputed' THEN 1 ELSE 0 END)     AS disputed,
                    SUM(amount)                                            AS total_amount,
                    SUM(CASE WHEN status IN ('overdue','legal','suspended') THEN amount ELSE 0 END)
                                                                           AS outstanding_amount,
                    SUM(CASE WHEN status='paid' THEN amount ELSE 0 END)    AS collected_amount,
                    AVG(CASE WHEN status IN ('overdue','legal') THEN DATEDIFF(NOW(), due_date) END)
                                                                           AS avg_overdue_days
                FROM invoices
                """
            )
            invoice_stats = cur.fetchone() or {}

            # High risk count
            cur.execute(
                """
                SELECT COUNT(*) AS high_risk_count,
                       SUM(amount) AS high_risk_amount
                FROM invoices
                WHERE ai_risk_score >= 0.70
                  AND status NOT IN ('paid', 'written_off')
                """
            )
            risk_stats = cur.fetchone() or {}

            # Recent decisions
            cur.execute(
                """
                SELECT decision, COUNT(*) as count
                FROM finance_decisions
                WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                GROUP BY decision
                ORDER BY count DESC
                LIMIT 10
                """
            )
            decision_breakdown = cur.fetchall() or []

            # Collection log stats (last 7 days)
            cur.execute(
                """
                SELECT action_type, COUNT(*) as count
                FROM finance_collection_log
                WHERE sent_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
                GROUP BY action_type
                """
            )
            action_stats = cur.fetchall() or []

        return {
            "invoices":          invoice_stats,
            "risk":              risk_stats,
            "decisions_30d":     decision_breakdown,
            "actions_7d":        action_stats,
            "timestamp":         datetime.utcnow().isoformat() + "Z",
        }
    except Exception as e:
        logger.error("get_finance_dashboard_stats failed: %s", e)
        return {"error": str(e)}


def get_cashflow_forecast() -> dict:
    """Get cashflow projection from outstanding invoices."""
    from core.db import get_db
    try:
        with get_db() as (_, cur):
            cur.execute(
                """
                SELECT
                    SUM(CASE WHEN due_date <= DATE_ADD(NOW(), INTERVAL 7 DAY)
                             AND status='pending' THEN amount ELSE 0 END) AS due_7_days,
                    SUM(CASE WHEN due_date <= DATE_ADD(NOW(), INTERVAL 30 DAY)
                             AND status='pending' THEN amount ELSE 0 END) AS due_30_days,
                    SUM(CASE WHEN status='overdue' THEN amount ELSE 0 END) AS overdue_total,
                    SUM(CASE WHEN status='overdue' AND ai_risk_score >= 0.70
                             THEN amount ELSE 0 END)                       AS high_risk_overdue,
                    SUM(CASE WHEN status='payment_plan' THEN amount ELSE 0 END) AS payment_plan_total
                FROM invoices
                WHERE status NOT IN ('paid', 'written_off', 'cancelled')
                """
            )
            return cur.fetchone() or {}
    except Exception as e:
        logger.warning("get_cashflow_forecast failed: %s", e)
        return {}


# ════════════════════════════════════════════════════════════════════════════
#  CUSTOMER HELPERS  (used by finance_actions.py)
# ════════════════════════════════════════════════════════════════════════════

def get_customer_email(customer_id: int) -> Optional[str]:
    """Get the email address for a customer."""
    from core.db import get_db
    try:
        with get_db() as (_, cur):
            cur.execute(
                "SELECT email FROM customers WHERE id = %s LIMIT 1",
                (customer_id,),
            )
            row = cur.fetchone()
            return row["email"] if row else None
    except Exception as e:
        logger.warning("get_customer_email failed for customer %s: %s", customer_id, e)
        return None


def get_customer_info(customer_id: int) -> Optional[dict]:
    """Get full customer info."""
    from core.db import get_db
    try:
        with get_db() as (_, cur):
            cur.execute(
                "SELECT * FROM customers WHERE id = %s LIMIT 1",
                (customer_id,),
            )
            return cur.fetchone()
    except Exception as e:
        logger.warning("get_customer_info failed: %s", e)
        return None


def update_customer_status(
    customer_id:    int,
    service_status: str  = "",
    is_blacklisted: bool = None,
    extra_fields:   dict = None,
) -> bool:
    """Update customer service status and/or blacklist flag."""
    from core.db import get_db
    _ensure_invoice_columns()  # ensures customers has the needed columns

    sets  = []
    vals  = []

    if service_status:
        sets.append("service_status = %s")
        vals.append(service_status[:50])

    if is_blacklisted is not None:
        sets.append("is_blacklisted = %s")
        vals.append(int(is_blacklisted))
        if is_blacklisted:
            sets.append("blacklisted_at = NOW()")

    if extra_fields:
        for k, v in extra_fields.items():
            if v == "NOW()":
                sets.append(f"{k} = NOW()")
            else:
                sets.append(f"{k} = %s")
                vals.append(v)

    if not sets:
        return False

    vals.append(customer_id)
    sql = f"UPDATE customers SET {', '.join(sets)} WHERE id = %s"

    try:
        with get_db() as (conn, cur):
            cur.execute(sql, tuple(vals))
            return cur.rowcount > 0
    except Exception as e:
        logger.error("update_customer_status failed for customer %s: %s", customer_id, e)
        return False


# ════════════════════════════════════════════════════════════════════════════
#  COLLECTION LOG  (used by finance_actions.py)
# ════════════════════════════════════════════════════════════════════════════

def log_collection_action(
    invoice_id:    Optional[int] = None,
    customer_id:   Optional[int] = None,
    action_type:   str           = "email",
    template_name: str           = "",
    subject:       str           = "",
    body:          str           = "",
    priority:      str           = "medium",
    status:        str           = "sent",
) -> int:
    """Log a collection action to finance_collection_log."""
    from core.db import get_db
    _ensure_finance_tables()
    try:
        with get_db() as (conn, cur):
            cur.execute(
                """
                INSERT INTO finance_collection_log
                    (invoice_id, customer_id, action_type, template_name,
                     subject, body, priority, status, sent_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """,
                (
                    invoice_id, customer_id,
                    action_type[:100], template_name[:100],
                    subject[:300], (body or "")[:5000],
                    priority[:50], status[:50],
                ),
            )
            return cur.lastrowid
    except Exception as e:
        logger.error("log_collection_action failed: %s", e)
        return 0


def get_collection_log(
    invoice_id:  Optional[int] = None,
    customer_id: Optional[int] = None,
    action_type: Optional[str] = None,
    limit:       int           = 50,
) -> list[dict]:
    """Get collection action log with optional filters."""
    from core.db import get_db
    _ensure_finance_tables()

    conditions = []
    params     = []

    if invoice_id is not None:
        conditions.append("invoice_id = %s")
        params.append(invoice_id)
    if customer_id is not None:
        conditions.append("customer_id = %s")
        params.append(customer_id)
    if action_type:
        conditions.append("action_type = %s")
        params.append(action_type)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)

    try:
        with get_db() as (_, cur):
            cur.execute(
                f"""
                SELECT * FROM finance_collection_log
                {where}
                ORDER BY sent_at DESC
                LIMIT %s
                """,
                tuple(params),
            )
            return cur.fetchall()
    except Exception as e:
        logger.warning("get_collection_log failed: %s", e)
        return []


def get_collection_action_stats(days: int = 7) -> dict:
    """Get collection action statistics for the dashboard."""
    from core.db import get_db
    _ensure_finance_tables()
    try:
        with get_db() as (_, cur):
            cur.execute(
                """
                SELECT
                    action_type,
                    status,
                    priority,
                    COUNT(*) AS count
                FROM finance_collection_log
                WHERE sent_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                GROUP BY action_type, status, priority
                ORDER BY count DESC
                """,
                (days,),
            )
            rows = cur.fetchall()

            # Summary counts
            cur.execute(
                """
                SELECT
                    SUM(CASE WHEN action_type = 'email' THEN 1 ELSE 0 END) AS emails_sent,
                    SUM(CASE WHEN action_type = 'legal_escalation' THEN 1 ELSE 0 END) AS legal_escalations,
                    SUM(CASE WHEN action_type = 'internal_notification' THEN 1 ELSE 0 END) AS notifications,
                    SUM(CASE WHEN action_type = 'system' THEN 1 ELSE 0 END) AS system_actions,
                    SUM(CASE WHEN action_type = 'call_scheduled' THEN 1 ELSE 0 END) AS calls_scheduled,
                    SUM(CASE WHEN action_type = 'followup_scheduled' THEN 1 ELSE 0 END) AS followups,
                    SUM(CASE WHEN priority = 'critical' THEN 1 ELSE 0 END) AS critical_actions,
                    COUNT(*) AS total
                FROM finance_collection_log
                WHERE sent_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                """,
                (days,),
            )
            summary = cur.fetchone() or {}

        return {"breakdown": rows, "summary": summary}
    except Exception as e:
        logger.warning("get_collection_action_stats failed: %s", e)
        return {"breakdown": [], "summary": {}}


# ════════════════════════════════════════════════════════════════════════════
#  LEGAL CASES
# ════════════════════════════════════════════════════════════════════════════

def _ensure_legal_cases_table() -> None:
    """Auto-create legal_cases table."""
    from core.db import get_db
    try:
        with get_db() as (conn, cur):
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS legal_cases (
                    id              INT AUTO_INCREMENT PRIMARY KEY,
                    invoice_id      INT          NOT NULL,
                    customer_id     INT          DEFAULT NULL,
                    case_ref        VARCHAR(100) NOT NULL,
                    case_type       VARCHAR(100) DEFAULT 'debt_collection',
                    amount          DECIMAL(12,2) DEFAULT 0,
                    status          VARCHAR(50)  DEFAULT 'opened',
                    priority        VARCHAR(50)  DEFAULT 'high',
                    assigned_to     VARCHAR(200) DEFAULT 'legal_team',
                    description     TEXT,
                    timeline_json   TEXT,
                    sla_deadline    DATETIME     DEFAULT NULL,
                    resolution      TEXT,
                    resolved_at     DATETIME     DEFAULT NULL,
                    created_at      DATETIME     DEFAULT CURRENT_TIMESTAMP,
                    updated_at      DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_invoice   (invoice_id),
                    INDEX idx_customer  (customer_id),
                    INDEX idx_status    (status),
                    INDEX idx_ref       (case_ref),
                    INDEX idx_created   (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
    except Exception as e:
        logger.warning("_ensure_legal_cases_table failed: %s", e)


def create_legal_case(
    invoice_id:  int,
    customer_id: Optional[int] = None,
    amount:      float         = 0,
    case_type:   str           = "debt_collection",
    description: str           = "",
    priority:    str           = "high",
    sla_days:    int           = 7,
) -> dict:
    """Create a new legal case for an invoice."""
    from core.db import get_db
    _ensure_legal_cases_table()

    import uuid
    case_ref = f"LEG-{datetime.utcnow().strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"

    timeline = json.dumps([{
        "event": "case_opened",
        "date": datetime.utcnow().isoformat() + "Z",
        "note": f"Legal case opened for invoice #{invoice_id}",
    }])

    try:
        with get_db() as (conn, cur):
            cur.execute(
                """
                INSERT INTO legal_cases
                    (invoice_id, customer_id, case_ref, case_type,
                     amount, status, priority, description,
                     timeline_json, sla_deadline)
                VALUES
                    (%s, %s, %s, %s, %s, 'opened', %s, %s, %s,
                     DATE_ADD(NOW(), INTERVAL %s DAY))
                """,
                (
                    invoice_id, customer_id, case_ref,
                    case_type[:100], amount, priority[:50],
                    description[:2000], timeline, sla_days,
                ),
            )
            case_id = cur.lastrowid

        return {
            "case_id":   case_id,
            "case_ref":  case_ref,
            "status":    "opened",
            "invoice_id": invoice_id,
            "sla_days":  sla_days,
        }
    except Exception as e:
        logger.error("create_legal_case failed: %s", e)
        return {"error": str(e)}


def get_legal_cases(
    status:      Optional[str] = None,
    customer_id: Optional[int] = None,
    limit:       int           = 50,
) -> list[dict]:
    """Get legal cases with optional filters."""
    from core.db import get_db
    _ensure_legal_cases_table()

    conditions = []
    params     = []
    if status:
        conditions.append("lc.status = %s")
        params.append(status)
    if customer_id is not None:
        conditions.append("lc.customer_id = %s")
        params.append(customer_id)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)

    try:
        with get_db() as (_, cur):
            cur.execute(
                f"""
                SELECT lc.*,
                       c.name   AS customer_name,
                       c.email  AS customer_email,
                       i.due_date,
                       i.status AS invoice_status,
                       DATEDIFF(NOW(), i.due_date) AS overdue_days
                FROM legal_cases lc
                LEFT JOIN customers c ON c.id = lc.customer_id
                LEFT JOIN invoices i  ON i.id = lc.invoice_id
                {where}
                ORDER BY lc.created_at DESC
                LIMIT %s
                """,
                tuple(params),
            )
            return cur.fetchall()
    except Exception as e:
        logger.warning("get_legal_cases failed: %s", e)
        return []


def get_legal_case(case_id: int) -> Optional[dict]:
    """Get a single legal case by ID."""
    from core.db import get_db
    _ensure_legal_cases_table()
    try:
        with get_db() as (_, cur):
            cur.execute(
                """
                SELECT lc.*,
                       c.name   AS customer_name,
                       c.email  AS customer_email,
                       c.phone  AS customer_phone,
                       i.amount AS invoice_amount,
                       i.due_date,
                       i.status AS invoice_status,
                       DATEDIFF(NOW(), i.due_date) AS overdue_days
                FROM legal_cases lc
                LEFT JOIN customers c ON c.id = lc.customer_id
                LEFT JOIN invoices i  ON i.id = lc.invoice_id
                WHERE lc.id = %s LIMIT 1
                """,
                (case_id,),
            )
            return cur.fetchone()
    except Exception as e:
        logger.warning("get_legal_case failed: %s", e)
        return None


def update_legal_case_status(
    case_id:    int,
    status:     str,
    note:       str = "",
    resolution: str = "",
) -> bool:
    """Update legal case status and append to timeline."""
    from core.db import get_db
    _ensure_legal_cases_table()

    try:
        with get_db() as (conn, cur):
            # Get current timeline
            cur.execute(
                "SELECT timeline_json FROM legal_cases WHERE id = %s",
                (case_id,),
            )
            row = cur.fetchone()
            if not row:
                return False

            timeline = json.loads(row.get("timeline_json") or "[]")
            timeline.append({
                "event":  f"status_changed_to_{status}",
                "date":   datetime.utcnow().isoformat() + "Z",
                "note":   note[:500],
            })

            resolved_clause = ", resolved_at = NOW()" if status in ("resolved", "settled", "closed") else ""

            cur.execute(
                f"""
                UPDATE legal_cases
                SET status        = %s,
                    timeline_json = %s,
                    resolution    = CASE WHEN %s != '' THEN %s ELSE resolution END
                    {resolved_clause}
                WHERE id = %s
                """,
                (status[:50], json.dumps(timeline), resolution, resolution[:2000], case_id),
            )
            return cur.rowcount > 0
    except Exception as e:
        logger.error("update_legal_case_status failed: %s", e)
        return False


# ════════════════════════════════════════════════════════════════════════════
#  ESCALATION TRACKING
# ════════════════════════════════════════════════════════════════════════════

def get_escalation_status(invoice_id: int) -> dict:
    """Get the current escalation status of an invoice."""
    from core.db import get_db

    try:
        with get_db() as (_, cur):
            # Get invoice current state
            cur.execute(
                """
                SELECT i.id, i.status, i.amount, i.due_date, i.ai_decision,
                       i.ai_risk_score, i.collection_strategy,
                       c.name AS customer_name, c.email AS customer_email,
                       DATEDIFF(NOW(), i.due_date) AS overdue_days
                FROM invoices i
                LEFT JOIN customers c ON c.id = i.customer_id
                WHERE i.id = %s LIMIT 1
                """,
                (invoice_id,),
            )
            invoice = cur.fetchone()
            if not invoice:
                return {"error": "Invoice not found"}

            # Get action history
            cur.execute(
                """
                SELECT action_type, template_name, priority, status, sent_at
                FROM finance_collection_log
                WHERE invoice_id = %s
                ORDER BY sent_at DESC
                LIMIT 20
                """,
                (invoice_id,),
            )
            actions = cur.fetchall()

            # Get legal cases
            cur.execute(
                """
                SELECT id, case_ref, status, priority, created_at, sla_deadline
                FROM legal_cases
                WHERE invoice_id = %s
                ORDER BY created_at DESC
                """,
                (invoice_id,),
            )
            legal = cur.fetchall()

            # Determine escalation tier
            status_val = invoice.get("status", "")
            tier_map = {
                "pending":   1, "overdue":      2,
                "suspended": 3, "legal":        4,
                "written_off": 5,
            }
            current_tier = tier_map.get(status_val, 1)

            tier_labels = {
                1: "reminder", 2: "follow_up",
                3: "suspension", 4: "legal",
                5: "write_off",
            }

        return {
            "invoice":       invoice,
            "current_tier":  current_tier,
            "tier_label":    tier_labels.get(current_tier, "unknown"),
            "actions_taken": actions,
            "legal_cases":   legal,
            "action_count":  len(actions),
        }
    except Exception as e:
        logger.warning("get_escalation_status failed: %s", e)
        return {"error": str(e)}


def get_active_escalations() -> list[dict]:
    """Get all invoices currently under active escalation."""
    from core.db import get_db
    try:
        with get_db() as (_, cur):
            cur.execute(
                """
                SELECT i.id AS invoice_id,
                       i.status,
                       i.amount,
                       i.ai_risk_score,
                       i.ai_decision,
                       i.collection_strategy,
                       c.name AS customer_name,
                       DATEDIFF(NOW(), i.due_date) AS overdue_days,
                       (SELECT COUNT(*) FROM finance_collection_log cl
                        WHERE cl.invoice_id = i.id) AS action_count,
                       (SELECT MAX(sent_at) FROM finance_collection_log cl
                        WHERE cl.invoice_id = i.id) AS last_action_at
                FROM invoices i
                LEFT JOIN customers c ON c.id = i.customer_id
                WHERE i.status IN ('overdue', 'suspended', 'legal', 'payment_plan')
                  AND i.due_date < NOW()
                ORDER BY DATEDIFF(NOW(), i.due_date) DESC
                LIMIT 100
                """,
            )
            return cur.fetchall()
    except Exception as e:
        logger.warning("get_active_escalations failed: %s", e)
        return []