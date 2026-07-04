"""

traing\finance_train.py 

💰 Finance Risk Model — v8.1  (Production-Ready, Low FP, 3-Tier Decisions)
===========================================================================

🔑 الفرق عن v8.0:
  ✅ Threshold رُفع من 0.14 → 0.30+ (يقلل FP جامد)
  ✅ 3-tier decisions: approve / review / reject (بدل binary)
  ✅ Decision Logging مع actual outcome tracking
  ✅ Human Override system (مع audit trail)
  ✅ Business-context decision modes per department
  ✅ FP cost penalty مرتفع في threshold optimization
  ✅ UI-ready reasons & explanations

🔧 BUG FIX v8.1.1:
  ✅ _to_features(): numpy array input → shape guard يضمن (1, N) مش (1, 1, N)
  ✅ _to_features(): dict input مع leakage guard محسّن

🌐 v8.2 — Node API Data Source:
  ✅ load_from_node_api(): يجيب customers + invoices من Node.js ERP API
     (بدل CSV) عن طريق NodeAPIClient الموجود في core/node_api_client.py
  ✅ Fallback chain: Node API → CSV → Synthetic data
  ✅ Field-name tolerant (snake_case / camelCase) لأن الـ Node controllers
     بترجّع Mongoose documents مباشرة من غير schema ثابت متفق عليه هنا

CSV Columns المتوقعة (schema ثابت):
  customer_id, invoice_id, age, gender, location, industry,
  business_type, years_with_company, income_revenue, credit_score,
  credit_limit, outstanding_balance, debt_ratio, invoice_amount,
  invoice_date, due_date, payment_date

Target:
  is_bad_payer = 1 إذا payment_delay > 30 يوم

Usage:
  python finance_train_v8.py --csv data.csv
  python finance_train_v8.py --csv data.csv --mode balanced --trials 50
  python finance_train_v8.py --csv data.csv --fp-penalty 5.0   # يرفع penalty على FP
  python finance_train_v8.py --from-node-api                  # 🌐 من Node API مباشرة
  python finance_train_v8.py --from-node-api --csv data.csv    # Node API مع CSV fallback
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import pickle
import sys
import uuid
import warnings
from datetime import datetime
from typing import Optional
import joblib
import numpy as np
import pandas as pd
try:
    import joblib
except ImportError:
    joblib = None

    

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Make sure `core.*` (node_api_client / node_finance_proxy) is importable ──
_APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _APP_ROOT not in sys.path:
    sys.path.insert(0, _APP_ROOT)

# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR     = os.path.join(BASE_DIR, "models")
LOG_DIR       = os.path.join(BASE_DIR, "decision_logs")
os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(LOG_DIR,   exist_ok=True)

MODEL_PATH    = os.path.join(MODEL_DIR, "payment_risk_v8.pkl")
METADATA_PATH = os.path.join(MODEL_DIR, "metadata_v8.json")
REPORT_PATH   = os.path.join(MODEL_DIR, "report_v8.txt")
DECISION_LOG  = os.path.join(LOG_DIR,   "decisions.jsonl")
OVERRIDE_LOG  = os.path.join(LOG_DIR,   "overrides.jsonl")
FEATURE_COLUMNS_PATH = os.path.join(MODEL_DIR, "finance_feature_columns.pkl")  # ← هنا

RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)

# ─────────────────────────────────────────────────────────────────────────────
# Risk lookup tables
# ─────────────────────────────────────────────────────────────────────────────
INDUSTRY_RISK = {
    "retail": 0.40, "hospitality": 0.50, "construction": 0.60,
    "manufacturing": 0.35, "technology": 0.25, "healthcare": 0.20,
    "education": 0.15, "government": 0.05, "financial": 0.20,
    "real_estate": 0.55, "food_beverage": 0.45,
    "transportation": 0.40, "unknown": 0.40,
    "real estate": 0.55, "food & beverage": 0.45,
}
SEASONAL_RISK = {
    1: 0.50, 2: 0.45, 3: 0.35, 4: 0.30, 5: 0.30, 6: 0.40,
    7: 0.35, 8: 0.40, 9: 0.30, 10: 0.25, 11: 0.30, 12: 0.55,
}
BUSINESS_TYPE_RISK = {
    "b2b": 0.30, "b2c": 0.45, "b2g": 0.15, "unknown": 0.35,
}

# ══════════════════════════════════════════════════════════════════════════════
# 🔥 v8.1 — IMPROVED DECISION MODES (3-tier thresholds)
# ══════════════════════════════════════════════════════════════════════════════
DECISION_MODES = {
    "safe": {
        "reject":      0.45,
        "review_high": 0.35,
        "review_low":  0.20,
        "description": "حماية مالية — للإدارة المالية والائتمان",
    },
    "balanced": {
        "reject":      0.50,
        "review_high": 0.38,
        "review_low":  0.22,
        "description": "متوازن — الوضع الافتراضي للـ ERP",
    },
    "aggressive": {
        "reject":      0.60,
        "review_high": 0.45,
        "review_low":  0.28,
        "description": "نمو مبيعات — للفرق التجارية",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# Feature groups  ✅ كلها معروفة قبل السداد — صفر Leakage
# ─────────────────────────────────────────────────────────────────────────────
BASE_FEATURES = [
    "amount_normalized",
    "customer_age_normalized",
    "years_with_company_normalized",
    "invoice_frequency",
    "industry_risk_factor",
    "seasonal_factor",
    "business_type_risk",
    "days_to_due_normalized",
]
CREDIT_FEATURES = [
    "credit_score_normalized",
    "credit_score_bucket",
    "credit_utilization",
    "debt_ratio",
    "credit_score_x_industry",
]
INCOME_FEATURES = [
    "income_normalized",
    "invoice_to_income_ratio",
    "balance_to_income_ratio",
]
BEHAVIORAL_FEATURES = [
    "hist_paid_ratio",
    "hist_late_ratio",
    "hist_paid_ratio_3",
    "hist_paid_ratio_6",
    "hist_late_ratio_3",
    "paid_trend",
    "late_trend",
    "last_paid",
    "last_late",
    "hist_max_delay",
    "hist_avg_delay_normalized",
    "delay_variance",
    "payment_volatility",
    "late_streak",
    "good_streak",
    "invoice_frequency_trend",
    "payment_velocity",
    "days_since_last_payment_norm",
    "hist_payment_count_normalized",
]
ENGINEERED_FEATURES = [
    "risk_composite",
    "amount_x_industry_risk",
    "clv_proxy",
    "recovery_signal",
    "behavioral_score",
    "credit_x_late",
]

ALL_FEATURES = BASE_FEATURES + CREDIT_FEATURES + INCOME_FEATURES + \
               BEHAVIORAL_FEATURES + ENGINEERED_FEATURES

LEAKY_FEATURES = {
    "overdue_days", "overdue_days_normalized",
    "overdue_x_industry", "payment_delay",
    "is_late", "is_bad_payer",
}

# ─────────────────────────────────────────────────────────────────────────────
# UI-ready feature reasons (Arabic + English key)
# ─────────────────────────────────────────────────────────────────────────────
FEATURE_REASON_MAP = {
    "hist_late_ratio":             {"ar": "نسبة تأخير تاريخية عالية",          "en": "High historical late payment rate"},
    "hist_late_ratio_3":           {"ar": "نسبة تأخير متصاعدة (3 فواتير أخيرة)", "en": "Rising late payments (last 3 invoices)"},
    "late_streak":                 {"ar": "سلسلة تأخيرات متتالية حديثة",       "en": "Recent consecutive late payments"},
    "late_trend":                  {"ar": "تزايد ملحوظ في التأخير",            "en": "Increasing payment delays trend"},
    "delay_variance":              {"ar": "عدم انتظام في مواعيد السداد",       "en": "Irregular payment timing"},
    "hist_max_delay":              {"ar": "أعلى تأخير مسجّل تاريخياً",         "en": "High maximum historical delay"},
    "credit_score_normalized":     {"ar": "درجة ائتمان منخفضة",               "en": "Low credit score"},
    "credit_score_bucket":         {"ar": "فئة ائتمان ضعيفة",                 "en": "Poor credit tier"},
    "credit_utilization":          {"ar": "استخدام ائتمان مرتفع",             "en": "High credit utilization"},
    "debt_ratio":                  {"ar": "نسبة دين مرتفعة",                  "en": "High debt ratio"},
    "credit_score_x_industry":     {"ar": "مخاطر ائتمان مركّبة مع القطاع",   "en": "Combined credit & industry risk"},
    "credit_x_late":               {"ar": "ائتمان منخفض مع تأخير تاريخي",    "en": "Low credit with late payment history"},
    "industry_risk_factor":        {"ar": "قطاع عالي المخاطر",                "en": "High-risk industry sector"},
    "business_type_risk":          {"ar": "نوع عمل ذو مخاطرة",               "en": "Higher-risk business type"},
    "seasonal_factor":             {"ar": "موسم مرتفع المخاطر",               "en": "High-risk season"},
    "risk_composite":              {"ar": "مؤشر مخاطرة مركّب عالٍ",          "en": "High composite risk score"},
    "behavioral_score":            {"ar": "سلوك دفع سلبي عام",               "en": "Negative payment behavior pattern"},
    "payment_volatility":          {"ar": "سلوك دفع غير مستقر",              "en": "Unstable payment behavior"},
    "amount_x_industry_risk":      {"ar": "مبلغ كبير في قطاع خطر",           "en": "Large invoice in risky sector"},
    "hist_paid_ratio":             {"ar": "نسبة سداد تاريخية منخفضة",        "en": "Low historical payment rate"},
    "hist_paid_ratio_3":           {"ar": "نسبة سداد ضعيفة مؤخراً",          "en": "Weak recent payment rate"},
    "paid_trend":                  {"ar": "تراجع في نسبة السداد",             "en": "Declining payment trend"},
    "last_late":                   {"ar": "آخر دفعة تأخرت",                  "en": "Last payment was late"},
    "invoice_to_income_ratio":     {"ar": "فاتورة كبيرة نسبةً للدخل",        "en": "Large invoice relative to income"},
    "balance_to_income_ratio":     {"ar": "رصيد مستحق مرتفع نسبةً للدخل",   "en": "High outstanding balance vs income"},
    "days_since_last_payment_norm":{"ar": "وقت طويل منذ آخر دفعة",           "en": "Long time since last payment"},
    "clv_proxy":                   {"ar": "قيمة عميل منخفضة",                "en": "Low customer lifetime value"},
    "recovery_signal":             {"ar": "بطء في التعافي بعد التأخير",       "en": "Slow recovery after late payments"},
    "days_to_due_normalized":      {"ar": "فترة سداد قصيرة جداً",            "en": "Very short payment window"},
}

HIST_DEFAULTS = {
    "hist_paid_ratio":               0.75,
    "hist_late_ratio":               0.15,
    "hist_avg_delay_normalized":     0.10,
    "hist_payment_count_normalized": 0.00,
    "hist_paid_ratio_3":             0.75,
    "hist_paid_ratio_6":             0.75,
    "hist_late_ratio_3":             0.15,
    "paid_trend":                    0.00,
    "late_trend":                    0.00,
    "last_paid":                     0.75,
    "last_late":                     0.15,
    "hist_max_delay":                0.05,
    "delay_variance":                0.05,
    "late_streak":                   0.00,
    "good_streak":                   0.50,
    "invoice_frequency_trend":       0.00,
    "payment_velocity":              0.50,
    "days_since_last_payment_norm":  0.30,
}


# ══════════════════════════════════════════════════════════════════════════════
# 1. CSV LOADER
# ══════════════════════════════════════════════════════════════════════════════

def load_and_prepare_csv(csv_path: str) -> tuple:
    log.info("📂 Loading CSV: %s", csv_path)
    df = pd.read_csv(csv_path)
    log.info("   Raw shape: %s | columns: %s", df.shape, list(df.columns))
    return _prepare_dataframe(df)


def _prepare_dataframe(df: pd.DataFrame) -> tuple:
    """
    Shared preparation pipeline for any DataFrame that already has (or can
    be coerced into) the expected schema — used by both load_and_prepare_csv()
    and load_from_node_api(), so Node-sourced data goes through exactly the
    same feature engineering / leakage handling as CSV data.
    """
    df = df.copy()
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    for col in ["invoice_date", "due_date", "payment_date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], dayfirst=False, errors="coerce")

    # ── Handle missing customer_id ─────────────────────────────────────────────
    if "customer_id" not in df.columns:
        log.warning("   ⚠️  customer_id missing — creating synthetic IDs")
        df["customer_id"] = [f"CUST-{str(i // 10).zfill(6)}" for i in range(len(df))]

    # ── Handle missing invoice_date ────────────────────────────────────────────
    if "invoice_date" not in df.columns:
        log.warning("   ⚠️  invoice_date missing — using invoice_month to approximate")
        if "invoice_month" in df.columns:
            df["invoice_date"] = pd.to_datetime(
                df["invoice_month"].apply(lambda m: f"2023-{int(m):02d}-01"),
                errors="coerce"
            )
        else:
            df["invoice_date"] = pd.Timestamp("2023-06-01")

    # ── Sort and sequence ──────────────────────────────────────────────────────
    sort_cols = ["customer_id"]
    if "invoice_date" in df.columns:
        sort_cols.append("invoice_date")
    df = df.sort_values(sort_cols, kind="stable").reset_index(drop=True)
    df["invoice_seq"] = df.groupby("customer_id").cumcount()
    if "payment_date" in df.columns and "due_date" in df.columns:
        df["payment_delay"] = (df["payment_date"] - df["due_date"]).dt.days.fillna(0)
    elif "is_bad_payer" in df.columns:
        log.info("   ✅ is_bad_payer column found directly in CSV — using as-is")
        df["payment_delay"] = df["is_bad_payer"].apply(lambda x: 31 if x == 1 else 0)
    else:
        log.warning("   ⚠️  payment_date/due_date missing — payment_delay = 0")
        df["payment_delay"] = 0

    if "is_bad_payer" not in df.columns:
        df["is_bad_payer"] = (df["payment_delay"] > 30).astype(int)
    else:
        df["is_bad_payer"] = df["is_bad_payer"].astype(int)

    df["_is_late_hist"]    = (df["payment_delay"] > 0).astype(float)
    df["_delay_norm_hist"] = (df["payment_delay"].clip(lower=0) / 90).clip(0, 1)

    if "invoice_date" in df.columns:
        df["invoice_month"] = df["invoice_date"].dt.month
    else:
        df["invoice_month"] = 6

    if "invoice_date" in df.columns and "due_date" in df.columns:
        df["days_to_due"] = (df["due_date"] - df["invoice_date"]).dt.days.fillna(30).clip(0, 180)
    else:
        df["days_to_due"] = 30.0

    df["days_since_last_payment"] = (
        df.groupby("customer_id")["invoice_date"]
        .transform(lambda x: x.diff().dt.days)
        .fillna(30).clip(0, 365)
    )

    log.info("   Bad payer rate: %.1f%% | Total invoices: %d | Customers: %d",
             df["is_bad_payer"].mean() * 100, len(df), df["customer_id"].nunique())

    df = build_historical_features(df)

    y      = df["is_bad_payer"].values
    months = df["invoice_month"].values

    LEAKY_TO_DROP = LEAKY_FEATURES - {"is_bad_payer"}
    for lf in LEAKY_TO_DROP:
        if lf in df.columns:
            df.drop(columns=[lf], inplace=True, errors="ignore")

    X, feature_names = build_feature_matrix(df)
    log.info("   Feature matrix: %s | bad=%.1f%%", X.shape, y.mean() * 100)
    return X, y, months, feature_names, df


# ══════════════════════════════════════════════════════════════════════════════
# 1b. NODE API LOADER  🌐  v8.2
# ══════════════════════════════════════════════════════════════════════════════
#
# يجيب customers + invoices من Node.js ERP API (بدل CSV) عن طريق
# NodeAPIClient الموجود في core/node_api_client.py، ويبني DataFrame
# بنفس الأعمدة اللي load_and_prepare_csv() متوقعاها بالظبط:
#
#   customer_id, invoice_id, age, gender, location, industry,
#   business_type, years_with_company, income_revenue, credit_score,
#   credit_limit, outstanding_balance, debt_ratio, invoice_amount,
#   invoice_date, due_date, payment_date
#
# ⚠️ الـ Node controllers بترجّع Mongoose documents زي ما هي (مفيش schema
#    ثابت متفق عليه هنا)، فالـ loader ده متسامح مع أسماء الحقول:
#    بيدور على snake_case وcamelCase variants قبل ما يـ default.
# ─────────────────────────────────────────────────────────────────────────────

# كل عمود متوقع → قائمة أسماء بديلة محتملة جايه من الـ Node API (بالترتيب)
_INVOICE_FIELD_ALIASES = {
    "invoice_id":            ["invoice_id", "invoiceId", "_id", "id"],
    "customer_id":           ["customer_id", "customerId"],
    "invoice_amount":        ["invoice_amount", "invoiceAmount", "amount", "total_amount", "totalAmount"],
    "invoice_date":          ["invoice_date", "invoiceDate", "created_at", "createdAt", "issue_date", "issueDate"],
    "due_date":               ["due_date", "dueDate"],
    "payment_date":           ["payment_date", "paymentDate", "paid_at", "paidAt"],
    "status":                 ["status"],
    "ai_risk_score":          ["ai_risk_score", "aiRiskScore", "risk_score", "riskScore"],
}

_CUSTOMER_FIELD_ALIASES = {
    "customer_id":            ["customer_id", "customerId", "_id", "id"],
    "age":                     ["age", "customer_age"],
    "gender":                  ["gender"],
    "location":                ["location", "city", "address"],
    "industry":                ["industry", "sector"],
    "business_type":           ["business_type", "businessType"],
    "years_with_company":      ["years_with_company", "yearsWithCompany", "tenure_years", "tenureYears"],
    "income_revenue":          ["income_revenue", "incomeRevenue", "annual_revenue", "annualRevenue", "revenue"],
    "credit_score":            ["credit_score", "creditScore"],
    "credit_limit":            ["credit_limit", "creditLimit"],
    "outstanding_balance":     ["outstanding_balance", "outstandingBalance", "balance"],
    "debt_ratio":              ["debt_ratio", "debtRatio"],
}


def _first_present(d: dict, aliases: list[str], default=None):
    """يرجّع أول قيمة موجودة (مش None) من قائمة أسماء بديلة داخل dict واحد."""
    for key in aliases:
        if key in d and d[key] is not None:
            return d[key]
    return default


def _extract_fields(record: dict, alias_map: dict) -> dict:
    return {out_col: _first_present(record, aliases) for out_col, aliases in alias_map.items()}


async def _fetch_all_node_data(limit_per_page: int = 200, max_pages: int = 100) -> tuple[list, list]:
    """
    يسحب كل الـ customers وكل الـ invoices من Node API بالـ pagination
    (limit/skip) لحد ما صفحة ترجع فاضية أو نوصل max_pages (حماية من infinite loop).

    بيرجّع (customers: list[dict], invoices: list[dict]) — raw records
    زي ما جايه من الـ API، من غير أي تعديل على أسماء الحقول.
    """
    from core.node_api_client import get_node_api_client

    client = get_node_api_client()
    await client.ensure_authenticated()

    customers: list = []
    skip = 0
    for _ in range(max_pages):
        page = await client.get_customers(limit=limit_per_page, skip=skip)
        if not page:
            break
        customers.extend(page)
        if len(page) < limit_per_page:
            break
        skip += limit_per_page
    log.info("   🌐 Node API: fetched %d customers", len(customers))

    invoices: list = []
    skip = 0
    for _ in range(max_pages):
        page = await client.get_invoices(limit=limit_per_page, skip=skip)
        if not page:
            break
        invoices.extend(page)
        if len(page) < limit_per_page:
            break
        skip += limit_per_page
    log.info("   🌐 Node API: fetched %d invoices", len(invoices))

    return customers, invoices


def _build_node_dataframe(customers: list, invoices: list) -> pd.DataFrame:
    """
    يبني DataFrame واحد بدمج كل invoice مع الـ customer بتاعه (join على
    customer_id)، وبيطبّع أسماء الحقول لنفس الأعمدة اللي load_and_prepare_csv()
    متوقعاها. أي حقل ناقص بيتسيب فاضي (NaN) — الـ pipeline بعد كده
    (_prepare_dataframe / build_feature_matrix) أصلاً بيعمل .fillna() بقيم
    افتراضية معقولة لكل عمود من دول.
    """
    customer_lookup: dict[str, dict] = {}
    for c in customers:
        norm = _extract_fields(c, _CUSTOMER_FIELD_ALIASES)
        cid = norm.get("customer_id")
        if cid is not None:
            customer_lookup[str(cid)] = norm

    rows = []
    for inv in invoices:
        inv_norm = _extract_fields(inv, _INVOICE_FIELD_ALIASES)
        cid = inv_norm.get("customer_id")
        cust_norm = customer_lookup.get(str(cid), {}) if cid is not None else {}

        row = {
            "customer_id":         cid,
            "invoice_id":          inv_norm.get("invoice_id"),
            "invoice_amount":      inv_norm.get("invoice_amount"),
            "invoice_date":        inv_norm.get("invoice_date"),
            "due_date":            inv_norm.get("due_date"),
            "payment_date":        inv_norm.get("payment_date"),
            "age":                 cust_norm.get("age"),
            "gender":              cust_norm.get("gender"),
            "location":            cust_norm.get("location"),
            "industry":            cust_norm.get("industry"),
            "business_type":       cust_norm.get("business_type"),
            "years_with_company":  cust_norm.get("years_with_company"),
            "income_revenue":      cust_norm.get("income_revenue"),
            "credit_score":        cust_norm.get("credit_score"),
            "credit_limit":        cust_norm.get("credit_limit"),
            "outstanding_balance": cust_norm.get("outstanding_balance"),
            "debt_ratio":          cust_norm.get("debt_ratio"),
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    return df


def load_from_node_api(limit_per_page: int = 200,
                       max_pages: int = 100,
                       min_rows: int = 50) -> Optional[tuple]:
    """
    🌐 Data source #1 (v8.2): يجيب customers + invoices من Node.js ERP API
    ويبنيهم في نفس الـ DataFrame schema اللي CSV loader بيستخدمه، وبعدين
    يمشي في نفس الـ pipeline (_prepare_dataframe) بالظبط.

    بيرجّع (X, y, months, feature_names, df) زي load_and_prepare_csv()،
    أو None لو:
      - فيه استثناء (auth فشل، Node مش شغال، circuit breaker مفتوح، ...)
      - عدد الصفوف اللي رجعت أقل من min_rows (بيانات مش كافية للتدريب)

    الـ caller (main()) مسؤول عن الـ fallback لـ CSV أو synthetic data
    لو رجع None — الدالة دي متعمدة تبلع أي error وترجع None بدل ما توقف
    التدريب كله.
    """
    log.info("🌐 Attempting to load training data from Node API...")
    try:
        customers, invoices = asyncio.run(
            _fetch_all_node_data(limit_per_page=limit_per_page, max_pages=max_pages)
        )
    except Exception as e:
        log.warning("   ⚠️  Node API fetch failed: %s", e)
        return None

    if not invoices:
        log.warning("   ⚠️  Node API returned 0 invoices — nothing to train on")
        return None

    df = _build_node_dataframe(customers, invoices)

    if len(df) < min_rows:
        log.warning(
            "   ⚠️  Node API returned only %d invoice rows (< min_rows=%d) — "
            "not enough data to train reliably", len(df), min_rows,
        )
        return None

    n_missing_customer = df["customer_id"].isna().sum()
    if n_missing_customer:
        log.warning(
            "   ⚠️  %d/%d invoices have no resolvable customer_id — "
            "these rows will get synthetic IDs downstream",
            n_missing_customer, len(df),
        )

    log.info("   ✅ Node API data assembled: %d invoice rows | %d customers matched",
             len(df), len(customers))

    try:
        return _prepare_dataframe(df)
    except Exception as e:
        log.warning("   ⚠️  Failed to prepare Node API data for training: %s", e)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# 2. SYNTHETIC DATA GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

def generate_synthetic_data(n_customers: int = 3000, seed: int = RANDOM_SEED) -> tuple:
    log.info("🔧 Generating synthetic data (%d customers)...", n_customers)
    rng = np.random.default_rng(seed)
    industries = list(INDUSTRY_RISK.keys())[:8]
    rows = []

    for cust_id in range(1, n_customers + 1):
        industry     = rng.choice(industries)
        credit_score = float(np.clip(rng.normal(680, 100), 300, 850))
        age          = float(rng.integers(22, 65))
        years_co     = float(rng.exponential(5))
        income       = float(rng.exponential(500_000))
        credit_limit = float(np.clip(rng.normal(50_000, 20_000), 5_000, 200_000))
        outstanding  = float(rng.exponential(5_000))
        debt_ratio   = float(np.clip(outstanding / max(income, 1), 0, 1))
        base_bad     = rng.random() < 0.25
        base_late    = 0.60 if base_bad else 0.10
        base_delay   = rng.exponential(30 if base_bad else 5)
        n_inv        = int(rng.integers(6, 22))

        hist_paid_ratio = 0.75
        hist_late_ratio = 0.15
        hist_avg_delay  = 0.10
        hist_paid3      = [0.75, 0.75, 0.75]
        hist_paid6      = [0.75] * 6
        hist_late3      = [0.15, 0.15, 0.15]
        last_paid_val   = 0.75
        last_late_val   = 0.15
        max_delay_hist  = 0.0
        delay_list      = []
        streak_late     = 0
        streak_good     = 0

        for inv_idx in range(n_inv):
            month       = int(rng.integers(1, 13))
            amount      = float(rng.exponential(150_000))
            inv_freq    = float(np.clip(rng.normal(0.4, 0.15), 0.05, 1.0))
            days_to_due = float(rng.integers(15, 90))
            late_prob   = float(np.clip(base_late + rng.normal(0, 0.05), 0.02, 0.98))
            is_late     = rng.random() < late_prob
            delay_days  = float(abs(rng.normal(base_delay, base_delay * 0.5 + 2))) if is_late else -float(rng.exponential(5))

            label      = int(delay_days > 30)
            delay_norm = min(max(delay_days, 0) / 90, 1.0)

            d_var       = float(np.std(delay_list)) if len(delay_list) > 1 else 0.05
            p_volatility= hist_late_ratio * (1.0 - hist_paid_ratio)
            max_d_norm  = max(delay_list) if delay_list else 0.0

            rows.append({
                "customer_id":                   f"CUST-{cust_id:06d}",
                "invoice_month":                 month,
                "invoice_seq":                   inv_idx,
                "age":                           age,
                "years_with_company":            years_co,
                "income_revenue":                income,
                "credit_score":                  credit_score,
                "credit_limit":                  credit_limit,
                "outstanding_balance":           outstanding,
                "debt_ratio":                    debt_ratio,
                "invoice_amount":                amount,
                "invoice_frequency":             inv_freq,
                "industry":                      industry,
                "business_type":                 "B2B",
                "days_to_due":                   days_to_due,
                "days_since_last_payment":       30.0,
                "hist_paid_ratio":               hist_paid_ratio,
                "hist_late_ratio":               hist_late_ratio,
                "hist_avg_delay_normalized":     hist_avg_delay,
                "hist_paid_ratio_3":             float(np.mean(hist_paid3[-3:])),
                "hist_paid_ratio_6":             float(np.mean(hist_paid6[-6:])),
                "hist_late_ratio_3":             float(np.mean(hist_late3[-3:])),
                "last_paid":                     last_paid_val,
                "last_late":                     last_late_val,
                "hist_max_delay":                max_d_norm,
                "delay_variance":                min(d_var, 1.0),
                "payment_volatility":            p_volatility,
                "late_streak":                   min(streak_late / 10, 1.0),
                "good_streak":                   min(streak_good / 10, 1.0),
                "invoice_frequency_trend":       0.5,
                "payment_velocity":              0.5,
                "days_since_last_payment_norm":  0.30,
                "hist_payment_count_normalized": min(inv_idx / 20, 1.0),
                "is_bad_payer":                  label,
            })

            paid_val       = 1.0 if delay_days <= 0 else 0.0
            late_val       = 0.0 if delay_days <= 0 else 1.0
            hist_paid_ratio= 0.9 * hist_paid_ratio + 0.1 * paid_val
            hist_late_ratio= 0.9 * hist_late_ratio + 0.1 * late_val
            hist_avg_delay = 0.9 * hist_avg_delay  + 0.1 * delay_norm
            hist_paid3.append(paid_val); hist_paid6.append(paid_val)
            hist_late3.append(late_val)
            last_paid_val  = paid_val; last_late_val = late_val
            delay_list.append(delay_norm)
            if max_d_norm > 0: max_delay_hist = max(max_delay_hist, delay_norm)
            streak_late = streak_late + 1 if late_val > 0.5 else 0
            streak_good = streak_good + 1 if paid_val >= 0.9 else 0

    df = pd.DataFrame(rows)
    df = df.sort_values(["customer_id", "invoice_seq"]).reset_index(drop=True)
    log.info("   Total invoices: %d | Bad payer rate: %.1f%%",
             len(df), df["is_bad_payer"].mean() * 100)

    X, feature_names = build_feature_matrix(df)
    y      = df["is_bad_payer"].values
    months = df["invoice_month"].values
    return X, y, months, feature_names, df


# ══════════════════════════════════════════════════════════════════════════════
# 3. HISTORICAL FEATURES — zero-leakage rolling windows (shift=1)
# ══════════════════════════════════════════════════════════════════════════════

def build_historical_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    cid_col  = "customer_id" if "customer_id" in df.columns else None
    df["__cid__"] = df[cid_col].astype(str) if cid_col else df.index.astype(str)

    if "invoice_seq" in df.columns:
        df["__tidx__"] = df["invoice_seq"].astype(int)
    elif "invoice_date" in df.columns:
        df["__tidx__"] = df.groupby("__cid__").cumcount()
    else:
        df["__tidx__"] = range(len(df))

    df = df.sort_values(["__cid__", "__tidx__"], kind="stable").reset_index(drop=True)

    paid_series  = (df["_is_late_hist"].fillna(0.0) < 0.5).astype(float) \
                   if "_is_late_hist" in df.columns else pd.Series(0.75, index=df.index)
    late_series  = df["_is_late_hist"].fillna(0.0) \
                   if "_is_late_hist" in df.columns else pd.Series(0.15, index=df.index)
    delay_series = df["_delay_norm_hist"].fillna(0.0) \
                   if "_delay_norm_hist" in df.columns else pd.Series(0.10, index=df.index)

    df["__paid__"]  = paid_series.astype(float)
    df["__late__"]  = late_series.astype(float)
    df["__delay__"] = delay_series.astype(float)

    g = df.groupby("__cid__")

    df["hist_paid_ratio"]           = g["__paid__"] .transform(lambda x: x.shift(1).expanding().mean())
    df["hist_late_ratio"]           = g["__late__"] .transform(lambda x: x.shift(1).expanding().mean())
    df["hist_avg_delay_normalized"] = g["__delay__"].transform(lambda x: x.shift(1).expanding().mean())

    df["hist_paid_ratio_3"]  = g["__paid__"].transform(lambda x: x.shift(1).rolling(3,  min_periods=1).mean())
    df["hist_paid_ratio_6"]  = g["__paid__"].transform(lambda x: x.shift(1).rolling(6,  min_periods=1).mean())
    df["hist_late_ratio_3"]  = g["__late__"].transform(lambda x: x.shift(1).rolling(3,  min_periods=1).mean())

    df["paid_trend"] = (df["hist_paid_ratio"]   - df["hist_paid_ratio_3"]).clip(-1, 1)
    df["late_trend"] = (df["hist_late_ratio_3"] - df["hist_late_ratio"]).clip(-1, 1)

    df["last_paid"]      = g["__paid__"].transform(lambda x: x.shift(1))
    df["last_late"]      = g["__late__"].transform(lambda x: x.shift(1))
    df["hist_max_delay"] = g["__delay__"].transform(lambda x: x.shift(1).expanding().max())

    df["delay_variance"] = g["__delay__"].transform(
        lambda x: x.shift(1).expanding().std().fillna(0)
    ).clip(0, 1)

    def _late_streak(series):
        shifted = (series.shift(1) > 0.5).astype(int)
        streak  = shifted * 0; cur = 0
        for i in range(len(shifted)):
            cur = cur + 1 if shifted.iloc[i] == 1 else 0
            streak.iloc[i] = cur
        max_s = streak.max()
        return (streak / max_s) if max_s > 0 else streak

    def _good_streak(series):
        shifted = (series.shift(1) >= 0.9).astype(int)
        streak  = shifted * 0; cur = 0
        for i in range(len(shifted)):
            cur = cur + 1 if shifted.iloc[i] == 1 else 0
            streak.iloc[i] = cur
        max_s = streak.max()
        return (streak / max_s) if max_s > 0 else streak

    df["late_streak"] = g["__late__"].transform(_late_streak)
    df["good_streak"] = g["__paid__"].transform(_good_streak)

    if "invoice_frequency" not in df.columns:
        if "invoice_date" in df.columns:
            df["invoice_frequency"] = (
                g["invoice_date"].transform(lambda x: (x - x.shift(1)).dt.days)
                .fillna(30).clip(1, 365).rdiv(30).clip(0, 1)
            )
        else:
            df["invoice_frequency"] = 0.40

    df["invoice_frequency_trend"] = g["invoice_frequency"].transform(
        lambda x: (x.shift(1).expanding().mean() - x.shift(2).expanding().mean())
    ).fillna(0).clip(-1, 1) * 0.5 + 0.5

    df["payment_velocity"] = (
        g["__tidx__"].transform(lambda x: x.diff().shift(1).expanding().mean())
        .fillna(1).clip(0, 24) / 24
    )

    if "days_since_last_payment" in df.columns:
        df["days_since_last_payment_norm"] = (
            df["days_since_last_payment"].clip(0, 365) / 365
        )
    else:
        df["days_since_last_payment_norm"] = 0.30

    df["__hist_cnt__"] = g.cumcount()
    max_cnt = max(df["__hist_cnt__"].quantile(0.99), 1)
    df["hist_payment_count_normalized"] = (df["__hist_cnt__"] / max_cnt).clip(0, 1)

    first_inv = (df["hist_payment_count_normalized"] == 0).sum()
    log.info("   First invoices (no history): %d (%.1f%%)",
             first_inv, 100 * first_inv / len(df))

    for col, default in HIST_DEFAULTS.items():
        if col in df.columns:
            df[col] = df[col].fillna(default)

    df.drop(columns=[c for c in df.columns if c.startswith("__")], inplace=True, errors="ignore")
    df.drop(columns=["_is_late_hist", "_delay_norm_hist"], inplace=True, errors="ignore")
    return df


# ══════════════════════════════════════════════════════════════════════════════
# 4. FEATURE MATRIX
# ══════════════════════════════════════════════════════════════════════════════

def _credit_bucket(credit: np.ndarray) -> np.ndarray:
    b = np.zeros_like(credit)
    b[credit >= 0.40] = 1
    b[credit >= 0.55] = 2
    b[credit >= 0.70] = 3
    b[credit >= 0.85] = 4
    return b / 4.0


def build_feature_matrix(df: pd.DataFrame) -> tuple[np.ndarray, list[str]]:

    def _get(col, default=0.0):
        if col in df.columns:
            return df[col].fillna(default).astype(float).clip(0, 1).values
        return np.full(len(df), float(default))

    def _raw_num(col, default=0.0):
        if col in df.columns:
            return pd.to_numeric(df[col], errors="coerce").fillna(default).values
        return np.full(len(df), float(default))

    def _raw_str(col, default="unknown"):
        if col in df.columns:
            return df[col].fillna(default).astype(str).values
        return np.full(len(df), default, dtype=object)

    amount_norm  = (_raw_num("invoice_amount", 50_000) / 500_000).clip(0, 1)
    age_norm     = (_raw_num("age", 35) / 80).clip(0, 1)
    years_norm   = (_raw_num("years_with_company", 3) / 30).clip(0, 1)
    inv_freq     = _get("invoice_frequency", 0.40)
    ind_risk     = np.vectorize(lambda x: INDUSTRY_RISK.get(str(x).lower(), 0.40))(
                       _raw_str("industry", "unknown"))
    seasonal     = np.vectorize(lambda m: SEASONAL_RISK.get(int(m), 0.35))(
                       _raw_num("invoice_month", 6).astype(int))
    biz_risk     = np.vectorize(lambda x: BUSINESS_TYPE_RISK.get(str(x).lower(), 0.35))(
                       _raw_str("business_type", "unknown"))
    days_to_due  = (_raw_num("days_to_due", 30) / 90).clip(0, 1)

    credit_raw   = _raw_num("credit_score", 650)
    credit_norm  = (credit_raw / 850).clip(0, 1)
    credit_buck  = _credit_bucket(credit_norm)
    outstanding  = _raw_num("outstanding_balance", 0)
    credit_limit = _raw_num("credit_limit", 50_000)
    credit_util  = np.where(credit_limit > 0, outstanding / credit_limit, 0.5).clip(0, 1)
    debt_ratio   = _raw_num("debt_ratio", 0.2).clip(0, 1)
    credit_x_ind = np.clip((1 - credit_norm) * ind_risk, 0, 1)

    income      = _raw_num("income_revenue", 300_000)
    income_norm = (income / 5_000_000).clip(0, 1)
    inv_amount  = _raw_num("invoice_amount", 50_000)
    inv_to_inc  = np.where(income > 0, inv_amount / income, 0.5).clip(0, 1)
    bal_to_inc  = np.where(income > 0, outstanding / income, 0.5).clip(0, 1)

    h_paid   = _get("hist_paid_ratio",               0.75)
    h_late   = _get("hist_late_ratio",               0.15)
    h_delay  = _get("hist_avg_delay_normalized",     0.10)
    h_cnt    = _get("hist_payment_count_normalized", 0.00)
    h_paid3  = _get("hist_paid_ratio_3",             0.75)
    h_paid6  = _get("hist_paid_ratio_6",             0.75)
    h_late3  = _get("hist_late_ratio_3",             0.15)
    p_trend  = _get("paid_trend",  0.00) * 0.5 + 0.5
    l_trend  = _get("late_trend",  0.00) * 0.5 + 0.5
    last_p   = _get("last_paid",   0.75)
    last_l   = _get("last_late",   0.15)
    max_d    = _get("hist_max_delay",    0.05)
    d_var    = _get("delay_variance",    0.05)
    l_streak = _get("late_streak",  0.00)
    g_streak = _get("good_streak",  0.50)
    freq_trnd= _get("invoice_frequency_trend", 0.50)
    velocity = _get("payment_velocity",        0.50)
    days_lpn = _get("days_since_last_payment_norm", 0.30)

    credit_x_late = np.clip((1 - credit_norm) * h_late, 0, 1)
    amount_x_risk = np.clip(amount_norm * ind_risk, 0, 1)
    clv_proxy     = np.clip(amount_norm * years_norm * inv_freq, 0, 1)
    recovery      = np.clip(1.0 - (h_paid - h_paid3), 0, 1)
    pay_volatility= np.clip(h_late * (1 - h_paid), 0, 1)

    risk_composite = np.clip(
        0.25 * h_late +
        0.15 * (1 - credit_norm) +
        0.15 * ind_risk +
        0.15 * h_delay +
        0.12 * credit_util +
        0.10 * debt_ratio +
        0.08 * seasonal, 0, 1
    )
    behavioral_score = np.clip(
        0.30 * h_late +
        0.20 * l_streak +
        0.15 * d_var +
        0.15 * (1 - h_paid) +
        0.10 * max_d +
        0.10 * l_trend, 0, 1
    )

    feature_names = (
        BASE_FEATURES + CREDIT_FEATURES + INCOME_FEATURES +
        BEHAVIORAL_FEATURES + ENGINEERED_FEATURES
    )

    X = np.column_stack([
        amount_norm, age_norm, years_norm, inv_freq,
        ind_risk, seasonal, biz_risk, days_to_due,
        credit_norm, credit_buck, credit_util, debt_ratio, credit_x_ind,
        income_norm, inv_to_inc, bal_to_inc,
        h_paid, h_late, h_paid3, h_paid6, h_late3,
        p_trend, l_trend,
        last_p, last_l,
        max_d, h_delay,
        d_var, pay_volatility,
        l_streak, g_streak,
        freq_trnd, velocity,
        days_lpn, h_cnt,
        risk_composite, amount_x_risk, clv_proxy, recovery, behavioral_score, credit_x_late,
    ])
    return X.astype(np.float64), feature_names


# ══════════════════════════════════════════════════════════════════════════════
# 5. LEAKAGE GUARD
# ══════════════════════════════════════════════════════════════════════════════

def validate_no_leakage(X: np.ndarray, y: np.ndarray,
                        feature_names: list[str],
                        max_auc: float = 0.85) -> bool:
    from sklearn.metrics import roc_auc_score
    log.info("\n🔍 Leakage check (hard limit AUC > %.2f → abort training)...", max_auc)
    suspicious = []
    for i, name in enumerate(feature_names):
        try:
            auc = roc_auc_score(y, X[:, i])
            auc = max(auc, 1 - auc)
            if auc > 0.70:
                status = "🔴" if auc > max_auc else ("🟡" if auc > 0.75 else "🟢")
                log.info("   %s %-48s AUC=%.3f", status, name, auc)
            if auc > max_auc:
                suspicious.append((name, round(auc, 4)))
        except Exception:
            pass

    if suspicious:
        log.error("   ❌ LEAKAGE DETECTED — aborting training:")
        for n, a in suspicious:
            log.error("      %s: %.3f", n, a)
        raise ValueError(
            f"Leakage detected in features: {suspicious}\n"
            "Remove any feature derived from payment_date/payment_delay."
        )
    log.info("   ✅ No leakage (all features AUC ≤ %.2f)", max_auc)
    return True


# ══════════════════════════════════════════════════════════════════════════════
# 6. PREPROCESSING
# ══════════════════════════════════════════════════════════════════════════════

def safe_preprocess(X: np.ndarray) -> np.ndarray:
    X = X.copy().astype(np.float64)
    X[~np.isfinite(X)] = np.nan
    for c in range(X.shape[1]):
        mask = np.isnan(X[:, c])
        if mask.any():
            X[mask, c] = np.nanmedian(X[:, c])
    for c in range(X.shape[1]):
        q1, q3 = np.percentile(X[:, c], [5, 95])
        X[:, c] = np.clip(X[:, c], q1 - 3 * (q3 - q1), q3 + 3 * (q3 - q1))
    return X


# ══════════════════════════════════════════════════════════════════════════════
# 7. TIME-BASED SPLIT
# ══════════════════════════════════════════════════════════════════════════════

def time_based_split(X, y, months=None, val_ratio=0.10, test_ratio=0.20):
    n = len(X)
    if months is not None:
        order = np.argsort(months, kind="stable")
        X, y  = X[order], y[order]

    te_start = int(n * (1 - test_ratio))
    va_start = int(n * (1 - test_ratio - val_ratio))

    X_tr = X[:va_start];  y_tr = y[:va_start]
    X_va = X[va_start:te_start]; y_va = y[va_start:te_start]
    X_te = X[te_start:];  y_te = y[te_start:]

    log.info("   ⏱️  3-way split: train=%d | val=%d | test=%d",
             len(X_tr), len(X_va), len(X_te))
    return X_tr, X_va, X_te, y_tr, y_va, y_te


# ══════════════════════════════════════════════════════════════════════════════
# 8. SMOTE
# ══════════════════════════════════════════════════════════════════════════════

def apply_smote(X, y):
    neg, pos = (y == 0).sum(), (y == 1).sum()
    ratio = neg / max(pos, 1)
    if ratio < 1.5:
        log.info("   Class balance OK — skipping SMOTE")
        return X, y
    try:
        from imblearn.over_sampling import SMOTE
        target = min(0.40, pos / neg * 2.5)
        sm = SMOTE(sampling_strategy=target, random_state=RANDOM_SEED, k_neighbors=5)
        X_r, y_r = sm.fit_resample(X, y)
        log.info("   SMOTE: %d → %d | bad: %.1f%% → %.1f%%",
                 len(X), len(X_r), y.mean() * 100, y_r.mean() * 100)
        return X_r, y_r
    except ImportError:
        log.warning("   imbalanced-learn not installed — class_weight used instead")
        return X, y


# ══════════════════════════════════════════════════════════════════════════════
# 9. OPTUNA TUNING
# ══════════════════════════════════════════════════════════════════════════════

def tune_hyperparameters(X, y, n_trials=50):
    try:
        import optuna
        from xgboost import XGBClassifier
        from sklearn.model_selection import StratifiedKFold, cross_val_score
    except ImportError as e:
        log.warning("Tuning skipped: %s", e)
        return {}

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    log.info("\n🔬 Optuna Tuning (%d trials)...", n_trials)

    pos_weight = (y == 0).sum() / max((y == 1).sum(), 1)
    skf = StratifiedKFold(n_splits=3, shuffle=True, random_state=RANDOM_SEED)

    def objective(trial):
        params = {
            "n_estimators":     trial.suggest_int("n_estimators", 150, 700),
            "max_depth":        trial.suggest_int("max_depth", 3, 7),
            "learning_rate":    trial.suggest_float("learning_rate", 0.01, 0.20, log=True),
            "subsample":        trial.suggest_float("subsample", 0.60, 1.00),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.50, 0.90),
            "min_child_weight": trial.suggest_int("min_child_weight", 3, 20),
            "gamma":            trial.suggest_float("gamma", 0.0, 4.0),
            "reg_alpha":        trial.suggest_float("reg_alpha", 0.5, 15.0, log=True),
            "reg_lambda":       trial.suggest_float("reg_lambda", 0.5, 15.0, log=True),
            "scale_pos_weight": pos_weight,
            "eval_metric":      "aucpr",
            "random_state":     RANDOM_SEED,
            "n_jobs":           -1,
        }
        scores = cross_val_score(
            XGBClassifier(**params), X, y,
            cv=skf, scoring="average_precision", n_jobs=-1,
        )
        trial.report(scores.mean(), step=0)
        if trial.should_prune():
            raise optuna.TrialPruned()
        return scores.mean()

    study = optuna.create_study(
        direction="maximize",
        pruner=optuna.pruners.MedianPruner(n_startup_trials=10),
        sampler=optuna.samplers.TPESampler(seed=RANDOM_SEED),
    )
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    log.info("   ✅ Best PR AUC: %.4f", study.best_value)
    return study.best_params


# ══════════════════════════════════════════════════════════════════════════════
# 10. ENSEMBLE (XGB + LGBM + LR)
# ══════════════════════════════════════════════════════════════════════════════

def build_ensemble(X_train, y_train, best_params):
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.preprocessing import StandardScaler

    pos_weight = (y_train == 0).sum() / max((y_train == 1).sum(), 1)

    try:
        from xgboost import XGBClassifier
        xgb_p = {
            "n_estimators": 400, "max_depth": 5, "learning_rate": 0.05,
            "subsample": 0.80, "colsample_bytree": 0.75,
            "min_child_weight": 5, "reg_alpha": 2.0, "reg_lambda": 3.0,
            "scale_pos_weight": pos_weight, "eval_metric": "aucpr",
            "random_state": RANDOM_SEED, "n_jobs": -1,
            **{k: v for k, v in best_params.items() if k != "scale_pos_weight"},
        }
        xgb_base = XGBClassifier(**xgb_p)
        xgb_base.fit(X_train, y_train)
        xgb_cal = CalibratedClassifierCV(xgb_base, method="isotonic", cv=5)
        xgb_cal.fit(X_train, y_train)
        log.info("   ✅ XGBoost trained & calibrated")
    except ImportError:
        from sklearn.ensemble import GradientBoostingClassifier
        xgb_base = GradientBoostingClassifier(n_estimators=200, max_depth=4, random_state=RANDOM_SEED)
        xgb_base.fit(X_train, y_train)
        xgb_cal = xgb_base
        log.warning("   XGBoost not found → GradientBoosting fallback")

    lgbm_cal = None
    try:
        import lightgbm as lgb
        lgbm_base = lgb.LGBMClassifier(
            n_estimators=500, max_depth=6, learning_rate=0.04,
            num_leaves=63, min_child_samples=25,
            reg_alpha=2.0, reg_lambda=3.0,
            scale_pos_weight=pos_weight,
            random_state=RANDOM_SEED, n_jobs=-1, verbose=-1,
        )
        lgbm_base.fit(X_train, y_train)
        lgbm_cal = CalibratedClassifierCV(lgbm_base, method="isotonic", cv=5)
        lgbm_cal.fit(X_train, y_train)
        log.info("   ✅ LightGBM trained & calibrated")
    except Exception as e:
        log.warning("   LightGBM failed: %s", e)

    lr_cal = None
    try:
        from sklearn.linear_model import LogisticRegression
        scaler  = StandardScaler()
        X_sc    = scaler.fit_transform(X_train)
        lr_base = LogisticRegression(
            C=0.05, class_weight="balanced", max_iter=1000,
            random_state=RANDOM_SEED, n_jobs=-1,
        )
        lr_base.fit(X_sc, y_train)
        lr_cal = {"model": lr_base, "scaler": scaler}
        log.info("   ✅ Logistic Regression trained")
    except Exception as e:
        log.warning("   LR failed: %s", e)

    if lgbm_cal and lr_cal:
        weights = (0.50, 0.35, 0.15)
    elif lgbm_cal:
        weights = (0.65, 0.35, 0.00)
    elif lr_cal:
        weights = (0.85, 0.00, 0.15)
    else:
        weights = (1.00, 0.00, 0.00)

    log.info("   Ensemble weights: XGB=%.2f LGBM=%.2f LR=%.2f", *weights)
    return {"xgb": xgb_cal, "lgbm": lgbm_cal, "lr": lr_cal,
            "weights": weights, "base_xgb": xgb_base}


def ensemble_predict_proba(ensemble, X):
    xw, lw, rw = ensemble["weights"]
    p = ensemble["xgb"].predict_proba(X)[:, 1] * xw
    if ensemble.get("lgbm") and lw > 0:
        p += ensemble["lgbm"].predict_proba(X)[:, 1] * lw
    if ensemble.get("lr") and rw > 0:
        lr = ensemble["lr"]
        X_s = lr["scaler"].transform(X)
        p  += lr["model"].predict_proba(X_s)[:, 1] * rw
    return p


# ══════════════════════════════════════════════════════════════════════════════
# 11. THRESHOLD OPTIMIZATION
# ══════════════════════════════════════════════════════════════════════════════

def optimize_threshold(y_val, y_proba_val, y_test, y_proba_test,
                       cost_fn=1000.0, cost_fp=100.0,
                       beta=2.0, fp_penalty_multiplier=5.0,
                       max_fp_rate=0.12):
    from sklearn.metrics import confusion_matrix, fbeta_score

    cost_fp_effective = cost_fp * fp_penalty_multiplier
    best_thresh = 0.40
    best_score  = -1e9

    for t in np.arange(0.15, 0.91, 0.01):
        yp = (y_proba_val >= t).astype(int)
        tn, fp, fn, tp = confusion_matrix(y_val, yp).ravel()
        cost  = fn * cost_fn + fp * cost_fp_effective
        fbeta = fbeta_score(y_val, yp, beta=beta, zero_division=0)
        fp_r  = fp / max(tn + fp, 1)
        fp_penalty = max(0, (fp_r - max_fp_rate) * 10)
        score = fbeta - (cost / (cost_fn * max(y_val.sum(), 1))) * 0.3 - fp_penalty
        if score > best_score:
            best_score, best_thresh = score, t

    for t in np.arange(best_thresh, 0.91, 0.01):
        yp  = (y_proba_val >= t).astype(int)
        tn, fp, fn, tp = confusion_matrix(y_val, yp).ravel()
        fp_r = fp / max(tn + fp, 1)
        if fp_r <= max_fp_rate:
            best_thresh = t
            break

    yp_test = (y_proba_test >= best_thresh).astype(int)
    tn_t, fp_t, fn_t, tp_t = confusion_matrix(y_test, yp_test).ravel()
    final_cost = fn_t * cost_fn + fp_t * cost_fp_effective
    fp_rate    = fp_t / max((y_test == 0).sum(), 1)

    log.info("   ✅ Optimal threshold=%.2f | FP-rate=%.1f%% | cost=%.0f | FP=%d FN=%d",
             best_thresh, fp_rate * 100, final_cost, fp_t, fn_t)
    return {
        "threshold":           round(float(best_thresh), 2),
        "total_cost":          round(final_cost, 2),
        "fp_rate":             round(fp_rate, 4),
        "fp_count":            int(fp_t),
        "fn_count":            int(fn_t),
        "cost_fn":             cost_fn,
        "cost_fp":             cost_fp,
        "fp_penalty_multiplier": fp_penalty_multiplier,
        "max_fp_rate_target":  max_fp_rate,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 12. CROSS VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

def run_cross_validation(model, X, y, n_folds=5):
    from sklearn.model_selection import StratifiedKFold, cross_validate
    log.info("\n🔁 Stratified %d-Fold CV...", n_folds)
    skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=RANDOM_SEED)
    scores = cross_validate(model, X, y, cv=skf,
                            scoring=["roc_auc", "average_precision", "f1", "recall"],
                            n_jobs=-1, return_train_score=True)
    results = {}
    for m in ["roc_auc", "average_precision", "f1", "recall"]:
        t = scores[f"test_{m}"]
        r = scores[f"train_{m}"]
        results[m] = {
            "test_mean":  round(float(t.mean()), 4),
            "test_std":   round(float(t.std()),  4),
            "train_mean": round(float(r.mean()), 4),
        }
        log.info("   %-20s: test=%.4f ± %.4f | train=%.4f", m, t.mean(), t.std(), r.mean())

    gap = results["roc_auc"]["train_mean"] - results["roc_auc"]["test_mean"]
    if gap > 0.05:
        log.warning("   ⚠️  Possible overfitting (gap=%.4f)", gap)
    else:
        log.info("   ✅ No significant overfitting (gap=%.4f)", gap)
    return results


# ══════════════════════════════════════════════════════════════════════════════
# 13. DECISION ENGINE — 3-tier + sub-tiers
# ══════════════════════════════════════════════════════════════════════════════

class DecisionEngine:
    MODES = DECISION_MODES

    def __init__(self, reject_threshold=0.50, review_high=0.38,
                 review_low=0.22, mode="balanced"):
        self.reject_threshold = reject_threshold
        self.review_high      = review_high
        self.review_low       = review_low
        self.mode             = mode

    @classmethod
    def from_mode(cls, mode="balanced"):
        cfg = cls.MODES.get(mode, cls.MODES["balanced"])
        return cls(
            reject_threshold=cfg["reject"],
            review_high=cfg["review_high"],
            review_low=cfg["review_low"],
            mode=mode,
        )

    def set_mode(self, mode: str):
        cfg = self.MODES.get(mode, self.MODES["balanced"])
        self.reject_threshold = cfg["reject"]
        self.review_high      = cfg["review_high"]
        self.review_low       = cfg["review_low"]
        self.mode             = mode

    def _risk_band(self, prob: float) -> str:
        if prob < 0.20:  return "low"
        if prob < 0.35:  return "medium"
        if prob < 0.55:  return "high"
        return "critical"

    def decide(self, prob: float) -> dict:
        rb = self._risk_band(prob)

        if prob >= self.reject_threshold:
            return {
                "decision":           "reject",
                "review_level":       None,
                "risk_score":         round(prob, 4),
                "risk_band":          rb,
                "confidence":         round(prob, 4),
                "mode":               self.mode,
                "recommended_action": "❌ رفض الفاتورة — مخاطرة عالية جداً",
                "reasons":            [],
            }
        elif prob >= self.review_high:
            mid  = (self.reject_threshold + self.review_high) / 2
            conf = max(0.0, 1.0 - abs(prob - mid))
            return {
                "decision":           "review",
                "review_level":       "escalate",
                "risk_score":         round(prob, 4),
                "risk_band":          rb,
                "confidence":         round(conf, 4),
                "mode":               self.mode,
                "recommended_action": "⚠️ تصعيد للمدير — يحتاج موافقة إدارية",
                "reasons":            [],
            }
        elif prob >= self.review_low:
            mid  = (self.review_high + self.review_low) / 2
            conf = max(0.0, 1.0 - abs(prob - mid))
            return {
                "decision":           "review",
                "review_level":       "monitor",
                "risk_score":         round(prob, 4),
                "risk_band":          rb,
                "confidence":         round(conf, 4),
                "mode":               self.mode,
                "recommended_action": "🟡 موافقة مع متابعة — مراقبة دورية مطلوبة",
                "reasons":            [],
            }
        else:
            return {
                "decision":           "approve",
                "review_level":       None,
                "risk_score":         round(prob, 4),
                "risk_band":          rb,
                "confidence":         round(1.0 - prob, 4),
                "mode":               self.mode,
                "recommended_action": "✅ موافقة — عميل موثوق",
                "reasons":            [],
            }

    def explain(self, result: dict, shap_values: dict,
                lang: str = "ar") -> dict:
        sorted_f = sorted(shap_values.items(), key=lambda x: abs(x[1]), reverse=True)
        reasons  = []
        for f, v in sorted_f[:5]:
            if abs(v) > 0.005 and f in FEATURE_REASON_MAP:
                reason_obj = FEATURE_REASON_MAP[f]
                reasons.append({
                    "feature":    f,
                    "impact":     round(float(v), 4),
                    "reason_ar":  reason_obj["ar"],
                    "reason_en":  reason_obj["en"],
                    "direction":  "risk" if v > 0 else "safe",
                })

        result["reasons"] = reasons or [
            {"feature": "general", "impact": 0, "reason_ar": "تقييم مخاطر عام",
             "reason_en": "General risk assessment", "direction": "neutral"}
        ]
        result["reasons_text"] = [r["reason_ar"] for r in result["reasons"]]
        return result

    def to_dict(self):
        return {
            "mode":              self.mode,
            "reject_threshold":  self.reject_threshold,
            "review_high":       self.review_high,
            "review_low":        self.review_low,
            "available_modes":   self.MODES,
            "decision_tiers":    {
                "approve":        f"score < {self.review_low}",
                "review_monitor": f"score in [{self.review_low}, {self.review_high})",
                "review_escalate":f"score in [{self.review_high}, {self.reject_threshold})",
                "reject":         f"score >= {self.reject_threshold}",
            },
        }


# ══════════════════════════════════════════════════════════════════════════════
# 14. SHAP
# ══════════════════════════════════════════════════════════════════════════════

def compute_shap(ensemble, X, feature_names):
    try:
        import shap
        log.info("\n🔍 Computing SHAP values...")
        sample = X[:min(2000, len(X))]
        base   = getattr(ensemble["base_xgb"], "estimator", ensemble["base_xgb"])
        exp    = shap.TreeExplainer(base)
        sv     = exp.shap_values(sample)
        if isinstance(sv, list):
            sv = sv[1]
        mean_abs = np.abs(sv).mean(axis=0)
        ranked   = sorted(zip(feature_names[:len(mean_abs)], mean_abs),
                          key=lambda x: x[1], reverse=True)
        result = {}
        log.info("   Top SHAP features:")
        for n, v in ranked[:15]:
            log.info("      %-48s %.4f", n, v)
            result[n] = round(float(v), 6)
        return result
    except Exception as e:
        log.warning("   SHAP failed: %s", e)
        return {}


# ══════════════════════════════════════════════════════════════════════════════
# 15. CALIBRATION
# ══════════════════════════════════════════════════════════════════════════════

def calibration_stats(y_true, y_proba, n_bins=10) -> dict:
    bins = np.linspace(0, 1, n_bins + 1)
    bin_means, bin_fracs, bin_counts = [], [], []
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (y_proba >= lo) & (y_proba < hi)
        if mask.sum() > 0:
            bin_means.append(round(float(y_proba[mask].mean()), 4))
            bin_fracs.append(round(float(y_true[mask].mean()), 4))
            bin_counts.append(int(mask.sum()))
    n   = len(y_true)
    ece = sum(cnt / n * abs(p - f)
              for cnt, p, f in zip(bin_counts, bin_means, bin_fracs))
    log.info("   📐 ECE: %.4f (good < 0.05)", ece)
    return {"ece": round(ece, 4), "bin_predicted": bin_means,
            "bin_actual": bin_fracs, "bin_counts": bin_counts}


# ══════════════════════════════════════════════════════════════════════════════
# 16. ERROR ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

def error_analysis(X_test, y_test, y_proba, y_pred, feature_names) -> dict:
    fn_mask = (y_test == 1) & (y_pred == 0)
    fp_mask = (y_test == 0) & (y_pred == 1)
    report  = {}
    for label, mask in [("false_negatives", fn_mask), ("false_positives", fp_mask)]:
        n = mask.sum()
        if n == 0:
            report[label] = {"count": 0}
            continue
        seg   = X_test[mask]
        stats = {"count": int(n), "avg_risk_score": round(float(y_proba[mask].mean()), 4)}
        for i, name in enumerate(feature_names[:seg.shape[1]]):
            diff = float(seg[:, i].mean() - X_test[:, i].mean())
            if abs(diff) > 0.07:
                stats[name] = {"diff": round(diff, 4)}
        report[label] = stats
        log.info("   %s: %d | avg_score=%.3f",
                 label.replace("_", " ").title(), n, stats["avg_risk_score"])
    return report


# ══════════════════════════════════════════════════════════════════════════════
# 17. DRIFT BASELINE
# ══════════════════════════════════════════════════════════════════════════════

def compute_drift_baseline(X, feature_names):
    return {
        n: {
            "mean":   round(float(np.mean(X[:, i])),           6),
            "std":    round(float(np.std(X[:, i])),            6),
            "p10":    round(float(np.percentile(X[:, i], 10)), 6),
            "median": round(float(np.percentile(X[:, i], 50)), 6),
            "p90":    round(float(np.percentile(X[:, i], 90)), 6),
        }
        for i, n in enumerate(feature_names[:X.shape[1]])
    }


# ══════════════════════════════════════════════════════════════════════════════
# 18. DECISION LOGGER
# ══════════════════════════════════════════════════════════════════════════════

class DecisionLogger:
    def __init__(self, decision_log_path=DECISION_LOG, override_log_path=OVERRIDE_LOG):
        self.decision_log_path = decision_log_path
        self.override_log_path = override_log_path
        os.makedirs(os.path.dirname(decision_log_path), exist_ok=True)

    def log_prediction(self, prediction_id: str, customer_id: str,
                       invoice_id: str, result: dict,
                       input_features: Optional[dict] = None) -> str:
        record = {
            "prediction_id":  prediction_id,
            "timestamp":      datetime.utcnow().isoformat() + "Z",
            "customer_id":    customer_id,
            "invoice_id":     invoice_id,
            "model_decision":  result.get("decision"),
            "review_level":   result.get("review_level"),
            "risk_score":     result.get("risk_score"),
            "risk_band":      result.get("risk_band"),
            "confidence":     result.get("confidence"),
            "mode":           result.get("mode"),
            "reasons":        result.get("reasons_text", []),
            "actual_outcome": None,
            "final_decision": None,
            "overridden":     False,
        }
        if input_features:
            safe_features = {k: v for k, v in input_features.items()
                             if k not in LEAKY_FEATURES}
            record["input_snapshot"] = safe_features

        with open(self.decision_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return prediction_id

    def log_override(self, prediction_id: str, original_decision: str,
                     override_decision: str, override_reason: str,
                     user_id: str, user_role: str = "finance_manager") -> dict:
        record = {
            "override_id":       str(uuid.uuid4()),
            "prediction_id":     prediction_id,
            "timestamp":         datetime.utcnow().isoformat() + "Z",
            "original_decision": original_decision,
            "override_decision": override_decision,
            "override_reason":   override_reason,
            "user_id":           user_id,
            "user_role":         user_role,
            "valid_decisions":   ["approve", "review", "reject"],
        }
        if override_decision not in ["approve", "review", "reject"]:
            raise ValueError("override_decision must be one of: approve, review, reject")

        with open(self.override_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        log.info("   🖊️  Override logged: %s → %s (by %s: %s)",
                 original_decision, override_decision, user_id, override_reason)
        return record

    def record_outcome(self, prediction_id: str, actual_outcome: str,
                       payment_delay_days: Optional[int] = None) -> bool:
        records = self._read_all()
        updated = False
        for r in records:
            if r.get("prediction_id") == prediction_id:
                r["actual_outcome"]      = actual_outcome
                r["payment_delay_days"]  = payment_delay_days
                r["outcome_recorded_at"] = datetime.utcnow().isoformat() + "Z"
                updated = True
                break
        if updated:
            self._write_all(records)
            log.info("   ✅ Outcome recorded for prediction %s: %s (delay=%s days)",
                     prediction_id, actual_outcome, payment_delay_days)
        return updated

    def get_model_accuracy(self) -> dict:
        records = self._read_all()
        completed = [r for r in records if r.get("actual_outcome") is not None]
        if not completed:
            return {"error": "No completed predictions with outcomes yet"}

        correct = fp_cases = fn_cases = overrides = 0
        for r in completed:
            actual_bad   = r["actual_outcome"] in ["paid_late", "defaulted"]
            model_reject = r["model_decision"] == "reject"
            if actual_bad == model_reject:
                correct += 1
            if model_reject and not actual_bad:
                fp_cases += 1
            if not model_reject and actual_bad:
                fn_cases += 1
            if r.get("overridden"):
                overrides += 1

        total = len(completed)
        return {
            "total_predictions": total,
            "accuracy":          round(correct / total, 4),
            "fp_rate":           round(fp_cases / total, 4),
            "fn_rate":           round(fn_cases / total, 4),
            "override_rate":     round(overrides / total, 4),
            "outcome_breakdown": {
                o: sum(1 for r in completed if r.get("actual_outcome") == o)
                for o in ["paid_on_time", "paid_late", "defaulted", "partial"]
            },
        }

    def _read_all(self) -> list:
        if not os.path.exists(self.decision_log_path):
            return []
        records = []
        with open(self.decision_log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return records

    def _write_all(self, records: list):
        with open(self.decision_log_path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")


# ══════════════════════════════════════════════════════════════════════════════
# 19. PRODUCTION PREDICTOR v8.1
# ══════════════════════════════════════════════════════════════════════════════

class FinanceRiskPredictorV8:
    """
    Production predictor v8.1 — Zero Leakage + 3-tier decisions + Logging.

    🔧 BUG FIX v8.1.1: _to_features() — shape guard يضمن output (1, N) دايماً:
      - لو data جاي dict → يتحول لـ DataFrame صح
      - لو data جاي numpy array بأي shape → يتعمله reshape صريح لـ (1, N)
      - safe_preprocess بتشتغل على 2D array فقط
    """

    def __init__(self, ensemble, decision_engine, feature_names,
                 shap_importance=None, metadata=None, logger=None):
        self.ensemble        = ensemble
        self.decision_engine = decision_engine
        self.feature_names   = feature_names
        self.shap_importance = shap_importance or {}
        self.metadata        = metadata or {}
        self.logger          = logger or DecisionLogger()

    def set_mode(self, mode: str):
        self.decision_engine.set_mode(mode)

    def _to_features(self, data) -> np.ndarray:
        """
        ✅ BUG FIX: يقبل dict أو numpy array ويضمن output shape (1, N) دايماً.

        المشكلة القديمة:
          pd.DataFrame([numpy_array]) → DataFrame بـ shape (1, 1) مش (1, N)
          → build_feature_matrix تنتج (1, N) مدفونة جوا array object
          → safe_preprocess تتعامل مع (1, 1, N) بدل (1, N)

        الحل:
          1. لو data numpy array → نعمل reshape مباشر ونرجع بدون DataFrame
          2. لو data dict → نعمله DataFrame صح (مش wrap في list لو فيه arrays)
        """
        # ── Guard: numpy array input ──────────────────────────────────────
        if isinstance(data, np.ndarray):
            arr = data.copy().astype(np.float64)
            # flatten أي extra dimensions: (1,1,N) أو (N,) → (1,N)
            arr = arr.reshape(1, -1) if arr.ndim != 2 else arr
            if arr.shape[0] != 1:
                # batch input — خد أول صف فقط
                arr = arr[:1, :]
            return safe_preprocess(arr)

        # ── Leakage guard (dict only) ─────────────────────────────────────
        if isinstance(data, dict):
            for lf in LEAKY_FEATURES:
                if lf in data:
                    raise ValueError(
                        f"Field '{lf}' is future information — leakage guard rejected it. "
                        "Remove from input."
                    )

        # ── Convert dict → DataFrame safely ──────────────────────────────
        # نتأكد إن كل value scalar أو list (مش numpy array) عشان pd.DataFrame ميعملش wrap غلط
        if isinstance(data, dict):
            safe_data = {}
            for k, v in data.items():
                if isinstance(v, np.ndarray):
                    # scalar extraction: (1,) → float, (1,1) → float
                    v_flat = v.flatten()
                    safe_data[k] = [float(v_flat[0])] if len(v_flat) > 0 else [0.0]
                else:
                    safe_data[k] = [v]
            df = pd.DataFrame(safe_data)
        else:
            df = pd.DataFrame([data])

        if "invoice_month" not in df.columns and "invoice_date" in df.columns:
            df["invoice_month"] = pd.to_datetime(df["invoice_date"]).dt.month

        if "days_to_due" not in df.columns:
            if "due_date" in df.columns and "invoice_date" in df.columns:
                df["days_to_due"] = (
                    pd.to_datetime(df["due_date"]) - pd.to_datetime(df["invoice_date"])
                ).dt.days.clip(0, 180)
            else:
                df["days_to_due"] = 30.0

        for col, default in HIST_DEFAULTS.items():
            if col not in df.columns:
                df[col] = default

        if "invoice_frequency" not in df.columns:
            df["invoice_frequency"] = 0.40
        if "days_since_last_payment" not in df.columns:
            df["days_since_last_payment"] = 30.0

        X, _ = build_feature_matrix(df)

        # ── Final shape guard ─────────────────────────────────────────────
        # build_feature_matrix بترجع (n_rows, n_features) — نضمن 2D
        if X.ndim != 2:
            X = X.reshape(1, -1)
        elif X.shape[0] == 0:
            raise ValueError("_to_features: empty feature matrix produced from input data")

        return safe_preprocess(X)

    def predict(self, data,
                customer_id: str = "unknown",
                invoice_id:  str = "unknown",
                log_decision: bool = True,
                lang: str = "ar") -> dict:
        X    = self._to_features(data)
        prob = float(ensemble_predict_proba(self.ensemble, X)[0])
        res  = self.decision_engine.decide(prob)
        res  = self.decision_engine.explain(res, self.shap_importance, lang=lang)

        pred_id = str(uuid.uuid4())
        res["prediction_id"] = pred_id

        if log_decision and isinstance(data, dict):
            self.logger.log_prediction(
                prediction_id=pred_id,
                customer_id=str(customer_id),
                invoice_id=str(invoice_id),
                result=res,
                input_features=data,
            )

        return res

    def override(self, prediction_id: str,
                 override_decision: str,
                 reason: str,
                 user_id: str,
                 user_role: str = "finance_manager") -> dict:
        records = self.logger._read_all()
        original = next((r for r in records if r.get("prediction_id") == prediction_id), None)
        if not original:
            raise ValueError(f"Prediction {prediction_id} not found in logs")
        return self.logger.log_override(
            prediction_id=prediction_id,
            original_decision=original["model_decision"],
            override_decision=override_decision,
            override_reason=reason,
            user_id=user_id,
            user_role=user_role,
        )

    def record_outcome(self, prediction_id: str,
                       actual_outcome: str,
                       payment_delay_days: Optional[int] = None) -> bool:
        return self.logger.record_outcome(
            prediction_id=prediction_id,
            actual_outcome=actual_outcome,
            payment_delay_days=payment_delay_days,
        )

    def get_accuracy_stats(self) -> dict:
        return self.logger.get_model_accuracy()

    def predict_raw(self, X: np.ndarray) -> np.ndarray:
        return ensemble_predict_proba(self.ensemble, safe_preprocess(X))

    def predict_batch(self, data_list: list,
                      customer_ids: Optional[list] = None,
                      invoice_ids:  Optional[list] = None,
                      log_decisions: bool = True) -> list:
        results = []
        for i, d in enumerate(data_list):
            cid = customer_ids[i] if customer_ids else "unknown"
            iid = invoice_ids[i]  if invoice_ids  else "unknown"
            results.append(self.predict(d, customer_id=cid,
                                        invoice_id=iid,
                                        log_decision=log_decisions))
        return results

    def get_info(self) -> dict:
        return {
            "version":         "8.1.1",
            "feature_count":   len(self.feature_names),
            "feature_names":   self.feature_names,
            "decision_engine": self.decision_engine.to_dict(),
            "trained_at":      self.metadata.get("trained_at"),
            "metrics":         self.metadata.get("metrics", {}),
            "ensemble":        self.metadata.get("ensemble_weights"),
            "leakage_guard":   "enabled — rejects overdue_days/payment_delay at inference",
            "decision_tiers":  "3-tier: approve / review (monitor|escalate) / reject",
            "logging":         f"decisions → {DECISION_LOG} | overrides → {OVERRIDE_LOG}",
            "bug_fixes": {
                "v8.1.1": "_to_features shape guard: numpy array input → reshape(1,-1) before safe_preprocess",
            },
        }


# ══════════════════════════════════════════════════════════════════════════════
# 20. MAIN TRAINING PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

def train(X_raw, y, months, feature_names, best_params,
          n_folds=5, cost_fn=1000.0, cost_fp=100.0,
          fp_penalty_multiplier=5.0, max_fp_rate=0.12,
          decision_mode="balanced", dry_run=False,
          max_leakage_auc=0.85):
    from sklearn.metrics import (
        roc_auc_score, average_precision_score, brier_score_loss,
        precision_score, recall_score, f1_score, accuracy_score,
        classification_report, confusion_matrix, fbeta_score,
    )

    log.info("\n%s", "=" * 65)
    log.info("  🏋️  Finance Risk Model v8.1.1 | %d samples | %d features",
             len(X_raw), X_raw.shape[1])
    log.info("  ✅ Leakage-free | 3-tier decisions | FP penalty x%.1f",
             fp_penalty_multiplier)
    log.info("%s", "=" * 65)

    X = safe_preprocess(X_raw)
    if dry_run:
        log.info("🔵 Dry run — pipeline OK")
        return {}

    validate_no_leakage(X, y, feature_names, max_auc=max_leakage_auc)

    log.info("\n⏱️  3-way time split...")
    X_tr, X_va, X_te, y_tr, y_va, y_te = time_based_split(X, y, months=months)

    log.info("\n⚖️  SMOTE on train set...")
    X_tr_r, y_tr_r = apply_smote(X_tr, y_tr)

    log.info("\n📦 Building ensemble (XGB + LGBM + LR)...")
    ensemble = build_ensemble(X_tr_r, y_tr_r, best_params)

    # ── v8.2: Save feature columns for inference alignment ───────────────
    try:
        import pickle as _pickle
        _fc_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "models", "finance", "finance_feature_columns.pkl")
        os.makedirs(os.path.dirname(_fc_path), exist_ok=True)
        with open(_fc_path, "wb") as _fc_f:
            _pickle.dump(feature_names, _fc_f)
        log.info("✅ [v8.2] Feature columns saved: %d → %s", len(feature_names), _fc_path)
    except Exception as _fc_err:
        log.error("❌ [v8.2] Failed to save feature columns: %s", _fc_err)

    cv_results = run_cross_validation(ensemble["xgb"], X_tr_r, y_tr_r, n_folds)

    y_proba_va = ensemble_predict_proba(ensemble, X_va)
    y_proba_te = ensemble_predict_proba(ensemble, X_te)
    y_pred_50  = (y_proba_te >= 0.50).astype(int)

    roc_auc   = roc_auc_score(y_te, y_proba_te)
    pr_auc    = average_precision_score(y_te, y_proba_te)
    brier     = brier_score_loss(y_te, y_proba_te)
    f1_50     = f1_score(y_te, y_pred_50, zero_division=0)
    recall_50 = recall_score(y_te, y_pred_50, zero_division=0)

    log.info("\n📊 Test @ threshold=0.50: ROC=%.4f PR=%.4f Brier=%.4f F1=%.4f Recall=%.4f",
             roc_auc, pr_auc, brier, f1_50, recall_50)

    if roc_auc > 0.98:
        log.warning("   ⚠️  ROC AUC=%.4f suspiciously high — double-check for leakage!", roc_auc)
    if roc_auc > 0.999:
        raise ValueError(f"ROC AUC={roc_auc:.4f} is 1.0 — leakage signal. Training aborted.")

    log.info("\n📐 Calibration...")
    cal_stats = calibration_stats(y_te, y_proba_te)

    log.info("\n💰 Threshold optimization (FP penalty x%.1f, max_fp_rate=%.0f%%)...",
             fp_penalty_multiplier, max_fp_rate * 100)
    cost_result = optimize_threshold(
        y_va, y_proba_va, y_te, y_proba_te,
        cost_fn=cost_fn, cost_fp=cost_fp,
        fp_penalty_multiplier=fp_penalty_multiplier,
        max_fp_rate=max_fp_rate,
    )
    ct        = cost_result["threshold"]
    y_pred_ct = (y_proba_te >= ct).astype(int)

    prec_ct = precision_score(y_te, y_pred_ct, zero_division=0)
    rec_ct  = recall_score(y_te, y_pred_ct, zero_division=0)
    f1_ct   = f1_score(y_te, y_pred_ct, zero_division=0)
    fb_ct   = fbeta_score(y_te, y_pred_ct, beta=2, zero_division=0)
    acc_ct  = accuracy_score(y_te, y_pred_ct)
    cm      = confusion_matrix(y_te, y_pred_ct)
    fp_rate = cm[0, 1] / max(cm[0].sum(), 1)

    log.info("   @ threshold=%.2f: P=%.4f R=%.4f F1=%.4f Fbeta2=%.4f FP-rate=%.1f%%",
             ct, prec_ct, rec_ct, f1_ct, fb_ct, fp_rate * 100)
    log.info("   CM: TN=%d FP=%d FN=%d TP=%d", cm[0,0], cm[0,1], cm[1,0], cm[1,1])

    decision_engine = DecisionEngine.from_mode(decision_mode)
    tiers = {"approve": 0, "review_monitor": 0, "review_escalate": 0, "reject": 0}
    for p in y_proba_te:
        res = decision_engine.decide(float(p))
        key = res["decision"] if res["decision"] != "review" else f"review_{res['review_level']}"
        tiers[key] = tiers.get(key, 0) + 1
    total_te = len(y_proba_te)
    log.info("\n   📊 3-tier breakdown (test set):")
    for k, v in tiers.items():
        log.info("      %-20s: %4d (%.1f%%)", k, v, 100*v/max(total_te,1))

    shap_imp     = compute_shap(ensemble, X_te, feature_names)
    err_analysis = error_analysis(X_te, y_te, y_proba_te, y_pred_ct, feature_names)
    cls_report   = classification_report(y_te, y_pred_ct,
                                         target_names=["Good Payer", "Bad Payer"])

    report_lines = [
        "=" * 65,
        "  Finance Risk Model v8.1.1 — Production Training Report",
        f"  Generated: {datetime.utcnow().isoformat()} UTC",
        "=" * 65,
        f"Samples:     {len(X_raw):,}  |  Features: {X_raw.shape[1]}",
        f"Bad rate:    {y.mean():.1%}",
        f"Split:       3-way time-based | Ensemble: XGB+LGBM+LR",
        "",
        "── v8.1.1 Bug Fixes ─────────────────────────────────────",
        "  ✅ _to_features shape guard: numpy(1,1,N) → reshape(1,N)",
        "  ✅ dict values with ndarray → scalar extraction before DataFrame",
        "",
        "── v8.1 FP Improvements ─────────────────────────────────",
        f"  Threshold raised:  ~0.14 (v8.0) → {ct:.2f} (v8.1)",
        f"  FP penalty:        x{fp_penalty_multiplier} multiplier in optimization",
        f"  Max FP rate target: {max_fp_rate:.0%}",
        f"  3-tier decisions:  approve / review (monitor|escalate) / reject",
        "",
        f"  Tier breakdown (test set, n={total_te}):",
        f"    ✅ approve:         {tiers.get('approve', 0):5d} ({100*tiers.get('approve',0)/max(total_te,1):.1f}%)",
        f"    🟡 review/monitor:  {tiers.get('review_monitor',0):5d} ({100*tiers.get('review_monitor',0)/max(total_te,1):.1f}%)",
        f"    ⚠️  review/escalate: {tiers.get('review_escalate',0):5d} ({100*tiers.get('review_escalate',0)/max(total_te,1):.1f}%)",
        f"    ❌ reject:          {tiers.get('reject',0):5d} ({100*tiers.get('reject',0)/max(total_te,1):.1f}%)",
        "",
        "── Cross Validation ─────────────────────────────────────",
    ]
    for m, v in cv_results.items():
        report_lines.append(f"  {m:22s}: test={v['test_mean']:.4f} ± {v['test_std']:.4f}")
    report_lines += [
        "",
        "── Test Results ─────────────────────────────────────────",
        f"  ROC AUC:    {roc_auc:.4f}",
        f"  PR AUC:     {pr_auc:.4f}",
        f"  Brier:      {brier:.4f}",
        f"  ECE:        {cal_stats['ece']:.4f}",
        "",
        f"── Optimal Threshold = {ct:.2f} ──────────────────────────",
        f"  Precision:  {prec_ct:.4f}",
        f"  Recall:     {rec_ct:.4f}",
        f"  F1:         {f1_ct:.4f}",
        f"  F-beta(2):  {fb_ct:.4f}",
        f"  FP-rate:    {fp_rate:.1%}",
        f"  FP-count:   {cost_result['fp_count']}",
        f"  FN-count:   {cost_result['fn_count']}",
        f"  Cost:       {cost_result['total_cost']:,.0f}",
        "",
        "── Classification Report ────────────────────────────────",
        cls_report,
        "── Error Analysis ───────────────────────────────────────",
        f"  FN (missed bad payers): {err_analysis.get('false_negatives', {}).get('count', 0)}",
        f"  FP (wrongly rejected):  {err_analysis.get('false_positives', {}).get('count', 0)}",
    ]
    report_text = "\n".join(report_lines)
    log.info("\n" + report_text)

    # ── v8.2: Save feature columns for alignment ──────────────────────────
    try:
        with open(FEATURE_COLUMNS_PATH, "wb") as f:
            pickle.dump(feature_names, f)
        log.info("✅ Feature columns saved: %d cols → %s",
                 len(feature_names), FEATURE_COLUMNS_PATH)
    except Exception as e:
        log.error("❌ Failed to save feature columns: %s", e)

    return {
        "ensemble":        ensemble,
        "decision_engine": decision_engine,
        "cost_result":     cost_result,
        "cv_results":      cv_results,
        "shap_importance": shap_imp,
        "calibration":     cal_stats,
        "error_analysis":  err_analysis,
        "tier_breakdown":  tiers,
        "metrics": {
            "roc_auc":        round(roc_auc, 4),
            "pr_auc":         round(pr_auc, 4),
            "brier":          round(brier, 4),
            "ece":            cal_stats["ece"],
            "f1":             round(f1_50, 4),
            "recall":         round(recall_50, 4),
            "f1_cost":        round(f1_ct, 4),
            "recall_cost":    round(rec_ct, 4),
            "precision_cost": round(prec_ct, 4),
            "fbeta2_cost":    round(fb_ct, 4),
            "fp_rate":        round(fp_rate, 4),
            "accuracy_cost":  round(acc_ct, 4),
        },
        "report_text": report_text,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 21. CLI MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Finance Risk Model Training v8.1.1 — Low FP, 3-tier, Logging",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--csv",            type=str,   default=None)
    parser.add_argument("--output",         type=str,   default=None)
    parser.add_argument("--dry-run",        action="store_true")
    parser.add_argument("--n-customers",    type=int,   default=3000)
    parser.add_argument("--trials",         type=int,   default=30)
    parser.add_argument("--folds",          type=int,   default=5)
    parser.add_argument("--cost-fn",        type=float, default=1000.0)
    parser.add_argument("--cost-fp",        type=float, default=100.0)
    parser.add_argument("--fp-penalty",     type=float, default=5.0)
    parser.add_argument("--max-fp-rate",    type=float, default=0.12)
    parser.add_argument("--max-auc",        type=float, default=0.85)
    parser.add_argument("--no-smote",       action="store_true")
    parser.add_argument("--mode",           choices=["safe", "balanced", "aggressive"],
                        default="balanced")
    parser.add_argument("--bad-days",       type=int,   default=30)
    # 🌐 v8.2 — Node API data source
    parser.add_argument("--from-node-api",  action="store_true",
                        help="جرّب تجيب بيانات التدريب من Node.js ERP API الأول "
                             "(قبل CSV/synthetic)")
    parser.add_argument("--node-api-min-rows", type=int, default=50,
                        help="أقل عدد invoice rows مقبول من Node API قبل ما نعتبره "
                             "فشل ونعمل fallback")
    parser.add_argument("--node-api-page-size", type=int, default=200,
                        help="حجم الصفحة (limit) لكل pagination request للـ Node API")
    args = parser.parse_args()

    global MODEL_PATH, METADATA_PATH, REPORT_PATH, FEATURE_COLUMNS_PATH
    if args.output:
        MODEL_PATH    = args.output
        METADATA_PATH = args.output.replace(".pkl", "_metadata.json")
        REPORT_PATH   = args.output.replace(".pkl", "_report.txt")
        os.makedirs(os.path.dirname(os.path.abspath(MODEL_PATH)), exist_ok=True)
        FEATURE_COLUMNS_PATH = args.output.replace(".pkl", "_feature_columns.pkl")

    print("=" * 65)
    print("  💰 Finance Risk Model v8.1.1 — Low FP | 3-tier | Logging")
    print("=" * 65)
    print(f"  Data source:  {'Node API → CSV → synthetic' if args.from_node_api else (args.csv or 'synthetic fallback')}")
    print(f"  Mode:         {args.mode}  [{DECISION_MODES[args.mode]['description']}]")
    print(f"  Bad payer:    payment_delay > {args.bad_days} days")
    print(f"  FP Penalty:   x{args.fp_penalty} (cost_fp_effective={args.cost_fp * args.fp_penalty:.0f})")
    print(f"  Max FP rate:  {args.max_fp_rate:.0%}")
    print(f"  Folds:        {args.folds} | Optuna: {args.trials} trials")
    print(f"  SMOTE:        {'disabled' if args.no_smote else 'enabled'}")
    print("=" * 65)

    X, y, months, feature_names, df = None, None, None, None, None
    data_source = "synthetic"

    # ── 🌐 v8.2: Node API first (if requested) ────────────────────────────
    if args.from_node_api:
        result_tuple = load_from_node_api(
            limit_per_page=args.node_api_page_size,
            min_rows=args.node_api_min_rows,
        )
        if result_tuple is not None:
            X, y, months, feature_names, df = result_tuple
            data_source = "node_api"
            log.info("✅ Using Node API as training data source")
        else:
            log.warning("⚠️  Node API data unavailable/insufficient — falling back to CSV/synthetic")

    # ── CSV (explicit --csv, or fallback after failed Node API attempt) ───
    if X is None and args.csv:
        try:
            X, y, months, feature_names, df = load_and_prepare_csv(args.csv)
            data_source = "csv"
        except Exception as e:
            log.error("CSV load failed: %s", e)
            if not args.from_node_api:
                raise
            log.warning("⚠️  CSV fallback also failed — falling back to synthetic data")

    # ── Synthetic (final fallback) ─────────────────────────────────────────
    if X is None:
        log.info("No usable Node API/CSV data — using synthetic data")
        X, y, months, feature_names, df = generate_synthetic_data(
            n_customers=args.n_customers
        )
        data_source = "synthetic"

    log.info("\n📦 Dataset: %d rows | %d features | bad=%.1f%% | source=%s",
             len(X), X.shape[1], y.mean() * 100, data_source)

    best_params = {}
    if args.trials > 0 and not args.dry_run:
        best_params = tune_hyperparameters(safe_preprocess(X), y, n_trials=args.trials)

    if args.no_smote:
        global apply_smote
        apply_smote = lambda X, y: (X, y)

    result = train(
        X, y, months, feature_names,
        best_params=best_params, n_folds=args.folds,
        cost_fn=args.cost_fn, cost_fp=args.cost_fp,
        fp_penalty_multiplier=args.fp_penalty,
        max_fp_rate=args.max_fp_rate,
        decision_mode=args.mode, dry_run=args.dry_run,
        max_leakage_auc=args.max_auc,
    )

    if args.dry_run or not result:
        log.info("✅ Dry run complete")
        return

    logger = DecisionLogger()

    metadata = {
        "version":             "8.1.1",
        "trained_at":          datetime.utcnow().isoformat() + "Z",
        "data_source":          data_source,
        "n_samples":           len(X),
        "feature_count":       len(feature_names),
        "feature_names":       feature_names,
        "leakage_policy": {
            "removed_v7_features": [
                "overdue_days_normalized", "overdue_x_industry",
                "risk_composite_with_overdue",
            ],
            "guard_at_inference": list(LEAKY_FEATURES),
        },
        "fp_improvements": {
            "threshold_raised_from": "~0.14 (v8.0)",
            "threshold_now":         result["cost_result"]["threshold"],
            "fp_penalty_multiplier": args.fp_penalty,
            "max_fp_rate_target":    args.max_fp_rate,
            "three_tier_decisions":  True,
            "decision_logging":      True,
            "human_override":        True,
        },
        "bug_fixes": {
            "v8.1.1": "_to_features shape guard — numpy input reshape(1,-1) + dict ndarray scalar extraction",
        },
        "schema": {
            "csv_input_columns": [
                "customer_id", "invoice_id", "age", "gender", "location",
                "industry", "business_type", "years_with_company",
                "income_revenue", "credit_score", "credit_limit",
                "outstanding_balance", "debt_ratio", "invoice_amount",
                "invoice_date", "due_date", "payment_date",
            ],
            "target": f"is_bad_payer (payment_delay > {args.bad_days} days)",
        },
        "ensemble_weights":  result["ensemble"]["weights"],
        "decision_engine":   result["decision_engine"].to_dict(),
        "cost_optimization": result["cost_result"],
        "tier_breakdown":    result["tier_breakdown"],
        "metrics":           result["metrics"],
        "cv_results":        result["cv_results"],
        "shap_importance":   result["shap_importance"],
        "calibration":       result["calibration"],
        "error_analysis":    result["error_analysis"],
        "drift_baseline":    compute_drift_baseline(X, feature_names),
        "logging_paths": {
            "decisions": DECISION_LOG,
            "overrides":  OVERRIDE_LOG,
        },
        "training_config": {
            "n_folds": args.folds, "n_trials": args.trials,
            "smote": not args.no_smote, "time_based_split": True,
            "random_seed": RANDOM_SEED,
            "cost_fn": args.cost_fn, "cost_fp": args.cost_fp,
            "fp_penalty_multiplier": args.fp_penalty,
            "max_fp_rate_target": args.max_fp_rate,
            "bad_payer_threshold_days": args.bad_days,
            "from_node_api": args.from_node_api,
        },
    }

    predictor = FinanceRiskPredictorV8(
        ensemble=result["ensemble"],
        decision_engine=result["decision_engine"],
        feature_names=feature_names,
        shap_importance=result["shap_importance"],
        metadata=metadata,
        logger=logger,
    )

    save_data = {
        "predictor": predictor,
        "ensemble":  result["ensemble"],
        "metadata":  metadata,
    }
    try:
        import cloudpickle
        with open(MODEL_PATH, "wb") as f:
            cloudpickle.dump(save_data, f)
        log.info("✅ Model saved with cloudpickle (recommended)")
    except ImportError:
        import pickle
        with open(MODEL_PATH, "wb") as f:
            pickle.dump(save_data, f)
        log.info("✅ Model saved with pickle (install cloudpickle for better compatibility)")
    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, default=str, ensure_ascii=False)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(result["report_text"])

    log.info("✅ Model saved to training dir: %s", MODEL_PATH)

    API_MODEL_DIR = os.path.join(BASE_DIR, "..", "models", "finance")
    os.makedirs(API_MODEL_DIR, exist_ok=True)
    api_model_path    = os.path.join(API_MODEL_DIR, "payment_risk_v8.pkl")
    api_metadata_path = os.path.join(API_MODEL_DIR, "metadata_v8.json")

    import shutil
    shutil.copy2(MODEL_PATH,    api_model_path)
    shutil.copy2(METADATA_PATH, api_metadata_path)
    log.info("✅ Model copied to API dir:      %s", os.path.abspath(api_model_path))
    log.info("✅ Metadata copied to API dir:   %s", os.path.abspath(api_metadata_path))
    print("\n✅ Model saved successfully — restart FastAPI to auto-load.")

    log.info("\n🔌 Demo prediction (mode=%s):", args.mode)
    demo_input = {
        "age": 35, "years_with_company": 9,
        "income_revenue": 1_848_845, "credit_score": 660,
        "credit_limit": 49_162, "outstanding_balance": 3_618,
        "debt_ratio": 0.198, "invoice_amount": 135_244,
        "industry": "Real Estate", "business_type": "B2B",
        "invoice_month": 1, "days_to_due": 30,
        "hist_late_ratio": 0.10, "hist_paid_ratio": 0.90,
        "late_streak": 0.0, "good_streak": 0.8,
    }
    demo = predictor.predict(demo_input, customer_id="CUST-000001",
                             invoice_id="INV-001", log_decision=True)
    log.info("   %s", json.dumps(demo, indent=4, ensure_ascii=False))

    log.info("\n🖊️  Demo override (finance manager override):")
    if demo.get("decision") == "reject":
        try:
            override_rec = predictor.override(
                prediction_id=demo["prediction_id"],
                override_decision="review",
                reason="العميل لديه ضمان بنكي — يُراجع يدوياً",
                user_id="finance_manager_001",
                user_role="finance_manager",
            )
            log.info("   Override recorded: %s", override_rec["override_id"])
        except Exception as e:
            log.warning("   Override demo failed: %s", e)

    # ── v8.2: Copy feature columns to API dir ────────────────────────────
    _fc_src = os.path.join(MODEL_DIR, "finance_feature_columns.pkl")
    _fc_dst = os.path.join(API_MODEL_DIR, "finance_feature_columns.pkl")
    if os.path.exists(_fc_src):
        shutil.copy2(_fc_src, _fc_dst)
        log.info("✅ Feature columns copied to API dir: %s", _fc_dst)

    m  = result["metrics"]
    de = result["decision_engine"]
    print(f"\n{'=' * 65}")
    print(f"  ✅ Model:     {MODEL_PATH}")
    print(f"  📋 Metadata: {METADATA_PATH}")
    print(f"  📄 Report:   {REPORT_PATH}")
    print(f"  📊 Logs:     {LOG_DIR}/")
    print(f"  🗂️  Source:   {data_source}")
    print(f"{'=' * 65}")
    print(f"  ROC AUC:    {m['roc_auc']:.4f}  (realistic: 0.75–0.88)")
    print(f"  PR AUC:     {m['pr_auc']:.4f}   (realistic: 0.40–0.70)")
    print(f"  Precision:  {m['precision_cost']:.4f}   ← مهم جداً (قل FP)")
    print(f"  Recall:     {m['recall_cost']:.4f}")
    print(f"  F-beta(2):  {m['fbeta2_cost']:.4f}")
    print(f"  FP-rate:    {m['fp_rate']:.1%}     ← target < {args.max_fp_rate:.0%}")
    print(f"  FP-count:   {result['cost_result']['fp_count']}")
    print(f"  FN-count:   {result['cost_result']['fn_count']}")
    print(f"  ECE:        {m['ece']:.4f}")
    print(f"  Threshold:  {result['cost_result']['threshold']:.2f}")
    print(f"  Mode:       {de.mode}")
    print(f"{'=' * 65}")
    print(f"\n  3-tier Decision Config [{args.mode}]:")
    print(f"    ✅ approve  : score < {de.review_low:.2f}")
    print(f"    🟡 monitor  : score in [{de.review_low:.2f}, {de.review_high:.2f})")
    print(f"    ⚠️  escalate : score in [{de.review_high:.2f}, {de.reject_threshold:.2f})")
    print(f"    ❌ reject   : score >= {de.reject_threshold:.2f}")
    print(f"\n{'=' * 65}")
    print(f"\n🚀 Commands:")
    print(f"   python finance_train.py --csv data.csv")
    print(f"   python finance_train.py --from-node-api")
    print(f"   python finance_train.py --from-node-api --csv data.csv   # Node API مع CSV fallback")
    print(f"   python finance_train.py --csv data.csv --mode safe --fp-penalty 8.0")
    print(f"   python finance_train.py --csv data.csv --mode aggressive --max-fp-rate 0.20")
    print(f"   python finance_train.py --csv data.csv --mode balanced --trials 100")
    print(f"   python finance_train.py --csv data.csv --bad-days 15 --fp-penalty 5")


if __name__ == "__main__":
    main()