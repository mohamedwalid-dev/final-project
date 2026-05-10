"""
📈 Escalation Engine — v1.0 Production
========================================
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
"""

from __future__ import annotations

import logging
from datetime import datetime
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


class EscalationEngine:
    """
    Manages the escalation ladder for overdue invoices.

    Usage:
        engine = EscalationEngine()
        result = await engine.escalate(invoice_id, force_tier=None)
    """

    async def get_current_tier(self, invoice_id: int) -> int:
        """Determine the current escalation tier from DB state."""
        try:
            from core.finance_db import get_escalation_status
            status_data = get_escalation_status(invoice_id)

            if "error" in status_data:
                return 0

            invoice = status_data.get("invoice", {})
            invoice_status = invoice.get("status", "pending")

            # Check if already in terminal/frozen state
            if invoice_status in ("paid", "written_off", "cancelled", "disputed"):
                return 0

            return status_data.get("current_tier", 1)
        except Exception as e:
            logger.warning("get_current_tier failed for invoice %s: %s", invoice_id, e)
            return 0

    async def escalate(
        self,
        invoice_id:  int,
        customer_id: Optional[int] = None,
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
        """
        from actions.finance_actions import FinanceActionExecutor

        current = await self.get_current_tier(invoice_id)

        if force_tier is not None:
            target_tier = max(1, min(force_tier, 6))
        else:
            target_tier = min(current + 1, 6)

        if target_tier <= current and force_tier is None:
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
            "📈 [Escalation] Invoice #%s: tier %d → %d (%s)",
            invoice_id, current, target_tier, tier_def["name"],
        )

        # If escalating to legal, create a legal case
        if target_tier == 5:
            try:
                from core.finance_db import create_legal_case
                case_result = create_legal_case(
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
                logger.warning("Legal case creation failed: %s", e)

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
                logger.warning(
                    "Escalation action %s failed: %s", action, e,
                )
                actions_executed.append({
                    "action": action,
                    "status": "failed",
                    "error":  str(e),
                })

        # Log the escalation itself
        try:
            from core.finance_db import log_collection_action
            log_collection_action(
                invoice_id=invoice_id,
                customer_id=customer_id,
                action_type="escalation",
                template_name=f"escalation_tier_{target_tier}",
                subject=f"Escalation: Invoice #{invoice_id} → {tier_def['name']}",
                body=f"Escalated from tier {current} to tier {target_tier} ({tier_def['label']})",
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
            "escalated_at":     datetime.utcnow().isoformat() + "Z",
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

        # Recommend based on overdue days
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
