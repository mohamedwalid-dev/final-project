"""
🏷️ Goal-Kind Taxonomy — Single Source of Truth
===============================================
File: app/orchestrator/agentic/kinds.py

ONE place that defines:
    - the canonical agentic "goal kinds"
    - how each kind maps to the system's REAL domain event_type
      (the exact strings published on core.event_bus by the trigger engine)
    - how to infer a kind from free text + a context dict

Why this file exists:
    Previously the kind-inference lived inside planner.py, and the event
    types lived inside core/trigger.py + core/finance_trigger.py. Two copies
    of the same knowledge drift apart. This module is imported by the planner
    and the coordinator's event endpoint so there is exactly one mapping.

    The canonical event_type strings below MUST match the ones the trigger
    engine subscribes/publishes (verified against core/trigger.py and
    core/finance_trigger.py):
        leave_requested · salary_review · incentive_request · absence_event
        invoice_overdue · invoice_created · payment_received
"""

from __future__ import annotations

from typing import Optional

# kind → {event_type, keywords, primary tool used by the deterministic planner}
GOAL_KINDS: dict[str, dict] = {
    "leave_review": {
        "event_type": "leave_requested",
        "keywords":   ("leave", "vacation", "time off", "إجازة", "اجازة", "أجازة"),
    },
    "salary_review": {
        "event_type": "salary_review",
        "keywords":   ("salary", "increment", "raise", "compensation", "راتب", "علاوة", "مرتب"),
    },
    "incentive_review": {
        "event_type": "incentive_request",
        "keywords":   ("incentive", "bonus", "reward", "حافز", "مكافأة", "مكافاه"),
    },
    "absence_review": {
        "event_type": "absence_event",
        "keywords":   ("absence", "absent", "no-show", "غياب", "تغيب"),
    },
    "invoice_collection": {
        "event_type": "invoice_overdue",
        "keywords":   ("invoice", "overdue", "collect", "collection", "payment due",
                       "فاتورة", "تحصيل", "متأخر", "مديونية"),
    },
    "new_invoice": {
        "event_type": "invoice_created",
        "keywords":   ("new invoice", "invoice created", "فاتورة جديدة"),
    },
    "payment_received": {
        "event_type": "payment_received",
        "keywords":   ("payment received", "paid", "settlement", "سداد", "دفعة", "تم الدفع"),
    },
    "risk_assessment": {
        "event_type": None,    # analytical goal — no domain event
        "keywords":   ("risk", "credit", "score", "creditworthiness", "مخاطر", "ملاءة"),
    },
    "generic": {
        "event_type": None,
        "keywords":   (),
    },
}

# Reverse map: event_type → kind (built once).
_EVENT_TO_KIND: dict[str, str] = {
    spec["event_type"]: kind
    for kind, spec in GOAL_KINDS.items()
    if spec.get("event_type")
}


def all_kinds() -> list[str]:
    return list(GOAL_KINDS.keys())


def kind_to_event_type(kind: str) -> Optional[str]:
    """Return the canonical domain event_type for a kind, or None."""
    return GOAL_KINDS.get((kind or "").lower(), {}).get("event_type")


def event_type_to_kind(event_type: str) -> str:
    """Map a real domain event_type back to a goal kind (defaults to 'generic')."""
    return _EVENT_TO_KIND.get((event_type or "").strip(), "generic")


def infer_kind(goal: str, context: Optional[dict] = None) -> str:
    """
    Infer the goal kind from the goal text first, then fall back to clues in
    the context dict (entity ids present). Always returns a valid kind.
    """
    g = (goal or "").lower()

    # 1) keyword match on the goal text (longest keyword sets win implicitly
    #    because more specific kinds like new_invoice are checked before the
    #    broad invoice_collection via ordering below).
    for kind in ("payment_received", "new_invoice", "invoice_collection",
                 "leave_review", "salary_review", "incentive_review",
                 "absence_review", "risk_assessment"):
        for kw in GOAL_KINDS[kind]["keywords"]:
            if kw in g:
                return kind

    # 2) context-based inference when the text was ambiguous.
    ctx = context or {}
    if ctx.get("invoice_id") or ctx.get("amount") or ctx.get("overdue_days"):
        return "invoice_collection"
    if ctx.get("absence_type_claimed") or ctx.get("unexcused_count_90d"):
        return "absence_review"
    if ctx.get("current_salary_egp") or ctx.get("requested_increment_pct"):
        return "salary_review"
    if ctx.get("incentive_type") or ctx.get("requested_amount_egp"):
        return "incentive_review"
    if ctx.get("requested_days") or ctx.get("leave_type"):
        return "leave_review"
    if ctx.get("employee_id"):
        return "leave_review"   # most common HR default

    return "generic"
