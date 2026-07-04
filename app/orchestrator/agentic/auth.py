"""
🔐 Agentic API-Key Auth
=======================
File: app/orchestrator/agentic/auth.py

A small FastAPI dependency that protects every /agentic/* endpoint with a
single shared API key, checked against the `X-Agentic-API-Key` request
header. The expected key comes from settings.AGENTIC_API_KEY (loaded from
.env).

Behaviour:
    - AGENTIC_API_KEY == ""  → auth DISABLED. Endpoints are open (dev mode).
                               A one-time warning is logged at startup use.
    - AGENTIC_API_KEY set     → header REQUIRED and must match exactly.
                               Missing  → 401.  Wrong → 403.

Why a shared key (not JWT): the agentic layer is a privileged internal
control plane (it can trigger real HR/Finance actions). A single rotated
secret on a dedicated header is the minimal correct control — no user
identity model is needed here. Comparison is constant-time to avoid timing
side-channels.
"""

from __future__ import annotations

import hmac
import logging
from typing import Optional

from fastapi import Header, HTTPException, status

logger = logging.getLogger(__name__)

_HEADER_NAME = "X-Agentic-API-Key"
_warned_open = False


def _expected_key() -> str:
    try:
        from config.settings import get_settings
        return get_settings().AGENTIC_API_KEY or ""
    except Exception as e:
        logger.error("🔐 [AgenticAuth] could not read settings: %s", e)
        return ""


def auth_enabled() -> bool:
    return bool(_expected_key())


async def require_agentic_key(
    x_agentic_api_key: Optional[str] = Header(default=None, alias=_HEADER_NAME),
) -> bool:
    """
    FastAPI dependency. Returns True when access is allowed, raises
    HTTPException otherwise. Use via:  dependencies=[Depends(require_agentic_key)]
    """
    global _warned_open
    expected = _expected_key()

    # Auth disabled — allow, but warn once so it's obvious in logs.
    if not expected:
        if not _warned_open:
            logger.warning(
                "🔓 [AgenticAuth] AGENTIC_API_KEY is empty — /agentic/* endpoints "
                "are OPEN. Set AGENTIC_API_KEY in .env to require the %s header.",
                _HEADER_NAME,
            )
            _warned_open = True
        return True

    if not x_agentic_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Missing {_HEADER_NAME} header.",
            headers={"WWW-Authenticate": _HEADER_NAME},
        )

    # Constant-time comparison.
    if not hmac.compare_digest(str(x_agentic_api_key), str(expected)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid agentic API key.",
        )
    return True
