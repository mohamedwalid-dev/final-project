"""
🧠 Finance Risk Model Handler — v3.1 (Production)
===================================================
File: app/agents/finance/risk_model_handler_v3.py

Changes from v3.0 → v3.1:
    ✅ Prediction latency tracking (ms) per request
    ✅ Model version stamped on every prediction response
    ✅ Input features snapshot in structured logs (audit-ready)
    ✅ FinanceExplainabilityEngine integrated — rich reasons replace "General risk"
    ✅ Structured log format (JSON-style fields) for easy parsing by ELK/Datadog
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
MODEL_DIR  = os.path.join(os.path.dirname(__file__), "..", "..", "models", "finance")
MODEL_PATH = os.path.join(MODEL_DIR, "payment_risk_v8.pkl")

INDUSTRY_RISK = {
    "retail": 0.40, "hospitality": 0.50, "construction": 0.60,
    "manufacturing": 0.35, "technology": 0.25, "healthcare": 0.20,
    "education": 0.15, "government": 0.05, "financial": 0.20,
    "real_estate": 0.55, "food_beverage": 0.45,
    "transportation": 0.40, "unknown": 0.40,
}

SEASONAL_RISK = {
    1: 0.50, 2: 0.45, 3: 0.35, 4: 0.30, 5: 0.30, 6: 0.40,
    7: 0.35, 8: 0.40, 9: 0.30, 10: 0.25, 11: 0.30, 12: 0.55,
}

BASE_FEATURE_NAMES = [
    "overdue_days_normalized",   # 0
    "amount_normalized",          # 1
    "paid_ratio",                 # 2
    "late_ratio",                 # 3
    "on_time_ratio",              # 4
    "customer_age_normalized",    # 5
    "invoice_frequency",          # 6
    "avg_delay_normalized",       # 7
    "credit_score_normalized",    # 8
    "industry_risk_factor",       # 9
    "seasonal_factor",            # 10
]


# ─────────────────────────────────────────────────────────────────────────────
# Structured Prediction Logger
# ─────────────────────────────────────────────────────────────────────────────

class PredictionLogger:
    """
    Emits structured log lines for every prediction.
    Format is compatible with ELK Stack, Datadog, and CloudWatch Insights.

    Each log line contains:
        request_id, model_version, latency_ms,
        risk_score, decision, reasons,
        input_snapshot (all 11 features)
    """

    def log(
        self,
        request_id:    str,
        model_version: str,
        latency_ms:    int,
        risk_score:    float,
        decision:      str,
        confidence:    float,
        reasons:       list,
        features:      np.ndarray,
        source:        str = "ml_model",
    ) -> None:
        """Emit a single structured log line for one prediction."""

        snapshot = self._build_snapshot(features)

        # ── Compact structured log (one line, easy to grep) ───────────────
        logger.info(
            "💰 [FinancePredict] "
            "request_id=%s | model=%s | latency=%dms | "
            "risk=%.4f | decision=%s | confidence=%.4f | source=%s | "
            "reasons=%s | features=%s",
            request_id,
            model_version,
            latency_ms,
            risk_score,
            decision,
            confidence,
            source,
            reasons,
            json.dumps(snapshot, separators=(",", ":")),
        )

        # ── Full structured payload at DEBUG level (for deep tracing) ─────
        if logger.isEnabledFor(logging.DEBUG):
            payload = {
                "event":         "finance_prediction",
                "request_id":    request_id,
                "model_version": model_version,
                "latency_ms":    latency_ms,
                "risk_score":    round(risk_score, 4),
                "decision":      decision,
                "confidence":    round(confidence, 4),
                "source":        source,
                "reasons":       reasons,
                "input_snapshot": snapshot,
            }
            logger.debug("💰 [FinancePredict:FULL] %s", json.dumps(payload, indent=2))

    def log_error(
        self,
        request_id:    str,
        model_version: str,
        latency_ms:    int,
        error:         str,
        features:      Optional[np.ndarray] = None,
    ) -> None:
        """Log a prediction failure with full context."""
        snapshot = self._build_snapshot(features) if features is not None else {}
        logger.error(
            "❌ [FinancePredict:ERROR] "
            "request_id=%s | model=%s | latency=%dms | "
            "error=%s | features=%s",
            request_id, model_version, latency_ms,
            error, json.dumps(snapshot, separators=(",", ":")),
        )

    def log_fallback(
        self,
        request_id:    str,
        model_version: str,
        latency_ms:    int,
        reason:        str,
    ) -> None:
        """Log that we fell back to rule-based prediction."""
        logger.warning(
            "⚠️ [FinancePredict:FALLBACK] "
            "request_id=%s | model=%s | latency=%dms | reason=%s",
            request_id, model_version, latency_ms, reason,
        )

    @staticmethod
    def _build_snapshot(features: Optional[np.ndarray]) -> dict:
        """Convert feature array → named dict for audit trail."""
        if features is None:
            return {}
        row = features[0] if features.ndim == 2 else features
        return {
            name: round(float(val), 4)
            for name, val in zip(BASE_FEATURE_NAMES, row)
            if name != "on_time_ratio"  # derived — skip to reduce noise
        }


_pred_logger = PredictionLogger()


# ─────────────────────────────────────────────────────────────────────────────
# Handler
# ─────────────────────────────────────────────────────────────────────────────

class FinanceRiskModelHandlerV3:
    """
    Thread-safe singleton handler for v3.x model.

    v3.1 additions:
        - predict() now returns `latency_ms` and `model_version`
        - Every call emits a structured log with input snapshot
        - Rich explainability via FinanceExplainabilityEngine
    """

    _instance: Optional["FinanceRiskModelHandlerV3"] = None
    _lock      = threading.Lock()

    def __init__(self):
        self._predictor    = None
        self._ensemble     = None
        self._metadata     = {}
        self._loaded       = False
        self._version      = "unknown"
        self._trained_at   = "unknown"
        self._load()

    @classmethod
    def get_instance(cls) -> "FinanceRiskModelHandlerV3":
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
            self._ensemble   = saved.get("ensemble")
            self._metadata   = saved.get("metadata", {})
            self._version    = self._metadata.get("version", "3.x")
            self._trained_at = self._metadata.get("trained_at", "unknown")
            self._loaded     = True

            metrics = self._metadata.get("metrics", {})
            de_cfg  = self._metadata.get("decision_engine", {})

            logger.info(
                "✅ Finance Risk Model v%s loaded | "
                "trained=%s | AUC=%.4f | features=%s | "
                "thresholds: reject≥%.2f review≥%.2f",
                self._version,
                self._trained_at,
                float(metrics.get("roc_auc") or 0),
                self._metadata.get("feature_count", "?"),
                de_cfg.get("reject_threshold", 0.70),
                de_cfg.get("review_threshold", 0.45),
            )
            return True

        except Exception as e:
            logger.error("❌ Finance model load error: %s", e, exc_info=True)
            self._loaded = False
            return False

    def reload(self) -> bool:
        with self._lock:
            self._predictor  = None
            self._ensemble   = None
            self._metadata   = {}
            self._loaded     = False
            return self._load()

    def is_loaded(self) -> bool:
        return self._loaded and (
            self._predictor is not None or self._ensemble is not None
        )

    # ── Feature Building ─────────────────────────────────────────────────────

    def build_features(self, data: dict) -> np.ndarray:
        """
        Build 11-feature normalized vector from raw invoice/customer data.
        Handles missing values, unknown industries, and edge cases.
        """
        from datetime import datetime

        def safe_float(val, default=0.0):
            try:
                v = float(val or default)
                return v if (v == v and abs(v) != float("inf")) else default
            except (TypeError, ValueError):
                return default

        overdue_days      = safe_float(data.get("overdue_days"),          0.0)
        amount            = safe_float(data.get("amount"),                 0.0)
        payment_count     = max(1, int(safe_float(data.get("payment_history_count"), 1)))
        paid_count        = int(safe_float(data.get("payment_history_paid"),  0))
        late_count        = int(safe_float(data.get("payment_history_late"),  0))
        customer_age_mo   = safe_float(data.get("customer_age_months"),    12.0)
        invoice_count_90d = safe_float(data.get("invoice_count_90d"),      1.0)
        avg_delay_days    = safe_float(data.get("avg_payment_delay_days"), 0.0)
        credit_score      = safe_float(data.get("credit_score"),           650.0)
        month             = int(safe_float(data.get("invoice_month"), datetime.utcnow().month))

        raw_industry  = str(data.get("industry", "unknown") or "unknown").lower().strip()
        industry_risk = INDUSTRY_RISK.get(raw_industry, INDUSTRY_RISK["unknown"])

        paid_ratio         = paid_count / payment_count
        late_ratio         = late_count / payment_count
        amount_normalized  = min(amount / 100_000.0, 1.0)
        credit_normalized  = min(max(credit_score, 300), 850) / 850.0
        age_normalized     = min(customer_age_mo / 60.0, 1.0)
        seasonal_factor    = SEASONAL_RISK.get(month, 0.35)
        overdue_normalized = min(overdue_days / 180.0, 1.0)

        return np.array([
            overdue_normalized,
            amount_normalized,
            paid_ratio,
            late_ratio,
            1.0 - late_ratio,          # on_time_ratio
            age_normalized,
            min(invoice_count_90d / 20.0, 1.0),
            min(avg_delay_days / 90.0, 1.0),
            credit_normalized,
            industry_risk,
            seasonal_factor,
        ], dtype=np.float64).reshape(1, -1)

    # ── Predict ──────────────────────────────────────────────────────────────

    def predict(self, data: dict, request_id: str = "") -> dict:
        """
        Full prediction pipeline — v3.1.

        Returns:
            {
                "risk_score":      float,
                "risk_label":      "low|medium|high",
                "decision":        "approve|manual_review|reject",
                "confidence":      float,
                "reasons":         [str, str, str],       ← rich, specific reasons
                "positive_factors":[str, ...],
                "negative_factors":[str, ...],
                "dominant_factor": str,
                "summary":         str,
                "feature_snapshot":dict,                  ← all 11 features (audit trail)
                "latency_ms":      int,                   ← prediction time in ms
                "model_version":   str,                   ← e.g. "8.0" or "3.1-rules"
                "source":          str,
            }
        """
        request_id    = request_id or _make_request_id()
        model_version = self._version if self._loaded else "rules-v3.1"
        t_start       = time.perf_counter()
        features      = None

        try:
            features = self.build_features(data)

            if self.is_loaded():
                result = self._ml_predict(features)
            else:
                result = self._rule_based_predict_raw(features)

            latency_ms = int((time.perf_counter() - t_start) * 1000)

            # ── Explainability ────────────────────────────────────────────
            explanation = self._explain(features, result["risk_score"], result["decision"])

            # Only override reasons if explainability produced something meaningful
            if explanation.reasons and explanation.reasons[0] != "General risk assessment":
                result["reasons"]          = explanation.reasons
                result["positive_factors"] = explanation.positive_factors
                result["negative_factors"] = explanation.negative_factors
                result["dominant_factor"]  = explanation.dominant_factor
                result["summary"]          = explanation.summary
                result["feature_snapshot"] = explanation.feature_snapshot
            else:
                result.setdefault("positive_factors", [])
                result.setdefault("negative_factors", result.get("reasons", []))
                result.setdefault("dominant_factor",  result.get("reasons", ["?"])[0])
                result.setdefault("summary",          "")
                result.setdefault("feature_snapshot", _pred_logger._build_snapshot(features))

            # ── Stamp metadata ────────────────────────────────────────────
            result["latency_ms"]    = latency_ms
            result["model_version"] = model_version
            result["request_id"]    = request_id

            # ── Structured log ────────────────────────────────────────────
            _pred_logger.log(
                request_id    = request_id,
                model_version = model_version,
                latency_ms    = latency_ms,
                risk_score    = result["risk_score"],
                decision      = result["decision"],
                confidence    = result.get("confidence", 0.0),
                reasons       = result["reasons"],
                features      = features,
                source        = result.get("source", "unknown"),
            )

            # ── Emit to MetricsCollector if available ────────────────────────
            try:
                from core.metrics_collector import get_metrics_collector, MetricEvent
                collector = get_metrics_collector()

                collector.emit(MetricEvent(
                    metric_type = result["decision"],
                    category    = "finance",
                    value       = result["risk_score"],
                    tags        = {
                        "request_id":   request_id,
                        "model_version": model_version,
                        "latency_ms":   latency_ms,
                        "confidence":   result.get("confidence", 0.0),
                        "llm_used":     result.get("llm_used", False),
                    },
                    entity_id   = data.get("invoice_id"),
                    entity_type = "invoice",
                ))
            except Exception:
                pass  # ignore if collector not running


            return result

        except Exception as e:
            latency_ms = int((time.perf_counter() - t_start) * 1000)
            _pred_logger.log_error(
                request_id    = request_id,
                model_version = model_version,
                latency_ms    = latency_ms,
                error         = str(e),
                features      = features,
            )
            logger.error("❌ [RiskHandler v3.1] predict() failed: %s", e, exc_info=True)

            # Structured fallback — never crash the caller
            return self._emergency_result(request_id, model_version, latency_ms, str(e))

    # ── ML Predict (internal) ─────────────────────────────────────────────────

    def _ml_predict(self, features: np.ndarray) -> dict:
        """Call the loaded ML predictor — returns raw result dict."""
        if self._predictor is not None:
            result = self._predictor.predict(features)
            return {
                "risk_score": float(result.get("risk_score", 0.5)),
                "decision":   result.get("decision", "manual_review"),
                "confidence": float(result.get("confidence", 0.5)),
                "reasons":    result.get("reasons", ["General risk assessment"]),
                "source":     "ml_model_v3.1",
                "risk_label": self._score_to_label(float(result.get("risk_score", 0.5))),
            }
        else:
            # Fallback: raw ensemble
            from training.finance_train import (
                add_engineered_features, safe_preprocess,
                ensemble_predict_proba, DecisionEngine,
            )
            X_clean = safe_preprocess(features)
            X_eng   = add_engineered_features(X_clean)
            prob    = float(ensemble_predict_proba(self._ensemble, X_eng)[0])
            de_cfg  = self._metadata.get("decision_engine", {})
            engine  = DecisionEngine(
                reject_threshold = de_cfg.get("reject_threshold", 0.70),
                review_threshold = de_cfg.get("review_threshold", 0.45),
            )
            res = engine.decide(prob)
            return {
                "risk_score": float(res.get("risk_score", prob)),
                "decision":   res.get("decision", "manual_review"),
                "confidence": float(res.get("confidence", prob)),
                "reasons":    res.get("reasons", ["General risk assessment"]),
                "source":     "ml_ensemble_v3.1",
                "risk_label": self._score_to_label(prob),
            }

    # ── Rule-based Predict (fallback, on normalized features) ─────────────────

    def _rule_based_predict_raw(self, features: np.ndarray) -> dict:
        """
        Rule-based prediction that operates on the pre-built feature array.
        Used when the ML model is not loaded.
        """
        row = features[0]

        overdue_norm  = float(row[0])
        paid_ratio    = float(row[2])
        late_ratio    = float(row[3])
        credit_norm   = float(row[8])
        industry_risk = float(row[9])
        amount_norm   = float(row[1])

        score  = 0.0
        score += overdue_norm  * 0.40
        score += (1.0 - paid_ratio) * 0.20
        score += late_ratio    * 0.15
        score += (1.0 - credit_norm) * 0.15
        score += industry_risk * 0.05
        score += amount_norm   * 0.05
        score  = min(max(score, 0.0), 1.0)

        if score >= 0.70:
            decision = "reject"
        elif score >= 0.45:
            decision = "manual_review"
        else:
            decision = "approve"

        _pred_logger.log_fallback(
            request_id    = "",
            model_version = "rules-v3.1",
            latency_ms    = 0,
            reason        = "ML model not loaded",
        )

        return {
            "risk_score": round(score, 4),
            "decision":   decision,
            "confidence": 0.70,
            "reasons":    ["General risk assessment"],   # will be overridden by explainability
            "source":     "rules-v3.1",
            "risk_label": self._score_to_label(score),
        }

    # ── Explainability ────────────────────────────────────────────────────────

    def _explain(
        self,
        features:   np.ndarray,
        risk_score: float,
        decision:   str,
    ):
        """Run the explainability engine — returns ExplainabilityResult."""
        try:
            from agents.finance.explainability import get_explainability_engine
            engine = get_explainability_engine()
            return engine.explain(features, risk_score, decision)
        except Exception as e:
            logger.warning("⚠️ Explainability engine failed: %s", e)
            # Return a minimal stub so the caller doesn't crash
            from types import SimpleNamespace
            stub = SimpleNamespace(
                reasons          = ["General risk assessment"],
                positive_factors = [],
                negative_factors = [],
                dominant_factor  = "General risk assessment",
                summary          = "",
                feature_snapshot = {},
            )
            return stub

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _score_to_label(self, score: float) -> str:
        if score >= 0.70: return "high"
        if score >= 0.45: return "medium"
        return "low"

    def _emergency_result(
        self,
        request_id:    str,
        model_version: str,
        latency_ms:    int,
        error_msg:     str,
    ) -> dict:
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
            "feature_snapshot": {},
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
            "feature_count":    self._metadata.get("feature_count", 11),
            "ensemble_weights": self._metadata.get("ensemble_weights"),
            "decision_engine": {
                "reject_threshold": de.get("reject_threshold", 0.70),
                "review_threshold": de.get("review_threshold", 0.45),
            },
            "cost_optimization": self._metadata.get("cost_optimization", {}),
            "explainability":    "v1.0 (threshold-based, SHAP-free)",
            "logging":           "structured (latency + snapshot + version per request)",
        }


# ─────────────────────────────────────────────────────────────────────────────
# Singleton accessor + helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_finance_risk_handler() -> FinanceRiskModelHandlerV3:
    """Singleton accessor — drop-in replacement for v3.0."""
    return FinanceRiskModelHandlerV3.get_instance()


def _make_request_id() -> str:
    import uuid
    return f"fin-{uuid.uuid4().hex[:12]}"