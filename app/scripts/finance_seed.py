"""
💰 Finance Seed Script — v1.0
================================
File: app/scripts/finance_seed.py

Generates realistic customers + invoices with varied risk scenarios
so the Finance AI Agent has real data to process autonomously.

Scenarios covered:
    🟢 Low risk   — good payers, fresh invoices
    🟡 Medium risk — occasional late, borderline overdue
    🔴 High risk   — chronic late payers, heavily overdue
    ⚫ Critical    — 90+ days, legal territory
    💳 Payment plan candidates — high amount, some history

Usage:
    python scripts/finance_seed.py              # seed only
    python scripts/finance_seed.py --reset      # drop + reseed
    python scripts/finance_seed.py --count 50   # custom count

Also exposed via FastAPI:
    POST /finance/seed
    POST /finance/seed/reset
"""

from __future__ import annotations

import argparse
import logging
import os
import random
import sys
from datetime import datetime, timedelta
from typing import Optional

# ── path fix so we can import core.db ─────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")


# ═════════════════════════════════════════════════════════════════════════════
# 📋  REALISTIC DATA POOLS
# ═════════════════════════════════════════════════════════════════════════════

CUSTOMER_NAMES = [
    "Nile Tech Solutions", "Cairo Digital Hub", "AlexDev Co.",
    "Heliopolis Trading", "Giza Manufacturing", "Red Sea Logistics",
    "Sinai Construction", "Delta Retail Group", "Luxor Hospitality",
    "Aswan Real Estate", "Maadi Financial Services", "Zamalek Media",
    "October Tech Park", "Nasr City Education", "Shubra Food & Beverage",
    "Mansoura Healthcare", "Tanta Industrial", "Asyut Transport",
    "Sohag Government Services", "Port Said Imports",
    "MNT Digital Agency", "Star Electronics", "GreenLeaf Agriculture",
    "BlueSky Aviation", "IronGate Security",
]

INDUSTRIES = [
    "technology", "retail", "manufacturing", "construction", "hospitality",
    "real_estate", "transportation", "healthcare", "education", "government",
    "financial", "food_beverage",
]

# Risk profiles: (credit_score_range, payment_behavior, overdue_range_days)
RISK_PROFILES = {
    "excellent": {
        "credit": (750, 850),
        "paid_ratio": (0.90, 1.00),
        "late_ratio": (0.00, 0.05),
        "overdue_days": (0, 5),
        "account_age_months": (24, 60),
        "weight": 20,
    },
    "good": {
        "credit": (680, 749),
        "paid_ratio": (0.80, 0.92),
        "late_ratio": (0.05, 0.15),
        "overdue_days": (3, 20),
        "account_age_months": (12, 36),
        "weight": 25,
    },
    "medium": {
        "credit": (580, 679),
        "paid_ratio": (0.60, 0.80),
        "late_ratio": (0.15, 0.35),
        "overdue_days": (15, 45),
        "account_age_months": (6, 24),
        "weight": 25,
    },
    "high_risk": {
        "credit": (450, 579),
        "paid_ratio": (0.35, 0.60),
        "late_ratio": (0.35, 0.60),
        "overdue_days": (30, 90),
        "account_age_months": (3, 18),
        "weight": 20,
    },
    "critical": {
        "credit": (300, 449),
        "paid_ratio": (0.10, 0.35),
        "late_ratio": (0.55, 0.90),
        "overdue_days": (90, 200),
        "account_age_months": (1, 12),
        "weight": 10,
    },
}

INVOICE_AMOUNTS_EGP = [
    500, 1200, 2500, 4000, 7500, 10000, 15000,
    25000, 40000, 60000, 85000, 100000,
]

INVOICE_DESCRIPTIONS = [
    "Software license renewal Q{q}",
    "Monthly SaaS subscription",
    "Professional services — project phase {n}",
    "Hardware supply order #{n}",
    "Consulting retainer — {month}",
    "Annual maintenance contract",
    "Implementation services",
    "Training & support package",
    "Custom development — milestone {n}",
    "Infrastructure upgrade",
]


# ═════════════════════════════════════════════════════════════════════════════
# 🏗️  SEED FUNCTIONS
# ═════════════════════════════════════════════════════════════════════════════

def _weighted_profile() -> str:
    """Pick a risk profile using weighted random selection."""
    profiles = list(RISK_PROFILES.keys())
    weights  = [RISK_PROFILES[p]["weight"] for p in profiles]
    return random.choices(profiles, weights=weights, k=1)[0]


def _rand_float(lo: float, hi: float, decimals: int = 2) -> float:
    return round(random.uniform(lo, hi), decimals)


def _rand_date_past(min_days: int, max_days: int) -> datetime:
    delta = random.randint(min_days, max_days)
    return datetime.utcnow() - timedelta(days=delta)


def _ensure_customers_table(cur, conn) -> None:
    """Create customers table if it doesn't exist."""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id                  INT AUTO_INCREMENT PRIMARY KEY,
            name                VARCHAR(200) NOT NULL,
            email               VARCHAR(200),
            phone               VARCHAR(50),
            industry            VARCHAR(100) DEFAULT 'unknown',
            credit_score        FLOAT        DEFAULT 650,
            account_age_months  INT          DEFAULT 12,
            service_status      VARCHAR(50)  DEFAULT 'active',
            is_blacklisted      TINYINT(1)   DEFAULT 0,
            suspension_reason   VARCHAR(200),
            suspended_at        DATETIME,
            blacklisted_at      DATETIME,
            created_at          DATETIME     DEFAULT CURRENT_TIMESTAMP,
            updated_at          DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    conn.commit()


def _ensure_invoices_table(cur, conn) -> None:
    """Create invoices table if it doesn't exist (with all AI columns)."""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id                  INT AUTO_INCREMENT PRIMARY KEY,
            customer_id         INT          NOT NULL,
            amount              DECIMAL(12,2) NOT NULL,
            due_date            DATETIME,
            status              VARCHAR(50)  DEFAULT 'pending',
            description         TEXT,
            overdue_days        INT          DEFAULT 0,
            ai_decision         VARCHAR(100),
            ai_risk_score       FLOAT        DEFAULT 0,
            ai_decision_reason  TEXT,
            ai_action_plan      TEXT,
            collection_strategy VARCHAR(50)  DEFAULT 'standard',
            first_reminder_days INT          DEFAULT 7,
            ai_request_id       VARCHAR(100),
            paid_at             DATETIME,
            written_off_at      DATETIME,
            created_at          DATETIME     DEFAULT CURRENT_TIMESTAMP,
            updated_at          DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_customer (customer_id),
            INDEX idx_status   (status),
            INDEX idx_due_date (due_date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    conn.commit()


def seed_customers(cur, conn, count: int = 25) -> list[int]:
    """Insert realistic customers. Returns list of inserted IDs."""
    inserted_ids = []

    used_names = random.sample(CUSTOMER_NAMES, min(count, len(CUSTOMER_NAMES)))
    # If count > pool, generate extra names
    extra = count - len(used_names)
    for i in range(extra):
        used_names.append(f"Company {random.randint(100, 999)} Ltd")

    for i, name in enumerate(used_names[:count]):
        profile_key = _weighted_profile()
        profile     = RISK_PROFILES[profile_key]
        industry    = random.choice(INDUSTRIES)
        credit      = random.randint(*profile["credit"])
        age_months  = random.randint(*profile["account_age_months"])
        email       = name.lower().replace(" ", "").replace(".", "")[:20] + f"{i}@example.com"
        phone       = f"+20 1{random.randint(0,2)}{random.randint(10000000, 99999999)}"

        cur.execute("""
            INSERT INTO customers
                (name, email, phone, industry, credit_score,
                 account_age_months, service_status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, 'active', NOW())
        """, (name, email, phone, industry, credit, age_months))

        inserted_ids.append(cur.lastrowid)

    conn.commit()
    logger.info("✅ Seeded %d customers", len(inserted_ids))
    return inserted_ids


def seed_invoices(cur, conn, customer_ids: list[int], invoices_per_customer: int = 3) -> int:
    """
    Insert invoices for each customer.
    Each customer gets 1-4 invoices across different statuses.
    Returns count of inserted invoices.
    """
    total = 0

    for cid in customer_ids:
        # Get customer's credit score to align invoice risk
        cur.execute("SELECT credit_score, industry FROM customers WHERE id = %s", (cid,))
        customer = cur.fetchone()
        if not customer:
            continue

        credit = float(customer.get("credit_score", 650) if isinstance(customer, dict) else customer[0])
        n_invoices = random.randint(1, invoices_per_customer)

        for j in range(n_invoices):
            amount      = random.choice(INVOICE_AMOUNTS_EGP)
            desc_tpl    = random.choice(INVOICE_DESCRIPTIONS)
            description = desc_tpl.format(q=random.randint(1,4), n=j+1, month=datetime.utcnow().strftime("%B"))

            # Determine overdue days based on credit score
            if credit >= 700:
                overdue_days = random.randint(0, 15)
            elif credit >= 580:
                overdue_days = random.randint(5, 45)
            elif credit >= 450:
                overdue_days = random.randint(20, 90)
            else:
                overdue_days = random.randint(60, 180)

            # Determine invoice status
            if overdue_days == 0:
                status   = "pending"
                due_date = datetime.utcnow() + timedelta(days=random.randint(1, 30))
            elif overdue_days <= 10:
                status   = random.choice(["pending", "overdue"])
                due_date = datetime.utcnow() - timedelta(days=overdue_days)
            elif overdue_days <= 44:
                status   = "overdue"
                due_date = datetime.utcnow() - timedelta(days=overdue_days)
            elif overdue_days <= 90:
                status   = random.choice(["overdue", "suspended"])
                due_date = datetime.utcnow() - timedelta(days=overdue_days)
            else:
                status   = random.choice(["overdue", "legal", "suspended"])
                due_date = datetime.utcnow() - timedelta(days=overdue_days)

            # Some invoices already paid (for feedback loop realism)
            if random.random() < 0.15:
                status   = "paid"
                due_date = datetime.utcnow() - timedelta(days=random.randint(1, 60))

            created_at = due_date - timedelta(days=random.randint(14, 45))

            cur.execute("""
                INSERT INTO invoices
                    (customer_id, amount, due_date, status,
                     description, overdue_days, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (cid, amount, due_date, status, description,
                  max(0, overdue_days), created_at))
            total += 1

    conn.commit()
    logger.info("✅ Seeded %d invoices across %d customers", total, len(customer_ids))
    return total


def _get_stats(cur) -> dict:
    """Return quick stats after seeding."""
    cur.execute("SELECT COUNT(*) as c FROM customers")
    row = cur.fetchone()
    customers = row["c"] if isinstance(row, dict) else row[0]

    cur.execute("SELECT status, COUNT(*) as c FROM invoices GROUP BY status")
    rows = cur.fetchall()
    invoice_stats = {}
    for r in rows:
        if isinstance(r, dict):
            invoice_stats[r["status"]] = r["c"]
        else:
            invoice_stats[r[0]] = r[1]

    cur.execute("SELECT SUM(amount) as t FROM invoices WHERE status IN ('overdue','legal','suspended')")
    row = cur.fetchone()
    outstanding = float(row["t"] or 0) if isinstance(row, dict) else float(row[0] or 0)

    return {
        "customers":   customers,
        "invoices":    invoice_stats,
        "outstanding_egp": outstanding,
    }


# ═════════════════════════════════════════════════════════════════════════════
# 🚀  MAIN ENTRY POINTS
# ═════════════════════════════════════════════════════════════════════════════

def run_seed(reset: bool = False, customer_count: int = 25) -> dict:
    """
    Main seed function — callable from script OR FastAPI endpoint.

    Args:
        reset: if True, truncate existing data first
        customer_count: how many customers to generate

    Returns:
        stats dict
    """
    from core.db import get_db, init_db_pool
    from core.finance_db import init_finance_db

    # Initialize DB pool (required when running as a standalone script)
    init_db_pool()

    # Ensure all finance tables exist
    init_finance_db()

    with get_db() as (conn, cur):
        # Ensure base tables exist
        _ensure_customers_table(cur, conn)
        _ensure_invoices_table(cur, conn)

        if reset:
            logger.info("🗑️  Resetting finance data...")
            cur.execute("SET FOREIGN_KEY_CHECKS = 0")
            for tbl in ["finance_collection_log", "finance_audit",
                        "finance_decisions", "invoices", "customers"]:
                try:
                    cur.execute(f"TRUNCATE TABLE {tbl}")
                    logger.info("   Truncated: %s", tbl)
                except Exception as e:
                    logger.warning("   Could not truncate %s: %s", tbl, e)
            cur.execute("SET FOREIGN_KEY_CHECKS = 1")
            conn.commit()
            logger.info("✅ Reset complete")

        # Check if already seeded
        if not reset:
            cur.execute("SELECT COUNT(*) as c FROM customers")
            row = cur.fetchone()
            existing = row["c"] if isinstance(row, dict) else row[0]
            if existing > 5:
                logger.info("ℹ️  Already have %d customers — skipping seed (use reset=True to override)", existing)
                return {"skipped": True, "reason": f"Already {existing} customers", **_get_stats(cur)}

        logger.info("🌱 Seeding finance data — %d customers...", customer_count)
        customer_ids = seed_customers(cur, conn, count=customer_count)
        invoice_count = seed_invoices(cur, conn, customer_ids, invoices_per_customer=3)

        stats = _get_stats(cur)
        logger.info(
            "✅ Seed complete | customers=%d | invoices=%s | outstanding=%.0f EGP",
            stats["customers"], stats["invoices"], stats["outstanding_egp"],
        )
        return {"seeded": True, **stats}


# ── CLI entry point ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Finance Seed Script")
    parser.add_argument("--reset",  action="store_true", help="Truncate existing data first")
    parser.add_argument("--count",  type=int, default=25, help="Number of customers to seed")
    args = parser.parse_args()

    result = run_seed(reset=args.reset, customer_count=args.count)
    print("\n📊 Seed Result:")
    import json
    print(json.dumps(result, indent=2, default=str))