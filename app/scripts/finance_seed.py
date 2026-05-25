"""
🌱 Finance Seed Script — v2.0 (MongoDB)
=========================================
File: app/scripts/finance_seed.py

Used by:
    - finance_seed_routes.py  → POST /finance/seed
    - finance_seeder.py       → python finance_seeder.py

run_seed() is async — awaitable from FastAPI routes.
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)


# ── Risk profiles ─────────────────────────────────────────────────────────────

_RISK_PROFILES = [
    # (weight, credit_range, overdue_day_choices, label)
    (0.20, (750, 850), [0, 0, 3, 5],              "excellent"),
    (0.25, (680, 749), [0, 5, 8, 15],             "good"),
    (0.25, (580, 679), [8, 15, 22, 35],            "medium"),
    (0.20, (450, 579), [30, 45, 60, 75],           "high"),
    (0.10, (300, 449), [90, 120, 150, 185, 200],   "critical"),
]

_INDUSTRIES = [
    "technology", "retail", "manufacturing", "construction",
    "hospitality", "real_estate", "transportation", "healthcare",
    "food_beverage", "government",
]

_NAME_POOL = [
    "Nile Tech Solutions", "Cairo Digital Hub", "AlexDev Co.",
    "Heliopolis Trading", "Giza Manufacturing", "Red Sea Logistics",
    "Sinai Construction", "Delta Retail Group", "Luxor Hospitality",
    "Aswan Real Estate", "Maadi Financial", "Zamalek Media",
    "October Tech Park", "Nasr City Education", "Shubra Food Co.",
    "Mohandessin Motors", "Dokki Pharma", "Agouza Real Estate",
    "Imbaba Retail", "Sohag Agriculture", "Mansoura Textiles",
    "Tanta Industries", "Ismailia Shipping", "Damietta Furniture",
    "Suez Energy Group",
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _pick_profile() -> dict:
    weights   = [p[0] for p in _RISK_PROFILES]
    profile   = random.choices(_RISK_PROFILES, weights=weights, k=1)[0]
    _, credit_range, overdue_choices, label = profile[1], profile[1], profile[2], profile[3]
    return {
        "credit_score":   random.randint(*profile[1]),
        "overdue_choices": profile[2],
        "risk_label":     profile[3],
    }


def _amount_for_risk(label: str) -> float:
    ranges = {
        "excellent": (500,   10_000),
        "good":      (2_000, 30_000),
        "medium":    (5_000, 50_000),
        "high":      (10_000, 80_000),
        "critical":  (20_000, 150_000),
    }
    lo, hi = ranges.get(label, (1_000, 20_000))
    return round(random.uniform(lo, hi), 2)


def _status_for_overdue(overdue_days: int, risk_label: str) -> str:
    if overdue_days == 0:
        return "paid" if random.random() < 0.25 else "pending"
    if overdue_days >= 180:
        return "overdue"   # write-off candidate
    if overdue_days >= 90:
        return "overdue"   # legal candidate
    if overdue_days >= 45 and risk_label in ("high", "critical"):
        return "suspended" if random.random() < 0.3 else "overdue"
    return "overdue"


# ═════════════════════════════════════════════════════════════════════════════
# 🌱  run_seed  — main entry point
# ═════════════════════════════════════════════════════════════════════════════

async def run_seed(
    reset:          bool = False,
    customer_count: int  = 25,
) -> dict:
    """
    Seed MongoDB with realistic finance test data.

    Args:
        reset:          Drop all collections before seeding.
        customer_count: How many customers to create.

    Returns:
        Summary dict with counts.
    """
    from core.mongo_connect import get_finance_db
    from models.finance_models import build_customer, build_invoice

    db = get_finance_db()

    # ── Optional reset ────────────────────────────────────────────────────────
    if reset:
        logger.info("🗑️ [FinanceSeed] Dropping all finance collections...")
        await db.customers.drop()
        await db.invoices.drop()
        await db.decisions.drop()
        await db.audit.drop()
        await db.clog.drop()
        await db.legal.drop()
        await db.init_indexes()
        logger.info("✅ [FinanceSeed] Collections dropped and re-indexed")

    # ── Skip if already seeded ────────────────────────────────────────────────
    existing = await db.customers.count_documents({})
    if existing > 0 and not reset:
        logger.info("⚠️ [FinanceSeed] Already seeded (%d customers). Skipping.", existing)
        return {
            "skipped":          True,
            "existing_customers": existing,
            "reason":           "Data already present. Use reset=True to reseed.",
        }

    # ── Seed customers ────────────────────────────────────────────────────────
    names    = random.sample(_NAME_POOL, min(customer_count, len(_NAME_POOL)))
    profiles = [_pick_profile() for _ in names]

    customer_ids   = []
    customer_risks = []

    for i, (name, profile) in enumerate(zip(names, profiles)):
        doc = build_customer({
            "name":               name,
            "email":              f"billing{i}@{name[:6].lower().replace(' ', '')}.com",
            "phone":              f"+20{random.randint(1_000_000_000, 1_999_999_999)}",
            "industry":           random.choice(_INDUSTRIES),
            "credit_score":       profile["credit_score"],
            "account_age_months": random.randint(3, 72),
            "service_status":     "active",
        })
        result = await db.customers.insert_one(doc)
        customer_ids.append(result.inserted_id)
        customer_risks.append(profile)

    logger.info("👤 [FinanceSeed] %d customers created", len(customer_ids))

    # ── Seed invoices ─────────────────────────────────────────────────────────
    invoice_count  = 0
    status_summary: dict[str, int] = {}

    for cid, profile in zip(customer_ids, customer_risks):
        risk_label      = profile["risk_label"]
        overdue_choices = profile["overdue_choices"]
        num_invoices    = random.randint(1, 4)

        for _ in range(num_invoices):
            overdue_days = random.choice(overdue_choices)
            status       = _status_for_overdue(overdue_days, risk_label)
            due_date     = _utcnow() - timedelta(days=overdue_days)
            is_disputed  = (
                risk_label in ("high", "critical")
                and random.random() < 0.10
            )
            if is_disputed:
                status = "disputed"

            doc = build_invoice({
                "customer_id": cid,
                "amount":      _amount_for_risk(risk_label),
                "due_date":    due_date,
                "status":      status,
                "description": f"Invoice — {risk_label} risk customer",
            })
            await db.invoices.insert_one(doc)
            invoice_count += 1
            status_summary[status] = status_summary.get(status, 0) + 1

    logger.info(
        "🧾 [FinanceSeed] %d invoices created | breakdown: %s",
        invoice_count, status_summary,
    )

    return {
        "seeded":          True,
        "customers":       len(customer_ids),
        "invoices":        invoice_count,
        "status_breakdown": status_summary,
        "timestamp":       _utcnow().isoformat(),
    }