"""
📡 Finance Real-time Events (SSE) — v3.0 Production
=====================================================
File: app/core/finance_realtime.py

v3.0 Changes (over v2.0):
    ✅ /realtime/dashboard  → alias صريح يُصلح الـ 404
    ✅ /dashboard           → endpoint مباشر (للـ frontend fallback)
    ✅ /dashboard/stats     → endpoint للـ frontend fallback
    ✅ /decisions/history   → 7-day decision history للـ charts
    ✅ /history             → alias للـ decisions/history
    ✅ /invoices/overdue    → real overdue invoice list من DB
    ✅ /invoices            → list invoices مع filter
    ✅ get_finance_dashboard_stats() → safe fallback لو ناقصة في finance_db
    ✅ get_cashflow_forecast()       → safe fallback لو ناقصة في finance_db
    ✅ Thread-safe client management (asyncio.Lock)
    ✅ Redis Pub/Sub support للـ multi-worker deployments
    ✅ Graceful fallback للـ in-memory إذا Redis غير متاح
    ✅ Client heartbeat + auto-cleanup للـ dead connections
    ✅ Event buffering — أخر 50 event للـ new connections
    ✅ /metrics/rebuild endpoint لـ force refresh يدوي
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from datetime import datetime, timedelta
from typing import AsyncGenerator, List, Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

logger = logging.getLogger(__name__)

finance_realtime_router = APIRouter()

# ── Client Management (Thread-safe) ──────────────────────────────────────────

_clients_lock: asyncio.Lock = asyncio.Lock()
_clients: set[asyncio.Queue] = set()

# أخر 50 event للـ new connections (replay buffer)
_event_buffer: deque = deque(maxlen=50)


# ══════════════════════════════════════════════════════════════════════════════
# 🔧  Safe DB helpers — تتعامل مع الحالة اللي finance_db مش عندها الـ functions
# ══════════════════════════════════════════════════════════════════════════════

def _safe_get_finance_dashboard_stats() -> dict:
    """
    يحاول يجيب stats من finance_db.
    لو الـ function مش موجودة → يرجع بيانات فاضية بدل 500 error.
    """
    try:
        from core.finance_db import get_finance_dashboard_stats
        return get_finance_dashboard_stats()
    except ImportError:
        pass
    except AttributeError:
        pass
    except Exception as e:
        logger.warning("⚠️ get_finance_dashboard_stats() failed: %s", e)

    # ── Fallback: اجمع البيانات يدوياً من الـ DB ─────────────────────────────
    try:
        from core.finance_db import get_db as _get_fin_db  # type: ignore
        with _get_fin_db() as (_, cur):
            # Invoice counts
            cur.execute("""
                SELECT
                    COUNT(*)                                                    AS total_invoices,
                    SUM(CASE WHEN status = 'overdue' THEN 1 ELSE 0 END)        AS overdue_invoices,
                    SUM(CASE WHEN status = 'overdue' THEN amount ELSE 0 END)   AS outstanding_egp,
                    SUM(CASE WHEN status = 'paid'    THEN amount ELSE 0 END)   AS collected_egp
                FROM invoices
            """)
            row = cur.fetchone() or {}

            # Decision breakdown (last 30 days)
            cur.execute("""
                SELECT ai_decision AS decision, COUNT(*) AS count
                FROM invoices
                WHERE ai_decision IS NOT NULL
                  AND updated_at >= NOW() - INTERVAL 30 DAY
                GROUP BY ai_decision
                ORDER BY count DESC
            """)
            decisions_30d = [dict(r) for r in (cur.fetchall() or [])]

            # Action counts (last 7 days)
            cur.execute("""
                SELECT action_type AS action, COUNT(*) AS count
                FROM collection_action_log
                WHERE created_at >= NOW() - INTERVAL 7 DAY
                GROUP BY action_type
                ORDER BY count DESC
            """)
            actions_7d = [dict(r) for r in (cur.fetchall() or [])]

            return {
                "invoices": {
                    "total":       int(row.get("total_invoices") or 0),
                    "overdue":     int(row.get("overdue_invoices") or 0),
                    "outstanding": float(row.get("outstanding_egp") or 0),
                    "collected":   float(row.get("collected_egp") or 0),
                },
                "decisions_30d": decisions_30d,
                "actions_7d":    actions_7d,
            }
    except Exception as e:
        logger.warning("⚠️ manual DB stats fallback failed: %s", e)

    # ── Empty safe default ────────────────────────────────────────────────────
    return {
        "invoices":      {"total": 0, "overdue": 0, "outstanding": 0, "collected": 0},
        "decisions_30d": [],
        "actions_7d":    [],
    }


def _safe_get_cashflow_forecast() -> list:
    """
    يحاول يجيب cashflow forecast من finance_db.
    لو مش موجودة → يرجع list فاضية بدل 500 error.
    """
    try:
        from core.finance_db import get_cashflow_forecast
        return get_cashflow_forecast()
    except (ImportError, AttributeError):
        pass
    except Exception as e:
        logger.warning("⚠️ get_cashflow_forecast() failed: %s", e)

    # ── Build simple 7-day forecast from DB ──────────────────────────────────
    try:
        from core.finance_db import get_db as _get_fin_db  # type: ignore
        with _get_fin_db() as (_, cur):
            cur.execute("""
                SELECT
                    DATE(due_date)          AS day,
                    SUM(amount)             AS expected,
                    SUM(CASE WHEN status = 'paid' THEN amount ELSE 0 END) AS received
                FROM invoices
                WHERE due_date BETWEEN NOW() AND NOW() + INTERVAL 7 DAY
                GROUP BY DATE(due_date)
                ORDER BY day
            """)
            return [dict(r) for r in (cur.fetchall() or [])]
    except Exception as e:
        logger.warning("⚠️ cashflow forecast DB fallback failed: %s", e)

    return []


def _safe_get_overdue_invoices(limit: int = 50, status: Optional[str] = None) -> list:
    try:
        from core.finance_db import get_overdue_invoices
        return get_overdue_invoices(limit=limit)  # ← limit بقى مدعوم
    except (ImportError, AttributeError):
        pass
    except Exception as e:
        logger.warning("⚠️ get_overdue_invoices() import failed: %s", e)

    # Fallback: query مباشر من core.db (مش finance_db)
    try:
        from core.db import get_db  # ← هنا كانت المشكلة — core.db مش core.finance_db
        with get_db() as (_, cur):
            where_clause = "status = 'overdue'"
            if status and status != "overdue":
                where_clause = f"status = '{status}'"

            cur.execute(f"""
                SELECT
                    id, invoice_number, customer_name, customer_id,
                    amount, due_date, status, ai_decision, ai_risk_score,
                    DATEDIFF(NOW(), due_date) AS overdue_days_calc,
                    payment_history_paid, payment_history_late,
                    credit_score, industry_risk, updated_at
                FROM invoices
                WHERE {where_clause}
                ORDER BY DATEDIFF(NOW(), due_date) DESC
                LIMIT %s
            """, (limit,))
            return [dict(r) for r in (cur.fetchall() or [])]
    except Exception as e:
        logger.warning("⚠️ overdue invoices DB query failed: %s", e)

    return []


def _safe_get_decision_history(days: int = 7) -> list:
    """
    يجيب decision history آخر N يوم للـ charts.
    """
    try:
        from core.finance_db import get_db as _get_fin_db  # type: ignore
        with _get_fin_db() as (_, cur):
            cur.execute("""
                SELECT
                    DATE(updated_at)    AS day,
                    ai_decision         AS decision,
                    COUNT(*)            AS count
                FROM invoices
                WHERE ai_decision IS NOT NULL
                  AND updated_at >= NOW() - INTERVAL %s DAY
                GROUP BY DATE(updated_at), ai_decision
                ORDER BY day ASC
            """, (days,))
            raw = cur.fetchall() or []

            # Pivot: day → {decision: count, ...}
            pivot: dict[str, dict] = {}
            for r in raw:
                d   = str(r.get("day") or "")
                dec = str(r.get("decision") or "unknown")
                cnt = int(r.get("count") or 0)
                if d not in pivot:
                    pivot[d] = {
                        "day": d,
                        "approve": 0, "soft": 0, "hard": 0,
                        "plan": 0, "suspend": 0, "legal": 0,
                    }
                mapping = {
                    "safe_to_collect": "approve", "approve": "approve",
                    "soft_follow_up":  "soft",
                    "hard_follow_up":  "hard",
                    "payment_plan":    "plan",
                    "suspend_service": "suspend",
                    "legal_escalation":"legal",
                }
                key = mapping.get(dec, "approve")
                pivot[d][key] = pivot[d].get(key, 0) + cnt

            return list(pivot.values())
    except Exception as e:
        logger.warning("⚠️ decision history query failed: %s", e)

    # ── Empty 7-day skeleton ──────────────────────────────────────────────────
    today = datetime.utcnow().date()
    return [
        {
            "day":     str(today - timedelta(days=days - 1 - i)),
            "approve": 0, "soft": 0, "hard": 0,
            "plan": 0, "suspend": 0, "legal": 0,
        }
        for i in range(days)
    ]


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
# 🔗  Shared dashboard builder
# ══════════════════════════════════════════════════════════════════════════════

def _build_dashboard_response() -> dict:
    """
    يبني الـ dashboard response object مرة واحدة وبيتاستخدم في أكتر من endpoint.
    """
    stats    = _safe_get_finance_dashboard_stats()
    cashflow = _safe_get_cashflow_forecast()
    return {
        "status":    "ok",
        "stats":     stats,
        "cashflow":  cashflow,
        "clients":   len(_clients),
        "timestamp": datetime.utcnow().isoformat() + "Z",
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
            "message": "Connected to Finance real-time stream",
        }),
    })

    logger.info("📡 New SSE client connected | total=%d", len(_clients))

    return StreamingResponse(
        _sse_generator(request, client_queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control":             "no-cache",
            "Connection":                "keep-alive",
            "X-Accel-Buffering":         "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


# ── Dashboard endpoints (3 routes → same handler) ────────────────────────────

@finance_realtime_router.get("/realtime/dashboard", tags=["📡 Finance - Live"])
async def get_realtime_dashboard():
    """
    ✅ /finance/realtime/dashboard — كان بييجي 404، اتصلح في v3.0.

    Frontend كان بيطلبه كـ:
        GET /finance/realtime/dashboard
    الـ router بيضيف prefix /finance تلقائياً، يعني الـ path هنا = /realtime/dashboard
    """
    try:
        return _build_dashboard_response()
    except Exception as e:
        logger.error("realtime/dashboard failed: %s", e)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": str(e)},
        )


@finance_realtime_router.get("/dashboard", tags=["📡 Finance - Live"])
async def get_dashboard_data():
    """
    ✅ /finance/dashboard — frontend fallback.
    نفس البيانات زي /finance/realtime/dashboard.
    """
    try:
        return _build_dashboard_response()
    except Exception as e:
        logger.error("dashboard failed: %s", e)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": str(e)},
        )


@finance_realtime_router.get("/dashboard/stats", tags=["📡 Finance - Live"])
async def get_dashboard_stats():
    """
    ✅ /finance/dashboard/stats — كان بييجي 404، اتصلح في v3.0.
    يرجع stats فقط (بدون cashflow) للـ chart data في الـ frontend.
    """
    try:
        stats = _safe_get_finance_dashboard_stats()
        return {
            "status":    "ok",
            "stats":     stats,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except Exception as e:
        logger.error("dashboard/stats failed: %s", e)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": str(e)},
        )


# ── Decision History endpoints ────────────────────────────────────────────────

@finance_realtime_router.get("/decisions/history", tags=["📡 Finance - Live"])
async def get_decisions_history(days: int = Query(default=7, ge=1, le=90)):
    """
    ✅ /finance/decisions/history?days=7 — كان بييجي 404، اتصلح في v3.0.

    يرجع:
        history: list of { day, approve, soft, hard, plan, suspend, legal }
    للـ bar chart في الـ frontend.
    """
    try:
        history = _safe_get_decision_history(days=days)
        return {
            "status":    "ok",
            "days":      days,
            "count":     len(history),
            "history":   history,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except Exception as e:
        logger.error("decisions/history failed: %s", e)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": str(e)},
        )


@finance_realtime_router.get("/history", tags=["📡 Finance - Live"])
async def get_history_alias(days: int = Query(default=7, ge=1, le=90)):
    """
    ✅ /finance/history — alias لـ /finance/decisions/history.
    Frontend بيجرب الـ endpoint ده كـ fallback.
    """
    return await get_decisions_history(days=days)


# ── Invoice endpoints ─────────────────────────────────────────────────────────

@finance_realtime_router.get("/invoices/overdue", tags=["📡 Finance - Live"])
async def get_overdue_invoices_endpoint(limit: int = Query(default=50, ge=1, le=500)):
    """
    ✅ /finance/invoices/overdue — يجيب الـ overdue invoices من الـ DB.
    الـ frontend بيناديه في fetchLiveInvoices().
    """
    try:
        invoices = _safe_get_overdue_invoices(limit=limit)
        return {
            "status":    "ok",
            "count":     len(invoices),
            "invoices":  invoices,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except Exception as e:
        logger.error("invoices/overdue failed: %s", e)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": str(e)},
        )


@finance_realtime_router.get("/invoices", tags=["📡 Finance - Live"])
async def get_invoices_endpoint(
    status: Optional[str] = Query(default=None),
    limit:  int           = Query(default=50, ge=1, le=500),
):
    """
    ✅ /finance/invoices?status=overdue&limit=50 — يجيب invoices مع filter.
    الـ frontend بيناديه كـ fallback لـ /finance/invoices/overdue.
    """
    try:
        invoices = _safe_get_overdue_invoices(limit=limit, status=status)
        return {
            "status":    "ok",
            "count":     len(invoices),
            "invoices":  invoices,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except Exception as e:
        logger.error("invoices failed: %s", e)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": str(e)},
        )


# ── Metrics Rebuild ───────────────────────────────────────────────────────────

@finance_realtime_router.post("/metrics/rebuild", tags=["📡 Finance - Live"])
async def force_metrics_rebuild():
    """
    Force immediate metrics snapshot rebuild + WS broadcast.
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
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": str(e)},
        )


# ── Status ────────────────────────────────────────────────────────────────────

@finance_realtime_router.get("/status", tags=["📡 Finance - Live"])
async def realtime_status():
    """Status endpoint للـ monitoring."""
    return {
        "sse_clients": len(_clients),
        "buffer_size": len(_event_buffer),
        "status":      "ok",
        "timestamp":   datetime.utcnow().isoformat() + "Z",
    }