"""
💰 Finance Seed Endpoints — add to main.py
===========================================
File: app/api/routes/finance_seed_routes.py

Endpoints:
    POST /finance/seed          — seed if DB is empty
    POST /finance/seed/reset    — truncate + reseed
    GET  /finance/seed/status   — check current data counts
    POST /finance/trigger-agent — manually fire the agent on all overdue invoices

Add to main.py:
    from api.routes.finance_seed_routes import finance_seed_router
    app.include_router(finance_seed_router, prefix="/finance", tags=["💰 Finance - Seed"])
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

finance_seed_router = APIRouter()


# ═════════════════════════════════════════════════════════════════════════════
# 📋  Schemas
# ═════════════════════════════════════════════════════════════════════════════

class SeedConfig(BaseModel):
    customer_count: int   = Field(25, ge=5, le=200, description="Number of customers to generate")
    reset:          bool  = Field(False, description="If true, truncate existing data first")


# ═════════════════════════════════════════════════════════════════════════════
# 🌱  SEED ENDPOINTS
# ═════════════════════════════════════════════════════════════════════════════

@finance_seed_router.post(
    "/seed",
    tags=["💰 Finance - Seed"],
    summary="🌱 Seed finance test data",
    description=(
        "Generates realistic customers + invoices with varied risk profiles. "
        "Safe to call multiple times — skips if data already exists. "
        "Use reset=true to truncate and reseed."
    ),
)
async def seed_finance_data(config: SeedConfig = SeedConfig()):
    """
    🌱 Seed realistic finance data for the AI agent to process.

    Risk distribution:
        🟢 20% Excellent — credit 750-850, minimal overdue
        🟡 25% Good      — credit 680-749, occasional late
        🟡 25% Medium    — credit 580-679, 15-45 days overdue
        🔴 20% High risk — credit 450-579, 30-90 days overdue
        ⚫ 10% Critical  — credit 300-449, 90-200 days overdue
    """
    try:
        from scripts.finance_seed import run_seed
        result = run_seed(reset=config.reset, customer_count=config.customer_count)
        return {
            "status":    "success",
            "result":    result,
            "next_step": "Call POST /trigger/run-now/overdue-invoices to run the AI agent",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except ImportError:
        # Fallback: run inline if scripts/ not in path
        return await _inline_seed(config.customer_count, config.reset)
    except Exception as e:
        logger.error("Seed failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Seed failed: {e}")


@finance_seed_router.post(
    "/seed/reset",
    tags=["💰 Finance - Seed"],
    summary="🗑️ Reset + reseed finance data",
    description="Truncates all finance data and seeds fresh realistic data.",
)
async def reset_and_seed(
    customer_count: int = Query(25, ge=5, le=200),
):
    """
    🗑️ Full reset — truncates invoices, customers, finance_decisions,
    finance_audit, finance_collection_log, then reseeds.
    """
    try:
        from scripts.finance_seed import run_seed
        result = run_seed(reset=True, customer_count=customer_count)
        return {
            "status":    "reset_and_seeded",
            "result":    result,
            "next_step": "Call POST /trigger/run-now/overdue-invoices to process all overdue invoices",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except ImportError:
        return await _inline_seed(customer_count, reset=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reset failed: {e}")


@finance_seed_router.get(
    "/seed/status",
    tags=["💰 Finance - Seed"],
    summary="📊 Check current finance data state",
)
async def finance_data_status():
    """
    📊 Returns current counts of customers, invoices by status,
    AI decisions made, and outstanding amount.
    """
    try:
        from core.db import get_db
        with get_db() as (_, cur):

            # Customers
            cur.execute("SELECT COUNT(*) as c FROM customers")
            r = cur.fetchone()
            customer_count = r["c"] if isinstance(r, dict) else r[0]

            # Invoices by status
            cur.execute("SELECT status, COUNT(*) as c, SUM(amount) as total FROM invoices GROUP BY status")
            invoice_rows = cur.fetchall()
            invoices = {}
            for row in invoice_rows:
                if isinstance(row, dict):
                    invoices[row["status"]] = {"count": row["c"], "amount_egp": float(row["total"] or 0)}
                else:
                    invoices[row[0]] = {"count": row[1], "amount_egp": float(row[2] or 0)}

            # AI decisions
            cur.execute("SELECT COUNT(*) as c FROM finance_decisions")
            r = cur.fetchone()
            decisions_count = (r["c"] if isinstance(r, dict) else r[0]) if r else 0

            # Outstanding
            cur.execute("""
                SELECT SUM(amount) as t FROM invoices
                WHERE status IN ('overdue','legal','suspended','payment_plan')
            """)
            r = cur.fetchone()
            outstanding = float((r["c"] if isinstance(r, dict) else r[0]) or 0) if r else 0

            return {
                "customers":        customer_count,
                "invoices":         invoices,
                "ai_decisions_made": decisions_count,
                "outstanding_egp":  outstanding,
                "has_data":         customer_count > 0,
                "ready_for_agent":  sum(
                    v["count"] for k, v in invoices.items()
                    if k in ("overdue", "pending")
                ) > 0,
                "timestamp":        datetime.utcnow().isoformat() + "Z",
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@finance_seed_router.post(
    "/trigger-agent",
    tags=["💰 Finance - Seed"],
    summary="🤖 Fire AI agent on all overdue invoices",
    description=(
        "Manually triggers the Finance AI Agent to process ALL overdue invoices right now. "
        "Normally this runs automatically every 5 minutes via the scheduler."
    ),
)
async def trigger_finance_agent(background_tasks: BackgroundTasks):
    """
    🤖 Fire the Finance Agent immediately on all overdue invoices.
    Runs in background — returns immediately with a job ID.
    """
    from core.finance_trigger import job_scan_overdue_invoices, job_scan_new_invoices

    async def _run():
        logger.info("🤖 [Manual Trigger] Running finance agent on all overdue invoices...")
        await job_scan_overdue_invoices()
        await job_scan_new_invoices()
        logger.info("✅ [Manual Trigger] Finance agent run complete")

    background_tasks.add_task(_run)

    return {
        "status":    "triggered",
        "message":   "Finance AI agent fired on all overdue invoices",
        "note":      "Results will appear in /finance/model/info and /finance/seed/status",
        "monitor":   "Check server logs for real-time processing",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


# ═════════════════════════════════════════════════════════════════════════════
# 🔧  INLINE SEED FALLBACK (no scripts/ import needed)
# ═════════════════════════════════════════════════════════════════════════════

async def _inline_seed(customer_count: int = 25, reset: bool = False) -> dict:
    """
    Inline seed — runs directly without the scripts/ module.
    Used when the main seed script can't be imported.
    """
    import random
    from datetime import timedelta
    from core.db import get_db
    from core.finance_db import init_finance_db

    init_finance_db()

    NAMES = [
        "Nile Tech Solutions", "Cairo Digital Hub", "AlexDev Co.",
        "Heliopolis Trading", "Giza Manufacturing", "Red Sea Logistics",
        "Sinai Construction", "Delta Retail Group", "Luxor Hospitality",
        "Aswan Real Estate", "Maadi Financial", "Zamalek Media",
        "October Tech Park", "Nasr City Education", "Shubra Food",
    ]
    INDUSTRIES = ["technology","retail","manufacturing","construction",
                  "hospitality","real_estate","transportation","healthcare"]

    with get_db() as (conn, cur):
        if reset:
            cur.execute("SET FOREIGN_KEY_CHECKS=0")
            for tbl in ["finance_collection_log","finance_audit",
                        "finance_decisions","invoices","customers"]:
                try:
                    cur.execute(f"TRUNCATE TABLE {tbl}")
                except Exception:
                    pass
            cur.execute("SET FOREIGN_KEY_CHECKS=1")
            conn.commit()

        customer_ids = []
        for i, name in enumerate(random.sample(NAMES, min(customer_count, len(NAMES)))):
            credit = random.randint(300, 850)
            cur.execute(
                "INSERT INTO customers (name,email,industry,credit_score,account_age_months) "
                "VALUES (%s,%s,%s,%s,%s)",
                (name, f"contact{i}@{name[:8].lower().replace(' ','')}.com",
                 random.choice(INDUSTRIES), credit, random.randint(3, 60)),
            )
            customer_ids.append(cur.lastrowid)
        conn.commit()

        invoice_count = 0
        for cid in customer_ids:
            for _ in range(random.randint(1, 3)):
                overdue = random.choice([0, 7, 20, 45, 90, 150])
                status  = ("paid" if random.random() < 0.15
                           else "overdue" if overdue > 5 else "pending")
                due_date = datetime.utcnow() - timedelta(days=overdue)
                cur.execute(
                    "INSERT INTO invoices (customer_id,amount,due_date,status,overdue_days) "
                    "VALUES (%s,%s,%s,%s,%s)",
                    (cid, random.choice([2500,7500,15000,40000,85000]),
                     due_date, status, max(0, overdue)),
                )
                invoice_count += 1
        conn.commit()

    return {
        "seeded":         True,
        "customers":      len(customer_ids),
        "invoices_approx": invoice_count,
        "method":         "inline_fallback",
    }