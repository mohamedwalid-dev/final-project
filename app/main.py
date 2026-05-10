"""
main.py — AI Enterprise ERP System v5.2
=========================================
# uvicorn main:app --host 0.0.0.0 --port 9000 --reload

✅ v5.0 Fixes:
    1. /leaves/submit: event_id created BEFORE event queue trigger → FK satisfied
    2. /leaves/submit: poll_leave_decision reads fresh DB status correctly
    3. All %d format strings with potential None values → use %s
    4. leaves table updated with ai_decision + confidence_score after decision
    5. CORS + global exception handler kept production-ready

✅ v5.1 Additions:
    6. Salary Reviews  — /salary-reviews/*
    7. Incentive Requests — /incentives/*
    8. Absence Events  — /absences/*
    9. Employee aggregated views for all new domains
    10. All new imports and schemas integrated (no dead string blocks)

✅ v5.2 Additions:
    11. Finance Risk API — /finance/* (merged from api/routes/finance.py)
        - DecisionEngine, FinanceRiskPredictor, feature engineering
        - POST /finance/predict-risk
        - POST /finance/predict-risk/batch
        - GET  /finance/model/info
        - POST /finance/model/reload
   0     - GET  /finance/model/thresholds
"""

import json
import logging
import os
import asyncio
import pickle
import warnings
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Optional, List

import numpy as np

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field, validator
from dotenv import load_dotenv

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

from core.db import (
    init_db_pool, health_check,
    # Employees
    get_employee, get_all_employees,
    # Leaves
    create_leave_request, get_pending_leaves, get_leave,
    update_leave_status, get_employee_leaves, get_leave_status,
    # Tickets
    create_ticket, get_pending_tickets, update_ticket_status,
    # Leads
    create_lead, get_new_leads, update_lead_status,
    # Events / Decisions / Actions / Audit
    create_event, get_pending_events, mark_event_done,
    save_decision, log_action, write_audit_log,
    # Execution tracker
    start_execution, finish_execution,
    # Memory
    save_memory, get_memory, get_all_memory,
    # Fix 2 — balance history
    get_balance_history,
    # Fix 4 — decision audit
    write_decision_audit,
    # Salary Reviews
    create_salary_review, get_salary_review,
    get_pending_salary_reviews, update_salary_review_status,
    get_employee_salary_reviews,
    # Incentive Requests
    create_incentive_request, get_incentive_request,
    get_pending_incentive_requests, update_incentive_status,
    get_employee_incentives,
    # Absence Events
    create_absence_event, get_absence_event,
    get_pending_absence_events, update_absence_event_status,
    get_employee_absences, get_employee_unexcused_count_90d,
    # HR Domain Audit
    get_hr_domain_audit,
)

from orchestrator.orchestrator import Orchestrator
from config.settings import get_settings

from core.trigger import (
    start_trigger_engine,
    stop_trigger_engine,
    get_scheduler_status,
    job_scan_pending_leaves,
    job_scan_pending_tickets,
    job_scan_new_leads,
    job_process_event_queue,
    job_scan_pending_salary_reviews,
    job_scan_pending_incentives,
    job_scan_pending_absences,
)
from core.webhook_handler import webhook_router
from core.event_bus import event_bus

from core.finance_db import init_finance_db
from core.finance_trigger import (
    job_scan_overdue_invoices,
    job_scan_new_invoices,
    register_finance_handlers,
    INVOICE_SCAN_SEC,
    NEW_INVOICE_SCAN_SEC,
)

from workflows.hr.leave_approval_workflow import LeaveApprovalWorkflow
from agents.hr.leave_model_handler import get_model_handler
from api.routes.finance_seed_routes import finance_seed_router
from core.finance_realtime import finance_realtime_router
from core.metrics_collector import start_metrics_collector, get_metrics_collector
from fastapi import WebSocket, WebSocketDisconnect


load_dotenv()
settings = get_settings()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

orchestrator   = Orchestrator()
leave_workflow = LeaveApprovalWorkflow()


# ─────────────────────────────────────────────────────────────────────────────
# Lifespan
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 AI Enterprise ERP starting up...")

    init_db_pool()
    logger.info("✅ DB pool ready")

    try:
        handler = get_model_handler()
        if handler.is_loaded():
            info = handler.get_info()
            logger.info(
                "✅ ML Model loaded | accuracy=%s | AUC=%s | features=%s",
                info.get("accuracy"), info.get("roc_auc"), info.get("feature_count"),
            )
        else:
            logger.warning(
                "⚠️ ML Model not found — fallback rules will be used. "
                "Run: python training/hr_train.py"
            )
    except Exception as e:
        logger.warning("⚠️ ML Model warm-up failed: %s", e)

    await start_trigger_engine(orchestrator)
    logger.info("✅ Trigger Engine started")

    # Finance DB tables
    try:
        init_finance_db()
        logger.info("✅ Finance DB tables initialized")
    except Exception as e:
        logger.warning("⚠️ Finance DB init failed: %s", e)

    # Finance risk model — pre-load at startup
    try:
        fin_pred = _load_fin_predictor()
        if fin_pred:
            logger.info("✅ Finance risk model ready for /finance/predict-risk")
        else:
            logger.warning(
                "⚠️ Finance risk model not loaded — /finance/predict-risk will return 503.\n"
                "   Run: python training/finance_train.py"
            )
    except Exception as e:
        logger.warning("⚠️ Finance risk model startup load failed: %s", e)

    print("\n" + "═" * 60)
    print(f"  🧠  {settings.APP_NAME}  —  ERP v5.1")
    print(f"  📦  Version     : {settings.APP_VERSION}")
    print(f"  🤖  LLM         : {settings.GEMINI_MODEL} ({settings.LLM_PROVIDER})")
    print(f"  🌡️   Temperature : {settings.LLM_TEMPERATURE}")
    print(f"  ⚡  Triggers     : Scheduler + DB Watcher + Webhooks")
    print(f"  🔑  API Key     : {'✅ Set' if settings.GOOGLE_API_KEY else '❌ Missing!'}")
    print(f"  📖  Docs        : http://localhost:9000/docs")
    print("═" * 60 + "\n")

    await start_metrics_collector()          # ← هنا قبل yield
    logger.info("✅ MetricsCollector started")

    yield                                    # ← yield واحد بس

    logger.info("🔴 Shutting down...")
    stop_trigger_engine()
    get_metrics_collector().stop()
    logger.info("🔴 MetricsCollector stopped")


# ─────────────────────────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title=f"🧠 {settings.APP_NAME} — ERP",
    description=(
        "Autonomous ERP powered by AI agents (LangChain + Google Gemini).\n\n"
        "**Modules:** HR · Leaves · Salary · Incentives · Absences · "
        "Tickets · Leads · CRM · Events · Memory · Audit\n\n"
        "**v5.1:** Full HR Domain Suite — Salary / Incentive / Absence workflows"
    ),
    version="5.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS or os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook_router, prefix="/webhooks", tags=["🌐 Webhooks"])
app.include_router(finance_seed_router, prefix="/finance", tags=["💰 Finance - Seed"])
app.include_router(finance_realtime_router, prefix="/finance", tags=["📡 Finance - Live"])

# Mount static files for UI widgets
import os
os.makedirs("app/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled error: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "status":    "error",
            "detail":    f"Internal server error: {str(exc)}",
            "type":      type(exc).__name__,
            "path":      str(request.url),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# 💰 Finance Risk — ML Engine (merged from api/routes/finance.py)
# ─────────────────────────────────────────────────────────────────────────────

# ── Domain constants ─────────────────────────────────────────────────────────
_INDUSTRY_RISK = {
    "retail": 0.40, "hospitality": 0.50, "construction": 0.60,
    "manufacturing": 0.35, "technology": 0.25, "healthcare": 0.20,
    "education": 0.15, "government": 0.05, "financial": 0.20,
    "real_estate": 0.55, "food_beverage": 0.45,
    "transportation": 0.40, "unknown": 0.40,
}

_SEASONAL_RISK = {
    1: 0.50, 2: 0.45, 3: 0.35, 4: 0.30, 5: 0.30, 6: 0.40,
    7: 0.35, 8: 0.40, 9: 0.30, 10: 0.25, 11: 0.30, 12: 0.55,
}

FIN_BASE_FEATURES = [
    "overdue_days_normalized", "amount_normalized", "paid_ratio",
    "late_ratio", "on_time_ratio", "customer_age_normalized",
    "invoice_frequency", "avg_delay_normalized", "credit_score_normalized",
    "industry_risk_factor", "seasonal_factor",
]
FIN_ENGINEERED_V2 = ["amount_x_overdue", "credit_x_late_ratio", "risk_score_composite"]
FIN_ENGINEERED_V3 = [
    "payment_trend", "payment_volatility", "clv_proxy",
    "rolling_avg_delay", "overdue_x_industry", "credit_age_interaction",
]
FIN_FEATURE_NAMES = FIN_BASE_FEATURES + FIN_ENGINEERED_V2 + FIN_ENGINEERED_V3

_FIN_MODEL_DIR  = os.path.join(os.path.dirname(__file__), "models", "finance")
_FIN_MODEL_PATH = os.path.join(_FIN_MODEL_DIR, "payment_risk_v8.pkl")
os.makedirs(_FIN_MODEL_DIR, exist_ok=True)


class FinanceDecisionEngine:
    """
    Translates ML probability → business decision.
    reject / manual_review / approve
    """
    def __init__(self, reject_threshold: float = 0.70, review_threshold: float = 0.45):
        self.reject_threshold = reject_threshold
        self.review_threshold = review_threshold

    def decide(self, prob: float) -> dict:
        if prob >= self.reject_threshold:
            decision   = "reject"
            confidence = prob
        elif prob >= self.review_threshold:
            decision   = "manual_review"
            confidence = 1.0 - abs(prob - (self.reject_threshold + self.review_threshold) / 2)
        else:
            decision   = "approve"
            confidence = 1.0 - prob
        return {
            "decision":   decision,
            "risk_score": round(prob, 4),
            "confidence": round(confidence, 4),
            "reasons":    [],
        }

    def explain(self, decision_dict: dict, shap_values: dict) -> dict:
        reason_map = {
            "overdue_days_normalized": "High overdue days",
            "late_ratio":              "High late payment ratio",
            "credit_score_normalized": "Low credit score",
            "industry_risk_factor":    "High-risk industry",
            "avg_delay_normalized":    "Long average payment delays",
            "amount_x_overdue":        "Large overdue amount",
            "risk_score_composite":    "High composite risk score",
            "payment_volatility":      "Unstable payment behavior",
            "payment_trend":           "Worsening payment trend",
            "overdue_x_industry":      "Sector + overdue compound risk",
        }
        sorted_features = sorted(shap_values.items(), key=lambda x: abs(x[1]), reverse=True)
        reasons = [
            reason_map[f] for f, v in sorted_features[:3]
            if abs(v) > 0.01 and f in reason_map
        ]
        decision_dict["reasons"] = reasons or ["General risk assessment"]
        return decision_dict

    def to_dict(self) -> dict:
        return {"reject_threshold": self.reject_threshold, "review_threshold": self.review_threshold}


def _fin_safe_preprocess(X: np.ndarray) -> np.ndarray:
    """NaN/Inf imputation + IQR outlier clipping."""
    X = X.copy().astype(np.float64)
    X[~np.isfinite(X)] = np.nan
    for col in range(X.shape[1]):
        mask = np.isnan(X[:, col])
        if mask.any():
            X[mask, col] = float(np.nanmedian(X[:, col]))
    for col in range(X.shape[1]):
        q1, q3 = np.percentile(X[:, col], [25, 75])
        iqr = q3 - q1
        X[:, col] = np.clip(X[:, col], q1 - 3 * iqr, q3 + 3 * iqr)
    return X


def _fin_add_features(X: np.ndarray) -> np.ndarray:
    """Add v2 + v3 engineered features."""
    # v2
    amount_x_overdue = X[:, 1] * X[:, 0]
    credit_x_late    = (1 - X[:, 8]) * X[:, 3]
    risk_composite   = (
        0.30 * X[:, 0] + 0.25 * X[:, 3] + 0.20 * (1 - X[:, 8]) +
        0.15 * X[:, 9] + 0.10 * X[:, 10]
    )
    # v3
    def _cn(a, cap=1.0): return np.clip(a, 0, cap)
    payment_std       = X[:, 3] * (1 - X[:, 2])
    trend_raw         = X[:, 2] - X[:, 3]
    clv_raw           = X[:, 1] * X[:, 5] * X[:, 6]
    rolling_delay     = 0.7 * X[:, 7] + 0.3 * (1 - X[:, 2])
    payment_trend     = _cn((trend_raw + 1) / 2)
    payment_vol       = _cn(payment_std)
    clv_proxy         = _cn(clv_raw)
    rolling_avg_delay = _cn(rolling_delay)
    overdue_x_ind     = _cn(X[:, 0] * X[:, 9])
    credit_age_inter  = _cn(X[:, 8] * X[:, 5])
    return np.column_stack([
        X,
        amount_x_overdue, credit_x_late, risk_composite,
        payment_trend, payment_vol, clv_proxy,
        rolling_avg_delay, overdue_x_ind, credit_age_inter,
    ])


def _fin_ensemble_predict_proba(ensemble: dict, X: np.ndarray) -> np.ndarray:
    weights = ensemble["weights"]
    if len(weights) == 2:
        xgb_w, lgbm_w = weights
        lr_w = 0.0
    else:
        xgb_w, lgbm_w, lr_w = weights
    proba = ensemble["xgb"].predict_proba(X)[:, 1] * xgb_w
    if ensemble.get("lgbm") and lgbm_w > 0:
        proba += ensemble["lgbm"].predict_proba(X)[:, 1] * lgbm_w
    if ensemble.get("lr") and lr_w > 0:
        lr_data = ensemble["lr"]
        X_scaled = lr_data["scaler"].transform(X)
        proba += lr_data["model"].predict_proba(X_scaled)[:, 1] * lr_w
    return proba


# Alias used by _V8FinanceRiskPredictor (v8 pickle may store a 3-weight ensemble)
ensemble_predict_proba_v8 = _fin_ensemble_predict_proba


def _fin_array_to_dict(row: np.ndarray) -> dict:
    """Convert an 11-element base-feature numpy row → dict with field names.

    Used by _V8FinanceRiskPredictor so that the v8 predictor's _to_features()
    method can rebuild all 41 engineered features from the 11-element API input.
    """
    keys = FIN_BASE_FEATURES  # 11 names defined above
    return {k: float(v) for k, v in zip(keys, row)}


class FinanceRiskPredictor:
    """
    Production inference wrapper: ensemble + FinanceDecisionEngine.

    This local class mirrors the one saved inside the training pickle so that
    models trained with the v3 script (which stores a FinanceRiskPredictor)
    can be used directly after being re-wrapped by _load_fin_predictor().
    """

    def __init__(
        self,
        ensemble: dict,
        decision_engine: "FinanceDecisionEngine",
        shap_importance: Optional[dict] = None,
    ):
        self.ensemble        = ensemble
        self.decision_engine = decision_engine
        self.shap_importance = shap_importance or {}

    def predict(self, X_base: np.ndarray) -> dict:
        """Single prediction. X_base shape: (1, 11) base features."""
        X_clean = _fin_safe_preprocess(X_base)
        X_eng   = _fin_add_features(X_clean)
        prob    = float(_fin_ensemble_predict_proba(self.ensemble, X_eng)[0])
        result  = self.decision_engine.decide(prob)
        return self.decision_engine.explain(result, self.shap_importance)

    def predict_batch(self, X_base: np.ndarray) -> list:
        """Batch prediction. X_base shape: (N, 11)."""
        X_clean = _fin_safe_preprocess(X_base)
        X_eng   = _fin_add_features(X_clean)
        probs   = _fin_ensemble_predict_proba(self.ensemble, X_eng)
        results = []
        for p in probs:
            r = self.decision_engine.decide(float(p))
            results.append(self.decision_engine.explain(r, self.shap_importance))
        return results


class _V8FinanceRiskPredictor(FinanceRiskPredictor):
    """
    Adapter for v8 model pickle.
    Uses _api_input_to_v8_features() to build the correct 41-feature vector
    from the 11-element API input, then calls the v8 ensemble directly.
    """
    def __init__(self, v8_predictor, decision_engine, shap_importance=None):
        super().__init__(
            ensemble        = v8_predictor.ensemble,
            decision_engine = decision_engine,
            shap_importance = shap_importance or {},
        )
        self._v8 = v8_predictor

    def predict(self, X_base: np.ndarray) -> dict:
        """X_base: (1, 11) normalized API inputs → 41 v8 features → prediction."""
        from training.finance_train import safe_preprocess as _v8_safe_preprocess
        X41   = _api_input_to_v8_features(X_base)
        X41   = _v8_safe_preprocess(X41)
        prob  = float(_fin_ensemble_predict_proba(self._v8.ensemble, X41)[0])
        result = self.decision_engine.decide(prob)
        return self.decision_engine.explain(result, self.shap_importance)

    def predict_batch(self, X_base: np.ndarray) -> list:
        """X_base: (N, 11) → batch predictions."""
        from training.finance_train import safe_preprocess as _v8_safe_preprocess
        results = []
        for row in X_base:
            X41  = _api_input_to_v8_features(row.reshape(1, -1))
            X41  = _v8_safe_preprocess(X41)
            prob = float(_fin_ensemble_predict_proba(self._v8.ensemble, X41)[0])
            r    = self.decision_engine.decide(prob)
            results.append(self.decision_engine.explain(r, self.shap_importance))
        return results

    # ── v8 Feature Mapping ────────────────────────────────────────────────────────

def _credit_bucket_v8(credit_norm: float) -> float:
    """Mirrors the _credit_bucket() function in finance_train.py."""
    if credit_norm >= 0.85: return 1.00
    if credit_norm >= 0.70: return 0.75
    if credit_norm >= 0.55: return 0.50
    if credit_norm >= 0.40: return 0.25
    return 0.0


def _api_input_to_v8_features(X_base: np.ndarray) -> np.ndarray:
    """
    Map the 11-element API input vector → 41-element v8 feature vector.

    API inputs (11):
        [0] overdue_days_normalized   [1] amount_normalized
        [2] paid_ratio                [3] late_ratio
        [4] on_time_ratio             [5] customer_age_normalized
        [6] invoice_frequency         [7] avg_delay_normalized
        [8] credit_score_normalized   [9] industry_risk_factor
        [10] seasonal_factor

    v8 layout (41):  BASE(8) + CREDIT(5) + INCOME(3) + BEHAVIORAL(19) + ENGINEERED(6)
    """
    r = X_base[0].astype(np.float64)

    # Unpack API inputs
    _overdue   = float(r[0])   # not a v8 feature — used only for derived proxies
    amount     = float(r[1])
    paid_r     = float(np.clip(r[2], 0, 1))
    late_r     = float(np.clip(r[3], 0, 1))
    age_norm   = float(r[5])
    inv_freq   = float(r[6])
    avg_delay  = float(r[7])
    credit     = float(np.clip(r[8], 0, 1))
    ind_risk   = float(r[9])
    seasonal   = float(r[10])

    # ── BASE (8) ──────────────────────────────────────────────────────────────
    years_norm      = float(np.clip(age_norm * 0.6, 0, 1))          # proxy from age
    biz_risk        = 0.35                                            # B2B default
    days_to_due_n   = 0.333                                          # 30/90 default

    # ── CREDIT (5) ────────────────────────────────────────────────────────────
    credit_bucket   = _credit_bucket_v8(credit)
    credit_util     = float(np.clip(late_r * 0.7 + _overdue * 0.15, 0, 1))
    debt_ratio      = float(np.clip(late_r * 0.5, 0, 1))
    credit_x_ind    = float(np.clip((1.0 - credit) * ind_risk, 0, 1))

    # ── INCOME (3) ────────────────────────────────────────────────────────────
    income_norm     = 0.10                                            # conservative default
    inv_to_income   = float(np.clip(amount * 1.5, 0, 1))
    bal_to_income   = float(np.clip(late_r * 0.4, 0, 1))

    # ── BEHAVIORAL (19) ───────────────────────────────────────────────────────
    hist_paid       = paid_r
    hist_late       = late_r
    hist_paid3      = float(np.clip(paid_r - _overdue * 0.1, 0, 1))  # slight recency decay
    hist_paid6      = paid_r
    hist_late3      = float(np.clip(late_r + _overdue * 0.05, 0, 1))
    # paid_trend / late_trend are clipped [-1,1] then mapped to [0,1]
    paid_trend_n    = float(np.clip(0.5 + (paid_r - hist_paid3) * 0.5, 0, 1))
    late_trend_n    = float(np.clip(0.5 + (hist_late3 - late_r) * 0.5, 0, 1))
    last_paid       = paid_r
    last_late       = late_r
    hist_max_delay  = float(np.clip(avg_delay * 1.4 + _overdue * 0.1, 0, 1))
    delay_var       = float(np.clip(late_r * 0.3, 0, 1))
    pay_volatility  = float(np.clip(late_r * (1.0 - paid_r), 0, 1))
    late_streak     = float(np.clip(late_r * 0.4 + _overdue * 0.2, 0, 1))
    good_streak     = float(np.clip(paid_r * 0.5, 0, 1))
    freq_trend      = 0.50
    velocity        = 0.50
    days_lp_norm    = float(np.clip(0.30 + _overdue * 0.1, 0, 1))
    hist_cnt_norm   = float(np.clip(age_norm * 0.35, 0, 1))

    # ── ENGINEERED (6) ────────────────────────────────────────────────────────
    credit_x_late   = float(np.clip((1.0 - credit) * late_r, 0, 1))
    amount_x_risk   = float(np.clip(amount * ind_risk, 0, 1))
    clv_proxy       = float(np.clip(amount * years_norm * inv_freq, 0, 1))
    recovery        = float(np.clip(1.0 - (paid_r - hist_paid3), 0, 1))
    behav_score     = float(np.clip(
        0.30 * late_r + 0.20 * late_streak + 0.15 * delay_var +
        0.15 * (1.0 - paid_r) + 0.10 * hist_max_delay + 0.10 * late_trend_n, 0, 1
    ))
    risk_composite  = float(np.clip(
        0.25 * late_r + 0.15 * (1.0 - credit) + 0.15 * ind_risk +
        0.15 * avg_delay + 0.12 * credit_util + 0.10 * debt_ratio +
        0.08 * seasonal, 0, 1
    ))

    X41 = np.array([[
        # BASE (8)
        amount, age_norm, years_norm, inv_freq,
        ind_risk, seasonal, biz_risk, days_to_due_n,
        # CREDIT (5)
        credit, credit_bucket, credit_util, debt_ratio, credit_x_ind,
        # INCOME (3)
        income_norm, inv_to_income, bal_to_income,
        # BEHAVIORAL (19)
        hist_paid, hist_late, hist_paid3, hist_paid6, hist_late3,
        paid_trend_n, late_trend_n,
        last_paid, last_late,
        hist_max_delay, avg_delay,
        delay_var, pay_volatility,
        late_streak, good_streak,
        freq_trend, velocity,
        days_lp_norm, hist_cnt_norm,
        # ENGINEERED (6)
        risk_composite, amount_x_risk, clv_proxy, recovery, behav_score, credit_x_late,
    ]], dtype=np.float64)

    assert X41.shape == (1, 41), f"v8 feature build error: got {X41.shape}"
    return X41


# ── Finance model singleton ───────────────────────────────────────────────────
_fin_predictor: Optional[FinanceRiskPredictor] = None


def _load_fin_predictor() -> Optional[FinanceRiskPredictor]:
    """Load (or reload) the finance risk model from disk.

    Handles multiple pickle formats:
      - v8.x: contains FinanceRiskPredictorV8 (from training module)
      - v3:   contains raw ensemble + metadata dict
    Both are wrapped in the local FinanceRiskPredictor interface.
    """
    global _fin_predictor

    # ── Check file exists ──────────────────────────────────────────────────
    if not os.path.exists(_FIN_MODEL_PATH):
        logger.warning(
            "⚠️ Finance model file not found: %s\n"
            "   Run: python training/finance_train.py",
            _FIN_MODEL_PATH,
        )
        return None

    logger.info("📂 Loading finance model from: %s", _FIN_MODEL_PATH)

    try:
        # ── Custom unpickler to resolve training module classes ─────────────
        #    The pickle was created in finance_train.py (__main__ context),
        #    so its classes are stored as "__main__.FinanceRiskPredictorV8" etc.
        #    We redirect those lookups to the actual training module.
        import importlib
        _train_mod = None
        try:
            _train_mod = importlib.import_module("training.finance_train")
        except Exception as imp_err:
            logger.debug("   Could not import training.finance_train: %s", imp_err)

        class _TrainingUnpickler(pickle.Unpickler):
            """Redirect class lookups for __main__ and training.finance_train*."""
            def find_class(self, module, name):
                # Classes saved from training script's __main__
                if module in ("__main__", "training.finance_train",
                              "training.finance_train_v3",
                              "training.finance_train_v8"):
                    if _train_mod and hasattr(_train_mod, name):
                        return getattr(_train_mod, name)
                return super().find_class(module, name)

        with open(_FIN_MODEL_PATH, "rb") as f:
            saved = _TrainingUnpickler(f).load()

        meta     = saved.get("metadata", {})
        ensemble = saved.get("ensemble")
        pred_obj = saved.get("predictor")
        version  = meta.get("version", "unknown")

        logger.info("   📋 Model version: %s | trained: %s",
                     version, meta.get("trained_at", "?"))

        # ── Strategy 1: Use v8 predictor directly via adapter ─────────────
        #    The v8 predictor has its own ensemble + decision engine inside.
        #    We wrap it so the /finance/predict-risk endpoint (which passes
        #    an 11-feature numpy array) still works.
        # ── Strategy 1: Use v8 predictor directly via adapter ─────────────
        if pred_obj is not None and hasattr(pred_obj, "ensemble"):
            logger.info("   🔗 Found v8 predictor object — wrapping with _V8FinanceRiskPredictor")

            v8_de  = getattr(pred_obj, "decision_engine", None)
            reject = getattr(v8_de, "reject_threshold", 0.50) if v8_de else 0.50
            review = getattr(v8_de, "review_low",        0.22) if v8_de else 0.22

            engine = FinanceDecisionEngine(
                reject_threshold = reject,
                review_threshold = review,
            )
            shap_imp = getattr(pred_obj, "shap_importance", None) or \
                       meta.get("shap_importance", {})

            _fin_predictor = _V8FinanceRiskPredictor(    # ← الصح
                v8_predictor    = pred_obj,
                decision_engine = engine,
                shap_importance = shap_imp,
            )
            logger.info(
                "✅ Finance risk model v%s loaded | reject≥%.2f review≥%.2f",
                version, reject, review,
            )
            return _fin_predictor
        logger.warning("⚠️ Finance model pickle has no 'predictor' or 'ensemble' key")
        return None

    except Exception as e:
        logger.error(
            "❌ Finance model load failed: %s | path=%s",
            e, _FIN_MODEL_PATH, exc_info=True,
        )
        return None


def _get_fin_predictor() -> Optional[FinanceRiskPredictor]:
    global _fin_predictor
    if _fin_predictor is None:
        _load_fin_predictor()
    return _fin_predictor


def _make_fin_request_id() -> str:
    import uuid
    return f"fin-{uuid.uuid4().hex[:12]}"

# ─────────────────────────────────────────────────────────────────────────────
# Schemas — Core
# ─────────────────────────────────────────────────────────────────────────────

class LeaveRequest(BaseModel):
    employee_id:    str  = Field(...)
    requested_days: int  = Field(..., gt=0)
    reason:         str  = Field("", max_length=500)
    leave_type:     str  = Field("annual")
    leave_balance:  int  = Field(0, ge=0)
    employee_name:     Optional[str]   = None
    performance_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    attendance_rate:   Optional[float] = Field(None, ge=0.0, le=1.0)
    team_workload:     str             = Field("medium")
    start_date:        Optional[date]  = None

    @validator("leave_type")
    def validate_leave_type(cls, v):
        allowed = {"annual", "sick", "emergency", "unpaid"}
        if v not in allowed:
            raise ValueError(f"leave_type must be one of: {allowed}")
        return v

    @validator("employee_id", pre=True)
    def coerce_employee_id(cls, v):
        return str(v)


class LeaveApprovalRequest(BaseModel):
    employee_id:         str             = Field(...)
    employee_name:       str             = Field("Unknown Employee")
    requested_days:      int             = Field(..., gt=0)
    leave_balance:       int             = Field(0, ge=0)
    leave_type:          str             = Field("annual")
    reason:              str             = Field("", max_length=500)
    leave_id:            Optional[int]   = None
    performance_score:   Optional[float] = Field(None, ge=0.0, le=1.0)
    attendance_rate:     Optional[float] = Field(None, ge=0.0, le=1.0)
    absence_count:       Optional[int]   = Field(None, ge=0)
    team_workload:       str             = Field("medium")
    job_level:           Optional[str]   = None
    years_of_experience: Optional[int]   = Field(None, ge=0)
    salary_grade:        Optional[str]   = None
    overtime_hours:      Optional[int]   = Field(None, ge=0)
    department:          Optional[str]   = None

    @validator("employee_id", pre=True)
    def coerce_id(cls, v):
        return str(v)

    @validator("leave_type")
    def validate_leave_type(cls, v):
        allowed = {"annual", "sick", "emergency", "unpaid"}
        if v not in allowed:
            raise ValueError(f"leave_type must be one of: {allowed}")
        return v


class LeaveStatusUpdate(BaseModel):
    status: str = Field(..., description="approved | rejected")
    notes:  str = Field("", max_length=500)

    @validator("status")
    def validate_status(cls, v):
        if v not in {"approved", "rejected"}:
            raise ValueError("status must be 'approved' or 'rejected'")
        return v


class TicketCreate(BaseModel):
    customer_id: Optional[int] = None
    subject:     str  = Field(..., min_length=5, max_length=200)
    description: str  = Field(..., min_length=10)
    priority:    str  = Field("medium")

    @validator("priority")
    def validate_priority(cls, v):
        if v not in {"low", "medium", "high", "urgent"}:
            raise ValueError("priority must be: low | medium | high | urgent")
        return v


class LeadCreate(BaseModel):
    name:   str           = Field(..., min_length=2, max_length=100)
    email:  EmailStr
    phone:  Optional[str] = Field(None, max_length=20)
    source: str           = Field("manual")
    notes:  str           = Field("", max_length=500)


class DecisionCreate(BaseModel):
    agent_type:   str
    entity:       str
    entity_id:    int
    decision:     str
    confidence:   float = Field(..., ge=0.0, le=1.0)
    reasoning:    str
    raw_response: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Schemas — HR Domain
# ─────────────────────────────────────────────────────────────────────────────

class SalaryReviewRequest(BaseModel):
    employee_id:                 str             = Field(...)
    employee_name:               Optional[str]   = None
    current_salary_egp:          float           = Field(..., ge=0)
    requested_increment_pct:     float           = Field(0.10, ge=0.0, le=1.0)
    market_median_egp:           float           = Field(0, ge=0)
    market_gap_pct:              float           = Field(0)
    months_since_last_increment: int             = Field(12, ge=0)
    months_in_role:              int             = Field(0, ge=0)
    appraisal_cycle:             str             = Field("Annual")
    kpi_achievement:             float           = Field(0.80, ge=0.0, le=1.0)
    budget_utilization:          float           = Field(0.80, ge=0.0, le=1.0)
    available_pool_egp:          float           = Field(0, ge=0)
    is_on_pip:                   bool            = Field(False)
    is_on_probation:             bool            = Field(False)
    performance_score:           Optional[float] = Field(None, ge=0.0, le=1.0)
    department:                  Optional[str]   = None
    job_level:                   Optional[str]   = None
    salary_grade:                Optional[str]   = None

    @validator("employee_id", pre=True)
    def coerce_id(cls, v):
        return str(v)


class IncentiveRequest(BaseModel):
    employee_id:                    str             = Field(...)
    employee_name:                  Optional[str]   = None
    incentive_type:                 str             = Field("performance_bonus")
    requested_amount_egp:           float           = Field(..., ge=0)
    kpi_achievement:                float           = Field(0.80, ge=0.0, le=1.0)
    performance_score:              float           = Field(0.75, ge=0.0, le=1.0)
    monthly_salary_egp:             float           = Field(0, ge=0)
    tenure_months:                  int             = Field(0, ge=0)
    is_on_pip:                      bool            = Field(False)
    is_critical_talent:             bool            = Field(False)
    incentive_budget_remaining_egp: float           = Field(0, ge=0)
    perf_trend:                     str             = Field("stable")
    reason:                         str             = Field("", max_length=500)
    department:                     Optional[str]   = None
    job_level:                      Optional[str]   = None
    salary_grade:                   Optional[str]   = None

    @validator("employee_id", pre=True)
    def coerce_id(cls, v):
        return str(v)

    @validator("incentive_type")
    def validate_incentive_type(cls, v):
        allowed = {
            "performance_bonus", "overtime_compensation",
            "retention_bonus", "project_bonus", "annual_bonus",
        }
        if v not in allowed:
            raise ValueError(f"incentive_type must be one of: {allowed}")
        return v


class AbsenceEventRequest(BaseModel):
    employee_id:                    str             = Field(...)
    employee_name:                  Optional[str]   = None
    absence_date:                   date            = Field(...)
    absence_type_claimed:           str             = Field("unexcused")
    duration_hours:                 float           = Field(8, ge=0)
    medical_certificate_provided:   bool            = Field(False)
    prior_approval_obtained:        bool            = Field(False)
    reason:                         str             = Field("", max_length=500)
    total_absences_90d:             int             = Field(0, ge=0)
    unexcused_count_90d:            int             = Field(0, ge=0)
    late_arrivals_90d:              int             = Field(0, ge=0)
    previous_warnings:              str             = Field("none")
    performance_score:              float           = Field(0.75, ge=0.0, le=1.0)
    is_on_pip:                      bool            = Field(False)
    department:                     Optional[str]   = None
    job_level:                      Optional[str]   = None
    salary_grade:                   Optional[str]   = None
    tenure_months:                  int             = Field(0, ge=0)

    @validator("employee_id", pre=True)
    def coerce_id(cls, v):
        return str(v)

    @validator("absence_type_claimed")
    def validate_absence_type(cls, v):
        allowed = {"unexcused", "sick", "emergency", "annual", "unpaid", "غياب بدون إذن"}
        if v not in allowed:
            raise ValueError(f"absence_type_claimed must be one of: {allowed}")
        return v

    @validator("previous_warnings")
    def validate_warnings(cls, v):
        allowed = {"none", "verbal", "written", "formal"}
        if v not in allowed:
            raise ValueError(f"previous_warnings must be one of: {allowed}")
        return v


# ─────────────────────────────────────────────────────────────────────────────
# System
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/", tags=["System"])
async def root():
    return {
        "system":   settings.APP_NAME,
        "version":  "5.1.0",
        "status":   "🟢 operational",
        "llm":      settings.GEMINI_MODEL,
        "agents":   [
            "HR Leave Approval (ML + Gemini AI)",
            "Salary Review Agent",
            "Incentive Agent",
            "Absence Management Agent",
            "Support Agent",
            "CRM Agent",
        ],
        "modules":  [
            "HR", "Leaves", "Salary Reviews", "Incentives",
            "Absence Management", "Tickets", "Leads", "Events", "Memory", "Audit",
        ],
        "triggers": {
            "scheduler":  "active",
            "db_watcher": "active",
            "webhooks":   "active — /webhooks/*",
        },
        "docs":   "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["System"])
async def health():
    db_status  = health_check()
    scheduler  = get_scheduler_status()
    ml_handler = get_model_handler()
    ml_info    = ml_handler.get_info()
    overall    = "healthy" if db_status.get("database") == "healthy" else "degraded"
    return {
        "status":          overall,
        "version":         "5.1.0",
        "pipeline":        "active",
        "llm_provider":    settings.LLM_PROVIDER,
        "llm_model":       settings.GEMINI_MODEL,
        "api_key_set":     bool(settings.GOOGLE_API_KEY),
        "trigger_engine":  "running" if scheduler.get("running") else "stopped",
        "scheduled_jobs":  scheduler.get("jobs_count", 0),
        "ml_model": {
            "loaded":     ml_info.get("loaded", False),
            "accuracy":   ml_info.get("accuracy"),
            "roc_auc":    ml_info.get("roc_auc"),
            "trained_at": ml_info.get("trained_at"),
        },
        "timestamp":       datetime.utcnow().isoformat() + "Z",
        **db_status,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Trigger Engine
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/trigger/run-now/{job_name}", tags=["⚡ Trigger Engine"])
async def trigger_run_now(job_name: str):
    jobs = {
        "leaves":           job_scan_pending_leaves,
        "tickets":          job_scan_pending_tickets,
        "leads":            job_scan_new_leads,
        "events":           job_process_event_queue,
        "salary-reviews":   job_scan_pending_salary_reviews,
        "incentives":       job_scan_pending_incentives,
        "absences":         job_scan_pending_absences,
        # ✅ Finance — أضفهم هنا
        "overdue-invoices": job_scan_overdue_invoices,
        "new-invoices":     job_scan_new_invoices,
    }
    job_fn = jobs.get(job_name)
    if not job_fn:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown job '{job_name}'. Available: {list(jobs.keys())}",
        )
    event_bus._idempotency._seen.clear()
    logger.info("🔥 Manual trigger: job '%s' — idempotency cache cleared", job_name)
    await job_fn()
    return {
        "job":       job_name,
        "status":    "executed",
        "note":      "Idempotency cache cleared for this run",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@app.get("/trigger/events/history", tags=["⚡ Trigger Engine"])
async def trigger_events_history(event_type: Optional[str] = None, limit: int = 30):
    history = event_bus.get_history(event_type=event_type, limit=limit)
    return {"count": len(history), "events": history}


# ─────────────────────────────────────────────────────────────────────────────
# Employees
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/employees", tags=["HR - Employees"])
def list_employees(active_only: bool = True):
    employees = get_all_employees(active_only=active_only)
    return {"count": len(employees), "employees": employees}


@app.get("/employees/{employee_id}", tags=["HR - Employees"])
def get_employee_by_id(employee_id: int):
    emp = get_employee(employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail=f"Employee {employee_id} not found")
    return emp


@app.get("/employees/{employee_id}/leaves", tags=["HR - Leaves"])
def employee_leave_history(employee_id: int):
    emp = get_employee(employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    leaves = get_employee_leaves(employee_id)
    return {"employee_id": employee_id, "count": len(leaves), "leaves": leaves}


@app.get("/employees/{employee_id}/balance-history", tags=["HR - Employees"])
def get_employee_balance_history(employee_id: int, limit: int = 20):
    """📊 Fix 2: Leave Balance Audit Trail — تاريخ تغييرات balance لموظف."""
    emp = get_employee(employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    history = get_balance_history(employee_id, limit=limit)
    return {
        "employee_id":     employee_id,
        "employee_name":   emp.get("name", ""),
        "current_balance": emp.get("leave_balance", 0),
        "history_count":   len(history),
        "history":         history,
        "note": (
            "No history yet — balance_audit_log will populate after next leave decision"
            if not history else None
        ),
    }


@app.get("/employees/{employee_id}/salary-reviews", tags=["HR - Employees"])
def employee_salary_history(employee_id: int):
    """💰 Salary review history for an employee."""
    emp = get_employee(employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    reviews = get_employee_salary_reviews(employee_id)
    return {
        "employee_id":   employee_id,
        "employee_name": emp.get("name", ""),
        "count":         len(reviews),
        "reviews":       reviews,
    }


@app.get("/employees/{employee_id}/incentives", tags=["HR - Employees"])
def employee_incentive_history(employee_id: int):
    """🏆 Incentive history for an employee."""
    emp = get_employee(employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    incentives = get_employee_incentives(employee_id)
    total_approved = sum(
        float(i.get("approved_amount_egp", 0) or 0)
        for i in incentives if i.get("status") == "approved"
    )
    return {
        "employee_id":        employee_id,
        "employee_name":      emp.get("name", ""),
        "count":              len(incentives),
        "total_approved_egp": total_approved,
        "incentives":         incentives,
    }


@app.get("/employees/{employee_id}/absences", tags=["HR - Employees"])
def employee_absence_history(employee_id: int, limit: int = 50):
    """🚫 Absence history for an employee."""
    emp = get_employee(employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    absences = get_employee_absences(employee_id, limit=limit)
    unexcused_total = sum(
        1 for a in absences
        if a.get("absence_type_claimed") == "unexcused"
        and a.get("status") not in ("pending", "cancelled")
    )
    return {
        "employee_id":     employee_id,
        "employee_name":   emp.get("name", ""),
        "count":           len(absences),
        "unexcused_total": unexcused_total,
        "absences":        absences,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Leaves — Helpers
# ─────────────────────────────────────────────────────────────────────────────

async def poll_leave_decision(leave_id: int, timeout: int = 30) -> dict:
    """Polls DB until leave status changes from pending/in_progress."""
    start    = asyncio.get_event_loop().time()
    interval = 0.5

    while True:
        leave_status = get_leave_status(leave_id)
        if leave_status in ("approved", "rejected", "escalated"):
            leave = get_leave(leave_id)
            return {
                "leave_id": leave_id,
                "decision": leave_status,
                "status":   leave_status,
                "leave":    leave,
                "message":  f"✅ Decision ready: {leave_status}",
            }

        elapsed = asyncio.get_event_loop().time() - start
        if elapsed > timeout:
            leave = get_leave(leave_id)
            return {
                "leave_id": leave_id,
                "decision": "processing",
                "status":   "processing",
                "leave":    leave,
                "message":  "⏳ Still processing — check /leaves/{leave_id}/decision later",
                "elapsed":  round(elapsed, 1),
            }

        await asyncio.sleep(interval)
        interval = min(interval + 0.5, 1.0)


async def _poll_until_terminal(
    fetch_fn,
    entity_id: int,
    terminal_statuses: set,
    timeout: int = 30,
) -> dict:
    """Generic poll helper for salary/incentive/absence — reusable across domains."""
    start    = asyncio.get_event_loop().time()
    interval = 0.5

    while True:
        record = fetch_fn(entity_id)
        if record and record.get("status") in terminal_statuses:
            return record

        if asyncio.get_event_loop().time() - start > timeout:
            return record or {}

        await asyncio.sleep(interval)
        interval = min(interval + 0.5, 1.0)


# ─────────────────────────────────────────────────────────────────────────────
# Leaves — Submit (Sync)
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/leaves/submit", status_code=status.HTTP_201_CREATED, tags=["HR - Leaves"])
async def submit_leave_sync(body: LeaveApprovalRequest, background_tasks: BackgroundTasks):
    """🧠 Submit leave request — AI decision returned immediately (Event-Driven)."""
    if body.employee_id.isdigit():
        emp = get_employee(int(body.employee_id))
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")

    leave_data = body.dict()
    leave_data["leave_days"] = leave_data.pop("requested_days")
    leave_id = create_leave_request(leave_data)

    event_id = create_event(
        event_type="leave_requested",
        entity="leaves",
        entity_id=leave_id,
        payload={
            "leave_id":      leave_id,
            "employee_id":   body.employee_id,
            "employee_name": body.employee_name or "",
            "leave_days":    body.requested_days,
            "leave_type":    body.leave_type,
            "leave_balance": body.leave_balance,
            "reason":        body.reason,
            "source":        "sync_api",
        },
    )

    logger.info(
        "📋 [submit] Leave #%s created | event #%s | employee=%s | days=%s | type=%s",
        leave_id, event_id, body.employee_id, body.requested_days, body.leave_type,
    )

    try:
        await job_process_event_queue()
    except Exception as e:
        logger.warning("⚠️ [submit] Event queue trigger failed: %s — scheduler will pick it up", e)

    result = await poll_leave_decision(leave_id, timeout=30)
    decision = result.get("decision", "unknown")

    background_tasks.add_task(
        write_audit_log,
        action       = f"leave_submit_{decision}",
        entity       = "leaves",
        entity_id    = leave_id,
        performed_by = "event_driven_pipeline_v5.1",
        details      = f"event_driven_submit | decision={decision} | event_id={event_id}",
    )

    result["leave_id"]  = leave_id
    result["event_id"]  = event_id
    result["submitted"] = True

    logger.info("✅ [submit] Leave #%s → %s | event=#%s", leave_id, decision, event_id)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Leaves — Async (background)
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/leaves", status_code=status.HTTP_201_CREATED, tags=["HR - Leaves"])
async def submit_leave_async(body: LeaveRequest, background_tasks: BackgroundTasks):
    if body.employee_id.isdigit():
        emp = get_employee(int(body.employee_id))
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")

    leave_data = body.dict()
    leave_data["leave_days"] = leave_data.pop("requested_days")
    leave_id = create_leave_request(leave_data)

    event_id = create_event(
        event_type="leave_requested",
        entity="leaves",
        entity_id=leave_id,
        payload={
            "leave_id":    leave_id,
            "employee_id": body.employee_id,
            "leave_days":  body.requested_days,
        },
    )

    # ✅ بس الـ audit log — مفيش event_bus.publish
    background_tasks.add_task(
        write_audit_log,
        action       = "leave_request_submitted_async",
        entity       = "leaves",
        entity_id    = leave_id,
        performed_by = f"employee_{body.employee_id}",
        details      = f"{body.requested_days} days — {body.leave_type} | event_id={event_id}",
    )

    logger.info(
        "📋 [async] Leave #%s created | event #%s | employee=%s — queued",
        leave_id, event_id, body.employee_id,
    )

    return {
        "message":      "Leave request queued — AI agent will process in background",
        "leave_id":     leave_id,
        "event_id":     event_id,
        "db_status":    "pending",
        "pipeline":     "EventBus → Trigger Engine → Orchestrator → HR Agent",
        "note":         "💡 Use POST /leaves/submit to get the AI decision immediately",
        "decision_url": f"/leaves/{leave_id}/decision",
    }


@app.post("/leaves/process", status_code=status.HTTP_201_CREATED, tags=["HR - Leaves"])
async def process_leave_with_workflow(body: LeaveApprovalRequest, background_tasks: BackgroundTasks):
    """Alias for /leaves/submit — kept for backward compatibility."""
    return await submit_leave_sync(body, background_tasks)


@app.get("/leaves/pending", tags=["HR - Leaves"])
def list_pending_leaves():
    leaves = get_pending_leaves()
    return {"count": len(leaves), "leaves": leaves}


@app.get("/leaves/{leave_id}", tags=["HR - Leaves"])
def get_leave_by_id(leave_id: int):
    leave = get_leave(leave_id)
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
    return leave


@app.get("/leaves/{leave_id}/decision", tags=["HR - Leaves"])
async def get_leave_decision(leave_id: int):
    """Get AI decision — triggers on-demand if still pending."""
    leave = get_leave(leave_id)
    if not leave:
        raise HTTPException(status_code=404, detail=f"Leave #{leave_id} not found")

    current_status = leave.get("status")
    if current_status in ("approved", "rejected", "escalated"):
        return {"leave_id": leave_id, "status": current_status, "leave": leave}

    if current_status == "pending":
        logger.info("🔄 Leave #%s is pending — triggering event queue on-demand", leave_id)
        try:
            event_id = create_event(
                event_type="leave_requested",
                entity="leaves",
                entity_id=leave_id,
                payload={
                    "leave_id":      leave_id,
                    "employee_id":   str(leave.get("employee_id", "")),
                    "employee_name": leave.get("employee_name", ""),
                    "leave_days":    leave.get("leave_days", 1),
                    "leave_type":    leave.get("leave_type", "annual"),
                    "leave_balance": int(leave.get("leave_balance") or 0),
                    "reason":        leave.get("reason", ""),
                    "source":        "on_demand_decision",
                },
            )
            try:
                await job_process_event_queue()
            except Exception as eq_err:
                logger.warning("⚠️ Event queue trigger failed: %s", eq_err)

            result = await poll_leave_decision(leave_id, timeout=30)
            return {
                "leave_id":          leave_id,
                "event_id":          event_id,
                "previous_status":   "pending",
                "workflow_decision": result,
                "note":              "Event-driven processing triggered on-demand",
            }
        except Exception as e:
            logger.error("❌ On-demand event processing failed for leave #%s: %s", leave_id, e)

    return {"leave_id": leave_id, "status": current_status, "leave": leave}


@app.get("/leaves/{leave_id}/audit", tags=["HR - Leaves"])
async def get_leave_decision_audit(leave_id: int):
    """📋 Fix 4: Complete Decision Audit Trail."""
    leave = get_leave(leave_id)
    if not leave:
        raise HTTPException(status_code=404, detail="Leave not found")

    from core.db import get_db

    audit_record  = None
    decisions_log = []
    balance_history = []

    try:
        with get_db() as (_, cur):
            cur.execute(
                "SELECT * FROM decision_audit WHERE leave_id = %s ORDER BY created_at DESC LIMIT 1",
                (leave_id,),
            )
            audit_record = cur.fetchone()
    except Exception:
        pass

    try:
        with get_db() as (_, cur):
            cur.execute(
                "SELECT * FROM decisions WHERE entity = 'leaves' AND entity_id = %s "
                "ORDER BY created_at DESC",
                (leave_id,),
            )
            decisions_log = cur.fetchall()
    except Exception:
        pass

    try:
        with get_db() as (_, cur):
            cur.execute(
                "SELECT * FROM balance_audit_log WHERE leave_id = %s ORDER BY created_at DESC",
                (leave_id,),
            )
            balance_history = cur.fetchall()
    except Exception:
        pass

    return {
        "leave_id":        leave_id,
        "current_status":  leave.get("status"),
        "employee_name":   leave.get("employee_name"),
        "leave_days":      leave.get("leave_days"),
        "decision_audit":  dict(audit_record) if audit_record else None,
        "balance_history": balance_history,
        "decisions_log":   decisions_log,
        "note": (
            "decision_audit table empty — apply Fix 4 workflow to enable full audit trail"
            if not audit_record else None
        ),
    }


@app.patch("/leaves/{leave_id}/status", tags=["HR - Leaves"])
def update_leave(leave_id: int, body: LeaveStatusUpdate, background_tasks: BackgroundTasks):
    leave = get_leave(leave_id)
    if not leave:
        raise HTTPException(status_code=404, detail="Leave not found")
    if not update_leave_status(leave_id, body.status, body.notes):
        raise HTTPException(status_code=500, detail="Failed to update leave status")
    background_tasks.add_task(
        write_audit_log,
        action       = f"leave_{body.status}",
        entity       = "leaves",
        entity_id    = leave_id,
        performed_by = "hr_agent",
        details      = body.notes,
    )
    return {"leave_id": leave_id, "new_status": body.status, "updated": True}


# ─────────────────────────────────────────────────────────────────────────────
# Salary Reviews
# ─────────────────────────────────────────────────────────────────────────────

_SALARY_TERMINAL  = {"approved", "escalated", "deferred", "rejected"}
_INCENTIVE_TERMINAL = {"approved", "rejected", "partial", "escalated", "escalated_ceo"}
_ABSENCE_TERMINAL = {
    "recorded", "warned_written", "warned_formal",
    "deducted", "deducted_double", "escalated",
    "suspension_review", "termination_review",
}


@app.post("/salary-reviews/submit", status_code=status.HTTP_201_CREATED, tags=["HR - Salary Reviews"])
async def submit_salary_review(body: SalaryReviewRequest, background_tasks: BackgroundTasks):
    """💰 Submit Salary Review — AI decision returned immediately."""
    if body.employee_id.isdigit():
        emp = get_employee(int(body.employee_id))
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")

    review_id = create_salary_review(body.dict())
    event_id  = create_event(
        event_type="salary_review",
        entity="salary_reviews",
        entity_id=review_id,
        payload={
            "review_id":                   review_id,
            "employee_id":                 body.employee_id,
            "employee_name":               body.employee_name or "",
            "current_salary_egp":          body.current_salary_egp,
            "requested_increment_pct":     body.requested_increment_pct,
            "market_median_egp":           body.market_median_egp,
            "market_gap_pct":              body.market_gap_pct,
            "months_since_last_increment": body.months_since_last_increment,
            "months_in_role":              body.months_in_role,
            "kpi_achievement":             body.kpi_achievement,
            "budget_utilization":          body.budget_utilization,
            "available_pool_egp":          body.available_pool_egp,
            "is_on_pip":                   body.is_on_pip,
            "is_on_probation":             body.is_on_probation,
            "appraisal_cycle":             body.appraisal_cycle,
            "performance_score":           body.performance_score,
            "department":                  body.department or "",
            "job_level":                   body.job_level or "junior",
            "salary_grade":                body.salary_grade or "C",
            "source":                      "sync_api",
        },
    )

    logger.info(
        "💰 [salary-submit] Review #%s | event #%s | employee=%s | increment=%.0f%%",
        review_id, event_id, body.employee_id, body.requested_increment_pct * 100,
    )

    try:
        await job_process_event_queue()
    except Exception as e:
        logger.warning("⚠️ [salary-submit] Event queue trigger failed: %s", e)

    review = await _poll_until_terminal(
        get_salary_review, review_id, _SALARY_TERMINAL, timeout=30
    )

    decision = review.get("ai_decision", review.get("status", "processing")) if review else "processing"
    background_tasks.add_task(
        write_audit_log,
        action       = f"salary_review_submit_{decision}",
        entity       = "salary_reviews",
        entity_id    = review_id,
        performed_by = "event_driven_pipeline_v5.1",
        details      = f"event_id={event_id} | decision={decision}",
    )

    is_done = review and review.get("status") in _SALARY_TERMINAL
    return {
        "review_id":   review_id,
        "event_id":    event_id,
        "submitted":   True,
        "decision":    decision,
        "status":      review.get("status") if review else "processing",
        "confidence":  review.get("confidence_score") if review else None,
        "reason":      review.get("decision_reason") if review else None,
        "review":      review,
        # ✅ NEW: direct link to explainability
        "explain_url": f"/salary-reviews/{review_id}/explain",
        "weighted_score": review.get("weighted_score") if review else None,
        "trigger":     review.get("trigger") if review else None,
        "trigger_phase": review.get("trigger_phase") if review else None,
        "message": (
            f"✅ Salary review decision ready: {decision}"
            if is_done
            else "⏳ Still processing — check /salary-reviews/{review_id}/decision later"
        ),
    }


@app.get("/salary-reviews/pending", tags=["HR - Salary Reviews"])
def list_pending_salary_reviews():
    reviews = get_pending_salary_reviews()
    return {"count": len(reviews), "reviews": reviews}


@app.get("/salary-reviews/{review_id}", tags=["HR - Salary Reviews"])
def get_salary_review_by_id(review_id: int):
    review = get_salary_review(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Salary review not found")
    return review


@app.get("/salary-reviews/{review_id}/decision", tags=["HR - Salary Reviews"])
async def get_salary_review_decision(review_id: int):
    """🔄 Get decision — triggers on-demand if still pending."""
    review = get_salary_review(review_id)
    if not review:
        raise HTTPException(status_code=404, detail=f"Salary review #{review_id} not found")

    if review.get("status") in _SALARY_TERMINAL:
        return {
            "review_id": review_id,
            "decision":  review.get("ai_decision"),
            "status":    review.get("status"),
            "review":    review,
        }

    if review.get("status") == "pending":
        try:
            create_event(
                event_type="salary_review",
                entity="salary_reviews",
                entity_id=review_id,
                payload={
                    "review_id":                  review_id,
                    "employee_id":                str(review.get("employee_id", "")),
                    "employee_name":              review.get("employee_name", ""),
                    "current_salary_egp":         float(review.get("current_salary_egp", 0)),
                    "requested_increment_pct":    float(review.get("requested_increment_pct", 0.10)),
                    "kpi_achievement":            float(review.get("kpi_achievement", 0.80)),
                    "budget_utilization":         float(review.get("budget_utilization", 0.80)),
                    "is_on_pip":                  bool(review.get("is_on_pip", False)),
                    "is_on_probation":            bool(review.get("is_on_probation", False)),
                    "performance_score":          float(review.get("performance_score") or 0.75),
                    "source":                     "on_demand",
                },
            )
            await job_process_event_queue()
        except Exception as e:
            logger.error("❌ On-demand salary trigger failed for #%s: %s", review_id, e)

    review = get_salary_review(review_id)
    return {"review_id": review_id, "status": review.get("status"), "review": review}


@app.get("/salary-reviews/{review_id}/audit", tags=["HR - Salary Reviews"])
async def get_salary_review_audit(review_id: int):
    """📋 Full audit trail for a salary review."""
    review = get_salary_review(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Salary review not found")
    audit = get_hr_domain_audit("salary", review_id)
    return {
        "review_id":      review_id,
        "current_status": review.get("status"),
        "employee_name":  review.get("employee_name"),
        "ai_decision":    review.get("ai_decision"),
        "confidence":     review.get("confidence_score"),
        "audit_trail":    audit,
    }


@app.get("/salary-reviews/{review_id}/explain", tags=["HR - Salary Reviews"])
async def explain_salary_decision(review_id: int):
    """
    🧠 Explainability API — Full decision breakdown for a salary review.
    
    Returns:
        - Which priority rule fired (P0–P5)
        - Weighted score with per-factor contributions
        - Threshold ladder (showing exactly where the score landed)
        - All factors evaluated with impact classification
        - Human-readable reason
        
    Perfect for:
        - HR managers who want to understand a decision
        - Audit and compliance reporting
        - Employee-facing explanations
    """
    from agents.hr.salary_decision_engine import (
        get_salary_decision_engine,
        SalaryDecisionInput,
        SalaryExplainabilityBuilder,
    )

    review = get_salary_review(review_id)
    if not review:
        raise HTTPException(status_code=404, detail=f"Salary review #{review_id} not found")

    # Re-run decision engine on stored data (deterministic — same input = same output)
    engine = get_salary_decision_engine()
    inp    = SalaryDecisionInput.from_dict(review)
    result = engine.decide(review, request_id=f"explain_{review_id}")

    explanation = SalaryExplainabilityBuilder.build(result, inp)

    return {
        "review_id":      review_id,
        "employee_name":  review.get("employee_name"),
        "stored_decision": review.get("ai_decision"),
        "engine_decision": result.decision,
        "decisions_match": review.get("ai_decision") == result.decision,
        "explanation":     explanation,
        "raw_score":       result.weighted_score,
        "score_breakdown": result.score_breakdown.to_dict() if result.score_breakdown else {},
    }


@app.get("/salary-reviews/decision-engine/thresholds", tags=["HR - Salary Reviews"])
async def get_decision_engine_thresholds():
    """
    📊 Get the current decision engine thresholds and weights.
    Useful for HR policy documentation and system transparency.
    """
    from agents.hr.salary_decision_engine import (
        SCORE_APPROVE, SCORE_ESCALATE, SCORE_DEFER,
        WEIGHT_PERFORMANCE, WEIGHT_KPI, WEIGHT_MARKET, WEIGHT_TENURE,
        PERF_REJECT_FLOOR, PERF_DEFER_FLOOR,
        LEVEL_INCREMENT_CAPS,
    )

    return {
        "version": "v6.0",
        "description": "Priority-based multi-factor salary decision engine",
        "priority_rules": {
            "P0": {"trigger": "is_on_pip = true",           "decision": "reject",               "confidence": "0.97"},
            "P1": {"trigger": f"performance_score < {PERF_REJECT_FLOOR:.0%}", "decision": "reject",  "confidence": "0.93"},
            "P2": {"trigger": "is_on_probation = true",     "decision": "defer",                "confidence": "0.92"},
            "P3": {"trigger": "budget_utilization > 95%",   "decision": "defer",                "confidence": "0.90"},
            "P4": {"trigger": "requested_increment > 30%",  "decision": "escalate_to_director", "confidence": "0.95"},
            "P5": {"trigger": "weighted score engine",       "decision": "score-based",          "confidence": "variable"},
        },
        "score_weights": {
            "performance_score":           f"{WEIGHT_PERFORMANCE:.0%}",
            "kpi_achievement":             f"{WEIGHT_KPI:.0%}",
            "market_gap_pct":              f"{WEIGHT_MARKET:.0%}",
            "months_since_last_increment": f"{WEIGHT_TENURE:.0%}",
        },
        "score_thresholds": {
            f">= {SCORE_APPROVE:.2f}": "approve_increment",
            f">= {SCORE_ESCALATE:.2f}": "escalate_to_director",
            f">= {SCORE_DEFER:.2f}": "defer",
            f"< {SCORE_DEFER:.2f}": "reject",
        },
        "performance_floors": {
            "reject_floor": f"< {PERF_REJECT_FLOOR:.0%} → always reject",
            "defer_floor":  f"< {PERF_DEFER_FLOOR:.0%} → never approve, best is defer",
        },
        "level_increment_caps": LEVEL_INCREMENT_CAPS,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Incentive Requests
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/incentives/submit", status_code=status.HTTP_201_CREATED, tags=["HR - Incentives"])
async def submit_incentive_request(body: IncentiveRequest, background_tasks: BackgroundTasks):
    """🏆 Submit Incentive Request — AI decision returned immediately."""
    if body.employee_id.isdigit():
        emp = get_employee(int(body.employee_id))
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")

    incentive_id = create_incentive_request(body.dict())
    event_id     = create_event(
        event_type="incentive_request",
        entity="incentive_requests",
        entity_id=incentive_id,
        payload={
            "incentive_id":                 incentive_id,
            "employee_id":                  body.employee_id,
            "employee_name":                body.employee_name or "",
            "incentive_type":               body.incentive_type,
            "requested_amount_egp":         body.requested_amount_egp,
            "kpi_achievement":              body.kpi_achievement,
            "performance_score":            body.performance_score,
            "monthly_salary_egp":           body.monthly_salary_egp,
            "tenure_months":                body.tenure_months,
            "is_on_pip":                    body.is_on_pip,
            "is_critical_talent":           body.is_critical_talent,
            "incentive_budget_remaining_egp": body.incentive_budget_remaining_egp,
            "perf_trend":                   body.perf_trend,
            "reason":                       body.reason,
            "department":                   body.department or "",
            "job_level":                    body.job_level or "junior",
            "salary_grade":                 body.salary_grade or "C",
            "source":                       "sync_api",
        },
    )

    logger.info(
        "🏆 [incentive-submit] #%s | event #%s | employee=%s | type=%s | amount=%s EGP",
        incentive_id, event_id, body.employee_id,
        body.incentive_type, body.requested_amount_egp,
    )

    try:
        await job_process_event_queue()
    except Exception as e:
        logger.warning("⚠️ [incentive-submit] Event queue trigger failed: %s", e)

    incentive = await _poll_until_terminal(
        get_incentive_request, incentive_id, _INCENTIVE_TERMINAL, timeout=30
    )

    decision = (
        incentive.get("ai_decision", incentive.get("status", "processing"))
        if incentive else "processing"
    )
    background_tasks.add_task(
        write_audit_log,
        action       = f"incentive_submit_{decision}",
        entity       = "incentive_requests",
        entity_id    = incentive_id,
        performed_by = "event_driven_pipeline_v5.1",
        details      = f"type={body.incentive_type} | decision={decision} | event_id={event_id}",
    )

    is_done = incentive and incentive.get("status") in _INCENTIVE_TERMINAL
    return {
        "incentive_id":    incentive_id,
        "incentive_type":  body.incentive_type,
        "event_id":        event_id,
        "submitted":       True,
        "decision":        decision,
        "status":          incentive.get("status") if incentive else "processing",
        "confidence":      incentive.get("confidence_score") if incentive else None,
        "reason":          incentive.get("decision_reason") if incentive else None,
        "approved_amount": incentive.get("approved_amount_egp") if incentive else None,
        "incentive":       incentive,
        "message": (
            f"✅ Incentive decision ready: {decision}"
            if is_done
            else "⏳ Still processing — check /incentives/{incentive_id}/decision later"
        ),
    }


@app.get("/incentives/pending", tags=["HR - Incentives"])
def list_pending_incentives():
    requests = get_pending_incentive_requests()
    return {"count": len(requests), "incentives": requests}


@app.get("/incentives/{incentive_id}", tags=["HR - Incentives"])
def get_incentive_by_id(incentive_id: int):
    req = get_incentive_request(incentive_id)
    if not req:
        raise HTTPException(status_code=404, detail="Incentive request not found")
    return req


@app.get("/incentives/{incentive_id}/decision", tags=["HR - Incentives"])
async def get_incentive_decision(incentive_id: int):
    """🔄 Get decision — triggers on-demand if still pending."""
    req = get_incentive_request(incentive_id)
    if not req:
        raise HTTPException(status_code=404, detail=f"Incentive request #{incentive_id} not found")

    if req.get("status") in _INCENTIVE_TERMINAL:
        return {
            "incentive_id":    incentive_id,
            "decision":        req.get("ai_decision"),
            "status":          req.get("status"),
            "approved_amount": req.get("approved_amount_egp"),
            "incentive":       req,
        }

    if req.get("status") == "pending":
        try:
            create_event(
                event_type="incentive_request",
                entity="incentive_requests",
                entity_id=incentive_id,
                payload={
                    "incentive_id":                incentive_id,
                    "employee_id":                 str(req.get("employee_id", "")),
                    "incentive_type":              req.get("incentive_type", "performance_bonus"),
                    "requested_amount_egp":        float(req.get("requested_amount_egp", 0)),
                    "kpi_achievement":             float(req.get("kpi_achievement", 0.80)),
                    "performance_score":           float(req.get("performance_score", 0.75)),
                    "monthly_salary_egp":          float(req.get("monthly_salary_egp", 0)),
                    "is_on_pip":                   bool(req.get("is_on_pip", False)),
                    "incentive_budget_remaining_egp":
                        float(req.get("incentive_budget_remaining_egp", 0)),
                    "source": "on_demand",
                },
            )
            await job_process_event_queue()
        except Exception as e:
            logger.error("❌ On-demand incentive trigger failed for #%s: %s", incentive_id, e)

    req = get_incentive_request(incentive_id)
    return {"incentive_id": incentive_id, "status": req.get("status"), "incentive": req}


@app.get("/incentives/{incentive_id}/audit", tags=["HR - Incentives"])
async def get_incentive_audit(incentive_id: int):
    """📋 Full audit trail for an incentive request."""
    req = get_incentive_request(incentive_id)
    if not req:
        raise HTTPException(status_code=404, detail="Incentive request not found")
    audit = get_hr_domain_audit("incentive", incentive_id)
    return {
        "incentive_id":    incentive_id,
        "current_status":  req.get("status"),
        "employee_name":   req.get("employee_name"),
        "incentive_type":  req.get("incentive_type"),
        "ai_decision":     req.get("ai_decision"),
        "approved_amount": req.get("approved_amount_egp"),
        "audit_trail":     audit,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Absence Events
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/absences/submit", status_code=status.HTTP_201_CREATED, tags=["HR - Absence Management"])
async def submit_absence_event(body: AbsenceEventRequest, background_tasks: BackgroundTasks):
    """🚫 Submit Absence Event — AI decision returned immediately."""
    if body.employee_id.isdigit():
        emp = get_employee(int(body.employee_id))
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")

    # Enrich: take the larger of payload vs live 90d count
    live_unexcused_90d = body.unexcused_count_90d
    try:
        live_count = get_employee_unexcused_count_90d(int(body.employee_id))
        if live_count > live_unexcused_90d:
            logger.info(
                "📊 [absence-submit] Live 90d count (%s) > payload (%s) — using live",
                live_count, live_unexcused_90d,
            )
            live_unexcused_90d = live_count
    except Exception:
        pass

    absence_data = body.dict()
    absence_data["absence_date"]        = str(body.absence_date)
    absence_data["unexcused_count_90d"] = live_unexcused_90d

    absence_id = create_absence_event(absence_data)
    event_id   = create_event(
        event_type="absence_event",
        entity="absence_events",
        entity_id=absence_id,
        payload={
            "absence_id":                   absence_id,
            "employee_id":                  body.employee_id,
            "employee_name":                body.employee_name or "",
            "absence_date":                 str(body.absence_date),
            "absence_type_claimed":         body.absence_type_claimed,
            "duration_hours":               body.duration_hours,
            "medical_certificate_provided": body.medical_certificate_provided,
            "prior_approval_obtained":      body.prior_approval_obtained,
            "reason":                       body.reason,
            "total_absences_90d":           body.total_absences_90d,
            "unexcused_count_90d":          live_unexcused_90d,
            "late_arrivals_90d":            body.late_arrivals_90d,
            "previous_warnings":            body.previous_warnings,
            "performance_score":            body.performance_score,
            "is_on_pip":                    body.is_on_pip,
            "department":                   body.department or "",
            "job_level":                    body.job_level or "junior",
            "tenure_months":                body.tenure_months,
            "salary_grade":                 body.salary_grade or "C",
            "source":                       "sync_api",
        },
    )

    logger.info(
        "🚫 [absence-submit] #%s | event #%s | employee=%s | type=%s | "
        "date=%s | unexcused_90d=%s",
        absence_id, event_id, body.employee_id,
        body.absence_type_claimed, body.absence_date, live_unexcused_90d,
    )

    try:
        await job_process_event_queue()
    except Exception as e:
        logger.warning("⚠️ [absence-submit] Event queue trigger failed: %s", e)

    absence = await _poll_until_terminal(
        get_absence_event, absence_id, _ABSENCE_TERMINAL, timeout=30
    )

    decision = (
        absence.get("ai_decision", absence.get("status", "processing"))
        if absence else "processing"
    )
    background_tasks.add_task(
        write_audit_log,
        action       = f"absence_submit_{decision}",
        entity       = "absence_events",
        entity_id    = absence_id,
        performed_by = "event_driven_pipeline_v5.1",
        details      = (
            f"type={body.absence_type_claimed} | decision={decision} | "
            f"event_id={event_id} | unexcused_90d={live_unexcused_90d}"
        ),
    )

    is_done = absence and absence.get("status") in _ABSENCE_TERMINAL
    return {
        "absence_id":             absence_id,
        "absence_date":           str(body.absence_date),
        "absence_type":           body.absence_type_claimed,
        "event_id":               event_id,
        "submitted":              True,
        "decision":               decision,
        "classification":         absence.get("ai_classification") if absence else None,
        "status":                 absence.get("status") if absence else "processing",
        "confidence":             absence.get("confidence_score") if absence else None,
        "reason":                 absence.get("decision_reason") if absence else None,
        "payroll_deduction_days": absence.get("payroll_deduction_days", 0) if absence else 0,
        "escalation_required":    bool(absence.get("escalation_required", False)) if absence else False,
        "absence":                absence,
        "message": (
            f"✅ Absence decision: {decision}"
            if is_done
            else "⏳ Still processing — check /absences/{absence_id}/decision later"
        ),
    }


@app.get("/absences/pending", tags=["HR - Absence Management"])
def list_pending_absences():
    events = get_pending_absence_events()
    return {"count": len(events), "absences": events}


@app.get("/absences/{absence_id}", tags=["HR - Absence Management"])
def get_absence_by_id(absence_id: int):
    event = get_absence_event(absence_id)
    if not event:
        raise HTTPException(status_code=404, detail="Absence event not found")
    return event



@app.get("/absences/{absence_id}/decision", tags=["HR - Absence Management"])
async def get_absence_decision(absence_id: int):
    """🔄 Get decision — triggers on-demand if still pending."""
    event = get_absence_event(absence_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Absence event #{absence_id} not found")

    if event.get("status") in _ABSENCE_TERMINAL:
        return {
            "absence_id":             absence_id,
            "decision":               event.get("ai_decision"),
            "classification":         event.get("ai_classification"),
            "status":                 event.get("status"),
            "payroll_deduction_days": event.get("payroll_deduction_days", 0),
            "escalation_required":    bool(event.get("escalation_required", False)),
            "absence":                event,
        }

    if event.get("status") == "pending":
        try:
            create_event(
                event_type="absence_event",
                entity="absence_events",
                entity_id=absence_id,
                payload={
                    "absence_id":              absence_id,
                    "employee_id":             str(event.get("employee_id", "")),
                    "absence_date":            str(event.get("absence_date", "")),
                    "absence_type_claimed":    event.get("absence_type_claimed", "unexcused"),
                    "duration_hours":          float(event.get("duration_hours", 8)),
                    "medical_certificate_provided":
                        bool(event.get("medical_certificate_provided", False)),
                    "unexcused_count_90d":     int(event.get("unexcused_count_90d", 0)),
                    "previous_warnings":       event.get("previous_warnings", "none"),
                    "performance_score":       float(event.get("performance_score") or 0.75),
                    "source":                  "on_demand",
                },
            )
            await job_process_event_queue()
        except Exception as e:
            logger.error("❌ On-demand absence trigger failed for #%s: %s", absence_id, e)

    event = get_absence_event(absence_id)
    return {"absence_id": absence_id, "status": event.get("status"), "absence": event}


@app.get("/absences/{absence_id}/audit", tags=["HR - Absence Management"])
async def get_absence_audit(absence_id: int):
    """📋 Full audit trail for an absence event."""
    event = get_absence_event(absence_id)
    if not event:
        raise HTTPException(status_code=404, detail="Absence event not found")
    audit = get_hr_domain_audit("absence", absence_id)
    return {
        "absence_id":             absence_id,
        "current_status":         event.get("status"),
        "employee_name":          event.get("employee_name"),
        "absence_date":           str(event.get("absence_date", "")),
        "ai_decision":            event.get("ai_decision"),
        "ai_classification":      event.get("ai_classification"),
        "payroll_deduction_days": event.get("payroll_deduction_days", 0),
        "escalation_required":    bool(event.get("escalation_required", False)),
        "audit_trail":            audit,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tickets
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/tickets", status_code=status.HTTP_201_CREATED, tags=["Support - Tickets"])
def create_support_ticket(body: TicketCreate, background_tasks: BackgroundTasks):
    ticket_id = create_ticket(body.dict())
    event_id  = create_event(
        event_type="ticket_created",
        entity="tickets",
        entity_id=ticket_id,
        payload={"priority": body.priority, "customer_id": body.customer_id},
    )
    background_tasks.add_task(
        event_bus.publish,
        "ticket_created",
        {"ticket_id": ticket_id, "event_id": event_id, **body.dict(), "source": "api"},
    )
    background_tasks.add_task(
        write_audit_log,
        action       = "ticket_created",
        entity       = "tickets",
        entity_id    = ticket_id,
        performed_by = f"customer_{body.customer_id or 'anonymous'}",
        details      = body.subject,
    )
    logger.info("🎫 Ticket #%s created — priority: %s", ticket_id, body.priority)
    return {
        "message":   "Ticket created",
        "ticket_id": ticket_id,
        "event_id":  event_id,
        "priority":  body.priority,
        "next":      "Support agent will process this automatically",
    }



@app.get("/tickets/pending", tags=["Support - Tickets"])
def list_pending_tickets():
    tickets = get_pending_tickets()
    return {"count": len(tickets), "tickets": tickets}


@app.patch("/tickets/{ticket_id}/status", tags=["Support - Tickets"])
def update_ticket(ticket_id: int, status_str: str, resolution: str = ""):
    if not update_ticket_status(ticket_id, status_str, resolution):
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {"ticket_id": ticket_id, "status": status_str, "updated": True}


# ─────────────────────────────────────────────────────────────────────────────
# Leads
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/leads", status_code=status.HTTP_201_CREATED, tags=["CRM - Leads"])
def add_lead(body: LeadCreate, background_tasks: BackgroundTasks):
    lead_id  = create_lead(body.dict())
    event_id = create_event(
        event_type="lead_added",
        entity="leads",
        entity_id=lead_id,
        payload={"source": body.source, "email": body.email},
    )
    background_tasks.add_task(
        event_bus.publish,
        "lead_added",
        {"lead_id": lead_id, "event_id": event_id, **body.dict(), "source": "api"},
    )
    background_tasks.add_task(
        write_audit_log,
        action       = "lead_created",
        entity       = "leads",
        entity_id    = lead_id,
        performed_by = "crm_api",
        details      = f"{body.name} — {body.source}",
    )
    logger.info("💼 Lead #%s added: %s", lead_id, body.name)
    return {"message": "Lead added", "lead_id": lead_id, "event_id": event_id, "status": "new"}


@app.patch("/leads/{lead_id}/status", tags=["CRM - Leads"])
def update_lead(lead_id: int, status_str: str, score: int = 0, notes: str = ""):
    if not update_lead_status(lead_id, status_str, score, notes):
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"lead_id": lead_id, "status": status_str, "score": score}


# ─────────────────────────────────────────────────────────────────────────────
# Events
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/events/pending", tags=["System - Events"])
def list_pending_events():
    events = get_pending_events()
    return {"count": len(events), "events": events}


@app.post("/events/{event_id}/done", tags=["System - Events"])
def mark_event_processed(event_id: int, result: str = "success"):
    mark_event_done(event_id, result)
    return {"event_id": event_id, "marked_as": result}


# ─────────────────────────────────────────────────────────────────────────────
# AI — Decisions & Memory
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/decisions", status_code=status.HTTP_201_CREATED, tags=["AI - Decisions"])
def record_decision(body: DecisionCreate):
    decision_id = save_decision(body.dict())
    return {"decision_id": decision_id, "recorded": True}


@app.get("/memory/{agent}", tags=["AI - Memory"])
def get_agent_memory(agent: str):
    memory = get_all_memory(agent)
    return {"agent": agent, "memory": memory}


@app.post("/memory/{agent}/{key}", tags=["AI - Memory"])
def set_agent_memory(agent: str, key: str, value: str):
    save_memory(agent, key, value)
    return {"agent": agent, "key": key, "saved": True}


# ─────────────────────────────────────────────────────────────────────────────
# Audit
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/audit/logs", tags=["Audit"])
async def get_audit_logs():
    from audit.logger import AuditLogger
    logs = AuditLogger().get_all()
    return {"count": len(logs), "logs": logs}


@app.get("/audit/leaves", tags=["Audit"])
async def get_leave_records():
    from actions.database import DatabaseAction
    records = DatabaseAction().get_leave_records()
    return {"count": len(records), "records": records}


@app.get("/audit/escalations", tags=["Audit"])
async def get_escalation_tickets():
    from actions.database import DatabaseAction
    tickets = DatabaseAction().get_escalation_tickets()
    return {"count": len(tickets), "tickets": tickets}


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/dashboard/stats", tags=["Dashboard"])
def dashboard_stats():
    pending_leaves   = get_pending_leaves()
    pending_tickets  = get_pending_tickets()
    new_leads        = get_new_leads()
    pending_events   = get_pending_events()
    pending_salaries = get_pending_salary_reviews()
    pending_incents  = get_pending_incentive_requests()
    pending_absences = get_pending_absence_events()
    scheduler        = get_scheduler_status()
    ml_info          = get_model_handler().get_info()

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "stats": {
            "leaves":  {"pending": len(pending_leaves)},
            "tickets": {
                "open":   len(pending_tickets),
                "urgent": sum(1 for t in pending_tickets if t.get("priority") == "urgent"),
            },
            "leads":  {"new": len(new_leads)},
            "hr_domains": {
                "salary_reviews": {"pending": len(pending_salaries)},
                "incentives":     {"pending": len(pending_incents)},
                "absences": {
                    "pending": len(pending_absences),
                    "critical": sum(
                        1 for a in pending_absences
                        if int(a.get("unexcused_count_90d", 0)) >= 3
                    ),
                },
            },
            "system": {
                "pending_events":  len(pending_events),
                "scheduler_jobs":  scheduler.get("jobs_count", 0),
                "trigger_running": scheduler.get("running", False),
            },
            "ml_model": {
                "loaded":     ml_info.get("loaded", False),
                "accuracy":   ml_info.get("accuracy"),
                "roc_auc":    ml_info.get("roc_auc"),
                "trained_at": ml_info.get("trained_at"),
            },
        },
    }


@app.get("/dashboard/analytics", tags=["Dashboard"])
async def get_dashboard_analytics():
    from actions.database import DatabaseAction
    records  = DatabaseAction().get_leave_records()
    total    = len(records)
    approved = sum(1 for r in records if r.get("status") == "approved")
    rejected = sum(1 for r in records if r.get("status") == "rejected")
    avg_conf = sum(r.get("confidence", 0) for r in records) / total if total > 0 else 0
    return {
        "status":             "online",
        "total_requests":     total,
        "approvals":          approved,
        "rejections":         rejected,
        "average_confidence": round(avg_conf, 2),
        "recent_decisions":   records[:5],
    }


# ─────────────────────────────────────────────────────────────────────────────
# AI Model
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/model/info", tags=["🤖 AI Model"])
def model_info():
    from agents.hr.hr_agent import HRAgent
    info         = HRAgent.get_model_info()
    handler_info = get_model_handler().get_info()
    return {
        "status":     "loaded" if info.get("loaded") else "not_loaded",
        "model_info": info,
        "v3_quality": {
            "leakage_validation": handler_info.get("leakage_check"),
            "edge_case_tests":    handler_info.get("edge_case_tests"),
            "business_costs":     handler_info.get("business_costs"),
        },
        "hint": (
            "Model not found. Run: python training/hr_train.py"
            if not info.get("loaded") else None
        ),
    }


@app.get("/model/diagnose", tags=["🤖 AI Model"])
async def diagnose_model_confidence(n_samples: int = 100):
    """🔍 Fix 1: Confidence Distribution Diagnostic."""
    handler = get_model_handler()
    if not handler.is_loaded():
        raise HTTPException(
            status_code=503,
            detail="Model not loaded. Run: python training/hr_train.py",
        )
    if not hasattr(handler, "diagnose_confidence"):
        raise HTTPException(
            status_code=501,
            detail="diagnose_confidence() not available. Update leave_model_handler.py to v5.1",
        )
    result = handler.diagnose_confidence(n_samples=n_samples)
    return {
        "diagnostic": result,
        "timestamp":  datetime.utcnow().isoformat() + "Z",
        "note":       "Run this after every training session to verify model health",
    }


@app.post("/model/reload", tags=["🤖 AI Model"])
async def reload_model():
    from agents.hr.hr_agent import HRAgent
    success         = HRAgent.reload_model()
    handler         = get_model_handler()
    handler_success = handler.reload()

    if success or handler_success:
        info = HRAgent.get_model_info()
        return {
            "reloaded":       True,
            "trained_at":     info.get("trained_at"),
            "accuracy":       info.get("accuracy"),
            "roc_auc":        info.get("roc_auc"),
            "handler_loaded": handler_success,
        }
    return JSONResponse(
        status_code=503,
        content={
            "reloaded": False,
            "error":    "Model file not found. Run: python training/hr_train.py",
        },
    )


@app.post("/model/train", tags=["🤖 AI Model"])
async def trigger_training(
    background_tasks:   BackgroundTasks,
    dry_run:            bool  = False,
    skip_leakage_check: bool  = False,
    skip_edge_tests:    bool  = False,
    skip_cost_sim:      bool  = False,
    monthly_requests:   int   = 200,
    cost_false_approve: float = 500.0,
    cost_false_reject:  float = 200.0,
):
    import subprocess
    import sys

    def _run_training():
        script = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "training", "hr_train.py"
        )
        cmd = [sys.executable, script]
        if dry_run:            cmd.append("--dry-run")
        if skip_leakage_check: cmd.append("--skip-leakage-check")
        if skip_edge_tests:    cmd.append("--skip-edge-tests")
        if skip_cost_sim:      cmd.append("--skip-cost-sim")
        cmd += ["--monthly-requests", str(monthly_requests)]
        cmd += ["--cost-false-approve", str(cost_false_approve)]
        cmd += ["--cost-false-reject",  str(cost_false_reject)]

        logger.info("🏋️ Starting training v3: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        logger.info("🏋️ Training finished | returncode=%s", result.returncode)
        if result.stdout:
            logger.info("[Training STDOUT]\n%s", result.stdout[-3000:])
        if result.stderr:
            logger.warning("[Training STDERR]\n%s", result.stderr[-1000:])

    background_tasks.add_task(_run_training)
    return {
        "status": "training_started",
        "config": {
            "dry_run":            dry_run,
            "skip_leakage_check": skip_leakage_check,
            "monthly_requests":   monthly_requests,
        },
        "note":    "Training running in background. Call POST /model/reload when done.",
        "monitor": "Check server logs for training progress.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# 💰 Finance Actions — Email / Escalation / Legal API
# ─────────────────────────────────────────────────────────────────────────────

class FinanceActionRequest(BaseModel):
    action:      str           = Field(..., description="Action name, e.g. send_polite_reminder")
    invoice_id:  Optional[int] = None
    customer_id: Optional[int] = None
    amount:      float         = Field(0, ge=0)
    decision:    str           = Field("manual_trigger")
    reason:      str           = Field("Manually triggered via API")

class LegalCaseUpdateRequest(BaseModel):
    status:     str = Field(..., description="New status: opened|in_progress|hearing|settled|resolved|closed")
    note:       str = Field("", max_length=500)
    resolution: str = Field("", max_length=2000)


@app.post("/finance/actions/execute", tags=["💰 Finance Actions"])
async def finance_execute_action(body: FinanceActionRequest):
    """⚡ Manually trigger a finance action (email, notification, system update)."""
    from actions.finance_actions import FinanceActionExecutor
    from agents.base_agent import generate_request_id

    executor   = FinanceActionExecutor()
    request_id = generate_request_id()

    result = await executor.execute(
        action=body.action,
        invoice_id=body.invoice_id,
        customer_id=body.customer_id,
        amount=body.amount,
        decision=body.decision,
        reason=body.reason,
        request_id=request_id,
    )

    return {
        "status":     "executed",
        "request_id": request_id,
        "action":     body.action,
        "result":     result,
        "timestamp":  datetime.utcnow().isoformat() + "Z",
    }


@app.get("/finance/actions/log", tags=["💰 Finance Actions"])
def finance_action_log(
    invoice_id:  Optional[int] = None,
    customer_id: Optional[int] = None,
    action_type: Optional[str] = None,
    limit:       int           = 50,
):
    """📋 View collection action log with optional filters."""
    from core.finance_db import get_collection_log
    logs = get_collection_log(
        invoice_id=invoice_id,
        customer_id=customer_id,
        action_type=action_type,
        limit=limit,
    )
    return {"count": len(logs), "logs": logs}


@app.get("/finance/actions/log/{invoice_id}", tags=["💰 Finance Actions"])
def finance_action_log_by_invoice(invoice_id: int):
    """📋 View all actions taken for a specific invoice."""
    from core.finance_db import get_collection_log
    logs = get_collection_log(invoice_id=invoice_id, limit=100)
    return {"invoice_id": invoice_id, "count": len(logs), "logs": logs}


@app.post("/finance/actions/escalate/{invoice_id}", tags=["💰 Finance Actions"])
async def finance_escalate_invoice(
    invoice_id:  int,
    customer_id: Optional[int] = None,
    amount:      float         = 0,
    force_tier:  Optional[int] = None,
):
    """📈 Escalate an invoice to the next collection tier (or force a specific tier)."""
    from actions.escalation_engine import escalation_engine
    from agents.base_agent import generate_request_id

    result = await escalation_engine.escalate(
        invoice_id=invoice_id,
        customer_id=customer_id,
        amount=amount,
        force_tier=force_tier,
        request_id=generate_request_id(),
    )
    return result


@app.get("/finance/escalation/{invoice_id}", tags=["💰 Finance Actions"])
def finance_escalation_status(invoice_id: int):
    """📊 Get escalation status and full action history for an invoice."""
    from core.finance_db import get_escalation_status
    return get_escalation_status(invoice_id)


@app.get("/finance/escalation", tags=["💰 Finance Actions"])
def finance_active_escalations():
    """📊 List all invoices currently under active escalation."""
    from core.finance_db import get_active_escalations
    escalations = get_active_escalations()
    return {"count": len(escalations), "escalations": escalations}


@app.get("/finance/legal/cases", tags=["💰 Finance Actions"])
def finance_legal_cases(
    status:      Optional[str] = None,
    customer_id: Optional[int] = None,
    limit:       int           = 50,
):
    """⚖️ List legal cases with optional filters."""
    from core.finance_db import get_legal_cases
    cases = get_legal_cases(status=status, customer_id=customer_id, limit=limit)
    return {"count": len(cases), "cases": cases}


@app.get("/finance/legal/cases/{case_id}", tags=["💰 Finance Actions"])
def finance_legal_case_detail(case_id: int):
    """⚖️ Get detailed info for a single legal case."""
    from core.finance_db import get_legal_case
    case = get_legal_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Legal case {case_id} not found")
    return case


@app.post("/finance/legal/cases/{case_id}/update", tags=["💰 Finance Actions"])
def finance_update_legal_case(case_id: int, body: LegalCaseUpdateRequest):
    """⚖️ Update legal case status and add timeline notes."""
    from core.finance_db import update_legal_case_status, get_legal_case
    ok = update_legal_case_status(
        case_id=case_id,
        status=body.status,
        note=body.note,
        resolution=body.resolution,
    )
    if not ok:
        raise HTTPException(status_code=404, detail=f"Legal case {case_id} not found or update failed")
    updated = get_legal_case(case_id)
    return {"updated": True, "case": updated}


@app.get("/finance/actions/dashboard-data", tags=["💰 Finance Actions"])
def finance_actions_dashboard_data(days: int = 7):
    """📊 Aggregated data for the Finance Actions dashboard."""
    from core.finance_db import (
        get_collection_action_stats,
        get_active_escalations,
        get_legal_cases,
        get_collection_log,
    )

    stats       = get_collection_action_stats(days=days)
    escalations = get_active_escalations()
    legal       = get_legal_cases(limit=20)
    recent_log  = get_collection_log(limit=20)

    return {
        "period_days":        days,
        "action_stats":       stats,
        "active_escalations": {"count": len(escalations), "items": escalations[:10]},
        "legal_cases":        {"count": len(legal), "items": legal[:10]},
        "recent_actions":     recent_log[:10],
        "timestamp":          datetime.utcnow().isoformat() + "Z",
    }


# ─────────────────────────────────────────────────────────────────────────────
# 💰 Finance Risk — API Endpoints
# ─────────────────────────────────────────────────────────────────────────────

class FinanceRiskInput(BaseModel):
    overdue_days_normalized:   float = Field(0.0, ge=0.0, le=1.0, description="Overdue days / 180")
    amount_normalized:         float = Field(0.0, ge=0.0, le=1.0, description="Invoice amount / 100000")
    paid_ratio:                float = Field(1.0, ge=0.0, le=1.0)
    late_ratio:                float = Field(0.0, ge=0.0, le=1.0)
    on_time_ratio:             float = Field(1.0, ge=0.0, le=1.0)
    customer_age_normalized:   float = Field(0.5, ge=0.0, le=1.0, description="Age in months / 60")
    invoice_frequency:         float = Field(0.5, ge=0.0, le=1.0, description="Invoice count / 20")
    avg_delay_normalized:      float = Field(0.0, ge=0.0, le=1.0, description="Avg delay days / 90")
    credit_score_normalized:   float = Field(0.8, ge=0.0, le=1.0, description="Credit score / 850")
    industry_risk_factor:      float = Field(0.35, ge=0.0, le=1.0)
    seasonal_factor:           float = Field(0.35, ge=0.0, le=1.0)
    # Optional raw fields for industry/month lookup
    industry:                  Optional[str] = None
    invoice_month:             Optional[int] = Field(None, ge=1, le=12)


class FinanceBatchInput(BaseModel):
    records: List[FinanceRiskInput] = Field(..., min_items=1, max_items=500)


# @app.post("/finance/predict-risk", tags=["💰 Finance"])
async def finance_predict_risk(body: "FinanceRiskInput"):  # noqa: F821
    """
    🔮 Predict payment risk for a single customer/invoice.
 
    Returns:
        decision      : approve / manual_review / reject
        risk_score    : ML probability (0–1)
        confidence    : decision confidence (0–1)
        reasons       : top-3 specific human-readable reasons
        positive_factors : what's working in the customer's favour
        negative_factors : what's driving risk up
        dominant_factor  : single most impactful factor
        summary          : one-sentence plain-English explanation
        feature_snapshot : all 11 input features (for audit trail)
        latency_ms       : prediction time in milliseconds
        model_version    : model version that produced this result
    """
    import numpy as np
    from datetime import datetime
 
    predictor = _get_fin_predictor()  # noqa: F821 — already defined in main.py
    if predictor is None:
        raise HTTPException(  # noqa: F821
            status_code=503,
            detail=(
                "Finance risk model not loaded. "
                "Run: python training/finance_train.py"
            ),
        )
 
    request_id = _make_fin_request_id()
 
    # ── Resolve industry / month overrides ───────────────────────────────────
    industry_factor = body.industry_risk_factor
    if body.industry:
        industry_factor = _INDUSTRY_RISK.get(  # noqa: F821
            body.industry.lower(), body.industry_risk_factor
        )
 
    seasonal_factor = body.seasonal_factor
    if body.invoice_month:
        seasonal_factor = _SEASONAL_RISK.get(  # noqa: F821
            body.invoice_month, body.seasonal_factor
        )
 
    X = np.array([[
        body.overdue_days_normalized,
        body.amount_normalized,
        body.paid_ratio,
        body.late_ratio,
        body.on_time_ratio,
        body.customer_age_normalized,
        body.invoice_frequency,
        body.avg_delay_normalized,
        body.credit_score_normalized,
        industry_factor,
        seasonal_factor,
    ]])
 
    # ── Call predictor — now returns latency_ms + model_version ──────────────
    result = predictor.predict(X)  # ← FinanceRiskPredictor.predict() in main.py
                                    #   (does NOT use handler, uses the pickle wrapper)
 
    # NOTE: if you're using _get_fin_predictor() (the FinanceRiskPredictor from main.py)
    # rather than the handler, you need to wrap it to get the new fields.
    # Easiest fix: also call the handler for the extra metadata:
 
    from agents.finance.explainability import get_explainability_engine
    import time as _time
 
    t0          = _time.perf_counter()
    explanation = get_explainability_engine().explain(X, result["risk_score"], result["decision"])
    latency_ms  = int((_time.perf_counter() - t0) * 1000)
 
    logger.info(                # noqa: F821 — logger defined at top of main.py
        "💰 [/finance/predict-risk] request_id=%s | risk=%.4f | decision=%s | "
        "latency=%dms | reasons=%s | snapshot=%s",
        request_id,
        result["risk_score"],
        result["decision"],
        latency_ms,
        explanation.reasons,
        {k: v["value"] for k, v in explanation.feature_snapshot.items()},
    )
 
    return {
        # ── Core decision ─────────────────────────────────────────────────
        "decision":          result["decision"],
        "risk_score":        result["risk_score"],
        "confidence":        result["confidence"],
 
        # ── Explainability (v3.1 NEW) ─────────────────────────────────────
        "reasons":           explanation.reasons,           # top-3 specific reasons
        "positive_factors":  explanation.positive_factors,  # what's good
        "negative_factors":  explanation.negative_factors,  # what's bad
        "dominant_factor":   explanation.dominant_factor,   # single biggest driver
        "summary":           explanation.summary,           # one-sentence English
 
        # ── Audit / Tracing (v3.1 NEW) ────────────────────────────────────
        "feature_snapshot":  explanation.feature_snapshot,  # all 11 features
        "request_id":        request_id,                    # trace ID
        "latency_ms":        latency_ms,                    # prediction time
        "model_version":     predictor.decision_engine.to_dict(),  # thresholds used
 
        # ── Legacy fields (kept for backward compat) ──────────────────────
        "thresholds": {
            "reject_above": predictor.decision_engine.reject_threshold,
            "review_above": predictor.decision_engine.review_threshold,
        },
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@app.post("/finance/predict-risk/batch", tags=["💰 Finance"])
async def finance_predict_risk_batch(body: "FinanceBatchInput"):
    """
    🔮 Batch predict — v2.0: Dashboard updates immediately after scoring.
    """
    import time as _time
    from datetime import datetime
    from agents.finance.explainability import get_explainability_engine
 
    predictor = _get_fin_predictor()
    if predictor is None:
        raise HTTPException(status_code=503, detail="Finance risk model not loaded.")
 
    explain_engine = get_explainability_engine()
    batch_start    = _time.perf_counter()
 
    rows = []
    for rec in body.records:
        industry_factor = _INDUSTRY_RISK.get(
            (rec.industry or "").lower(), rec.industry_risk_factor
        )
        seasonal_factor = _SEASONAL_RISK.get(
            rec.invoice_month or 0, rec.seasonal_factor
        )
        rows.append([
            rec.overdue_days_normalized, rec.amount_normalized,
            rec.paid_ratio, rec.late_ratio, rec.on_time_ratio,
            rec.customer_age_normalized, rec.invoice_frequency,
            rec.avg_delay_normalized, rec.credit_score_normalized,
            industry_factor, seasonal_factor,
        ])
 
    X       = np.array(rows)
    results = predictor.predict_batch(X)
 
    enriched = []
    for i, (res, rec_row) in enumerate(zip(results, X)):
        feat_arr    = rec_row.reshape(1, -1)
        explanation = explain_engine.explain(feat_arr, res["risk_score"], res["decision"])
 
        enriched.append({
            **res,
            "reasons":          explanation.reasons,
            "positive_factors": explanation.positive_factors,
            "negative_factors": explanation.negative_factors,
            "dominant_factor":  explanation.dominant_factor,
            "summary":          explanation.summary,
            "feature_snapshot": explanation.feature_snapshot,
        })
 
    batch_latency_ms = int((_time.perf_counter() - batch_start) * 1000)
 
    logger.info(
        "💰 [/finance/predict-risk/batch] count=%d | total_latency=%dms | "
        "avg_latency=%.1fms",
        len(enriched),
        batch_latency_ms,
        batch_latency_ms / max(len(enriched), 1),
    )
 
    # ── ✅ v2.0: Push batch metrics → Dashboard يتحدّث فورًا ────────────────
    try:
        high_risk = sum(1 for r in enriched if r.get("risk_score", 0) >= 0.70)
        avg_risk  = sum(r.get("risk_score", 0) for r in enriched) / max(len(enriched), 1)
 
        from core.finance_metrics_bridge import metrics_bridge
        await metrics_bridge.on_batch_scored(
            count            = len(enriched),
            high_risk_count  = high_risk,
            avg_risk         = avg_risk,
            batch_latency_ms = batch_latency_ms,
        )
    except Exception as e:
        logger.debug("metrics_bridge batch push failed (non-critical): %s", e)
 
    return {
        "count":            len(enriched),
        "results":          enriched,
        "batch_latency_ms": batch_latency_ms,
        "avg_latency_ms":   round(batch_latency_ms / max(len(enriched), 1), 1),
        "timestamp":        datetime.utcnow().isoformat() + "Z",
    }

 
# print("=" * 60)
# print("PATCH لـ main.py — finance_predict_risk_batch")
# print("=" * 60)
# print(PATCH_CODE)
 


@app.get("/finance/model/info", tags=["💰 Finance"])
def finance_model_info():
    """
    📋 Finance risk model metadata and status.
    """
    if not os.path.exists(_FIN_MODEL_PATH):
        return {
            "loaded":  False,
            "message": "Model not found. Run: python training/finance_train.py",
            "path":    _FIN_MODEL_PATH,
        }
    try:
        with open(_FIN_MODEL_PATH, "rb") as f:
            saved = pickle.load(f)
        meta = saved.get("metadata", {})
        predictor = _get_fin_predictor()
        engine    = predictor.decision_engine if predictor else None
        return {
            "loaded":            True,
            "version":           meta.get("version", "unknown"),
            "trained_at":        meta.get("trained_at"),
            "n_samples":         meta.get("n_samples"),
            "feature_count":     meta.get("feature_count"),
            "ensemble_weights":  meta.get("ensemble_weights"),
            "decision_engine":   engine.to_dict() if engine else meta.get("decision_engine"),
            "metrics":           meta.get("metrics"),
            "cost_optimization": meta.get("cost_optimization"),
            "shap_top10":        dict(list((meta.get("shap_importance") or {}).items())[:10]),
            "path":              _FIN_MODEL_PATH,
        }
    except Exception as e:
        return {"loaded": False, "error": str(e), "path": _FIN_MODEL_PATH}


@app.post("/finance/model/reload", tags=["💰 Finance"])
def finance_model_reload():
    """
    🔄 Hot-reload the finance risk model from disk (after retraining).
    """
    predictor = _load_fin_predictor()
    if predictor is None:
        raise HTTPException(
            status_code=503,
            detail=f"Model not found at {_FIN_MODEL_PATH}. Run training first.",
        )
    return {
        "reloaded":  True,
        "path":      _FIN_MODEL_PATH,
        "thresholds": predictor.decision_engine.to_dict(),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@app.get("/finance/model/thresholds", tags=["💰 Finance"])
def finance_model_thresholds():
    """
    📊 Current decision engine thresholds and industry/seasonal risk tables.
    """
    predictor = _get_fin_predictor()
    engine    = predictor.decision_engine if predictor else FinanceDecisionEngine()
    return {
        "decision_engine": engine.to_dict(),
        "decision_logic": {
            f">= {engine.reject_threshold}": "reject",
            f">= {engine.review_threshold}": "manual_review",
            f"< {engine.review_threshold}":  "approve",
        },
        "industry_risk_factors": _INDUSTRY_RISK,
        "seasonal_risk_factors": _SEASONAL_RISK,
        "feature_names":         FIN_FEATURE_NAMES,
        "model_loaded":          predictor is not None,
    }


@app.websocket("/ws/metrics")
async def metrics_websocket(websocket: WebSocket):
    await websocket.accept()
    collector = get_metrics_collector()
    await collector.ws_connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep-alive
    except WebSocketDisconnect:
        await collector.ws_disconnect(websocket)

# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=9000, reload=True, log_level="info")