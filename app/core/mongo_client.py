# core/mongo_client.py
from __future__ import annotations

import logging
import os
import ssl
import sys
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import certifi
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

_DEFAULT_SERVER_SELECTION_MS = 10_000
_DEFAULT_CONNECT_MS          = 10_000
_DEFAULT_SOCKET_MS           = 20_000

_LOCAL_HOSTS = frozenset({
    "localhost", "127.0.0.1", "0.0.0.0", "mongo", "mongodb", "host.docker.internal",
})


# ══════════════════════════════════════════════════════════════════════════════
#  WINDOWS TLS PATCH
#  Fixes: [SSL: TLSV1_ALERT_INTERNAL_ERROR] on Windows + Python 3.11 + Atlas
# ══════════════════════════════════════════════════════════════════════════════

def _apply_windows_tls_patch() -> None:
    """
    Patch ssl.create_default_context to use certifi CA bundle on Windows.
    Also disables OCSP stapling check which causes TLS failures on Windows.
    Called automatically at module import — no action needed elsewhere.
    """
    if sys.platform != "win32":
        return

    _original = ssl.create_default_context

    def _patched(purpose=ssl.Purpose.SERVER_AUTH, **kwargs):  # type: ignore[override]
        if "cafile" not in kwargs:
            kwargs["cafile"] = certifi.where()
        ctx = _original(purpose, **kwargs)
        ctx.check_hostname = True
        ctx.verify_mode    = ssl.CERT_REQUIRED
        # Suppress SSLv2/SSLv3 (also helps with TLS negotiation issues)
        ctx.options |= getattr(ssl, "OP_NO_SSLv2", 0)
        ctx.options |= getattr(ssl, "OP_NO_SSLv3", 0)
        return ctx

    ssl.create_default_context = _patched  # type: ignore[assignment]
    logger.debug("Windows TLS patch applied — using certifi CA bundle")


# Apply patch immediately on import (Windows only, no-op elsewhere)
_apply_windows_tls_patch()


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def is_local_mongo_uri(uri: str) -> bool:
    if uri.startswith("mongodb+srv://"):
        return False
    host = (urlparse(uri).hostname or "").lower()
    return host in _LOCAL_HOSTS


def resolve_mongo_uri() -> str:
    backend   = os.getenv("MONGO_BACKEND", "atlas").strip().lower()
    atlas_uri = (os.getenv("MONGO_URI", "").strip()
                 or os.getenv("MONGO_URI_ATLAS", "").strip())
    local_uri = os.getenv("MONGO_URI_LOCAL", "mongodb://127.0.0.1:27017").strip()

    if backend == "local" or _env_bool("MONGO_USE_LOCAL", False):
        logger.info("MongoDB backend: local (%s)", local_uri)
        return local_uri

    if not atlas_uri:
        raise RuntimeError(
            "MONGO_BACKEND=atlas but MONGO_URI is empty. "
            "Copy connection string from Atlas: Connect -> Drivers -> Python"
        )
    if not atlas_uri.startswith("mongodb+srv://"):
        raise RuntimeError(
            f"Atlas backend requires mongodb+srv:// URI. Got: {atlas_uri[:40]}..."
        )

    logger.info("MongoDB backend: atlas (%s)", urlparse(atlas_uri).hostname or "?")
    return atlas_uri


def normalize_mongo_uri(uri: str) -> str:
    uri = uri.strip()
    if is_local_mongo_uri(uri):
        return uri
    parsed  = urlparse(uri)
    qs      = parse_qs(parsed.query, keep_blank_values=True)
    changed = False
    if "retryWrites" not in qs:
        qs["retryWrites"] = ["true"]
        changed = True
    if "w" not in qs:
        qs["w"] = ["majority"]
        changed = True
    if not changed:
        return uri
    flat = {k: v[-1] if v else "" for k, v in qs.items()}
    return urlunparse(parsed._replace(query=urlencode(flat)))


# ══════════════════════════════════════════════════════════════════════════════
#  CLIENT KWARGS  —  TLS logic lives here
# ══════════════════════════════════════════════════════════════════════════════

def mongo_client_kwargs(uri: str, *, tls_insecure: bool | None = None) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "serverSelectionTimeoutMS": int(
            os.getenv("MONGO_SERVER_SELECTION_TIMEOUT_MS", str(_DEFAULT_SERVER_SELECTION_MS))
        ),
        "connectTimeoutMS": int(
            os.getenv("MONGO_CONNECT_TIMEOUT_MS", str(_DEFAULT_CONNECT_MS))
        ),
        "socketTimeoutMS": int(
            os.getenv("MONGO_SOCKET_TIMEOUT_MS", str(_DEFAULT_SOCKET_MS))
        ),
        "maxPoolSize": 10,
        "minPoolSize": 1,
    }

    # Local MongoDB — no TLS needed
    if is_local_mongo_uri(uri):
        return kwargs

    # Resolve tls_insecure from env if not passed explicitly
    if tls_insecure is None:
        tls_insecure = _env_bool("MONGO_TLS_INSECURE", False)

    if tls_insecure:
        # ── DEV ONLY: skip certificate validation entirely ─────────────────
        logger.warning(
            "MONGO_TLS_INSECURE=true — certificate validation DISABLED (dev only!)"
        )
        kwargs.update({
            "tls":                        True,
            "tlsAllowInvalidCertificates": True,
            "tlsAllowInvalidHostnames":    True,
            "retryWrites":                 True,
            "retryReads":                  True,
        })
    else:
        # ── PRODUCTION: validate certs with certifi CA bundle ──────────────
        kwargs.update({
            "tls":          True,
            "tlsCAFile":    certifi.where(),
            "retryWrites":  True,
            "retryReads":   True,
        })

        # Windows: always disable OCSP endpoint check — #1 cause of TLS errors
        # Also respects explicit env override on other platforms
        if sys.platform == "win32" or _env_bool("MONGO_TLS_DISABLE_OCSP", False):
            kwargs["tlsDisableOCSPEndpointCheck"] = True
            logger.debug("tlsDisableOCSPEndpointCheck=True (Windows/env override)")

    return kwargs


# ══════════════════════════════════════════════════════════════════════════════
#  PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════

def create_mongo_client(
    uri: str | None = None,
    *,
    tls_insecure: bool | None = None,
) -> AsyncIOMotorClient:
    """
    Create a Motor async client (local or Atlas).

    Usage:
        client = create_mongo_client()          # uses MONGO_URI from env
        client = create_mongo_client(uri=..., tls_insecure=True)  # explicit
    """
    resolved = normalize_mongo_uri(uri or resolve_mongo_uri())
    return AsyncIOMotorClient(
        resolved,
        **mongo_client_kwargs(resolved, tls_insecure=tls_insecure),
    )


async def verify_mongo_connection(client: AsyncIOMotorClient, db_name: str) -> dict:
    """
    Ping MongoDB and return version info.
    Raises on failure — caller decides whether to abort or continue degraded.
    """
    ping = await client.admin.command("ping")
    try:
        info    = await client.admin.command("buildInfo")
        version = info.get("version", "unknown")
    except Exception:
        version = "unknown"
    logger.info(
        "MongoDB ping OK | version=%s | db=%s", version, db_name
    )
    return {"ok": ping.get("ok"), "version": version, "db": db_name}