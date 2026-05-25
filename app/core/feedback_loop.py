"""
🔄 Finance Feedback Loop — v2.0 Production (MongoDB/Motor)
===========================================================
File: app/core/feedback_loop.py

v2.0 Changes (Migration: MySQL → MongoDB):
    ✅ ai_feedback           → MongoDB collection  (بدل MySQL table)
    ✅ ai_accuracy_metrics   → MongoDB collection  (بدل MySQL table)
    ✅ _get_decisions_to_evaluate() ← Motor aggregation pipeline بدل raw SQL
    ✅ _save_feedback()             ← upsert في MongoDB بدل INSERT ... ON DUPLICATE KEY
    ✅ _compute_accuracy_metrics()  ← aggregation بدل SQL GROUP BY
    ✅ _save_accuracy_metrics()     ← bulk_write (upserts) بدل MySQL INSERT
    ✅ _check_drift()               ← Motor find + aggregation بدل SQL AVG
    ✅ get_accuracy_summary()       ← Motor aggregation بدل SQL GROUP BY
    ✅ كل import لـ core.db اتشال تماماً
    ✅ get_finance_db() singleton من core.mongo_connect

How it works:
    1. Scheduler runs daily
    2. Finds all AI decisions made 7+ days ago
    3. Checks what actually happened (paid? still overdue? legal?)
    4. Calculates accuracy per decision type
    5. Detects model drift (accuracy dropping)
    6. Triggers alert if drift detected

Add to trigger.py:
    from core.feedback_loop import job_run_feedback_loop
    _scheduler.add_job(
        job_run_feedback_loop,
        trigger=CronTrigger(hour=2, minute=0),
        id="feedback_loop",
        name="[Finance] AI Feedback Loop",
        max_instances=1,
    )
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from bson import ObjectId
from pymongo import UpdateOne, ASCENDING, DESCENDING

logger = logging.getLogger(__name__)


# ── DB helper ─────────────────────────────────────────────────────────────────

def _get_db():
    """Return the shared FinanceDB instance (Motor async)."""
    from core.mongo_connect import get_finance_db
    return get_finance_db()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Outcome Rules ─────────────────────────────────────────────────────────────

OUTCOME_MATRIX: dict[str, dict[str, str]] = {
    "safe_to_collect": {
        "paid":        "correct",
        "overdue":     "wrong",
        "legal":       "wrong",
        "written_off": "wrong",
        "partial":     "partial",
    },
    "soft_follow_up": {
        "paid":         "correct",
        "partial":      "partial",
        "overdue":      "wrong",
        "legal":        "wrong",
        "written_off":  "wrong",
        "payment_plan": "partial",
        "suspended":    "neutral",
    },
    "hard_follow_up": {
        "paid":         "correct",
        "payment_plan": "correct",
        "partial":      "partial",
        "legal":        "neutral",
        "suspended":    "neutral",
        "overdue":      "wrong",
        "written_off":  "wrong",
    },
    "payment_plan": {
        "paid":         "correct",
        "payment_plan": "correct",
        "partial":      "partial",
        "overdue":      "wrong",
        "legal":        "wrong",
        "written_off":  "wrong",
    },
    "suspend_service": {
        "paid":         "correct",
        "payment_plan": "correct",
        "legal":        "neutral",
        "suspended":    "neutral",
        "written_off":  "wrong",
        "overdue":      "wrong",
    },
    "legal_escalation": {
        "legal":       "neutral",
        "paid":        "correct",
        "written_off": "neutral",
        "overdue":     "wrong",
        "suspended":   "neutral",
    },
    "write_off": {
        "written_off": "correct",
        "paid":        "wrong",
        "legal":       "neutral",
        "overdue":     "neutral",
    },
    "on_hold_disputed": {
        "disputed": "correct",
        "paid":     "correct",
        "overdue":  "neutral",
        "legal":    "neutral",
    },
}


def _classify_outcome(decision: str, actual_status: str, days_elapsed: int) -> str:
    matrix  = OUTCOME_MATRIX.get(decision, {})
    outcome = matrix.get(actual_status, "unknown")
    if outcome == "neutral" and actual_status == "overdue" and days_elapsed >= 30:
        outcome = "wrong"
    return outcome


# ═════════════════════════════════════════════════════════════════════════════
# 📊  FEEDBACK — MongoDB FUNCTIONS
# ═════════════════════════════════════════════════════════════════════════════

async def _ensure_feedback_indexes() -> None:
    """
    بدل CREATE TABLE IF NOT EXISTS — نعمل indexes على الـ collections.
    آمن تُنادى أكتر من مرة (idempotent).
    """
    try:
        db = _get_db()

        # ai_feedback
        await db.db["ai_feedback"].create_indexes([
            # unique على finance_decision_id عشان نمنع duplicates
            __import__("pymongo").IndexModel(
                [("finance_decision_id", ASCENDING)],
                unique=True, sparse=True,
            ),
            __import__("pymongo").IndexModel([("ai_decision", ASCENDING)]),
            __import__("pymongo").IndexModel([("outcome", ASCENDING)]),
            __import__("pymongo").IndexModel([("invoice_id", ASCENDING)]),
            __import__("pymongo").IndexModel([("evaluated_at", DESCENDING)]),
        ])

        # ai_accuracy_metrics
        await db.db["ai_accuracy_metrics"].create_indexes([
            # unique compound — بدل UNIQUE KEY uq_date_decision
            __import__("pymongo").IndexModel(
                [("metric_date", ASCENDING), ("decision_type", ASCENDING)],
                unique=True,
            ),
            __import__("pymongo").IndexModel([("metric_date", DESCENDING)]),
            __import__("pymongo").IndexModel([("drift_detected", ASCENDING)]),
        ])

        logger.debug("✅ Feedback indexes ready")
    except Exception as e:
        logger.warning("⚠️ Feedback index init failed: %s", e)


async def _get_decisions_to_evaluate(min_days: int = 7) -> list[dict]:
    """
    بدل raw SQL JOIN بين finance_decisions و invoices:
    بنعمل aggregation pipeline على finance_decisions
    ونعمل $lookup على invoices.

    بيرجع decisions اتعملت من >= min_days ومش متقيّمة في ai_feedback.
    """
    try:
        db     = _get_db()
        cutoff = _utcnow() - timedelta(days=min_days)

        # الـ ObjectIds اللي اتقيّموا قبل كده
        evaluated_cursor = db.db["ai_feedback"].find(
            {"finance_decision_id": {"$exists": True, "$ne": None}},
            {"finance_decision_id": 1},
        )
        evaluated_ids = {
            doc["finance_decision_id"]
            async for doc in evaluated_cursor
        }

        pipeline = [
            # فقط decisions على invoices قبل الـ cutoff
            {
                "$match": {
                    "entity":     "invoices",
                    "created_at": {"$lte": cutoff},
                    "_id":        {"$nin": list(evaluated_ids)},
                }
            },
            # $lookup لجيب current invoice status
            {
                "$lookup": {
                    "from":         "invoices",
                    "localField":   "entity_id",
                    "foreignField": "_id",
                    "as":           "_inv",
                }
            },
            {"$unwind": {"path": "$_inv", "preserveNullAndEmptyArrays": True}},
            # نحسب days_elapsed
            {
                "$addFields": {
                    "current_status": "$_inv.status",
                    "customer_id":    "$_inv.customer_id",
                    "days_elapsed": {
                        "$toInt": {
                            "$divide": [
                                {"$subtract": [_utcnow(), "$created_at"]},
                                86_400_000,
                            ]
                        }
                    },
                }
            },
            {"$project": {"_inv": 0}},
            {"$limit": 500},
        ]

        docs = await db.decisions.aggregate(pipeline).to_list(None)
        return docs

    except Exception as e:
        logger.error("❌ _get_decisions_to_evaluate failed: %s", e)
        return []


async def _save_feedback(row: dict) -> None:
    """
    بدل INSERT ... ON DUPLICATE KEY UPDATE:
    نعمل upsert بـ finance_decision_id كـ filter.
    """
    try:
        db = _get_db()

        decision_id = row.get("_id")   # ObjectId of finance_decision doc
        invoice_oid = row.get("entity_id")
        customer_id = row.get("customer_id")

        await db.db["ai_feedback"].update_one(
            {"finance_decision_id": decision_id},
            {
                "$set": {
                    "finance_decision_id": decision_id,
                    "invoice_id":    invoice_oid,
                    "customer_id":   customer_id,
                    "ai_decision":   str(row.get("decision", "")),
                    "ai_risk_score": float(row.get("risk_score") or 0),
                    "actual_status": str(row.get("current_status") or ""),
                    "outcome":       str(row.get("outcome", "")),
                    "days_elapsed":  int(row.get("days_elapsed") or 0),
                    "decision_date": row.get("created_at"),
                    "evaluated_at":  _utcnow(),
                }
            },
            upsert=True,
        )
    except Exception as e:
        logger.warning("⚠️ _save_feedback failed: %s", e)


async def _compute_accuracy_metrics(date_str: str) -> list[dict]:
    """
    بدل SQL GROUP BY على ai_feedback:
    aggregation pipeline يجمّع by ai_decision لليوم المحدد.
    """
    try:
        db = _get_db()

        # نحول date_str لـ datetime range (UTC)
        day_start = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        day_end   = day_start + timedelta(days=1)

        pipeline = [
            {
                "$match": {
                    "evaluated_at": {"$gte": day_start, "$lt": day_end}
                }
            },
            {
                "$group": {
                    "_id":      "$ai_decision",
                    "total":    {"$sum": 1},
                    "correct":  {"$sum": {"$cond": [{"$eq": ["$outcome", "correct"]},  1, 0]}},
                    "wrong":    {"$sum": {"$cond": [{"$eq": ["$outcome", "wrong"]},    1, 0]}},
                    "partial":  {"$sum": {"$cond": [{"$eq": ["$outcome", "partial"]},  1, 0]}},
                    "neutral":  {"$sum": {"$cond": [{"$eq": ["$outcome", "neutral"]},  1, 0]}},
                    "avg_risk": {"$avg": "$ai_risk_score"},
                }
            },
        ]

        docs = await db.db["ai_feedback"].aggregate(pipeline).to_list(None)
        # نضيف ai_decision كـ key واضح
        for d in docs:
            d["ai_decision"] = d.pop("_id", "")
        return docs

    except Exception as e:
        logger.error("❌ _compute_accuracy_metrics failed: %s", e)
        return []


async def _save_accuracy_metrics(date_str: str, metrics: list[dict]) -> None:
    """
    بدل INSERT ... ON DUPLICATE KEY UPDATE:
    bulk_write مع UpdateOne upserts.
    """
    if not metrics:
        return
    try:
        db = _get_db()

        day_start = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)

        ops = []
        for m in metrics:
            total   = int(m.get("total") or 0)
            correct = int(m.get("correct") or 0)
            wrong   = int(m.get("wrong") or 0)
            partial = int(m.get("partial") or 0)
            neutral = int(m.get("neutral") or 0)
            accuracy = round(correct / total * 100, 2) if total > 0 else 0.0

            ops.append(UpdateOne(
                {
                    "metric_date":   day_start,
                    "decision_type": m["ai_decision"],
                },
                {
                    "$set": {
                        "metric_date":   day_start,
                        "decision_type": m["ai_decision"],
                        "total_count":   total,
                        "correct_count": correct,
                        "wrong_count":   wrong,
                        "partial_count": partial,
                        "neutral_count": neutral,
                        "accuracy_pct":  accuracy,
                        "avg_risk_score": round(float(m.get("avg_risk") or 0), 4),
                        # drift_detected يتحدث في _check_drift
                    },
                    "$setOnInsert": {"drift_detected": False, "created_at": _utcnow()},
                },
                upsert=True,
            ))

        if ops:
            await db.db["ai_accuracy_metrics"].bulk_write(ops, ordered=False)

    except Exception as e:
        logger.error("❌ _save_accuracy_metrics failed: %s", e)


async def _check_drift(metrics: list[dict]) -> list[dict]:
    """
    بدل SQL AVG + UPDATE:
    Motor: بنجيب avg من آخر 7 أيام ونقارن بـ today.
    بيرجع list of drifting decision types.
    """
    drifting = []
    try:
        db       = _get_db()
        now      = _utcnow()
        week_ago = now - timedelta(days=7)

        for m in metrics:
            decision_type = m["ai_decision"]
            total_today   = int(m.get("total") or 1)
            correct_today = int(m.get("correct") or 0)
            today_acc     = correct_today / total_today * 100

            # 7-day avg accuracy من ai_accuracy_metrics
            pipeline = [
                {
                    "$match": {
                        "decision_type": decision_type,
                        "metric_date":   {"$gte": week_ago},
                    }
                },
                {
                    "$group": {
                        "_id":     None,
                        "avg_acc": {"$avg": "$accuracy_pct"},
                    }
                },
            ]
            docs    = await db.db["ai_accuracy_metrics"].aggregate(pipeline).to_list(1)
            avg_acc = float(docs[0]["avg_acc"]) if docs else 0.0

            if avg_acc > 0 and today_acc < avg_acc - 15:
                drifting.append({
                    "decision_type":   decision_type,
                    "today_accuracy":  round(today_acc, 1),
                    "avg_7d_accuracy": round(avg_acc, 1),
                    "drop":            round(avg_acc - today_acc, 1),
                })
                # Flag drift في الـ metrics doc
                day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                await db.db["ai_accuracy_metrics"].update_one(
                    {
                        "decision_type": decision_type,
                        "metric_date":   {"$gte": day_start},
                    },
                    {"$set": {"drift_detected": True}},
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
    await _ensure_feedback_indexes()

    decisions = await _get_decisions_to_evaluate(min_days=7)
    if not decisions:
        logger.info("✅ [FeedbackLoop] No decisions to evaluate.")
        return

    logger.info("🔄 [FeedbackLoop] Evaluating %d decisions...", len(decisions))

    evaluated     = 0
    correct_count = 0
    wrong_count   = 0

    for row in decisions:
        ai_decision   = str(row.get("decision", ""))
        actual_status = str(row.get("current_status") or "")
        days_elapsed  = int(row.get("days_elapsed") or 0)

        outcome        = _classify_outcome(ai_decision, actual_status, days_elapsed)
        row["outcome"] = outcome

        await _save_feedback(row)
        evaluated += 1

        if outcome == "correct":
            correct_count += 1
        elif outcome == "wrong":
            wrong_count += 1

    # Compute today's metrics
    today_str = _utcnow().strftime("%Y-%m-%d")
    metrics   = await _compute_accuracy_metrics(today_str)
    await _save_accuracy_metrics(today_str, metrics)

    overall_acc = (correct_count / evaluated * 100) if evaluated > 0 else 0
    logger.info(
        "✅ [FeedbackLoop] Evaluated=%d | Correct=%d | Wrong=%d | Accuracy=%.1f%%",
        evaluated, correct_count, wrong_count, overall_acc,
    )

    # Check for drift
    drifting = await _check_drift(metrics)
    if drifting:
        await _send_drift_alert(drifting, overall_acc)
    else:
        logger.info("✅ [FeedbackLoop] No drift detected.")


async def _send_drift_alert(drifting: list[dict], overall_acc: float) -> None:
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
                data=d,
            )
        logger.warning(
            "🚨 [FeedbackLoop] Drift detected in %d decision types! Overall: %.1f%%",
            len(drifting), overall_acc,
        )
    except Exception as e:
        logger.error("❌ [FeedbackLoop] Drift alert failed: %s", e)


# ═════════════════════════════════════════════════════════════════════════════
# 📊  ACCURACY SUMMARY — for dashboard/API
# ═════════════════════════════════════════════════════════════════════════════

async def get_accuracy_summary(days: int = 30) -> dict:
    """
    بدل SQL GROUP BY على ai_accuracy_metrics:
    Motor aggregation يجيب avg accuracy per decision type.
    """
    await _ensure_feedback_indexes()
    try:
        db     = _get_db()
        since  = _utcnow() - timedelta(days=days)

        # Per-decision breakdown
        pipeline = [
            {"$match": {"metric_date": {"$gte": since}}},
            {
                "$group": {
                    "_id":             "$decision_type",
                    "avg_accuracy":    {"$avg": "$accuracy_pct"},
                    "total_evaluated": {"$sum": "$total_count"},
                    "total_correct":   {"$sum": "$correct_count"},
                    "total_wrong":     {"$sum": "$wrong_count"},
                    "drift_ever":      {"$max": "$drift_detected"},
                    "last_evaluated":  {"$max": "$metric_date"},
                }
            },
            {
                "$project": {
                    "_id":            0,
                    "decision_type":  "$_id",
                    "avg_accuracy":   {"$round": ["$avg_accuracy", 1]},
                    "total_evaluated": 1,
                    "total_correct":   1,
                    "total_wrong":     1,
                    "drift_ever":      1,
                    "last_evaluated":  1,
                }
            },
            {"$sort": {"avg_accuracy": ASCENDING}},
        ]
        by_decision = await db.db["ai_accuracy_metrics"].aggregate(pipeline).to_list(None)

        # Overall summary
        overall_pipeline = [
            {"$match": {"metric_date": {"$gte": since}}},
            {
                "$group": {
                    "_id":               None,
                    "overall_accuracy":  {"$avg": "$accuracy_pct"},
                    "total_evaluated":   {"$sum": "$total_count"},
                    "total_drift_alerts":{"$sum": {"$cond": ["$drift_detected", 1, 0]}},
                }
            },
            {
                "$project": {
                    "_id":               0,
                    "overall_accuracy":  {"$round": ["$overall_accuracy", 1]},
                    "total_evaluated":   1,
                    "total_drift_alerts":1,
                }
            },
        ]
        overall_docs = await db.db["ai_accuracy_metrics"].aggregate(overall_pipeline).to_list(1)
        overall      = overall_docs[0] if overall_docs else {}

        return {
            "period_days": days,
            "overall":     overall,
            "by_decision": by_decision,
            "as_of":       _utcnow().isoformat() + "Z",
        }

    except Exception as e:
        logger.error("❌ get_accuracy_summary failed: %s", e)
        return {"error": str(e)}