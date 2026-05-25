"""
💰 Finance Seed Endpoints — add to main.py
===========================================
File: app/api/routes/finance_seed_routes.py

Endpoints:
    POST /finance/seed          — seed if DB is empty
    POST /finance/seed/reset    — drop + reseed
    GET  /finance/seed/status   — check current data counts
    POST /finance/trigger-agent — manually fire the agent on all overdue invoices

Add to main.py:
    from api.routes.finance_seed_routes import finance_seed_router
    app.include_router(finance_seed_router, prefix="/finance", tags=["💰 Finance - Seed"])
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

finance_seed_router = APIRouter()


# ═════════════════════════════════════════════════════════════════════════════
# 📋  Schemas
# ═════════════════════════════════════════════════════════════════════════════

class SeedConfig(BaseModel):
    customer_count: int  = Field(25, ge=5, le=200, description="Number of customers to generate")
    reset:          bool = Field(False, description="If true, drop existing data first")


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
        "Use reset=true to drop and reseed."
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
        result = await run_seed(reset=config.reset, customer_count=config.customer_count)
        return {
            "status":    "success",
            "result":    result,
            "next_step": "Call POST /finance/trigger-agent to run the AI agent",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except ImportError:
        return await _inline_seed(config.customer_count, config.reset)
    except Exception as e:
        logger.error("Seed failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Seed failed: {e}")


@finance_seed_router.post(
    "/seed/reset",
    tags=["💰 Finance - Seed"],
    summary="🗑️ Reset + reseed finance data",
    description="Drops all finance collections and seeds fresh realistic data.",
)
async def reset_and_seed(
    customer_count: int = Query(25, ge=5, le=200),
):
    """
    🗑️ Full reset — drops invoices, customers, finance_decisions,
    finance_audit, finance_collection_log, legal_cases, then reseeds.
    """
    try:
        from scripts.finance_seed import run_seed
        result = await run_seed(reset=True, customer_count=customer_count)
        return {
            "status":    "reset_and_seeded",
            "result":    result,
            "next_step": "Call POST /finance/trigger-agent to process all overdue invoices",
            "timestamp": datetime.now(timezone.utc).isoformat(),
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
        from core.mongo_connect import get_finance_db
        db = get_finance_db()

        # Customer count
        customer_count = await db.customers.count_documents({})

        # Invoices grouped by status
        pipeline = [
            {"$group": {
                "_id":   "$status",
                "count": {"$sum": 1},
                "total": {"$sum": "$amount"},
            }}
        ]
        invoice_docs = await db.invoices.aggregate(pipeline).to_list(None)
        invoices = {
            d["_id"]: {"count": d["count"], "amount_egp": round(d["total"], 2)}
            for d in invoice_docs
        }

        # AI decisions count
        decisions_count = await db.decisions.count_documents({})

        # Outstanding amount
        outstanding_pipeline = [
            {"$match": {"status": {"$in": ["overdue", "legal", "suspended", "payment_plan"]}}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
        ]
        out_docs = await db.invoices.aggregate(outstanding_pipeline).to_list(1)
        outstanding = round(out_docs[0]["total"], 2) if out_docs else 0.0

        overdue_pending_count = sum(
            v["count"] for k, v in invoices.items()
            if k in ("overdue", "pending")
        )

        return {
            "customers":         customer_count,
            "invoices":          invoices,
            "ai_decisions_made": decisions_count,
            "outstanding_egp":   outstanding,
            "has_data":          customer_count > 0,
            "ready_for_agent":   overdue_pending_count > 0,
            "timestamp":         datetime.now(timezone.utc).isoformat(),
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
    Runs in background — returns immediately.
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
        "note":      "Results will appear in /finance/seed/status",
        "monitor":   "Check server logs for real-time processing",
        "timestamp": datetime.now(timezone.utc).isoformat(),
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
    from core.mongo_connect import get_finance_db
    from models.finance_models import build_customer, build_invoice

    db = get_finance_db()

    if reset:
        await db.customers.drop()
        await db.invoices.drop()
        await db.decisions.drop()
        await db.audit.drop()
        await db.clog.drop()
        await db.legal.drop()
        await db.init_indexes()
        logger.info("🗑️ [InlineSeed] All finance collections dropped and re-indexed")

    NAMES = [
        "Nile Tech Solutions", "Cairo Digital Hub", "AlexDev Co.",
        "Heliopolis Trading", "Giza Manufacturing", "Red Sea Logistics",
        "Sinai Construction", "Delta Retail Group", "Luxor Hospitality",
        "Aswan Real Estate", "Maadi Financial", "Zamalek Media",
        "October Tech Park", "Nasr City Education", "Shubra Food",
    ]
    INDUSTRIES = [
        "technology", "retail", "manufacturing", "construction",
        "hospitality", "real_estate", "transportation", "healthcare",
    ]

    customer_ids = []
    for i, name in enumerate(random.sample(NAMES, min(customer_count, len(NAMES)))):
        doc = build_customer({
            "name":               name,
            "email":              f"contact{i}@{name[:8].lower().replace(' ', '')}.com",
            "industry":           random.choice(INDUSTRIES),
            "credit_score":       random.randint(300, 850),
            "account_age_months": random.randint(3, 60),
            "service_status":     "active",
        })
        result = await db.customers.insert_one(doc)
        customer_ids.append(result.inserted_id)

    invoice_count = 0
    for cid in customer_ids:
        for _ in range(random.randint(1, 3)):
            overdue_days = random.choice([0, 7, 20, 45, 90, 150])
            status = (
                "paid"    if random.random() < 0.15
                else "overdue" if overdue_days > 5
                else "pending"
            )
            due_date = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=overdue_days)
            doc = build_invoice({
                "customer_id": cid,
                "amount":      random.choice([2500, 7500, 15000, 40000, 85000]),
                "due_date":    due_date,
                "status":      status,
            })
            await db.invoices.insert_one(doc)
            invoice_count += 1

    return {
        "seeded":          True,
        "customers":       len(customer_ids),
        "invoices_approx": invoice_count,
        "method":          "inline_fallback",
    }