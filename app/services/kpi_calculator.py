"""
📊 KPI Calculator — Dashboard Stats Pre-computation
======================================================
File: app/services/kpi_calculator.py

v6.5.1 Fix:
    ❌ REMOVED: hr_db.db["tickets"].count_documents(...) ,
                hr_db.db["leads"].count_documents(...) ,
                hr_db.db["events"].count_documents(...)
       These called Motor-style collection methods directly. NodeHRProxy
       has no real Motor connection anymore — hr_db.db["..."] resolves
       to a MockCollection stub with no count_documents(), which crashed
       every run of this job with:
           AttributeError: 'MockCollection' object has no attribute 'count_documents'

    ✅ tickets / leads / events are DISABLED pending Node API routes
       (same as /events/pending, /decisions, etc. in main.py v6.5).
       Their KPI fields now report 0 with a "disabled" flag instead of
       crashing the whole KPI calculation (which also blocked the
       leave/salary/incentive/absence counts that DO work today).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def calculate_dashboard_kpis() -> dict:
    from core.node_hr_proxy import get_hr_db
    from core.trigger import get_scheduler_status
    from agents.hr.leave_model_handler import get_model_handler

    hr_db     = get_hr_db()
    scheduler = get_scheduler_status()
    ml_info   = get_model_handler().get_info()

    # ── Only call methods that actually exist on NodeHRProxy today ─────────
    # tickets / leads / events have no Node route yet (see main.py v6.5
    # "_EVENTS_DISABLED_DETAIL" etc.) — don't touch hr_db.db["..."] directly.
    (
        pending_leaves,
        pending_salaries,
        pending_incents,
        pending_absences,
    ) = await asyncio.gather(
        hr_db.get_pending_leaves(),
        hr_db.get_pending_salary_reviews(),
        hr_db.get_pending_incentive_requests(),
        hr_db.get_pending_absence_events(),
    )

    return {
        "_id": "global",
        "stats": {
            "leaves":  {"pending": len(pending_leaves)},
            "tickets": {
                "open":       0,
                "urgent":     0,
                "_disabled":  "no /hr/tickets route in Node.js API yet",
            },
            "leads": {
                "new":       0,
                "_disabled": "no /hr/leads route in Node.js API yet",
            },
            "hr_domains": {
                "salary_reviews": {"pending": len(pending_salaries)},
                "incentives":     {"pending": len(pending_incents)},
                "absences": {
                    "pending":  len(pending_absences),
                    "critical": sum(
                        1 for a in pending_absences
                        if int(a.get("unexcused_count_90d", 0)) >= 3
                    ),
                },
            },
            "system": {
                "pending_events":  0,
                "_pending_events_disabled": "no /hr/events route in Node.js API yet",
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
        "updated_at": datetime.now(timezone.utc),
    }