"""
⚖️ Explainable Conflict Resolver — v1.0
=========================================
File: app/agents/hr/conflict_resolver.py

ℹ️ NODE.JS / DB NOTE:
    This file has no MongoDB/Motor dependency and makes no HTTP calls to
    the Node.js API. It only analyzes in-memory dicts (ml_result, payload,
    breakdown) that are already passed in by the caller (hr_agent.py) and
    returns a structured analysis dict — no database or network I/O
    happens inside this module. There is nothing to repoint for the
    Node.js migration — left otherwise identical to v1.0.

🎯 وظيفته:
    لما الـ ML Layer والـ Rules Layer يختلفوا في القرار،
    الـ Conflict Resolver يوضح:
      - ليه اختلفوا
      - أي layer غلب
      - هل فيه data inconsistency
      - ليه القرار النهائي اتاخد

يُستخدم في:
    HRAgent._build_result()     — لإضافة conflict_analysis للـ result
    DecisionValidationLayer     — لتسجيل سبب الـ override بوضوح
    /model/debug endpoint       — لعرض full decision trace

Output:
    {
        "conflict_detected":     bool,
        "ml_decision":           str,
        "rules_decision":        str | None,
        "final_decision":        str,
        "winner":                "ml" | "rules" | "no_conflict",
        "conflict_type":         str | None,
        "conflict_severity":     "none" | "minor" | "major" | "critical",
        "root_cause":            str,
        "data_issues":           list[str],
        "resolution_reason":     str,
        "feature_importance":    dict,
        "confidence_breakdown":  dict,
        "recommendations":       list[str],
    }
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ── Conflict Types ────────────────────────────────────────────────────────────
CONFLICT_TYPES = {
    "BALANCE_MISMATCH":       "Data inconsistency in leave_balance field",
    "LOW_CONF_APPROVE":       "ML wants to approve but confidence is borderline",
    "RULES_OVERRIDE_ML":      "Business rule overrode ML decision",
    "FIELD_MISSING":          "Required field was missing — defaults used",
    "OUTLIER_DETECTED":       "Input contains outlier values affecting confidence",
    "TIER_BOUNDARY":          "Confidence sits exactly on tier boundary",
    "NO_CONFLICT":            "ML and rules are aligned — no conflict",
}

# ── Severity Levels ───────────────────────────────────────────────────────────
SEVERITY_CRITICAL = "critical"   # Hard rule override (balance=0, days>balance)
SEVERITY_MAJOR    = "major"      # Low-confidence approve → escalated
SEVERITY_MINOR    = "minor"      # Borderline values, missing fields
SEVERITY_NONE     = "none"       # All good


class ConflictResolver:
    """
    يحلل الاختلاف بين ML prediction وBusiness Rules.

    Usage:
        resolver = ConflictResolver()
        analysis = resolver.resolve(
            ml_result=ml_result,
            rules_decision="reject",      # ← من DecisionValidationLayer
            final_decision="reject",
            payload=original_payload,
        )
    """

    def resolve(
        self,
        ml_result:       dict,
        final_decision:  str,
        payload:         dict,
        rules_decision:  Optional[str] = None,
        override_rule:   Optional[str] = None,
        tier:            int = 2,
        thresholds:      Optional[dict] = None,
    ) -> dict:
        """
        الدالة الرئيسية — تحلل الـ conflict وترجع full analysis.

        Args:
            ml_result:       نتيجة الـ ML model (من LeaveModelHandler.predict)
            final_decision:  القرار النهائي بعد كل الـ layers
            payload:         الـ input dict الأصلي
            rules_decision:  قرار الـ validation layer (لو اتغير)
            override_rule:   اسم القاعدة اللي عملت override (rule_1, rule_2, ...)
            tier:            الـ tier اللي اشتغل (1, 2, 3)
            thresholds:      الـ thresholds المستخدمة

        Returns:
            ConflictAnalysis dict
        """
        ml_decision  = ml_result.get("decision", "escalate")
        ml_conf      = float(ml_result.get("confidence", 0.5))
        breakdown    = ml_result.get("breakdown", {})
        ml_source    = ml_result.get("source", "ml_model")
        is_outlier   = ml_result.get("is_outlier", False)
        warnings     = ml_result.get("input_warnings", [])

        thresholds = thresholds or {"approve": 0.72, "escalate": 0.42}
        t_approve  = thresholds.get("approve", 0.72)
        t_reject   = thresholds.get("escalate", 0.42)

        # ── Step 1: Detect Data Issues ────────────────────────────────────────
        data_issues = self._detect_data_issues(payload, breakdown, warnings)

        # ── Step 2: Classify Conflict ─────────────────────────────────────────
        conflict_detected  = (rules_decision is not None and rules_decision != ml_decision)
        conflict_type      = None
        conflict_severity  = SEVERITY_NONE
        winner             = "no_conflict"

        if conflict_detected:
            conflict_type, conflict_severity = self._classify_conflict(
                override_rule, ml_conf, t_approve, t_reject, data_issues
            )
            winner = "rules"   # Rules always win when they override
        elif abs(ml_conf - t_approve) < 0.02:
            # Borderline threshold — minor conflict with itself
            conflict_type     = "TIER_BOUNDARY"
            conflict_severity = SEVERITY_MINOR
            conflict_detected = True
            winner            = "ml"
        elif data_issues:
            conflict_type     = "FIELD_MISSING" if any("missing" in i for i in data_issues) else "OUTLIER_DETECTED"
            conflict_severity = SEVERITY_MINOR
            conflict_detected = True
            winner            = "ml"

        # ── Step 3: Root Cause Analysis ───────────────────────────────────────
        root_cause = self._build_root_cause(
            conflict_type, override_rule, ml_conf, t_approve, t_reject,
            ml_decision, final_decision, data_issues, payload, breakdown
        )

        # ── Step 4: Resolution Reason ─────────────────────────────────────────
        resolution_reason = self._build_resolution(
            winner, final_decision, conflict_type, ml_conf,
            override_rule, ml_source
        )

        # ── Step 5: Feature Importance ────────────────────────────────────────
        feature_importance = self._compute_feature_importance(breakdown, payload)

        # ── Step 6: Confidence Breakdown ─────────────────────────────────────
        confidence_breakdown = self._build_confidence_breakdown(
            ml_conf, t_approve, t_reject, tier, is_outlier
        )

        # ── Step 7: Recommendations ───────────────────────────────────────────
        recommendations = self._build_recommendations(
            conflict_type, conflict_severity, data_issues, ml_conf,
            payload, breakdown, override_rule
        )

        # ── Log ───────────────────────────────────────────────────────────────
        if conflict_detected:
            log_fn = logger.warning if conflict_severity in (SEVERITY_MAJOR, SEVERITY_CRITICAL) else logger.info
            log_fn(
                f"⚖️ [ConflictResolver] {conflict_severity.upper()} conflict | "
                f"type={conflict_type} | ml={ml_decision} → final={final_decision} | "
                f"winner={winner} | conf={ml_conf:.3f}"
            )

        return {
            "conflict_detected":    conflict_detected,
            "ml_decision":          ml_decision,
            "rules_decision":       rules_decision,
            "final_decision":       final_decision,
            "winner":               winner,
            "conflict_type":        conflict_type,
            "conflict_severity":    conflict_severity,
            "root_cause":           root_cause,
            "data_issues":          data_issues,
            "resolution_reason":    resolution_reason,
            "feature_importance":   feature_importance,
            "confidence_breakdown": confidence_breakdown,
            "recommendations":      recommendations,
            "tier":                 tier,
            "override_rule":        override_rule,
            "is_outlier":           is_outlier,
            "input_warnings_count": len(warnings),
        }

    # ── Private: Data Issue Detection ─────────────────────────────────────────

    def _detect_data_issues(self, payload: dict, breakdown: dict, warnings: list) -> list[str]:
        issues = []

        # Balance inconsistency (الـ bug الرئيسي في Leave #52)
        payload_balance   = int(payload.get("leave_balance", payload.get("leave_bal", -1)))
        breakdown_balance = float(breakdown.get("leave_balance", -1))
        if payload_balance >= 0 and breakdown_balance >= 0:
            if abs(payload_balance - breakdown_balance) > 1:
                issues.append(
                    f"BALANCE_MISMATCH: payload says {payload_balance}d "
                    f"but model used {breakdown_balance:.0f}d — "
                    f"check field mapping (leave_balance vs leave_bal)"
                )

        # Requested days alias mismatch
        req_days   = payload.get("requested_days")
        leave_days = payload.get("leave_days")
        if req_days and leave_days and abs(int(req_days) - int(leave_days)) > 0:
            issues.append(
                f"DAYS_ALIAS_MISMATCH: requested_days={req_days} "
                f"but leave_days={leave_days} — possible double counting"
            )

        # Zero balance with non-zero approval
        if payload_balance == 0:
            issues.append("ZERO_BALANCE: leave_balance is 0 — hard reject should apply")

        # Days exceed balance
        req = int(payload.get("requested_days", payload.get("leave_days", 0)))
        bal = int(payload.get("leave_balance", 0))
        if req > bal and bal > 0:
            issues.append(
                f"DAYS_EXCEED_BALANCE: requested {req}d > balance {bal}d"
            )

        # Missing fields from warnings
        missing_fields = [w.split(":")[1].split("=")[0] for w in warnings if "missing_field" in w]
        if missing_fields:
            issues.append(f"MISSING_FIELDS: {', '.join(missing_fields)} used defaults")

        # Outlier values from warnings
        clipped = [w for w in warnings if "above_max" in w or "below_min" in w]
        if clipped:
            issues.append(f"CLIPPED_VALUES: {len(clipped)} field(s) out of valid range")

        return issues

    # ── Private: Conflict Classification ──────────────────────────────────────

    def _classify_conflict(
        self,
        override_rule: Optional[str],
        ml_conf:       float,
        t_approve:     float,
        t_reject:      float,
        data_issues:   list,
    ) -> tuple[str, str]:
        if override_rule == "rule_1_zero_balance":
            return "BALANCE_MISMATCH", SEVERITY_CRITICAL
        if override_rule == "rule_2_days_exceed_balance":
            return "BALANCE_MISMATCH", SEVERITY_CRITICAL
        if override_rule == "rule_3_low_confidence_approve":
            return "LOW_CONF_APPROVE", SEVERITY_MAJOR
        if any("BALANCE_MISMATCH" in i for i in data_issues):
            return "BALANCE_MISMATCH", SEVERITY_CRITICAL
        if override_rule:
            return "RULES_OVERRIDE_ML", SEVERITY_MAJOR
        return "RULES_OVERRIDE_ML", SEVERITY_MINOR

    # ── Private: Root Cause ───────────────────────────────────────────────────

    def _build_root_cause(
        self,
        conflict_type:  Optional[str],
        override_rule:  Optional[str],
        ml_conf:        float,
        t_approve:      float,
        t_reject:       float,
        ml_decision:    str,
        final_decision: str,
        data_issues:    list,
        payload:        dict,
        breakdown:      dict,
    ) -> str:
        if not conflict_type or conflict_type == "NO_CONFLICT":
            return f"No conflict — ML ({ml_decision}, conf={ml_conf:.0%}) and rules are aligned."

        if conflict_type == "BALANCE_MISMATCH":
            pb = payload.get("leave_balance", "?")
            bb = breakdown.get("leave_balance", "?")
            return (
                f"Data inconsistency detected in leave_balance: "
                f"API payload has {pb}d but model feature vector used {bb}d. "
                f"This caused the ML to see a different balance than what was submitted. "
                f"Root fix: verify field mapping in _build_features() and sanitize_input()."
            )

        if conflict_type == "LOW_CONF_APPROVE":
            return (
                f"ML returned approve with confidence={ml_conf:.0%}, "
                f"which is below the minimum safe threshold ({t_approve:.0%}) "
                f"required for auto-approval. "
                f"Rule 3 in DecisionValidationLayer converted this to escalate "
                f"to protect against uncertain approvals."
            )

        if conflict_type == "TIER_BOUNDARY":
            diff = abs(ml_conf - t_approve)
            return (
                f"Confidence ({ml_conf:.4f}) is within {diff:.4f} of the "
                f"approve threshold ({t_approve}). "
                f"Tiny changes in input data could flip the decision. "
                f"Consider adding a ±0.02 buffer zone around tier boundaries."
            )

        if conflict_type == "FIELD_MISSING":
            missing = [i for i in data_issues if "MISSING" in i]
            return (
                f"Required fields were absent from the request — defaults were substituted. "
                f"Issues: {'; '.join(missing)}. "
                f"Decisions made on incomplete data are less reliable."
            )

        if conflict_type == "OUTLIER_DETECTED":
            outliers = [i for i in data_issues if "CLIPPED" in i or "outlier" in i.lower()]
            return (
                f"Input contains values outside the model's training range. "
                f"The model's confidence may be unreliable. Details: {'; '.join(outliers)}"
            )

        return (
            f"Business rule override: ML said '{ml_decision}' (conf={ml_conf:.0%}) "
            f"but validation layer applied rule '{override_rule}' → final='{final_decision}'."
        )

    # ── Private: Resolution Reason ────────────────────────────────────────────

    def _build_resolution(
        self,
        winner:         str,
        final_decision: str,
        conflict_type:  Optional[str],
        ml_conf:        float,
        override_rule:  Optional[str],
        ml_source:      str,
    ) -> str:
        if winner == "no_conflict":
            return (
                f"ML model ({ml_source}) and business rules agreed on '{final_decision}' "
                f"with confidence {ml_conf:.0%}. No override needed."
            )
        if winner == "rules":
            rule_map = {
                "rule_1_zero_balance":          "Zero balance — absolute rejection",
                "rule_2_days_exceed_balance":   "Requested days exceed balance",
                "rule_3_low_confidence_approve": "Low confidence on approve — safety escalation",
            }
            rule_desc = rule_map.get(override_rule, override_rule or "unknown rule")
            return (
                f"Business rule won over ML. "
                f"Rule applied: '{rule_desc}'. "
                f"ML confidence ({ml_conf:.0%}) was insufficient to override hard constraints. "
                f"Final decision: '{final_decision}'."
            )
        return (
            f"ML model decision '{final_decision}' (conf={ml_conf:.0%}) "
            f"was accepted — no business rule violation detected."
        )

    # ── Private: Feature Importance ───────────────────────────────────────────

    def _compute_feature_importance(self, breakdown: dict, payload: dict) -> dict:
        """
        يحسب approximate importance لكل feature في القرار.
        مش الـ actual SHAP — ده heuristic للـ explainability.
        """
        leave_days    = float(breakdown.get("leave_days", 1))
        balance       = float(breakdown.get("leave_balance", 0))
        perf          = float(breakdown.get("performance_score", 0.75))
        absence       = float(breakdown.get("absence_count", 2))
        balance_ratio = float(breakdown.get("balance_ratio", 0))
        perf_bal      = float(breakdown.get("perf_balance_score", 0))
        overtime      = float(breakdown.get("overtime_hours", 0))

        # Approximate contribution weights (from training pipeline)
        importance = {
            "leave_balance":      round(min(balance_ratio / 5.0, 1.0) * 35, 1),
            "performance_score":  round(perf * 30, 1),
            "absence_count":      round(max(0, 1 - absence / 15) * 20, 1),
            "balance_ratio":      round(min(balance_ratio / 3.0, 1.0) * 35, 1),
            "perf_balance_score": round(perf_bal * 25, 1),
            "overtime_hours":     round(min(overtime / 200, 1.0) * 5, 1),
        }

        # Normalize to 100%
        total = sum(importance.values()) or 1
        normalized = {k: round(v / total * 100, 1) for k, v in importance.items()}

        # Sort descending
        return dict(sorted(normalized.items(), key=lambda x: x[1], reverse=True))

    # ── Private: Confidence Breakdown ─────────────────────────────────────────

    def _build_confidence_breakdown(
        self,
        ml_conf:    float,
        t_approve:  float,
        t_reject:   float,
        tier:       int,
        is_outlier: bool,
    ) -> dict:
        distance_from_approve = round(ml_conf - t_approve, 4)
        distance_from_reject  = round(ml_conf - t_reject, 4)
        tier_label = {1: "Auto-Approve", 2: "Gray Zone (LLM Review)", 3: "Auto-Reject"}.get(tier, "Unknown")

        return {
            "raw_confidence":          round(ml_conf, 4),
            "t_approve":               t_approve,
            "t_reject":                t_reject,
            "distance_from_approve":   distance_from_approve,
            "distance_from_reject":    distance_from_reject,
            "tier":                    tier,
            "tier_label":              tier_label,
            "is_outlier":              is_outlier,
            "outlier_penalty_applied": 0.05 if is_outlier else 0.0,
            "effective_threshold":     t_approve + (0.05 if is_outlier else 0.0),
            "verdict": (
                "borderline" if abs(distance_from_approve) < 0.03
                else "clear_approve" if ml_conf >= t_approve
                else "clear_reject" if ml_conf < t_reject
                else "gray_zone"
            ),
        }

    # ── Private: Recommendations ──────────────────────────────────────────────

    def _build_recommendations(
        self,
        conflict_type:     Optional[str],
        conflict_severity: str,
        data_issues:       list,
        ml_conf:           float,
        payload:           dict,
        breakdown:         dict,
        override_rule:     Optional[str],
    ) -> list[str]:
        recs = []

        # Balance mismatch fix
        if any("BALANCE_MISMATCH" in i for i in data_issues):
            recs.append(
                "🔧 FIX REQUIRED: Add logger.info(f'RAW leave_balance: {data[\"leave_balance\"]}') "
                "in LeaveModelHandler._build_features() to trace balance field mapping."
            )
            recs.append(
                "🔧 CHECK: Verify sanitize_input() correctly handles both "
                "'leave_balance' and 'leave_bal' field names."
            )

        # Missing fields
        if any("MISSING_FIELDS" in i for i in data_issues):
            recs.append(
                "📋 IMPROVE: Ensure API clients always send all required fields "
                "(performance_score, absence_count, years_of_experience)."
            )

        # Borderline confidence
        if conflict_type == "TIER_BOUNDARY":
            recs.append(
                "⚙️ CONSIDER: Add a ±0.02 hysteresis buffer around tier thresholds "
                "to prevent flip-flopping on borderline cases."
            )

        # Low confidence approve
        if override_rule == "rule_3_low_confidence_approve":
            recs.append(
                f"📊 INSIGHT: ML confidence {ml_conf:.0%} is consistently in the "
                f"gray zone. Retrain the model with more samples around this range, "
                "or adjust VALIDATION_MIN_CONFIDENCE_FOR_APPROVE in hr_thresholds.py."
            )

        # Outlier
        if any("CLIPPED" in i for i in data_issues):
            recs.append(
                "🧪 VALIDATE: Some input values were outside training range. "
                "Check INPUT_BOUNDS in leave_model_handler.py."
            )

        # Zero balance
        if any("ZERO_BALANCE" in i for i in data_issues):
            recs.append(
                "🚫 EXPECTED: Zero balance rejection is working correctly (Rule 1). "
                "Verify the employee's actual balance in DB matches the API payload."
            )

        if not recs:
            recs.append("✅ No action needed — decision pipeline is working as expected.")

        return recs


# ── Singleton ─────────────────────────────────────────────────────────────────
_resolver: Optional[ConflictResolver] = None


def get_conflict_resolver() -> ConflictResolver:
    global _resolver
    if _resolver is None:
        _resolver = ConflictResolver()
    return _resolver