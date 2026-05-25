"""
📡 Finance Real-time Events (SSE) — v4.0 (MongoDB/Motor)
=========================================================
File: app/core/finance_realtime.py

v4.0 Changes (Migration: MySQL → MongoDB):
    ✅ _safe_get_finance_dashboard_stats() ← FinanceDB.get_finance_dashboard_stats()
    ✅ _safe_get_cashflow_forecast()       ← FinanceDB.get_cashflow_forecast()
    ✅ _safe_get_overdue_invoices()        ← FinanceDB.get_overdue_invoices()
    ✅ _safe_get_decision_history()        ← FinanceDB.decisions aggregate بدل SQL pivot
    ✅ كل SQL fallback queries اتشالت تماماً
    ✅ كل import لـ core.db / core.finance_db اتشال تماماً
    ✅ invoice_id الآن ObjectId string — serialized بـ default=str

v3.0 Features (unchanged):
    ✅ /realtime/dashboard + /dashboard + /dashboard/stats
    ✅ /decisions/history + /history alias
    ✅ /invoices/overdue + /invoices
    ✅ Thread-safe SSE client management (asyncio.Lock)
    ✅ Redis Pub/Sub support للـ multi-worker
    ✅ Graceful fallback لـ in-memory إذا Redis غير متاح
    ✅ Client heartbeat + auto-cleanup
    ✅ Event buffering (آخر 50 event للـ new connections)
    ✅ /metrics/rebuild endpoint
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

logger = logging.getLogger(__name__)

finance_realtime_router = APIRouter()


# ══════════════════════════════════════════════════════════════════════════════
# 🔌  DB helper
# ══════════════════════════════════════════════════════════════════════════════

def _get_db():
    """Return shared FinanceDB instance (Motor async)."""
    from core.mongo_connect import get_finance_db
    return get_finance_db()


# ── Client Management (Thread-safe) ──────────────────────────────────────────

_clients_lock: asyncio.Lock  = asyncio.Lock()
_clients:      set[asyncio.Queue] = set()
_event_buffer: deque          = deque(maxlen=50)


# ══════════════════════════════════════════════════════════════════════════════
# 🔧  Safe async DB helpers
# ══════════════════════════════════════════════════════════════════════════════

async def _safe_get_finance_dashboard_stats() -> dict:
    """
    يجيب stats من FinanceDB.get_finance_dashboard_stats() (Motor async).
    بدل SQL GROUP BY queries في core.finance_db.
    """
    try:
        db = _get_db()
        return await db.get_finance_dashboard_stats()
    except Exception as e:
        logger.warning("⚠️ get_finance_dashboard_stats() failed: %s", e)

    # Safe empty default
    return {
        "invoices": {
            "total_invoices":     0,
            "paid":               0,
            "overdue":            0,
            "legal":              0,
            "suspended":          0,
            "written_off":        0,
            "payment_plan":       0,
            "disputed":           0,
            "total_amount":       0.0,
            "collected_amount":   0.0,
            "outstanding_amount": 0.0,
        },
        "risk":          {},
        "decisions_30d": [],
        "actions_7d":    [],
        "timestamp":     datetime.now(timezone.utc).isoformat(),
    }


async def _safe_get_cashflow_forecast() -> dict:
    """
    يجيب cashflow forecast من FinanceDB.get_cashflow_forecast() (Motor async).
    بدل SQL GROUP BY DATE(due_date).
    """
    try:
        db = _get_db()
        return await db.get_cashflow_forecast()
    except Exception as e:
        logger.warning("⚠️ get_cashflow_forecast() failed: %s", e)

    return {
        "due_7_days":         0.0,
        "due_30_days":        0.0,
        "overdue_total":      0.0,
        "high_risk_overdue":  0.0,
        "payment_plan_total": 0.0,
    }


async def _safe_get_overdue_invoices(
    limit:  int = 50,
    status: Optional[str] = None,
) -> list:
    """
    يجيب invoices من FinanceDB.get_overdue_invoices() أو get_pending_invoices().
    بدل SQL fallback في core.db.

    لو status محدد وغير overdue → بنفلتر من invoices collection مباشرةً.
    """
    try:
        db = _get_db()

        if status and status != "overdue":
            # فلترة حسب status محدد
            cursor = db.invoices.find(
                {"status": status},
                limit=limit,
            ).sort("due_date", 1)
            docs = await cursor.to_list(limit)
            # serialize ObjectId
            return [_serialize_doc(d) for d in docs]

        # Default: overdue invoices (بتيجي مع overdue_days_calc)
        invoices = await db.get_overdue_invoices(min_days=1, limit=limit)
        return [_serialize_doc(d) for d in invoices]

    except Exception as e:
        logger.warning("⚠️ _safe_get_overdue_invoices() failed: %s", e)

    return []


async def _safe_get_decision_history(days: int = 7) -> list:
    """
    يجيب decision history آخر N يوم للـ charts.

    MongoDB: بنعمل aggregation على finance_decisions collection.
    بدل SQL pivot query في core.finance_db.

    يرجع:
        list of { day, approve, soft, hard, plan, suspend, legal }
    """
    try:
        db     = _get_db()
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        pipeline = [
            {
                "$match": {
                    "created_at": {"$gte": cutoff},
                    "decision":   {"$ne": None},
                }
            },
            {
                "$group": {
                    "_id": {
                        "day":      {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                        "decision": "$decision",
                    },
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"_id.day": 1}},
        ]

        raw = await db.decisions.aggregate(pipeline).to_list(None)

        # Pivot: day → {approve, soft, hard, plan, suspend, legal}
        DECISION_MAP = {
            "safe_to_collect":  "approve",
            "approve":          "approve",
            "invoice_registered": "approve",
            "soft_follow_up":   "soft",
            "hard_follow_up":   "hard",
            "payment_plan":     "plan",
            "suspend_service":  "suspend",
            "legal_escalation": "legal",
            "write_off":        "legal",
        }

        pivot: dict[str, dict] = {}
        for r in raw:
            d   = r["_id"]["day"]
            dec = r["_id"]["decision"]
            cnt = int(r["count"])
            if d not in pivot:
                pivot[d] = {
                    "day":     d,
                    "approve": 0, "soft": 0, "hard": 0,
                    "plan":    0, "suspend": 0, "legal": 0,
                }
            key = DECISION_MAP.get(dec, "approve")
            pivot[d][key] = pivot[d].get(key, 0) + cnt

        # لو في أيام مفيهاش data → نضيف صفوف فاضية عشان الـ chart يكون متكامل
        today = datetime.now(timezone.utc).date()
        for i in range(days):
            day_str = str(today - timedelta(days=days - 1 - i))
            if day_str not in pivot:
                pivot[day_str] = {
                    "day":     day_str,
                    "approve": 0, "soft": 0, "hard": 0,
                    "plan":    0, "suspend": 0, "legal": 0,
                }

        return sorted(pivot.values(), key=lambda x: x["day"])

    except Exception as e:
        logger.warning("⚠️ _safe_get_decision_history() failed: %s", e)

    # Empty N-day skeleton
    today = datetime.now(timezone.utc).date()
    return [
        {
            "day":     str(today - timedelta(days=days - 1 - i)),
            "approve": 0, "soft": 0, "hard": 0,
            "plan":    0, "suspend": 0, "legal": 0,
        }
        for i in range(days)
    ]


# ══════════════════════════════════════════════════════════════════════════════
# 🔧  Shared serializer
# ══════════════════════════════════════════════════════════════════════════════

def _serialize_doc(doc: dict) -> dict:
    """Convert ObjectId + datetime → JSON-safe strings (safe for SSE)."""
    from bson import ObjectId
    out = {}
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            out[k] = str(v)
        elif isinstance(v, datetime):
            out[k] = v.isoformat()
        elif isinstance(v, dict):
            out[k] = _serialize_doc(v)
        elif isinstance(v, list):
            out[k] = [
                _serialize_doc(i) if isinstance(i, dict)
                else (str(i) if isinstance(i, ObjectId) else i)
                for i in v
            ]
        else:
            out[k] = v
    return out


# ══════════════════════════════════════════════════════════════════════════════
# 📣  Event Push helpers
# ══════════════════════════════════════════════════════════════════════════════

async def push_finance_event(event_type: str, data: dict) -> None:
    """
    Push event لـ:
        1. كل الـ SSE clients المتصلين (in-memory)
        2. Redis Pub/Sub (إذا متاح) للـ multi-worker
    """
    message = {
        "event": event_type,
        "data":  data,
        "ts":    time.time(),
    }
    _event_buffer.append(message)
    await _broadcast_to_clients(message)
    asyncio.create_task(_redis_publish(event_type, data))


async def _broadcast_to_clients(message: dict) -> None:
    """Broadcast to all connected SSE clients."""
    if not _clients:
        return

    payload = {
        "event": message["event"],
        "data":  json.dumps(message["data"], default=str),
    }

    dead_clients: set = set()
    async with _clients_lock:
        for q in list(_clients):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                logger.warning("⚠️ SSE queue full — dropping slow client")
                dead_clients.add(q)
            except Exception:
                dead_clients.add(q)

    if dead_clients:
        async with _clients_lock:
            _clients.difference_update(dead_clients)
        logger.debug("🧹 Removed %d dead SSE clients", len(dead_clients))


async def _redis_publish(event_type: str, data: dict) -> None:
    """Publish to Redis channel للـ multi-worker support (best-effort)."""
    try:
        import os
        import redis.asyncio as aioredis  # type: ignore
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            return
        r = aioredis.from_url(redis_url, socket_connect_timeout=2)
        channel = f"finance:events:{event_type}"
        await r.publish(channel, json.dumps({"event": event_type, "data": data}, default=str))
        await r.aclose()
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# 📡  SSE Generator
# ══════════════════════════════════════════════════════════════════════════════

async def _sse_generator(
    request:      Request,
    client_queue: asyncio.Queue,
) -> AsyncGenerator[str, None]:
    try:
        # Replay آخر 10 events للـ client الجديد
        for buffered in list(_event_buffer)[-10:]:
            event = buffered["event"]
            data  = json.dumps(buffered["data"], default=str)
            yield f"event: {event}\ndata: {data}\n\n"

        while True:
            if await request.is_disconnected():
                logger.debug("📡 SSE client disconnected")
                break
            try:
                message = await asyncio.wait_for(client_queue.get(), timeout=20.0)
                event   = message["event"]
                data    = message["data"]
                yield f"event: {event}\ndata: {data}\n\n"
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"

    except asyncio.CancelledError:
        logger.debug("📡 SSE connection cancelled")
    except Exception as e:
        logger.debug("📡 SSE generator error: %s", e)
    finally:
        async with _clients_lock:
            _clients.discard(client_queue)
        logger.debug("📡 SSE client cleaned up | total=%d", len(_clients))


# ══════════════════════════════════════════════════════════════════════════════
# 🔗  Shared dashboard builder (async)
# ══════════════════════════════════════════════════════════════════════════════

async def _build_dashboard_response() -> dict:
    """
    يبني الـ dashboard response — async عشان FinanceDB methods كلها async.
    """
    stats, cashflow = await asyncio.gather(
        _safe_get_finance_dashboard_stats(),
        _safe_get_cashflow_forecast(),
        return_exceptions=True,
    )
    # لو gather رجع exception → نستخدم empty dict
    if isinstance(stats, Exception):
        logger.warning("dashboard stats failed: %s", stats)
        stats = {}
    if isinstance(cashflow, Exception):
        logger.warning("cashflow forecast failed: %s", cashflow)
        cashflow = {}

    return {
        "status":    "ok",
        "stats":     stats,
        "cashflow":  cashflow,
        "clients":   len(_clients),
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
    }


# ══════════════════════════════════════════════════════════════════════════════
# 🚀  Endpoints
# ══════════════════════════════════════════════════════════════════════════════

# ── SSE Live Stream ───────────────────────────────────────────────────────────

@finance_realtime_router.get("/live", tags=["📡 Finance - Live"])
async def finance_live_events(request: Request):
    """
    SSE endpoint للـ frontend EventSource.

    Frontend:
        const es = new EventSource('/finance/live');
        es.addEventListener('invoice_processed', (e) => {...});
        es.addEventListener('snapshot', (e) => {...});
    """
    client_queue: asyncio.Queue = asyncio.Queue(maxsize=200)

    async with _clients_lock:
        _clients.add(client_queue)

    await client_queue.put({
        "event": "connected",
        "data":  json.dumps({
            "status":  "ok",
            "clients": len(_clients),
            "message": "Connected to Finance real-time stream (MongoDB v4.0)",
        }),
    })

    logger.info("📡 New SSE client connected | total=%d", len(_clients))

    return StreamingResponse(
        _sse_generator(request, client_queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control":               "no-cache",
            "Connection":                  "keep-alive",
            "X-Accel-Buffering":           "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


# ── Dashboard endpoints ───────────────────────────────────────────────────────

@finance_realtime_router.get("/realtime/dashboard", tags=["📡 Finance - Live"])
async def get_realtime_dashboard():
    """
    /finance/realtime/dashboard — MongoDB async version.
    """
    try:
        return await _build_dashboard_response()
    except Exception as e:
        logger.error("realtime/dashboard failed: %s", e)
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})


@finance_realtime_router.get("/dashboard", tags=["📡 Finance - Live"])
async def get_dashboard_data():
    """
    /finance/dashboard — frontend fallback.
    """
    try:
        return await _build_dashboard_response()
    except Exception as e:
        logger.error("dashboard failed: %s", e)
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})


@finance_realtime_router.get("/dashboard/stats", tags=["📡 Finance - Live"])
async def get_dashboard_stats():
    """
    /finance/dashboard/stats — stats فقط بدون cashflow.
    """
    try:
        stats = await _safe_get_finance_dashboard_stats()
        return {
            "status":    "ok",
            "stats":     stats,
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        }
    except Exception as e:
        logger.error("dashboard/stats failed: %s", e)
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})


# ── Decision History endpoints ────────────────────────────────────────────────

@finance_realtime_router.get("/decisions/history", tags=["📡 Finance - Live"])
async def get_decisions_history(days: int = Query(default=7, ge=1, le=90)):
    """
    /finance/decisions/history?days=7

    يرجع:
        history: list of { day, approve, soft, hard, plan, suspend, legal }
    للـ bar chart في الـ frontend.

    MongoDB: aggregation على finance_decisions بدل SQL pivot.
    """
    try:
        history = await _safe_get_decision_history(days=days)
        return {
            "status":    "ok",
            "days":      days,
            "count":     len(history),
            "history":   history,
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        }
    except Exception as e:
        logger.error("decisions/history failed: %s", e)
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})


@finance_realtime_router.get("/history", tags=["📡 Finance - Live"])
async def get_history_alias(days: int = Query(default=7, ge=1, le=90)):
    """
    /finance/history — alias لـ /finance/decisions/history.
    """
    return await get_decisions_history(days=days)


# ── Invoice endpoints ─────────────────────────────────────────────────────────

@finance_realtime_router.get("/invoices/overdue", tags=["📡 Finance - Live"])
async def get_overdue_invoices_endpoint(limit: int = Query(default=50, ge=1, le=500)):
    """
    /finance/invoices/overdue — يجيب overdue invoices من MongoDB.
    """
    try:
        invoices = await _safe_get_overdue_invoices(limit=limit)
        return {
            "status":    "ok",
            "count":     len(invoices),
            "invoices":  invoices,
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        }
    except Exception as e:
        logger.error("invoices/overdue failed: %s", e)
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})


@finance_realtime_router.get("/invoices", tags=["📡 Finance - Live"])
async def get_invoices_endpoint(
    status: Optional[str] = Query(default=None),
    limit:  int           = Query(default=50, ge=1, le=500),
):
    """
    /finance/invoices?status=overdue&limit=50 — invoices مع filter.
    """
    try:
        invoices = await _safe_get_overdue_invoices(limit=limit, status=status)
        return {
            "status":    "ok",
            "count":     len(invoices),
            "invoices":  invoices,
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        }
    except Exception as e:
        logger.error("invoices failed: %s", e)
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})


# ── Metrics Rebuild ───────────────────────────────────────────────────────────

@finance_realtime_router.post("/metrics/rebuild", tags=["📡 Finance - Live"])
async def force_metrics_rebuild():
    """
    Force immediate metrics snapshot rebuild + broadcast.
    POST /finance/metrics/rebuild
    """
    try:
        from core.metrics_collector import get_metrics_collector
        collector = get_metrics_collector()
        snapshot  = await collector.get_snapshot(force=True)

        await push_finance_event("metrics_rebuilt", {
            "total_invoices":    snapshot.total_invoices,
            "overdue_invoices":  snapshot.overdue_invoices,
            "outstanding_egp":   snapshot.outstanding_egp,
            "collected_egp":     snapshot.collected_egp,
            "ai_decisions_made": snapshot.ai_decisions_made,
            "emails_sent":       snapshot.emails_sent,
            "escalations":       snapshot.escalations,
        })

        return {
            "status":   "rebuilt",
            "snapshot": snapshot.to_dict(),
        }
    except Exception as e:
        logger.error("force_metrics_rebuild failed: %s", e)
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})


# ── Status ────────────────────────────────────────────────────────────────────

@finance_realtime_router.get("/status", tags=["📡 Finance - Live"])
async def realtime_status():
    """Status endpoint للـ monitoring."""
    return {
        "sse_clients": len(_clients),
        "buffer_size": len(_event_buffer),
        "status":      "ok",
        "db_engine":   "mongodb_motor",
        "timestamp":   datetime.now(timezone.utc).isoformat() + "Z",
    }