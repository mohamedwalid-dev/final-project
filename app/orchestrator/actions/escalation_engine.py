"""
📈 Escalation Engine — v2.1 Production (MongoDB)
=================================================
File: app/actions/escalation_engine.py

Multi-tier escalation ladder for invoice collection.
Manages automatic and manual escalation flows.

Tiers:
    1. reminder       → polite/friendly email
    2. follow_up      → payment reminder + call
    3. urgent         → urgent notice + account manager
    4. suspension     → suspend service + legal warning
    5. legal          → legal case creation
    6. write_off      → bad debt write-off

CHANGELOG (v2.1):
    - BUG FIX: get_current_tier() no longer collapses "lookup failed" and
      "invoice genuinely has no tier yet" into the same return value (0).
      A dedicated TierLookupError is raised on failure, and escalate()
      aborts instead of silently treating the invoice as fresh (tier 0).
    - FIX: legal case creation failure at tier 5 now ABORTS the escalation
      (no actions executed, no log written) instead of silently continuing
      and sending legal-warning emails with no corresponding legal case
      in the database.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Escalation tier definitions
ESCALATION_TIERS = {
    1: {
        "name":    "reminder",
        "label":   "تذكير ودي",
        "actions": ["send_polite_reminder", "schedule_followup_14_days"],
        "sla_days": 14,
    },
    2: {
        "name":    "follow_up",
        "label":   "متابعة",
        "actions": ["send_payment_reminder", "notify_account_manager", "schedule_followup_7_days"],
        "sla_days": 7,
    },
    3: {
        "name":    "urgent",
        "label":   "إشعار عاجل",
        "actions": ["send_urgent_notice", "call_customer", "notify_collections_team"],
        "sla_days": 5,
    },
    4: {
        "name":    "suspension",
        "label":   "إيقاف الخدمة",
        "actions": ["suspend_service", "send_suspension_notice", "send_legal_warning_letter", "notify_management"],
        "sla_days": 7,
    },
    5: {
        "name":    "legal",
        "label":   "إجراء قانوني",
        "actions": ["escalate_to_legal", "send_legal_warning_letter", "notify_management"],
        "sla_days": 30,
    },
    6: {
        "name":    "write_off",
        "label":   "شطب الدين",
        "actions": ["write_off_invoice", "update_bad_debt_report", "blacklist_customer", "notify_finance_team"],
        "sla_days": 0,
    },
}

# Map invoice statuses to tiers
STATUS_TO_TIER = {
    "pending":      0,
    "overdue":      2,
    "suspended":    4,
    "legal":        5,
    "written_off":  6,
    "payment_plan": 2,
    "disputed":     0,  # frozen
    "paid":         0,  # terminal
}


class TierLookupError(Exception):
    """
    Raised when get_current_tier() cannot reliably determine the invoice's
    current tier (DB error, timeout, malformed response, etc).

    This is intentionally distinct from "tier 0" — tier 0 means "this
    invoice legitimately has no escalation history yet" (e.g. paid,
    written_off, disputed, or brand-new). An error means "we don't know",
    and the caller must NOT treat "don't know" as "tier 0", because that
    silently resets the ladder for invoices that may already be deep in
    escalation (e.g. tier 5/legal) and causes duplicate/out-of-order
    escalation actions.
    """

    def __init__(self, invoice_id: str, original_error: Exception):
        self.invoice_id = invoice_id
        self.original_error = original_error
        super().__init__(
            f"Could not determine current escalation tier for invoice "
            f"#{invoice_id}: {original_error}"
        )


class EscalationEngine:
    """
    Manages the escalation ladder for overdue invoices.
    Uses MongoDB via FinanceDB (Motor async).

    Usage:
        engine = EscalationEngine()
        result = await engine.escalate(invoice_id, force_tier=None)
    """

    async def get_current_tier(self, invoice_id: str) -> int:
        """
        Determine the current escalation tier from MongoDB state.

        Returns 0 ONLY when the invoice is genuinely tier-less (terminal
        status like paid/written_off/cancelled/disputed, or it has no
        escalation record at all — status_data explicitly says so).

        Raises:
            TierLookupError: if the DB call fails or the response can't be
                trusted. Callers must NOT catch this and fall back to 0 —
                that was the original bug. A failed lookup is "unknown",
                not "fresh".
        """
        try:
            from orchestrator.actions.finance_actions import _get_db as get_finance_db
            db = get_finance_db()
            status_data = await db.get_escalation_status(invoice_id)
        except Exception as e:
            logger.error(
                "❌ [Escalation] get_current_tier DB call failed for invoice %s: %s",
                invoice_id, e,
            )
            raise TierLookupError(invoice_id, e) from e

        if "error" in status_data:
            # The DB layer itself reported a problem retrieving status.
            # This is NOT the same as "no escalation record" — treat it
            # as an unknown/untrusted lookup, not tier 0.
            logger.error(
                "❌ [Escalation] get_escalation_status returned error for "
                "invoice %s: %s",
                invoice_id, status_data.get("error"),
            )
            raise TierLookupError(
                invoice_id,
                RuntimeError(status_data.get("error", "unknown DB error")),
            )

        invoice = status_data.get("invoice", {})
        invoice_status = invoice.get("status", "pending")

        if invoice_status in ("paid", "written_off", "cancelled", "disputed"):
            # Legitimately terminal/frozen — tier 0 is correct here.
            return 0

        # current_tier defaults to 1 only when the field is genuinely
        # absent from a SUCCESSFUL lookup (i.e. invoice has no escalation
        # history yet) — not as an error fallback.
        return status_data.get("current_tier", 1)

    async def escalate(
        self,
        invoice_id:  str,
        customer_id: Optional[str] = None,
        amount:      float         = 0,
        force_tier:  Optional[int] = None,
        request_id:  str           = "",
    ) -> dict:
        """
        Escalate an invoice to the next tier (or a specific tier).

        Returns dict with:
            - tier, tier_name, tier_label
            - actions_executed (list of action results)
            - escalated (bool)

        If the current tier cannot be reliably determined, escalation is
        aborted with escalated=False and reason="tier_lookup_failed" —
        UNLESS force_tier is explicitly provided, since the caller is then
        stating the target tier directly and doesn't need current-tier
        context to compute it. force_tier still skips the lookup entirely
        (matches prior behavior), so an operator can manually push an
        invoice to a specific tier even if automatic detection is down.
        """
        from actions.finance_actions import FinanceActionExecutor

        current: Optional[int] = None

        if force_tier is None:
            # We need to know the current tier to compute current + 1.
            try:
                current = await self.get_current_tier(invoice_id)
            except TierLookupError as e:
                logger.error(
                    "🛑 [Escalation] Aborting escalate() for invoice %s — "
                    "current tier unknown, refusing to assume tier 0: %s",
                    invoice_id, e,
                )
                return {
                    "escalated":    False,
                    "reason":       "tier_lookup_failed",
                    "detail":       str(e),
                    "current_tier": None,
                    "tier_name":    "unknown",
                }
            target_tier = min(current + 1, 6)
        else:
            # Explicit target tier — no need to trust/guess current tier.
            target_tier = max(1, min(force_tier, 6))
            # Still try to fetch current tier for logging/response context,
            # but a failure here is non-fatal since force_tier overrides it.
            try:
                current = await self.get_current_tier(invoice_id)
            except TierLookupError as e:
                logger.warning(
                    "⚠️ [Escalation] Could not determine current tier for "
                    "invoice %s during forced escalation (proceeding anyway "
                    "since force_tier=%s was given): %s",
                    invoice_id, force_tier, e,
                )
                current = None

        if current is not None and target_tier <= current and force_tier is None:
            return {
                "escalated":    False,
                "reason":       f"Already at tier {current}, cannot escalate further without force",
                "current_tier": current,
                "tier_name":    ESCALATION_TIERS.get(current, {}).get("name", "unknown"),
            }

        tier_def = ESCALATION_TIERS.get(target_tier)
        if not tier_def:
            return {"escalated": False, "reason": f"Invalid tier: {target_tier}"}

        logger.info(
            "📈 [Escalation] Invoice #%s: tier %s → %d (%s)",
            invoice_id, current if current is not None else "?", target_tier, tier_def["name"],
        )

        # If escalating to legal, create a legal case via MongoDB.
        # A failure here ABORTS the escalation entirely — we never want
        # tier-5 actions (legal warning emails, "escalate_to_legal", etc.)
        # to fire without a corresponding legal case existing in the DB.
        if target_tier == 5:
            try:
                from orchestrator.actions.finance_actions import _get_db as get_finance_db
                db = get_finance_db()
                case_result = await db.create_legal_case(
                    invoice_id=invoice_id,
                    customer_id=customer_id,
                    amount=amount,
                    description=f"Auto-escalated from tier {current} to legal",
                    sla_days=tier_def["sla_days"],
                )
                logger.info(
                    "⚖️ [Escalation] Legal case created: %s",
                    case_result.get("case_ref", "?"),
                )
            except Exception as e:
                logger.error(
                    "🛑 [Escalation] Legal case creation FAILED for invoice "
                    "%s — aborting tier-5 escalation (no actions executed, "
                    "no log written, invoice tier unchanged): %s",
                    invoice_id, e,
                )
                return {
                    "escalated":    False,
                    "reason":       "legal_case_creation_failed",
                    "detail":       str(e),
                    "current_tier": current,
                    "tier_name":    ESCALATION_TIERS.get(current, {}).get("name", "unknown") if current is not None else "unknown",
                }

        # Execute all actions for this tier
        executor = FinanceActionExecutor()
        actions_executed = []

        for action in tier_def["actions"]:
            try:
                result = await executor.execute(
                    action=action,
                    invoice_id=invoice_id,
                    customer_id=customer_id,
                    amount=amount,
                    decision=f"escalation_tier_{target_tier}",
                    reason=f"Escalated to {tier_def['name']} (tier {target_tier})",
                    request_id=request_id,
                )
                actions_executed.append({
                    "action": action,
                    "status": "executed",
                    "result": result,
                })
            except Exception as e:
                logger.warning("Escalation action %s failed: %s", action, e)
                actions_executed.append({
                    "action": action,
                    "status": "failed",
                    "error":  str(e),
                })

        # Log the escalation via MongoDB collection log
        try:
            from orchestrator.actions.finance_actions import _get_db as get_finance_db
            db = get_finance_db()
            await db.log_collection_action(
                invoice_id=invoice_id,
                customer_id=customer_id,
                action_type="escalation",
                template_name=f"escalation_tier_{target_tier}",
                subject=f"Escalation: Invoice #{invoice_id} → {tier_def['name']}",
                body=f"Escalated from tier {current if current is not None else '?'} to tier {target_tier} ({tier_def['label']})",
                priority="critical" if target_tier >= 4 else "high",
                status="escalated",
            )
        except Exception as e:
            logger.warning("Escalation log failed: %s", e)

        return {
            "escalated":        True,
            "invoice_id":       invoice_id,
            "previous_tier":    current,
            "current_tier":     target_tier,
            "tier_name":        tier_def["name"],
            "tier_label":       tier_def["label"],
            "sla_days":         tier_def["sla_days"],
            "actions_executed": actions_executed,
            "escalated_at":     datetime.now(timezone.utc).isoformat(),
        }

    def get_tier_info(self, tier: int) -> dict:
        """Get info about a specific tier."""
        return ESCALATION_TIERS.get(tier, {})

    def get_all_tiers(self) -> dict:
        """Get all tier definitions."""
        return ESCALATION_TIERS

    def recommend_next_action(self, invoice_status: str, overdue_days: int) -> dict:
        """Recommend the next escalation action based on current state."""
        current_tier = STATUS_TO_TIER.get(invoice_status, 1)

        if invoice_status in ("paid", "written_off", "cancelled"):
            return {"action": "none", "reason": "Invoice is in terminal state"}

        if invoice_status == "disputed":
            return {"action": "wait", "reason": "Invoice is under dispute — no escalation allowed"}

        if overdue_days >= 180:
            recommended = 6
        elif overdue_days >= 90:
            recommended = 5
        elif overdue_days >= 45:
            recommended = 4
        elif overdue_days >= 30:
            recommended = 3
        elif overdue_days >= 14:
            recommended = 2
        elif overdue_days >= 1:
            recommended = 1
        else:
            return {"action": "wait", "reason": "Invoice is not yet overdue"}

        target = max(recommended, current_tier + 1)
        target = min(target, 6)

        tier_def = ESCALATION_TIERS.get(target, {})
        return {
            "recommended_tier": target,
            "tier_name":        tier_def.get("name", "unknown"),
            "tier_label":       tier_def.get("label", ""),
            "actions":          tier_def.get("actions", []),
            "current_tier":     current_tier,
            "overdue_days":     overdue_days,
        }


# Singleton
escalation_engine = EscalationEngine()
