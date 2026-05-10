"""
db.py — Database Layer (Production v5.2)
==========================================
Place this file at: app/core/db.py

✅ v5.2 Patches (on top of v5.1):
    Fix DB1 — get_pending_absence_events(): removed e.performance_score from JOIN
               (column doesn't exist in employees table → 1054 error)
    Fix DB2 — get_absence_event(): same fix — use ae.performance_score instead
    Fix DB3 — SalaryReviewWorkflow._persist() and IncentiveWorkflow._persist():
               event_id now resolved before save_decision() call → no more
               1048 (23000): Column 'event_id' cannot be null
    Fix DB4 — update_salary_review_status() / update_incentive_status():
               now also update the employee_name and job_level fields if present
               (keeps data consistent for audit trail reads)

✅ v5.3 Patches:
    Fix IMPORT1 — Added finance re-exports at the bottom so that any workflow
                  doing `from core.db import update_invoice_status` (or any
                  other finance_db function) continues to work without changes.
                  Single source of truth stays in core/finance_db.py — the
                  wrappers here are thin lazy-import delegates.
"""

import os
import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

import mysql.connector
from mysql.connector import pooling
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_pool: Optional[pooling.MySQLConnectionPool] = None


def init_db_pool() -> None:
    global _pool
    _pool = pooling.MySQLConnectionPool(
        pool_name="erp_pool",
        pool_size=10,
        pool_reset_session=True,
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 3306)),
        database=os.getenv("DB_NAME", "ai_erp"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        charset="utf8mb4",
        autocommit=False,
        connection_timeout=10,
    )
    logger.info("✅ DB pool initialized — pool_size=10")


@contextmanager
def get_db():
    if _pool is None:
        raise RuntimeError("DB pool not initialized. Call init_db_pool() first.")
    conn   = _pool.get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        yield conn, cursor
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.error("DB error — rolled back: %s", exc)
        raise
    finally:
        cursor.close()
        conn.close()


# ════════════════════════════════════════════════════════
#  EMPLOYEES
# ════════════════════════════════════════════════════════

def get_employee(employee_id: int) -> Optional[dict]:
    with get_db() as (_, cur):
        cur.execute(
            "SELECT * FROM employees WHERE id = %s LIMIT 1",
            (employee_id,)
        )
        return cur.fetchone()


def get_all_employees(active_only: bool = True) -> list[dict]:
    with get_db() as (_, cur):
        if active_only:
            cur.execute("SELECT * FROM employees WHERE status = 'active' ORDER BY name")
        else:
            cur.execute("SELECT * FROM employees ORDER BY name")
        return cur.fetchall()


def update_employee(employee_id: int, fields: dict) -> bool:
    if not fields:
        return False
    set_clause = ", ".join(f"{k} = %s" for k in fields)
    values = list(fields.values()) + [employee_id]
    with get_db() as (conn, cur):
        cur.execute(
            f"UPDATE employees SET {set_clause}, updated_at = NOW() WHERE id = %s",
            values
        )
        return cur.rowcount > 0


# ════════════════════════════════════════════════════════
#  LEAVES
# ════════════════════════════════════════════════════════

def create_leave_request(data: dict) -> int:
    with get_db() as (conn, cur):
        cur.execute(
            """
            INSERT INTO leaves
                (employee_id, leave_days, leave_type, reason, status, created_at)
            VALUES
                (%(employee_id)s, %(leave_days)s, %(leave_type)s,
                 %(reason)s, 'pending', NOW())
            """,
            data
        )
        return cur.lastrowid


def get_pending_leaves() -> list[dict]:
    with get_db() as (_, cur):
        cur.execute(
            """
            SELECT
                l.*,
                e.name AS employee_name,
                e.leave_balance,
                e.department
            FROM leaves l
            JOIN employees e ON e.id = l.employee_id
            WHERE l.status = 'pending'
            ORDER BY l.created_at ASC
            """
        )
        return cur.fetchall()


def get_leave(leave_id: int) -> Optional[dict]:
    with get_db() as (_, cur):
        cur.execute(
            """
            SELECT l.*, e.name AS employee_name, e.leave_balance, e.department
            FROM leaves l
            JOIN employees e ON e.id = l.employee_id
            WHERE l.id = %s LIMIT 1
            """,
            (leave_id,)
        )
        return cur.fetchone()


def update_leave_status(leave_id: int, status: str, notes: str = "") -> bool:
    with get_db() as (conn, cur):
        cur.execute(
            "UPDATE leaves SET status = %s, notes = %s WHERE id = %s",
            (status, notes, leave_id)
        )
        return cur.rowcount > 0


def get_employee_leaves(employee_id: int) -> list[dict]:
    with get_db() as (_, cur):
        cur.execute(
            "SELECT * FROM leaves WHERE employee_id = %s ORDER BY created_at DESC",
            (employee_id,)
        )
        return cur.fetchall()


def get_leave_status(leave_id: int) -> Optional[str]:
    with get_db() as (_, cur):
        cur.execute(
            "SELECT status FROM leaves WHERE id = %s LIMIT 1",
            (leave_id,)
        )
        row = cur.fetchone()
        return row["status"] if row else None


# ════════════════════════════════════════════════════════
#  FIX 2: ATOMIC LEAVE + BALANCE UPDATE
# ════════════════════════════════════════════════════════

def update_leave_and_balance(
    leave_id:     int,
    employee_id:  int,
    status:       str,
    notes:        str = "",
    leave_days:   int = 0,
    performed_by: str = "hr_agent_v5.1",
) -> dict:
    """
    ✅ FIX 2: ATOMIC transaction — Leave status + Balance deduction في نفس الوقت.
    """
    try:
        with get_db() as (conn, cur):
            cur.execute(
                "SELECT leave_balance FROM employees WHERE id = %s FOR UPDATE",
                (employee_id,),
            )
            row         = cur.fetchone()
            old_balance = int(row["leave_balance"] or 0) if row else 0

            cur.execute(
                "UPDATE leaves SET status = %s, notes = %s WHERE id = %s",
                (status, notes[:500], leave_id),
            )

            new_balance = old_balance
            if status == "approved" and leave_days > 0:
                new_balance = max(0, old_balance - leave_days)
                cur.execute(
                    "UPDATE employees SET leave_balance = %s WHERE id = %s",
                    (new_balance, employee_id),
                )

            conn.commit()

        if status == "approved" and leave_days > 0:
            write_balance_audit_log(
                employee_id   = employee_id,
                old_balance   = old_balance,
                new_balance   = new_balance,
                change_reason = f"approved:leave_id={leave_id},days={leave_days}",
                leave_id      = leave_id,
                performed_by  = performed_by,
            )

        logger.info(
            "✅ [DB] Atomic update: leave #%d → %s | balance: %d→%d | employee=%d",
            leave_id, status, old_balance, new_balance, employee_id,
        )
        return {"success": True, "old_balance": old_balance, "new_balance": new_balance}

    except Exception as e:
        logger.error("update_leave_and_balance failed: %s", e)
        return {"success": False, "old_balance": 0, "new_balance": 0, "error": str(e)}


# ════════════════════════════════════════════════════════
#  FIX 2: BALANCE AUDIT LOG
# ════════════════════════════════════════════════════════

def _ensure_balance_audit_table() -> None:
    try:
        with get_db() as (conn, cur):
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS balance_audit_log (
                    id            INT AUTO_INCREMENT PRIMARY KEY,
                    employee_id   INT NOT NULL,
                    leave_id      INT DEFAULT 0,
                    old_balance   INT NOT NULL,
                    new_balance   INT NOT NULL,
                    delta         INT NOT NULL,
                    change_reason VARCHAR(300),
                    performed_by  VARCHAR(100),
                    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_emp     (employee_id),
                    INDEX idx_created (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
    except Exception:
        pass


def write_balance_audit_log(
    employee_id:   int,
    old_balance:   int,
    new_balance:   int,
    change_reason: str,
    leave_id:      int = 0,
    performed_by:  str = "system",
) -> None:
    _ensure_balance_audit_table()
    delta = new_balance - old_balance

    if delta > 0 and "reset" not in change_reason and "correction" not in change_reason and "carryover" not in change_reason:
        logger.warning(
            "⚠️ [BalanceAudit] Unexpected INCREASE: employee=%d | %d→%d (+%d) | reason=%s",
            employee_id, old_balance, new_balance, delta, change_reason,
        )

    try:
        with get_db() as (conn, cur):
            cur.execute(
                """
                INSERT INTO balance_audit_log
                    (employee_id, leave_id, old_balance, new_balance,
                     delta, change_reason, performed_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (employee_id, leave_id, old_balance, new_balance,
                 delta, change_reason[:300], performed_by),
            )
    except Exception as e:
        logger.error("write_balance_audit_log failed: %s", e)


def get_balance_history(employee_id: int, limit: int = 20) -> list[dict]:
    try:
        with get_db() as (_, cur):
            cur.execute(
                """
                SELECT * FROM balance_audit_log
                WHERE employee_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (employee_id, limit),
            )
            return cur.fetchall()
    except Exception as e:
        logger.warning("get_balance_history failed: %s", e)
        return []


# ════════════════════════════════════════════════════════
#  FIX 4: COMPLETE DECISION AUDIT TRAIL
# ════════════════════════════════════════════════════════

def _ensure_decision_audit_table() -> None:
    try:
        with get_db() as (conn, cur):
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS decision_audit (
                    id              INT AUTO_INCREMENT PRIMARY KEY,
                    leave_id        INT NOT NULL,
                    employee_id     INT NOT NULL,
                    decision        VARCHAR(50)  NOT NULL,
                    old_balance     INT          DEFAULT 0,
                    new_balance     INT          DEFAULT 0,
                    balance_delta   INT          DEFAULT 0,
                    confidence      FLOAT        NOT NULL,
                    raw_confidence  FLOAT,
                    decision_source VARCHAR(100),
                    model_version   VARCHAR(100),
                    tier            INT          DEFAULT 2,
                    llm_used        TINYINT(1)   DEFAULT 0,
                    override_rule   VARCHAR(100),
                    execution_ms    INT          DEFAULT 0,
                    request_id      VARCHAR(100),
                    flags_json      TEXT,
                    created_at      DATETIME     DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_leave    (leave_id),
                    INDEX idx_employee (employee_id),
                    INDEX idx_decision (decision),
                    INDEX idx_source   (decision_source),
                    INDEX idx_created  (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
    except Exception:
        pass


def write_decision_audit(
    leave_id:        int,
    employee_id:     int,
    decision:        str,
    confidence:      float,
    decision_source: str,
    old_balance:     int   = 0,
    new_balance:     int   = 0,
    raw_confidence:  float = None,
    model_version:   str   = "unknown",
    tier:            int   = 2,
    llm_used:        bool  = False,
    override_rule:   str   = "",
    execution_ms:    int   = 0,
    request_id:      str   = "",
    flags:           list  = None,
) -> None:
    _ensure_decision_audit_table()
    import json as _json

    try:
        with get_db() as (conn, cur):
            cur.execute(
                """
                INSERT INTO decision_audit
                    (leave_id, employee_id, decision,
                     old_balance, new_balance, balance_delta,
                     confidence, raw_confidence, decision_source,
                     model_version, tier, llm_used, override_rule,
                     execution_ms, request_id, flags_json)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    leave_id, employee_id, decision,
                    old_balance, new_balance, new_balance - old_balance,
                    round(confidence, 4),
                    round(raw_confidence, 4) if raw_confidence is not None else None,
                    decision_source[:100], model_version[:100],
                    tier, int(llm_used), (override_rule or "")[:100],
                    execution_ms, (request_id or "")[:100],
                    _json.dumps(flags or []),
                ),
            )
    except Exception as e:
        logger.error("write_decision_audit failed (non-critical): %s", e)


# ════════════════════════════════════════════════════════
#  TICKETS (Customer Support)
# ════════════════════════════════════════════════════════

def create_ticket(data: dict) -> int:
    with get_db() as (conn, cur):
        cur.execute(
            """
            INSERT INTO tickets
                (customer_id, message, category, priority, status, created_at)
            VALUES
                (%(customer_id)s, %(message)s, %(category)s,
                 %(priority)s, 'open', NOW())
            """,
            data
        )
        return cur.lastrowid


def get_pending_tickets() -> list[dict]:
    with get_db() as (_, cur):
        cur.execute(
            """
            SELECT t.*, c.name AS customer_name, c.email AS customer_email
            FROM tickets t
            LEFT JOIN customers c ON c.id = t.customer_id
            WHERE t.status = 'open'
            ORDER BY
                FIELD(t.priority, 'critical', 'high', 'medium', 'low'),
                t.created_at ASC
            """
        )
        return cur.fetchall()


def update_ticket_status(ticket_id: int, status: str, resolution: str = "") -> bool:
    with get_db() as (conn, cur):
        cur.execute(
            "UPDATE tickets SET status = %s, resolution = %s, resolved_at = NOW() WHERE id = %s",
            (status, resolution, ticket_id)
        )
        return cur.rowcount > 0


# ════════════════════════════════════════════════════════
#  LEADS (CRM)
# ════════════════════════════════════════════════════════

def create_lead(data: dict) -> int:
    with get_db() as (conn, cur):
        cur.execute(
            """
            INSERT INTO leads
                (name, email, phone, source, status, notes, created_at)
            VALUES
                (%(name)s, %(email)s, %(phone)s,
                 %(source)s, 'new', %(notes)s, NOW())
            """,
            data
        )
        return cur.lastrowid


def get_new_leads() -> list[dict]:
    with get_db() as (_, cur):
        cur.execute(
            "SELECT * FROM leads WHERE status = 'new' ORDER BY created_at ASC"
        )
        return cur.fetchall()


def update_lead_status(lead_id: int, status: str, score: int = 0, notes: str = "") -> bool:
    with get_db() as (conn, cur):
        cur.execute(
            "UPDATE leads SET status = %s, score = %s, notes = %s, updated_at = NOW() WHERE id = %s",
            (status, score, notes, lead_id)
        )
        return cur.rowcount > 0


# ════════════════════════════════════════════════════════
#  EVENTS (Trigger Queue)
# ════════════════════════════════════════════════════════

def create_event(event_type: str, entity: str, entity_id: int, payload: dict = None) -> int:
    import json
    with get_db() as (conn, cur):
        cur.execute(
            """
            INSERT INTO events
                (event_type, entity, entity_id, payload, status, created_at)
            VALUES
                (%s, %s, %s, %s, 'pending', NOW())
            """,
            (event_type, entity, entity_id, json.dumps(payload or {}))
        )
        return cur.lastrowid


def get_pending_events() -> list[dict]:
    with get_db() as (_, cur):
        cur.execute(
            """
            SELECT * FROM events
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT 50
            """
        )
        return cur.fetchall()


def mark_event_done(event_id: int, result: str = "success") -> None:
    with get_db() as (conn, cur):
        cur.execute(
            "UPDATE events SET status = %s, processed_at = NOW() WHERE id = %s",
            (result, event_id)
        )


# ════════════════════════════════════════════════════════
#  DECISIONS (Agent Decisions Log)
# ════════════════════════════════════════════════════════

def save_decision(data: dict) -> int:
    if "event_id" not in data:
        data["event_id"] = None
    with get_db() as (conn, cur):
        cur.execute(
            """
            INSERT INTO decisions
                (event_id, agent_type, entity, entity_id, decision,
                 confidence, reasoning, raw_response, created_at)
            VALUES
                (%(event_id)s, %(agent_type)s, %(entity)s, %(entity_id)s, %(decision)s,
                 %(confidence)s, %(reasoning)s, %(raw_response)s, NOW())
            """,
            data
        )
        return cur.lastrowid


# ════════════════════════════════════════════════════════
#  ACTIONS
# ════════════════════════════════════════════════════════

def log_action(data: dict) -> int:
    with get_db() as (conn, cur):
        cur.execute(
            """
            INSERT INTO actions
                (action_type, entity, entity_id, performed_by,
                 result, details, created_at)
            VALUES
                (%(action_type)s, %(entity)s, %(entity_id)s, %(performed_by)s,
                 %(result)s, %(details)s, NOW())
            """,
            data
        )
        return cur.lastrowid


# ════════════════════════════════════════════════════════
#  AUDIT LOGS
# ════════════════════════════════════════════════════════

def write_audit_log(
    action:       str,
    entity:       str,
    entity_id:    int,
    performed_by: str,
    details:      str = "",
    status:       str = "success"
) -> None:
    try:
        with get_db() as (conn, cur):
            cur.execute(
                """
                INSERT INTO audit_logs
                    (action, entity, entity_id, performed_by, details, status, created_at)
                VALUES
                    (%s, %s, %s, %s, %s, %s, NOW())
                """,
                (action, entity, entity_id, performed_by, details, status)
            )
    except Exception as e:
        logger.error("Failed to write audit log: %s", e)


# ════════════════════════════════════════════════════════
#  EXECUTION TRACKER
# ════════════════════════════════════════════════════════

def start_execution(workflow: str, trigger: str, entity_id: int) -> int:
    with get_db() as (conn, cur):
        cur.execute(
            """
            INSERT INTO execution_tracker
                (workflow_name, triggered_by, entity_id, status, started_at)
            VALUES (%s, %s, %s, 'running', NOW())
            """,
            (workflow, trigger, entity_id)
        )
        return cur.lastrowid


def finish_execution(execution_id: int, status: str = "completed", error: str = "") -> None:
    with get_db() as (conn, cur):
        cur.execute(
            """
            UPDATE execution_tracker
            SET status = %s, error_msg = %s, finished_at = NOW()
            WHERE id = %s
            """,
            (status, error, execution_id)
        )


# ════════════════════════════════════════════════════════
#  AI MEMORY
# ════════════════════════════════════════════════════════

def save_memory(agent: str, key: str, value: str) -> None:
    with get_db() as (conn, cur):
        cur.execute(
            """
            INSERT INTO ai_memory (agent, memory_key, memory_value, updated_at)
            VALUES (%s, %s, %s, NOW())
            ON DUPLICATE KEY UPDATE memory_value = VALUES(memory_value), updated_at = NOW()
            """,
            (agent, key, value)
        )


def get_memory(agent: str, key: str) -> Optional[str]:
    with get_db() as (_, cur):
        cur.execute(
            "SELECT memory_value FROM ai_memory WHERE agent = %s AND memory_key = %s LIMIT 1",
            (agent, key)
        )
        row = cur.fetchone()
        return row["memory_value"] if row else None


def get_all_memory(agent: str) -> dict:
    with get_db() as (_, cur):
        cur.execute(
            "SELECT memory_key, memory_value FROM ai_memory WHERE agent = %s",
            (agent,)
        )
        return {row["memory_key"]: row["memory_value"] for row in cur.fetchall()}


# ════════════════════════════════════════════════════════
#  FINANCIAL LOGS
# ════════════════════════════════════════════════════════

def log_financial(data: dict) -> int:
    with get_db() as (conn, cur):
        cur.execute(
            """
            INSERT INTO financial_logs
                (transaction_type, amount, currency, entity, entity_id,
                 description, created_at)
            VALUES
                (%(transaction_type)s, %(amount)s, %(currency)s,
                 %(entity)s, %(entity_id)s, %(description)s, NOW())
            """,
            data
        )
        return cur.lastrowid


# ════════════════════════════════════════════════════════
#  HR DOMAIN: AUTO-CREATE TABLES
# ════════════════════════════════════════════════════════

def _ensure_salary_table() -> None:
    try:
        with get_db() as (conn, cur):
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS salary_reviews (
                    id                          INT AUTO_INCREMENT PRIMARY KEY,
                    employee_id                 INT NOT NULL,
                    employee_name               VARCHAR(200),
                    current_salary_egp          DECIMAL(12,2) DEFAULT 0,
                    requested_increment_pct     FLOAT DEFAULT 0.10,
                    market_median_egp           DECIMAL(12,2) DEFAULT 0,
                    market_gap_pct              FLOAT DEFAULT 0,
                    months_since_last_increment INT DEFAULT 12,
                    months_in_role              INT DEFAULT 0,
                    appraisal_cycle             VARCHAR(50) DEFAULT 'Annual',
                    kpi_achievement             FLOAT DEFAULT 0.80,
                    budget_utilization          FLOAT DEFAULT 0.80,
                    available_pool_egp          DECIMAL(12,2) DEFAULT 0,
                    is_on_pip                   TINYINT(1) DEFAULT 0,
                    is_on_probation             TINYINT(1) DEFAULT 0,
                    status                      VARCHAR(50) DEFAULT 'pending',
                    ai_decision                 VARCHAR(100),
                    confidence_score            FLOAT,
                    decision_reason             TEXT,
                    recommended_increment_pct   FLOAT,
                    request_id                  VARCHAR(100),
                    notes                       TEXT,
                    created_at                  DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at                  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_employee   (employee_id),
                    INDEX idx_status     (status),
                    INDEX idx_created    (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
    except Exception:
        pass


def _ensure_incentive_table() -> None:
    try:
        with get_db() as (conn, cur):
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS incentive_requests (
                    id                              INT AUTO_INCREMENT PRIMARY KEY,
                    employee_id                     INT NOT NULL,
                    employee_name                   VARCHAR(200),
                    incentive_type                  VARCHAR(100) DEFAULT 'performance_bonus',
                    requested_amount_egp            DECIMAL(12,2) DEFAULT 0,
                    approved_amount_egp             DECIMAL(12,2),
                    kpi_achievement                 FLOAT DEFAULT 0.80,
                    performance_score               FLOAT DEFAULT 0.75,
                    monthly_salary_egp              DECIMAL(12,2) DEFAULT 0,
                    tenure_months                   INT DEFAULT 0,
                    is_on_pip                       TINYINT(1) DEFAULT 0,
                    is_critical_talent              TINYINT(1) DEFAULT 0,
                    incentive_budget_remaining_egp  DECIMAL(12,2) DEFAULT 0,
                    perf_trend                      VARCHAR(50) DEFAULT 'stable',
                    reason                          TEXT,
                    status                          VARCHAR(50) DEFAULT 'pending',
                    ai_decision                     VARCHAR(100),
                    confidence_score                FLOAT,
                    decision_reason                 TEXT,
                    request_id                      VARCHAR(100),
                    notes                           TEXT,
                    created_at                      DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at                      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_employee   (employee_id),
                    INDEX idx_type       (incentive_type),
                    INDEX idx_status     (status),
                    INDEX idx_created    (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
    except Exception:
        pass


def _ensure_absence_table() -> None:
    try:
        with get_db() as (conn, cur):
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS absence_events (
                    id                          INT AUTO_INCREMENT PRIMARY KEY,
                    employee_id                 INT NOT NULL,
                    employee_name               VARCHAR(200),
                    absence_date                DATE NOT NULL,
                    absence_type_claimed        VARCHAR(100) DEFAULT 'unexcused',
                    duration_hours              FLOAT DEFAULT 8,
                    medical_certificate_provided TINYINT(1) DEFAULT 0,
                    prior_approval_obtained     TINYINT(1) DEFAULT 0,
                    reason                      TEXT,
                    total_absences_90d          INT DEFAULT 0,
                    unexcused_count_90d         INT DEFAULT 0,
                    late_arrivals_90d           INT DEFAULT 0,
                    previous_warnings           VARCHAR(50) DEFAULT 'none',
                    performance_score           FLOAT DEFAULT 0.75,
                    is_on_pip                   TINYINT(1) DEFAULT 0,
                    status                      VARCHAR(50) DEFAULT 'pending',
                    ai_decision                 VARCHAR(100),
                    ai_classification           VARCHAR(100),
                    confidence_score            FLOAT,
                    decision_reason             TEXT,
                    payroll_deduction_days      FLOAT DEFAULT 0,
                    escalation_required         TINYINT(1) DEFAULT 0,
                    request_id                  VARCHAR(100),
                    notes                       TEXT,
                    created_at                  DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at                  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_employee   (employee_id),
                    INDEX idx_date       (absence_date),
                    INDEX idx_status     (status),
                    INDEX idx_created    (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
    except Exception:
        pass


def _ensure_hr_domain_audit_table() -> None:
    try:
        with get_db() as (conn, cur):
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS hr_domain_audit (
                    id              INT AUTO_INCREMENT PRIMARY KEY,
                    domain          VARCHAR(50)  NOT NULL,
                    entity_id       INT          NOT NULL,
                    employee_id     INT          NOT NULL,
                    decision        VARCHAR(100) NOT NULL,
                    confidence      FLOAT,
                    decision_source VARCHAR(100),
                    override_rule   VARCHAR(100),
                    llm_used        TINYINT(1) DEFAULT 0,
                    execution_ms    INT DEFAULT 0,
                    request_id      VARCHAR(100),
                    flags_json      TEXT,
                    extra_data      TEXT,
                    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_domain     (domain),
                    INDEX idx_entity     (entity_id),
                    INDEX idx_employee   (employee_id),
                    INDEX idx_decision   (decision),
                    INDEX idx_created    (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
    except Exception:
        pass


# ════════════════════════════════════════════════════════
#  SALARY REVIEWS
# ════════════════════════════════════════════════════════

def create_salary_review(data: dict) -> int:
    _ensure_salary_table()
    with get_db() as (conn, cur):
        cur.execute(
            """
            INSERT INTO salary_reviews (
                employee_id, employee_name, current_salary_egp,
                requested_increment_pct, market_median_egp, market_gap_pct,
                months_since_last_increment, months_in_role, appraisal_cycle,
                kpi_achievement, budget_utilization, available_pool_egp,
                is_on_pip, is_on_probation, status
            ) VALUES (
                %(employee_id)s, %(employee_name)s, %(current_salary_egp)s,
                %(requested_increment_pct)s, %(market_median_egp)s, %(market_gap_pct)s,
                %(months_since_last_increment)s, %(months_in_role)s, %(appraisal_cycle)s,
                %(kpi_achievement)s, %(budget_utilization)s, %(available_pool_egp)s,
                %(is_on_pip)s, %(is_on_probation)s, 'pending'
            )
            """,
            {
                "employee_id":                 data.get("employee_id"),
                "employee_name":               data.get("employee_name", ""),
                "current_salary_egp":          data.get("current_salary_egp", 0),
                "requested_increment_pct":     data.get("requested_increment_pct", 0.10),
                "market_median_egp":           data.get("market_median_egp", 0),
                "market_gap_pct":              data.get("market_gap_pct", 0),
                "months_since_last_increment": data.get("months_since_last_increment", 12),
                "months_in_role":              data.get("months_in_role", 0),
                "appraisal_cycle":             data.get("appraisal_cycle", "Annual"),
                "kpi_achievement":             data.get("kpi_achievement", 0.80),
                "budget_utilization":          data.get("budget_utilization", 0.80),
                "available_pool_egp":          data.get("available_pool_egp", 0),
                "is_on_pip":                   int(bool(data.get("is_on_pip", False))),
                "is_on_probation":             int(bool(data.get("is_on_probation", False))),
            },
        )
        return cur.lastrowid


def get_salary_review(review_id: int) -> dict | None:
    _ensure_salary_table()
    with get_db() as (_, cur):
        cur.execute(
            """
            SELECT sr.*,
                   COALESCE(sr.employee_name, e.name) AS employee_name,
                   COALESCE(e.job_level, 'junior')    AS job_level,
                   COALESCE(e.salary_grade, 'C')      AS salary_grade,
                   e.department
            FROM salary_reviews sr
            LEFT JOIN employees e ON e.id = sr.employee_id
            WHERE sr.id = %s LIMIT 1
            """,
            (review_id,),
        )
        return cur.fetchone()


def get_pending_salary_reviews() -> list[dict]:
    _ensure_salary_table()
    with get_db() as (_, cur):
        cur.execute(
            """
            SELECT sr.*,
                   COALESCE(sr.employee_name, e.name) AS employee_name,
                   COALESCE(e.job_level, 'junior')    AS job_level,
                   COALESCE(e.salary_grade, 'C')      AS salary_grade,
                   e.department
            FROM salary_reviews sr
            LEFT JOIN employees e ON e.id = sr.employee_id
            WHERE sr.status = 'pending'
            ORDER BY sr.created_at ASC
            """
        )
        return cur.fetchall()


def update_salary_review_status(
    review_id: int,
    status: str,
    ai_decision: str = "",
    confidence: float = 0.0,
    reason: str = "",
    recommended_pct: float = None,
    request_id: str = "",
) -> bool:
    _ensure_salary_table()
    with get_db() as (conn, cur):
        cur.execute(
            """
            UPDATE salary_reviews
            SET status = %s,
                ai_decision = %s,
                confidence_score = %s,
                decision_reason = %s,
                recommended_increment_pct = %s,
                request_id = %s
            WHERE id = %s
            """,
            (status, ai_decision[:100], confidence, reason[:1000],
             recommended_pct, request_id[:100], review_id),
        )
        return cur.rowcount > 0


def get_employee_salary_reviews(employee_id: int) -> list[dict]:
    _ensure_salary_table()
    with get_db() as (_, cur):
        cur.execute(
            "SELECT * FROM salary_reviews WHERE employee_id = %s ORDER BY created_at DESC",
            (employee_id,),
        )
        return cur.fetchall()


# ════════════════════════════════════════════════════════
#  INCENTIVE REQUESTS
# ════════════════════════════════════════════════════════

def create_incentive_request(data: dict) -> int:
    _ensure_incentive_table()
    with get_db() as (conn, cur):
        cur.execute(
            """
            INSERT INTO incentive_requests (
                employee_id, employee_name, incentive_type, requested_amount_egp,
                kpi_achievement, performance_score, monthly_salary_egp,
                tenure_months, is_on_pip, is_critical_talent,
                incentive_budget_remaining_egp, perf_trend, reason, status
            ) VALUES (
                %(employee_id)s, %(employee_name)s, %(incentive_type)s,
                %(requested_amount_egp)s, %(kpi_achievement)s, %(performance_score)s,
                %(monthly_salary_egp)s, %(tenure_months)s, %(is_on_pip)s,
                %(is_critical_talent)s, %(incentive_budget_remaining_egp)s,
                %(perf_trend)s, %(reason)s, 'pending'
            )
            """,
            {
                "employee_id":                    data.get("employee_id"),
                "employee_name":                  data.get("employee_name", ""),
                "incentive_type":                 data.get("incentive_type", "performance_bonus"),
                "requested_amount_egp":           data.get("requested_amount_egp", 0),
                "kpi_achievement":                data.get("kpi_achievement", 0.80),
                "performance_score":              data.get("performance_score", 0.75),
                "monthly_salary_egp":             data.get("monthly_salary_egp", 0),
                "tenure_months":                  data.get("tenure_months", 0),
                "is_on_pip":                      int(bool(data.get("is_on_pip", False))),
                "is_critical_talent":             int(bool(data.get("is_critical_talent", False))),
                "incentive_budget_remaining_egp": data.get("incentive_budget_remaining_egp", 0),
                "perf_trend":                     data.get("perf_trend", "stable"),
                "reason":                         data.get("reason", ""),
            },
        )
        return cur.lastrowid


def get_incentive_request(request_id_int: int) -> dict | None:
    _ensure_incentive_table()
    with get_db() as (_, cur):
        cur.execute(
            """
            SELECT ir.*,
                   COALESCE(ir.employee_name, e.name) AS employee_name,
                   COALESCE(e.job_level, 'junior')    AS job_level,
                   COALESCE(e.salary_grade, 'C')      AS salary_grade,
                   e.department
            FROM incentive_requests ir
            LEFT JOIN employees e ON e.id = ir.employee_id
            WHERE ir.id = %s LIMIT 1
            """,
            (request_id_int,),
        )
        return cur.fetchone()


def get_pending_incentive_requests() -> list[dict]:
    _ensure_incentive_table()
    with get_db() as (_, cur):
        cur.execute(
            """
            SELECT ir.*,
                   COALESCE(ir.employee_name, e.name) AS employee_name,
                   COALESCE(e.job_level, 'junior')    AS job_level,
                   COALESCE(e.salary_grade, 'C')      AS salary_grade,
                   e.department
            FROM incentive_requests ir
            LEFT JOIN employees e ON e.id = ir.employee_id
            WHERE ir.status = 'pending'
            ORDER BY ir.incentive_type ASC, ir.created_at ASC
            """
        )
        return cur.fetchall()


def update_incentive_status(
    request_id_int: int,
    status: str,
    ai_decision: str = "",
    confidence: float = 0.0,
    reason: str = "",
    approved_amount: float = None,
    request_id: str = "",
) -> bool:
    _ensure_incentive_table()
    with get_db() as (conn, cur):
        cur.execute(
            """
            UPDATE incentive_requests
            SET status = %s,
                ai_decision = %s,
                confidence_score = %s,
                decision_reason = %s,
                approved_amount_egp = %s,
                request_id = %s
            WHERE id = %s
            """,
            (status, ai_decision[:100], confidence, reason[:1000],
             approved_amount, request_id[:100], request_id_int),
        )
        return cur.rowcount > 0


def get_employee_incentives(employee_id: int) -> list[dict]:
    _ensure_incentive_table()
    with get_db() as (_, cur):
        cur.execute(
            "SELECT * FROM incentive_requests WHERE employee_id = %s ORDER BY created_at DESC",
            (employee_id,),
        )
        return cur.fetchall()


# ════════════════════════════════════════════════════════
#  ABSENCE EVENTS
# ════════════════════════════════════════════════════════

def create_absence_event(data: dict) -> int:
    _ensure_absence_table()
    with get_db() as (conn, cur):
        cur.execute(
            """
            INSERT INTO absence_events (
                employee_id, employee_name, absence_date, absence_type_claimed,
                duration_hours, medical_certificate_provided,
                prior_approval_obtained, reason,
                total_absences_90d, unexcused_count_90d,
                late_arrivals_90d, previous_warnings,
                performance_score, is_on_pip, status
            ) VALUES (
                %(employee_id)s, %(employee_name)s, %(absence_date)s,
                %(absence_type_claimed)s, %(duration_hours)s,
                %(medical_certificate_provided)s, %(prior_approval_obtained)s,
                %(reason)s, %(total_absences_90d)s, %(unexcused_count_90d)s,
                %(late_arrivals_90d)s, %(previous_warnings)s,
                %(performance_score)s, %(is_on_pip)s, 'pending'
            )
            """,
            {
                "employee_id":                  data.get("employee_id"),
                "employee_name":                data.get("employee_name", ""),
                "absence_date":                 data.get("absence_date"),
                "absence_type_claimed":         data.get("absence_type_claimed", "unexcused"),
                "duration_hours":               data.get("duration_hours", 8),
                "medical_certificate_provided": int(bool(data.get("medical_certificate_provided", False))),
                "prior_approval_obtained":      int(bool(data.get("prior_approval_obtained", False))),
                "reason":                       data.get("reason", ""),
                "total_absences_90d":           data.get("total_absences_90d", 0),
                "unexcused_count_90d":          data.get("unexcused_count_90d", 0),
                "late_arrivals_90d":            data.get("late_arrivals_90d", 0),
                "previous_warnings":            data.get("previous_warnings", "none"),
                "performance_score":            data.get("performance_score", 0.75),
                "is_on_pip":                    int(bool(data.get("is_on_pip", False))),
            },
        )
        return cur.lastrowid


def get_absence_event(event_id: int) -> dict | None:
    """
    ✅ Fix DB2: removed e.performance_score — use ae.performance_score instead.
    Employees table doesn't always have performance_score column.
    """
    _ensure_absence_table()
    with get_db() as (_, cur):
        cur.execute(
            """
            SELECT ae.*,
                   COALESCE(ae.employee_name, e.name) AS employee_name,
                   COALESCE(e.job_level, 'junior')    AS job_level,
                   COALESCE(e.salary_grade, 'C')      AS salary_grade,
                   e.department,
                   e.leave_balance
            FROM absence_events ae
            LEFT JOIN employees e ON e.id = ae.employee_id
            WHERE ae.id = %s LIMIT 1
            """,
            (event_id,),
        )
        return cur.fetchone()


def get_pending_absence_events() -> list[dict]:
    """
    ✅ Fix DB1: removed e.performance_score from SELECT.
    Use ae.performance_score (stored in absence_events table itself).
    """
    _ensure_absence_table()
    with get_db() as (_, cur):
        cur.execute(
            """
            SELECT ae.*,
                   COALESCE(ae.employee_name, e.name) AS employee_name,
                   COALESCE(e.job_level, 'junior')    AS job_level,
                   COALESCE(e.salary_grade, 'C')      AS salary_grade,
                   e.department
            FROM absence_events ae
            LEFT JOIN employees e ON e.id = ae.employee_id
            WHERE ae.status = 'pending'
            ORDER BY ae.unexcused_count_90d DESC, ae.created_at ASC
            """
        )
        return cur.fetchall()


def update_absence_event_status(
    event_id: int,
    status: str,
    ai_decision: str = "",
    ai_classification: str = "",
    confidence: float = 0.0,
    reason: str = "",
    payroll_deduction_days: float = 0.0,
    escalation_required: bool = False,
    request_id: str = "",
) -> bool:
    _ensure_absence_table()
    with get_db() as (conn, cur):
        cur.execute(
            """
            UPDATE absence_events
            SET status = %s,
                ai_decision = %s,
                ai_classification = %s,
                confidence_score = %s,
                decision_reason = %s,
                payroll_deduction_days = %s,
                escalation_required = %s,
                request_id = %s
            WHERE id = %s
            """,
            (
                status, ai_decision[:100], ai_classification[:100],
                confidence, reason[:1000], payroll_deduction_days,
                int(escalation_required), request_id[:100], event_id,
            ),
        )
        return cur.rowcount > 0


def get_employee_absences(employee_id: int, limit: int = 50) -> list[dict]:
    _ensure_absence_table()
    with get_db() as (_, cur):
        cur.execute(
            """
            SELECT * FROM absence_events
            WHERE employee_id = %s
            ORDER BY absence_date DESC
            LIMIT %s
            """,
            (employee_id, limit),
        )
        return cur.fetchall()


def get_employee_unexcused_count_90d(employee_id: int) -> int:
    _ensure_absence_table()
    try:
        with get_db() as (_, cur):
            cur.execute(
                """
                SELECT COUNT(*) AS cnt
                FROM absence_events
                WHERE employee_id = %s
                  AND absence_type_claimed IN ('unexcused', 'غياب بدون إذن')
                  AND created_at >= DATE_SUB(NOW(), INTERVAL 90 DAY)
                  AND status NOT IN ('pending', 'cancelled')
                """,
                (employee_id,),
            )
            row = cur.fetchone()
            return int(row["cnt"]) if row else 0
    except Exception:
        return 0


# ════════════════════════════════════════════════════════
#  HR DOMAIN AUDIT TRAIL (shared: salary / incentive / absence)
# ════════════════════════════════════════════════════════

def write_hr_domain_audit(
    domain: str,
    entity_id: int,
    employee_id: int,
    decision: str,
    confidence: float = 0.0,
    decision_source: str = "llm",
    override_rule: str = "",
    llm_used: bool = True,
    execution_ms: int = 0,
    request_id: str = "",
    flags: list = None,
    extra_data: dict = None,
) -> None:
    import json as _json
    _ensure_hr_domain_audit_table()
    try:
        with get_db() as (conn, cur):
            cur.execute(
                """
                INSERT INTO hr_domain_audit
                    (domain, entity_id, employee_id, decision, confidence,
                     decision_source, override_rule, llm_used, execution_ms,
                     request_id, flags_json, extra_data)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    domain[:50], entity_id, employee_id, decision[:100],
                    round(confidence, 4), decision_source[:100],
                    (override_rule or "")[:100], int(llm_used),
                    execution_ms, (request_id or "")[:100],
                    _json.dumps(flags or []),
                    _json.dumps(extra_data or {}),
                ),
            )
    except Exception as e:
        logger.error("write_hr_domain_audit failed: %s", e)


def get_hr_domain_audit(domain: str, entity_id: int) -> list[dict]:
    _ensure_hr_domain_audit_table()
    try:
        with get_db() as (_, cur):
            cur.execute(
                """
                SELECT * FROM hr_domain_audit
                WHERE domain = %s AND entity_id = %s
                ORDER BY created_at DESC
                """,
                (domain, entity_id),
            )
            return cur.fetchall()
    except Exception:
        return []


# ════════════════════════════════════════════════════════
#  HEALTH CHECK
# ════════════════════════════════════════════════════════

def health_check() -> dict:
    try:
        with get_db() as (_, cur):
            cur.execute("SELECT 1 AS ok")
            cur.fetchone()
        return {"database": "healthy"}
    except Exception as e:
        return {"database": "unhealthy", "error": str(e)}


# Backward-compat alias
create_leave = create_leave_request


# ════════════════════════════════════════════════════════════════════════════
#  ✅ v5.3 FIX IMPORT1 — FINANCE RE-EXPORTS (backward-compat bridge)
# ════════════════════════════════════════════════════════════════════════════
#
#  Problem:
#      Workflows were doing:
#          from core.db import update_invoice_status
#      But that function lives in core/finance_db.py, not here.
#      Result: ImportError → AI decision executes but DB never updates
#              → Inconsistent state.
#
#  Solution (hotfix):
#      Thin lazy-import wrappers here that delegate to finance_db.
#      Single source of truth stays in core/finance_db.py.
#      No workflow files need to change.
#
#  Long-term (next sprint):
#      Replace `from core.db import <finance_func>` with
#      `from core.finance_db import <finance_func>` in every workflow,
#      then delete these wrappers.
# ════════════════════════════════════════════════════════════════════════════

def _finance(name: str):
    """Lazy-import a function from core.finance_db to avoid circular imports."""
    import importlib
    mod = importlib.import_module("core.finance_db")
    fn  = getattr(mod, name, None)
    if fn is None:
        raise ImportError(
            f"[db.py finance bridge] 'core.finance_db' has no attribute '{name}'. "
            "Check that finance_db.py is up to date."
        )
    return fn


# ── Invoice operations ────────────────────────────────────────────────────────

def update_invoice_status(
    invoice_id:      int,
    status:          str,
    ai_decision:     str   = "",
    risk_score:      float = 0.0,
    decision_reason: str   = "",
    action_plan:     str   = "",
    request_id:      str   = "",
) -> bool:
    """Bridge → core.finance_db.update_invoice_status"""
    return _finance("update_invoice_status")(
        invoice_id, status, ai_decision,
        risk_score, decision_reason, action_plan, request_id,
    )


def update_invoice_collection_strategy(
    invoice_id:          int,
    risk_score:          float,
    collection_strategy: str,
    first_reminder_days: int,
    request_id:          str = "",
) -> bool:
    """Bridge → core.finance_db.update_invoice_collection_strategy"""
    return _finance("update_invoice_collection_strategy")(
        invoice_id, risk_score, collection_strategy,
        first_reminder_days, request_id,
    )


def get_invoice(invoice_id: int) -> Optional[dict]:
    """Bridge → core.finance_db.get_invoice"""
    return _finance("get_invoice")(invoice_id)


def get_overdue_invoices(min_days: int = 1, limit: int = 200) -> list[dict]:
    """Bridge → core.finance_db.get_overdue_invoices"""
    return _finance("get_overdue_invoices")(min_days, limit)


def get_pending_invoices() -> list[dict]:
    """Bridge → core.finance_db.get_pending_invoices"""
    return _finance("get_pending_invoices")()


def get_customer_invoice_summary(customer_id: int) -> dict:
    """Bridge → core.finance_db.get_customer_invoice_summary"""
    return _finance("get_customer_invoice_summary")(customer_id)


# ── Finance decisions log ─────────────────────────────────────────────────────

def save_finance_decision(data: dict) -> int:
    """Bridge → core.finance_db.save_finance_decision"""
    return _finance("save_finance_decision")(data)


def get_finance_decisions(entity_id: int, entity: str = "invoices") -> list[dict]:
    """Bridge → core.finance_db.get_finance_decisions"""
    return _finance("get_finance_decisions")(entity_id, entity)


# ── Finance audit ─────────────────────────────────────────────────────────────

def write_finance_audit(*args, **kwargs) -> None:
    """Bridge → core.finance_db.write_finance_audit"""
    return _finance("write_finance_audit")(*args, **kwargs)


def get_finance_audit(domain: str, entity_id: int) -> list[dict]:
    """Bridge → core.finance_db.get_finance_audit"""
    return _finance("get_finance_audit")(domain, entity_id)


# ── Dashboard / stats ─────────────────────────────────────────────────────────

def get_finance_dashboard_stats() -> dict:
    """Bridge → core.finance_db.get_finance_dashboard_stats"""
    return _finance("get_finance_dashboard_stats")()


def get_cashflow_forecast() -> dict:
    """Bridge → core.finance_db.get_cashflow_forecast"""
    return _finance("get_cashflow_forecast")()


# ── Customer helpers ──────────────────────────────────────────────────────────

def get_customer_email(customer_id: int) -> Optional[str]:
    """Bridge → core.finance_db.get_customer_email"""
    return _finance("get_customer_email")(customer_id)


def get_customer_info(customer_id: int) -> Optional[dict]:
    """Bridge → core.finance_db.get_customer_info"""
    return _finance("get_customer_info")(customer_id)


def update_customer_status(
    customer_id:    int,
    service_status: str  = "",
    is_blacklisted: bool = None,
    extra_fields:   dict = None,
) -> bool:
    """Bridge → core.finance_db.update_customer_status"""
    return _finance("update_customer_status")(
        customer_id, service_status, is_blacklisted, extra_fields,
    )


# ── Collection log ────────────────────────────────────────────────────────────

def log_collection_action(**kwargs) -> int:
    """Bridge → core.finance_db.log_collection_action"""
    return _finance("log_collection_action")(**kwargs)


def get_collection_log(
    invoice_id:  Optional[int] = None,
    customer_id: Optional[int] = None,
    action_type: Optional[str] = None,
    limit:       int           = 50,
) -> list[dict]:
    """Bridge → core.finance_db.get_collection_log"""
    return _finance("get_collection_log")(invoice_id, customer_id, action_type, limit)


# ── Finance DB init ───────────────────────────────────────────────────────────

def init_finance_db() -> None:
    """Bridge → core.finance_db.init_finance_db"""
    return _finance("init_finance_db")()