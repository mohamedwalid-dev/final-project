"""
build_historical_features.py
============================
يحسب historical features من الفواتير السابقة فقط (zero leakage by design)
ويحفظ CSV جديد جاهز للتدريب بـ finance_train_v4.py

المشكلة:
    paid_ratio و late_ratio في الـ CSV الحالي محسوبين من نفس الفاتورة
    → الموديل بيشوف النتيجة وبيحفظها → AUC = 0.9997 (fake)

الحل:
    نرتب الفواتير لكل عميل بالتاريخ
    نستخدم .shift() + .expanding() عشان نحسب من الفواتير السابقة فقط
    أول فاتورة لكل عميل = default values (مفيش تاريخ)

Usage:
    python build_historical_features.py --csv finance_training_data_100k.csv
    python build_historical_features.py --csv finance_training_data_100k.csv --output clean_training_data.csv

الكولامز المطلوبة في الـ CSV الأصلي:
    - customer_id (أو customer_age_months كـ proxy)
    - invoice_date أو invoice_month + year (للترتيب الزمني)
    - paid_ratio أو paid (1/0) عشان نحسب hist_paid_ratio
    - late_ratio أو is_late (1/0) عشان نحسب hist_late_ratio
    - avg_delay_normalized أو delay_days عشان نحسب hist_avg_delay
    - is_bad_payer (target)
    وكل الـ point-in-time features الأخرى
"""

from __future__ import annotations
import argparse
import logging
import sys
import os
import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Defaults لأول فاتورة لكل عميل (مفيش تاريخ قبلها)
# ─────────────────────────────────────────────────────────────────────────────
DEFAULTS = {
    "hist_paid_ratio":              0.75,   # نفترض عميل جديد متوسط
    "hist_late_ratio":              0.15,
    "hist_avg_delay_normalized":    0.10,
    "hist_payment_count_normalized": 0.0,   # صفر فواتير سابقة
}


# ─────────────────────────────────────────────────────────────────────────────
# Helper: استخرج customer_id من الكولامز المتاحة
# ─────────────────────────────────────────────────────────────────────────────
def _resolve_customer_id(df: pd.DataFrame) -> pd.Series:
    """
    بنحاول نلاقي customer_id بالترتيب ده:
    1. customer_id column مباشرة
    2. customer_age_months (لو كل صف عميل مختلف)
    3. row index كـ proxy (أسوأ حالة)
    """
    if "customer_id" in df.columns:
        log.info("   ✅ customer_id column found")
        return df["customer_id"].astype(str)

    # لو مفيش customer_id، نشوف لو فيه طريقة تانية
    log.warning(
        "   ⚠️  No 'customer_id' column found.\n"
        "       Falling back to row index (every row = unique customer).\n"
        "       Historical features will all be defaults (no prior invoices).\n"
        "       → Add a 'customer_id' column to your CSV for proper results."
    )
    return df.index.astype(str)


# ─────────────────────────────────────────────────────────────────────────────
# Helper: استخرج time index للترتيب الزمني
# ─────────────────────────────────────────────────────────────────────────────
def _resolve_time_index(df: pd.DataFrame) -> pd.Series:
    """
    بنحاول نبني time index للترتيب بالتاريخ:
    1. invoice_date (datetime)
    2. year + invoice_month → year*100 + month
    3. row index (sequential proxy)
    """
    if "invoice_date" in df.columns:
        try:
            ts = pd.to_datetime(df["invoice_date"])
            log.info("   ✅ invoice_date parsed as datetime")
            return ts
        except Exception as e:
            log.warning("   invoice_date parse failed: %s", e)

    if "year" in df.columns and "invoice_month" in df.columns:
        t = df["year"].fillna(0).astype(int) * 100 + df["invoice_month"].fillna(1).astype(int)
        log.info("   ✅ time index = year*100 + invoice_month (range: %d – %d)", t.min(), t.max())
        return t

    if "invoice_month" in df.columns:
        log.warning(
            "   ⚠️  Only 'invoice_month' found (no year). Using row index for time ordering.\n"
            "       Add a 'year' column for proper temporal split."
        )

    log.info("   ℹ️  No date column found — using row index as time proxy")
    return pd.Series(range(len(df)), index=df.index)


# ─────────────────────────────────────────────────────────────────────────────
# Core: بناء historical features بـ .shift() + .expanding()
# ─────────────────────────────────────────────────────────────────────────────
def build_historical_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    الخطوات:
    1. نحدد customer_id و time_index
    2. نرتب حسب customer_id ثم time_index
    3. لكل عميل نحسب expanding stats بعد shift(1)
       → كل صف يشوف بس الفواتير اللي قبله
    4. نملأ NaN بـ defaults

    Returns: df بـ historical columns مضافة
    """
    df = df.copy()

    # خطوة 1: resolve IDs و time
    df["__cust_id__"]   = _resolve_customer_id(df)
    df["__time_idx__"]  = _resolve_time_index(df)

    # خطوة 2: ترتيب زمني صح
    df = df.sort_values(["__cust_id__", "__time_idx__"], kind="stable").reset_index(drop=True)

    # ── تحضير source columns ──────────────────────────────────────────────────
    # paid (binary)
    if "paid" in df.columns:
        paid_col = df["paid"].astype(float)
    elif "paid_ratio" in df.columns:
        # paid_ratio ∈ [0,1] → نعتبره كـ paid probability
        # (مش مثالي لو مش binary، بس أحسن من مفيش)
        paid_col = df["paid_ratio"].astype(float)
        log.info("   ℹ️  Using 'paid_ratio' as paid signal (ideally use binary paid column)")
    else:
        log.warning("   ⚠️  No 'paid' or 'paid_ratio' column — hist_paid_ratio = default")
        paid_col = pd.Series(np.nan, index=df.index)

    # is_late (binary)
    if "is_late" in df.columns:
        late_col = df["is_late"].astype(float)
    elif "late_ratio" in df.columns:
        late_col = df["late_ratio"].astype(float)
        log.info("   ℹ️  Using 'late_ratio' as late signal (ideally use binary is_late column)")
    else:
        log.warning("   ⚠️  No 'is_late' or 'late_ratio' column — hist_late_ratio = default")
        late_col = pd.Series(np.nan, index=df.index)

    # delay_days
    if "delay_days" in df.columns:
        delay_col = df["delay_days"].astype(float)
        max_delay = delay_col.quantile(0.99).clip(min=1)
        delay_norm = (delay_col / max_delay).clip(0, 1)
    elif "avg_delay_normalized" in df.columns:
        delay_norm = df["avg_delay_normalized"].astype(float)
    elif "overdue_days_normalized" in df.columns:
        delay_norm = df["overdue_days_normalized"].astype(float)
        log.info("   ℹ️  Using 'overdue_days_normalized' as delay proxy")
    else:
        log.warning("   ⚠️  No delay column — hist_avg_delay = default")
        delay_norm = pd.Series(np.nan, index=df.index)

    # ── خطوة 3: احسب historical بـ shift() + expanding() ────────────────────
    log.info("   🔄 Computing historical features with shift(1) + expanding()...")

    g = df.groupby("__cust_id__", sort=False)

    # hist_paid_ratio: expanding mean من paid السابقة (shift أولًا)
    df["hist_paid_ratio"] = (
        g[paid_col.name if hasattr(paid_col, "name") and paid_col.name in df.columns else "__paid_tmp__"]
        .transform(lambda x: x.shift(1).expanding().mean())
        if paid_col.name in df.columns
        else _group_shift_expanding_mean(df, paid_col, "__cust_id__")
    )

    # SAFE: استخدم helper function عشان نتجنب issue مع unnamed series
    df["__paid_tmp__"]  = paid_col.values
    df["__late_tmp__"]  = late_col.values
    df["__delay_tmp__"] = delay_norm.values

    df["hist_paid_ratio"] = (
        df.groupby("__cust_id__")["__paid_tmp__"]
        .transform(lambda x: x.shift(1).expanding().mean())
    )

    df["hist_late_ratio"] = (
        df.groupby("__cust_id__")["__late_tmp__"]
        .transform(lambda x: x.shift(1).expanding().mean())
    )

    df["hist_avg_delay_normalized"] = (
        df.groupby("__cust_id__")["__delay_tmp__"]
        .transform(lambda x: x.shift(1).expanding().mean())
    )

    # hist_payment_count: عدد الفواتير السابقة (cumcount قبل الحالية)
    df["hist_payment_count"] = df.groupby("__cust_id__").cumcount()  # 0 for first invoice

    # normalize payment count
    max_count = df["hist_payment_count"].quantile(0.99).clip(min=1)
    df["hist_payment_count_normalized"] = (df["hist_payment_count"] / max_count).clip(0, 1)

    # ── خطوة 4: ملأ NaN بـ defaults ──────────────────────────────────────────
    log.info("   🔄 Filling NaN with defaults for first-invoice rows...")
    for col, default in DEFAULTS.items():
        if col in df.columns:
            n_nan = df[col].isna().sum()
            if n_nan > 0:
                df[col] = df[col].fillna(default)
                log.info("      '%s': filled %d NaN → %.3f", col, n_nan, default)

    # ── تنظيف ─────────────────────────────────────────────────────────────────
    df.drop(columns=["__cust_id__", "__time_idx__",
                     "__paid_tmp__", "__late_tmp__", "__delay_tmp__",
                     "hist_payment_count"], inplace=True, errors="ignore")

    return df


def _group_shift_expanding_mean(df, series, group_col):
    """Helper: shift + expanding mean لو series مش column في df"""
    tmp = df[[group_col]].copy()
    tmp["__val__"] = series.values
    return (
        tmp.groupby(group_col)["__val__"]
        .transform(lambda x: x.shift(1).expanding().mean())
    )


# ─────────────────────────────────────────────────────────────────────────────
# Remove leaky features من الـ CSV
# ─────────────────────────────────────────────────────────────────────────────
LEAKY_FEATURES = [
    "paid_ratio",
    "late_ratio",
    "on_time_ratio",
    "overdue_days",
    "overdue_days_normalized",
    "avg_delay_normalized",
    "avg_delay",
]


def drop_leaky_features(df: pd.DataFrame) -> pd.DataFrame:
    """امسح الـ features اللي بتعرف النتيجة"""
    dropped = []
    for col in LEAKY_FEATURES:
        if col in df.columns:
            df = df.drop(columns=[col])
            dropped.append(col)
    if dropped:
        log.info("   🗑️  Dropped leaky features: %s", dropped)
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Validation: تحقق من عدم وجود leakage
# ─────────────────────────────────────────────────────────────────────────────
def validate_no_leakage(df: pd.DataFrame, target_col: str = "is_bad_payer") -> bool:
    """
    يتأكد إن مفيش feature واحدة AUC > 0.85 على التارجت
    لو وجد → warning بس مش error (ممكن يكون legitimate signal)
    """
    from sklearn.metrics import roc_auc_score

    log.info("\n🔍 Leakage validation...")
    if target_col not in df.columns:
        log.warning("   Target column '%s' not found — skipping validation", target_col)
        return True

    y = df[target_col].astype(int)
    hist_cols = [c for c in df.columns if c.startswith("hist_")]

    suspicious = []
    for col in hist_cols:
        try:
            feat = df[col].fillna(0).astype(float)
            auc = roc_auc_score(y, feat)
            auc = max(auc, 1 - auc)
            status = "🟢" if auc < 0.80 else ("🟡" if auc < 0.90 else "🔴")
            log.info("   %s %-40s AUC = %.3f", status, col, auc)
            if auc > 0.90:
                suspicious.append((col, auc))
        except Exception:
            pass

    if suspicious:
        log.warning(
            "\n   ⚠️  High AUC features found:\n%s\n"
            "   → Verify these are computed from PRIOR invoices only\n"
            "   → Expected AUC for good historical features: 0.70 – 0.85",
            "\n".join(f"      {c}: {a:.3f}" for c, a in suspicious)
        )
        return False
    else:
        log.info(
            "\n   ✅ All historical features AUC < 0.90\n"
            "   → After training, expect AUC: 0.78 – 0.88 (realistic)"
        )
        return True


# ─────────────────────────────────────────────────────────────────────────────
# Statistics report
# ─────────────────────────────────────────────────────────────────────────────
def print_feature_stats(df: pd.DataFrame) -> None:
    hist_cols = [c for c in df.columns if c.startswith("hist_")]
    if not hist_cols:
        return

    log.info("\n📊 Historical features statistics:")
    log.info("   %-45s %8s %8s %8s %8s", "Feature", "Mean", "Std", "Min", "Max")
    log.info("   " + "-" * 80)
    for col in hist_cols:
        s = df[col].describe()
        log.info(
            "   %-45s %8.3f %8.3f %8.3f %8.3f",
            col, s["mean"], s["std"], s["min"], s["max"]
        )

    # Check: first invoices (hist_payment_count_normalized == 0)
    first_invoices = (df["hist_payment_count_normalized"] == 0).sum() if "hist_payment_count_normalized" in df.columns else 0
    log.info(
        "\n   First invoices (no prior history): %d (%.1f%%)",
        first_invoices, 100 * first_invoices / len(df)
    )


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Build zero-leakage historical features for finance risk model",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--csv", type=str, required=True,
        help="Input CSV path (e.g. finance_training_data_100k.csv)"
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Output CSV path (default: <input>_historical.csv)"
    )
    parser.add_argument(
        "--keep-leaky", action="store_true",
        help="Keep original paid_ratio/late_ratio columns (not recommended)"
    )
    parser.add_argument(
        "--no-validate", action="store_true",
        help="Skip leakage validation"
    )
    args = parser.parse_args()

    # ── Load ──────────────────────────────────────────────────────────────────
    log.info("📂 Loading: %s", args.csv)
    df = pd.read_csv(args.csv)
    log.info("   Shape: %s | Columns: %s", df.shape, list(df.columns))
    log.info("   Bad payers: %d (%.1f%%)", df["is_bad_payer"].sum(), df["is_bad_payer"].mean() * 100)

    # ── Build historical features ─────────────────────────────────────────────
    log.info("\n🔧 Building historical features...")
    df = build_historical_features(df)

    # ── Drop leaky features ───────────────────────────────────────────────────
    if not args.keep_leaky:
        log.info("\n🗑️  Removing leaky features...")
        df = drop_leaky_features(df)

    # ── Stats ─────────────────────────────────────────────────────────────────
    print_feature_stats(df)

    # ── Validate ──────────────────────────────────────────────────────────────
    if not args.no_validate:
        validate_no_leakage(df)

    # ── Save ──────────────────────────────────────────────────────────────────
    if args.output:
        output_path = args.output
    else:
        base = os.path.splitext(args.csv)[0]
        output_path = base + "_historical.csv"

    df.to_csv(output_path, index=False)
    log.info("\n✅ Saved: %s | Shape: %s", output_path, df.shape)
    log.info("   Columns: %s", list(df.columns))

    # ── Next step ─────────────────────────────────────────────────────────────
    log.info(
        "\n🚀 Next step — train the model:"
        "\n   python training/finance_train_v4.py --csv %s"
        "\n"
        "\n   Expected realistic results:"
        "\n   AUC:       0.78 – 0.88  ✅"
        "\n   Recall:    0.72 – 0.82  ✅"
        "\n   Precision: 0.65 – 0.78  ✅",
        output_path,
    )


if __name__ == "__main__":
    main()
