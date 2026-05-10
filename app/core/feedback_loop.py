"""
🔄 Finance Feedback Loop — v1.0 Production
============================================
File: app/core/feedback_loop.py

Compares AI decisions with actual customer behavior.
Feeds accuracy metrics back to improve the system.

How it works:
    1. Scheduler runs daily
    2. Finds all AI decisions made 7+ days ago
    3. Checks what actually happened (paid? still overdue? legal?)
    4. Calculates accuracy per decision type
    5. Detects model drift (accuracy dropping)
    6. Triggers alert if drift detected

Outcome Classification:
    AI Decision          → Good Outcome      → Bad Outcome
    soft_follow_up       → paid              → still overdue 14+ days
    hard_follow_up       → paid / plan       → legal / write_off
    payment_plan         → partial / paid    → write_off / no payment
    suspend_service      → paid after suspend → legal / write_off
    legal_escalation     → collected legally → write_off

Add to trigger.py:
    from core.feedback_loop import job_run_feedback_loop
    _scheduler.add_job(
        job_run_feedback_loop,
        trigger=CronTrigger(hour=2, minute=0),  # daily 2 AM
        id="feedback_loop",
        name="[Finance] AI Feedback Loop",
        max_instances=1,
    )
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


# ── Outcome Rules ─────────────────────────────────────────────────────────────
# Maps (decision, actual_status) → outcome label

OUTCOME_MATRIX: dict[str, dict[str, str]] = {
    "safe_to_collect": {
        "paid":        "correct",
        "overdue":     "wrong",
        "legal":       "wrong",
        "written_off": "wrong",
        "partial":     "partial",
    },
    "soft_follow_up": {
        "paid":             "correct",
        "partial":          "partial",
        "overdue":          "wrong",   # still unpaid after soft nudge
        "legal":            "wrong",
        "written_off":      "wrong",
        "payment_plan":     "partial",
        "suspended":        "neutral",
    },
    "hard_follow_up": {
        "paid":             "correct",
        "payment_plan":     "correct",  # escalation worked → plan agreed
        "partial":          "partial",
        "legal":            "neutral",  # escalated correctly
        "suspended":        "neutral",
        "overdue":          "wrong",
        "written_off":      "wrong",
    },
    "payment_plan": {
        "paid":             "correct",
        "payment_plan":     "correct",  # still on plan — in progress
        "partial":          "partial",
        "overdue":          "wrong",
        "legal":            "wrong",
        "written_off":      "wrong",
    },
    "suspend_service": {
        "paid":             "correct",  # suspension worked!
        "payment_plan":     "correct",
        "legal":            "neutral",  # escalated
        "suspended":        "neutral",  # still suspended — waiting
        "written_off":      "wrong",
        "overdue":          "wrong",
    },
    "legal_escalation": {
        "legal":            "neutral",   # in progress
        "paid":             "correct",   # legal worked
        "written_off":      "neutral",   # last resort — acceptable
        "overdue":          "wrong",     # should not still be overdue
        "suspended":        "neutral",
    },
    "write_off": {
        "written_off":  "correct",
        "paid":         "wrong",        # wrote off but customer paid — lost revenue
        "legal":        "neutral",
        "overdue":      "neutral",
    },
    "on_hold_disputed": {
        "disputed":     "correct",
        "paid":         "correct",
        "overdue":      "neutral",
        "legal":        "neutral",
    },
}


def _classify_outcome(decision: str, actual_status: str, days_elapsed: int) -> str:
    """Classify whether an AI decision led to a good outcome."""
    matrix = OUTCOME_MATRIX.get(decision, {})
    outcome = matrix.get(actual_status, "unknown")

    # Override: if decision was soft/hard follow_up and still overdue after 30 days → definitely wrong
    if outcome == "neutral" and actual_status == "overdue" and days_elapsed >= 30:
        outcome = "wrong"

    return outcome


# ═════════════════════════════════════════════════════════════════════════════
# 📊  FEEDBACK DB FUNCTIONS
# ═════════════════════════════════════════════════════════════════════════════

def _ensure_feedback_tables() -> None:
    try:
        from core.db import get_db
        with get_db() as (conn, cur):
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ai_feedback (
                    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
                    finance_decision_id BIGINT       DEFAULT NULL,
                    invoice_id      INT              NOT NULL,
                    customer_id     INT              DEFAULT NULL,
                    ai_decision     VARCHAR(100)     NOT NULL,
                    ai_risk_score   FLOAT            DEFAULT 0,
                    actual_status   VARCHAR(100)     DEFAULT NULL,
                    outcome         VARCHAR(20)      DEFAULT NULL,
                    days_elapsed    INT              DEFAULT 0,
                    decision_date   DATETIME         DEFAULT NULL,
                    evaluated_at    DATETIME         DEFAULT NULL,
                    notes           TEXT             DEFAULT NULL,
                    INDEX idx_decision   (ai_decision),
                    INDEX idx_outcome    (outcome),
                    INDEX idx_invoice    (invoice_id),
                    INDEX idx_evaluated  (evaluated_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS ai_accuracy_metrics (
                    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
                    metric_date     DATE             NOT NULL,
                    decision_type   VARCHAR(100)     NOT NULL,
                    total_count     INT              DEFAULT 0,
                    correct_count   INT              DEFAULT 0,
                    wrong_count     INT              DEFAULT 0,
                    partial_count   INT              DEFAULT 0,
                    neutral_count   INT              DEFAULT 0,
                    accuracy_pct    FLOAT            DEFAULT 0,
                    avg_risk_score  FLOAT            DEFAULT 0,
                    drift_detected  TINYINT(1)       DEFAULT 0,
                    created_at      DATETIME         DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uq_date_decision (metric_date, decision_type),
                    INDEX idx_date   (metric_date),
                    INDEX idx_drift  (drift_detected)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            conn.commit()
    except Exception as e:
        logger.warning("⚠️ Feedback table init failed: %s", e)


def _get_decisions_to_evaluate(min_days: int = 7) -> list[dict]:
    """Get AI decisions made at least min_days ago, not yet evaluated."""
    try:
        from core.db import get_db
        with get_db() as (_, cur):
            cur.execute(
                """
                SELECT
                    fd.id           AS decision_id,
                    fd.entity_id    AS invoice_id,
                    fd.decision     AS ai_decision,
                    fd.risk_score   AS ai_risk_score,
                    fd.created_at   AS decision_date,
                    i.status        AS current_status,
                    i.customer_id   AS customer_id,
                    DATEDIFF(NOW(), fd.created_at) AS days_elapsed
                FROM finance_decisions fd
                JOIN invoices i ON i.id = fd.entity_id
                WHERE fd.entity = 'invoices'
                  AND fd.created_at <= DATE_SUB(NOW(), INTERVAL %s DAY)
                  AND fd.id NOT IN (
                      SELECT finance_decision_id
                      FROM ai_feedback
                      WHERE finance_decision_id IS NOT NULL
                  )
                ORDER BY fd.created_at ASC
                LIMIT 500
                """,
                (min_days,),
            )
            return cur.fetchall()
    except Exception as e:
        logger.error("❌ _get_decisions_to_evaluate failed: %s", e)
        return []


def _save_feedback(row: dict) -> None:
    try:
        from core.db import get_db
        with get_db() as (conn, cur):
            cur.execute(
                """
                INSERT INTO ai_feedback
                    (finance_decision_id, invoice_id, customer_id,
                     ai_decision, ai_risk_score, actual_status,
                     outcome, days_elapsed, decision_date, evaluated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                ON DUPLICATE KEY UPDATE
                    actual_status = VALUES(actual_status),
                    outcome       = VALUES(outcome),
                    evaluated_at  = NOW()
                """,
                (
                    row["decision_id"],
                    row["invoice_id"],
                    row["customer_id"],
                    row["ai_decision"],
                    float(row["ai_risk_score"] or 0),
                    row["current_status"],
                    row["outcome"],
                    int(row["days_elapsed"] or 0),
                    row["decision_date"],
                ),
            )
            conn.commit()
    except Exception as e:
        logger.warning("⚠️ _save_feedback failed: %s", e)


def _compute_accuracy_metrics(date_str: str) -> list[dict]:
    """Compute daily accuracy per decision type."""
    try:
        from core.db import get_db
        with get_db() as (_, cur):
            cur.execute(
                """
                SELECT
                    ai_decision,
                    COUNT(*)                                                AS total,
                    SUM(CASE WHEN outcome='correct'  THEN 1 ELSE 0 END)    AS correct,
                    SUM(CASE WHEN outcome='wrong'    THEN 1 ELSE 0 END)    AS wrong,
                    SUM(CASE WHEN outcome='partial'  THEN 1 ELSE 0 END)    AS partial,
                    SUM(CASE WHEN outcome='neutral'  THEN 1 ELSE 0 END)    AS neutral,
                    AVG(ai_risk_score)                                      AS avg_risk
                FROM ai_feedback
                WHERE DATE(evaluated_at) = %s
                GROUP BY ai_decision
                """,
                (date_str,),
            )
            return cur.fetchall()
    except Exception as e:
        logger.error("❌ _compute_accuracy_metrics failed: %s", e)
        return []


def _save_accuracy_metrics(date_str: str, metrics: list[dict]) -> None:
    try:
        from core.db import get_db
        with get_db() as (conn, cur):
            for m in metrics:
                total   = int(m["total"] or 0)
                correct = int(m["correct"] or 0)
                wrong   = int(m["wrong"] or 0)
                partial = int(m["partial"] or 0)
                neutral = int(m["neutral"] or 0)

                accuracy = (correct / total * 100) if total > 0 else 0.0

                cur.execute(
                    """
                    INSERT INTO ai_accuracy_metrics
                        (metric_date, decision_type, total_count, correct_count,
                         wrong_count, partial_count, neutral_count,
                         accuracy_pct, avg_risk_score)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON DUPLICATE KEY UPDATE
                        total_count   = VALUES(total_count),
                        correct_count = VALUES(correct_count),
                        wrong_count   = VALUES(wrong_count),
                        partial_count = VALUES(partial_count),
                        neutral_count = VALUES(neutral_count),
                        accuracy_pct  = VALUES(accuracy_pct),
                        avg_risk_score= VALUES(avg_risk_score)
                    """,
                    (date_str, m["ai_decision"], total, correct, wrong, partial, neutral,
                     round(accuracy, 2), float(m["avg_risk"] or 0)),
                )
            conn.commit()
    except Exception as e:
        logger.error("❌ _save_accuracy_metrics failed: %s", e)


def _check_drift(metrics: list[dict]) -> list[dict]:
    """
    Detect model drift: accuracy dropped >15% vs last 7-day avg.
    Returns list of drifting decision types.
    """
    drifting = []
    try:
        from core.db import get_db
        with get_db() as (_, cur):
            for m in metrics:
                decision_type = m["ai_decision"]
                today_acc     = float(m["correct"] or 0) / max(int(m["total"] or 1), 1) * 100

                # Get 7-day average
                cur.execute(
                    """
                    SELECT AVG(accuracy_pct) AS avg_acc
                    FROM ai_accuracy_metrics
                    WHERE decision_type = %s
                      AND metric_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
                    """,
                    (decision_type,),
                )
                row     = cur.fetchone()
                avg_acc = float(row["avg_acc"] or 0) if row else 0

                if avg_acc > 0 and today_acc < avg_acc - 15:
                    drifting.append({
                        "decision_type": decision_type,
                        "today_accuracy": round(today_acc, 1),
                        "avg_7d_accuracy": round(avg_acc, 1),
                        "drop": round(avg_acc - today_acc, 1),
                    })
                    # Flag in DB
                    cur.execute(
                        """
                        UPDATE ai_accuracy_metrics
                        SET drift_detected = 1
                        WHERE decision_type = %s AND metric_date = CURDATE()
                        """,
                        (decision_type,),
                    )
    except Exception as e:
        logger.error("❌ _check_drift failed: %s", e)

    return drifting


# ═════════════════════════════════════════════════════════════════════════════
# ⏰  SCHEDULER JOB
# ═════════════════════════════════════════════════════════════════════════════

async def job_run_feedback_loop() -> None:
    """
    ⏰ Daily feedback loop job.

    Evaluates all AI decisions made 7+ days ago,
    scores them as correct/wrong/partial,
    computes daily accuracy, and detects drift.
    """
    logger.info("🔄 [FeedbackLoop] Starting daily evaluation...")
    _ensure_feedback_tables()

    decisions = _get_decisions_to_evaluate(min_days=7)
    if not decisions:
        logger.info("✅ [FeedbackLoop] No decisions to evaluate.")
        return

    logger.info("🔄 [FeedbackLoop] Evaluating %d decisions...", len(decisions))

    evaluated     = 0
    correct_count = 0
    wrong_count   = 0

    for row in decisions:
        ai_decision    = str(row.get("ai_decision", ""))
        actual_status  = str(row.get("current_status", ""))
        days_elapsed   = int(row.get("days_elapsed") or 0)

        outcome = _classify_outcome(ai_decision, actual_status, days_elapsed)
        row["outcome"] = outcome

        _save_feedback(row)
        evaluated += 1

        if outcome == "correct":
            correct_count += 1
        elif outcome == "wrong":
            wrong_count += 1

    # Compute today's metrics
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    metrics   = _compute_accuracy_metrics(today_str)
    _save_accuracy_metrics(today_str, metrics)

    overall_acc = (correct_count / evaluated * 100) if evaluated > 0 else 0
    logger.info(
        "✅ [FeedbackLoop] Evaluated=%d | Correct=%d | Wrong=%d | Accuracy=%.1f%%",
        evaluated, correct_count, wrong_count, overall_acc,
    )

    # Check for drift
    drifting = _check_drift(metrics)
    if drifting:
        await _send_drift_alert(drifting, overall_acc)
    else:
        logger.info("✅ [FeedbackLoop] No drift detected.")


async def _send_drift_alert(drifting: list[dict], overall_acc: float) -> None:
    """Send drift alert via the monitoring system."""
    try:
        from core.finance_monitor import get_monitor
        monitor = get_monitor()
        for d in drifting:
            await monitor.alert(
                level   = "warning",
                title   = f"Model Drift Detected: {d['decision_type']}",
                message = (
                    f"Accuracy dropped {d['drop']:.1f}% for '{d['decision_type']}'. "
                    f"Today: {d['today_accuracy']}% vs 7-day avg: {d['avg_7d_accuracy']}%"
                ),
                data    = d,
            )
        logger.warning(
            "🚨 [FeedbackLoop] Drift detected in %d decision types! Overall accuracy: %.1f%%",
            len(drifting), overall_acc,
        )
    except Exception as e:
        logger.error("❌ [FeedbackLoop] Drift alert failed: %s", e)


def get_accuracy_summary(days: int = 30) -> dict:
    """Get accuracy summary for the last N days — used by dashboard/API."""
    _ensure_feedback_tables()
    try:
        from core.db import get_db
        with get_db() as (_, cur):
            cur.execute(
                """
                SELECT
                    decision_type,
                    ROUND(AVG(accuracy_pct), 1)     AS avg_accuracy,
                    SUM(total_count)                AS total_evaluated,
                    SUM(correct_count)              AS total_correct,
                    SUM(wrong_count)                AS total_wrong,
                    MAX(drift_detected)             AS drift_ever,
                    MAX(metric_date)                AS last_evaluated
                FROM ai_accuracy_metrics
                WHERE metric_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                GROUP BY decision_type
                ORDER BY avg_accuracy ASC
                """,
                (days,),
            )
            rows = cur.fetchall()

            # Overall
            cur.execute(
                """
                SELECT
                    ROUND(AVG(accuracy_pct), 1) AS overall_accuracy,
                    SUM(total_count)            AS total_evaluated,
                    SUM(drift_detected)         AS total_drift_alerts
                FROM ai_accuracy_metrics
                WHERE metric_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                """,
                (days,),
            )
            overall = cur.fetchone() or {}

            return {
                "period_days":  days,
                "overall":      overall,
                "by_decision":  rows,
                "as_of":        datetime.utcnow().isoformat() + "Z",
            }
    except Exception as e:
        logger.error("❌ get_accuracy_summary failed: %s", e)
        return {"error": str(e)}