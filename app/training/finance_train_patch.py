"""
🔧 finance_train_patch.py — Schema-Aware CSV Loader
=====================================================
File: app/training/finance_train_patch.py

هذا الملف يحتوي على نسخة معدّلة من load_and_prepare_csv()
تتعامل مع الـ CSV بتاعك اللي columns بتاعته pre-normalized.

طريقة الاستخدام:
    بدل ما تشغّل:
        python training/finance_train.py --csv data.csv

    شغّل:
        python training/finance_train_patch.py --csv data.csv --mode balanced

    أو عدّل finance_train.py وحط في أول load_and_prepare_csv():
        from training.finance_train_patch import smart_load_csv as load_and_prepare_csv
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

import numpy as np
import pandas as pd

# ── Add app/ to path ──────────────────────────────────────────────────────────
APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Features مشكوك في leakage بتاعتها
# ─────────────────────────────────────────────────────────────────────────────
# credit_score_normalized → AUC=0.905 (predictive جداً = مشتق من payment history)
# credit_score_bucket     → AUC=0.862 (derived من credit_score_normalized)
# credit_x_late           → AUC=0.905 (credit_score × hist_late_ratio = double leakage)
# credit_score            → الأصل اللي بيولّد كل ده
LEAKAGE_FEATURES = {
    "credit_score_normalized",
    "credit_score_bucket",
    "credit_x_late",
    "credit_score",
}

# ─────────────────────────────────────────────────────────────────────────────
# Column detection
# ─────────────────────────────────────────────────────────────────────────────

def _detect_schema(columns: list[str]) -> str:
    """
    Detect which CSV schema we have.

    Returns:
        "native"      — columns match finance_train expected schema
        "pre_normed"  — columns are pre-normalized (CSV بتاعك)
        "mixed"       — بعضهم موجود وبعضهم لا
    """
    native_signals  = {"invoice_amount", "age", "years_with_company", "income_revenue"}
    prenorm_signals = {"amount_normalized", "customer_age_normalized",
                       "credit_score_normalized", "industry_risk_factor"}

    cols = set(columns)
    has_native  = len(native_signals  & cols) >= 2
    has_prenorm = len(prenorm_signals & cols) >= 2

    if has_native and not has_prenorm:
        return "native"
    if has_prenorm:
        return "pre_normed"
    return "mixed"


# ─────────────────────────────────────────────────────────────────────────────
# Smart Loader
# ─────────────────────────────────────────────────────────────────────────────

def smart_load_csv(csv_path: str) -> tuple:
    """
    Drop-in replacement for finance_train.load_and_prepare_csv().

    تلقائياً يكتشف الـ schema ويختار الـ loader المناسب:
    - "native"    → finance_train.load_and_prepare_csv() العادية
    - "pre_normed" → AdaptedCSVLoader.load() (بتاعتنا)
    - "mixed"     → AdaptedCSVLoader.load() مع تحذير
    """
    log.info("📂 [smart_load_csv] Reading: %s", csv_path)
    header = pd.read_csv(csv_path, nrows=0)
    columns = [c.strip().lower().replace(" ", "_") for c in header.columns]
    schema = _detect_schema(columns)
    log.info("   Schema detected: %s", schema)

    if schema == "native":
        log.info("   ✅ Using native finance_train loader")
        from training.finance_train import load_and_prepare_csv
        return load_and_prepare_csv(csv_path)
    else:
        if schema == "mixed":
            log.warning(
                "   ⚠️  Mixed schema detected — using AdaptedCSVLoader. "
                "Review column mappings carefully."
            )
        else:
            log.info("   ✅ Pre-normalized schema — using AdaptedCSVLoader")
        from training.csv_adapter import AdaptedCSVLoader
        return AdaptedCSVLoader.load(csv_path)


# ─────────────────────────────────────────────────────────────────────────────
# Leakage feature removal
# ─────────────────────────────────────────────────────────────────────────────

def drop_leakage_features(
    X: np.ndarray,
    feature_names: list[str],
) -> tuple[np.ndarray, list[str]]:
    """
    يشيل الـ features اللي AUC بتاعتها عالية جداً بشكل مريب
    لأنها derived من payment history بشكل غير مباشر.

    بيرجع (X_clean, feature_names_clean).
    """
    drop_idx = [i for i, f in enumerate(feature_names) if f in LEAKAGE_FEATURES]
    if not drop_idx:
        log.info("✅ No leakage features found — nothing to drop")
        return X, feature_names

    dropped = [feature_names[i] for i in drop_idx]
    log.warning("🚨 Dropping %d leakage feature(s): %s", len(dropped), dropped)

    X_clean = np.delete(X, drop_idx, axis=1)
    names_clean = [f for f in feature_names if f not in LEAKAGE_FEATURES]

    log.info(
        "   Features: %d → %d (removed %d)",
        len(feature_names), len(names_clean), len(dropped),
    )
    return X_clean, names_clean


# ─────────────────────────────────────────────────────────────────────────────
# Standalone training entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    """
    Runs the full finance_train pipeline with smart CSV loading.
    Accepts all the same args as finance_train.py main().
    """
    # Import everything from finance_train
    from training.finance_train import (
        safe_preprocess, tune_hyperparameters, train,
        generate_synthetic_data, compute_drift_baseline,
        DecisionEngine, DecisionLogger, FinanceRiskPredictorV8,
        DECISION_MODES, MODEL_PATH, METADATA_PATH, REPORT_PATH,
        DECISION_LOG, OVERRIDE_LOG, LOG_DIR,
    )
    import json
    import pickle
    import shutil
    import warnings
    from datetime import datetime
    warnings.filterwarnings("ignore")

    parser = argparse.ArgumentParser(
        description="Finance Risk Model Training — Schema-Aware Loader",
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
    parser.add_argument("--no-drop-leakage", action="store_true",
                        help="Skip automatic leakage feature removal")
    args = parser.parse_args()

    # ── Override paths if --output given ─────────────────────────────────────
    mp = args.output or MODEL_PATH
    meta_p  = mp.replace(".pkl", "_metadata.json")
    rep_p   = mp.replace(".pkl", "_report.txt")
    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(mp)), exist_ok=True)

    print("=" * 65)
    print("  💰 Finance Risk Model — Schema-Aware Training")
    print("=" * 65)
    print(f"  CSV:          {args.csv or 'synthetic fallback'}")
    print(f"  Mode:         {args.mode}  [{DECISION_MODES[args.mode]['description']}]")
    print(f"  Bad payer:    payment_delay > {args.bad_days} days")
    print(f"  FP Penalty:   x{args.fp_penalty}")
    print(f"  Max FP rate:  {args.max_fp_rate:.0%}")
    print(f"  Folds:        {args.folds} | Optuna: {args.trials} trials")
    print(f"  Drop leakage: {'no (--no-drop-leakage)' if args.no_drop_leakage else 'yes (auto)'}")
    print("=" * 65)

    # ── Load data ─────────────────────────────────────────────────────────────
    X = y = months = feature_names = df = None
    if args.csv:
        try:
            X, y, months, feature_names, df = smart_load_csv(args.csv)
        except Exception as e:
            log.error("CSV load failed: %s", e, exc_info=True)
            raise

    if X is None:
        log.info("No CSV — using synthetic data")
        X, y, months, feature_names, df = generate_synthetic_data(
            n_customers=args.n_customers
        )

    # ── Drop leakage features ─────────────────────────────────────────────────
    if not args.no_drop_leakage:
        X, feature_names = drop_leakage_features(X, feature_names)

    log.info("\n📦 Dataset: %d rows | %d features | bad=%.1f%%",
             len(X), X.shape[1], y.mean() * 100)

    # ── Optuna tuning ─────────────────────────────────────────────────────────
    best_params = {}
    if args.trials > 0 and not args.dry_run:
        best_params = tune_hyperparameters(safe_preprocess(X), y, n_trials=args.trials)

    # ── Train ─────────────────────────────────────────────────────────────────
    if args.no_smote:
        import training.finance_train as ft_mod
        ft_mod.apply_smote = lambda X, y: (X, y)

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

    # ── Save ─────────────────────────────────────────────────────────────────
    logger_obj = DecisionLogger()
    metadata = {
        "version":       "8.1.1-adapted",
        "trained_at":    datetime.utcnow().isoformat() + "Z",
        "n_samples":     len(X),
        "feature_count": len(feature_names),
        "feature_names": feature_names,
        "csv_schema":    "pre_normalized_adapted",
        "leakage_features_dropped": list(LEAKAGE_FEATURES) if not args.no_drop_leakage else [],
        "ensemble_weights": result["ensemble"]["weights"],
        "decision_engine":  result["decision_engine"].to_dict(),
        "cost_optimization": result["cost_result"],
        "metrics":           result["metrics"],
        "cv_results":        result["cv_results"],
        "shap_importance":   result["shap_importance"],
        "calibration":       result["calibration"],
        "drift_baseline":    compute_drift_baseline(X, feature_names),
    }

    predictor = FinanceRiskPredictorV8(
        ensemble=result["ensemble"],
        decision_engine=result["decision_engine"],
        feature_names=feature_names,
        shap_importance=result["shap_importance"],
        metadata=metadata,
        logger=logger_obj,
    )

    save_data = {"predictor": predictor, "ensemble": result["ensemble"], "metadata": metadata}

    try:
        import cloudpickle
        with open(mp, "wb") as f:
            cloudpickle.dump(save_data, f)
        log.info("✅ Saved with cloudpickle → %s", mp)
    except ImportError:
        with open(mp, "wb") as f:
            pickle.dump(save_data, f)
        log.info("✅ Saved with pickle → %s", mp)

    with open(meta_p, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, default=str, ensure_ascii=False)
    with open(rep_p, "w", encoding="utf-8") as f:
        f.write(result["report_text"])

    # Copy to API models dir
    BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
    API_MODEL_DIR = os.path.join(BASE_DIR, "..", "models", "finance")
    os.makedirs(API_MODEL_DIR, exist_ok=True)
    shutil.copy2(mp,     os.path.join(API_MODEL_DIR, "payment_risk_v8.pkl"))
    shutil.copy2(meta_p, os.path.join(API_MODEL_DIR, "metadata_v8.json"))
    log.info("✅ Copied to API models dir: %s", API_MODEL_DIR)

    m = result["metrics"]
    print(f"\n{'=' * 65}")
    print(f"  ✅ Model saved: {mp}")
    print(f"{'=' * 65}")
    print(f"  ROC AUC:    {m['roc_auc']:.4f}")
    print(f"  PR AUC:     {m['pr_auc']:.4f}")
    print(f"  Precision:  {m['precision_cost']:.4f}")
    print(f"  Recall:     {m['recall_cost']:.4f}")
    print(f"  FP-rate:    {m['fp_rate']:.1%}")
    print(f"  Threshold:  {result['cost_result']['threshold']:.2f}")
    print(f"{'=' * 65}")
    print(f"\n🚀 Next: restart FastAPI — model loads automatically.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    main()