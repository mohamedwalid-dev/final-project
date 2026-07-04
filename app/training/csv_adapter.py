"""
🔧 Finance Training CSV Adapter — v1.0
=======================================
File: app/training/csv_adapter.py

يحل مشكلة: CSV بتاعك فيه columns pre-normalized بأسماء مختلفة
عن الـ schema اللي finance_train.py بيتوقعها.

CSV Columns الموجودة:
    amount_normalized, customer_age_normalized, invoice_frequency,
    credit_score_normalized, industry_risk_factor, seasonal_factor,
    is_bad_payer, amount, credit_score, industry, customer_age_months,
    payment_count, invoice_month, hist_paid_ratio, hist_late_ratio,
    hist_avg_delay_normalized, hist_payment_count_normalized

المشكلة:
    build_feature_matrix() بتدور على:
    - invoice_amount (مش amount_normalized)
    - age (مش customer_age_months)
    - years_with_company (مش موجودة خالص)
    - income_revenue (مش موجودة خالص)
    - credit_score (موجودة ✅)
    - credit_limit (مش موجودة)
    - outstanding_balance (مش موجودة)
    - debt_ratio (مش موجودة)
    وبتعمل np.full(len(df), default) لكل حاجة مش موجودة → features فاضية

الحل:
    AdaptedCSVLoader يعمل:
    1. Column mapping (rename الـ columns للأسماء المتوقعة)
    2. De-normalization لـ amount و credit_score (عشان build_feature_matrix تعيد normalize صح)
    3. Reconstruction للـ columns المفقودة من القيم المتاحة
    4. Passthrough للـ hist_* features (موجودة ومش محتاجة build_historical_features)
"""

from __future__ import annotations

import logging
import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants (من finance_train.py)
# ─────────────────────────────────────────────────────────────────────────────

INDUSTRY_RISK_INV = {
    0.40: "retail", 0.50: "hospitality", 0.60: "construction",
    0.35: "manufacturing", 0.25: "technology", 0.20: "healthcare",
    0.15: "education", 0.05: "government", 0.55: "real_estate",
    0.45: "food_beverage", 0.40: "transportation",
}

SEASONAL_RISK_INV = {
    0.50: 1,  0.45: 2,  0.35: 3,  0.30: 4,  0.30: 5,  0.40: 6,
    0.35: 7,  0.40: 8,  0.30: 9,  0.25: 10, 0.30: 11, 0.55: 12,
}

HIST_FEATURES = [
    "hist_paid_ratio", "hist_late_ratio", "hist_avg_delay_normalized",
    "hist_payment_count_normalized",
]

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
    "invoice_frequency_trend":       0.50,
    "payment_velocity":              0.50,
    "days_since_last_payment_norm":  0.30,
}


# ══════════════════════════════════════════════════════════════════════════════
class AdaptedCSVLoader:
    """
    Adapts pre-normalized CSV → schema expected by finance_train.py.

    يشتغل في خطوتين:
    Step 1: adapt_dataframe() → يحوّل الـ DataFrame للـ schema الصح
    Step 2: finance_train.build_feature_matrix() يشتغل عليه عادي

    Usage:
        from training.csv_adapter import AdaptedCSVLoader
        X, y, months, feature_names, df = AdaptedCSVLoader.load(csv_path)
    """

    # Map من الـ column names الموجودة في CSV → الأسماء المتوقعة
    COLUMN_MAP = {
        "payment_count":        "hist_payment_count_raw",   # سنحوّله لـ hist features
        "customer_age_months":  "customer_age_months",      # ✅ keep as-is
        "amount":               "invoice_amount",            # ✅ rename
        "invoice_month":        "invoice_month",             # ✅ keep
        "industry":             "industry",                  # ✅ keep
        "is_bad_payer":         "is_bad_payer",             # ✅ target
    }

    @classmethod
    def load(cls, csv_path: str) -> tuple:
        """
        Full pipeline: CSV → (X, y, months, feature_names, df)
        Drop-in replacement for finance_train.load_and_prepare_csv()
        """
        log.info("📂 [AdaptedCSVLoader] Loading: %s", csv_path)
        df_raw = pd.read_csv(csv_path)
        df_raw.columns = [c.strip().lower().replace(" ", "_") for c in df_raw.columns]

        log.info("   Raw shape: %s | columns: %s", df_raw.shape, list(df_raw.columns))

        df = cls.adapt_dataframe(df_raw)

        log.info("   Adapted shape: %s | bad_payer_rate: %.1f%%",
                 df.shape, df["is_bad_payer"].mean() * 100)

        # استدعي الـ feature matrix builder من finance_train
        from training.finance_train import (
            build_feature_matrix,
            LEAKY_FEATURES,
        )

        y      = df["is_bad_payer"].values.astype(int)
        months = df["invoice_month"].values.astype(int)

        # Drop leaky columns
        LEAKY_TO_DROP = LEAKY_FEATURES - {"is_bad_payer"}
        for lf in LEAKY_TO_DROP:
            if lf in df.columns:
                df.drop(columns=[lf], inplace=True, errors="ignore")

        X, feature_names = build_feature_matrix(df)
        log.info("   Feature matrix: %s | bad=%.1f%%", X.shape, y.mean() * 100)

        return X, y, months, feature_names, df

    @classmethod
    def adapt_dataframe(cls, df_raw: pd.DataFrame) -> pd.DataFrame:
        """
        Core adaptation logic.
        يحوّل الـ DataFrame من CSV schema → finance_train schema.
        """
        df = df_raw.copy()

        # ── Step 1: Reconstruct invoice_amount ───────────────────────────────
        # CSV فيه amount_normalized (0-1) و amount (القيمة الأصلية)
        if "amount" in df.columns and "invoice_amount" not in df.columns:
            df["invoice_amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(50_000)
            log.info("   ✅ invoice_amount ← amount")
        elif "amount_normalized" in df.columns and "invoice_amount" not in df.columns:
            # De-normalize: amount_normalized = amount / 500_000
            df["invoice_amount"] = df["amount_normalized"] * 500_000
            log.info("   ✅ invoice_amount ← amount_normalized × 500,000")

        # ── Step 2: Reconstruct credit_score ─────────────────────────────────
        if "credit_score" not in df.columns and "credit_score_normalized" in df.columns:
            # credit_score_normalized = credit_score / 850
            df["credit_score"] = (df["credit_score_normalized"] * 850).clip(300, 850)
            log.info("   ✅ credit_score ← credit_score_normalized × 850")
        elif "credit_score" in df.columns:
            df["credit_score"] = pd.to_numeric(df["credit_score"], errors="coerce").fillna(650)

        # ── Step 3: Reconstruct age ───────────────────────────────────────────
        if "age" not in df.columns:
            if "customer_age_normalized" in df.columns:
                # customer_age_normalized = age / 80 (roughly)
                df["age"] = (df["customer_age_normalized"] * 80).clip(18, 80)
                log.info("   ✅ age ← customer_age_normalized × 80")
            else:
                df["age"] = 35.0
                log.warning("   ⚠️  age → default 35")

        # ── Step 4: Reconstruct years_with_company ────────────────────────────
        if "years_with_company" not in df.columns:
            if "customer_age_months" in df.columns:
                # استخدم customer_age_months كـ proxy لـ years_with_company
                df["years_with_company"] = (
                    pd.to_numeric(df["customer_age_months"], errors="coerce").fillna(24) / 12
                ).clip(0, 30)
                log.info("   ✅ years_with_company ← customer_age_months / 12")
            else:
                df["years_with_company"] = 3.0
                log.warning("   ⚠️  years_with_company → default 3")

        # ── Step 5: Reconstruct income_revenue ────────────────────────────────
        if "income_revenue" not in df.columns:
            if "invoice_amount" in df.columns:
                # income = invoice_amount * 10 (rough proxy)
                df["income_revenue"] = (df["invoice_amount"] * 10).clip(50_000, 10_000_000)
                log.info("   ✅ income_revenue ← invoice_amount × 10 (proxy)")
            else:
                df["income_revenue"] = 500_000.0
                log.warning("   ⚠️  income_revenue → default 500,000")

        # ── Step 6: Reconstruct credit_limit & outstanding_balance ────────────
        if "credit_limit" not in df.columns:
            # proxy: credit_limit ~ credit_score * 100
            df["credit_limit"] = (df["credit_score"] * 100).clip(5_000, 500_000)
            log.info("   ✅ credit_limit ← credit_score × 100 (proxy)")

        if "outstanding_balance" not in df.columns:
            if "hist_late_ratio" in df.columns:
                df["outstanding_balance"] = (
                    df["invoice_amount"] * df["hist_late_ratio"] * 0.5
                ).clip(0, 500_000)
                log.info("   ✅ outstanding_balance ← invoice_amount × hist_late_ratio × 0.5 (proxy)")
            else:
                df["outstanding_balance"] = (df["invoice_amount"] * 0.1).clip(0, 50_000)

        # ── Step 7: Reconstruct debt_ratio ────────────────────────────────────
        if "debt_ratio" not in df.columns:
            df["debt_ratio"] = (
                df["outstanding_balance"] / df["income_revenue"].replace(0, 1)
            ).clip(0, 1)
            log.info("   ✅ debt_ratio ← outstanding_balance / income_revenue")

        # ── Step 8: invoice_frequency ────────────────────────────────────────
        if "invoice_frequency" not in df.columns:
            df["invoice_frequency"] = 0.40
            log.warning("   ⚠️  invoice_frequency → default 0.40")
        else:
            df["invoice_frequency"] = pd.to_numeric(
                df["invoice_frequency"], errors="coerce"
            ).fillna(0.40).clip(0, 1)

        # ── Step 9: industry ─────────────────────────────────────────────────
        if "industry" not in df.columns:
            if "industry_risk_factor" in df.columns:
                # reverse-map industry_risk_factor → industry name
                def _inv_industry(risk_val):
                    risk_val = round(float(risk_val), 2)
                    if risk_val <= 0.05: return "government"
                    if risk_val <= 0.15: return "education"
                    if risk_val <= 0.20: return "healthcare"
                    if risk_val <= 0.25: return "technology"
                    if risk_val <= 0.35: return "manufacturing"
                    if risk_val <= 0.40: return "retail"
                    if risk_val <= 0.45: return "food_beverage"
                    if risk_val <= 0.50: return "hospitality"
                    if risk_val <= 0.55: return "real_estate"
                    return "construction"
                df["industry"] = df["industry_risk_factor"].apply(_inv_industry)
                log.info("   ✅ industry ← industry_risk_factor (reverse-mapped)")
            else:
                df["industry"] = "unknown"
                log.warning("   ⚠️  industry → default 'unknown'")
        else:
            df["industry"] = df["industry"].fillna("unknown").astype(str)

        # ── Step 10: business_type ────────────────────────────────────────────
        if "business_type" not in df.columns:
            df["business_type"] = "B2B"

        # ── Step 11: days_to_due ─────────────────────────────────────────────
        if "days_to_due" not in df.columns:
            df["days_to_due"] = 30.0

        # ── Step 12: days_since_last_payment ─────────────────────────────────
        if "days_since_last_payment" not in df.columns:
            df["days_since_last_payment"] = 30.0

        # ── Step 13: customer_id & invoice_seq ───────────────────────────────
        if "customer_id" not in df.columns:
            df["customer_id"] = [f"CUST-{str(i // 10).zfill(6)}" for i in range(len(df))]

        if "invoice_seq" not in df.columns:
            df["invoice_seq"] = df.groupby("customer_id").cumcount()

        # ── Step 14: payment_delay & is_bad_payer ────────────────────────────
        if "is_bad_payer" in df.columns:
            df["is_bad_payer"] = df["is_bad_payer"].astype(int)
            df["payment_delay"] = df["is_bad_payer"].apply(lambda x: 31 if x == 1 else 0)
        else:
            df["payment_delay"] = 0
            df["is_bad_payer"]  = 0

        # ── Step 15: Inject pre-computed hist_* features ──────────────────────
        # الـ CSV عنده hist features جاهزة → ناخدها مباشرة بدل ما نحسبها
        cls._inject_hist_features(df, df_raw)

        # ── Step 16: invoice_month ────────────────────────────────────────────
        if "invoice_month" not in df.columns:
            df["invoice_month"] = 6
        else:
            df["invoice_month"] = pd.to_numeric(
                df["invoice_month"], errors="coerce"
            ).fillna(6).astype(int).clip(1, 12)

        return df

    @classmethod
    def _inject_hist_features(cls, df: pd.DataFrame, df_raw: pd.DataFrame) -> None:
        """
        الـ CSV عنده hist features pre-computed → ناخدها مباشرة.
        ده أحسن من حسابهم من أول لأن البيانات فعلاً مش فيها تسلسل تاريخي صح.
        """

        # hist_paid_ratio
        if "hist_paid_ratio" in df_raw.columns:
            df["hist_paid_ratio"] = pd.to_numeric(
                df_raw["hist_paid_ratio"], errors="coerce"
            ).fillna(0.75).clip(0, 1)
        else:
            df["hist_paid_ratio"] = 0.75

        # hist_late_ratio
        if "hist_late_ratio" in df_raw.columns:
            df["hist_late_ratio"] = pd.to_numeric(
                df_raw["hist_late_ratio"], errors="coerce"
            ).fillna(0.15).clip(0, 1)
        else:
            df["hist_late_ratio"] = 0.15

        # hist_avg_delay_normalized
        if "hist_avg_delay_normalized" in df_raw.columns:
            df["hist_avg_delay_normalized"] = pd.to_numeric(
                df_raw["hist_avg_delay_normalized"], errors="coerce"
            ).fillna(0.10).clip(0, 1)
        else:
            df["hist_avg_delay_normalized"] = 0.10

        # hist_payment_count_normalized
        if "hist_payment_count_normalized" in df_raw.columns:
            df["hist_payment_count_normalized"] = pd.to_numeric(
                df_raw["hist_payment_count_normalized"], errors="coerce"
            ).fillna(0.0).clip(0, 1)
        elif "payment_count" in df_raw.columns:
            max_count = df_raw["payment_count"].quantile(0.99)
            df["hist_payment_count_normalized"] = (
                df_raw["payment_count"] / max(max_count, 1)
            ).clip(0, 1)
            log.info("   ✅ hist_payment_count_normalized ← payment_count / max_count")
        else:
            df["hist_payment_count_normalized"] = 0.0

        # ── Derive additional hist features from available ones ───────────────

        # hist_paid_ratio_3 — use same as hist_paid_ratio (best approximation)
        df["hist_paid_ratio_3"] = df["hist_paid_ratio"]
        df["hist_paid_ratio_6"] = df["hist_paid_ratio"]
        df["hist_late_ratio_3"] = df["hist_late_ratio"]

        # paid_trend / late_trend — دلالياً صفر (مش عندنا تسلسل زمني)
        df["paid_trend"] = 0.0
        df["late_trend"] = 0.0

        # last_paid / last_late — proxy من الـ hist ratios
        df["last_paid"] = df["hist_paid_ratio"]
        df["last_late"] = df["hist_late_ratio"]

        # hist_max_delay — proxy من hist_avg_delay
        df["hist_max_delay"] = (df["hist_avg_delay_normalized"] * 1.5).clip(0, 1)

        # delay_variance — proxy
        df["delay_variance"] = (df["hist_avg_delay_normalized"] * 0.5).clip(0, 1)

        # late_streak — proxy: لو hist_late_ratio > 0.5 → متصاعد
        df["late_streak"] = (df["hist_late_ratio"] > 0.5).astype(float) * 0.5

        # good_streak — proxy
        df["good_streak"] = (df["hist_paid_ratio"] > 0.8).astype(float) * 0.6

        # invoice_frequency_trend
        df["invoice_frequency_trend"] = 0.5

        # payment_velocity
        df["payment_velocity"] = df["hist_paid_ratio"]

        # days_since_last_payment_norm
        df["days_since_last_payment_norm"] = 0.30

        log.info(
            "   ✅ hist_* features injected: paid=%.3f late=%.3f delay=%.3f count=%.3f",
            df["hist_paid_ratio"].mean(),
            df["hist_late_ratio"].mean(),
            df["hist_avg_delay_normalized"].mean(),
            df["hist_payment_count_normalized"].mean(),
        )
