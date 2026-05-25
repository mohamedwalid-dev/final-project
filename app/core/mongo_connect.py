"""
🔌 MongoDB Atlas Connection — Synergy ERP
==========================================
File: core/mongo_connect.py

Steps to run:
1. pip install motor pymongo python-dotenv certifi
2. Add MONGO_URI + MONGO_DB to your .env file
3. Import `get_finance_db` or `get_hr_db` anywhere in your FastAPI app

.env example:
    MONGO_URI=mongodb+srv://USER:PASS@cluster.mongodb.net/?retryWrites=true&w=majority&authSource=admin
    MONGO_DB=ERP
    # Dev only if SSL fails on Windows:
    # MONGO_TLS_INSECURE=true
"""

import os
import logging
from dotenv import load_dotenv

from core.mongo_client import (
    create_mongo_client,
    is_local_mongo_uri,
    resolve_mongo_uri,
    verify_mongo_connection,
)

load_dotenv()
logger = logging.getLogger(__name__)

# ── Lazy singletons ────────────────────────────────────────────────────────
_mongo_client: object | None = None
_finance_db_instance = None
_hr_db_instance = None


def _mongo_uri() -> str:
    return resolve_mongo_uri()


def _mongo_db_name() -> str:
    return os.getenv("MONGO_DB", "synergy_erp").strip()


def get_shared_mongo_client():
    """Single Motor client for the whole app (Finance + HR)."""
    global _mongo_client
    if _mongo_client is None:
        uri = _mongo_uri()
        _mongo_client = create_mongo_client(uri)
        kind = "local" if is_local_mongo_uri(uri) else "atlas"
        logger.info("MongoDB client created (%s)", kind)
    return _mongo_client


def get_finance_db():
    """
    Get the global FinanceDB instance.
    Call this inside your route handlers or services.

    Example:
        db = get_finance_db()
        invoice = await db.get_invoice(invoice_id)
    """
    global _finance_db_instance
    if _finance_db_instance is None:
        from models.finance_models import FinanceDB

        uri = _mongo_uri()
        db_name = _mongo_db_name()
        _finance_db_instance = FinanceDB(
            uri=uri,
            db_name=db_name,
            client=get_shared_mongo_client(),
        )
        logger.info("✅ FinanceDB ready — db=%s", db_name)

    return _finance_db_instance


def get_hr_db():
    """
    Get the global HRDB instance.
    Call this inside your route handlers or services.

    Example:
        db = get_hr_db()
        leave_id = await db.create_leave_request({...})
        leave    = await db.get_leave(leave_id)
    """
    global _hr_db_instance
    if _hr_db_instance is None:
        from models.hr_models import HRDB

        uri = _mongo_uri()
        db_name = _mongo_db_name()
        _hr_db_instance = HRDB(
            uri=uri,
            db_name=db_name,
            client=get_shared_mongo_client(),
        )
        logger.info("✅ HRDB ready — db=%s", db_name)

    return _hr_db_instance


async def ensure_mongo_ready() -> dict:
    """Ping Atlas, init Finance + HR indexes. Call from FastAPI lifespan."""
    client = get_shared_mongo_client()
    db_name = _mongo_db_name()

    ping = await verify_mongo_connection(client, db_name)
    logger.info("✅ MongoDB ping OK — version=%s db=%s", ping.get("version"), db_name)

    finance_db = get_finance_db()
    hr_db = get_hr_db()

    await finance_db.init_indexes()
    logger.info("✅ FinanceDB indexes ready")

    await hr_db.init_indexes()
    logger.info("✅ HRDB indexes ready")

    return {"ping": ping, "db": db_name}


# ════════════════════════════════════════════════════════════════════════════
#  FASTAPI LIFESPAN INTEGRATION
# ════════════════════════════════════════════════════════════════════════════

from contextlib import asynccontextmanager
from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Use this as your FastAPI lifespan to init indexes on startup.

    Example in main.py:
        from core.mongo_connect import lifespan
        app = FastAPI(lifespan=lifespan)
    """
    await ensure_mongo_ready()
    logger.info("🚀 Synergy ERP — MongoDB Atlas fully ready")
    yield

    client = get_shared_mongo_client()
    client.close()
    logger.info("🛑 MongoDB connection closed")


# ════════════════════════════════════════════════════════════════════════════
#  QUICK CONNECTION TEST  —  run: python -m core.mongo_connect
# ════════════════════════════════════════════════════════════════════════════

async def _test_connection():
    """Test Atlas connection for both FinanceDB and HRDB."""
    from datetime import datetime, timezone, timedelta
    from bson import ObjectId

    print("\n[MongoDB] Testing connection (%s)...\n" % _mongo_uri().split("@")[-1][:60])

    try:
        ready = await ensure_mongo_ready()
        print(f"[OK] Ping — MongoDB {ready['ping'].get('version')} — db={ready['db']}\n")
    except Exception as exc:
        print("[FAIL] MongoDB connection failed.\n")
        print(f"   Error: {exc}\n")
        try:
            import urllib.request
            ip = urllib.request.urlopen("https://api.ipify.org", timeout=5).read().decode().strip()
            print(f"   Your public IP (add in Atlas): {ip}\n")
        except Exception:
            pass
        print("   Run: python -m core.atlas_check\n")
        print("   Checklist:")
        print("   1. Atlas > Network Access > Add IP Address (your IP or 0.0.0.0/0 for dev)")
        print("      https://cloud.mongodb.com/v2/6a0f8245d16844e9d18ebf91#/security/network/accessList")
        print("   2. Atlas > Database Access > user readWrite on database '%s'" % _mongo_db_name())
        print("   3. MONGO_URI = Connect -> Drivers -> Python (copy full SRV string)")
        print("   4. pip install motor pymongo certifi")
        print("   5. Windows: MONGO_TLS_DISABLE_OCSP=true in .env (already recommended)")
        raise

    finance_db = get_finance_db()
    hr_db = get_hr_db()

    # ── FINANCE TESTS ──────────────────────────────────────────────────────
    print("--- FinanceDB ---")

    customer_id = await finance_db.customers.insert_one({
        "name":           "Test Customer",
        "email":          "test@synergy.com",
        "credit_score":   720,
        "industry":       "retail",
        "service_status": "active",
        "is_blacklisted": False,
        "created_at":     datetime.now(timezone.utc),
        "updated_at":     datetime.now(timezone.utc),
    })
    cid = customer_id.inserted_id
    print(f"[OK] Test customer inserted: {cid}")

    inv_id = await finance_db.create_invoice({
        "customer_id": cid,
        "amount":      5000.00,
        "due_date":    datetime.now(timezone.utc) - timedelta(days=10),
        "description": "Test invoice",
        "status":      "overdue",
    })
    print(f"[OK] Test invoice inserted: {inv_id}")

    dec_id = await finance_db.save_finance_decision({
        "entity_id":  inv_id,
        "decision":   "send_reminder",
        "confidence": 0.85,
        "risk_score": 0.42,
        "reasoning":  "Customer has moderate risk score",
        "action_plan":"Send email reminder + schedule follow-up call",
    })
    print(f"[OK] Finance decision saved: {dec_id}")

    stats = await finance_db.get_finance_dashboard_stats()
    print(f"[OK] Finance dashboard stats: total_invoices={stats.get('invoices', {}).get('total_invoices', 0)}")

    await finance_db.invoices.delete_one({"_id": ObjectId(inv_id)})
    await finance_db.customers.delete_one({"_id": cid})
    await finance_db.decisions.delete_one({"_id": ObjectId(dec_id)})
    print("[OK] Finance test data cleaned up")

    # ── HR TESTS ───────────────────────────────────────────────────────────
    print("\n--- HRDB ---")

    leave_id = await hr_db.create_leave_request({
        "employee_id":   999,
        "employee_name": "Test Employee",
        "department":    "Engineering",
        "leave_type":    "annual",
        "leave_days":    3,
        "reason":        "Test leave request",
        "leave_balance": 15,
        "status":        "pending",
    })
    print(f"[OK] Test leave request inserted: {leave_id}")

    leave = await hr_db.get_leave(leave_id)
    print(f"[OK] Leave fetched: status={leave.get('status')}, employee={leave.get('employee_name')}")

    updated = await hr_db.update_leave_status(
        leave_id=leave_id,
        status="approved",
        ai_decision="approve",
        confidence=0.92,
        reason="Sufficient balance and no conflicts",
        decision_source="ml",
        tier=1,
    )
    print(f"[OK] Leave status updated: {updated}")

    hr_stats = await hr_db.get_hr_dashboard_stats()
    print(f"[OK] HR dashboard stats: leaves={hr_stats.get('leaves')}")

    await hr_db.leaves.delete_one({"_id": ObjectId(leave_id)})
    print("[OK] HR test data cleaned up")

    print("\n[SUCCESS] All tests passed. Atlas is ready for Finance + HR.\n")


if __name__ == "__main__":
    import asyncio
    asyncio.run(_test_connection())
