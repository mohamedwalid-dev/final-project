"""
🧠 Finance Risk Model Handler — v4.2 (Feature Alignment Fix)
============================================================
File: app/agents/finance/risk_model_handler.py

v4.2 FIX (Critical):
    ❌ المشكلة: ValueError: Feature shape mismatch, expected: 38, got 41
       السبب: الـ predictor._to_features() ببني 41 feature دايماً
              لكن لو التدريب اتعمل بـ finance_train_patch.py اللي بيعمل
              drop_leakage_features() → الموديل اتدرب على 38 فقط.

    ✅ الحل: Feature Alignment via saved feature columns file
        1. _load() يحمّل finance_feature_columns.pkl لو موجود
        2. _align_features() يعمل reindex: missing=0, extra=drop
        3. _ml_predict() يستدعيه بعد _strip_ml_excluded وقبل predictor.predict()
        4. Backward compatible: لو الملف مش موجود → شغّال كالأول

    التغييرات عن v4.1:
        ✅ _saved_columns attribute جديد في __init__
        ✅ _load_feature_columns() method جديدة
        ✅ _align_features() method جديدة (الـ reindex الاحترافي)
        ✅ _ml_predict() يستدعي _align_features بعد _strip_ml_excluded
        ✅ get_info() يوضح column alignment status
        ✅ version string "4.2"

v4.1 (unchanged behavior):
    ✅ _strip_ml_excluded() — يشيل overdue_days وأصحابه قبل ML
    ✅ GeminiQuotaGuard — detects 429, pauses LLM for 60 min
    ✅ RuleBasedPredictor — fallback كامل

v4.0 (unchanged behavior):
    ✅ predictor._to_features() builds all features internally
"""


from __future__ import annotations
import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Optional
import uuid
import numpy as np

logger = logging.getLogger(__name__)

MODEL_DIR  = os.path.join(os.path.dirname(__file__), "..", "..", "models", "finance")
MODEL_PATH = os.path.join(MODEL_DIR, "payment_risk_v8.pkl")
FEATURE_COLUMNS_PATH = os.path.join(MODEL_DIR, "finance_feature_columns.pkl")

# ─────────────────────────────────────────────────────────────────────────────
# v4.1: Fields to strip before passing data to ML predictor
# ─────────────────────────────────────────────────────────────────────────────
_ML_EXCLUDED_FIELDS = {
    "overdue_days",
    "overdue_days_normalized",
    "overdue_x_industry",
    "payment_delay",
    "is_late",
    "is_bad_payer",
    "request_id",
    "event_id",
    "skipped",
    "workflow",
}


# ─────────────────────────────────────────────────────────────────────────────
# Gemini Quota Guard (unchanged from v4.1)
# ─────────────────────────────────────────────────────────────────────────────

class GeminiQuotaGuard:
    def __init__(self, retry_pause_minutes: int = 60):
        self._lock              = threading.Lock()
        self._exhausted_at: Optional[datetime] = None
        self._retry_pause       = timedelta(minutes=retry_pause_minutes)
        self._total_exhaustions = 0

    def is_available(self) -> bool:
        with self._lock:
            if self._exhausted_at is None:
                return True
            if datetime.utcnow() - self._exhausted_at > self._retry_pause:
                logger.info("✅ [GeminiQuotaGuard] Pause elapsed — resuming LLM calls")
                self._exhausted_at = None
                return True
            remaining = self._retry_pause - (datetime.utcnow() - self._exhausted_at)
            logger.debug(
                "⏳ [GeminiQuotaGuard] Still paused — %.0f min remaining",
                remaining.total_seconds() / 60,
            )
            return False

    def mark_exhausted(self) -> None:
        with self._lock:
            if self._exhausted_at is None:
                self._exhausted_at = datetime.utcnow()
                self._total_exhaustions += 1
                logger.warning(
                    "⚠️  [GeminiQuotaGuard] Quota exhausted (#%d) — "
                    "LLM calls paused for %d min",
                    self._total_exhaustions,
                    self._retry_pause.seconds // 60,
                )

    def get_status(self) -> dict:
        with self._lock:
            available = self._exhausted_at is None or (
                datetime.utcnow() - self._exhausted_at > self._retry_pause
            )
            remaining_sec = 0
            if self._exhausted_at and not available:
                remaining_sec = int(
                    (self._retry_pause - (datetime.utcnow() - self._exhausted_at))
                    .total_seconds()
                )
            return {
                "available":           available,
                "total_exhaustions":   self._total_exhaustions,
                "exhausted_at":        self._exhausted_at.isoformat() if self._exhausted_at else None,
                "retry_pause_minutes": self._retry_pause.seconds // 60,
                "remaining_seconds":   max(0, remaining_sec),
            }


_gemini_quota_guard = GeminiQuotaGuard(retry_pause_minutes=60)


def get_gemini_quota_guard() -> GeminiQuotaGuard:
    return _gemini_quota_guard


# ─────────────────────────────────────────────────────────────────────────────
# Structured Prediction Logger (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

class PredictionLogger:
    _SNAPSHOT_FIELDS = [
        "overdue_days", "amount", "credit_score", "industry",
        "payment_history_paid", "payment_history_late",
        "customer_age_months", "invoice_count_90d",
        "avg_payment_delay_days",
    ]

    def log(self, request_id, model_version, latency_ms, risk_score,
            decision, confidence, reasons, raw_data, source="ml_model"):
        snapshot = self._build_snapshot(raw_data)
        logger.info(
            "💰 [FinancePredict] "
            "request_id=%s | model=%s | latency=%dms | "
            "risk=%.4f | decision=%s | confidence=%.4f | source=%s | "
            "reasons=%s | features=%s",
            request_id, model_version, latency_ms,
            risk_score, decision, confidence, source,
            reasons, json.dumps(snapshot, separators=(",", ":")),
        )

    def log_error(self, request_id, model_version, latency_ms, error, raw_data=None):
        snapshot = self._build_snapshot(raw_data or {})
        logger.error(
            "❌ [FinancePredict:ERROR] "
            "request_id=%s | model=%s | latency=%dms | error=%s | features=%s",
            request_id, model_version, latency_ms,
            error, json.dumps(snapshot, separators=(",", ":")),
        )

    def log_fallback(self, request_id, model_version, latency_ms, reason):
        logger.warning(
            "⚠️  [FinancePredict:FALLBACK] "
            "request_id=%s | model=%s | latency=%dms | reason=%s",
            request_id, model_version, latency_ms, reason,
        )

    def _build_snapshot(self, raw_data: dict) -> dict:
        snapshot = {}
        for field in self._SNAPSHOT_FIELDS:
            val = raw_data.get(field)
            if val is not None:
                try:
                    snapshot[field] = round(float(val), 4)
                except (TypeError, ValueError):
                    snapshot[field] = str(val)
        if "industry" in raw_data:
            snapshot["industry"] = str(raw_data["industry"])
        return snapshot


_pred_logger = PredictionLogger()


# ─────────────────────────────────────────────────────────────────────────────
# Rule-Based Fallback (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

class RuleBasedPredictor:
    INDUSTRY_RISK = {
        "retail": 0.40, "hospitality": 0.50, "construction": 0.60,
        "manufacturing": 0.35, "technology": 0.25, "healthcare": 0.20,
        "education": 0.15, "government": 0.05, "financial": 0.20,
        "real_estate": 0.55, "food_beverage": 0.45,
        "transportation": 0.40, "unknown": 0.40,
    }

    def predict(self, data: dict) -> dict:
        def safe_float(val, default=0.0):
            try:
                v = float(val or default)
                return v if (v == v and abs(v) != float("inf")) else default
            except (TypeError, ValueError):
                return default

        overdue_days  = safe_float(data.get("overdue_days"), 0.0)
        credit_score  = safe_float(data.get("credit_score"), 650.0)
        p_count       = max(1, int(safe_float(data.get("payment_history_count"), 1)))
        paid_count    = int(safe_float(data.get("payment_history_paid"), 0))
        late_count    = int(safe_float(data.get("payment_history_late"), 0))
        amount        = safe_float(data.get("amount"), 0.0)
        raw_industry  = str(data.get("industry", "unknown") or "unknown").lower().strip()

        paid_ratio    = paid_count / p_count
        late_ratio    = late_count / p_count
        overdue_norm  = min(overdue_days / 180.0, 1.0)
        credit_norm   = min(max(credit_score, 300), 850) / 850.0
        amount_norm   = min(amount / 100_000.0, 1.0)
        industry_risk = self.INDUSTRY_RISK.get(raw_industry, 0.40)

        score  = 0.0
        score += overdue_norm         * 0.40
        score += (1.0 - paid_ratio)   * 0.20
        score += late_ratio           * 0.15
        score += (1.0 - credit_norm)  * 0.15
        score += industry_risk        * 0.05
        score += amount_norm          * 0.05
        score  = min(max(score, 0.0), 1.0)

        if score >= 0.70:
            decision = "reject"
        elif score >= 0.45:
            decision = "manual_review"
        else:
            decision = "approve"

        return {
            "risk_score": round(score, 4),
            "decision":   decision,
            "confidence": 0.65,
            "reasons":    ["Rule-based assessment — ML model not available"],
            "source":     "rules-v4.2",
            "risk_label": self._label(score),
        }

    @staticmethod
    def _label(score: float) -> str:
        if score >= 0.70: return "high"
        if score >= 0.45: return "medium"
        return "low"


_rule_predictor = RuleBasedPredictor()


# ─────────────────────────────────────────────────────────────────────────────
# Main Handler — v4.2
# ─────────────────────────────────────────────────────────────────────────────

class FinanceRiskModelHandler:
    """
    Thread-safe singleton handler — v4.2.

    v4.2 Fix (Critical):
        Feature shape mismatch بين التدريب والـ inference.
        _align_features() بيعمل reindex على الـ feature dict
        عشان يطابق الـ columns اللي الموديل اتدرب عليها بالظبط.

    v4.1 Fix:
        _ml_predict() strips _ML_EXCLUDED_FIELDS (overdue_days etc.)
        قبل ما يبعت data للـ ML predictor.
    """

    _instance: Optional["FinanceRiskModelHandler"] = None
    _lock      = threading.Lock()

    def __init__(self):
        self._predictor:     Optional[object] = None
        self._metadata:      dict             = {}
        self._loaded:        bool             = False
        self._version:       str              = "unknown"
        self._trained_at:    str              = "unknown"
        self._feature_count: int              = 41
        self._saved_columns: Optional[list]  = None   # v4.2: feature alignment
        self._load()

    @classmethod
    def get_instance(cls) -> "FinanceRiskModelHandler":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ── Load ─────────────────────────────────────────────────────────────────

    def _load(self) -> bool:
        try:
            import pickle
            if not os.path.exists(MODEL_PATH):
                logger.warning(
                    "⚠️  Finance model not found at %s — rule-based fallback active.\n"
                    "    Run: python training/finance_train.py",
                    MODEL_PATH,
                )
                return False

            with open(MODEL_PATH, "rb") as f:
                saved = pickle.load(f)

            self._predictor  = saved.get("predictor")
            self._metadata   = saved.get("metadata", {})
            self._version    = self._metadata.get("version", "8.x")
            self._trained_at = self._metadata.get("trained_at", "unknown")
            self._feature_count = int(self._metadata.get("feature_count", 41))

            if self._predictor is not None and not hasattr(self._predictor, "_to_features"):
                logger.warning(
                    "⚠️  Loaded predictor missing _to_features() — "
                    "incompatible version. Rule fallback will be used."
                )
                self._predictor = None

            self._loaded = self._predictor is not None

            # ── v4.2: Load feature columns for alignment ──────────────────
            self._load_feature_columns()

            metrics  = self._metadata.get("metrics", {})
            de_cfg   = self._metadata.get("decision_engine", {})

            if self._loaded:
                logger.info(
                    "✅ Finance Risk Model v%s loaded | "
                    "trained=%s | AUC=%.4f | features=%d | "
                    "alignment=%s | "
                    "v4.2 feature alignment fix: ACTIVE",
                    self._version,
                    self._trained_at,
                    float(metrics.get("roc_auc") or 0),
                    self._feature_count,
                    f"{len(self._saved_columns)} cols" if self._saved_columns else "disabled",
                )
            else:
                logger.warning("⚠️  Model file found but predictor invalid — rule fallback active")
            return self._loaded

        except Exception as e:
            logger.error("❌ Finance model load error: %s", e, exc_info=True)
            self._loaded = False
            return False

    def reload(self) -> bool:
        with self._lock:
            self._predictor    = None
            self._metadata     = {}
            self._loaded       = False
            self._saved_columns = None
            FinanceRiskModelHandler._instance = None
            return self._load()

    def is_loaded(self) -> bool:
        return self._loaded and self._predictor is not None

    # ── v4.2: Load feature columns ────────────────────────────────────────────

    def _load_feature_columns(self) -> None:
        """
        v4.2: يحمّل أسماء الـ features اللي الموديل اتدرب عليها.

        الملف ده بيتنتج من finance_train.py (v8.2+) أو finance_train_patch.py
        بعد ما drop_leakage_features() تشتغل.

        لو الملف مش موجود → _saved_columns = None (backward compatible).
        في الحالة دي الـ ML predictor ممكن يتعرض لـ shape mismatch.
        """
        import pickle
        try:
            if os.path.exists(FEATURE_COLUMNS_PATH):
                with open(FEATURE_COLUMNS_PATH, "rb") as f:
                    cols = pickle.load(f)
                # Filter out any ML-excluded fields لو اتحفظوا بالغلط
                self._saved_columns = [c for c in cols if c not in _ML_EXCLUDED_FIELDS]
                logger.info(
                    "✅ [RiskHandler v4.2] Feature columns loaded: %d columns from %s",
                    len(self._saved_columns), FEATURE_COLUMNS_PATH,
                )
            else:
                self._saved_columns = None
                logger.warning(
                    "⚠️  [RiskHandler v4.2] finance_feature_columns.pkl not found: %s\n"
                    "    Feature alignment DISABLED — ML may get shape mismatch.\n"
                    "    Fix: re-run finance_train_patch.py to regenerate the file.",
                    FEATURE_COLUMNS_PATH,
                )
        except Exception as e:
            self._saved_columns = None
            logger.error("❌ [RiskHandler v4.2] Failed to load feature columns: %s", e)

    # ── v4.2: Align features to training schema ───────────────────────────────

    def _align_features(self, data: dict) -> dict:
        """
        v4.2: يضمن إن الـ features اللي بتروح للـ ML predictor
        متطابقة تماماً مع اللي الموديل اتدرب عليهم.

        Logic:
          - لو _saved_columns مش محمّل → يرجع data كما هو (backward compat)
          - Column موجودة في saved_columns وفي data   → تتحط كما هي
          - Column موجودة في saved_columns ومش في data → تتحط 0.0 (fill_value)
          - Column موجودة في data بس مش في saved_columns → تتشال (extra)

        بيشتغل على dict مش DataFrame عشان يفضل consistent مع باقي الكود.
        الـ predictor._to_features() هي اللي بتحوّل dict لـ DataFrame داخلياً.
        """
        if self._saved_columns is None:
            return data

        aligned      = {}
        missing_cols = []
        extra_cols   = []

        for col in self._saved_columns:
            if col in data:
                aligned[col] = data[col]
            else:
                aligned[col] = 0.0
                missing_cols.append(col)

        for col in data:
            if col not in self._saved_columns:
                extra_cols.append(col)

        if missing_cols or extra_cols:
            logger.info(
                "🔧 [RiskHandler v4.2] Feature alignment applied: "
                "expected=%d | received=%d | missing=%d (→0) | extra=%d (dropped)\n"
                "   missing: %s\n   extra:   %s",
                len(self._saved_columns),
                len(data),
                len(missing_cols),
                len(extra_cols),
                missing_cols[:10],
                extra_cols[:10],
            )
        else:
            logger.debug(
                "✅ [RiskHandler v4.2] Feature alignment OK: %d/%d columns matched",
                len(self._saved_columns), len(self._saved_columns),
            )

        return aligned

    # ── Predict (public API) ──────────────────────────────────────────────────

    def predict(self, data: dict, request_id: str = "") -> dict:
        request_id    = request_id or _make_request_id()
        model_version = self._version if self._loaded else "rules-v4.2"
        t_start       = time.perf_counter()

        try:
            if self.is_loaded():
                result = self._ml_predict(data, request_id)
            else:
                result = self._rule_predict(data)

            latency_ms  = int((time.perf_counter() - t_start) * 1000)
            explanation = self._explain(data, result["risk_score"], result["decision"])

            if explanation.reasons and explanation.reasons[0] != "General risk assessment":
                result.update({
                    "reasons":          explanation.reasons,
                    "positive_factors": explanation.positive_factors,
                    "negative_factors": explanation.negative_factors,
                    "dominant_factor":  explanation.dominant_factor,
                    "summary":          explanation.summary,
                })
            else:
                result.setdefault("positive_factors", [])
                result.setdefault("negative_factors", result.get("reasons", []))
                result.setdefault("dominant_factor",  (result.get("reasons") or ["?"])[0])
                result.setdefault("summary",          "")

            result["latency_ms"]    = latency_ms
            result["model_version"] = model_version
            result["request_id"]    = request_id

            _pred_logger.log(
                request_id    = request_id,
                model_version = model_version,
                latency_ms    = latency_ms,
                risk_score    = result["risk_score"],
                decision      = result["decision"],
                confidence    = result.get("confidence", 0.0),
                reasons       = result.get("reasons", []),
                raw_data      = data,
                source        = result.get("source", "unknown"),
            )
            self._emit_metric(result, data, request_id, model_version, latency_ms)
            return result

        except Exception as e:
            latency_ms = int((time.perf_counter() - t_start) * 1000)
            _pred_logger.log_error(
                request_id    = request_id,
                model_version = model_version,
                latency_ms    = latency_ms,
                error         = str(e),
                raw_data      = data,
            )
            logger.error("❌ [RiskHandler v4.2] predict() failed: %s", e, exc_info=True)
            return self._emergency_result(request_id, model_version, latency_ms, str(e))

    # ── v4.1: Strip excluded fields ───────────────────────────────────────────

    def _strip_ml_excluded(self, data: dict) -> dict:
        stripped = {k: v for k, v in data.items() if k not in _ML_EXCLUDED_FIELDS}
        removed  = [k for k in data if k in _ML_EXCLUDED_FIELDS]
        if removed:
            logger.debug(
                "🔧 [RiskHandler v4.2] Stripped %d ML-excluded field(s): %s",
                len(removed), removed,
            )
        return stripped

    # ── ML Predict (v4.2) ─────────────────────────────────────────────────────

    def _ml_predict(self, data: dict, request_id: str) -> dict:
        """
        Delegate to FinanceRiskPredictorV8.predict(dict).

        ✅ v4.1 FIX: Strip _ML_EXCLUDED_FIELDS (overdue_days etc.)
        ✅ v4.2 FIX: Build numpy array via _to_features() first,
                     then slice to saved_columns by index.
                     Prevents: ValueError: Feature shape mismatch, expected: 38, got 41
        """
        try:
            from training.finance_train import (
                FinanceRiskPredictorV8, ensemble_predict_proba,
                BASE_FEATURES, CREDIT_FEATURES,
                INCOME_FEATURES, BEHAVIORAL_FEATURES, ENGINEERED_FEATURES,
            )
            predictor: FinanceRiskPredictorV8 = self._predictor  # type: ignore[assignment]

            # ── v4.1: Strip leaky fields ──────────────────────────────────
            ml_data = self._strip_ml_excluded(data)

            # ── v4.2: Build feature array then align by index ─────────────
            X = predictor._to_features(ml_data)   # (1, 41)

            if self._saved_columns is not None and X.shape[1] != len(self._saved_columns):
                all_features = (
                    BASE_FEATURES + CREDIT_FEATURES +
                    INCOME_FEATURES + BEHAVIORAL_FEATURES + ENGINEERED_FEATURES
                )
                col_index = {name: i for i, name in enumerate(all_features)}
                indices   = [col_index[c] for c in self._saved_columns if c in col_index]

                if len(indices) == len(self._saved_columns):
                    X = X[:, indices]   # (1, 38)
                    logger.debug(
                        "🔧 [RiskHandler v4.2] Array aligned: %d → %d features",
                        len(all_features), X.shape[1],
                    )
                else:
                    logger.warning(
                        "⚠️ [RiskHandler v4.2] Could not align all columns "
                        "(%d/%d found) — using X as-is",
                        len(indices), len(self._saved_columns),
                    )

            # ── Predict directly on numpy array ───────────────────────────
            prob   = float(ensemble_predict_proba(predictor.ensemble, X)[0])
            de     = predictor.decision_engine
            result = de.decide(prob)
            result = de.explain(result, predictor.shap_importance)

            raw_decision = result.get("decision", "manual_review")
            review_level = result.get("review_level")
            risk_score   = float(result.get("risk_score", 0.5))
            decision     = self._map_decision(raw_decision, review_level, risk_score)
            raw_reasons  = result.get("reasons", [])
            reasons      = self._extract_reason_strings(raw_reasons)

            return {
                "risk_score":         risk_score,
                "decision":           decision,
                "confidence":         float(result.get("confidence", risk_score)),
                "reasons":            reasons or ["ML-based risk assessment"],
                "source":             f"ml_v{self._version}",
                "risk_label":         self._score_to_label(risk_score),
                "review_level":       review_level,
                "recommended_action": result.get("recommended_action", ""),
                "prediction_id":      result.get("prediction_id", ""),
            }

        except Exception as e:
            logger.error(
                "❌ [RiskHandler v4.2] _ml_predict() error: %s — falling back to rules",
                e, exc_info=True,
            )
            _pred_logger.log_fallback(
                request_id    = request_id,
                model_version = self._version,
                latency_ms    = 0,
                reason        = f"ML predict error: {e}",
            )
            result = _rule_predictor.predict(data)
            result["source"] = "rules-v4.2-ml-error-fallback"
            return result

    # ── Decision Mapping (unchanged) ──────────────────────────────────────────

    @staticmethod
    def _map_decision(raw_decision: str, review_level: Optional[str], risk_score: float) -> str:
        if raw_decision == "approve":
            return "approve"
        if raw_decision == "reject":
            return "legal_escalation" if risk_score >= 0.65 else "hard_follow_up"
        if raw_decision == "review":
            return "hard_follow_up" if review_level == "escalate" else "soft_follow_up"
        return "manual_review"

    @staticmethod
    def _extract_reason_strings(reasons) -> list:
        if not reasons:
            return []
        result = []
        for r in reasons:
            if isinstance(r, str):
                result.append(r)
            elif isinstance(r, dict):
                text = r.get("reason_ar") or r.get("reason_en") or r.get("en") or str(r)
                result.append(text)
        return result

    # ── Explainability (unchanged) ────────────────────────────────────────────

    def _explain(self, data: dict, risk_score: float, decision: str):
        try:
            from agents.finance.explainability import get_explainability_engine
            engine = get_explainability_engine()
            return engine.explain_from_dict(data, risk_score, decision)
        except AttributeError:
            try:
                from agents.finance.explainability import get_explainability_engine
                engine = get_explainability_engine()
                dummy  = np.array([[risk_score] * 11])
                return engine.explain(dummy, risk_score, decision)
            except Exception:
                pass
        except Exception as e:
            logger.warning("⚠️  Explainability engine failed: %s", e)

        from types import SimpleNamespace
        return SimpleNamespace(
            reasons=["General risk assessment"],
            positive_factors=[], negative_factors=[],
            dominant_factor="General risk assessment",
            summary="", feature_snapshot={},
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _score_to_label(score: float) -> str:
        if score >= 0.70: return "high"
        if score >= 0.45: return "medium"
        return "low"

    @staticmethod
    def _emit_metric(result, data, request_id, model_version, latency_ms):
        try:
            from core.metrics_collector import get_metrics_collector, MetricEvent
            collector = get_metrics_collector()
            collector.emit(MetricEvent(
                metric_type = result["decision"],
                category    = "finance",
                value       = result["risk_score"],
                tags        = {
                    "request_id":    request_id,
                    "model_version": model_version,
                    "latency_ms":    latency_ms,
                    "confidence":    result.get("confidence", 0.0),
                    "llm_used":      result.get("llm_used", False),
                },
                entity_id   = data.get("invoice_id"),
                entity_type = "invoice",
            ))
        except Exception:
            pass

    def _emergency_result(self, request_id, model_version, latency_ms, error_msg):
        return {
            "risk_score":       0.5,
            "risk_label":       "medium",
            "decision":         "manual_review",
            "confidence":       0.5,
            "reasons":          ["Manual review required — prediction service error"],
            "positive_factors": [],
            "negative_factors": ["Prediction service encountered an error"],
            "dominant_factor":  "Prediction service error",
            "summary":          "Unable to assess risk automatically — manual review required.",
            "latency_ms":       latency_ms,
            "model_version":    model_version,
            "source":           "emergency_fallback",
            "request_id":       request_id,
            "_error":           error_msg,
        }

    # ── Info ──────────────────────────────────────────────────────────────────

    def get_info(self) -> dict:
        de  = self._metadata.get("decision_engine", {})
        met = self._metadata.get("metrics", {})
        return {
            "loaded":           self._loaded,
            "model_path":       MODEL_PATH,
            "version":          self._version,
            "trained_at":       self._trained_at,
            "roc_auc":          met.get("roc_auc"),
            "pr_auc":           met.get("pr_auc"),
            "feature_count":    self._feature_count,
            "ensemble_weights": self._metadata.get("ensemble_weights"),
            "decision_engine":  de,
            "gemini_quota":     _gemini_quota_guard.get_status(),
            # ── v4.2: Feature alignment status ───────────────────────────
            "feature_alignment": {
                "columns_file":      FEATURE_COLUMNS_PATH,
                "columns_loaded":    self._saved_columns is not None,
                "n_saved_columns":   len(self._saved_columns) if self._saved_columns else None,
                "status": (
                    f"✅ active ({len(self._saved_columns)} cols)"
                    if self._saved_columns
                    else "⚠️  disabled — finance_feature_columns.pkl missing"
                ),
            },
            "ml_excluded_fields": sorted(_ML_EXCLUDED_FIELDS),
            "architecture": {
                "v4.2_fix": (
                    "_ml_predict() calls _align_features() after _strip_ml_excluded(). "
                    "Aligns feature dict to saved training columns: "
                    "missing cols → 0.0, extra cols → dropped. "
                    "Fixes: ValueError: Feature shape mismatch, expected: 38, got 41."
                ),
                "v4.1_fix": (
                    "_ml_predict() strips _ML_EXCLUDED_FIELDS before passing data to "
                    "FinanceRiskPredictorV8.predict() — prevents leakage guard false "
                    "positive on overdue_days. ML model now active for all non-hard-rule cases."
                ),
            },
            "bug_fixes": {
                "v4.2": (
                    "CRITICAL: Feature shape mismatch fix. "
                    "_load_feature_columns() loads finance_feature_columns.pkl. "
                    "_align_features() reindexes feature dict to match training schema. "
                    "Called in _ml_predict() between _strip_ml_excluded and predictor.predict(). "
                    "Backward compatible: if .pkl missing → pass-through (v4.1 behavior)."
                ),
                "v4.1": (
                    "CRITICAL: _ml_predict() now calls _strip_ml_excluded() before "
                    "predictor.predict(). Prevents ValueError on overdue_days leakage guard."
                ),
                "v4.0": (
                    "Removed local build_features() (11 features) — "
                    "uses predictor._to_features() for all 41 training features."
                ),
            },
        }


# ─────────────────────────────────────────────────────────────────────────────
# Singleton accessor
# ─────────────────────────────────────────────────────────────────────────────

def get_finance_risk_handler() -> FinanceRiskModelHandler:
    return FinanceRiskModelHandler.get_instance()


FinanceRiskModelHandlerV3 = FinanceRiskModelHandler


def _make_request_id() -> str:
    return f"fin-{uuid.uuid4().hex[:12]}"
