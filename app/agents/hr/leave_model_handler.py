"""
🤖 Leave Model Handler — Production v5.1
==========================================
File: app/agents/hr/leave_model_handler.py

✅ v5.1 Patches:
    Fix 1 — Confidence Hard Cap (max=0.97, min=0.03)
    Fix 1 — Suspicious confidence warning (>= 0.99)
    Fix 1 — raw_confidence preserved for debugging
    Fix 1 — diagnose_confidence() method added
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import joblib
import numpy as np

logger = logging.getLogger(__name__)

# ── Model paths ───────────────────────────────────────────────────────────────
_BASE        = Path(__file__).resolve().parent.parent.parent
MODEL_DIR    = _BASE / "app" / "models" / "hr"
MODEL_PATH   = MODEL_DIR / "leave_approval_model.pkl"
SCALER_PATH  = MODEL_DIR / "scaler.pkl"
ENCODER_PATH = MODEL_DIR / "encoders.pkl"
META_PATH    = MODEL_DIR / "model_metadata.json"

VALID_JOB_LEVELS    = {"junior", "senior", "lead", "manager"}
VALID_SALARY_GRADES = {"a", "b", "c", "d", "e"}

INPUT_BOUNDS = {
    "leave_days":          (1,    90),
    "leave_balance":       (0,    180),
    "performance_score":   (0.0,  1.0),
    "absence_count":       (0,    100),
    "years_of_experience": (0,    50),
    "overtime_hours":      (0,    500),
}

INPUT_DEFAULTS = {
    "leave_days":          1,
    "leave_balance":       15,
    "performance_score":   0.70,
    "absence_count":       2,
    "years_of_experience": 3,
    "salary_grade":        "C",
    "job_level":           "junior",
    "overtime_hours":      0,
}

# ── FIX 1: Confidence Caps ────────────────────────────────────────────────────
CONFIDENCE_MAX = 0.97   # مفيش model حقيقي بيدي > 97%
CONFIDENCE_MIN = 0.03   # مفيش model حقيقي بيدي < 3%


def _days_to_fy_end() -> int:
    now    = datetime.utcnow()
    year   = now.year
    fy_end = datetime(year if now.month <= 6 else year + 1, 6, 30)
    return max(0, (fy_end - now).days)


# ══════════════════════════════════════════════════════════════════════════════
# Input Sanitizer
# ══════════════════════════════════════════════════════════════════════════════

def sanitize_input(data: dict) -> tuple[dict, list[str]]:
    clean    = dict(data)
    warnings = []

    for field, default in INPUT_DEFAULTS.items():
        if field not in clean or clean[field] is None:
            clean[field] = default
            warnings.append(f"missing_field:{field}=default({default})")

    for field, (lo, hi) in INPUT_BOUNDS.items():
        if field in clean:
            try:
                val = float(clean[field])
                if val < lo:
                    warnings.append(f"below_min:{field}={val}<{lo} → clipped to {lo}")
                    val = lo
                elif val > hi:
                    warnings.append(f"above_max:{field}={val}>{hi} → clipped to {hi}")
                    val = hi
                clean[field] = val
            except (TypeError, ValueError):
                warnings.append(f"invalid_type:{field}={clean[field]} → using default")
                clean[field] = INPUT_DEFAULTS.get(field, 0)

    job_level = str(clean.get("job_level", "junior")).lower().strip()
    if job_level not in VALID_JOB_LEVELS:
        warnings.append(f"unknown_job_level:'{job_level}' → fallback to 'junior'")
        clean["_unknown_job_level"] = job_level
        clean["job_level"] = "junior"
    else:
        clean["job_level"] = job_level

    salary_grade = str(clean.get("salary_grade", "C")).upper().strip()
    if salary_grade.lower() not in VALID_SALARY_GRADES:
        warnings.append(f"unknown_salary_grade:'{salary_grade}' → fallback to 'C'")
        clean["_unknown_salary_grade"] = salary_grade
        clean["salary_grade"] = "C"
    else:
        clean["salary_grade"] = salary_grade

    if "requested_days" in data and "leave_days" not in data:
        clean["leave_days"] = float(data["requested_days"])

    return clean, warnings


# ══════════════════════════════════════════════════════════════════════════════
# LeaveModelHandler
# ══════════════════════════════════════════════════════════════════════════════

class LeaveModelHandler:

    def __init__(self):
        self._model:        Optional[object]  = None
        self._scaler:       Optional[object]  = None
        self._encoders:     dict              = {}
        self._feature_cols: list[str]         = []
        self._metadata:     dict              = {}
        self._loaded:       bool              = False

    # ── Public API ────────────────────────────────────────────────────────────

    def load(self) -> bool:
        try:
            if not MODEL_PATH.exists():
                logger.warning(
                    "⚠️ [ModelHandler] Model not found at %s. "
                    "Run: python training/hr_train.py", MODEL_PATH,
                )
                return False

            self._model        = joblib.load(MODEL_PATH)
            self._scaler       = joblib.load(SCALER_PATH)
            enc_data           = joblib.load(ENCODER_PATH)
            self._encoders     = enc_data["encoders"]
            self._feature_cols = enc_data["feature_cols"]

            if META_PATH.exists():
                with open(META_PATH, "r", encoding="utf-8") as f:
                    self._metadata = json.load(f)

            self._loaded = True

            trained_at = self._metadata.get("trained_at", "unknown")
            acc        = self._metadata.get("evaluation", {}).get("accuracy", "?")
            auc        = self._metadata.get("evaluation", {}).get("roc_auc", "?")
            t          = self._metadata.get("thresholds", {})
            edge       = self._metadata.get("edge_case_testing")
            cost       = self._metadata.get("business_costs")

            logger.info(
                "✅ [ModelHandler] Loaded | trained=%s | accuracy=%s | AUC=%s | "
                "t_approve=%s | t_escalate=%s%s%s",
                trained_at[:10], acc, auc,
                t.get("approve", "?"), t.get("escalate", "?"),
                f" | edge_pass={edge['loose_rate']:.0%}" if edge and edge.get("loose_rate") else "",
                f" | monthly_cost={cost['monthly_cost_egp']:.0f}EGP"
                if cost and cost.get("monthly_cost_egp") else "",
            )
            return True

        except Exception as e:
            logger.error("❌ [ModelHandler] Failed to load model: %s", e, exc_info=True)
            self._loaded = False
            return False

    def reload(self) -> bool:
        self._loaded = False
        return self.load()

    def is_loaded(self) -> bool:
        return self._loaded

    def get_info(self) -> dict:
        if not self._loaded:
            return {"loaded": False, "path": str(MODEL_PATH)}
        return {
            "loaded":          True,
            "model_type":      self._metadata.get("model_type", "unknown"),
            "trained_at":      self._metadata.get("trained_at"),
            "data_source":     self._metadata.get("data_source"),
            "n_samples":       self._metadata.get("n_training_samples"),
            "feature_count":   len(self._feature_cols),
            "features":        self._feature_cols,
            "thresholds":      self._metadata.get("thresholds", {}),
            "accuracy":        self._metadata.get("evaluation", {}).get("accuracy"),
            "roc_auc":         self._metadata.get("evaluation", {}).get("roc_auc"),
            "f1_score":        self._metadata.get("evaluation", {}).get("f1_score"),
            "cv_auc":          self._metadata.get("evaluation", {}).get("cv_auc_mean"),
            "model_path":      str(MODEL_PATH),
            "leakage_check":   self._metadata.get("leakage_validation"),
            "edge_case_tests": self._metadata.get("edge_case_testing"),
            "business_costs":  self._metadata.get("business_costs"),
            # v5.1 additions
            "confidence_cap":  {"max": CONFIDENCE_MAX, "min": CONFIDENCE_MIN},
        }

    def predict(self, input_data: dict) -> dict:
        """
        v5.1: Confidence hard cap + raw_confidence preserved + suspicious warning.
        """
        if not self._loaded:
            self.load()

        if not self._loaded:
            logger.warning(
                "⚠️ [ModelHandler] Model not loaded — using fallback rules. "
                "Run: python training/hr_train.py then POST /model/reload"
            )
            return self._fallback_rules(input_data)

        clean_data, input_warnings = sanitize_input(input_data)
        if input_warnings:
            logger.debug("⚠️ [ModelHandler] Input warnings: %s", input_warnings)

        is_outlier = self._detect_outlier(clean_data)

        try:
            X, breakdown = self._build_features(clean_data)
            X_scaled     = self._scaler.transform(X.reshape(1, -1))
            proba        = self._model.predict_proba(X_scaled)[0]

            # ── FIX 1: Confidence Sanity Check + Hard Cap ─────────────────────
            raw_confidence = float(proba[1])

            # Red flag: مفيش model طبيعي بيدي >= 0.99
            if raw_confidence >= 0.99:
                logger.warning(
                    "⚠️ [ModelHandler] SUSPICIOUS confidence=%.4f — "
                    "possible feature leakage or overfitting. "
                    "Run: python training/hr_train.py (with leakage check enabled)",
                    raw_confidence,
                )

            # Hard cap: 0.97 max / 0.03 min
            confidence = max(CONFIDENCE_MIN, min(CONFIDENCE_MAX, raw_confidence))

            if confidence != raw_confidence:
                logger.info(
                    "📊 [ModelHandler] Confidence capped: %.4f → %.4f",
                    raw_confidence, confidence,
                )
            # ── END FIX 1 ──────────────────────────────────────────────────────

            try:
                from config.hr_thresholds import get_thresholds_from_metadata
                thresholds = get_thresholds_from_metadata(self._metadata)
            except ImportError:
                thresholds = {
                    "approve":  self._metadata.get("thresholds", {}).get("approve", 0.72),
                    "escalate": self._metadata.get("thresholds", {}).get("escalate", 0.42),
                }

            t_approve  = thresholds["approve"]
            t_escalate = thresholds.get("escalate", 0.42)

            # Outlier: raise approve threshold slightly for safety
            effective_t_approve = t_approve + (0.05 if is_outlier else 0.0)

            if confidence >= effective_t_approve:
                decision = "approve"
                tier     = 1
            elif confidence >= t_escalate:
                decision = "escalate"
                tier     = 2
            else:
                decision = "reject"
                tier     = 3

            key_factors = self._explain_decision(clean_data, confidence, decision, input_warnings)

            logger.info(
                "🤖 [ModelHandler] predict → tier=%d | %s | "
                "raw=%.4f | conf=%.4f | "
                "leave=%dd | balance=%d%s%s",
                tier, decision, raw_confidence, confidence,
                int(clean_data.get("leave_days", 1)),
                int(clean_data.get("leave_balance", 0)),
                " | ⚠️OUTLIER" if is_outlier else "",
                f" | warnings={len(input_warnings)}" if input_warnings else "",
            )

            return {
                "approved":        decision == "approve",
                "confidence":      round(confidence, 4),
                "raw_confidence":  round(raw_confidence, 4),   # ← v5.1: للـ debugging
                "decision":        decision,
                "tier":            tier,
                "breakdown":       breakdown,
                "key_factors":     key_factors,
                "input_warnings":  input_warnings,
                "is_outlier":      is_outlier,
                "model_used":      True,
                "source":          "ml_model",
            }

        except Exception as e:
            logger.error("❌ [ModelHandler] Prediction failed: %s", e, exc_info=True)
            return self._fallback_rules(input_data)

    def diagnose_confidence(self, n_samples: int = 100) -> dict:
        """
        🔍 FIX 1: Confidence Distribution Diagnostic.

        يكشف:
            - Overfitting    → pct_above_99 > 10%
            - Leakage        → raw mean > 0.90 + high pct_above_99
            - Collapsed dist → std < 0.05

        يُستدعى من: GET /model/diagnose
        """
        if not self._loaded:
            return {"error": "Model not loaded", "status": "🔴 NOT LOADED"}

        rng       = np.random.default_rng(42)
        raw_list  = []
        cap_list  = []

        for _ in range(n_samples):
            sample = {
                "leave_days":          int(rng.integers(1, 21)),
                "leave_balance":       int(rng.integers(0, 30)),
                "performance_score":   round(float(rng.beta(5, 3)), 3),
                "absence_count":       int(rng.integers(0, 15)),
                "years_of_experience": int(rng.integers(0, 20)),
                "overtime_hours":      int(rng.integers(0, 80)),
                "job_level":           rng.choice(["junior", "senior", "lead", "manager"]).item(),
                "salary_grade":        rng.choice(["A", "B", "C", "D", "E"]).item(),
            }
            pred = self.predict(sample)
            raw_list.append(pred.get("raw_confidence", pred["confidence"]))
            cap_list.append(pred["confidence"])

        raw   = np.array(raw_list)
        capped = np.array(cap_list)

        pct_above_99 = float((raw > 0.99).mean())
        pct_above_95 = float((raw > 0.95).mean())
        capped_count = int((raw != capped).sum())

        red_flags = []
        if pct_above_99 > 0.10:
            red_flags.append(
                f"🚨 LEAKAGE/OVERFIT: {pct_above_99:.0%} of samples have raw confidence > 99%"
            )
        if pct_above_95 > 0.40:
            red_flags.append(
                f"⚠️ HIGH CONFIDENCE BIAS: {pct_above_95:.0%} > 95% — model not discriminating well"
            )
        if float(raw.std()) < 0.05:
            red_flags.append(
                f"⚠️ LOW VARIANCE: std={raw.std():.4f} — collapsed predictions"
            )

        buckets = {
            "0.00–0.20": int((raw < 0.20).sum()),
            "0.20–0.40": int(((raw >= 0.20) & (raw < 0.40)).sum()),
            "0.40–0.60": int(((raw >= 0.40) & (raw < 0.60)).sum()),
            "0.60–0.80": int(((raw >= 0.60) & (raw < 0.80)).sum()),
            "0.80–0.95": int(((raw >= 0.80) & (raw < 0.95)).sum()),
            "0.95–1.00 ⚠️": int((raw >= 0.95).sum()),
        }

        status = (
            "🔴 PROBLEMATIC" if red_flags
            else "🟡 REVIEW SUGGESTED" if pct_above_95 > 0.15
            else "✅ HEALTHY"
        )

        return {
            "status":        status,
            "n_samples":     n_samples,
            "raw_stats": {
                "mean":         round(float(raw.mean()), 4),
                "std":          round(float(raw.std()), 4),
                "min":          round(float(raw.min()), 4),
                "max":          round(float(raw.max()), 4),
                "pct_above_99": round(pct_above_99, 3),
                "pct_above_95": round(pct_above_95, 3),
            },
            "cap_applied_count": capped_count,
            "cap_applied_pct":   round(capped_count / n_samples, 3),
            "distribution":      buckets,
            "red_flags":         red_flags,
            "recommendation": (
                "🔧 Retrain: python training/hr_train.py — ensure leakage check is ON"
                if red_flags else
                "✅ Confidence distribution looks realistic"
            ),
        }

    # ── Private helpers ───────────────────────────────────────────────────────

    def _detect_outlier(self, data: dict) -> bool:
        return any([
            float(data.get("leave_days",        1)) > 30,
            float(data.get("leave_balance",     15)) > 90,
            float(data.get("absence_count",      2)) > 30,
            float(data.get("overtime_hours",     0)) > 200,
            float(data.get("performance_score", 0.7)) == 0.0,
            float(data.get("performance_score", 0.7)) == 1.0,
        ])

    def _build_features(self, data: dict) -> tuple:
        leave_days   = float(data.get("leave_days",   1))
        leave_bal    = float(data.get("leave_balance", 15))
        perf_score   = float(data.get("performance_score", 0.70))
        absence      = float(data.get("absence_count", 2))
        job_level    = str(data.get("job_level", "junior")).lower()
        years_exp    = float(data.get("years_of_experience", 3))
        salary_grade = str(data.get("salary_grade", "C")).upper()
        overtime     = float(data.get("overtime_hours", 0))

        balance_ratio    = min(leave_bal / max(leave_days, 1), 5.0)
        days_to_fy       = float(_days_to_fy_end())
        absence_per_year = min(absence / max(years_exp, 1), 10.0)
        perf_bal_score   = min(perf_score * min(balance_ratio, 2.0) / 2.0, 1.0)

        breakdown = {
            "leave_days":          leave_days,
            "leave_balance":       leave_bal,
            "performance_score":   perf_score,
            "absence_count":       absence,
            "years_of_experience": years_exp,
            "overtime_hours":      overtime,
            "balance_ratio":       round(balance_ratio, 2),
            "days_to_fy_end":      days_to_fy,
            "absence_per_year":    round(absence_per_year, 2),
            "perf_balance_score":  round(perf_bal_score, 2),
            "job_level":           job_level,
            "salary_grade":        salary_grade,
        }

        job_level_enc = self._safe_encode("job_level", job_level)
        salary_enc    = self._safe_encode("salary_grade", salary_grade.lower())

        feature_map = {
            "leave_days":          leave_days,
            "leave_balance":       leave_bal,
            "performance_score":   perf_score,
            "absence_count":       absence,
            "years_of_experience": years_exp,
            "overtime_hours":      overtime,
            "balance_ratio":       balance_ratio,
            "days_to_fy_end":      days_to_fy,
            "absence_per_year":    absence_per_year,
            "perf_balance_score":  perf_bal_score,
            "job_level_enc":       job_level_enc,
            "salary_grade_enc":    salary_enc,
        }

        X = np.array(
            [feature_map.get(col, 0.0) for col in self._feature_cols],
            dtype=np.float32,
        )
        return X, breakdown

    def _safe_encode(self, col: str, value: str) -> int:
        le = self._encoders.get(col)
        if le is None:
            return 0
        try:
            return int(le.transform([value])[0])
        except ValueError:
            logger.debug(
                "⚠️ [ModelHandler] Unknown '%s' value: '%s' — fallback 0 (classes: %s)",
                col, value, list(le.classes_),
            )
            return 0

    def _explain_decision(
        self,
        data:           dict,
        confidence:     float,
        decision:       str,
        input_warnings: list[str] = None,
    ) -> list[str]:
        factors = []

        leave_days    = float(data.get("leave_days", 1))
        balance       = float(data.get("leave_balance", 15))
        perf          = float(data.get("performance_score", 0.70))
        absence       = float(data.get("absence_count", 2))
        overtime      = float(data.get("overtime_hours", 0))
        balance_ratio = balance / max(leave_days, 1)

        if balance == 0:
            factors.append("🚫 رصيد الإجازة صفر — لا يمكن الموافقة")
        elif balance < leave_days:
            factors.append(f"⚠️ رصيد ({balance:.0f}d) أقل من الطلب ({leave_days:.0f}d)")
        elif balance_ratio >= 3:
            factors.append(f"✅ رصيد ممتاز ({balance:.0f}d متاح)")
        elif balance_ratio >= 1.5:
            factors.append(f"✅ رصيد كافي ({balance:.0f}d)")
        else:
            factors.append(f"ℹ️ رصيد محدود ({balance:.0f}d لـ {leave_days:.0f}d مطلوب)")

        if perf >= 0.85:
            factors.append(f"✅ أداء ممتاز ({perf:.0%})")
        elif perf >= 0.65:
            factors.append(f"ℹ️ أداء جيد ({perf:.0%})")
        elif perf >= 0.45:
            factors.append(f"⚠️ أداء مقبول ({perf:.0%})")
        else:
            factors.append(f"🚫 أداء منخفض ({perf:.0%}) — يؤثر على القرار")

        if absence == 0:
            factors.append("✅ سجل حضور مثالي")
        elif absence <= 3:
            factors.append(f"✅ حضور جيد ({absence:.0f} غياب)")
        elif absence <= 8:
            factors.append(f"ℹ️ غياب متوسط ({absence:.0f})")
        else:
            factors.append(f"⚠️ غياب مرتفع ({absence:.0f}) — تأثير سلبي")

        if overtime >= 40:
            factors.append(f"✅ ساعات إضافية عالية ({overtime:.0f}h) — يدعم الموافقة")

        if input_warnings:
            missing = [w for w in input_warnings if w.startswith("missing_field")]
            unknown = [w for w in input_warnings if "unknown" in w]
            clipped = [w for w in input_warnings if "above_max" in w or "below_min" in w]
            if missing:
                factors.append(f"ℹ️ بيانات ناقصة — قيم افتراضية ({len(missing)} حقل)")
            if unknown:
                factors.append("⚠️ قيم غير معروفة — يُنصح بمراجعة البيانات")
            if clipped:
                factors.append("ℹ️ قيم خارج النطاق — تم تصحيحها تلقائياً")

        if decision == "escalate":
            factors.append(f"📋 محولة للمدير للمراجعة (ثقة = {confidence:.0%})")

        return factors

    def _fallback_rules(self, data: dict) -> dict:
        clean_data, input_warnings = sanitize_input(data)

        leave_days    = float(clean_data.get("leave_days", 1))
        balance       = float(clean_data.get("leave_balance", 15))
        perf          = float(clean_data.get("performance_score", 0.70))
        absence       = float(clean_data.get("absence_count", 2))
        balance_ratio = balance / max(leave_days, 1)

        score = (
            min(balance_ratio / 3.0, 1.0) * 0.40
            + perf                          * 0.35
            + max(0, 1 - absence / 10)      * 0.25
        )

        try:
            from config.hr_thresholds import TIER1_APPROVE_THRESHOLD, TIER3_REJECT_THRESHOLD
            t_approve  = TIER1_APPROVE_THRESHOLD
            t_escalate = TIER3_REJECT_THRESHOLD
        except ImportError:
            t_approve  = 0.72
            t_escalate = 0.42

        if balance == 0 or leave_days > balance * 1.5:
            confidence = 0.10
            decision   = "reject"
            tier       = 3
        elif score >= t_approve:
            confidence = 0.82
            decision   = "approve"
            tier       = 1
        elif score >= t_escalate:
            confidence = 0.55
            decision   = "escalate"
            tier       = 2
        else:
            confidence = 0.25
            decision   = "reject"
            tier       = 3

        logger.warning(
            "⚠️ [ModelHandler] FALLBACK RULES activated — "
            "model not loaded | decision=%s | score=%.2f | "
            "To fix: python training/hr_train.py && POST /model/reload",
            decision, score,
        )

        return {
            "approved":        decision == "approve",
            "confidence":      confidence,
            "raw_confidence":  confidence,   # same in fallback
            "decision":        decision,
            "tier":            tier,
            "breakdown":       {
                "balance_ratio": round(balance_ratio, 2),
                "score":         round(score, 3),
                "note":          "fallback_rules — ML model not loaded",
            },
            "key_factors": [
                f"🔧 Fallback rules used — score: {score:.2f}",
                "⚠️ ML model غير محمل — نتيجة تقريبية",
                "💡 Fix: python training/hr_train.py ثم POST /model/reload",
            ],
            "input_warnings": input_warnings,
            "is_outlier":     False,
            "model_used":     False,
            "source":         "fallback_rules",
        }


# ── Singleton ─────────────────────────────────────────────────────────────────
_handler_instance: Optional[LeaveModelHandler] = None


def get_model_handler() -> LeaveModelHandler:
    global _handler_instance
    if _handler_instance is None:
        _handler_instance = LeaveModelHandler()
        _handler_instance.load()
    return _handler_instance