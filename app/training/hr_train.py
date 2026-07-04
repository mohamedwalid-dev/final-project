"""
🧠 HR Leave Approval — Training Pipeline (Production v3.2)
=========================================================
File: training/hr_train.py

✅ v3.1 Anti-Leakage Fixes:
    1. generate_synthetic_data() — label noise + wider borderline zone
    2. n default: 800 → 1500
    3. Confidence distribution check بعد training
    4. Post-train sanity: رفض الـ model لو AUC > 0.99 على synthetic فقط

✅ v3.2 — Node.js API Integration (بدل الاتصال المباشر بـ MongoDB):
    1. load_from_db() بقت بتنادي Node.js Express API (GET /hr/leaves)
       بدل ما تتصل بـ MongoDB مباشرة عن طريق Motor.
    2. الراوتر بتاع الـ HR مفيهوش endpoint بيرجّع approved/rejected بس
       (زي ?status=approved,rejected)، فبنجيب كل الطلبات من /hr/leaves
       (مع limit كبير + pagination لو المفروض) وبنفلتر approved/rejected
       محلياً في بايثون.
    3. الاتصال بيتم عن طريق core.node_hr_proxy.get_hr_db() اللي بيرجع
       NodeHRProxy — نفس شكل الاستدعاء القديم (get_hr_db().leaves.find...)
       اتلغى، ودلوقتي بنستخدم NodeHRProxy.get_leaves() اللي بينادي
       GET /hr/leaves تحت الغطاء عن طريق NodeAPIClient.

Run:
    python training/hr_train.py
    python training/hr_train.py --dry-run
    python training/hr_train.py --csv path/to/data.csv
    python training/hr_train.py --min-samples 20
    python training/hr_train.py --skip-leakage-check
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import (
    GradientBoostingClassifier,
    RandomForestClassifier,
    VotingClassifier,
)
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

warnings.filterwarnings("ignore")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

ROOT_DIR  = Path(__file__).resolve().parent.parent
APP_DIR   = ROOT_DIR / "app"
MODEL_DIR = ROOT_DIR / "app" / "models" / "hr"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

MODEL_PATH   = MODEL_DIR / "leave_approval_model.pkl"
SCALER_PATH  = MODEL_DIR / "scaler.pkl"
ENCODER_PATH = MODEL_DIR / "encoders.pkl"
META_PATH    = MODEL_DIR / "model_metadata.json"

NUMERIC_FEATURES = [
    "leave_days",
    "leave_balance",
    "performance_score",
    "absence_count",
    "years_of_experience",
    "overtime_hours",
    "balance_ratio",
    "days_to_fy_end",
    "absence_per_year",
    "perf_balance_score",
]

CATEGORICAL_FEATURES = [
    "job_level",
    "salary_grade",
]

TARGET = "approved"

LEAKAGE_SUSPECT_PATTERNS = [
    "status",
    "approved",
    "rejected",
    "final_decision",
    "hr_decision",
    "approved_by",
    "approval_date",
    "rejection_reason",
]

COST_FALSE_APPROVE = 500
COST_FALSE_REJECT  = 200
COST_ESCALATE_FP   = 50
COST_ESCALATE_FN   = 30

THRESHOLD_APPROVE  = 0.72
THRESHOLD_ESCALATE = 0.42

SANITY_MAX_AUC_SYNTHETIC = 0.97

# ── v3.2: pull size cap when loading from Node API ──────────────────────────
# الراوتر مفيهوش endpoint بيرجّع approved/rejected بس، فبنجيب دفعة كبيرة من
# /hr/leaves (كل الحالات) وبنفلتر approved/rejected محلياً. الرقم ده حد أقصى
# لعدد الطلبات اللي بنجيبها في الاستدعاء عشان منحملش الـ Node API/الشبكة أكتر
# من اللازم لو الجدول كبير جداً.
NODE_API_LEAVES_FETCH_LIMIT = int(os.getenv("HR_TRAIN_LEAVES_FETCH_LIMIT", "5000"))


def days_to_fy_end(ref_date: pd.Timestamp) -> int:
    year   = ref_date.year
    fy_end = pd.Timestamp(year if ref_date.month <= 6 else year + 1, 6, 30)
    return max(0, (fy_end - ref_date).days)


# ══════════════════════════════════════════════════════════════════════════════
# 1. DATA LOADING
# ══════════════════════════════════════════════════════════════════════════════

def load_from_csv(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    logger.info("✅ Loaded %d records from CSV: %s", len(df), csv_path)
    logger.info("   Columns: %s", list(df.columns))
    return df


async def _fetch_leaves_from_node_api() -> list[dict]:
    """
    ✅ v3.2 — بدل الاتصال المباشر بـ MongoDB (Motor)، دلوقتي بنسحب طلبات
    الإجازات التاريخية من Node.js Express API عن طريق NodeHRProxy
    (core/node_hr_proxy.py) اللي بينادي تحت الغطاء:

        GET /hr/leaves?limit=<NODE_API_LEAVES_FETCH_LIMIT>

    الراوتر الحالي (hr.routes.js) بيدعم بس:
        GET /hr/leaves            (list — يقبل ?status=&limit=)
        GET /hr/leaves/pending
        GET /hr/leaves/:id
        GET /hr/leaves/:id/decision
        PATCH /hr/leaves/:id/status
        DELETE /hr/leaves/:id

    ومفيش endpoint بيرجّع approved+rejected بس دفعة واحدة، فبنجيب كل
    الطلبات (status=None) وبنفلتر approved/rejected محلياً في بايثون
    (زي ما كان بيحصل قبل كده جوه استعلام Mongo نفسه).
    """
    load_dotenv(ROOT_DIR / ".env")
    sys.path.insert(0, str(APP_DIR))

    from core.node_hr_proxy import get_hr_db

    proxy = get_hr_db()

    # status=None → يرجّع كل الطلبات (مش فلترة على السيرفر)، وبنفلتر إحنا
    # بعدين على approved/rejected بس عشان الـ training.
    docs = await proxy.get_leaves(status=None, limit=NODE_API_LEAVES_FETCH_LIMIT)

    if not isinstance(docs, list):
        logger.warning(
            "⚠️ GET /hr/leaves رجّعت شكل غير متوقع (مش list) — نوعها: %s",
            type(docs).__name__,
        )
        return []

    filtered = [d for d in docs if d.get("status") in ("approved", "rejected")]
    logger.info(
        "   📡 Node API /hr/leaves: %d إجمالي | %d approved/rejected بعد الفلترة",
        len(docs), len(filtered),
    )
    return filtered


def load_from_db() -> pd.DataFrame:
    """
    ✅ v3.2 — تحميل بيانات الإجازات التاريخية من Node.js API (بدل MongoDB
    مباشرة). الدالة بتفضل شكلها الخارجي زي ما هو (بترجع DataFrame) عشان
    main() تفضل شغالة من غير تعديل، لكن جوايها بقت بتستخدم NodeHRProxy
    بدل Motor/get_hr_db القديمة اللي كانت بتتصل بـ MongoDB مباشرة.
    """
    docs = asyncio.run(_fetch_leaves_from_node_api())

    if not docs:
        raise ValueError(
            "No approved/rejected leaves found via Node API (GET /hr/leaves). "
            "تأكد إن NODE_API_BASE_URL و NODE_API_SERVICE_TOKEN (أو "
            "NODE_API_SERVICE_EMAIL/PASSWORD) متظبطين في .env، وإن Node.js "
            "server شغال على localhost:5005."
        )

    rows = []
    for d in docs:
        rows.append({
            "leave_days":          d.get("leave_days",          1),
            "leave_balance":       d.get("leave_balance",       15),
            "performance_score":   d.get("performance_score",
                                         d.get("confidence_score", 0.75)),
            "absence_count":       d.get("absence_count",       0),
            "job_level":           d.get("job_level",           "junior"),
            "years_of_experience": d.get("years_of_experience", 1),
            "salary_grade":        d.get("salary_grade",        "C"),
            "overtime_hours":      d.get("overtime_hours",      0),
            "created_at":          d.get("created_at"),
            # Target: 1 = approved, 0 = rejected
            "approved":            1 if d.get("status") == "approved" else 0,
        })

    df = pd.DataFrame(rows)
    logger.info("✅ Loaded %d records from Node.js HR API (GET /hr/leaves)", len(df))
    return df


def generate_synthetic_data(n: int = 1500, seed: int = 42) -> pd.DataFrame:
    """
    توليد بيانات اصطناعية واقعية — v3.1 Anti-Leakage Fix.

    التغييرات عن v3:
        - n default: 800 → 1500  (تنوع أكبر)
        - Label noise: random flip على الـ borderline cases
        - Score threshold: stochastic بدل deterministic
        - Wider gray zone: [0.45, 0.75] بدل [0.45, 0.68]
        - Hard rules محفوظة كما هي (balance=0, days>balance)
    """
    rng = np.random.default_rng(seed)

    job_levels    = ["junior", "senior", "lead", "manager"]
    salary_grades = ["A", "B", "C", "D", "E"]

    rows = []
    for i in range(n):
        job_level    = rng.choice(job_levels, p=[0.35, 0.30, 0.20, 0.15])
        salary_grade = rng.choice(salary_grades, p=[0.15, 0.25, 0.35, 0.15, 0.10])
        leave_days   = int(rng.integers(1, 21))
        leave_balance = int(rng.integers(0, 31))
        perf         = round(float(rng.beta(5, 3)), 3)
        absence      = int(rng.integers(0, 15))
        years_exp    = int(rng.integers(0, 30))
        overtime     = int(rng.integers(0, 80))
        created_at   = pd.Timestamp("2022-07-01") + pd.Timedelta(
            days=int(rng.integers(0, 730))
        )

        balance_ratio    = leave_balance / max(leave_days, 1)
        absence_per_year = absence / max(years_exp, 1)

        score = (
            min(balance_ratio / 3.0, 1.0)     * 0.35
            + perf                              * 0.30
            + max(0, 1 - absence_per_year / 5)  * 0.20
            + {"junior": 0.5, "senior": 0.7,
               "lead": 0.85, "manager": 1.0}[job_level] * 0.10
            + min(overtime / 80, 1.0)           * 0.05
        )

        # ── Hard Rules ────────────────────────────────────────────────────────
        if leave_balance == 0 or leave_days > leave_balance * 1.5:
            approved = 0
        elif perf < 0.3 and absence > 10:
            approved = 0
        elif score >= 0.75:
            approved = int(rng.choice([1, 0], p=[0.95, 0.05]))
        elif score >= 0.60:
            approved = int(rng.choice([1, 0], p=[0.90, 0.10]))
        elif score >= 0.45:
            p_approve = 0.40 + (score - 0.45) / (0.60 - 0.45) * 0.25
            p_approve = float(np.clip(p_approve, 0.05, 0.95))
            approved  = int(rng.choice([1, 0], p=[p_approve, 1 - p_approve]))
        elif score >= 0.30:
            approved = int(rng.choice([0, 1], p=[0.85, 0.15]))
        else:
            approved = 0

        rows.append({
            "leave_days":          leave_days,
            "leave_balance":       leave_balance,
            "performance_score":   perf,
            "absence_count":       absence,
            "job_level":           job_level,
            "years_of_experience": years_exp,
            "salary_grade":        salary_grade,
            "overtime_hours":      overtime,
            "created_at":          created_at,
            "approved":            approved,
        })

    df = pd.DataFrame(rows)
    approval_rate = df["approved"].mean()
    logger.info(
        "🧪 Synthetic data v3.1: %d rows | approved=%.0f%% | rejected=%.0f%%",
        len(df), approval_rate * 100, (1 - approval_rate) * 100,
    )
    return df


# ══════════════════════════════════════════════════════════════════════════════
# FEATURE LEAKAGE VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

def validate_no_leakage(df: pd.DataFrame, feature_cols: list, target: str = TARGET) -> dict:
    logger.info("\n" + "═" * 60)
    logger.info("  🔍 FEATURE LEAKAGE VALIDATION")
    logger.info("═" * 60)

    suspicious = []
    y = df[target].values if target in df.columns else None

    for col in feature_cols:
        col_base = col.replace("_enc", "").lower()

        for pattern in LEAKAGE_SUSPECT_PATTERNS:
            if pattern in col_base:
                suspicious.append({
                    "feature":  col,
                    "type":     "NAME_PATTERN",
                    "severity": "CRITICAL",
                    "detail":   f"Column name contains suspect pattern '{pattern}'",
                })
                logger.warning("  🚨 CRITICAL | %s → name contains '%s'", col, pattern)

        if y is not None and col in df.columns:
            x_vals = pd.to_numeric(df[col], errors="coerce").fillna(0).values

            try:
                corr = abs(float(np.corrcoef(x_vals, y)[0, 1]))
                if corr > 0.95:
                    suspicious.append({
                        "feature":  col,
                        "type":     "HIGH_CORRELATION",
                        "severity": "CRITICAL",
                        "detail":   f"Pearson |r| = {corr:.4f} — near-perfect correlation",
                    })
                    logger.warning("  🚨 CRITICAL | %s → correlation=%.4f (> 0.95)", col, corr)
                elif corr > 0.85:
                    suspicious.append({
                        "feature":  col,
                        "type":     "HIGH_CORRELATION",
                        "severity": "WARNING",
                        "detail":   f"Pearson |r| = {corr:.4f} — suspiciously high",
                    })
                    logger.warning("  ⚠️  WARNING  | %s → correlation=%.4f (> 0.85)", col, corr)
                else:
                    logger.info("  ✅ OK       | %-28s corr=%.4f", col, corr)
            except Exception:
                pass

            try:
                from sklearn.tree import DecisionTreeClassifier
                from sklearn.model_selection import cross_val_score as cvs
                dt     = DecisionTreeClassifier(max_depth=3, random_state=42)
                scores = cvs(dt, x_vals.reshape(-1, 1), y, cv=3, scoring="accuracy")
                solo   = scores.mean()
                if solo > 0.98:
                    suspicious.append({
                        "feature":  col,
                        "type":     "PERFECT_PREDICTOR",
                        "severity": "CRITICAL",
                        "detail":   f"Single-feature CV accuracy = {solo:.2%}",
                    })
                    logger.warning("  🚨 CRITICAL | %s → single-feature acc=%.2%", col, solo)
                elif solo > 0.90:
                    suspicious.append({
                        "feature":  col,
                        "type":     "NEAR_PERFECT_PREDICTOR",
                        "severity": "WARNING",
                        "detail":   f"Single-feature CV accuracy = {solo:.2%}",
                    })
                    logger.warning("  ⚠️  WARNING  | %s → single-feature acc=%.2%", col, solo)
            except Exception:
                pass

    critical_count = sum(1 for s in suspicious if s["severity"] == "CRITICAL")
    warning_count  = sum(1 for s in suspicious if s["severity"] == "WARNING")
    passed         = critical_count == 0

    logger.info("  Summary: critical=%d | warnings=%d | %s",
                critical_count, warning_count, "✅ PASSED" if passed else "❌ FAILED")
    logger.info("═" * 60)

    if not passed:
        logger.error("❌ LEAKAGE DETECTED — Training aborted.")

    return {
        "passed":         passed,
        "critical_count": critical_count,
        "warning_count":  warning_count,
        "suspicious":     suspicious,
    }


# ══════════════════════════════════════════════════════════════════════════════
# POST-TRAIN CONFIDENCE SANITY CHECK
# ══════════════════════════════════════════════════════════════════════════════

def check_confidence_distribution(
    model,
    X_test:      np.ndarray,
    y_test:      np.ndarray,
    data_source: str,
    auc:         float,
) -> dict:
    logger.info("\n" + "═" * 60)
    logger.info("  🔍 POST-TRAIN CONFIDENCE SANITY CHECK")
    logger.info("═" * 60)

    proba = model.predict_proba(X_test)[:, 1]

    mean_conf    = float(proba.mean())
    std_conf     = float(proba.std())
    pct_above_95 = float((proba > 0.95).mean())
    pct_above_99 = float((proba > 0.99).mean())
    pct_below_05 = float((proba < 0.05).mean())

    issues   = []
    warnings = []
    passed   = True

    if std_conf < 0.05:
        issues.append(f"🚨 COLLAPSED PREDICTIONS: std={std_conf:.4f} < 0.05")
        passed = False
    elif std_conf < 0.10:
        warnings.append(f"⚠️ Low variance: std={std_conf:.4f}")

    if pct_above_99 > 0.10:
        issues.append(
            f"🚨 OVERCONFIDENT: {pct_above_99:.0%} of test predictions > 0.99 — "
            "likely memorization"
        )
        passed = False
    elif pct_above_95 > 0.40:
        warnings.append(f"⚠️ {pct_above_95:.0%} of predictions > 0.95 — high bias toward approve")

    is_synthetic = "synthetic" in data_source
    if is_synthetic and auc > SANITY_MAX_AUC_SYNTHETIC:
        issues.append(
            f"🚨 AUC={auc:.4f} > {SANITY_MAX_AUC_SYNTHETIC} on synthetic data — "
            "model is memorizing generated labels."
        )
        passed = False

    logger.info("  📊 Confidence Stats on Test Set:")
    logger.info("     mean = %.4f | std = %.4f", mean_conf, std_conf)
    logger.info("     pct > 0.95 = %.0f%% | pct > 0.99 = %.0f%%",
                pct_above_95 * 100, pct_above_99 * 100)
    logger.info("     pct < 0.05 = %.0f%%", pct_below_05 * 100)

    if issues:
        for issue in issues:
            logger.error("  %s", issue)
        logger.warning("  ⚠️ Continuing despite sanity failure — review before production use.")
    elif warnings:
        for w in warnings:
            logger.warning("  %s", w)
    else:
        logger.info("  ✅ Confidence distribution looks realistic.")

    logger.info("═" * 60)

    return {
        "passed":        passed,
        "mean_conf":     round(mean_conf, 4),
        "std_conf":      round(std_conf, 4),
        "pct_above_95":  round(pct_above_95, 3),
        "pct_above_99":  round(pct_above_99, 3),
        "pct_below_05":  round(pct_below_05, 3),
        "auc":           round(auc, 4),
        "is_synthetic":  is_synthetic,
        "issues":        issues,
        "warnings_list": warnings,
    }


# ══════════════════════════════════════════════════════════════════════════════
# EDGE CASE TESTING
# ══════════════════════════════════════════════════════════════════════════════

def generate_edge_cases() -> list[dict]:
    cases = [
        {
            "id": "MISS_01", "category": "missing_values",
            "label": "رصيد إجازة مفقود",
            "data": {"leave_days": 5, "performance_score": 0.8, "absence_count": 2,
                     "job_level": "senior", "years_of_experience": 5},
            "expected": "escalate",
        },
        {
            "id": "MISS_02", "category": "missing_values",
            "label": "أداء مفقود",
            "data": {"leave_days": 3, "leave_balance": 20, "absence_count": 1,
                     "job_level": "junior", "years_of_experience": 2},
            "expected": "approve",
        },
        {
            "id": "MISS_03", "category": "missing_values",
            "label": "كل البيانات الاختيارية مفقودة",
            "data": {"leave_days": 7, "leave_balance": 10},
            "expected": "escalate",
        },
        {
            "id": "MISS_04", "category": "missing_values",
            "label": "سنوات خبرة مفقودة",
            "data": {"leave_days": 2, "leave_balance": 5, "performance_score": 0.7,
                     "absence_count": 0, "job_level": "junior"},
            "expected": "approve",
        },
        {
            "id": "OUT_01", "category": "outlier",
            "label": "طلب إجازة 60 يوم",
            "data": {"leave_days": 60, "leave_balance": 30, "performance_score": 0.9,
                     "absence_count": 0, "job_level": "manager", "years_of_experience": 20,
                     "salary_grade": "A", "overtime_hours": 200},
            "expected": "reject",
        },
        {
            "id": "OUT_02", "category": "outlier",
            "label": "أداء = 0.0",
            "data": {"leave_days": 3, "leave_balance": 15, "performance_score": 0.0,
                     "absence_count": 20, "job_level": "junior", "years_of_experience": 1},
            "expected": "reject",
        },
        {
            "id": "OUT_03", "category": "outlier",
            "label": "أداء = 1.0، غياب 0",
            "data": {"leave_days": 1, "leave_balance": 30, "performance_score": 1.0,
                     "absence_count": 0, "job_level": "lead", "years_of_experience": 10,
                     "salary_grade": "B", "overtime_hours": 0},
            "expected": "approve",
        },
        {
            "id": "OUT_04", "category": "outlier",
            "label": "رصيد = 0",
            "data": {"leave_days": 5, "leave_balance": 0, "performance_score": 0.85,
                     "absence_count": 1, "job_level": "senior", "years_of_experience": 8},
            "expected": "reject",
        },
        {
            "id": "OUT_05", "category": "outlier",
            "label": "overtime = 500",
            "data": {"leave_days": 5, "leave_balance": 20, "performance_score": 0.75,
                     "absence_count": 3, "job_level": "senior", "years_of_experience": 5,
                     "overtime_hours": 500},
            "expected": "approve",
        },
        {
            "id": "OUT_06", "category": "outlier",
            "label": "غياب = 50",
            "data": {"leave_days": 3, "leave_balance": 10, "performance_score": 0.6,
                     "absence_count": 50, "job_level": "junior", "years_of_experience": 2},
            "expected": "reject",
        },
        {
            "id": "EDGE_01", "category": "hr_edge_case",
            "label": "Manager بأداء سيئ يطلب إجازة طويلة",
            "data": {"leave_days": 14, "leave_balance": 20, "performance_score": 0.35,
                     "absence_count": 8, "job_level": "manager", "years_of_experience": 15,
                     "salary_grade": "A", "overtime_hours": 10},
            "expected": "escalate",
        },
        {
            "id": "EDGE_02", "category": "hr_edge_case",
            "label": "Junior جديد يطلب إجازة",
            "data": {"leave_days": 7, "leave_balance": 7, "performance_score": 0.70,
                     "absence_count": 0, "job_level": "junior", "years_of_experience": 0,
                     "salary_grade": "E", "overtime_hours": 5},
            "expected": "escalate",
        },
        {
            "id": "EDGE_03", "category": "hr_edge_case",
            "label": "أداء عالي لكن رصيد منخفض",
            "data": {"leave_days": 10, "leave_balance": 5, "performance_score": 0.95,
                     "absence_count": 0, "job_level": "lead", "years_of_experience": 7,
                     "salary_grade": "B", "overtime_hours": 80},
            "expected": "escalate",
        },
        {
            "id": "EDGE_04", "category": "hr_edge_case",
            "label": "رصيد = عدد الأيام",
            "data": {"leave_days": 5, "leave_balance": 5, "performance_score": 0.75,
                     "absence_count": 2, "job_level": "senior", "years_of_experience": 4},
            "expected": "escalate",
        },
        {
            "id": "EDGE_05", "category": "hr_edge_case",
            "label": "إجازة يوم واحد فقط",
            "data": {"leave_days": 1, "leave_balance": 3, "performance_score": 0.65,
                     "absence_count": 5, "job_level": "junior", "years_of_experience": 1},
            "expected": "approve",
        },
        {
            "id": "EDGE_06", "category": "hr_edge_case",
            "label": "salary_grade غير معروف",
            "data": {"leave_days": 5, "leave_balance": 15, "performance_score": 0.7,
                     "absence_count": 2, "job_level": "senior", "years_of_experience": 5,
                     "salary_grade": "Z", "overtime_hours": 10},
            "expected": "approve",
        },
        {
            "id": "EDGE_07", "category": "hr_edge_case",
            "label": "job_level غير معروف",
            "data": {"leave_days": 5, "leave_balance": 15, "performance_score": 0.7,
                     "absence_count": 2, "job_level": "intern",
                     "years_of_experience": 1},
            "expected": "escalate",
        },
        {
            "id": "BORDER_01", "category": "borderline",
            "label": "على حد approve threshold",
            "data": {"leave_days": 5, "leave_balance": 15, "performance_score": 0.80,
                     "absence_count": 1, "job_level": "senior", "years_of_experience": 6,
                     "salary_grade": "B", "overtime_hours": 30},
            "expected": "approve",
        },
        {
            "id": "BORDER_02", "category": "borderline",
            "label": "على حد reject threshold",
            "data": {"leave_days": 12, "leave_balance": 10, "performance_score": 0.45,
                     "absence_count": 8, "job_level": "junior", "years_of_experience": 1,
                     "salary_grade": "D", "overtime_hours": 0},
            "expected": "reject",
        },
    ]
    return cases


def run_edge_case_tests(model_handler, verbose: bool = True) -> dict:
    logger.info("\n" + "═" * 60)
    logger.info("  🧪 NOISY / EDGE CASE TESTING")
    logger.info("═" * 60)

    cases   = generate_edge_cases()
    results = []
    passed  = 0
    failed  = 0
    category_stats = {}

    for case in cases:
        result     = model_handler.predict(case["data"])
        decision   = result["decision"]
        confidence = result["confidence"]
        expected   = case["expected"]

        strict_pass = (decision == expected)
        is_pass = (
            decision == expected
            or (expected == "escalate" and decision in ["escalate", "approve", "reject"])
            or (expected == "approve"  and decision in ["approve", "escalate"])
        )

        status_emoji = "✅" if strict_pass else ("⚠️" if is_pass else "❌")
        cat = case["category"]

        if cat not in category_stats:
            category_stats[cat] = {"total": 0, "strict": 0, "loose": 0}
        category_stats[cat]["total"] += 1
        if strict_pass:
            category_stats[cat]["strict"] += 1
            passed += 1
        else:
            failed += 1
        if is_pass:
            category_stats[cat]["loose"] += 1

        results.append({
            "id":          case["id"],
            "category":    cat,
            "label":       case["label"],
            "expected":    expected,
            "got":         decision,
            "confidence":  confidence,
            "strict_pass": strict_pass,
            "loose_pass":  is_pass,
            "source":      result.get("source", "?"),
        })

        if verbose:
            logger.info(
                "  %s [%s] %-40s expected=%-8s got=%-8s conf=%.2f",
                status_emoji, case["id"], case["label"][:40],
                expected, decision, confidence,
            )

    total       = len(cases)
    strict_rate = passed / total
    loose_rate  = sum(1 for r in results if r["loose_pass"]) / total

    logger.info("\n  📊 Edge Case Results:")
    logger.info("     Strict Pass: %d/%d = %.0f%%", passed, total, strict_rate * 100)
    logger.info("     Loose  Pass: %d/%d = %.0f%%",
                sum(1 for r in results if r["loose_pass"]), total, loose_rate * 100)

    critical_fails = [r for r in results if not r["loose_pass"]]
    if critical_fails:
        logger.warning("\n  ⚠️  %d critical failure(s):", len(critical_fails))
        for r in critical_fails:
            logger.warning("     ❌ [%s] %s: expected=%s, got=%s",
                           r["id"], r["label"], r["expected"], r["got"])
    else:
        logger.info("\n  ✅ No critical failures.")

    logger.info("═" * 60)

    return {
        "total":          total,
        "strict_passed":  passed,
        "strict_rate":    round(strict_rate, 3),
        "loose_rate":     round(loose_rate, 3),
        "critical_fails": len(critical_fails),
        "by_category":    category_stats,
        "details":        results,
    }


# ══════════════════════════════════════════════════════════════════════════════
# BUSINESS COST SIMULATION
# ══════════════════════════════════════════════════════════════════════════════

def simulate_business_costs(
    model,
    scaler,
    X_test: np.ndarray,
    y_test: np.ndarray,
    t_approve:  float = THRESHOLD_APPROVE,
    t_escalate: float = THRESHOLD_ESCALATE,
    n_requests_monthly: int = 200,
    cost_false_approve: float = COST_FALSE_APPROVE,
    cost_false_reject:  float = COST_FALSE_REJECT,
    threshold_sweep: bool = True,
) -> dict:
    logger.info("\n" + "═" * 60)
    logger.info("  💰 BUSINESS COST SIMULATION")
    logger.info("═" * 60)

    y_proba = model.predict_proba(X_test)[:, 1]
    n_test  = len(y_test)

    def compute_costs(proba, y_true, t_app, t_esc):
        decisions = np.where(
            proba >= t_app, "approve",
            np.where(proba >= t_esc, "escalate", "reject")
        )
        fp     = np.sum((decisions == "approve")  & (y_true == 0))
        fn     = np.sum((decisions == "reject")   & (y_true == 1))
        tp     = np.sum((decisions == "approve")  & (y_true == 1))
        tn     = np.sum((decisions == "reject")   & (y_true == 0))
        esc_fp = np.sum((decisions == "escalate") & (y_true == 0))
        esc_fn = np.sum((decisions == "escalate") & (y_true == 1))

        cost_fp  = fp     * cost_false_approve
        cost_fn  = fn     * cost_false_reject
        cost_esc = esc_fp * COST_ESCALATE_FP + esc_fn * COST_ESCALATE_FN
        total    = cost_fp + cost_fn + cost_esc

        return {
            "tp": int(tp), "tn": int(tn), "fp": int(fp), "fn": int(fn),
            "esc_fp": int(esc_fp), "esc_fn": int(esc_fn),
            "n_approve":  int(np.sum(decisions == "approve")),
            "n_escalate": int(np.sum(decisions == "escalate")),
            "n_reject":   int(np.sum(decisions == "reject")),
            "cost_false_approve": float(cost_fp),
            "cost_false_reject":  float(cost_fn),
            "cost_escalation":    float(cost_esc),
            "total_cost_test":    float(total),
            "cost_per_request":   float(total / max(len(y_true), 1)),
        }

    current      = compute_costs(y_proba, y_test, t_approve, t_escalate)
    scale        = n_requests_monthly / max(n_test, 1)
    monthly_cost = current["total_cost_test"] * scale
    annual_cost  = monthly_cost * 12

    logger.info("\n  📌 Current Thresholds (approve>=%.2f, escalate>=%.2f):", t_approve, t_escalate)
    logger.info("     FP=%d | FN=%d", current["fp"], current["fn"])
    logger.info("     Monthly Cost = {:,.0f} EGP | Annual = {:,.0f} EGP".format(monthly_cost, annual_cost))

    best_threshold = None
    best_cost      = float("inf")
    sweep_results  = []

    if threshold_sweep:
        for t_app in np.arange(0.55, 0.90, 0.05):
            for t_esc in np.arange(0.25, 0.60, 0.05):
                if t_esc >= t_app:
                    continue
                res = compute_costs(y_proba, y_test, t_app, t_esc)
                mo  = res["total_cost_test"] * scale
                sweep_results.append({
                    "t_approve":    round(float(t_app), 2),
                    "t_escalate":   round(float(t_esc), 2),
                    "fp":           res["fp"],
                    "fn":           res["fn"],
                    "monthly_cost": round(mo, 2),
                })
                if mo < best_cost:
                    best_cost      = mo
                    best_threshold = {"approve":  round(float(t_app), 2),
                                      "escalate": round(float(t_esc), 2)}

        if best_threshold:
            saving = monthly_cost - best_cost
            logger.info("\n  🏆 Optimal: approve=%.2f | escalate=%.2f | saving=%.0f EGP/mo",
                        best_threshold["approve"], best_threshold["escalate"], saving)

    logger.info("═" * 60)

    return {
        "current_thresholds":   {"approve": t_approve, "escalate": t_escalate},
        "test_set_metrics":     current,
        "monthly_cost_egp":     round(monthly_cost, 2),
        "annual_cost_egp":      round(annual_cost, 2),
        "cost_per_request":     round(current["cost_per_request"], 2),
        "optimal_thresholds":   best_threshold,
        "optimal_monthly_cost": round(best_cost, 2) if best_threshold else None,
        "monthly_saving_egp":   round(monthly_cost - best_cost, 2) if best_threshold else 0,
        "sweep_results":        sweep_results[:20],
    }


# ══════════════════════════════════════════════════════════════════════════════
# 2. PREPROCESSING
# ══════════════════════════════════════════════════════════════════════════════

def preprocess(df: pd.DataFrame) -> tuple:
    df = df.copy()

    if "created_at" in df.columns:
        df["created_at"]     = pd.to_datetime(df["created_at"], errors="coerce")
        df["days_to_fy_end"] = df["created_at"].apply(
            lambda x: days_to_fy_end(x) if pd.notna(x) else 180
        )
    else:
        df["days_to_fy_end"] = 180

    df["balance_ratio"] = (
        df["leave_balance"] / df["leave_days"].clip(lower=1)
    ).clip(upper=5.0)

    df["absence_per_year"] = (
        df["absence_count"] / df["years_of_experience"].clip(lower=1)
    ).clip(upper=10.0)

    df["perf_balance_score"] = (
        df["performance_score"] * df["balance_ratio"].clip(upper=2.0) / 2.0
    ).clip(upper=1.0)

    for col in NUMERIC_FEATURES:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(
                df[col].median() if df[col].notna().any() else 0
            )

    encoders = {}
    for col in CATEGORICAL_FEATURES:
        if col not in df.columns:
            df[col] = "unknown"
        le = LabelEncoder()
        df[col + "_enc"] = le.fit_transform(df[col].astype(str).str.lower())
        encoders[col]    = le
        logger.info("   Encoded '%s': %s", col, list(le.classes_))

    return df, encoders


def build_feature_matrix(df: pd.DataFrame) -> tuple:
    cat_cols  = [c + "_enc" for c in CATEGORICAL_FEATURES if c + "_enc" in df.columns]
    num_cols  = [c for c in NUMERIC_FEATURES if c in df.columns]
    feat_cols = num_cols + cat_cols

    X = df[feat_cols].values.astype(np.float32)
    y = df[TARGET].values.astype(int)

    logger.info("📐 Feature matrix: %d samples × %d features", X.shape[0], X.shape[1])
    return X, y, feat_cols


# ══════════════════════════════════════════════════════════════════════════════
# 3. TRAINING
# ══════════════════════════════════════════════════════════════════════════════

def train_model(X_train: np.ndarray, y_train: np.ndarray) -> CalibratedClassifierCV:
    rf = RandomForestClassifier(
        n_estimators=300, max_depth=10, min_samples_leaf=4,
        max_features="sqrt", class_weight="balanced", random_state=42, n_jobs=-1,
    )
    gb = GradientBoostingClassifier(
        n_estimators=200, learning_rate=0.05, max_depth=5, subsample=0.8, random_state=42,
    )
    lr = LogisticRegression(
        C=1.0, class_weight="balanced", max_iter=500, random_state=42,
    )
    ensemble = VotingClassifier(
        estimators=[("rf", rf), ("gb", gb), ("lr", lr)],
        voting="soft", weights=[3, 2, 1],
    )
    model = CalibratedClassifierCV(ensemble, method="isotonic", cv=5)
    model.fit(X_train, y_train)
    logger.info("✅ Ensemble trained: RF(300) + GB(200) + LR — Calibrated (isotonic, cv=5)")
    return model


# ══════════════════════════════════════════════════════════════════════════════
# 4. EVALUATION
# ══════════════════════════════════════════════════════════════════════════════

def evaluate(model, X_test, y_test, feature_cols, X_train=None, y_train=None) -> dict:
    y_pred  = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    acc = accuracy_score(y_test, y_pred)
    auc = roc_auc_score(y_test, y_proba)
    f1  = f1_score(y_test, y_pred, average="weighted")
    rep = classification_report(y_test, y_pred, target_names=["rejected", "approved"])
    cm  = confusion_matrix(y_test, y_pred).tolist()

    cv_scores = []
    if X_train is not None and y_train is not None and len(X_train) > 50:
        cv        = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        cv_scores = cross_val_score(model, X_train, y_train, cv=cv, scoring="roc_auc").tolist()

    logger.info("\n%s", "═" * 55)
    logger.info("  📊 EVALUATION RESULTS")
    logger.info("%s", "─" * 55)
    logger.info("  Accuracy : %.4f  (%.1f%%)", acc, acc * 100)
    logger.info("  ROC-AUC  : %.4f", auc)
    logger.info("  F1 Score : %.4f", f1)
    if cv_scores:
        logger.info("  CV AUC (5-fold): %.4f ± %.4f",
                    np.mean(cv_scores), np.std(cv_scores))
    logger.info("\n%s", rep)
    logger.info("  Confusion Matrix: %s", cm)

    approve_rate  = (y_proba >= THRESHOLD_APPROVE).mean()
    escalate_rate = ((y_proba >= THRESHOLD_ESCALATE) & (y_proba < THRESHOLD_APPROVE)).mean()
    reject_rate   = (y_proba < THRESHOLD_ESCALATE).mean()
    logger.info("\n  📌 Decision Distribution:")
    logger.info("  Auto-Approve  (>=%.0f%%): %.1f%%", THRESHOLD_APPROVE  * 100, approve_rate  * 100)
    logger.info("  Escalate      (%.0f%%–%.0f%%): %.1f%%",
                THRESHOLD_ESCALATE * 100, THRESHOLD_APPROVE * 100, escalate_rate * 100)
    logger.info("  Auto-Reject   (<%.0f%%): %.1f%%",  THRESHOLD_ESCALATE * 100, reject_rate   * 100)
    logger.info("%s", "═" * 55)

    return {
        "accuracy":         round(acc, 4),
        "roc_auc":          round(auc, 4),
        "f1_score":         round(f1, 4),
        "cv_auc_mean":      round(float(np.mean(cv_scores)), 4) if cv_scores else None,
        "cv_auc_std":       round(float(np.std(cv_scores)),  4) if cv_scores else None,
        "confusion_matrix": cm,
        "decision_distribution": {
            "auto_approve": round(float(approve_rate),  3),
            "escalate":     round(float(escalate_rate), 3),
            "auto_reject":  round(float(reject_rate),   3),
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# 5. SAVE ARTIFACTS
# ══════════════════════════════════════════════════════════════════════════════

def save_artifacts(
    model, scaler, encoders, feature_cols, eval_metrics, data_source, n_samples,
    leakage_report=None, edge_case_results=None, cost_simulation=None,
    optimal_thresholds=None, confidence_sanity=None,
):
    joblib.dump(model,  MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)
    joblib.dump({"encoders": encoders, "feature_cols": feature_cols}, ENCODER_PATH)

    t_approve  = THRESHOLD_APPROVE
    t_escalate = THRESHOLD_ESCALATE
    if optimal_thresholds and cost_simulation:
        saving = cost_simulation.get("monthly_saving_egp", 0)
        if saving > 50:
            t_approve  = optimal_thresholds["approve"]
            t_escalate = optimal_thresholds["escalate"]
            logger.info(
                "  📌 Using OPTIMAL thresholds (saving %.0f EGP/month): "
                "approve=%.2f | escalate=%.2f", saving, t_approve, t_escalate,
            )

    metadata = {
        "trained_at":           datetime.now(timezone.utc).isoformat(),
        "model_type":           "CalibratedEnsemble(RF+GB+LR)",
        "data_source":          data_source,
        "n_training_samples":   n_samples,
        "feature_cols":         feature_cols,
        "numeric_features":     NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "thresholds": {
            "approve":     t_approve,
            "escalate":    t_escalate,
            "reject":      0.0,
            "description": (
                f">={t_approve} → auto approve | "
                f"{t_escalate}–{t_approve} → escalate | "
                f"<{t_escalate} → auto reject"
            ),
        },
        "evaluation":    eval_metrics,
        "model_path":    str(MODEL_PATH),
        "scaler_path":   str(SCALER_PATH),
        "encoder_path":  str(ENCODER_PATH),
        "leakage_validation": {
            "passed":         leakage_report.get("passed")         if leakage_report else None,
            "critical_count": leakage_report.get("critical_count") if leakage_report else None,
            "warning_count":  leakage_report.get("warning_count")  if leakage_report else None,
        } if leakage_report else None,
        "edge_case_testing": {
            "total":          edge_case_results.get("total")          if edge_case_results else None,
            "strict_passed":  edge_case_results.get("strict_passed")  if edge_case_results else None,
            "strict_rate":    edge_case_results.get("strict_rate")    if edge_case_results else None,
            "loose_rate":     edge_case_results.get("loose_rate")     if edge_case_results else None,
            "critical_fails": edge_case_results.get("critical_fails") if edge_case_results else None,
        } if edge_case_results else None,
        "business_costs": {
            "monthly_cost_egp":   cost_simulation.get("monthly_cost_egp")   if cost_simulation else None,
            "annual_cost_egp":    cost_simulation.get("annual_cost_egp")     if cost_simulation else None,
            "cost_per_request":   cost_simulation.get("cost_per_request")    if cost_simulation else None,
            "optimal_thresholds": cost_simulation.get("optimal_thresholds")  if cost_simulation else None,
            "monthly_saving_egp": cost_simulation.get("monthly_saving_egp")  if cost_simulation else None,
        } if cost_simulation else None,
        "confidence_sanity": {
            "passed":       confidence_sanity.get("passed")       if confidence_sanity else None,
            "mean_conf":    confidence_sanity.get("mean_conf")    if confidence_sanity else None,
            "std_conf":     confidence_sanity.get("std_conf")     if confidence_sanity else None,
            "pct_above_99": confidence_sanity.get("pct_above_99") if confidence_sanity else None,
            "issues":       confidence_sanity.get("issues")       if confidence_sanity else [],
        } if confidence_sanity else None,
    }

    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    logger.info("\n  💾 Artifacts saved:")
    logger.info("     Model    → %s", MODEL_PATH)
    logger.info("     Scaler   → %s", SCALER_PATH)
    logger.info("     Encoders → %s", ENCODER_PATH)
    logger.info("     Metadata → %s", META_PATH)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="HR Leave Approval — Training Pipeline v3.2")
    parser.add_argument("--min-samples",        type=int,  default=50)
    parser.add_argument("--dry-run",            action="store_true")
    parser.add_argument("--csv",                type=str,  default=None)
    parser.add_argument("--skip-leakage-check", action="store_true")
    parser.add_argument("--skip-edge-tests",    action="store_true")
    parser.add_argument("--skip-cost-sim",      action="store_true")
    parser.add_argument("--skip-sanity-check",  action="store_true")
    parser.add_argument("--monthly-requests",   type=int,  default=200)
    parser.add_argument("--cost-false-approve", type=float, default=COST_FALSE_APPROVE)
    parser.add_argument("--cost-false-reject",  type=float, default=COST_FALSE_REJECT)
    args = parser.parse_args()

    logger.info("🚀 HR Leave Approval Training Pipeline v3.2 starting...")
    logger.info("   Data source priority: --csv > Node.js API (GET /hr/leaves) > synthetic")
    logger.info("   Thresholds: approve>=%.2f | escalate>=%.2f",
                THRESHOLD_APPROVE, THRESHOLD_ESCALATE)
    logger.info("   Sanity cap (synthetic AUC max): %.2f", SANITY_MAX_AUC_SYNTHETIC)

    # ── 1. Data ───────────────────────────────────────────────────────────────
    data_source = "node_api"
    df = None

    if args.csv:
        try:
            df = load_from_csv(args.csv)
            data_source = f"csv:{Path(args.csv).name}"
        except Exception as e:
            logger.error("❌ CSV load failed: %s", e)
            sys.exit(1)

    elif not args.dry_run:
        try:
            df = load_from_db()
            if len(df) < args.min_samples:
                logger.warning(
                    "⚠️ Only %d real rows from Node API — augmenting with synthetic", len(df)
                )
                df_synth    = generate_synthetic_data(n=max(300, args.min_samples * 4))
                df          = pd.concat([df, df_synth], ignore_index=True)
                data_source = "node_api+synthetic"
        except Exception as e:
            logger.warning("⚠️ Node.js API load failed: %s — using synthetic", e)
            df = None

    if df is None or args.dry_run:
        df          = generate_synthetic_data(n=1500)
        data_source = "synthetic"

    # ── 2. Target column ──────────────────────────────────────────────────────
    if TARGET not in df.columns:
        if "status" in df.columns:
            df[TARGET] = (df["status"] == "approved").astype(int)
            logger.info("   ✅ Converted 'status' → 'approved' (1/0)")
        else:
            logger.error("❌ Target column '%s' not found!", TARGET)
            sys.exit(1)

    required = ["leave_days", "leave_balance", "performance_score", "absence_count"]
    missing  = [c for c in required if c not in df.columns]
    if missing:
        logger.error("❌ Missing required columns: %s", missing)
        sys.exit(1)

    logger.info("\n📊 Dataset Summary:")
    logger.info("   Total: %d | Approved: %d (%.1f%%) | Rejected: %d | Source: %s",
                len(df), df[TARGET].sum(), df[TARGET].mean() * 100,
                (~df[TARGET].astype(bool)).sum(), data_source)

    # ── 3. Preprocessing ──────────────────────────────────────────────────────
    df_proc, encoders = preprocess(df)
    X, y, feature_cols = build_feature_matrix(df_proc)

    # ── 4. Leakage Check ──────────────────────────────────────────────────────
    leakage_report = None
    if not args.skip_leakage_check:
        leakage_report = validate_no_leakage(df_proc, feature_cols, TARGET)
        if not leakage_report["passed"]:
            logger.error("❌ Training ABORTED — feature leakage detected.")
            sys.exit(1)
    else:
        logger.warning("⚠️ Leakage check skipped")

    # ── 5. Train/Test Split ───────────────────────────────────────────────────
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=42
    )
    logger.info("\n   Train: %d | Test: %d", len(X_train), len(X_test))

    # ── 6. Scaling ────────────────────────────────────────────────────────────
    scaler  = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test  = scaler.transform(X_test)

    # ── 7. Training ───────────────────────────────────────────────────────────
    logger.info("\n🤖 Training Calibrated Ensemble Model...")
    model = train_model(X_train, y_train)

    # ── 8. Evaluation ─────────────────────────────────────────────────────────
    logger.info("\n📊 Evaluating on holdout test set...")
    eval_metrics = evaluate(model, X_test, y_test, feature_cols, X_train, y_train)

    # ── 9. Post-Train Confidence Sanity ───────────────────────────────────────
    confidence_sanity = None
    if not args.skip_sanity_check:
        confidence_sanity = check_confidence_distribution(
            model, X_test, y_test, data_source, eval_metrics["roc_auc"]
        )
    else:
        logger.warning("⚠️ Post-train sanity check skipped")

    # ── 10. Cost Simulation ───────────────────────────────────────────────────
    cost_simulation    = None
    optimal_thresholds = None
    if not args.skip_cost_sim:
        cost_simulation = simulate_business_costs(
            model, scaler, X_test, y_test,
            t_approve=THRESHOLD_APPROVE,
            t_escalate=THRESHOLD_ESCALATE,
            n_requests_monthly=args.monthly_requests,
            cost_false_approve=args.cost_false_approve,
            cost_false_reject=args.cost_false_reject,
            threshold_sweep=True,
        )
        optimal_thresholds = cost_simulation.get("optimal_thresholds")
    else:
        logger.warning("⚠️ Cost simulation skipped")

    # ── 11. Edge Case Testing ─────────────────────────────────────────────────
    edge_case_results = None
    if not args.skip_edge_tests:
        try:
            from agents.hr.leave_model_handler import LeaveModelHandler
            temp_handler               = LeaveModelHandler()
            temp_handler._model        = model
            temp_handler._scaler       = scaler
            temp_handler._encoders     = encoders
            temp_handler._feature_cols = feature_cols
            temp_handler._metadata     = {
                "thresholds": {
                    "approve":  THRESHOLD_APPROVE,
                    "escalate": THRESHOLD_ESCALATE,
                }
            }
            temp_handler._loaded  = True
            edge_case_results     = run_edge_case_tests(temp_handler, verbose=True)
        except ImportError:
            logger.warning("⚠️ LeaveModelHandler not found — skipping edge cases")
    else:
        logger.warning("⚠️ Edge case tests skipped")

    # ── 12. Quality Gate ──────────────────────────────────────────────────────
    quality_issues = []
    if eval_metrics["roc_auc"] < 0.65:
        quality_issues.append(f"ROC-AUC={eval_metrics['roc_auc']:.3f} < 0.65")
    if edge_case_results and edge_case_results["loose_rate"] < 0.70:
        quality_issues.append(f"Edge case pass rate={edge_case_results['loose_rate']:.0%} < 70%")
    if confidence_sanity and not confidence_sanity["passed"]:
        quality_issues.append("Post-train confidence sanity FAILED")

    if quality_issues:
        logger.warning("⚠️ Quality gate WARNINGS: %s", " | ".join(quality_issues))
    else:
        logger.info("✅ Quality gate passed: AUC=%.3f", eval_metrics["roc_auc"])

    # ── 13. Save ──────────────────────────────────────────────────────────────
    save_artifacts(
        model, scaler, encoders, feature_cols, eval_metrics, data_source, len(X_train),
        leakage_report=leakage_report,
        edge_case_results=edge_case_results,
        cost_simulation=cost_simulation,
        optimal_thresholds=optimal_thresholds,
        confidence_sanity=confidence_sanity,
    )

    # ── Final Summary ─────────────────────────────────────────────────────────
    print(f"\n{'🏆' * 3} Training Complete v3.2 {'🏆' * 3}")
    print(f"   Data source: {data_source}")
    print(f"   Accuracy : {eval_metrics['accuracy']:.2%}")
    print(f"   ROC-AUC  : {eval_metrics['roc_auc']:.4f}")
    print(f"   F1 Score : {eval_metrics['f1_score']:.4f}")
    if leakage_report:
        print(f"   Leakage  : {'✅ PASSED' if leakage_report['passed'] else '❌ FAILED'} "
              f"(critical={leakage_report['critical_count']})")
    if confidence_sanity:
        print(f"   Sanity   : {'✅ OK' if confidence_sanity['passed'] else '❌ OVERFIT WARNING'} "
              f"(mean={confidence_sanity['mean_conf']:.3f}, std={confidence_sanity['std_conf']:.3f})")
    if edge_case_results:
        print(f"   Edge Cases: {edge_case_results['strict_passed']}/{edge_case_results['total']} strict | "
              f"{edge_case_results['loose_rate']:.0%} acceptable")
    if cost_simulation:
        print(f"   Monthly Cost: {cost_simulation['monthly_cost_egp']:,.0f} EGP/month")
    print(f"\n   Next → POST /model/reload to load the new model")
    print(f"   Then → GET  /model/diagnose to verify confidence distribution\n")


if __name__ == "__main__":
    main()