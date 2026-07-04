"""
🌱 Finance Database Seeder — v2.0 (MongoDB)
============================================
Run: python finance_seeder.py

Creates:
    ✅ 10 customers  (mix of risk levels)
    ✅ 30+ invoices  (overdue, pending, paid — different stages)

After seeding:
    - Scheduler يلاقي invoices ويشغّل الـ AI Agent تلقائيًا
    - أو شغّل يدوي: POST /finance/trigger-agent
"""

import asyncio
import os
import random
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()


# ── Sample Data ───────────────────────────────────────────────────────────────

CUSTOMERS = [
    # (name, industry, credit_score, risk_level)
    ("ACME Corporation",     "manufacturing", 750, "low"),
    ("Delta Trading Co.",    "retail",        620, "medium"),
    ("Nile Construction",    "construction",  480, "high"),
    ("TechVision Egypt",     "technology",    820, "low"),
    ("Cairo Hospitality",    "hospitality",   540, "high"),
    ("Pharma Plus",          "healthcare",    780, "low"),
    ("Real Estate Masters",  "real_estate",   510, "high"),
    ("Food & Bev Solutions", "food_beverage", 640, "medium"),
    ("GovServices Ltd",      "government",    890, "low"),
    ("Transport Network",    "transportation",560, "medium"),
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _due_date(overdue_days: int) -> datetime:
    return _utcnow() - timedelta(days=overdue_days)


def _amount(risk: str) -> float:
    if risk == "high":   return round(random.uniform(5000,  80000), 2)
    if risk == "medium": return round(random.uniform(2000,  30000), 2)
    return round(random.uniform(500, 15000), 2)


# ── Seeder Functions ──────────────────────────────────────────────────────────

async def seed_customers(db) -> list:
    """Insert CUSTOMERS list → returns list of inserted ObjectIds."""
    print("👤 Seeding customers...")
    from models.finance_models import build_customer

    ids = []
    for name, industry, credit_score, _ in CUSTOMERS:
        doc = build_customer({
            "name":               name,
            "email":              f"contact@{name[:8].lower().replace(' ', '')}.com",
            "phone":              f"+20{random.randint(1000000000, 1999999999)}",
            "industry":           industry,
            "credit_score":       credit_score,
            "account_age_months": random.randint(6, 60),
            "service_status":     "active",
        })
        result = await db.customers.insert_one(doc)
        ids.append(result.inserted_id)
        print(f"   ✅ Customer: {name} (id={result.inserted_id})")
    return ids


async def seed_invoices(db, customer_ids: list) -> int:
    """Insert invoices with varied overdue scenarios."""
    print("\n🧾 Seeding invoices...")
    from models.finance_models import build_invoice

    base_scenarios = [
        # (overdue_days, status, label)
        (0,   "pending", "🆕 New invoice — needs risk assessment"),
        (3,   "pending", "🆕 Very new — 3 days"),
        (8,   "overdue", "⚠️ Slightly overdue — 8 days"),
    ]

    heavy_scenarios = [
        # (overdue_days, status, is_disputed)
        (15,  "overdue", False),
        (35,  "overdue", False),
        (50,  "overdue", False),
        (95,  "overdue", False),
        (185, "overdue", False),
        (30,  "overdue", True),
        (0,   "paid",    False),
    ]

    count = 0

    for cid, (_, _, _, risk) in zip(customer_ids, CUSTOMERS):
        # Base scenarios for every customer
        for overdue_days, status, label in base_scenarios:
            doc = build_invoice({
                "customer_id": cid,
                "amount":      _amount(risk),
                "due_date":    _due_date(overdue_days),
                "status":      status,
            })
            result = await db.invoices.insert_one(doc)
            count += 1
            print(f"   ✅ Invoice {result.inserted_id} | {label} | risk={risk}")

        # Extra heavy scenarios for high-risk only
        if risk == "high":
            for overdue_days, status, is_disputed in heavy_scenarios:
                doc = build_invoice({
                    "customer_id": cid,
                    "amount":      _amount(risk),
                    "due_date":    _due_date(overdue_days),
                    "status":      "disputed" if is_disputed else status,
                })
                result = await db.invoices.insert_one(doc)
                count += 1
                print(f"   🔴 Heavy {result.inserted_id} | {overdue_days}d | disputed={is_disputed}")

    print(f"\n   📊 Total invoices created: {count}")
    return count


def print_summary(customer_count: int, invoice_count: int) -> None:
    print("\n" + "═" * 55)
    print("  📊 Seeding Summary")
    print("═" * 55)
    print(f"  👤 Customers  : {customer_count}")
    print(f"  🧾 Invoices   : {invoice_count}")
    print("═" * 55)
    print("\n  ✅ Seeding complete!")
    print("\n  Next steps:")
    print("  1. Start the server:  uvicorn main:app --port 9000 --reload")
    print("  2. Trigger manually:  POST /finance/trigger-agent")
    print("  3. Or wait 5 min for scheduler to run automatically")
    print("  4. Check results:     GET  /finance/seed/status")
    print()


async def main(reset: bool = False, customer_count: int = 10):
    print("🌱 Finance Database Seeder v2.0 (MongoDB)")
    print("=" * 55)

    from core.node_finance_proxy import get_finance_db
    await ensure_mongo_ready()
    db = get_finance_db()

    if reset:
        print("🗑️  Dropping existing finance collections...")
        await db.customers.drop()
        await db.invoices.drop()
        await db.decisions.drop()
        await db.audit.drop()
        await db.clog.drop()
        await db.legal.drop()
        await db.init_indexes()
        print("   ✅ Collections dropped and re-indexed\n")

    # Check if already seeded
    existing = await db.customers.count_documents({})
    if existing > 0 and not reset:
        print(f"⚠️  Already seeded ({existing} customers found). Use reset=True to reseed.")
        return

    customer_ids = await seed_customers(db)
    invoice_count = await seed_invoices(db, customer_ids[:customer_count])
    print_summary(len(customer_ids[:customer_count]), invoice_count)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Finance MongoDB Seeder")
    parser.add_argument("--reset",          action="store_true", help="Drop and reseed")
    parser.add_argument("--customers", "-n", type=int, default=10, help="Number of customers")
    args = parser.parse_args()
    asyncio.run(main(reset=args.reset, customer_count=args.customers))
