"""
🤖 Shared LLM Client — Agentic Layer
=====================================
File: app/orchestrator/agentic/llm_client.py

A single, reusable async Gemini client for the agentic layer with:
    - Process-level quota guard (reuses the same 429/RESOURCE_EXHAUSTED
      back-off pattern already used by FinanceAgent).
    - Hard timeout per call.
    - Robust JSON extraction (handles ```json fences, leading prose, etc.).
    - A deterministic fallback contract: callers always pass a fallback
      builder, so when the LLM is unavailable (no key / quota / import
      error / timeout) the system keeps working.

This module NEVER raises on an LLM failure — it returns
(result, used_llm: bool) and lets the caller decide.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import threading
import time
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# Default per-call timeout (seconds). Kept independent from the HR/Finance
# LLM_TIMEOUT_SECONDS so the agentic layer can be tuned separately.
DEFAULT_LLM_TIMEOUT_SEC = 25.0
DEFAULT_COOLDOWN_SEC    = 65.0


class _AgenticQuotaGuard:
    """Process-level Gemini quota tracker — mirrors FinanceAgent's guard."""

    def __init__(self, cooldown_seconds: float = DEFAULT_COOLDOWN_SEC):
        self._lock          = threading.Lock()
        self._blocked_until = 0.0
        self._cooldown      = cooldown_seconds
        self._total_skips   = 0

    def is_blocked(self) -> bool:
        return time.monotonic() < self._blocked_until

    def report_exhausted(self, retry_after_seconds: float = DEFAULT_COOLDOWN_SEC) -> None:
        with self._lock:
            self._blocked_until = time.monotonic() + max(retry_after_seconds, self._cooldown)
            self._total_skips  += 1
            logger.warning(
                "🛑 [Agentic/QuotaGuard] Gemini quota exhausted — LLM paused for %.0fs "
                "(total skips: %d)",
                retry_after_seconds, self._total_skips,
            )

    def status(self) -> dict:
        remaining = max(0.0, self._blocked_until - time.monotonic())
        return {
            "blocked":           self.is_blocked(),
            "remaining_seconds": int(remaining),
            "total_skips":       self._total_skips,
        }


_quota_guard = _AgenticQuotaGuard()


def get_quota_guard() -> _AgenticQuotaGuard:
    return _quota_guard


def _extract_retry_after(exc: Exception) -> float:
    msg = str(exc)
    m = re.search(r"'retryDelay':\s*'(\d+)s'", msg)
    if m:
        return float(m.group(1)) + 5.0
    m = re.search(r"retry in (\d+(?:\.\d+)?)s", msg, re.IGNORECASE)
    if m:
        return float(m.group(1)) + 5.0
    return DEFAULT_COOLDOWN_SEC


def extract_json(text: str) -> Optional[dict]:
    """
    Best-effort JSON object extraction from an LLM response.
    Handles ```json fences, surrounding prose, and trailing commentary.
    """
    if not text:
        return None
    # 1) fenced ```json ... ```
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fence.group(1) if fence else None
    # 2) first balanced-looking {...}
    if candidate is None:
        brace = re.search(r"\{.*\}", text, re.DOTALL)
        candidate = brace.group(0) if brace else None
    if candidate is None:
        return None
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        # Tolerate trailing commas
        cleaned = re.sub(r",\s*([}\]])", r"\1", candidate)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return None


class AgenticLLMClient:
    """
    Async wrapper around ChatGoogleGenerativeAI with graceful degradation.

    Usage:
        client = get_llm_client()
        result, used_llm = await client.complete_json(
            prompt="...",
            fallback=lambda: {...},     # deterministic dict
        )
    """

    def __init__(self, timeout_sec: float = DEFAULT_LLM_TIMEOUT_SEC):
        self._timeout = timeout_sec

    def is_available(self) -> bool:
        """True if an API key is set and quota is not cooling down."""
        if _quota_guard.is_blocked():
            return False
        try:
            from config.settings import get_settings
            return bool(get_settings().GOOGLE_API_KEY)
        except Exception:
            return False

    async def _raw_call(self, prompt: str, temperature: float) -> Optional[str]:
        """Single Gemini call. Returns text or None on any failure."""
        if _quota_guard.is_blocked():
            logger.info("⏭️ [Agentic/LLM] Quota cooling down — skipping call")
            return None
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            from config.settings import get_settings

            settings = get_settings()
            if not settings.GOOGLE_API_KEY:
                logger.debug("⚠️ [Agentic/LLM] GOOGLE_API_KEY not set — skipping")
                return None

            llm = ChatGoogleGenerativeAI(
                model          = settings.GEMINI_MODEL,
                google_api_key = settings.GOOGLE_API_KEY,
                temperature    = temperature,
                max_retries    = 0,   # quota guard handles back-off
            )
            response = await asyncio.wait_for(llm.ainvoke(prompt), timeout=self._timeout)
            return getattr(response, "content", None) or str(response)

        except asyncio.TimeoutError:
            logger.warning("⏰ [Agentic/LLM] call timed out after %.0fs", self._timeout)
            return None
        except Exception as e:
            err = str(e)
            if "RESOURCE_EXHAUSTED" in err or "429" in err:
                _quota_guard.report_exhausted(_extract_retry_after(e))
            elif isinstance(e, ImportError) or "langchain_google_genai" in err:
                logger.warning("⚠️ [Agentic/LLM] langchain_google_genai not installed")
            else:
                logger.warning("⚠️ [Agentic/LLM] call failed: %s", err[:200])
            return None

    async def complete_json(
        self,
        prompt: str,
        fallback: Callable[[], dict],
        temperature: float = 0.1,
    ) -> tuple[dict, bool]:
        """
        Return (parsed_json, used_llm). Falls back to `fallback()` on any
        failure or unparseable output. NEVER raises.
        """
        text = await self._raw_call(prompt, temperature)
        if text is None:
            return fallback(), False
        parsed = extract_json(text)
        if parsed is None:
            logger.info("⚠️ [Agentic/LLM] response not parseable as JSON — using fallback")
            return fallback(), False
        return parsed, True

    async def complete_text(
        self,
        prompt: str,
        fallback: Callable[[], str],
        temperature: float = 0.2,
    ) -> tuple[str, bool]:
        """Return (text, used_llm) for free-form completions."""
        text = await self._raw_call(prompt, temperature)
        if text is None or not text.strip():
            return fallback(), False
        return text.strip(), True


_client: Optional[AgenticLLMClient] = None
_client_lock = threading.Lock()


def get_llm_client() -> AgenticLLMClient:
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = AgenticLLMClient()
    return _client
