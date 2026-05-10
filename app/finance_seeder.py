"""
🌱 Finance Database Seeder — v1.0
===================================
Run: python finance_seeder.py

Creates:
    ✅ 10 customers  (mix of risk levels)
    ✅ 30 invoices   (overdue, pending, paid — different stages)
    ✅ Payment history per customer

After seeding:
    - Scheduler يلاقي invoices ويشغّل الـ AI Agent تلقائيًا
    - أو شغّل يدوي: POST /trigger/run-now/overdue-invoices
"""

import os
import sys
import random
from datetime import datetime, timedelta, date

# ── Add project root to path ──────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from core.db import get_db


# ── Sample Data ───────────────────────────────────────────────────────────────

CUSTOMERS = [
    # (name, industry, credit_score, risk_level)
    ("ACME Corporation",       "manufacturing",  750, "low"),
    ("Delta Trading Co.",      "retail",         620, "medium"),
    ("Nile Construction",      "construction",   480, "high"),
    ("TechVision Egypt",       "technology",     820, "low"),
    ("Cairo Hospitality",      "hospitality",    540, "high"),
    ("Pharma Plus",            "healthcare",     780, "low"),
    ("Real Estate Masters",    "real_estate",    510, "high"),
    ("Food & Bev Solutions",   "food_beverage",  640, "medium"),
    ("GovServices Ltd",        "government",     890, "low"),
    ("Transport Network",      "transportation", 560, "medium"),
]

def random_due_date(overdue_days: int) -> date:
    """Returns a due date that makes the invoice overdue by N days."""
    return date.today() - timedelta(days=overdue_days)

def random_amount(risk: str) -> float:
    if risk == "high":   return round(random.uniform(5000, 80000), 2)
    if risk == "medium": return round(random.uniform(2000, 30000), 2)
    return round(random.uniform(500, 15000), 2)


def seed_customers(conn, cur) -> list[int]:
    """Insert customers — returns list of IDs."""
    print("👤 Seeding customers...")
    customer_ids = []

    # Ensure columns exist
    try:
        cur.execute("""
            ALTER TABLE customers
            ADD COLUMN IF NOT EXISTS industry      VARCHAR(50)  DEFAULT 'unknown',
            ADD COLUMN IF NOT EXISTS credit_score  INT          DEFAULT 650,
            ADD COLUMN IF NOT EXISTS service_status VARCHAR(20) DEFAULT 'active',
            ADD COLUMN IF NOT EXISTS account_age_months INT     DEFAULT 12,
            ADD COLUMN IF NOT EXISTS is_blacklisted TINYINT(1)  DEFAULT 0,
            ADD COLUMN IF NOT EXISTS suspension_reason VARCHAR(200) DEFAULT NULL,
            ADD COLUMN IF NOT EXISTS suspended_at    DATETIME DEFAULT NULL,
            ADD COLUMN IF NOT EXISTS blacklisted_at  DATETIME DEFAULT NULL
        """)
        conn.commit()
    except Exception as e:
        print(f"   ⚠️ Column check: {e}")

    for name, industry, credit_score, _ in CUSTOMERS:
        try:
            cur.execute(
                """
                INSERT INTO customers
                    (name, industry, credit_score, service_status, account_age_months)
                VALUES (%s, %s, %s, 'active', %s)
                """,
                (name, industry, credit_score, random.randint(6, 60)),
            )
            conn.commit()
            customer_ids.append(cur.lastrowid)
            print(f"   ✅ Customer: {name} (id={cur.lastrowid})")
        except Exception as e:
            print(f"   ⚠️ {name}: {e}")
            # Try to get existing
            cur.execute("SELECT id FROM customers WHERE name = %s LIMIT 1", (name,))
            row = cur.fetchone()
            if row:
                customer_ids.append(row["id"])

    return customer_ids


def seed_invoices(conn, cur, customer_ids: list[int]) -> None:
    """Insert invoices with varied overdue status."""
    print("\n🧾 Seeding invoices...")

    # Ensure invoices table has needed columns
    try:
        cur.execute("""
            ALTER TABLE invoices
            ADD COLUMN IF NOT EXISTS ai_risk_score     FLOAT         DEFAULT NULL,
            ADD COLUMN IF NOT EXISTS ai_decision       VARCHAR(100)  DEFAULT NULL,
            ADD COLUMN IF NOT EXISTS ai_decision_reason TEXT         DEFAULT NULL,
            ADD COLUMN IF NOT EXISTS collection_strategy VARCHAR(50) DEFAULT 'standard',
            ADD COLUMN IF NOT EXISTS is_disputed       TINYINT(1)    DEFAULT 0,
            ADD COLUMN IF NOT EXISTS paid_at           DATETIME      DEFAULT NULL,
            ADD COLUMN IF NOT EXISTS written_off_at    DATETIME      DEFAULT NULL
        """)
        conn.commit()
    except Exception as e:
        print(f"   ⚠️ Invoice column check: {e}")

    scenarios = [
        # (overdue_days, status, label)
        (0,   "pending",  "🆕 New invoice — needs risk assessment"),
        (3,   "pending",  "🆕 Very new — 3 days"),
        (8,   "overdue",  "⚠️ Slightly overdue — 8 days"),
        (15,  "overdue",  "⚠️ 2 weeks overdue"),
        (22,  "overdue",  "⚠️ 3 weeks overdue"),
        (35,  "overdue",  "🔴 Over a month overdue"),
        (50,  "overdue",  "🔴 Suspension candidate (45+ days)"),
        (60,  "overdue",  "🔴 60 days — heavy risk"),
        (95,  "overdue",  "⚖️ Legal candidate (90+ days)"),
        (185, "overdue",  "❌ Write-off candidate (180+ days)"),
        (30,  "overdue",  "💬 Disputed invoice"),
        (0,   "paid",     "✅ Already paid — recent"),
    ]

    invoice_count = 0
    for i, (cust_id, (_, _, _, risk)) in enumerate(zip(customer_ids, CUSTOMERS)):
        for j, (overdue_days, base_status, label) in enumerate(scenarios[:3]):
            amount   = random_amount(risk)
            due_date = random_due_date(overdue_days)
            status   = base_status
            is_disputed = 0

            # Some variety
            if j == 2 and risk == "high":
                overdue_days = random.randint(30, 100)
                due_date = random_due_date(overdue_days)
                status = "overdue"

            try:
                cur.execute(
                    """
                    INSERT INTO invoices
                        (customer_id, amount, due_date, status, is_disputed, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        cust_id,
                        amount,
                        due_date,
                        status,
                        is_disputed,
                        datetime.now() - timedelta(days=overdue_days + 2),
                    ),
                )
                conn.commit()
                invoice_count += 1
                print(f"   ✅ Invoice #{cur.lastrowid} | {label} | {amount:,.0f} EGP | cust={cust_id}")
            except Exception as e:
                print(f"   ⚠️ Invoice insert: {e}")

    # Add heavy scenarios for high-risk customers
    heavy_scenarios = [
        (50, "overdue", False),   # suspension candidate
        (95, "overdue", False),   # legal candidate
        (185, "overdue", False),  # write-off
        (30, "overdue", True),    # disputed
    ]

    high_risk_customers = [
        (cid, risk) for cid, (_, _, _, risk) in zip(customer_ids, CUSTOMERS)
        if risk == "high"
    ]

    for cust_id, risk in high_risk_customers:
        for overdue_days, status, is_disputed in heavy_scenarios:
            amount = random_amount(risk)
            try:
                cur.execute(
                    """
                    INSERT INTO invoices
                        (customer_id, amount, due_date, status, is_disputed, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        cust_id,
                        amount,
                        random_due_date(overdue_days),
                        status,
                        1 if is_disputed else 0,
                        datetime.now() - timedelta(days=overdue_days + 2),
                    ),
                )
                conn.commit()
                invoice_count += 1
                days_label = f"{overdue_days}d"
                print(f"   🔴 Heavy invoice #{cur.lastrowid} | {days_label} | {amount:,.0f} EGP | disputed={is_disputed}")
            except Exception as e:
                print(f"   ⚠️ Heavy invoice: {e}")

    print(f"\n   📊 Total invoices created: {invoice_count}")


def ensure_finance_tables(conn, cur) -> None:
    """Create finance-specific tables if they don't exist."""
    print("\n🏗️ Ensuring finance DB tables...")

    tables = [
        """
        CREATE TABLE IF NOT EXISTS finance_decisions (
            id              BIGINT AUTO_INCREMENT PRIMARY KEY,
            agent_type      VARCHAR(100) NOT NULL,
            entity          VARCHAR(50)  NOT NULL,
            entity_id       INT          NOT NULL,
            event_id        INT          DEFAULT NULL,
            decision        VARCHAR(100) NOT NULL,
            confidence      FLOAT        DEFAULT 0,
            risk_score      FLOAT        DEFAULT 0,
            reasoning       TEXT         DEFAULT NULL,
            action_plan     TEXT         DEFAULT NULL,
            execution_ms    INT          DEFAULT 0,
            request_id      VARCHAR(100) DEFAULT NULL,
            created_at      DATETIME     DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_entity    (entity, entity_id),
            INDEX idx_decision  (decision),
            INDEX idx_created   (created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
        """
        CREATE TABLE IF NOT EXISTS finance_audit_log (
            id              BIGINT AUTO_INCREMENT PRIMARY KEY,
            domain          VARCHAR(50)  NOT NULL,
            entity_id       INT          NOT NULL,
            customer_id     INT          DEFAULT NULL,
            decision        VARCHAR(100) NOT NULL,
            risk_score      FLOAT        DEFAULT 0,
            confidence      FLOAT        DEFAULT 0,
            decision_source VARCHAR(100) DEFAULT NULL,
            llm_used        TINYINT(1)   DEFAULT 0,
            request_id      VARCHAR(100) DEFAULT NULL,
            execution_ms    INT          DEFAULT 0,
            action_plan     TEXT         DEFAULT NULL,
            created_at      DATETIME     DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_domain    (domain, entity_id),
            INDEX idx_customer  (customer_id),
            INDEX idx_created   (created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
        """
        CREATE TABLE IF NOT EXISTS finance_collection_log (
            id              BIGINT AUTO_INCREMENT PRIMARY KEY,
            invoice_id      INT          DEFAULT NULL,
            customer_id     INT          DEFAULT NULL,
            action_type     VARCHAR(100) NOT NULL,
            template_name   VARCHAR(200) DEFAULT NULL,
            subject         VARCHAR(300) DEFAULT NULL,
            body            TEXT         DEFAULT NULL,
            priority        VARCHAR(20)  DEFAULT 'medium',
            status          VARCHAR(50)  DEFAULT 'sent',
            sent_at         DATETIME     DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_invoice  (invoice_id),
            INDEX idx_customer (customer_id),
            INDEX idx_type     (action_type)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
    ]

    for sql in tables:
        try:
            cur.execute(sql)
            conn.commit()
            print("   ✅ Table ready")
        except Exception as e:
            print(f"   ⚠️ Table: {e}")


def print_summary(cur) -> None:
    print("\n" + "═" * 55)
    print("  📊 Database Summary")
    print("═" * 55)

    try:
        cur.execute("SELECT COUNT(*) AS n FROM customers")
        print(f"  👤 Customers  : {cur.fetchone()['n']}")

        cur.execute("SELECT COUNT(*) AS n FROM invoices")
        print(f"  🧾 Total invoices : {cur.fetchone()['n']}")

        cur.execute("SELECT status, COUNT(*) AS n FROM invoices GROUP BY status")
        for row in cur.fetchall():
            icon = {"pending": "🆕", "overdue": "🔴", "paid": "✅"}.get(row["status"], "•")
            print(f"     {icon} {row['status']:<15} {row['n']}")

        cur.execute(
            "SELECT COUNT(*) AS n FROM invoices "
            "WHERE status IN ('pending','overdue') AND (ai_risk_score IS NULL OR ai_risk_score = 0)"
        )
        print(f"\n  🤖 Awaiting AI  : {cur.fetchone()['n']} invoices")
    except Exception as e:
        print(f"  ⚠️ Summary error: {e}")

    print("═" * 55)
    print("\n  ✅ Seeding complete!")
    print("\n  Next steps:")
    print("  1. Start the server:  uvicorn main:app --port 9000 --reload")
    print("  2. Trigger manually:  POST /trigger/run-now/overdue-invoices")
    print("  3. Or wait 5 min for scheduler to run automatically")
    print("  4. Check results:     GET  /finance/invoices")
    print()


def main():
    print("🌱 Finance Database Seeder v1.0")
    print("=" * 55)

    try:
        with get_db() as (conn, cur):
            ensure_finance_tables(conn, cur)
            customer_ids = seed_customers(conn, cur)
            if not customer_ids:
                print("❌ No customers created — check DB connection")
                return
            seed_invoices(conn, cur, customer_ids)
            print_summary(cur)
    except Exception as e:
        print(f"\n❌ Seeder failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()