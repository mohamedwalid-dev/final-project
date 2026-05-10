"""
💰 Finance Agent — v1.0 Production
=====================================
File: app/agents/finance/finance_agent.py

Risk Decision System for Invoice & Payment Management.

Decision Types:
    ✅ safe_to_collect      — low risk, standard follow-up
    ⚠️  soft_follow_up      — send reminder email
    🔔 hard_follow_up       — call + escalate to account manager
    🚫 suspend_service      — stop service until payment
    ⚖️  legal_escalation     — send to legal team
    💳 payment_plan         — offer installment plan
    ❌ write_off            — mark as bad debt

Pipeline:
    Invoice Event → Feature Builder → ML Risk Score
                  → Rule Check → LLM Reasoning
                  → Decision → Action Worker → Audit Log
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from agents.base_agent import BaseAgent, RequestContext, generate_request_id
from agents.finance.risk_model_handler import get_finance_risk_handler
from config.hr_thresholds import LLM_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# ⚙️  THRESHOLDS & CONFIG
# ════════════════════════════════════════════════════════════════════════════

HIGH_RISK_THRESHOLD   = 0.70   # above → hard action
MEDIUM_RISK_THRESHOLD = 0.45   # above → soft action
LOW_RISK_THRESHOLD    = 0.25   # below → safe

MAX_OVERDUE_DAYS_SUSPEND = 45   # suspend service after 45 days overdue
MAX_OVERDUE_DAYS_LEGAL   = 90   # legal escalation after 90 days overdue
MAX_OVERDUE_DAYS_WRITEOFF= 180  # write-off after 180 days overdue

MIN_AMOUNT_FOR_LEGAL     = 5000.0   # EGP — below this don't go legal
MIN_AMOUNT_FOR_WRITEOFF  = 500.0    # EGP — below this write off directly


# ════════════════════════════════════════════════════════════════════════════
# 💰  FINANCE AGENT
# ════════════════════════════════════════════════════════════════════════════

class FinanceAgent(BaseAgent):
    """
    Finance AI Agent — Invoice Risk & Collection Decision System.

    Entry points:
        await agent.process_invoice(data)        ← main: overdue invoice
        await agent.process_payment_received(data) ← payment received
        await agent.process_new_invoice(data)    ← new invoice created

    Static:
        FinanceAgent.get_model_info() → dict
    """

    @property
    def name(self) -> str:
        return "FinanceAgent_v1.0"

    # ── BaseAgent.process (sync wrapper) ──────────────────────────────────────

    def process(self, data: dict) -> dict:
        """Sync wrapper — delegates to async_process."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self.process_invoice(data))
                    return future.result(timeout=60)
            return loop.run_until_complete(self.process_invoice(data))
        except Exception as e:
            logger.error("[FinanceAgent] process() failed: %s", e)
            return self._emergency_fallback(data, str(e))

    # ── Main: Overdue Invoice Pipeline ────────────────────────────────────────

    async def process_invoice(self, data: dict) -> dict:
        """
        Main overdue invoice decision pipeline.

        Flow:
            1. Hard Business Rules (instant decisions)
            2. ML Risk Score
            3. Gemini LLM Reasoning (for borderline cases)
            4. Final Decision + Action Plan
        """
        request_id  = data.get("request_id") or generate_request_id()
        data        = {**data, "request_id": request_id}
        invoice_id  = data.get("invoice_id", "?")
        customer_id = data.get("customer_id", "?")

        logger.info(
            "[request_id=%s] 💰 [FinanceAgent] invoice processing — "
            "invoice=%s customer=%s",
            request_id, invoice_id, customer_id,
        )

        # ── Phase 1: Hard Rules (instant, no ML needed) ────────────────────
        hard_rule_result = self._apply_hard_rules(data, request_id)
        if hard_rule_result:
            logger.info(
                "[request_id=%s] 📏 Hard rule fired: %s → %s",
                request_id,
                hard_rule_result.get("rule"),
                hard_rule_result.get("decision"),
            )
            return hard_rule_result

        # ── Phase 2: ML Risk Scoring ───────────────────────────────────────
        try:
            handler   = get_finance_risk_handler()
            ml_result = handler.predict(data)
            risk_score = ml_result.get("risk_score", 0.5)
            risk_label = ml_result.get("risk_label", "medium")
        except Exception as e:
            logger.warning(
                "[request_id=%s] ⚠️ ML predict failed: %s — using rule-based fallback",
                request_id, e,
            )
            risk_score = self._compute_rule_based_risk(data)
            risk_label = self._score_to_label(risk_score)
            ml_result  = {"risk_score": risk_score, "risk_label": risk_label, "source": "rules"}

        logger.info(
            "[request_id=%s] 🤖 Risk score: %.3f (%s)",
            request_id, risk_score, risk_label,
        )

        # ── Phase 3: Quick Decision for clear cases ────────────────────────
        if risk_score >= HIGH_RISK_THRESHOLD:
            # High risk → try LLM for nuanced reasoning, then decide
            llm_result = await self._invoke_llm(data, ml_result, request_id)
            decision   = self._finalize_decision(data, risk_score, llm_result, request_id)
        elif risk_score <= LOW_RISK_THRESHOLD:
            # Low risk → safe, standard collection
            decision = self._build_low_risk_decision(data, ml_result, request_id)
        else:
            # Medium risk → LLM review
            llm_result = await self._invoke_llm(data, ml_result, request_id)
            decision   = self._finalize_decision(data, risk_score, llm_result, request_id)

        logger.info(
            "[request_id=%s] ✅ [FinanceAgent] Final: %s | risk=%.3f | "
            "action=%s",
            request_id,
            decision.get("decision"),
            risk_score,
            decision.get("primary_action"),
        )
        try:
            from core.metrics_collector import get_metrics_collector, MetricEvent
            await get_metrics_collector().emit(MetricEvent(
                metric_type = decision. get("decision", "unknown"),
                category    = "finance",
                value       = 1,
                tags        = {
                    "risk_score":   decision.get("risk_score", 0),
                    "overdue_days": data.get("overdue_days", 0),
                    "model_source": decision.get("model_source", "unknown"),
                    "llm_used":     decision.get("llm_used", False),
                },
                entity_id   = data.get("invoice_id"),
                entity_type = "invoice",
                request_id  = request_id,
            ))
        except Exception as e:
            logger.debug("MetricsCollector emit skipped: %s", e)

        return decision

    # ── Payment Received Pipeline ─────────────────────────────────────────────

    async def process_payment_received(self, data: dict) -> dict:
        """Handle payment received event — update risk profile."""
        request_id  = data.get("request_id") or generate_request_id()
        invoice_id  = data.get("invoice_id", "?")
        amount_paid = float(data.get("amount_paid", 0))
        amount_due  = float(data.get("amount_due", 0))

        logger.info(
            "[request_id=%s] 💳 Payment received — invoice=%s amount=%s",
            request_id, invoice_id, amount_paid,
        )

        # Full payment
        if amount_paid >= amount_due:
            decision_val = "payment_complete"
            reason       = (
                f"Full payment of {amount_paid:,.2f} EGP received. "
                f"Invoice #{invoice_id} is now settled. "
                "Customer risk profile updated positively."
            )
            next_actions = ["mark_invoice_paid", "update_customer_credit_score", "send_receipt"]
        # Partial payment
        elif amount_paid > 0:
            remaining    = amount_due - amount_paid
            decision_val = "partial_payment"
            reason       = (
                f"Partial payment of {amount_paid:,.2f} EGP received. "
                f"Remaining balance: {remaining:,.2f} EGP. "
                "Schedule follow-up for remaining amount."
            )
            next_actions = [
                "update_invoice_partial",
                "schedule_followup",
                "send_partial_receipt",
            ]
        else:
            decision_val = "no_payment"
            reason       = "Payment event received but amount is 0."
            next_actions = ["investigate_payment_event"]

        return {
            "decision":        decision_val,
            "confidence":      0.99,
            "risk":            "low",
            "reason":          reason,
            "primary_action":  next_actions[0] if next_actions else "no_action",
            "action_plan":     next_actions,
            "invoice_id":      invoice_id,
            "amount_paid":     amount_paid,
            "amount_due":      amount_due,
            "domain":          "finance",
            "request_id":      request_id,
            "llm_used":        False,
            "model_source":    "payment_rules",
        }

    # ── New Invoice Pipeline ──────────────────────────────────────────────────

    async def process_new_invoice(self, data: dict) -> dict:
        """
        Handle new invoice created — assess customer risk upfront
        and set collection strategy.
        """
        request_id  = data.get("request_id") or generate_request_id()
        invoice_id  = data.get("invoice_id", "?")
        customer_id = data.get("customer_id", "?")
        amount      = float(data.get("amount", 0))

        logger.info(
            "[request_id=%s] 🧾 New invoice — invoice=%s customer=%s amount=%s",
            request_id, invoice_id, customer_id, amount,
        )

        # Compute upfront risk from customer history
        try:
            handler    = get_finance_risk_handler()
            ml_result  = handler.predict(data)
            risk_score = ml_result.get("risk_score", 0.3)
        except Exception:
            risk_score = self._compute_rule_based_risk(data)
            ml_result  = {"risk_score": risk_score, "source": "rules"}

        risk_label   = self._score_to_label(risk_score)
        due_date_str = data.get("due_date", "30 days from today")

        # Set collection strategy based on upfront risk
        if risk_score >= HIGH_RISK_THRESHOLD:
            strategy    = "aggressive"
            first_reminder_days = 3
            notes       = "High-risk customer — monitor closely, remind early."
        elif risk_score >= MEDIUM_RISK_THRESHOLD:
            strategy    = "standard"
            first_reminder_days = 7
            notes       = "Medium-risk — standard collection schedule."
        else:
            strategy    = "relaxed"
            first_reminder_days = 14
            notes       = "Low-risk customer — standard payment expected."

        return {
            "decision":              "invoice_registered",
            "confidence":            0.90,
            "risk":                  risk_label,
            "risk_score":            round(risk_score, 4),
            "reason":                notes,
            "primary_action":        "set_collection_strategy",
            "action_plan":           [
                "set_collection_strategy",
                f"schedule_first_reminder_in_{first_reminder_days}_days",
                "update_customer_risk_profile",
            ],
            "collection_strategy":   strategy,
            "first_reminder_days":   first_reminder_days,
            "invoice_id":            invoice_id,
            "customer_id":           customer_id,
            "amount":                amount,
            "due_date":              due_date_str,
            "domain":                "finance",
            "request_id":            request_id,
            "llm_used":              False,
            "model_source":          ml_result.get("source", "ml_model"),
        }

    # ── Phase 1: Hard Business Rules ──────────────────────────────────────────

    def _apply_hard_rules(self, data: dict, request_id: str) -> Optional[dict]:
        """
        Instant decisions based on hard rules — no ML needed.
        Returns result dict if rule fires, else None.
        """
        overdue_days  = int(data.get("overdue_days", 0))
        amount        = float(data.get("amount", 0))
        payment_count = int(data.get("payment_history_count", 0))
        paid_count    = int(data.get("payment_history_paid", 0))
        is_disputed   = bool(data.get("is_disputed", False))
        has_guarantee = bool(data.get("has_bank_guarantee", False))

        # Rule F0: Disputed invoice → put on hold, investigate
        if is_disputed:
            return self._build_decision(
                decision      = "on_hold_disputed",
                confidence    = 0.99,
                risk          = "medium",
                reason        = (
                    "Invoice is currently under dispute. "
                    "All collection actions are suspended until dispute is resolved. "
                    "Escalate to account manager for investigation."
                ),
                primary_action= "escalate_to_account_manager",
                action_plan   = [
                    "put_invoice_on_hold",
                    "notify_account_manager",
                    "send_dispute_acknowledgment_to_customer",
                ],
                rule          = "rule_f0_disputed",
                data          = data,
                request_id    = request_id,
            )

        # Rule F1: Write-off threshold (180+ days)
        if overdue_days >= MAX_OVERDUE_DAYS_WRITEOFF:
            if amount < MIN_AMOUNT_FOR_WRITEOFF:
                return self._build_decision(
                    decision      = "write_off",
                    confidence    = 0.97,
                    risk          = "high",
                    reason        = (
                        f"Invoice overdue {overdue_days} days (≥{MAX_OVERDUE_DAYS_WRITEOFF}). "
                        f"Amount {amount:,.2f} EGP is below minimum for legal action. "
                        "Writing off as bad debt."
                    ),
                    primary_action= "write_off_invoice",
                    action_plan   = [
                        "write_off_invoice",
                        "update_bad_debt_report",
                        "blacklist_customer",
                        "notify_finance_team",
                    ],
                    rule          = "rule_f1_writeoff",
                    data          = data,
                    request_id    = request_id,
                )
            else:
                return self._build_decision(
                    decision      = "legal_escalation",
                    confidence    = 0.98,
                    risk          = "high",
                    reason        = (
                        f"Invoice overdue {overdue_days} days (≥{MAX_OVERDUE_DAYS_WRITEOFF}). "
                        f"Amount {amount:,.2f} EGP requires legal action. "
                        "Escalating to legal team immediately."
                    ),
                    primary_action= "escalate_to_legal",
                    action_plan   = [
                        "suspend_service",
                        "escalate_to_legal",
                        "send_legal_warning_letter",
                        "blacklist_customer",
                        "notify_management",
                    ],
                    rule          = "rule_f1_legal_180days",
                    data          = data,
                    request_id    = request_id,
                )

        # Rule F2: Legal escalation (90+ days, amount > threshold)
        if overdue_days >= MAX_OVERDUE_DAYS_LEGAL and amount >= MIN_AMOUNT_FOR_LEGAL:
            return self._build_decision(
                decision      = "legal_escalation",
                confidence    = 0.97,
                risk          = "high",
                reason        = (
                    f"Invoice overdue {overdue_days} days (≥{MAX_OVERDUE_DAYS_LEGAL}). "
                    f"Amount {amount:,.2f} EGP exceeds legal threshold. "
                    "Immediate legal escalation required."
                ),
                primary_action= "escalate_to_legal",
                action_plan   = [
                    "suspend_service",
                    "escalate_to_legal",
                    "send_legal_warning_letter",
                    "notify_management",
                ],
                rule          = "rule_f2_legal_90days",
                data          = data,
                request_id    = request_id,
            )

        # Rule F3: Suspend service (45+ days overdue)
        if overdue_days >= MAX_OVERDUE_DAYS_SUSPEND and not has_guarantee:
            return self._build_decision(
                decision      = "suspend_service",
                confidence    = 0.95,
                risk          = "high",
                reason        = (
                    f"Invoice overdue {overdue_days} days (≥{MAX_OVERDUE_DAYS_SUSPEND}). "
                    "Service suspension applied as per collection policy."
                ),
                primary_action= "suspend_service",
                action_plan   = [
                    "suspend_service",
                    "send_suspension_notice",
                    "schedule_legal_review",
                    "notify_account_manager",
                ],
                rule          = "rule_f3_suspend_45days",
                data          = data,
                request_id    = request_id,
            )

        # Rule F4: Perfect payment history → trust them (even if overdue)
        if payment_count >= 5 and paid_count == payment_count and overdue_days < 15:
            return self._build_decision(
                decision      = "soft_follow_up",
                confidence    = 0.92,
                risk          = "low",
                reason        = (
                    f"Customer has perfect payment history ({paid_count}/{payment_count}). "
                    f"Invoice only {overdue_days} days overdue. "
                    "Gentle reminder recommended."
                ),
                primary_action= "send_friendly_reminder",
                action_plan   = [
                    "send_friendly_reminder",
                    "schedule_followup_7_days",
                ],
                rule          = "rule_f4_perfect_history",
                data          = data,
                request_id    = request_id,
            )

        return None  # No hard rule fired → proceed to ML

    # ── Phase 2: Finalize Decision ────────────────────────────────────────────

    def _finalize_decision(
        self,
        data:       dict,
        risk_score: float,
        llm_result: Optional[dict],
        request_id: str,
    ) -> dict:
        """Combine ML risk score + LLM reasoning into final decision."""
        overdue_days = int(data.get("overdue_days", 0))
        amount       = float(data.get("amount", 0))

        # LLM provided a decision
        if llm_result and llm_result.get("decision"):
            decision_val   = llm_result["decision"]
            reason         = llm_result.get("reason", "AI-based risk assessment.")
            action_plan    = llm_result.get("action_plan", [decision_val])
            confidence     = float(llm_result.get("confidence", risk_score))
            source         = "llm_reasoning"
        else:
            # Fallback to rule-based decision from score
            decision_val, reason, action_plan = self._score_to_decision(
                risk_score, overdue_days, amount, data
            )
            confidence = risk_score
            source     = "risk_score_rules"

        primary_action = action_plan[0] if action_plan else decision_val
        risk_label     = self._score_to_label(risk_score)

        return {
            "decision":        decision_val,
            "confidence":      round(confidence, 4),
            "risk":            risk_label,
            "risk_score":      round(risk_score, 4),
            "reason":          reason,
            "primary_action":  primary_action,
            "action_plan":     action_plan,
            "invoice_id":      data.get("invoice_id"),
            "customer_id":     data.get("customer_id"),
            "amount":          amount,
            "overdue_days":    overdue_days,
            "domain":          "finance",
            "llm_used":        llm_result is not None,
            "model_source":    source,
            "request_id":      request_id,
            "flags":           llm_result.get("flags", []) if llm_result else [],
        }

    def _build_low_risk_decision(self, data: dict, ml_result: dict, request_id: str) -> dict:
        """Low risk path — standard collection."""
        overdue_days = int(data.get("overdue_days", 0))
        amount       = float(data.get("amount", 0))

        if overdue_days <= 7:
            decision_val = "safe_to_collect"
            reason       = "Low-risk invoice, minimal overdue. Standard payment expected."
            action_plan  = ["send_polite_reminder", "schedule_followup_14_days"]
        else:
            decision_val = "soft_follow_up"
            reason       = f"Low-risk customer, {overdue_days} days overdue. Friendly follow-up recommended."
            action_plan  = ["send_friendly_reminder", "schedule_followup_7_days"]

        return {
            "decision":       decision_val,
            "confidence":     round(ml_result.get("risk_score", 0.2), 4),
            "risk":           "low",
            "risk_score":     round(ml_result.get("risk_score", 0.2), 4),
            "reason":         reason,
            "primary_action": action_plan[0],
            "action_plan":    action_plan,
            "invoice_id":     data.get("invoice_id"),
            "customer_id":    data.get("customer_id"),
            "amount":         amount,
            "overdue_days":   overdue_days,
            "domain":         "finance",
            "llm_used":       False,
            "model_source":   ml_result.get("source", "ml_model"),
            "request_id":     request_id,
            "flags":          [],
        }

    # ── LLM Invocation ────────────────────────────────────────────────────────

    async def _invoke_llm(
        self,
        data:       dict,
        ml_result:  dict,
        request_id: str,
    ) -> Optional[dict]:
        """Call Gemini for nuanced invoice risk reasoning."""
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            from config.settings import get_settings
            from agents.finance.prompts import FinancePromptBuilder

            settings = get_settings()
            if not settings.GOOGLE_API_KEY:
                logger.warning(
                    "[request_id=%s] ⚠️ GOOGLE_API_KEY not set — skipping LLM",
                    request_id,
                )
                return None

            llm = ChatGoogleGenerativeAI(
                model          = settings.GEMINI_MODEL,
                google_api_key = settings.GOOGLE_API_KEY,
                temperature    = 0.05,
            )

            prompt = FinancePromptBuilder.invoice_risk(
                data      = {**data, "risk_score": ml_result.get("risk_score", 0.5)},
                trace_id  = request_id,
            )

            logger.debug("[request_id=%s] 🧠 Sending finance prompt to Gemini", request_id)

            response = await asyncio.wait_for(
                llm.ainvoke(prompt),
                timeout=LLM_TIMEOUT_SECONDS,
            )

            parsed = self._parse_llm_json(response.content, request_id)
            if parsed:
                logger.info(
                    "[request_id=%s] ✅ LLM decision: %s | conf=%.3f",
                    request_id,
                    parsed.get("decision", "?"),
                    float(parsed.get("confidence", 0)),
                )
            return parsed

        except asyncio.TimeoutError:
            logger.warning(
                "[request_id=%s] ⏰ Finance LLM timeout — rule fallback",
                request_id,
            )
        except ImportError:
            logger.warning(
                "[request_id=%s] ⚠️ langchain_google_genai not installed",
                request_id,
            )
        except Exception as e:
            logger.warning("[request_id=%s] ⚠️ Finance LLM failed: %s", request_id, e)
        return None

    # ── Score → Decision Mapping ──────────────────────────────────────────────

    def _score_to_decision(
        self,
        risk_score:  float,
        overdue_days: int,
        amount:      float,
        data:        dict,
    ) -> tuple[str, str, list]:
        """Map risk score + context to decision + action plan."""

        if risk_score >= 0.85:
            decision   = "hard_follow_up"
            reason     = (
                f"Very high risk score ({risk_score:.0%}). "
                f"Invoice {overdue_days} days overdue, amount {amount:,.2f} EGP. "
                "Immediate hard follow-up required."
            )
            action_plan = [
                "send_urgent_notice",
                "call_customer",
                "notify_account_manager",
                "schedule_legal_review_7_days",
            ]
        elif risk_score >= HIGH_RISK_THRESHOLD:
            # Check if payment plan is appropriate
            if amount >= 10000 and int(data.get("payment_history_paid", 0)) > 0:
                decision   = "payment_plan"
                reason     = (
                    f"High risk ({risk_score:.0%}) but customer has prior payments. "
                    f"Amount {amount:,.2f} EGP — offer installment plan."
                )
                action_plan = [
                    "propose_payment_plan",
                    "send_payment_plan_offer",
                    "schedule_followup_3_days",
                ]
            else:
                decision   = "hard_follow_up"
                reason     = (
                    f"High risk score ({risk_score:.0%}). "
                    f"Invoice {overdue_days} days overdue. "
                    "Escalate to collections team."
                )
                action_plan = [
                    "send_urgent_notice",
                    "notify_collections_team",
                    "schedule_suspension_review",
                ]
        elif risk_score >= MEDIUM_RISK_THRESHOLD:
            decision   = "soft_follow_up"
            reason     = (
                f"Medium risk ({risk_score:.0%}). "
                f"Invoice {overdue_days} days overdue. "
                "Standard follow-up recommended."
            )
            action_plan = [
                "send_payment_reminder",
                "schedule_followup_7_days",
            ]
        else:
            decision   = "safe_to_collect"
            reason     = (
                f"Low risk ({risk_score:.0%}). "
                "Standard collection process."
            )
            action_plan = ["send_polite_reminder", "schedule_followup_14_days"]

        return decision, reason, action_plan

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_decision(
        self,
        decision:      str,
        confidence:    float,
        risk:          str,
        reason:        str,
        primary_action:str,
        action_plan:   list,
        rule:          str,
        data:          dict,
        request_id:    str,
    ) -> dict:
        """Build a standardized decision result dict."""
        return {
            "decision":       decision,
            "confidence":     confidence,
            "risk":           risk,
            "risk_score":     confidence if risk == "high" else (0.5 if risk == "medium" else 0.2),
            "reason":         reason,
            "primary_action": primary_action,
            "action_plan":    action_plan,
            "override_rule":  rule,
            "invoice_id":     data.get("invoice_id"),
            "customer_id":    data.get("customer_id"),
            "amount":         float(data.get("amount", 0)),
            "overdue_days":   int(data.get("overdue_days", 0)),
            "domain":         "finance",
            "llm_used":       False,
            "model_source":   "hard_rules",
            "request_id":     request_id,
            "flags":          [f"🔴 Hard rule: {rule}"],
        }

    def _compute_rule_based_risk(self, data: dict) -> float:
        """Fallback risk score from rules when ML model unavailable."""
        score        = 0.3   # base
        overdue_days = int(data.get("overdue_days", 0))
        amount       = float(data.get("amount", 0))
        payment_count = int(data.get("payment_history_count", 0))
        paid_count    = int(data.get("payment_history_paid", 0))
        late_count    = int(data.get("payment_history_late", 0))

        # Overdue days contribution
        if overdue_days >= 60:
            score += 0.35
        elif overdue_days >= 30:
            score += 0.25
        elif overdue_days >= 15:
            score += 0.15
        elif overdue_days >= 7:
            score += 0.05

        # Amount contribution
        if amount >= 50000:
            score += 0.10
        elif amount >= 10000:
            score += 0.05

        # Payment history
        if payment_count > 0:
            bad_ratio = (payment_count - paid_count) / payment_count
            score += bad_ratio * 0.30

        # Late payments
        if late_count >= 3:
            score += 0.15
        elif late_count >= 1:
            score += 0.05

        return min(max(score, 0.0), 1.0)

    def _score_to_label(self, score: float) -> str:
        if score >= HIGH_RISK_THRESHOLD:
            return "high"
        elif score >= MEDIUM_RISK_THRESHOLD:
            return "medium"
        return "low"

    def _parse_llm_json(self, content: str, request_id: str) -> Optional[dict]:
        """Parse LLM JSON response."""
        if not content:
            return None
        cleaned = content.strip()
        if cleaned.startswith("```"):
            lines   = cleaned.splitlines()
            cleaned = "\n".join(
                l for l in lines if not l.strip().startswith("```")
            ).strip()
        try:
            parsed = json.loads(cleaned)
            if "decision" not in parsed:
                parsed["decision"] = "soft_follow_up"
            return parsed
        except json.JSONDecodeError:
            pass

        start = cleaned.find("{")
        end   = cleaned.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(cleaned[start:end])
            except json.JSONDecodeError:
                pass

        logger.warning(
            "[request_id=%s] ⚠️ Finance LLM returned non-JSON",
            request_id,
        )
        return None

    def _emergency_fallback(self, data: dict, error: str) -> dict:
        request_id = data.get("request_id", generate_request_id())
        return {
            "decision":       "hard_follow_up",
            "confidence":     0.5,
            "risk":           "high",
            "reason":         f"⚠️ Agent error — manual review required. Error: {error}",
            "primary_action": "manual_review",
            "action_plan":    ["manual_review"],
            "invoice_id":     data.get("invoice_id"),
            "customer_id":    data.get("customer_id"),
            "domain":         "finance",
            "llm_used":       False,
            "model_source":   "emergency_fallback",
            "request_id":     request_id,
            "_agent_error":   True,
        }

    @staticmethod
    def get_model_info() -> dict:
        return get_finance_risk_handler().get_info()