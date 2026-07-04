"""
main.py — AI Enterprise ERP System v6.5 (Node.js API Edition)
================================================================
# uvicorn main:app --host 0.0.0.0 --port 9000 --reload

✅ v6.0 Migration:
    - Removed ALL MySQL / core.db imports
    - All HR operations → HRDB (Motor/MongoDB)
    - All Finance operations → FinanceDB (Motor/MongoDB)
    - Lifespan uses ensure_mongo_ready() for Atlas init
    - All route handlers are async with await db.method()

✅ v6.1 Fix B1:
    - submit_leave_sync        → direct workflow call (bypass idempotency)
    - submit_salary_review     → direct workflow call
    - submit_incenwtive_request → direct workflow call
    - submit_absence_event     → direct workflow call

✅ v6.4 — Node.js API Bridge Layer ("Method 1"):
    - New: core/node_api_client.py — async, retrying, circuit-breaker-
      protected client over the Node.js/Express HR + Finance REST API
      (http://localhost:5005/v1/*).
    - New: agents/tools/node_api_tools.py — 22 LangChain @tool-wrapped
      functions over that client, registered onto the agentic
      coordinator at startup.
    - New: GET /health/node-api — reachability + circuit-breaker status
      for the Node.js dependency.

✅ v6.5 — FULL Node.js API Migration (2026-07):
    - REMOVED every direct MongoDB/Motor call. get_hr_db() and
      get_finance_db() now ALWAYS return the Node.js-backed proxies
      (core/node_hr_proxy.py / core/node_finance_proxy.py) — there is
      no more direct `hr_db.db["..."]` collection access anywhere in
      this file. Every single route goes through NodeAPIClient →
      Node.js/Express → MongoDB.
    - /employees, /employees/{id}: DISABLED (503). There is no
      /hr/employees route in hr.routes.js today — confirmed against
      the actual route file. Re-enable once that route exists in Node.
    - /employees/{id}/salary-reviews, /employees/{id}/incentives: now
      use NodeHRProxy.get_employee_salary_reviews() /
      get_employee_incentives() (N+1 client-side filtering — see
      node_hr_proxy.py docstrings for why; there's no
      /hr/salary-reviews/employee/:id or /hr/incentive-requests/employee/:id
      route yet, unlike leaves/absences which do have one).
    - /events/pending, /events/{id}/done: DISABLED (503). No
      /hr/events or generic /events route exists in Node — the
      MongoDB-native event-bus/scheduler queue has no Node equivalent.
    - /decisions (generic HR decision log), /memory/*: DISABLED (503).
      No /hr/decisions or /hr/memory route exists in Node.
    - /audit/logs (generic, cross-domain): DISABLED (503). Node only
      exposes /hr/audit/:domain/:entity_id (domain+entity scoped), not
      a flat "all audit logs" listing. Domain-scoped audit endpoints
      (/leaves/{id}/audit, /salary-reviews/{id}/audit, etc.) are
      UNCHANGED and fully working.
    - /audit/leaves: now uses hr_db.get_leaves() (GET /hr/leaves)
      instead of the old direct hr_db.leaves.find() Motor cursor.
    - /dashboard/analytics: now uses hr_db.get_leaves() instead of the
      old direct hr_db.leaves.find() Motor cursor.
    - /health/detailed: MongoDB ping replaced with a Node API bridge
      ping (there is no direct Mongo connection left to ping from this
      service).
    - Nothing else changed. Every route that already went through
      get_hr_db()/get_finance_db() method calls (not raw .db[...]
      access) keeps working exactly as before, now fully backed by the
      Node.js REST API end to end.
"""

import json
import logging
import os
import asyncio
import pickle
import time
import warnings
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from typing import Optional, List
from core.cache_manager import get_cache_manager, CacheKeys

_AGENT_DEBUG_LOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "debug-d1730a.log",
)


def _agent_debug_log(
    location: str,
    message: str,
    data: Optional[dict] = None,
    hypothesis_id: str = "",
    run_id: str = "pre-fix",
) -> None:
    # #region agent log
    try:
        payload = {
            "sessionId": "d1730a",
            "timestamp": int(time.time() * 1000),
            "location": location,
            "message": message,
            "data": data or {},
            "hypothesisId": hypothesis_id,
            "runId": run_id,
        }
        with open(_AGENT_DEBUG_LOG_PATH, "a", encoding="utf-8") as _df:
            _df.write(json.dumps(payload, default=str) + "\n")
    except Exception:
        pass
    # #endregion

import numpy as np
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field, validator
from dotenv import load_dotenv

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)


from orchestrator.orchestrator import Orchestrator
from config.settings import get_settings
from utils.serialize_utils import serialize_doc
from core.trigger import (
    start_trigger_engine,
    stop_trigger_engine,
    get_scheduler_status,
    job_scan_pending_leaves,
    job_process_event_queue,
    job_scan_pending_salary_reviews,
    job_scan_pending_incentives,
    job_scan_pending_absences,
)
from core.webhook_handler import webhook_router
from core.event_bus import event_bus

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

# ── Agentic Layer (Self-planning · Tool use · Multi-agent · Reflection) ────────
# Additive package — does NOT modify any existing module. See
# app/orchestrator/agentic/ for the full implementation.
from orchestrator.agentic import agentic_router, get_agentic_coordinator

# ── v6.4: Node.js API Bridge Layer ("Method 1" — AI talks to APIs only) ───────
from core.node_api_client import (
    init_node_api_client,
    init_node_api_client_async,
    close_node_api_client,
    get_node_api_client,
    NodeAPIError,   # ✅ needed for the dedicated exception handler below
)
from agents.tools.node_api_tools import NODE_API_TOOLS

# ── v6.5: get_hr_db() / get_finance_db() now ALWAYS resolve to the
# Node.js-backed proxies. These are the ONLY db accessors used anywhere
# in this file from now on — there is no more direct Motor/pymongo
# import left in main.py.
from core.node_hr_proxy import get_hr_db
from core.node_finance_proxy import get_finance_db


load_dotenv()
settings = get_settings()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Suppress PyMongo background task noise ────────────────────────────────────
# Kept even though this service no longer opens its own Motor connection —
# some shared dependencies (workflows, training modules) may still import
# pymongo transitively. Harmless no-op otherwise.
for _noisy_logger in ("pymongo.client", "pymongo.connection", "pymongo.serverSelection"):
    logging.getLogger(_noisy_logger).setLevel(logging.WARNING)

# ── Background Health Cache ────────────────────────────────────────────────────
import time as _monotime

HEALTH_PING_INTERVAL_SEC = 30
_health_cache: dict = {
    "db_status":        "initializing",
    "redis_status":     "initializing",
    "last_checked":     None,
    "db_latency_ms":    0,
    "redis_latency_ms": 0,
    "scheduler_status": {"running": False, "jobs_count": 0},
    "ml_info":          {"loaded": False},
}
_health_cache_lock = asyncio.Lock()
_health_cache_task: Optional[asyncio.Task] = None


async def _update_health_cache() -> None:
    """Background coroutine: pings the Node.js API bridge + Redis and
    updates _health_cache every 30s. There is no direct MongoDB
    connection from this service anymore — "db_status" here reflects
    the Node.js API's reachability, since that's what actually gates
    every read/write this service does."""
    while True:
        try:
            db_status, db_latency = "healthy (API)", 0
            try:
                t0 = _monotime.perf_counter()
                client = get_node_api_client()
                await client.ping(timeout_sec=2.0)
                db_latency = int((_monotime.perf_counter() - t0) * 1000)
            except Exception as e:
                db_status = f"degraded (API): {str(e)[:80]}"

            redis_status, redis_latency = "healthy", 0
            try:
                t0 = _monotime.perf_counter()
                await asyncio.wait_for(get_cache_manager().ping(), timeout=0.5)
                redis_latency = int((_monotime.perf_counter() - t0) * 1000)
            except Exception:
                redis_status = "degraded: unreachable (fallback active)"

            try:
                scheduler_status = get_scheduler_status()
            except Exception as e:
                scheduler_status = {"running": False, "jobs_count": 0, "error": str(e)[:80]}

            try:
                ml_info = get_model_handler().get_info()
            except Exception as e:
                ml_info = {"loaded": False, "error": str(e)[:80]}

            async with _health_cache_lock:
                _health_cache.update({
                    "db_status":        db_status,
                    "redis_status":     redis_status,
                    "last_checked":     datetime.utcnow().isoformat() + "Z",
                    "db_latency_ms":    db_latency,
                    "redis_latency_ms": redis_latency,
                    "scheduler_status": scheduler_status,
                    "ml_info":          ml_info,
                })
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.debug("_update_health_cache error: %s", e)

        try:
            await asyncio.sleep(HEALTH_PING_INTERVAL_SEC)
        except asyncio.CancelledError:
            break


# ── Finance In-Memory Cache ────────────────────────────────────────────────────
_DASHBOARD_MEM_CACHE:  dict = {}
_MODEL_INFO_MEM_CACHE: dict = {}

DASHBOARD_CACHE_TTL_SEC  = 30
MODEL_INFO_CACHE_TTL_SEC = 120


def _mem_cache_get(store: dict, key: str):
    entry = store.get(key)
    if entry and _monotime.monotonic() < entry["expires_at"]:
        return entry["data"]
    store.pop(key, None)
    return None


def _mem_cache_set(store: dict, key: str, data, ttl_sec: int):
    store[key] = {"data": data, "expires_at": _monotime.monotonic() + ttl_sec}


orchestrator   = Orchestrator()
leave_workflow = LeaveApprovalWorkflow()


# ─────────────────────────────────────────────────────────────────────────────
# Lifespan
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 AI Enterprise ERP v6.5 (Node.js API Edition) starting up...")

    # ── Node API init ──────────────────────────────────────────────────────
    try:
        await init_node_api_client_async()
        logger.info("✅ Node API Client initialized (with eager login if configured)")
    except Exception as e:
        logger.error("❌ Node API Client init failed: %s", e)
        raise

    # ── ML Model warm-up ──────────────────────────────────────────────────
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

    # ── Trigger Engine ────────────────────────────────────────────────────
    await start_trigger_engine(orchestrator)
    logger.info("✅ Trigger Engine started")

    # ── Health Cache background pinger ─────────────────────────────────────
    global _health_cache_task
    _health_cache_task = asyncio.create_task(_update_health_cache())
    logger.info("✅ Health cache background pinger started")

    # ── Finance risk model ────────────────────────────────────────────────
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
    print(f"  🧠  {settings.APP_NAME}  —  ERP v6.5 (Node.js API Edition)")
    print(f"  📦  Version     : {settings.APP_VERSION}")
    print(f"  🤖  LLM         : {settings.GEMINI_MODEL} ({settings.LLM_PROVIDER})")
    print(f"  🌡️   Temperature : {settings.LLM_TEMPERATURE}")
    print(f"  ⚡  Triggers     : Scheduler + DB Watcher + Webhooks")
    print(f"  🔑  API Key     : {'✅ Set' if settings.GOOGLE_API_KEY else '❌ Missing!'}")
    print(f"  🔌  Data Layer  : Node.js/Express REST API only (no direct MongoDB)")
    print(f"  📖  Docs        : http://localhost:9000/docs")
    print("═" * 60 + "\n")

    await start_metrics_collector()
    logger.info("✅ MetricsCollector started")

    # ── v6.4: Node.js API Bridge Layer init ─────────────────────────────────
    try:
        node_api_client = get_node_api_client()
        ping_result = await node_api_client.ping()
        if ping_result.get("reachable"):
            logger.info(
                "✅ Node.js API bridge ready — base_url reachable | latency=%dms",
                ping_result.get("latency_ms", -1),
            )
        else:
            logger.warning(
                "⚠️ Node.js API bridge initialized but NOT reachable right now "
                "(%s) — tools will retry/circuit-break per call, this is "
                "non-fatal at startup in case Node.js is still booting.",
                ping_result.get("error", "unknown"),
            )
    except Exception as e:
        logger.warning("⚠️ Node.js API bridge init failed (non-fatal): %s", e)

    # ── Agentic Layer wiring ───────────────────────────────────────────────
    # ✅ FIX (2026-07): the coordinator was never meant to own tool
    # registration — hasattr(coordinator, "register_tools") was always
    # False because AgenticCoordinator only exposes wire_agents() (message
    # bus) + run_goal() (plan/act/reflect). The actual registry for
    # planner-callable tools is orchestrator/agentic/tools.py's
    # ToolRegistry, and it now auto-registers every NODE_API_TOOLS entry
    # (wrapped via _wrap_langchain_tool, prefixed "node_api.") the first
    # time get_tool_registry() runs — see that file's module docstring.
    # No manual registration call is needed here anymore; importing
    # get_tool_registry() eagerly below just forces that auto-registration
    # to happen at startup (so failures surface in the startup log, same
    # as before) instead of lazily on the first /agentic/* request.
    try:
        coordinator = get_agentic_coordinator()
        coordinator.wire_agents()

        from orchestrator.agentic.tools import get_tool_registry
        registry = get_tool_registry()
        node_api_tool_count = sum(
            1 for name in registry.names() if name.startswith("node_api.")
        )
        logger.info(
            "✅ Tool registry ready — %d tools total (%d from NODE_API_TOOLS)",
            len(registry.names()), node_api_tool_count,
        )
        logger.info("✅ Agentic layer ready — /agentic/* (plan·tools·bus·reflection)")
    except Exception as e:
        logger.warning("⚠️ Agentic layer wiring failed (non-fatal): %s", e)

    # ── Redis Cache ────────────────────────────────────────────────────────
    try:
        cache_ok = await get_cache_manager().ping()
        if cache_ok:
            logger.info("✅ Redis cache connected — dashboard caching active")
            _health_cache["redis_status"] = "healthy"
        else:
            logger.warning("⚠️ Redis unreachable — fallback active")
            _health_cache["redis_status"] = "degraded: unreachable (fallback active)"
    except Exception as e:
        logger.warning("⚠️ Redis check failed at startup (non-fatal): %s", e)
        _health_cache["redis_status"] = "degraded: startup check failed"

    # ── Dashboard Cache Warmup disabled because of Node API switch ────────

    yield

    logger.info("🔴 Shutting down...")
    stop_trigger_engine()
    get_metrics_collector().stop()
    logger.info("🔴 MetricsCollector stopped")
    if _health_cache_task is not None:
        _health_cache_task.cancel()
        try:
            await _health_cache_task
        except asyncio.CancelledError:
            pass
        logger.info("🔴 Health cache background pinger stopped")
    # v6.4: close the Node.js API bridge's pooled httpx connections cleanly
    # on shutdown, same pattern as the trigger engine / metrics collector
    # above — avoids leaking open sockets on reload/restart.
    try:
        await close_node_api_client()
    except Exception as e:
        logger.debug("close_node_api_client() error during shutdown: %s", e)


# ─────────────────────────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title=f"🧠 {settings.APP_NAME} — ERP",
    description=(
        "Autonomous ERP powered by AI agents (LangChain + Google Gemini).\n\n"
        "**Modules:** HR · Leaves · Salary · Incentives · Absences · "
        "Events · Audit\n\n"
        "**v6.1:** Direct Workflow submit — bypasses event-bus idempotency\n\n"
        "**v6.5:** Full Node.js API migration — every route reads/writes "
        "through the Node.js/Express REST API. No direct MongoDB connection "
        "left in this service."
    ),
    version="6.5.0",
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

# 🧠 Agentic layer — autonomous plan→act→reflect loop + agent message bus
app.include_router(agentic_router, prefix="/agentic", tags=["🧠 Agentic"])

import os
os.makedirs("app/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# ✅ FIX (2026-07): NodeAPIError already carries a real, meaningful
# status_code from the Node.js API's own response (400 for validation
# errors, 401 for auth, 404 for missing routes, 5xx after retries/circuit
# open — see core/node_api_client.py's NodeAPIError + _request()). Without
# a dedicated handler, every NodeAPIError fell through to the generic
# Exception handler below, which always answers 500 regardless of the
# real cause — so a simple bad-input error (e.g. an employee_id that
# isn't a valid MongoDB ObjectId) looked identical to an actual server
# crash from the caller's point of view. This handler must be registered
# BEFORE @app.exception_handler(Exception): FastAPI/Starlette matches the
# most specific registered exception type, so NodeAPIError (a subclass of
# Exception) is caught here first and never reaches the generic handler.
@app.exception_handler(NodeAPIError)
async def node_api_error_handler(request: Request, exc: NodeAPIError):
    status_code = exc.status_code or 502  # 502 Bad Gateway: upstream (Node) failed with no code we can trust
    is_client_error = status_code is not None and 400 <= status_code < 500

    if is_client_error:
        logger.warning(
            "⚠️ NodeAPIError (client error, endpoint=%s): %s",
            exc.endpoint, exc,
        )
    else:
        logger.error(
            "❌ NodeAPIError (upstream/server error, endpoint=%s): %s",
            exc.endpoint, exc, exc_info=True,
        )

    return JSONResponse(
        status_code=status_code,
        content={
            "status":      "error",
            "detail":      str(exc),
            "type":        "NodeAPIError",
            "node_endpoint": exc.endpoint,
            "path":        str(request.url),
            "timestamp":   datetime.utcnow().isoformat() + "Z",
        },
    )


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
# 💰 Finance Risk — ML Engine
# ─────────────────────────────────────────────────────────────────────────────

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

_FIN_ML_EXCLUDED = {
    "overdue_days", "overdue_days_normalized", "overdue_x_industry",
    "payment_delay", "is_late", "is_bad_payer",
}

_FIN_MODEL_DIR  = os.path.join(os.path.dirname(__file__), "models", "finance")
_FIN_MODEL_PATH = os.path.join(_FIN_MODEL_DIR, "payment_risk_v8.pkl")
os.makedirs(_FIN_MODEL_DIR, exist_ok=True)


class FinanceDecisionEngine:
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
    amount_x_overdue = X[:, 1] * X[:, 0]
    credit_x_late    = (1 - X[:, 8]) * X[:, 3]
    risk_composite   = (
        0.30 * X[:, 0] + 0.25 * X[:, 3] + 0.20 * (1 - X[:, 8]) +
        0.15 * X[:, 9] + 0.10 * X[:, 10]
    )
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


ensemble_predict_proba_v8 = _fin_ensemble_predict_proba


def _fin_array_to_dict(row: np.ndarray) -> dict:
    keys = FIN_BASE_FEATURES
    return {k: float(v) for k, v in zip(keys, row)}


def _fin_api_row_to_ml_dict(row: np.ndarray) -> dict:
    d = _fin_array_to_dict(row)
    age = float(d["customer_age_normalized"])
    return {
        k: v for k, v in {
            "amount_normalized": d["amount_normalized"],
            "customer_age_normalized": age,
            "years_with_company_normalized": float(np.clip(age * 0.6, 0, 1)),
            "invoice_frequency": d["invoice_frequency"],
            "industry_risk_factor": d["industry_risk_factor"],
            "seasonal_factor": d["seasonal_factor"],
            "hist_paid_ratio": d["paid_ratio"],
            "hist_late_ratio": d["late_ratio"],
            "hist_avg_delay_normalized": d["avg_delay_normalized"],
            "paid_ratio": d["paid_ratio"],
            "late_ratio": d["late_ratio"],
            "on_time_ratio": d["on_time_ratio"],
            "credit_score_normalized": d["credit_score_normalized"],
        }.items() if k not in _FIN_ML_EXCLUDED
    }


def _fin_align_v8_features(v8_predictor, X_full: np.ndarray) -> np.ndarray:
    from training.finance_train import (
        BASE_FEATURES, CREDIT_FEATURES, INCOME_FEATURES,
        BEHAVIORAL_FEATURES, ENGINEERED_FEATURES,
    )
    feature_names = getattr(v8_predictor, "feature_names", None) or []
    if not feature_names or X_full.shape[1] == len(feature_names):
        return X_full
    all_features = (
        BASE_FEATURES + CREDIT_FEATURES + INCOME_FEATURES +
        BEHAVIORAL_FEATURES + ENGINEERED_FEATURES
    )
    col_index = {name: i for i, name in enumerate(all_features)}
    indices = [col_index[c] for c in feature_names if c in col_index]
    if len(indices) == len(feature_names):
        return X_full[:, indices]
    return X_full[:, : len(feature_names)]


class FinanceRiskPredictor:
    def __init__(self, ensemble, decision_engine, shap_importance=None):
        self.ensemble        = ensemble
        self.decision_engine = decision_engine
        self.shap_importance = shap_importance or {}

    def predict(self, X_base: np.ndarray) -> dict:
        X_clean = _fin_safe_preprocess(X_base)
        X_eng   = _fin_add_features(X_clean)
        prob    = float(_fin_ensemble_predict_proba(self.ensemble, X_eng)[0])
        result  = self.decision_engine.decide(prob)
        return self.decision_engine.explain(result, self.shap_importance)

    def predict_batch(self, X_base: np.ndarray) -> list:
        X_clean = _fin_safe_preprocess(X_base)
        X_eng   = _fin_add_features(X_clean)
        probs   = _fin_ensemble_predict_proba(self.ensemble, X_eng)
        results = []
        for p in probs:
            r = self.decision_engine.decide(float(p))
            results.append(self.decision_engine.explain(r, self.shap_importance))
        return results


FEATURE_COLUMNS_PATH_FOR_API = os.path.join(
    os.path.dirname(__file__), "models", "finance", "finance_feature_columns.pkl"
)


class _V8FinanceRiskPredictor(FinanceRiskPredictor):
    """
    PATCHED — adds the same column-alignment fix that
    agents/finance/risk_model_handler.py (v4.2) already has, so
    /finance/predict-risk and /finance/predict-risk/batch stop
    crashing with "Feature shape mismatch, expected 38, got 41".
    """

    def __init__(self, v8_predictor, decision_engine, shap_importance=None):
        super().__init__(
            ensemble        = v8_predictor.ensemble,
            decision_engine = decision_engine,
            shap_importance = shap_importance or {},
        )
        self._v8 = v8_predictor
        self._saved_columns = self._load_saved_columns()

    @staticmethod
    def _load_saved_columns():
        try:
            if os.path.exists(FEATURE_COLUMNS_PATH_FOR_API):
                with open(FEATURE_COLUMNS_PATH_FOR_API, "rb") as f:
                    cols = pickle.load(f)
                logger.info(
                    "✅ [predict-risk fix] Loaded %d training feature columns from %s",
                    len(cols), FEATURE_COLUMNS_PATH_FOR_API,
                )
                return cols
        except Exception as e:
            logger.error("❌ [predict-risk fix] Could not load feature columns: %s", e)
        logger.warning(
            "⚠️  [predict-risk fix] finance_feature_columns.pkl not found — "
            "alignment disabled, shape mismatch may still occur."
        )
        return None

    def _align(self, X41):
        """Reindex the 41-col array down to whatever columns the model actually trained on."""
        import numpy as np
        if self._saved_columns is None or X41.shape[1] == len(self._saved_columns):
            return X41
        from training.finance_train import (
            BASE_FEATURES, CREDIT_FEATURES, INCOME_FEATURES,
            BEHAVIORAL_FEATURES, ENGINEERED_FEATURES,
        )
        all_features = (
            BASE_FEATURES + CREDIT_FEATURES + INCOME_FEATURES +
            BEHAVIORAL_FEATURES + ENGINEERED_FEATURES
        )
        col_index = {name: i for i, name in enumerate(all_features)}
        indices = [col_index[c] for c in self._saved_columns if c in col_index]
        if len(indices) != len(self._saved_columns):
            logger.warning(
                "⚠️  [predict-risk fix] Could not align all columns (%d/%d found) — "
                "using X as-is, mismatch may still occur.",
                len(indices), len(self._saved_columns),
            )
            return X41
        return X41[:, indices]

    def predict(self, X_base):
        from training.finance_train import safe_preprocess as _v8_safe_preprocess
        X41   = _api_input_to_v8_features(X_base)
        X41   = self._align(X41)                       # ← THE ACTUAL FIX
        X41   = _v8_safe_preprocess(X41)
        prob  = float(_fin_ensemble_predict_proba(self._v8.ensemble, X41)[0])
        result = self.decision_engine.decide(prob)
        return self.decision_engine.explain(result, self.shap_importance)

    def predict_batch(self, X_base):
        from training.finance_train import safe_preprocess as _v8_safe_preprocess
        results = []
        for row in X_base:
            X41  = _api_input_to_v8_features(row.reshape(1, -1))
            X41  = self._align(X41)                    # ← THE ACTUAL FIX
            X41  = _v8_safe_preprocess(X41)
            prob = float(_fin_ensemble_predict_proba(self._v8.ensemble, X41)[0])
            r    = self.decision_engine.decide(prob)
            results.append(self.decision_engine.explain(r, self.shap_importance))
        return results


def _credit_bucket_v8(credit_norm: float) -> float:
    if credit_norm >= 0.85: return 1.00
    if credit_norm >= 0.70: return 0.75
    if credit_norm >= 0.55: return 0.50
    if credit_norm >= 0.40: return 0.25
    return 0.0


def _api_input_to_v8_features(X_base: np.ndarray) -> np.ndarray:
    r = X_base[0].astype(np.float64)
    _overdue   = float(r[0])
    amount     = float(r[1])
    paid_r     = float(np.clip(r[2], 0, 1))
    late_r     = float(np.clip(r[3], 0, 1))
    age_norm   = float(r[5])
    inv_freq   = float(r[6])
    avg_delay  = float(r[7])
    credit     = float(np.clip(r[8], 0, 1))
    ind_risk   = float(r[9])
    seasonal   = float(r[10])

    years_norm      = float(np.clip(age_norm * 0.6, 0, 1))
    biz_risk        = 0.35
    days_to_due_n   = 0.333
    credit_bucket   = _credit_bucket_v8(credit)
    credit_util     = float(np.clip(late_r * 0.7 + _overdue * 0.15, 0, 1))
    debt_ratio      = float(np.clip(late_r * 0.5, 0, 1))
    credit_x_ind    = float(np.clip((1.0 - credit) * ind_risk, 0, 1))
    income_norm     = 0.10
    inv_to_income   = float(np.clip(amount * 1.5, 0, 1))
    bal_to_income   = float(np.clip(late_r * 0.4, 0, 1))
    hist_paid       = paid_r
    hist_late       = late_r
    hist_paid3      = float(np.clip(paid_r - _overdue * 0.1, 0, 1))
    hist_paid6      = paid_r
    hist_late3      = float(np.clip(late_r + _overdue * 0.05, 0, 1))
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
        amount, age_norm, years_norm, inv_freq,
        ind_risk, seasonal, biz_risk, days_to_due_n,
        credit, credit_bucket, credit_util, debt_ratio, credit_x_ind,
        income_norm, inv_to_income, bal_to_income,
        hist_paid, hist_late, hist_paid3, hist_paid6, hist_late3,
        paid_trend_n, late_trend_n,
        last_paid, last_late,
        hist_max_delay, avg_delay,
        delay_var, pay_volatility,
        late_streak, good_streak,
        freq_trend, velocity,
        days_lp_norm, hist_cnt_norm,
        risk_composite, amount_x_risk, clv_proxy, recovery, behav_score, credit_x_late,
    ]], dtype=np.float64)

    assert X41.shape == (1, 41), f"v8 feature build error: got {X41.shape}"
    return X41


_fin_predictor: Optional[FinanceRiskPredictor] = None


def _load_fin_predictor() -> Optional[FinanceRiskPredictor]:
    global _fin_predictor

    if not os.path.exists(_FIN_MODEL_PATH):
        logger.warning(
            "⚠️ Finance model file not found: %s\n"
            "   Run: python training/finance_train.py",
            _FIN_MODEL_PATH,
        )
        return None

    logger.info("📂 Loading finance model from: %s", _FIN_MODEL_PATH)

    try:
        import importlib
        _train_mod = None
        try:
            _train_mod = importlib.import_module("training.finance_train")
        except Exception as imp_err:
            logger.debug("   Could not import training.finance_train: %s", imp_err)

        class _TrainingUnpickler(pickle.Unpickler):
            def find_class(self, module, name):
                if module in ("__main__", "training.finance_train",
                            "training.finance_train_v3",
                            "training.finance_train_v8"):
                    try:
                        import importlib
                        for mod_name in ("training.finance_train",
                                        "training.finance_train_v8"):
                            try:
                                mod = importlib.import_module(mod_name)
                                if hasattr(mod, name):
                                    return getattr(mod, name)
                            except ImportError:
                                continue
                    except Exception:
                        pass
                return super().find_class(module, name)

        with open(_FIN_MODEL_PATH, "rb") as f:
            saved = _TrainingUnpickler(f).load()

        meta     = saved.get("metadata", {})
        pred_obj = saved.get("predictor")
        version  = meta.get("version", "unknown")

        logger.info("   📋 Model version: %s | trained: %s",
                     version, meta.get("trained_at", "?"))

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

            _fin_predictor = _V8FinanceRiskPredictor(
                v8_predictor    = pred_obj,
                decision_engine = engine,
                shap_importance = shap_imp,
            )
            logger.info(
                "✅ Finance risk model v%s loaded | reject>=%.2f review>=%.2f",
                version, reject, review,
            )
            try:
                import numpy as _np
                _dummy = _np.zeros((1, len(FIN_BASE_FEATURES)), dtype=_np.float64)
                _fin_predictor.predict(_dummy)
                logger.info("✅ [predict-risk fix] Startup self-test predict() succeeded")
            except Exception as self_test_err:
                logger.error(
                    "❌ [predict-risk fix] Startup self-test predict() FAILED — "
                    "model will be unusable until fixed: %s", self_test_err,
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
    leave_id:            Optional[str]   = None
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


class DecisionCreate(BaseModel):
    agent_type:   str
    entity:       str
    entity_id:    str
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
        # ⚠️ FIX: aligned with Node's ABSENCE_TYPES_CLAIMED enum
        # (models/hr.model.js) — the old set here ("sick", "annual",
        # "unpaid", the Arabic value) no longer matches what Node
        # actually accepts and would fail Mongoose validation on
        # every non-"unexcused"/"emergency" submission.
        allowed = {"unexcused", "unexcused_no_permission", "medical", "emergency", "approved_late", "other"}
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
        "version":  "6.5.0",
        "status":   "🟢 operational",
        "database": "Node.js/Express REST API (MongoDB Atlas behind it)",
        "llm":      settings.GEMINI_MODEL,
        "agents":   [
            "HR Leave Approval (ML + Gemini AI)",
            "Salary Review Agent",
            "Incentive Agent",
            "Absence Management Agent",
        ],
        "modules":  [
            "HR", "Leaves", "Salary Reviews", "Incentives",
            "Absence Management", "Audit",
        ],
        "triggers": {
            "scheduler":  "active",
            "db_watcher": "active",
            "webhooks":   "active — /webhooks/*",
        },
        "integrations": {
            "node_api_bridge": "active — ALL HR/Finance data reads/writes go through the Node.js REST API",
        },
        "disabled_pending_node_routes": [
            "/employees (no /hr/employees route in Node yet)",
            "/events/* (no /hr/events route in Node)",
            "/decisions (generic HR decision log — no /hr/decisions route in Node)",
            "/memory/* (no /hr/memory route in Node)",
            "/audit/logs (generic — Node only exposes /hr/audit/:domain/:entity_id)",
        ],
        "docs":   "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["System"])
async def health():
    """
    ⚡ Lightweight health check — pure cache read, < 10ms guaranteed.
    Everything here — db (Node API bridge), redis, scheduler, ml — comes
    from _health_cache, refreshed every 30s by _update_health_cache().
    For real-time check: GET /health/detailed
    For the Node.js API bridge specifically: GET /health/node-api
    """
    t0 = _monotime.perf_counter()

    cached = dict(_health_cache)

    cached_db    = cached.get("db_status",    "initializing")
    cached_redis = cached.get("redis_status", "initializing")
    last_checked = cached.get("last_checked")
    db_latency   = cached.get("db_latency_ms", 0)
    scheduler    = cached.get("scheduler_status", {}) or {}
    ml_info      = cached.get("ml_info", {}) or {}

    overall    = "healthy" if "degraded" not in cached_db else "degraded"
    latency_ms = int((_monotime.perf_counter() - t0) * 1000)

    return {
        "status":          overall,
        "version":         "6.5.0",
        "database":        "Node.js/Express REST API",
        "db_status":       cached_db,
        "db_latency_ms":   db_latency,
        "redis_status":    cached_redis,
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
        "health_cache": {
            "last_checked": last_checked,
            "interval_sec": HEALTH_PING_INTERVAL_SEC,
            "latency_ms":   latency_ms,
        },
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

@app.get("/health/detailed", tags=["System"])
async def health_detailed():
    """🔍 Full system health check — includes Node API bridge ping, ML
    model, scheduler status. There is no direct MongoDB connection left
    in this service, so "db_status" here reflects the Node.js API's
    reachability (same dependency that every route in this file relies
    on for reads/writes)."""
    scheduler  = get_scheduler_status()
    ml_handler = get_model_handler()
    ml_info    = ml_handler.get_info()

    db_status = "healthy"
    try:
        client = get_node_api_client()
        ping_result = await client.ping(timeout_sec=3.0)
        if not ping_result.get("reachable"):
            db_status = f"degraded: {ping_result.get('error', 'unreachable')}"
    except Exception as e:
        db_status = f"degraded: {e}"

    redis_status = "healthy" if await get_cache_manager().ping() else "degraded: unreachable (fallback active)"

    overall = "healthy" if db_status == "healthy" else "degraded"
    return {
        "status":          overall,
        "version":         "6.5.0",
        "database":        "Node.js/Express REST API",
        "db_status":       db_status,
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
        "cache": {"redis": redis_status},
        "timestamp":       datetime.utcnow().isoformat() + "Z",
    }


@app.get("/health/node-api", tags=["System"])
async def health_node_api():
    """
    🔌 v6.4 — Node.js API Bridge health check.
    Reports whether the Node.js/Express HR+Finance REST API
    (NODE_API_BASE_URL) is currently reachable, plus the AI Agent's
    circuit-breaker state for it. This is now this service's ONLY data
    dependency — there is no MongoDB fallback.

    - reachable: false + circuit not open  -> transient, or NODE_API_BASE_URL
      is misconfigured. Check NODE_API_BASE_URL and that the Node.js
      process is actually running on that host/port.
    - circuit.open: true -> the bridge has seen NODE_API_CB_FAILURE_THRESHOLD
      consecutive failures and is failing fast for NODE_API_CB_COOLDOWN_SEC
      to avoid piling up latency against a dead backend. It will
      automatically retry after the cooldown.
    """
    client = get_node_api_client()
    ping_result = await client.ping()
    circuit = client.circuit_status

    overall = "healthy"
    if circuit.get("open"):
        overall = "degraded: circuit breaker open"
    elif not ping_result.get("reachable"):
        overall = "degraded: unreachable"

    return {
        "status":        overall,
        "base_url":      os.getenv("NODE_API_BASE_URL", "http://localhost:5005/v1"),
        "reachable":     ping_result.get("reachable"),
        "latency_ms":    ping_result.get("latency_ms"),
        "error":         ping_result.get("error"),
        "circuit_breaker": circuit,
        "tools_registered": len(NODE_API_TOOLS),
        "timestamp":     datetime.utcnow().isoformat() + "Z",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Trigger Engine
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/trigger/run-now/{job_name}", tags=["Trigger Engine"])
async def trigger_run_now(job_name: str):
    jobs = {
        "leaves":           job_scan_pending_leaves,
        "events":           job_process_event_queue,
        "salary-reviews":   job_scan_pending_salary_reviews,
        "incentives":       job_scan_pending_incentives,
        "absences":         job_scan_pending_absences,
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


@app.get("/trigger/events/history", tags=["Trigger Engine"])
async def trigger_events_history(event_type: Optional[str] = None, limit: int = 30):
    history = event_bus.get_history(event_type=event_type, limit=limit)
    return {"count": len(history), "events": history}


# ─────────────────────────────────────────────────────────────────────────────
# Employees
# ─────────────────────────────────────────────────────────────────────────────
# ⚠️ v6.5: DISABLED. There is no /hr/employees route in hr.routes.js today
# (confirmed against the actual route file — only leaves, salary-reviews,
# absence-events, incentive-requests, audit, and balance-audit exist).
# These endpoints now return 503 instead of silently returning empty data
# from the Mock collections, so callers get a clear, honest signal instead
# of a fake "0 employees" response. Re-enable once GET /hr/employees(/:id)
# exists on the Node side — wire it into NodeHRProxy the same way
# get_leaves()/get_salary_reviews() etc. are wired, then restore these two
# routes to call it.

_EMPLOYEES_DISABLED_DETAIL = (
    "Employees endpoint is disabled: there is no /hr/employees route in "
    "the Node.js API yet (hr.routes.js only defines leaves, "
    "salary-reviews, absence-events, incentive-requests, audit, and "
    "balance-audit). Add GET /hr/employees(/:id) to hr.routes.js + "
    "hr.controller.js, wire it into core/node_hr_proxy.py, then this "
    "route can be re-enabled."
)


@app.get("/employees", tags=["HR - Employees"])
async def list_employees(active_only: bool = True, limit: int = 100, skip: int = 0):
    raise HTTPException(status_code=503, detail=_EMPLOYEES_DISABLED_DETAIL)


@app.get("/employees/{employee_id}", tags=["HR - Employees"])
async def get_employee_by_id(employee_id: str):
    raise HTTPException(status_code=503, detail=_EMPLOYEES_DISABLED_DETAIL)


@app.get("/employees/{employee_id}/leaves", tags=["HR - Leaves"])
async def employee_leave_history(employee_id: str):
    hr_db  = get_hr_db()
    leaves = await hr_db.get_employee_leaves(employee_id)
    return {"employee_id": employee_id, "count": len(leaves), "leaves": leaves}


@app.get("/employees/{employee_id}/balance-history", tags=["HR - Employees"])
async def get_employee_balance_history(employee_id: str, limit: int = 20):
    hr_db   = get_hr_db()
    history = await hr_db.get_balance_history(employee_id, limit=limit)
    return {
        "employee_id":   employee_id,
        "history_count": len(history),
        "history":       history,
        "note": (
            "No history yet — balance_audit_log will populate after next leave decision"
            if not history else None
        ),
    }


@app.get("/employees/{employee_id}/salary-reviews", tags=["HR - Employees"])
async def employee_salary_history(employee_id: str):
    """⚠️ v6.5: uses NodeHRProxy.get_employee_salary_reviews() — there is
    no /hr/salary-reviews/employee/:id route in Node, so this fetches
    GET /hr/salary-reviews and filters by employee_id client-side. See
    node_hr_proxy.py docstring for the tradeoffs (N+1-ish, capped scan)."""
    hr_db   = get_hr_db()
    reviews = await hr_db.get_employee_salary_reviews(employee_id)
    return {"employee_id": employee_id, "count": len(reviews), "reviews": reviews}


@app.get("/employees/{employee_id}/incentives", tags=["HR - Employees"])
async def employee_incentive_history(employee_id: str):
    """⚠️ v6.5: uses NodeHRProxy.get_employee_incentives() — same
    client-side-filter caveat as salary-reviews above (no
    /hr/incentive-requests/employee/:id route in Node yet)."""
    hr_db      = get_hr_db()
    incentives = await hr_db.get_employee_incentives(employee_id)
    total_approved = sum(
        float(i.get("approved_amount_egp", 0) or 0)
        for i in incentives if i.get("status") == "approved"
    )
    return {
        "employee_id":        employee_id,
        "count":              len(incentives),
        "total_approved_egp": total_approved,
        "incentives":         incentives,
    }


@app.get("/employees/{employee_id}/absences", tags=["HR - Employees"])
async def employee_absence_history(employee_id: str, limit: int = 50):
    hr_db    = get_hr_db()
    absences = await hr_db.get_employee_absences(employee_id, limit=limit)
    unexcused_total = sum(
        1 for a in absences
        if a.get("absence_type_claimed") == "unexcused"
        and a.get("status") not in ("pending", "cancelled")
    )
    return {
        "employee_id":     employee_id,
        "count":           len(absences),
        "unexcused_total": unexcused_total,
        "absences":        absences,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Leaves — Helpers
# ─────────────────────────────────────────────────────────────────────────────

async def poll_leave_decision(leave_id: str, timeout: int = 30) -> dict:
    """Polls the Node.js API until leave status changes from pending/in_progress."""
    hr_db    = get_hr_db()
    start    = asyncio.get_event_loop().time()
    interval = 0.5

    while True:
        leave_status = await hr_db.get_leave_status(leave_id)
        if leave_status in ("approved", "rejected", "escalated"):
            leave = await hr_db.get_leave(leave_id)
            return {
                "leave_id": leave_id,
                "decision": leave_status,
                "status":   leave_status,
                "leave":    leave,
                "message":  f"✅ Decision ready: {leave_status}",
            }

        elapsed = asyncio.get_event_loop().time() - start
        if elapsed > timeout:
            leave = await hr_db.get_leave(leave_id)
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
    entity_id: str,
    terminal_statuses: set,
    timeout: int = 30,
) -> dict:
    """Generic async poll helper for salary/incentive/absence."""
    start    = asyncio.get_event_loop().time()
    interval = 0.5

    while True:
        record = await fetch_fn(entity_id)
        if record and record.get("status") in terminal_statuses:
            return record

        if asyncio.get_event_loop().time() - start > timeout:
            return record or {}

        await asyncio.sleep(interval)
        interval = min(interval + 0.5, 1.0)


# ─────────────────────────────────────────────────────────────────────────────
# Leaves — Submit (Sync)  *** v6.1 FIX B1: Direct Workflow ***
# ─────────────────────────────────────────────────────────────────────────────

async def _finalize_leave_submission_bg(leave_id: str, payload: dict) -> None:
    """
    v6.3 fix: _create_mongo_event() used to be awaited inside the route,
    as a SECOND blocking round-trip before the 202 could go out — even
    though nothing reads it back before the workflow runs. It's
    audit/history-only, so it now happens here, after the response.
    v6.5: writes go through hr_db.write_hr_audit() (POST /hr/audit) —
    there's no generic /hr/events route in Node, so the event-log
    concept is folded into the same HR audit trail Node already exposes.
    """
    event_id = None
    try:
        event_id = await _log_hr_event(
            event_type="leave_requested",
            entity="leaves",
            entity_id=leave_id,
            payload={
                "leave_id":      leave_id,
                "employee_id":   payload.get("employee_id"),
                "employee_name": payload.get("employee_name") or "",
                "leave_days":    payload.get("requested_days"),
                "leave_type":    payload.get("leave_type"),
                "leave_balance": payload.get("leave_balance"),
                "reason":        payload.get("reason"),
                "source":        "async_bg_v6.5",
            },
        )
    except Exception as e:
        logger.warning("⚠️ [leave-bg] event log write failed for #%s: %s", leave_id, e)

    await _run_leave_workflow_bg(leave_id, event_id, payload)


@app.post("/leaves/submit", status_code=status.HTTP_202_ACCEPTED, tags=["HR - Leaves"])
async def submit_leave_sync(body: LeaveApprovalRequest, background_tasks: BackgroundTasks):
    """
    🧠 Submit leave request — AI processed in background (v6.3).
    Returns 202 Accepted immediately (< 200ms target).
    v6.5: create_leave_request() now routes through NodeHRProxy
    (POST /hr/leaves) instead of a direct Motor insert.
    Poll: GET /leaves/{leave_id}/decision
    """
    hr_db = get_hr_db()

    leave_data = body.dict()
    leave_data["leave_days"] = leave_data.pop("requested_days")
    leave_id = await hr_db.create_leave_request(leave_data)

    logger.info(
        "📋 [submit-v6.5] Leave #%s | employee=%s — queued for background",
        leave_id, body.employee_id,
    )

    # Event-log write + AI workflow both run AFTER the response — client does NOT wait
    background_tasks.add_task(_finalize_leave_submission_bg, leave_id, body.dict())

    return {
        "message":      "Leave request accepted — AI agent will process in background",
        "leave_id":     leave_id,
        "db_status":    "pending",
        "submitted":    True,
        "decision_url": f"/leaves/{leave_id}/decision",
        "note":         "Poll /leaves/{leave_id}/decision to get the AI result",
        "version":      "v6.5-node-api",
    }

# ─────────────────────────────────────────────────────────────────────────────
# Leaves — Async (background)
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/leaves", status_code=status.HTTP_201_CREATED, tags=["HR - Leaves"])
async def submit_leave_async(body: LeaveRequest, background_tasks: BackgroundTasks):
    hr_db      = get_hr_db()
    leave_data = body.dict()
    leave_data["leave_days"] = leave_data.pop("requested_days")
    leave_id   = await hr_db.create_leave_request(leave_data)

    event_id = await _log_hr_event(
        event_type="leave_requested",
        entity="leaves",
        entity_id=leave_id,
        payload={
            "leave_id":    leave_id,
            "employee_id": body.employee_id,
            "leave_days":  body.requested_days,
        },
    )

    background_tasks.add_task(
        _write_hr_audit,
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
        "pipeline":     "EventBus -> Trigger Engine -> Orchestrator -> HR Agent",
        "note":         "Use POST /leaves/submit to get the AI decision immediately",
        "decision_url": f"/leaves/{leave_id}/decision",
    }


@app.post("/leaves/process", status_code=status.HTTP_201_CREATED, tags=["HR - Leaves"])
async def process_leave_with_workflow(body: LeaveApprovalRequest, background_tasks: BackgroundTasks):
    """Alias for /leaves/submit — kept for backward compatibility."""
    return await submit_leave_sync(body, background_tasks)


@app.get("/leaves/pending", tags=["HR - Leaves"])
async def list_pending_leaves():
    hr_db  = get_hr_db()
    leaves = await hr_db.get_pending_leaves()
    return {"count": len(leaves), "leaves": leaves}


@app.get("/leaves/{leave_id}", tags=["HR - Leaves"])
async def get_leave_by_id(leave_id: str):
    hr_db = get_hr_db()
    leave = await hr_db.get_leave(leave_id)
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
    return leave


@app.get("/leaves/{leave_id}/decision", tags=["HR - Leaves"])
async def get_leave_decision(leave_id: str):
    """Get AI decision — triggers on-demand if still pending."""
    hr_db = get_hr_db()
    leave = await hr_db.get_leave(leave_id)
    if not leave:
        raise HTTPException(status_code=404, detail=f"Leave #{leave_id} not found")

    current_status = leave.get("status")
    if current_status in ("approved", "rejected", "escalated"):
        return {"leave_id": leave_id, "status": current_status, "leave": leave}

    if current_status == "pending":
        logger.info("🔄 Leave #%s is pending — triggering event queue on-demand", leave_id)
        try:
            event_id = await _log_hr_event(
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
async def get_leave_decision_audit(leave_id: str):
    """📋 Complete Decision Audit Trail."""
    hr_db = get_hr_db()
    leave = await hr_db.get_leave(leave_id)
    if not leave:
        raise HTTPException(status_code=404, detail="Leave not found")

    audit_trail     = await hr_db.get_hr_domain_audit("leave", leave_id)
    balance_history = await hr_db.get_balance_history(leave.get("employee_id"), limit=10)

    return {
        "leave_id":        leave_id,
        "current_status":  leave.get("status"),
        "employee_name":   leave.get("employee_name"),
        "leave_days":      leave.get("leave_days"),
        "audit_trail":     audit_trail,
        "balance_history": balance_history,
    }


@app.patch("/leaves/{leave_id}/status", tags=["HR - Leaves"])
async def update_leave(leave_id: str, body: LeaveStatusUpdate, background_tasks: BackgroundTasks):
    hr_db   = get_hr_db()
    leave   = await hr_db.get_leave(leave_id)
    if not leave:
        raise HTTPException(status_code=404, detail="Leave not found")
    updated = await hr_db.update_leave_status(leave_id, body.status, notes=body.notes)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update leave status")
    background_tasks.add_task(
        _write_hr_audit,
        action       = f"leave_{body.status}",
        entity       = "leaves",
        entity_id    = leave_id,
        performed_by = "hr_agent",
        details      = body.notes,
    )
    return {"leave_id": leave_id, "new_status": body.status, "updated": True}


# ─────────────────────────────────────────────────────────────────────────────
# Terminal status sets
# ─────────────────────────────────────────────────────────────────────────────

_SALARY_TERMINAL    = {"approved", "escalated", "deferred", "rejected"}
_INCENTIVE_TERMINAL = {"approved", "rejected", "partial", "escalated", "escalated_ceo"}
_ABSENCE_TERMINAL   = {
    "recorded", "warned_written", "warned_formal",
    "deducted", "deducted_double", "escalated",
    "suspension_review", "termination_review",
}


# ─────────────────────────────────────────────────────────────────────────────
# Salary Reviews  *** v6.1 FIX B1: Direct Workflow ***
# ─────────────────────────────────────────────────────────────────────────────

async def _run_salary_workflow_bg(review_id: str, event_id: str, payload: dict) -> None:
    """Background task: runs SalaryReviewWorkflow and persists the result."""
    
    # ✅ Idempotency guard — منع double run
    hr_db = get_hr_db()
    current = await hr_db.get_salary_review(review_id)
    if current and current.get("status") in _SALARY_TERMINAL:
        logger.info(
            "⏭️ [salary-bg] Review #%s already terminal (%s) — skipping duplicate run",
            review_id, current.get("status"),
        )
        return

    try:
        from workflows.hr.leave_approval_workflow import SalaryReviewWorkflow
        workflow = SalaryReviewWorkflow()
        workflow_payload = {**payload, "review_id": review_id}
        result   = await workflow.async_run(workflow_payload)
        decision = result.get("decision", "unknown")
        logger.info("✅ [salary-bg] Review #%s -> %s", review_id, decision)
    except Exception as e:
        logger.error("❌ [salary-bg] Workflow failed for review #%s: %s", review_id, e)
        decision = "processing"

    await _write_hr_audit(
        action       = f"salary_review_submit_{decision}",
        entity       = "salary_reviews",
        entity_id    = review_id,
        performed_by = "bg_workflow_v6.5",
        details      = f"event_id={event_id} | decision={decision}",
    )


async def _finalize_salary_submission_bg(review_id: str, payload: dict) -> None:
    """v6.5: event-log write goes through hr_db.write_hr_audit() — no
    generic /hr/events route in Node."""
    event_id = None
    try:
        event_id = await _log_hr_event(
            event_type="salary_review",
            entity="salary_reviews",
            entity_id=review_id,
            payload={**payload, "review_id": review_id, "source": "async_bg_v6.5"},
        )
    except Exception as e:
        logger.warning("⚠️ [salary-bg] event log write failed for #%s: %s", review_id, e)

    await _run_salary_workflow_bg(review_id, event_id, payload)


@app.post("/salary-reviews/submit", status_code=status.HTTP_202_ACCEPTED, tags=["HR - Salary Reviews"])
async def submit_salary_review(body: SalaryReviewRequest, background_tasks: BackgroundTasks):
    """💰 Submit Salary Review — accepted instantly, AI processes in background.
    v6.5: create_salary_review() routes through NodeHRProxy (POST /hr/salary-reviews)."""
    hr_db     = get_hr_db()
    review_id = await hr_db.create_salary_review(body.dict())

    logger.info(
        "💰 [salary-submit] Review #%s | employee=%s — queued for background",
        review_id, body.employee_id,
    )

    background_tasks.add_task(_finalize_salary_submission_bg, review_id, body.dict())

    return {
        "message":      "Salary review accepted — AI agent will process in background",
        "review_id":    review_id,
        "db_status":    "pending",
        "submitted":    True,
        "decision_url": f"/salary-reviews/{review_id}/decision",
        "explain_url":  f"/salary-reviews/{review_id}/explain",
        "note":         "Poll /salary-reviews/{review_id}/decision to get the AI result",
    }


@app.get("/salary-reviews/pending", tags=["HR - Salary Reviews"])
async def list_pending_salary_reviews():
    hr_db   = get_hr_db()
    reviews = await hr_db.get_pending_salary_reviews()
    return {"count": len(reviews), "reviews": reviews}


@app.get("/salary-reviews/{review_id}", tags=["HR - Salary Reviews"])
async def get_salary_review_by_id(review_id: str):
    hr_db  = get_hr_db()
    review = await hr_db.get_salary_review(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Salary review not found")
    return review

@app.get("/salary-reviews/{review_id}/decision", tags=["HR - Salary Reviews"])
async def get_salary_review_decision(review_id: str):
    hr_db  = get_hr_db()
    review = await hr_db.get_salary_review(review_id)
    if not review:
        raise HTTPException(status_code=404, detail=f"Salary review #{review_id} not found")

    # ✅ Already terminal — return immediately
    if review.get("status") in _SALARY_TERMINAL:
        return {
            "review_id": review_id,
            "decision":  review.get("ai_decision"),
            "status":    review.get("status"),
            "review":    review,
        }

    if review.get("status") == "pending":
        # ✅ FIX 2a: زوّد الانتظار لـ 45 ثانية (Gemini calls بتاخد 15-30s)
        logger.info("⏳ [on-demand] Salary review #%s — waiting up to 45s for background workflow...", review_id)
        for i in range(45):
            await asyncio.sleep(1)
            review = await hr_db.get_salary_review(review_id)
            if review.get("status") in _SALARY_TERMINAL:
                logger.info(
                    "✅ [on-demand] Review #%s resolved after %ds: %s",
                    review_id, i + 1, review.get("status"),
                )
                break

        # ✅ FIX 2b: بس لو فضل pending بعد 45 ثانية — شغّل on-demand
        # (مش قبل — لأن الـ background workflow غالبًا لسه شغال)
        if review.get("status") not in _SALARY_TERMINAL:
            logger.warning(
                "⚠️ [on-demand] Review #%s still pending after 45s — "
                "background workflow may have failed, running on-demand",
                review_id,
            )
            try:
                background_payload = {**review, "review_id": review_id}
                await _run_salary_workflow_bg(review_id, None, background_payload)
            except Exception as e:
                logger.error("❌ On-demand salary workflow failed for #%s: %s", review_id, e)

        review = await hr_db.get_salary_review(review_id)
        return {
            "review_id": review_id,
            "decision":  review.get("ai_decision"),
            "status":    review.get("status"),
            "review":    review,
        }

    return {
        "review_id": review_id,
        "status":    review.get("status"),
        "review":    review,
    }

@app.get("/salary-reviews/{review_id}/audit", tags=["HR - Salary Reviews"])
async def get_salary_review_audit(review_id: str):
    hr_db  = get_hr_db()
    review = await hr_db.get_salary_review(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Salary review not found")
    audit = await hr_db.get_hr_domain_audit("salary", review_id)
    return {
        "review_id":      review_id,
        "current_status": review.get("status"),
        "employee_name":  review.get("employee_name"),
        "ai_decision":    review.get("ai_decision"),
        "confidence":     review.get("confidence_score"),
        "audit_trail":    audit,
    }


@app.get("/salary-reviews/{review_id}/explain", tags=["HR - Salary Reviews"])
async def explain_salary_decision(review_id: str):
    """🧠 Explainability API — Full decision breakdown for a salary review."""
    from agents.hr.salary_decision_engine import (
        get_salary_decision_engine,
        SalaryDecisionInput,
        SalaryExplainabilityBuilder,
    )

    hr_db  = get_hr_db()
    review = await hr_db.get_salary_review(review_id)
    if not review:
        raise HTTPException(status_code=404, detail=f"Salary review #{review_id} not found")

    engine      = get_salary_decision_engine()
    inp         = SalaryDecisionInput.from_dict(review)
    result      = engine.decide(review, request_id=f"explain_{review_id}")
    explanation = SalaryExplainabilityBuilder.build(result, inp)

    return {
        "review_id":       review_id,
        "employee_name":   review.get("employee_name"),
        "stored_decision": review.get("ai_decision"),
        "engine_decision": result.decision,
        "decisions_match": review.get("ai_decision") == result.decision,
        "explanation":     explanation,
        "raw_score":       result.weighted_score,
        "score_breakdown": result.score_breakdown.to_dict() if result.score_breakdown else {},
    }


@app.get("/salary-reviews/decision-engine/thresholds", tags=["HR - Salary Reviews"])
async def get_decision_engine_thresholds():
    from agents.hr.salary_decision_engine import (
        SCORE_APPROVE, SCORE_ESCALATE, SCORE_DEFER,
        WEIGHT_PERFORMANCE, WEIGHT_KPI, WEIGHT_MARKET, WEIGHT_TENURE,
        PERF_REJECT_FLOOR, PERF_DEFER_FLOOR,
        LEVEL_INCREMENT_CAPS,
    )
    return {
        "version": "v6.5",
        "description": "Priority-based multi-factor salary decision engine",
        "priority_rules": {
            "P0": {"trigger": "is_on_pip = true",           "decision": "reject",               "confidence": "0.97"},
            "P1": {"trigger": f"performance_score < {PERF_REJECT_FLOOR:.0%}", "decision": "reject", "confidence": "0.93"},
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
            f">= {SCORE_APPROVE:.2f}":   "approve_increment",
            f">= {SCORE_ESCALATE:.2f}":  "escalate_to_director",
            f">= {SCORE_DEFER:.2f}":     "defer",
            f"< {SCORE_DEFER:.2f}":      "reject",
        },
        "performance_floors": {
            "reject_floor": f"< {PERF_REJECT_FLOOR:.0%} -> always reject",
            "defer_floor":  f"< {PERF_DEFER_FLOOR:.0%} -> never approve, best is defer",
        },
        "level_increment_caps": LEVEL_INCREMENT_CAPS,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Incentive Requests  *** v6.1 FIX B1: Direct Workflow ***
# ─────────────────────────────────────────────────────────────────────────────

async def _run_incentive_workflow_bg(incentive_id: str, event_id: str, payload: dict) -> None:
    """Background task: runs IncentiveWorkflow and persists the result."""
    
    hr_db = get_hr_db()
    current = await hr_db.get_incentive_request(incentive_id)
    if current and current.get("status") in _INCENTIVE_TERMINAL:
        logger.info("⏭️ [incentive-bg] Incentive #%s already terminal — skipping", incentive_id)
        return

    try:
        from workflows.hr.leave_approval_workflow import IncentiveWorkflow
        workflow = IncentiveWorkflow()
        workflow_payload = {**payload, "incentive_id": incentive_id}
        result   = await workflow.async_run(workflow_payload)
        decision = result.get("decision", "unknown")
        logger.info("✅ [incentive-bg] #%s -> %s", incentive_id, decision)
    except Exception as e:
        logger.error("❌ [incentive-bg] Workflow failed for #%s: %s", incentive_id, e)
        decision = "processing"

    await _write_hr_audit(
        action       = f"incentive_submit_{decision}",
        entity       = "incentive_requests",
        entity_id    = incentive_id,
        performed_by = "bg_workflow_v6.5",
        details      = f"type={payload.get('incentive_type', '')} | decision={decision} | event_id={event_id}",
    )


async def _run_leave_workflow_bg(leave_id: str, event_id: str, payload: dict) -> None:
    """
    Background task: LeaveApprovalWorkflow — runs after 202 Accepted returns.
    Same pattern as _run_salary_workflow_bg.
    """

    hr_db = get_hr_db()
    current = await hr_db.get_leave(leave_id)
    if current and current.get("status") in {"approved", "rejected", "escalated"}:
        logger.info("⏭️ [leave-bg] Leave #%s already terminal — skipping", leave_id)
        return
    t_start = _monotime.perf_counter()
    try:
        from workflows.hr.leave_approval_workflow import LeaveApprovalWorkflow
        workflow = LeaveApprovalWorkflow()
        workflow_payload = {**payload, "leave_id": leave_id}
        result   = await workflow.async_run(workflow_payload)
        decision = result.get("decision", "unknown")
        latency_ms = int((_monotime.perf_counter() - t_start) * 1000)
        logger.info("✅ [leave-bg] Leave #%s -> %s | latency=%dms", leave_id, decision, latency_ms)
    except Exception as e:
        logger.error("❌ [leave-bg] Workflow failed for #%s: %s", leave_id, e)
        decision   = "processing"
        latency_ms = 0

    await _write_hr_audit(
        action       = f"leave_submit_{decision}",
        entity       = "leaves",
        entity_id    = leave_id,
        performed_by = "bg_workflow_v6.5",
        details      = f"decision={decision} | event_id={event_id} | latency_ms={latency_ms}",
    )


async def _finalize_incentive_submission_bg(incentive_id: str, payload: dict) -> None:
    """v6.5: event-log write goes through hr_db.write_hr_audit()."""
    event_id = None
    try:
        event_id = await _log_hr_event(
            event_type="incentive_request",
            entity="incentive_requests",
            entity_id=incentive_id,
            payload={**payload, "incentive_id": incentive_id, "source": "async_bg_v6.5"},
        )
    except Exception as e:
        logger.warning("⚠️ [incentive-bg] event log write failed for #%s: %s", incentive_id, e)

    await _run_incentive_workflow_bg(incentive_id, event_id, payload)


@app.post("/incentives/submit", status_code=status.HTTP_202_ACCEPTED, tags=["HR - Incentives"])
async def submit_incentive_request(body: IncentiveRequest, background_tasks: BackgroundTasks):
    """🏆 Submit Incentive Request — accepted instantly, AI processes in background."""
    hr_db        = get_hr_db()
    incentive_id = await hr_db.create_incentive_request(body.dict())

    logger.info(
        "🏆 [incentive-submit] #%s | employee=%s — queued for background",
        incentive_id, body.employee_id,
    )

    background_tasks.add_task(_finalize_incentive_submission_bg, incentive_id, body.dict())

    return {
        "message":        "Incentive request accepted — AI agent will process in background",
        "incentive_id":   incentive_id,
        "incentive_type": body.incentive_type,
        "db_status":      "pending",
        "submitted":      True,
        "decision_url":   f"/incentives/{incentive_id}/decision",
        "note":           "Poll /incentives/{incentive_id}/decision to get the AI result",
    }


@app.get("/incentives/pending", tags=["HR - Incentives"])
async def list_pending_incentives():
    hr_db    = get_hr_db()
    requests = await hr_db.get_pending_incentive_requests()
    return {"count": len(requests), "incentives": requests}


@app.get("/incentives/{incentive_id}", tags=["HR - Incentives"])
async def get_incentive_by_id(incentive_id: str):
    hr_db = get_hr_db()
    req   = await hr_db.get_incentive_request(incentive_id)
    if not req:
        raise HTTPException(status_code=404, detail="Incentive request not found")
    return req


@app.get("/incentives/{incentive_id}/decision", tags=["HR - Incentives"])
async def get_incentive_decision(incentive_id: str):
    hr_db = get_hr_db()
    req   = await hr_db.get_incentive_request(incentive_id)
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
            await _log_hr_event(
                event_type="incentive_request",
                entity="incentive_requests",
                entity_id=incentive_id,
                payload={
                    "incentive_id":                   incentive_id,
                    "employee_id":                    str(req.get("employee_id", "")),
                    "incentive_type":                 req.get("incentive_type", "performance_bonus"),
                    "requested_amount_egp":           float(req.get("requested_amount_egp", 0)),
                    "kpi_achievement":                float(req.get("kpi_achievement", 0.80)),
                    "performance_score":              float(req.get("performance_score", 0.75)),
                    "monthly_salary_egp":             float(req.get("monthly_salary_egp", 0)),
                    "is_on_pip":                      bool(req.get("is_on_pip", False)),
                    "incentive_budget_remaining_egp": float(req.get("incentive_budget_remaining_egp", 0)),
                    "source": "on_demand",
                },
            )
            await job_process_event_queue()
        except Exception as e:
            logger.error("❌ On-demand incentive trigger failed for #%s: %s", incentive_id, e)

    req = await hr_db.get_incentive_request(incentive_id)
    return {"incentive_id": incentive_id, "status": req.get("status"), "incentive": req}


@app.get("/incentives/{incentive_id}/audit", tags=["HR - Incentives"])
async def get_incentive_audit(incentive_id: str):
    hr_db = get_hr_db()
    req   = await hr_db.get_incentive_request(incentive_id)
    if not req:
        raise HTTPException(status_code=404, detail="Incentive request not found")
    audit = await hr_db.get_hr_domain_audit("incentive", incentive_id)
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
# Absence Events  *** v6.1 FIX B1: Direct Workflow ***
# ─────────────────────────────────────────────────────────────────────────────

async def _run_absence_workflow_bg(absence_id: str, event_id: str, absence_data: dict) -> None:
    """Background task: runs AbsenceWorkflow and persists the result."""
    try:
        from workflows.hr.leave_approval_workflow import AbsenceWorkflow
        workflow = AbsenceWorkflow()
        workflow_payload = {**absence_data, "absence_id": absence_id}
        result   = await workflow.async_run(workflow_payload)
        decision = result.get("decision", "unknown")
        logger.info("✅ [absence-bg] #%s -> %s", absence_id, decision)
    except Exception as e:
        logger.error("❌ [absence-bg] Workflow failed for #%s: %s", absence_id, e)
        decision = "processing"

    await _write_hr_audit(
        action       = f"absence_submit_{decision}",
        entity       = "absence_events",
        entity_id    = absence_id,
        performed_by = "bg_workflow_v6.5",
        details      = f"type={absence_data.get('absence_type_claimed', '')} | decision={decision} | event_id={event_id}",
    )


async def _finalize_absence_submission_bg(absence_id: str, absence_data: dict) -> None:
    """v6.5: event-log write goes through hr_db.write_hr_audit()."""
    event_id = None
    try:
        event_id = await _log_hr_event(
            event_type="absence_event",
            entity="absence_events",
            entity_id=absence_id,
            payload={**absence_data, "absence_id": absence_id, "source": "async_bg_v6.5"},
        )
    except Exception as e:
        logger.warning("⚠️ [absence-bg] event log write failed for #%s: %s", absence_id, e)

    await _run_absence_workflow_bg(absence_id, event_id, absence_data)


@app.post("/absences/submit", status_code=status.HTTP_202_ACCEPTED, tags=["HR - Absence Management"])
async def submit_absence_event(body: AbsenceEventRequest, background_tasks: BackgroundTasks):
    """🚫 Submit Absence Event — accepted instantly, AI processes in background.
    The live unexcused-count read stays in the hot path on purpose — it
    feeds absence_data, which both the stored document and the AI workflow
    depend on, so it has to resolve before we can create the record.
    v6.5: get_employee_unexcused_count_90d() now derives the count from
    GET /hr/absence-events/employee/:id (via NodeHRProxy) instead of a
    direct Motor aggregate."""
    hr_db = get_hr_db()

    live_unexcused_90d = body.unexcused_count_90d
    try:
        live_count = await hr_db.get_employee_unexcused_count_90d(body.employee_id)
        if live_count > live_unexcused_90d:
            logger.info(
                "📊 Live 90d count (%s) > payload (%s) — using live",
                live_count, live_unexcused_90d,
            )
            live_unexcused_90d = live_count
    except Exception:
        pass

    absence_data = body.dict()
    absence_data["absence_date"]        = str(body.absence_date)
    absence_data["unexcused_count_90d"] = live_unexcused_90d

    absence_id = await hr_db.create_absence_event(absence_data)

    logger.info(
        "🚫 [absence-submit] #%s | employee=%s — queued for background",
        absence_id, body.employee_id,
    )

    background_tasks.add_task(_finalize_absence_submission_bg, absence_id, absence_data)

    return {
        "message":      "Absence event accepted — AI agent will process in background",
        "absence_id":   absence_id,
        "absence_date": str(body.absence_date),
        "absence_type": body.absence_type_claimed,
        "db_status":    "pending",
        "submitted":    True,
        "decision_url": f"/absences/{absence_id}/decision",
        "note":         "Poll /absences/{absence_id}/decision to get the AI result",
    }


@app.get("/absences/pending", tags=["HR - Absence Management"])
async def list_pending_absences():
    hr_db  = get_hr_db()
    events = await hr_db.get_pending_absence_events()
    return {"count": len(events), "absences": events}



@app.get("/absences/{absence_id}", tags=["HR - Absence Management"])
async def get_absence_by_id(absence_id: str):
    hr_db = get_hr_db()
    event = await hr_db.get_absence_event(absence_id)
    if not event:
        raise HTTPException(status_code=404, detail="Absence event not found")
    return event


@app.get("/absences/{absence_id}/decision", tags=["HR - Absence Management"])
async def get_absence_decision(absence_id: str):
    hr_db = get_hr_db()
    event = await hr_db.get_absence_event(absence_id)
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
            await _log_hr_event(
                event_type="absence_event",
                entity="absence_events",
                entity_id=absence_id,
                payload={
                    "absence_id":                   absence_id,
                    "employee_id":                  str(event.get("employee_id", "")),
                    "absence_date":                 str(event.get("absence_date", "")),
                    "absence_type_claimed":         event.get("absence_type_claimed", "unexcused"),
                    "duration_hours":               float(event.get("duration_hours", 8)),
                    "medical_certificate_provided": bool(event.get("medical_certificate_provided", False)),
                    "unexcused_count_90d":          int(event.get("unexcused_count_90d", 0)),
                    "previous_warnings":            event.get("previous_warnings", "none"),
                    "performance_score":            float(event.get("performance_score") or 0.75),
                    "source":                       "on_demand",
                },
            )
            await job_process_event_queue()
        except Exception as e:
            logger.error("❌ On-demand absence trigger failed for #%s: %s", absence_id, e)

    event = await hr_db.get_absence_event(absence_id)
    return {"absence_id": absence_id, "status": event.get("status"), "absence": event}


@app.get("/absences/{absence_id}/audit", tags=["HR - Absence Management"])
async def get_absence_audit(absence_id: str):
    hr_db = get_hr_db()
    event = await hr_db.get_absence_event(absence_id)
    if not event:
        raise HTTPException(status_code=404, detail="Absence event not found")
    audit = await hr_db.get_hr_domain_audit("absence", absence_id)
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
# Events
# ─────────────────────────────────────────────────────────────────────────────
# ⚠️ v6.5: DISABLED. There is no /hr/events or generic /events route in
# Node — hr.routes.js only exposes domain entities (leaves, salary-reviews,
# absence-events, incentive-requests) plus /hr/audit and /hr/balance-audit.
# The old Motor-native "events" collection (pending event-bus queue) has no
# Node equivalent today. Internal event-bus/scheduler processing
# (job_process_event_queue etc.) is untouched and keeps working — only
# these two HTTP introspection endpoints are disabled.

_EVENTS_DISABLED_DETAIL = (
    "Events endpoint is disabled: there is no /hr/events (or generic "
    "/events) route in the Node.js API. The internal event-bus/scheduler "
    "queue has no Node-backed equivalent yet. Add one to hr.routes.js if "
    "you need external visibility into pending events; the trigger "
    "engine itself is unaffected and keeps running "
    "(see /trigger/run-now/{job_name})."
)


@app.get("/events/pending", tags=["System - Events"])
async def list_pending_events(limit: int = 50):
    raise HTTPException(status_code=503, detail=_EVENTS_DISABLED_DETAIL)


@app.post("/events/{event_id}/done", tags=["System - Events"])
async def mark_event_processed(event_id: str, result: str = "success"):
    raise HTTPException(status_code=503, detail=_EVENTS_DISABLED_DETAIL)


# ─────────────────────────────────────────────────────────────────────────────
# AI — Decisions & Memory
# ─────────────────────────────────────────────────────────────────────────────
# ⚠️ v6.5: DISABLED. There is no generic /hr/decisions route (only
# /finance/decisions/:entity_id + /finance/decisions/history, which are
# Finance-specific and already wired via NodeFinanceProxy elsewhere in
# this file), and no /hr/memory route at all in hr.routes.js.

_HR_DECISIONS_DISABLED_DETAIL = (
    "Generic HR decision logging is disabled: there is no /hr/decisions "
    "route in the Node.js API. Finance decisions ARE available via "
    "/finance/decisions/{entity_id} (see FinanceDecisionEngine routes) "
    "— this endpoint was for a separate, generic HR decision log that "
    "has no Node-backed equivalent yet."
)

_HR_MEMORY_DISABLED_DETAIL = (
    "Agent memory endpoint is disabled: there is no /hr/memory route in "
    "the Node.js API (hr.routes.js has no memory concept at all). Add "
    "one to hr.routes.js + hr.controller.js, wire it into "
    "core/node_hr_proxy.py, then re-enable this route."
)


@app.post("/decisions", status_code=status.HTTP_201_CREATED, tags=["AI - Decisions"])
async def record_decision(body: DecisionCreate):
    raise HTTPException(status_code=503, detail=_HR_DECISIONS_DISABLED_DETAIL)


@app.get("/memory/{agent}", tags=["AI - Memory"])
async def get_agent_memory(agent: str):
    raise HTTPException(status_code=503, detail=_HR_MEMORY_DISABLED_DETAIL)


@app.post("/memory/{agent}/{key}", tags=["AI - Memory"])
async def set_agent_memory(agent: str, key: str, value: str):
    raise HTTPException(status_code=503, detail=_HR_MEMORY_DISABLED_DETAIL)


# ─────────────────────────────────────────────────────────────────────────────
# Audit
# ─────────────────────────────────────────────────────────────────────────────
# ⚠️ v6.5: /audit/logs (generic, cross-domain) is DISABLED — Node only
# exposes /hr/audit/:domain/:entity_id (domain+entity scoped, e.g.
# "leave"/"salary"/"absence"/"incentive" + a specific id), not a flat
# "every audit log in the system" listing. Domain-scoped audit is fully
# working via get_hr_domain_audit() (used throughout this file, e.g.
# /leaves/{id}/audit, /salary-reviews/{id}/audit, etc.) — only this
# generic listing is unavailable.
# /audit/leaves now uses hr_db.get_leaves() (GET /hr/leaves) instead of
# the old direct hr_db.leaves.find() Motor cursor.

_AUDIT_LOGS_DISABLED_DETAIL = (
    "Generic cross-domain audit log listing is disabled: the Node.js API "
    "only exposes /hr/audit/:domain/:entity_id (scoped to one domain + "
    "one entity id), not a flat listing of every audit log in the "
    "system. Domain-scoped audit trails are fully available — see "
    "/leaves/{id}/audit, /salary-reviews/{id}/audit, "
    "/incentives/{id}/audit, /absences/{id}/audit."
)


@app.get("/audit/logs", tags=["Audit"])
async def get_audit_logs(limit: int = 100):
    raise HTTPException(status_code=503, detail=_AUDIT_LOGS_DISABLED_DETAIL)


@app.get("/audit/leaves", tags=["Audit"])
async def get_leave_records():
    """v6.5: uses hr_db.get_leaves() (GET /hr/leaves) instead of the old
    direct hr_db.leaves.find() Motor cursor — NodeHRProxy has no raw
    collection access, only the REST-backed get_leaves()."""
    hr_db   = get_hr_db()
    records = await hr_db.get_leaves(limit=200)
    return {"count": len(records), "records": records}


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/dashboard/stats", tags=["Dashboard"])
async def dashboard_stats():
    """
    📊 Reads pre-computed KPIs from hr_db.get_dashboard_kpis() (GET
    /hr/dashboard via NodeHRProxy). No live Mongo aggregation here.

    Fallback: لو الـ KPI مش موجودة أو قديمة، بنحسبها live مرة واحدة.
    """
    hr_db = get_hr_db()
    kpis  = await hr_db.get_dashboard_kpis()

    STALE_THRESHOLD_SEC = 300   # لو أقدم من 5 دقايق، الـ scheduler غالبًا متعطل

    is_stale = True
    if kpis and kpis.get("updated_at"):
        updated_at = kpis["updated_at"]
        if isinstance(updated_at, datetime):
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
            age_sec  = (datetime.now(timezone.utc) - updated_at).total_seconds()
            is_stale = age_sec > STALE_THRESHOLD_SEC
        elif isinstance(updated_at, str):
            # Node API قد يرجع ISO string بدل datetime object
            is_stale = False  # عندنا timestamp من Node، نثق فيه كـ "حي" افتراضيًا

    if kpis and not is_stale:
        updated_at = kpis.get("updated_at")
        return {
            "timestamp": updated_at.isoformat() if isinstance(updated_at, datetime) else str(updated_at),
            "stats":     kpis.get("stats", kpis),
            "_source":   "node_api",
        }

    # ── Fallback: compute live (only on cold-start or scheduler outage) ────
    logger.warning(
        "⚠️ [/dashboard/stats] dashboard_kpis %s — computing live as fallback",
        "missing" if not kpis else "stale",
    )
    from services.kpi_calculator import calculate_dashboard_kpis
    fresh_kpis = await calculate_dashboard_kpis()

    try:
        await hr_db.save_dashboard_kpis(fresh_kpis)
    except Exception as e:
        logger.debug("save_dashboard_kpis (fallback path) failed: %s", e)

    return {
        "timestamp": fresh_kpis["updated_at"].isoformat(),
        "stats":     fresh_kpis["stats"],
        "_source":   "live_fallback",
    }


@app.get("/dashboard/analytics", tags=["Dashboard"])
async def get_dashboard_analytics():
    """v6.5: uses hr_db.get_leaves() (GET /hr/leaves) instead of the old
    direct hr_db.leaves.find() Motor cursor."""
    hr_db   = get_hr_db()
    records = await hr_db.get_leaves(limit=200)

    total    = len(records)
    approved = sum(1 for r in records if r.get("status") == "approved")
    rejected = sum(1 for r in records if r.get("status") == "rejected")
    avg_conf = sum(r.get("confidence_score", 0) for r in records) / total if total > 0 else 0

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

@app.get("/model/info", tags=["AI Model"])
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


@app.get("/model/diagnose", tags=["AI Model"])
async def diagnose_model_confidence(n_samples: int = 100):
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


@app.post("/model/reload", tags=["AI Model"])
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


@app.post("/model/train", tags=["AI Model"])
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
    import subprocess, sys

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
        if result.stdout: logger.info("[Training STDOUT]\n%s", result.stdout[-3000:])
        if result.stderr: logger.warning("[Training STDERR]\n%s", result.stderr[-1000:])

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
# Finance Actions
# ─────────────────────────────────────────────────────────────────────────────

class FinanceActionRequest(BaseModel):
    action:      str           = Field(..., description="Action name, e.g. send_polite_reminder")
    invoice_id:  Optional[str] = None
    customer_id: Optional[str] = None
    amount:      float         = Field(0, ge=0)
    decision:    str           = Field("manual_trigger")
    reason:      str           = Field("Manually triggered via API")


class LegalCaseUpdateRequest(BaseModel):
    status:     str = Field(...)
    note:       str = Field("", max_length=500)
    resolution: str = Field("", max_length=2000)


@app.get("/finance/actions/log", tags=["Finance Actions"])
async def finance_action_log(
    invoice_id:  Optional[str] = None,
    customer_id: Optional[str] = None,
    action_type: Optional[str] = None,
    limit:       int           = 100,
):
    from utils.serialize_utils import serialize_doc
    fin_db = get_finance_db()
    logs   = await fin_db.get_collection_log(
        invoice_id=invoice_id,
        customer_id=customer_id,
        action_type=action_type,
        limit=limit,
    )
    return {"count": len(logs), "logs": serialize_doc(logs)}


@app.get("/finance/actions/log/{invoice_id}", tags=["Finance Actions"])
async def finance_action_log_by_invoice(invoice_id: str):
    from utils.serialize_utils import serialize_doc
    fin_db = get_finance_db()
    logs   = await fin_db.get_collection_log(invoice_id=invoice_id, limit=100)
    return {"invoice_id": invoice_id, "count": len(logs), "logs": serialize_doc(logs)}


@app.get("/finance/legal/cases", tags=["Finance Actions"])
async def finance_legal_cases(
    status:      Optional[str] = None,
    customer_id: Optional[str] = None,
    limit:       int           = 50,
):
    from utils.serialize_utils import serialize_doc
    fin_db = get_finance_db()
    cases  = await fin_db.get_legal_cases(status=status, customer_id=customer_id, limit=limit)
    return {"count": len(cases), "cases": serialize_doc(cases)}


@app.get("/finance/legal/cases/{case_id}", tags=["Finance Actions"])
async def finance_legal_case_detail(case_id: str):
    from utils.serialize_utils import serialize_doc
    fin_db = get_finance_db()
    case   = await fin_db.get_legal_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Legal case {case_id} not found")
    return serialize_doc(case)


@app.post("/finance/legal/cases/{case_id}/update", tags=["Finance Actions"])
async def finance_update_legal_case(case_id: str, body: LegalCaseUpdateRequest):
    from utils.serialize_utils import serialize_doc
    fin_db = get_finance_db()
    ok     = await fin_db.update_legal_case_status(
        case_id=case_id,
        status=body.status,
        note=body.note,
        resolution=body.resolution,
    )
    if not ok:
        raise HTTPException(
            status_code=404,
            detail=f"Legal case {case_id} not found or update failed",
        )
    updated = await fin_db.get_legal_case(case_id)
    return {"updated": True, "case": serialize_doc(updated)}


@app.get("/finance/escalation/{invoice_id}", tags=["Finance Actions"])
async def finance_escalation_status(invoice_id: str):
    from utils.serialize_utils import serialize_doc
    fin_db = get_finance_db()
    result = await fin_db.get_escalation_status(invoice_id)
    return serialize_doc(result)


@app.get("/finance/escalation", tags=["Finance Actions"])
async def finance_active_escalations():
    from utils.serialize_utils import serialize_doc
    fin_db      = get_finance_db()
    escalations = await fin_db.get_active_escalations()
    return {"count": len(escalations), "escalations": serialize_doc(escalations)}


@app.get("/finance/actions/dashboard-data", tags=["Finance Actions"])
async def finance_actions_dashboard_data(days: int = 7):
    """
    Finance dashboard data — layered cache.
    L1: in-memory (< 0.1ms)  TTL=30s
    L2: Redis     (< 5ms)    TTL=30s
    L3: Node.js API (network-bound) fallback only
    Target: < 500ms on L1/L2 hit.
    """
    from utils.serialize_utils import serialize_doc

    t0        = _monotime.perf_counter()
    cache_key = f"finance:dashboard:days={days}"

    # ── L1: In-memory ─────────────────────────────────────────────────────
    mem_hit = _mem_cache_get(_DASHBOARD_MEM_CACHE, cache_key)
    if mem_hit is not None:
        latency_ms = int((_monotime.perf_counter() - t0) * 1000)
        return {**mem_hit, "_cache": "memory", "_latency_ms": latency_ms}

    # ── L2: Redis ─────────────────────────────────────────────────────────
    cache = get_cache_manager()
    try:
        redis_hit = await asyncio.wait_for(cache.get_json(cache_key), timeout=0.5)
        if redis_hit is not None:
            _mem_cache_set(_DASHBOARD_MEM_CACHE, cache_key, redis_hit, DASHBOARD_CACHE_TTL_SEC)
            latency_ms = int((_monotime.perf_counter() - t0) * 1000)
            return {**redis_hit, "_cache": "redis", "_latency_ms": latency_ms}
    except Exception as _re:
        logger.debug("⚠️ [dashboard-data] Redis miss: %s", _re)

    # ── L3: Node.js API (cache miss) ────────────────────────────────────────
    logger.info("📊 [dashboard-data] Cache MISS — querying Node.js API (days=%d)", days)
    fin_db = get_finance_db()
    stats, escalations, legal, recent_log = await asyncio.gather(
        fin_db.get_collection_action_stats(days=days),
        fin_db.get_active_escalations(),
        fin_db.get_legal_cases(limit=20),
        fin_db.get_collection_log(limit=20),
    )
    payload = {
        "period_days":        days,
        "action_stats":       serialize_doc(stats),
        "active_escalations": {"count": len(escalations), "items": serialize_doc(escalations[:10])},
        "legal_cases":        {"count": len(legal),       "items": serialize_doc(legal[:10])},
        "recent_actions":     serialize_doc(recent_log[:10]),
        "timestamp":          datetime.utcnow().isoformat() + "Z",
    }
    _mem_cache_set(_DASHBOARD_MEM_CACHE, cache_key, payload, DASHBOARD_CACHE_TTL_SEC)
    asyncio.create_task(_safe_finance_cache_write(cache, cache_key, payload, DASHBOARD_CACHE_TTL_SEC))
    latency_ms = int((_monotime.perf_counter() - t0) * 1000)
    logger.info("📊 [dashboard-data] Node.js API done | %dms", latency_ms)
    return {**payload, "_cache": "miss", "_latency_ms": latency_ms}


async def _safe_finance_cache_write(cache, key: str, data: dict, ttl: int) -> None:
    """Fire-and-forget Redis write — never blocks the response."""
    try:
        await asyncio.wait_for(cache.set_json(key, data, ttl=ttl), timeout=1.0)
    except Exception as e:
        logger.debug("⚠️ [finance-cache] Redis write skipped: %s", e)


@app.post("/finance/actions/execute", tags=["Finance Actions"])
async def finance_execute_action(body: FinanceActionRequest):
    from actions.finance_actions import FinanceActionExecutor
    from agents.base_agent import generate_request_id
    from utils.serialize_utils import serialize_doc

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
        "result":     serialize_doc(result),
        "timestamp":  datetime.utcnow().isoformat() + "Z",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Finance Risk — API Endpoints
# ─────────────────────────────────────────────────────────────────────────────

class FinanceRiskInput(BaseModel):
    overdue_days_normalized:   float = Field(0.0, ge=0.0, le=1.0)
    amount_normalized:         float = Field(0.0, ge=0.0, le=1.0)
    paid_ratio:                float = Field(1.0, ge=0.0, le=1.0)
    late_ratio:                float = Field(0.0, ge=0.0, le=1.0)
    on_time_ratio:             float = Field(1.0, ge=0.0, le=1.0)
    customer_age_normalized:   float = Field(0.5, ge=0.0, le=1.0)
    invoice_frequency:         float = Field(0.5, ge=0.0, le=1.0)
    avg_delay_normalized:      float = Field(0.0, ge=0.0, le=1.0)
    credit_score_normalized:   float = Field(0.8, ge=0.0, le=1.0)
    industry_risk_factor:      float = Field(0.35, ge=0.0, le=1.0)
    seasonal_factor:           float = Field(0.35, ge=0.0, le=1.0)
    industry:                  Optional[str] = None
    invoice_month:              Optional[int] = Field(None, ge=1, le=12)


class FinanceBatchInput(BaseModel):
    records: List[FinanceRiskInput] = Field(..., min_items=1, max_items=500)


@app.post("/finance/predict-risk", tags=["Finance"])
async def finance_predict_risk(body: FinanceRiskInput):
    import time as _time
    from agents.finance.explainability import get_explainability_engine

    predictor = _get_fin_predictor()
    if predictor is None:
        raise HTTPException(
            status_code=503,
            detail="Finance risk model not loaded. Run: python training/finance_train.py",
        )

    request_id = _make_fin_request_id()

    industry_factor = _INDUSTRY_RISK.get(
        (body.industry or "").lower(), body.industry_risk_factor
    )
    seasonal_factor = _SEASONAL_RISK.get(
        body.invoice_month or 0, body.seasonal_factor
    )

    X = np.array([[
        body.overdue_days_normalized, body.amount_normalized,
        body.paid_ratio, body.late_ratio, body.on_time_ratio,
        body.customer_age_normalized, body.invoice_frequency,
        body.avg_delay_normalized, body.credit_score_normalized,
        industry_factor, seasonal_factor,
    ]])

    result = await asyncio.to_thread(predictor.predict, X)

    # #region agent log
    _agent_debug_log(
        "main.py:finance_predict_risk",
        "predict-risk succeeded",
        {
            "request_id": request_id,
            "risk_score": result.get("risk_score"),
            "decision": result.get("decision"),
        },
        hypothesis_id="H1",
    )
    # #endregion

    t0          = _time.perf_counter()
    explanation = await asyncio.to_thread(
        get_explainability_engine().explain, X, result["risk_score"], result["decision"]
    )
    latency_ms  = int((_time.perf_counter() - t0) * 1000)

    logger.info(
        "💰 [/finance/predict-risk] request_id=%s | risk=%.4f | decision=%s | latency=%dms",
        request_id, result["risk_score"], result["decision"], latency_ms,
    )

    return {
        "decision":          result["decision"],
        "risk_score":        result["risk_score"],
        "confidence":        result["confidence"],
        "reasons":           explanation.reasons,
        "positive_factors":  explanation.positive_factors,
        "negative_factors":  explanation.negative_factors,
        "dominant_factor":   explanation.dominant_factor,
        "summary":           explanation.summary,
        "feature_snapshot":  explanation.feature_snapshot,
        "request_id":        request_id,
        "latency_ms":        latency_ms,
        "model_version":     predictor.decision_engine.to_dict(),
        "thresholds": {
            "reject_above": predictor.decision_engine.reject_threshold,
            "review_above": predictor.decision_engine.review_threshold,
        },
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@app.post("/finance/predict-risk/batch", tags=["Finance"])
async def finance_predict_risk_batch(body: FinanceBatchInput):
    import time as _time
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
    results = await asyncio.to_thread(predictor.predict_batch, X)

    enriched = []
    for i, (res, rec_row) in enumerate(zip(results, X)):
        feat_arr    = rec_row.reshape(1, -1)
        explanation = await asyncio.to_thread(
            explain_engine.explain, feat_arr, res["risk_score"], res["decision"]
        )
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
        "💰 [/finance/predict-risk/batch] count=%d | total_latency=%dms",
        len(enriched), batch_latency_ms,
    )

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

@app.get("/finance/model/info", tags=["Finance"])
def finance_model_info():
    """
    Finance ML model metadata.
    In-memory cache — no disk I/O after first call.
    Target: < 300ms first call / < 1ms cached.
    """
    t0        = _monotime.perf_counter()
    cache_key = "finance_model_info"

    cached = _mem_cache_get(_MODEL_INFO_MEM_CACHE, cache_key)
    if cached is not None:
        return {**cached, "_cache": "memory", "_latency_ms": int((_monotime.perf_counter() - t0) * 1000)}

    if not os.path.exists(_FIN_MODEL_PATH):
        return {"loaded": False, "message": "Model not found. Run: python training/finance_train.py", "path": _FIN_MODEL_PATH}

    try:
        predictor = _get_fin_predictor()
        engine    = predictor.decision_engine if predictor else None
        with open(_FIN_MODEL_PATH, "rb") as f:
            saved = pickle.load(f)
        meta = saved.get("metadata", {})
        info = {
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
        _mem_cache_set(_MODEL_INFO_MEM_CACHE, cache_key, info, MODEL_INFO_CACHE_TTL_SEC)
        return {**info, "_cache": "miss", "_latency_ms": int((_monotime.perf_counter() - t0) * 1000)}
    except Exception as e:
        return {"loaded": False, "error": str(e), "path": _FIN_MODEL_PATH}
        

@app.post("/finance/model/reload", tags=["Finance"])
def finance_model_reload():
    predictor = _load_fin_predictor()
    if predictor is None:
        raise HTTPException(
            status_code=503,
            detail=f"Model not found at {_FIN_MODEL_PATH}. Run training first.",
        )
    return {
        "reloaded":   True,
        "path":       _FIN_MODEL_PATH,
        "thresholds": predictor.decision_engine.to_dict(),
        "timestamp":  datetime.utcnow().isoformat() + "Z",
    }


@app.get("/finance/model/thresholds", tags=["Finance"])
def finance_model_thresholds():
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


# ─────────────────────────────────────────────────────────────────────────────
# v6.4 — Node.js API Bridge Diagnostics
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/node-api/tools", tags=["🔌 Node API Bridge"])
async def list_node_api_tools():
    """List every LangChain tool registered from agents/tools/node_api_tools.py,
    so you can confirm from a browser/curl exactly what the AI Agent can call
    without having to read the source or trigger an actual agent run."""
    return {
        "count": len(NODE_API_TOOLS),
        "base_url": os.getenv("NODE_API_BASE_URL", "http://localhost:5005/v1"),
        "tools": [
            {"name": t.name, "description": (t.description or "").strip().split("\n")[0]}
            for t in NODE_API_TOOLS
        ],
    }


@app.post("/node-api/cache/clear", tags=["🔌 Node API Bridge"])
async def clear_node_api_bridge_cache():
    """Manually bust the Node API bridge's short-TTL read cache. Useful right
    after a write happened on the Node.js side that this cache might still be
    masking (cache TTL defaults to NODE_API_CACHE_TTL_SEC, 20s)."""
    from core.node_api_client import clear_node_api_cache
    n = clear_node_api_cache()
    return {"cleared_entries": n, "timestamp": datetime.utcnow().isoformat() + "Z"}


@app.get("/node-api/tools/{tool_name}/test", tags=["🔌 Node API Bridge"])
async def test_node_api_tool(tool_name: str):
    """Dev-only smoke test: call one Node API bridge tool with its default
    arguments and return the raw result. Lets you verify the Node.js ->
    Python bridge end-to-end from a browser without going through Gemini/
    LangChain planning. NOT authenticated beyond whatever this router
    already requires — do not expose this route outside a trusted network
    in production; consider removing or gating it behind an admin check
    before a public deploy."""
    tool_map = {t.name: t for t in NODE_API_TOOLS}
    tool_obj = tool_map.get(tool_name)
    if not tool_obj:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown tool '{tool_name}'. Available: {sorted(tool_map.keys())}",
        )
    try:
        raw = await tool_obj.ainvoke({})
    except Exception as e:
        # Tools that require an id argument (e.g. get_invoice_by_id) will
        # raise a validation error here since {} omits it — that's expected
        # and still confirms the tool + client wiring is reachable.
        return {
            "tool": tool_name,
            "note": "Called with no arguments — this tool likely requires one; "
                    "this confirms wiring, not a full call.",
            "error": str(e)[:300],
        }
    return {"tool": tool_name, "result": json.loads(raw)}


@app.websocket("/ws/metrics")
async def metrics_websocket(websocket: WebSocket):
    await websocket.accept()
    collector = get_metrics_collector()
    await collector.ws_connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await collector.ws_disconnect(websocket)


# ─────────────────────────────────────────────────────────────────────────────
# Internal Helpers — HR event + audit writers (Node.js API backed)
# ─────────────────────────────────────────────────────────────────────────────
# ⚠️ v6.5: these used to insert directly into MongoDB's "events" and
# "audit_logs" collections via Motor. There is no generic /hr/events
# route in Node, so _log_hr_event() now folds the "event" concept into
# the same /hr/audit trail Node already exposes (POST /hr/audit) —
# it's tagged with a distinct `action` prefix ("event_") so it's still
# distinguishable from ordinary audit entries in the trail, and the
# returned id can still be threaded through to the background workflow
# exactly like the old Mongo-generated event_id was.

async def _log_hr_event(
    event_type: str,
    entity:     str,
    entity_id:  str,
    payload:    dict,
) -> str:
    """Node-backed replacement for the old direct-Mongo _create_mongo_event().
    Writes to POST /hr/audit (the only HR-side write-log endpoint Node
    exposes) with action="event_{event_type}", and returns whatever id
    Node hands back (falls back to entity_id if the controller doesn't
    echo one) so callers can keep threading it through unchanged.

    ⚠️ FIX: the Node-side HRDomainAudit schema requires a "domain"
    field (separate from "entity"/"entity_id"). This call used to omit
    it entirely, which made every single _log_hr_event() call fail
    Mongoose validation with "domain: Path `domain` is required." —
    silently swallowed by the except block below, so the entire HR
    event-log trail was being dropped without any visible error other
    than a WARNING log line. `entity` (e.g. "leaves", "salary_reviews",
    "absence_events", "incentive_requests") is a reasonable domain
    value here — it's already the right granularity and Node's
    /hr/audit/:domain/:entity_id read endpoint expects a domain string
    like "leave"/"salary"/"absence"/"incentive" in the rest of this
    file, so we normalize the plural entity name down to that same
    singular form for consistency with how audit trails are actually
    queried elsewhere (see get_hr_domain_audit() call sites)."""
    hr_db = get_hr_db()

    _entity_to_domain = {
        "leaves":             "leave",
        "salary_reviews":     "salary",
        "absence_events":     "absence",
        "incentive_requests": "incentive",
    }
    domain = _entity_to_domain.get(entity, entity)

    try:
        res = await hr_db.write_hr_audit(
            action=f"event_{event_type}",
            entity=entity,
            domain=domain,
            entity_id=entity_id,
            performed_by=payload.get("source", "system"),
            details=json.dumps(payload, default=str)[:2000],
        )
        if isinstance(res, dict):
            return str(res.get("_id") or res.get("id") or entity_id)
        return entity_id
    except Exception as e:
        logger.warning("⚠️ _log_hr_event failed (event_type=%s, entity_id=%s): %s",
                        event_type, entity_id, e)
        return entity_id


_ENTITY_TO_DOMAIN = {
    "leaves":             "leave",
    "salary_reviews":     "salary",
    "absence_events":     "absence",
    "incentive_requests": "incentive",
}


_ENTITY_TO_DOMAIN = {
    "leaves":             "leave",
    "salary_reviews":     "salary",
    "absence_events":     "absence",
    "incentive_requests": "incentive",
}


async def _write_hr_audit(
    action:       str,
    entity:       str,
    entity_id:    str,
    performed_by: str,
    details:      str,
) -> None:
    """Node-backed replacement for the old direct-Mongo _write_mongo_audit().
    Routes through hr_db.write_hr_audit() → POST /hr/audit.

    ⚠️ FIX: the Node-side HRDomainAudit schema requires a "domain" field
    this call never sent, so every single background-task audit write
    (leave/salary/absence/incentive submit-result logging) was failing
    validation and only surfacing as an ERROR log line, with the audit
    trail entry silently lost."""
    try:
        hr_db = get_hr_db()
        await hr_db.write_hr_audit(
            action=action,
            entity=entity,
            domain=_ENTITY_TO_DOMAIN.get(entity, entity),
            entity_id=entity_id,
            performed_by=performed_by,
            details=details,
        )
    except Exception as e:
        logger.error("_write_hr_audit failed: %s", e)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=9000, reload=True, log_level="info")