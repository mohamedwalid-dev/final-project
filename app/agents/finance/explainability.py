"""
🔍 Finance Risk Explainability Engine — v1.1
=============================================
File: app/agents/finance/explainability.py

Converts normalized feature values → human-readable business reasons.
Works independently of SHAP — pure threshold-based rule engine.

v1.1 Changes:
    ✅ Three-tier impact system: positive | negative | neutral
       "neutral" = weak signals (e.g. amount size) — shown in neutral_factors,
       NEVER pollute the top-3 reasons list
    ✅ reasons list filters to weight >= 0.50 strong signals only
    ✅ RecommendedActionEngine — decision-aware business action per prediction

Usage:
    from agents.finance.explainability import FinanceExplainabilityEngine

    engine  = FinanceExplainabilityEngine()
    result  = engine.explain(features_array, risk_score=0.72, decision="reject")

    result["reasons"]             → ["Invoice overdue 130 days", "Late payment rate 60%", ...]
    result["positive_factors"]    → ["Established customer (4+ years)", ...]
    result["negative_factors"]    → ["Severely overdue invoice (>100 days)", ...]
    result["neutral_factors"]     → ["Significant invoice amount (30,000 EGP)"]
    result["recommended_action"]  → "Suspend service and send formal legal demand letter"
    result["summary"]             → "High risk — dominated by critical overdue period ..."
    result["dominant_factor"]     → "Severely overdue invoice (>100 days)"
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Data Structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ExplainationFinding:
    """A single explainability finding for one feature."""
    feature:  str
    label:    str           # human name ("Overdue Days")
    value:    float         # normalized value (0-1)
    display:  str           # human value ("130 days", "65%")
    impact:   str           # "positive" | "negative" | "neutral"
    reason:   str           # full human-readable sentence
    weight:   float         # risk contribution weight (0-1)

    @property
    def is_strong(self) -> bool:
        """Strong signals qualify for the top-3 reasons list."""
        if self.impact == "negative":
            return self.weight >= 0.50
        if self.impact == "positive":
            return self.weight >= 0.60
        return False   # neutral never enters reasons


@dataclass
class ExplainabilityResult:
    """Full explainability output for one prediction."""
    decision:             str
    risk_score:           float
    positive_factors:     List[str]                   = field(default_factory=list)
    negative_factors:     List[str]                   = field(default_factory=list)
    neutral_factors:      List[str]                   = field(default_factory=list)
    all_findings:         List[ExplainationFinding]   = field(default_factory=list)
    dominant_factor:      Optional[str]               = None
    summary:              str                         = ""
    reasons:              List[str]                   = field(default_factory=list)
    recommended_action:   str                         = ""
    feature_snapshot:     dict                        = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "reasons":            self.reasons,
            "positive_factors":   self.positive_factors,
            "negative_factors":   self.negative_factors,
            "neutral_factors":    self.neutral_factors,
            "dominant_factor":    self.dominant_factor,
            "recommended_action": self.recommended_action,
            "summary":            self.summary,
            "feature_snapshot":   self.feature_snapshot,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Rule Definitions
# ─────────────────────────────────────────────────────────────────────────────

# Each rule: (condition_fn, impact, reason_template_fn, weight)
# Condition receives the normalized feature value (0-1).
# Reason template receives (value, display_value) → str.

_RULES: List[dict] = [

    # ── Overdue Days (index 0, denorm × 180) ──────────────────────────────
    {
        "name":    "overdue_days_normalized",
        "idx":     0,
        "label":   "Overdue Days",
        "denorm":  lambda v: f"{int(v * 180)} days",
        "checks": [
            (lambda v: v >= 0.56,  "negative", lambda v, d: f"Critically overdue invoice ({d} — very high default risk)",  1.00),
            (lambda v: v >= 0.33,  "negative", lambda v, d: f"Invoice significantly overdue ({d})",                         0.85),
            (lambda v: v >= 0.17,  "negative", lambda v, d: f"Invoice overdue {d}",                                         0.60),
            (lambda v: v >= 0.06,  "neutral",  lambda v, d: f"Minor overdue period ({d}) — within tolerance",              0.20),
            (lambda v: v < 0.06,   "positive", lambda v, d: f"No significant overdue history (within grace period)",        0.80),
        ],
    },

    # ── Paid Ratio (index 2, already 0-1) ──────────────────────────────────
    {
        "name":    "paid_ratio",
        "idx":     2,
        "label":   "Payment Completion Rate",
        "denorm":  lambda v: f"{v:.0%}",
        "checks": [
            (lambda v: v >= 0.95,  "positive", lambda v, d: f"Near-perfect payment completion rate ({d})",                  0.95),
            (lambda v: v >= 0.85,  "positive", lambda v, d: f"Strong payment history — {d} of invoices paid",               0.80),
            (lambda v: v >= 0.70,  "positive", lambda v, d: f"Adequate payment record ({d} completion rate)",                0.55),
            (lambda v: v < 0.40,   "negative", lambda v, d: f"Very poor payment completion ({d}) — high default risk",      0.90),
            (lambda v: v < 0.60,   "negative", lambda v, d: f"Below-average payment completion rate ({d})",                 0.65),
            (lambda v: v < 0.70,   "neutral",  lambda v, d: f"Moderate payment completion rate ({d})",                     0.25),
        ],
    },

    # ── Late Ratio (index 3, already 0-1) ─────────────────────────────────
    {
        "name":    "late_ratio",
        "idx":     3,
        "label":   "Late Payment Rate",
        "denorm":  lambda v: f"{v:.0%}",
        "checks": [
            (lambda v: v >= 0.55,  "negative", lambda v, d: f"Majority of payments historically late ({d} late rate)",     0.90),
            (lambda v: v >= 0.35,  "negative", lambda v, d: f"Frequent late payment pattern ({d} late rate)",               0.70),
            (lambda v: v >= 0.15,  "neutral",  lambda v, d: f"Occasional late payments ({d} late rate)",                   0.30),
            (lambda v: v < 0.05,   "positive", lambda v, d: f"Consistently on-time payment history (late rate: {d})",      0.90),
            (lambda v: v < 0.10,   "positive", lambda v, d: f"Rarely pays late (late rate: {d})",                           0.70),
            (lambda v: v < 0.15,   "positive", lambda v, d: f"Low late payment rate ({d})",                                 0.45),
        ],
    },

    # ── Customer Age (index 5, denorm × 60 months) ────────────────────────
    {
        "name":    "customer_age_normalized",
        "idx":     5,
        "label":   "Customer Relationship Age",
        "denorm":  lambda v: f"{int(v * 60)} months",
        "checks": [
            (lambda v: v >= 0.67,  "positive", lambda v, d: f"Long-standing customer relationship ({d})",                  0.65),
            (lambda v: v >= 0.33,  "positive", lambda v, d: f"Established customer account ({d})",                         0.45),
            (lambda v: v < 0.10,   "negative", lambda v, d: f"Very new customer — limited credit history ({d})",            0.60),
            (lambda v: v < 0.17,   "neutral",  lambda v, d: f"Relatively new customer account ({d})",                      0.30),
        ],
    },

    # ── Average Delay (index 7, denorm × 90 days) ─────────────────────────
    {
        "name":    "avg_delay_normalized",
        "idx":     7,
        "label":   "Average Payment Delay",
        "denorm":  lambda v: f"{int(v * 90)} days",
        "checks": [
            (lambda v: v >= 0.56,  "negative", lambda v, d: f"Very long average payment delay ({d})",                      0.85),
            (lambda v: v >= 0.33,  "negative", lambda v, d: f"Above-average payment delay ({d} average)",                  0.60),
            (lambda v: v >= 0.17,  "neutral",  lambda v, d: f"Moderate average payment delay ({d})",                       0.30),
            (lambda v: v < 0.06,   "positive", lambda v, d: f"Minimal average payment delay ({d})",                        0.80),
            (lambda v: v < 0.11,   "positive", lambda v, d: f"Low payment delay history ({d} average delay)",              0.60),
        ],
    },

    # ── Credit Score (index 8, denorm × 850) ──────────────────────────────
    {
        "name":    "credit_score_normalized",
        "idx":     8,
        "label":   "Credit Score",
        "denorm":  lambda v: f"{int(v * 850)}/850",
        "checks": [
            (lambda v: v >= 0.88,  "positive", lambda v, d: f"Excellent credit score ({d})",                               0.90),
            (lambda v: v >= 0.76,  "positive", lambda v, d: f"Good credit score ({d})",                                    0.70),
            (lambda v: v >= 0.65,  "positive", lambda v, d: f"Acceptable credit score ({d})",                              0.40),
            (lambda v: v < 0.47,   "negative", lambda v, d: f"Poor credit score ({d}) — elevated risk",                   0.90),
            (lambda v: v < 0.59,   "negative", lambda v, d: f"Below-average credit score ({d})",                          0.60),
            (lambda v: v < 0.65,   "neutral",  lambda v, d: f"Borderline credit score ({d})",                             0.25),
        ],
    },

    # ── Industry Risk (index 9, raw factor 0-1) ───────────────────────────
    {
        "name":    "industry_risk_factor",
        "idx":     9,
        "label":   "Industry Risk",
        "denorm":  lambda v: f"{v:.0%} risk factor",
        "checks": [
            (lambda v: v >= 0.55,  "negative", lambda v, d: f"Operating in very high-risk industry ({d})",                 0.75),
            (lambda v: v >= 0.40,  "negative", lambda v, d: f"Operating in above-average risk industry ({d})",             0.50),
            (lambda v: v >= 0.30,  "neutral",  lambda v, d: f"Moderate industry risk sector ({d})",                       0.20),
            (lambda v: v < 0.10,   "positive", lambda v, d: f"Very low-risk industry (government/education)",              0.70),
            (lambda v: v < 0.20,   "positive", lambda v, d: f"Low-risk industry sector ({d})",                            0.55),
            (lambda v: v < 0.30,   "neutral",  lambda v, d: f"Below-average industry risk ({d})",                         0.25),
        ],
    },

    # ── Invoice Amount (index 1, denorm × 100,000 EGP) ───────────────────
    # Amount alone is NEVER a strong risk signal — always neutral
    {
        "name":    "amount_normalized",
        "idx":     1,
        "label":   "Invoice Amount",
        "denorm":  lambda v: f"{v * 100_000:,.0f} EGP",
        "checks": [
            (lambda v: v >= 0.50,  "neutral",  lambda v, d: f"Very large invoice — high financial exposure ({d})",        0.40),
            (lambda v: v >= 0.10,  "neutral",  lambda v, d: f"Significant invoice amount ({d})",                          0.20),
            (lambda v: v < 0.05,   "neutral",  lambda v, d: f"Low-exposure invoice amount ({d})",                         0.15),
        ],
    },

    # ── Seasonal Factor (index 10, raw factor 0-1) ────────────────────────
    # Seasonality is context — neutral by default
    {
        "name":    "seasonal_factor",
        "idx":     10,
        "label":   "Seasonal Risk",
        "denorm":  lambda v: f"{v:.0%}",
        "checks": [
            (lambda v: v >= 0.50,  "neutral",  lambda v, d: f"High seasonal collection risk period ({d})",                0.25),
            (lambda v: v < 0.30,   "neutral",  lambda v, d: f"Favourable seasonal period for collection ({d})",           0.20),
        ],
    },

    # ── Invoice Frequency (index 6, denorm × 20) ─────────────────────────
    {
        "name":    "invoice_frequency",
        "idx":     6,
        "label":   "Invoice Frequency",
        "denorm":  lambda v: f"{int(v * 20)} invoices/quarter",
        "checks": [
            (lambda v: v >= 0.50,  "positive", lambda v, d: f"High invoice frequency — active & trackable customer ({d})", 0.40),
            (lambda v: v < 0.10,   "neutral",  lambda v, d: f"Infrequent invoice history — limited data ({d})",           0.25),
        ],
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Recommended Action Engine
# ─────────────────────────────────────────────────────────────────────────────

# Rule: (decision, dominant_feature, min_risk, max_risk, action_text)
# Matched top-to-bottom; first match wins.
# dominant_feature is the `feature` field of the highest-weight finding.

_ACTION_RULES: List[tuple] = [
    # ── reject ───────────────────────────────────────────────────────────────
    ("reject", "overdue_days_normalized",   0.70, 1.0,
     "Suspend service immediately and send formal legal demand letter"),
    ("reject", "late_ratio",                0.70, 1.0,
     "Place on credit hold — require full upfront payment before any new service"),
    ("reject", "credit_score_normalized",   0.70, 1.0,
     "Require bank guarantee or letter of credit — do not extend further credit"),
    ("reject", "paid_ratio",                0.70, 1.0,
     "Escalate to collections team — consider debt recovery agency referral"),
    ("reject", "industry_risk_factor",      0.70, 1.0,
     "Reduce credit limit to zero and require advance payment only"),
    ("reject", None,                        0.70, 1.0,
     "Escalate to collections team and suspend all pending services"),

    # ── manual_review ─────────────────────────────────────────────────────────
    ("manual_review", "overdue_days_normalized", 0.55, 0.70,
     "Request 30% upfront payment and set a firm payment deadline within 14 days"),
    ("manual_review", "overdue_days_normalized", 0.45, 0.55,
     "Send structured payment reminder with a 7-day payment deadline"),
    ("manual_review", "late_ratio",              0.45, 1.0,
     "Request partial upfront payment (≥30%) or reduce credit limit"),
    ("manual_review", "credit_score_normalized", 0.45, 1.0,
     "Require a co-signer or reduce credit limit — do not increase exposure"),
    ("manual_review", "paid_ratio",              0.45, 1.0,
     "Offer a payment plan with monthly instalments and a 10% upfront deposit"),
    ("manual_review", "avg_delay_normalized",    0.45, 1.0,
     "Switch to shorter NET-15 payment terms and automate payment reminders"),
    ("manual_review", None,                      0.45, 1.0,
     "Schedule an account review call — assess whether to reduce credit limit"),

    # ── safe_to_collect / approve ─────────────────────────────────────────────
    ("safe_to_collect", None,   0.0, 1.0,
     "Send a polite automated reminder — standard NET-30 terms apply"),
    ("approve",         None,   0.0, 1.0,
     "Standard payment terms apply — no immediate action required"),

    # ── soft_follow_up ────────────────────────────────────────────────────────
    ("soft_follow_up", "overdue_days_normalized", 0.0, 1.0,
     "Send a friendly payment reminder email — follow up in 7 days if no response"),
    ("soft_follow_up", "late_ratio",              0.0, 1.0,
     "Send a reminder and review credit terms at next renewal"),
    ("soft_follow_up", None,                      0.0, 1.0,
     "Send a friendly payment reminder and schedule a follow-up in 7 days"),

    # ── hard_follow_up ────────────────────────────────────────────────────────
    ("hard_follow_up", "overdue_days_normalized", 0.0, 1.0,
     "Call the customer directly — escalate to account manager if no answer within 24h"),
    ("hard_follow_up", None,                      0.0, 1.0,
     "Escalate to account manager — call customer and send written demand notice"),

    # ── payment_plan ──────────────────────────────────────────────────────────
    ("payment_plan", None, 0.0, 1.0,
     "Propose 3–6 monthly instalments with 15–20% upfront deposit — get signed agreement"),

    # ── suspend_service ───────────────────────────────────────────────────────
    ("suspend_service", None, 0.0, 1.0,
     "Suspend all services now — reinstate only upon receipt of full overdue balance"),

    # ── legal_escalation ──────────────────────────────────────────────────────
    ("legal_escalation", None, 0.0, 1.0,
     "Transfer to legal team immediately — initiate formal debt recovery proceedings"),

    # ── write_off ─────────────────────────────────────────────────────────────
    ("write_off", None, 0.0, 1.0,
     "Write off as bad debt — blacklist customer and notify finance team for reporting"),

    # ── catch-all ─────────────────────────────────────────────────────────────
    (None, None, 0.0, 1.0,
     "Review account manually with the collections team"),
]


class RecommendedActionEngine:
    """
    Maps (decision, dominant_feature, risk_score) → a single, specific business action.

    Matching priority:
        1. decision + dominant_feature + risk_range   (most specific)
        2. decision + risk_range                      (no feature match)
        3. catch-all                                  (fallback)
    """

    def get_action(
        self,
        decision:          str,
        dominant_feature:  Optional[str],
        risk_score:        float,
    ) -> str:
        # Pass 1: exact match on decision + dominant_feature + risk_range
        for dec, feat, lo, hi, action in _ACTION_RULES:
            if (
                dec is not None
                and feat is not None
                and dec == decision
                and feat == dominant_feature
                and lo <= risk_score <= hi
            ):
                return action

        # Pass 2: decision + risk_range (feature wildcard)
        for dec, feat, lo, hi, action in _ACTION_RULES:
            if (
                dec is not None
                and feat is None
                and dec == decision
                and lo <= risk_score <= hi
            ):
                return action

        # Pass 3: catch-all
        return "Review account manually with the collections team"


_action_engine = RecommendedActionEngine()



_DECISION_SUMMARIES = {
    "approve": (
        "Low risk — {dominant}. "
        "Customer profile supports standard payment terms."
    ),
    "manual_review": (
        "Medium risk — {dominant}. "
        "Manual review recommended before proceeding."
    ),
    "reject": (
        "High risk — {dominant}. "
        "Collection action required immediately."
    ),
    "safe_to_collect": (
        "Low risk — {dominant}. "
        "Standard collection process applies."
    ),
    "soft_follow_up": (
        "Moderate concern — {dominant}. "
        "Gentle reminder recommended."
    ),
    "hard_follow_up": (
        "Elevated risk — {dominant}. "
        "Escalation to collections team required."
    ),
    "suspend_service": (
        "High risk — {dominant}. "
        "Service suspension warranted pending full payment."
    ),
    "legal_escalation": (
        "Critical risk — {dominant}. "
        "Legal action required."
    ),
    "payment_plan": (
        "High risk but recoverable — {dominant}. "
        "Structured payment plan recommended."
    ),
    "write_off": (
        "Unrecoverable risk — {dominant}. "
        "Write-off recommended."
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# Main Engine
# ─────────────────────────────────────────────────────────────────────────────

class FinanceExplainabilityEngine:
    """
    Threshold-based explainability engine for finance risk decisions.

    Produces:
        - reasons           : top 3 reasons (API-ready list)
        - positive_factors  : what's working in the customer's favour
        - negative_factors  : what's driving up risk
        - dominant_factor   : single most impactful reason
        - summary           : one-sentence plain-English summary
        - feature_snapshot  : full feature dict for audit trail

    Does NOT require SHAP — works on raw normalized feature arrays.
    """

    def explain(
        self,
        features:   np.ndarray,
        risk_score: float,
        decision:   str,
    ) -> ExplainabilityResult:
        """
        Generate full explainability output.

        Args:
            features:   shape (1, 11) — normalized 11-feature base vector
            risk_score: ML probability (0-1)
            decision:   final decision string (approve / reject / manual_review / …)

        Returns:
            ExplainabilityResult with reasons, neutral_factors, recommended_action, etc.
        """
        if features.ndim == 2:
            row = features[0]
        else:
            row = features

        findings: List[ExplainationFinding] = []

        for rule_def in _RULES:
            idx     = rule_def["idx"]
            val     = float(row[idx]) if idx < len(row) else 0.0
            display = rule_def["denorm"](val)

            for condition_fn, impact, reason_fn, weight in rule_def["checks"]:
                if condition_fn(val):
                    findings.append(ExplainationFinding(
                        feature  = rule_def["name"],
                        label    = rule_def["label"],
                        value    = round(val, 4),
                        display  = display,
                        impact   = impact,
                        reason   = reason_fn(val, display),
                        weight   = weight,
                    ))
                    break   # only first matching rule per feature

        # ── Split by impact ───────────────────────────────────────────────────
        negative = sorted(
            [f for f in findings if f.impact == "negative"],
            key=lambda x: x.weight, reverse=True,
        )
        positive = sorted(
            [f for f in findings if f.impact == "positive"],
            key=lambda x: x.weight, reverse=True,
        )
        neutral = sorted(
            [f for f in findings if f.impact == "neutral"],
            key=lambda x: x.weight, reverse=True,
        )

        neg_reasons     = [f.reason for f in negative]
        pos_reasons     = [f.reason for f in positive]
        neutral_reasons = [f.reason for f in neutral]

        # ── Dominant factor: highest-weight NON-neutral finding ───────────────
        strong_findings = sorted(
            [f for f in findings if f.impact != "neutral"],
            key=lambda x: x.weight, reverse=True,
        )
        dominant_finding = strong_findings[0] if strong_findings else (
            sorted(findings, key=lambda x: x.weight, reverse=True)[0]
            if findings else None
        )
        dominant        = dominant_finding.reason  if dominant_finding else "General risk assessment"
        dominant_feat   = dominant_finding.feature if dominant_finding else None

        # ── Top-3 reasons: strong signals only (weight-filtered) ──────────────
        strong_neg = [f.reason for f in negative if f.is_strong]
        strong_pos = [f.reason for f in positive if f.is_strong]
        top_reasons = (strong_neg + strong_pos)[:3] or ["General risk assessment"]

        # ── Recommended action ────────────────────────────────────────────────
        recommended_action = _action_engine.get_action(
            decision         = decision,
            dominant_feature = dominant_feat,
            risk_score       = risk_score,
        )

        # ── Summary ───────────────────────────────────────────────────────────
        template = _DECISION_SUMMARIES.get(
            decision,
            "Risk score {risk:.0%} — {dominant}."
        )
        summary = template.format(dominant=dominant.lower(), risk=risk_score)

        # ── Feature snapshot (audit trail) ────────────────────────────────────
        snapshot = {
            r["name"]: {
                "value":   round(float(row[r["idx"]]) if r["idx"] < len(row) else 0.0, 4),
                "display": r["denorm"](float(row[r["idx"]]) if r["idx"] < len(row) else 0.0),
            }
            for r in _RULES
        }

        return ExplainabilityResult(
            decision            = decision,
            risk_score          = round(risk_score, 4),
            positive_factors    = pos_reasons,
            negative_factors    = neg_reasons,
            neutral_factors     = neutral_reasons,
            all_findings        = findings,
            dominant_factor     = dominant,
            summary             = summary,
            reasons             = top_reasons,
            recommended_action  = recommended_action,
            feature_snapshot    = snapshot,
        )

    def explain_from_data(
        self,
        data:       dict,
        risk_score: float,
        decision:   str,
    ) -> ExplainabilityResult:
        """
        Convenience method — builds feature array from raw API/event data dict,
        then calls explain().

        Uses same normalization as FinanceRiskModelHandlerV3.build_features().
        """
        from datetime import datetime

        def safe_float(val, default=0.0):
            try:
                v = float(val or default)
                return v if (v == v and abs(v) != float("inf")) else default
            except (TypeError, ValueError):
                return default

        SEASONAL_RISK = {
            1: 0.50, 2: 0.45, 3: 0.35, 4: 0.30, 5: 0.30, 6: 0.40,
            7: 0.35, 8: 0.40, 9: 0.30, 10: 0.25, 11: 0.30, 12: 0.55,
        }
        INDUSTRY_RISK = {
            "retail": 0.40, "hospitality": 0.50, "construction": 0.60,
            "manufacturing": 0.35, "technology": 0.25, "healthcare": 0.20,
            "education": 0.15, "government": 0.05, "financial": 0.20,
            "real_estate": 0.55, "food_beverage": 0.45,
            "transportation": 0.40, "unknown": 0.40,
        }

        overdue_days      = safe_float(data.get("overdue_days"), 0)
        amount            = safe_float(data.get("amount"), 0)
        payment_count     = max(1, int(safe_float(data.get("payment_history_count"), 1)))
        paid_count        = int(safe_float(data.get("payment_history_paid"), 0))
        late_count        = int(safe_float(data.get("payment_history_late"), 0))
        customer_age_mo   = safe_float(data.get("customer_age_months"), 12)
        invoice_count_90d = safe_float(data.get("invoice_count_90d"), 1)
        avg_delay_days    = safe_float(data.get("avg_payment_delay_days"), 0)
        credit_score      = safe_float(data.get("credit_score"), 650)
        month             = int(safe_float(data.get("invoice_month"), datetime.utcnow().month))
        industry          = str(data.get("industry", "unknown")).lower().strip()

        features = np.array([
            min(overdue_days / 180.0, 1.0),
            min(amount / 100_000.0, 1.0),
            paid_count / payment_count,
            late_count / payment_count,
            1.0 - (late_count / payment_count),
            min(customer_age_mo / 60.0, 1.0),
            min(invoice_count_90d / 20.0, 1.0),
            min(avg_delay_days / 90.0, 1.0),
            min(max(credit_score, 300), 850) / 850.0,
            INDUSTRY_RISK.get(industry, 0.40),
            SEASONAL_RISK.get(month, 0.35),
        ], dtype=np.float64)

        return self.explain(features, risk_score, decision)


# ─────────────────────────────────────────────────────────────────────────────
# Singleton accessor
# ─────────────────────────────────────────────────────────────────────────────

_engine: Optional[FinanceExplainabilityEngine] = None


def get_explainability_engine() -> FinanceExplainabilityEngine:
    """Module-level singleton — cheap to reuse across requests."""
    global _engine
    if _engine is None:
        _engine = FinanceExplainabilityEngine()
    return _engine