"""
🤖 Base Agent — v4.0 Production
================================
File: app/agents/base_agent.py

✅ v4.0 Features:
    1. request_id per-request tracing (injected automatically if not provided)
    2. trace_id propagation through the full pipeline
    3. Centralized error handling — every agent.run() is safe by default
    4. Thresholds from config/hr_thresholds.py (no hardcoding)
    5. Structured logging: [request_id=xxx] prefix on every log line
"""

from __future__ import annotations

import logging
import traceback
import uuid
from abc import ABC, abstractmethod
from typing import Optional

from audit.logger import AuditLogger

# ── Import centralized thresholds ─────────────────────────────────────────────
try:
    from config.hr_thresholds import (
        TIER1_APPROVE_THRESHOLD,
        TIER3_REJECT_THRESHOLD,
        RISK_LOW_THRESHOLD,
        RISK_MEDIUM_THRESHOLD,
        classify_risk as _classify_risk_fn,
        apply_standard_threshold as _apply_threshold_fn,
    )
    _THRESHOLDS_LOADED = True
except ImportError:
    TIER1_APPROVE_THRESHOLD = 0.72
    TIER3_REJECT_THRESHOLD  = 0.42
    RISK_LOW_THRESHOLD      = 0.80
    RISK_MEDIUM_THRESHOLD   = 0.50
    _THRESHOLDS_LOADED      = False

    def _classify_risk_fn(confidence: float) -> str:
        if confidence >= RISK_LOW_THRESHOLD:
            return "low"
        elif confidence >= RISK_MEDIUM_THRESHOLD:
            return "medium"
        return "high"

    def _apply_threshold_fn(confidence: float) -> str:
        if confidence >= TIER1_APPROVE_THRESHOLD:
            return "approve"
        elif confidence >= TIER3_REJECT_THRESHOLD:
            return "escalate"
        return "reject"

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# 🆔  REQUEST CONTEXT
# ════════════════════════════════════════════════════════════════════════════

def generate_request_id() -> str:
    """Generate a short unique request ID for distributed tracing."""
    return uuid.uuid4().hex[:12]  # e.g. "a3f7d2c910b4"


class RequestContext:
    """
    Lightweight context object passed through the pipeline.
    Carries request_id and trace_id for structured logging.
    """

    __slots__ = ("request_id", "trace_id", "agent_name", "started_at")

    def __init__(
        self,
        request_id: Optional[str] = None,
        trace_id: Optional[str]   = None,
        agent_name: str           = "unknown_agent",
    ) -> None:
        import time
        self.request_id  = request_id or generate_request_id()
        self.trace_id    = trace_id   or self.request_id
        self.agent_name  = agent_name
        self.started_at  = time.monotonic()

    def elapsed_ms(self) -> float:
        import time
        return round((time.monotonic() - self.started_at) * 1000, 1)

    def log_prefix(self) -> str:
        return f"[request_id={self.request_id}]"

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "trace_id":   self.trace_id,
            "agent_name": self.agent_name,
        }


# ════════════════════════════════════════════════════════════════════════════
# 🤖  BASE AGENT
# ════════════════════════════════════════════════════════════════════════════

class BaseAgent(ABC):
    """
    Abstract base for all AI agents in Synergy ERP.

    Every concrete agent must implement:
        - name   → str      (human-readable agent name)
        - process(data)     → decision dict

    Workflows call run() or async_run(), not process() directly.

    Automatic features:
        - request_id injected into every call if not provided
        - Structured log lines: [request_id=abc123] AgentName started
        - Error handling: process() exceptions → safe escalate result
        - Timing: elapsed_ms logged on completion
    """

    def __init__(self) -> None:
        self.audit_logger = AuditLogger()
        self._logger      = logging.getLogger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable agent name."""
        ...

    @abstractmethod
    def process(self, data: dict) -> dict:
        """

        1. ML prediction
        2. reasoning    
        3. AI logic

        Core reasoning method.

        Args:
            data: Cleaned, validated input dict. Will contain 'request_id' and
                  'trace_id' injected by run().

        Returns:
            {
                "decision":   "approve" | "reject" | "escalate",
                "confidence": float (0.0 → 1.0),
                "risk":       "low" | "medium" | "high",
                "reason":     str,
                "request_id": str,     ← always present
                ...
            }
        """
        ...

    # ── Public Sync Entry Point ───────────────────────────────────────────────

    def run(self, data: dict, request_id: Optional[str] = None) -> dict:
        """
        Public sync entry point — wraps process() with:
            - request_id injection
            - structured logging
            - error handling + safe fallback
            - timing

        Args:
            data:       Input dict for the agent.
            request_id: Optional caller-provided request ID for tracing.

        Returns:
            Decision dict — NEVER raises.
        """
        ctx = RequestContext(
            request_id = request_id or data.get("request_id") or generate_request_id(),
            agent_name = self.name,
        )
        data = {**data, "request_id": ctx.request_id, "trace_id": ctx.trace_id}

        self._log_info(ctx, f"{self.name} started")
        self.audit_logger.log(
            event_type = self.name,
            stage      = "agent_start",
            message    = f"{ctx.log_prefix()} {self.name} started processing",
        )

        try:
            result = self.process(data)
            result.setdefault("request_id", ctx.request_id)
            result.setdefault("trace_id",   ctx.trace_id)

            conf = result.get("confidence", 0)
            self._log_info(
                ctx,
                f"{self.name} → {result.get('decision')} "
                f"(conf={conf:.3f}, risk={result.get('risk')}, "
                f"elapsed={ctx.elapsed_ms()}ms)",
            )
            self.audit_logger.log(
                event_type = self.name,
                stage      = "agent_complete",
                message    = (
                    f"{ctx.log_prefix()} {self.name} decision: "
                    f"{result.get('decision')} conf={conf:.3f} "
                    f"elapsed={ctx.elapsed_ms()}ms"
                ),
            )
            return result

        except Exception as exc:
            return self._handle_error(ctx, exc, data)

    # ── Public Async Entry Point ──────────────────────────────────────────────

    async def async_run(self, data: dict, request_id: Optional[str] = None) -> dict:
        """
        Async version of run(). Calls async_process() if available,
        otherwise falls back to sync process().

        NEVER raises — always returns a safe result.
        """
        ctx = RequestContext(
            request_id = request_id or data.get("request_id") or generate_request_id(),
            agent_name = self.name,
        )
        data = {**data, "request_id": ctx.request_id, "trace_id": ctx.trace_id}

        self._log_info(ctx, f"{self.name} async started")
        self.audit_logger.log(
            event_type = self.name,
            stage      = "agent_async_start",
            message    = f"{ctx.log_prefix()} {self.name} async processing started",
        )

        try:
            if hasattr(self, "async_process"):
                result = await self.async_process(data)  # type: ignore[attr-defined]
            else:
                result = self.process(data)

            result.setdefault("request_id", ctx.request_id)
            result.setdefault("trace_id",   ctx.trace_id)

            conf = result.get("confidence", 0)
            self._log_info(
                ctx,
                f"{self.name} async → {result.get('decision')} "
                f"(conf={conf:.3f}, elapsed={ctx.elapsed_ms()}ms)",
            )
            self.audit_logger.log(
                event_type = self.name,
                stage      = "agent_async_complete",
                message    = (
                    f"{ctx.log_prefix()} {self.name} async decision: "
                    f"{result.get('decision')} conf={conf:.3f}"
                ),
            )
            return result

        except Exception as exc:
            return self._handle_error(ctx, exc, data)

    # ── Shared Helpers ────────────────────────────────────────────────────────

    def _classify_risk(self, confidence: float) -> str:
        """Maps confidence score → risk label using centralized thresholds."""
        return _classify_risk_fn(confidence)

    def _apply_threshold(self, confidence: float) -> str:
        """Standard 3-tier decision gate using centralized thresholds."""
        return _apply_threshold_fn(confidence)

    def _log_info(self, ctx: RequestContext, message: str) -> None:
        """Emit a structured info log with request_id prefix."""
        self._logger.info("%s %s", ctx.log_prefix(), message)

    def _log_warning(self, ctx: RequestContext, message: str) -> None:
        """Emit a structured warning log with request_id prefix."""
        self._logger.warning("%s %s", ctx.log_prefix(), message)

    def _log_error(self, ctx: RequestContext, message: str) -> None:
        """Emit a structured error log with request_id prefix."""
        self._logger.error("%s %s", ctx.log_prefix(), message)

    def _handle_error(self, ctx: RequestContext, exc: Exception, data: dict) -> dict:
        """
        Safe error handler — logs the full traceback and returns an escalate result.
        The pipeline should NEVER crash due to an agent exception.
        """
        tb = traceback.format_exc()
        self._log_error(
            ctx,
            f"{self.name} FAILED with {type(exc).__name__}: {exc}\n{tb}",
        )

        # This writes in an official log:
            # Who experienced an error
            # When
            # In which agent
        self.audit_logger.log(
            event_type = self.name,
            stage      = "agent_error",

            # request_id
            # اسم الـ agent
            # Error Type
            # part of the message

            message    = (
                f"{ctx.log_prefix()} {self.name} error: "
                f"{type(exc).__name__}: {str(exc)[:200]}"
            ),
            level      = "ERROR",
        )

        return {
            "decision":       "escalate",
            "confidence":     0.5,
            "risk":           "high",
            "reason":         (
                f"⚠️ Agent error — escalated for human review. "
                f"Error: {type(exc).__name__}: {str(exc)[:150]}"
            ),
            "reasoning":      f"[{self.name}] Exception: {type(exc).__name__}: {str(exc)[:200]}",
            "breakdown":      {},
            "key_factors":    [f"🚨 {self.name} encountered an error — human review required"],
            "ai_flags":       [f"❌ Agent error: {type(exc).__name__} (request_id={ctx.request_id})"],
            "llm_used":       False,
            "model_source":   "error_fallback",
            "input_warnings": [],
            "is_outlier":     False,
            "request_id":     ctx.request_id,
            "trace_id":       ctx.trace_id,
            "error_type":     type(exc).__name__,
            "error_detail":   str(exc)[:300],
            "_agent_error":   True,
        }
