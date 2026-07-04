"""
🌱 Finance Seed Script — v3.0 (Node.js API backend)
=========================================
File: app/scripts/finance_seed.py

Used by:
    - finance_seed_routes.py  → POST /finance/seed
    - finance_seeder.py       → python finance_seeder.py

run_seed() is async — awaitable from FastAPI routes.

v3 — migrated off direct MongoDB (Motor) access to NodeFinanceProxy
     (core/node_finance_proxy.py), which routes every read/write through
     the Node.js/Express API instead of touching `db.customers` /
     `db.invoices` collections directly. Two consequences worth noting:

    1. NO RESET SUPPORT. The old v2 script could `await db.customers.drop()`
       etc. before reseeding. NodeFinanceProxy has no delete-all/drop
       endpoint — only per-record `delete_customer(id)` / `delete_invoice(id)`
       exist in finance.routes.js, and there's no bulk-list-everything
       endpoint to loop over safely either. Rather than bolt on a slow,
       partial, and easy-to-get-wrong N+1 "delete everything one at a time"
       path, the `reset` parameter has been removed entirely. If a real
       reset is needed, clear the data on the Node/Mongo side directly
       (or ask the Node team for a bulk-delete/reset endpoint) and then
       call run_seed() again.
    2. "ALREADY SEEDED" CHECK VIA get_customers(limit=1). There is no
       count_documents() equivalent over HTTP. We treat "at least one
       customer already exists" as "already seeded" and skip, same
       intent as the old count-based check, just cheaper (limit=1
       instead of pulling everything).
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


def _extract_customer_id(res) -> Optional[str]:
    """Node's POST /finance/customers controller response shape isn't
    pinned down anywhere in node_api_client.py's docstring (only GET
    shapes are confirmed there), so this is defensive rather than
    assuming a single exact shape:
      - dict with {"customer": {"_id"|"id": ...}}   (nested, like hr's leave/review/absence)
      - dict with {"customer_id": ...}               (flat, like hr's absence_id/review_id)
      - dict with {"_id"|"id": ...} directly          (bare object)
      - list containing one such dict                 (seen elsewhere in this API)
    Returns None (not "mock_id") on failure — for seeding we'd rather
    skip linking invoices to a bad id and log it than silently attach
    invoices to a fake "mock_id" customer.
    """
    if isinstance(res, list):
        res = res[0] if res else {}
    if not isinstance(res, dict):
        return None

    nested = res.get("customer")
    if isinstance(nested, dict):
        _id = nested.get("_id") or nested.get("id")
        if _id:
            return str(_id)

    _id = res.get("customer_id")
    if _id:
        return str(_id)

    _id = res.get("_id") or res.get("id")
    if _id:
        return str(_id)

    return None


# ═════════════════════════════════════════════════════════════════════════════
# 🌱  run_seed  — main entry point
# ═════════════════════════════════════════════════════════════════════════════

async def run_seed(
    customer_count: int = 25,
    reset: Optional[bool] = None,
) -> dict:
    """
    Seed finance data via the Node.js API (NodeFinanceProxy).

    Args:
        customer_count: How many customers to create.
        reset: ⚠️ ACCEPTED BUT IGNORED (no-op). Kept only so existing
            callers like finance_seed_routes.py
            (`run_seed(reset=config.reset, ...)`) don't hard-crash with
            TypeError while they still pass this kwarg. NodeFinanceProxy
            has no delete-all/drop endpoint (see module docstring) —
            there is nothing this parameter can actually trigger. If
            `reset=True` is passed, a warning is logged so it's obvious
            in the logs that no reset happened, instead of silently
            pretending it did. The real fix is to remove `reset` from
            finance_seed_routes.py's call (and ideally from its request
            schema) once that route is updated; this parameter should
            be deleted at that point rather than kept indefinitely.

    Returns:
        Summary dict with counts.

    Note: no real reset support — see module docstring. This always
    skips if any customer already exists on the Node side.
    """
    from core.node_finance_proxy import get_finance_db
    from models.finance_models import build_customer, build_invoice

    if reset:
        logger.warning(
            "⚠️ [FinanceSeed] reset=True was passed but is a no-op — "
            "NodeFinanceProxy has no delete-all/drop endpoint. No data "
            "was cleared. Update the caller (e.g. finance_seed_routes.py) "
            "to stop passing reset, or clear data on the Node/Mongo side "
            "directly before calling run_seed()."
        )

    db = get_finance_db()

    # ── Skip if already seeded ────────────────────────────────────────────────
    try:
        existing = await db.get_customers(limit=1)
    except Exception as e:
        logger.warning("⚠️ [FinanceSeed] could not check existing customers via Node API: %s", e)
        existing = []

    if existing:
        logger.info("⚠️ [FinanceSeed] Already seeded (at least 1 customer found via Node API). Skipping.")
        return {
            "skipped": True,
            "reason": "Data already present on the Node API. No reset support — "
                      "clear data on the Node/Mongo side directly if you need to reseed.",
        }

    # ── Seed customers ────────────────────────────────────────────────────────
    names    = random.sample(_NAME_POOL, min(customer_count, len(_NAME_POOL)))
    profiles = [_pick_profile() for _ in names]

    customer_ids   = []
    customer_risks = []
    failed_customers = 0

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
        try:
            res = await db.create_customer(doc)
        except Exception as e:
            logger.warning("⚠️ [FinanceSeed] create_customer failed for %r: %s", name, e)
            failed_customers += 1
            continue

        cid = _extract_customer_id(res)
        if not cid:
            logger.warning(
                "⚠️ [FinanceSeed] create_customer for %r succeeded but no id could "
                "be extracted from the response (%r) — skipping invoices for this customer",
                name, res,
            )
            failed_customers += 1
            continue

        customer_ids.append(cid)
        customer_risks.append(profile)

    logger.info(
        "👤 [FinanceSeed] %d customers created via Node API%s",
        len(customer_ids),
        f" ({failed_customers} failed)" if failed_customers else "",
    )

    # ── Seed invoices ─────────────────────────────────────────────────────────
    invoice_count    = 0
    failed_invoices  = 0
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
            try:
                await db.create_invoice(doc)
            except Exception as e:
                logger.warning("⚠️ [FinanceSeed] create_invoice failed for customer %s: %s", cid, e)
                failed_invoices += 1
                continue

            invoice_count += 1
            status_summary[status] = status_summary.get(status, 0) + 1

    logger.info(
        "🧾 [FinanceSeed] %d invoices created via Node API%s | breakdown: %s",
        invoice_count,
        f" ({failed_invoices} failed)" if failed_invoices else "",
        status_summary,
    )

    return {
        "seeded":           True,
        "customers":        len(customer_ids),
        "customers_failed": failed_customers,
        "invoices":         invoice_count,
        "invoices_failed":  failed_invoices,
        "status_breakdown": status_summary,
        "timestamp":        _utcnow().isoformat(),
    }