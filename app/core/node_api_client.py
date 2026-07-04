"""
core/node_api_client.py — Node.js ERP Backend API Client
==========================================================
Implements the "Method 1" integration pattern for Synergy ERP:

    AI Agent (FastAPI / LangChain tools)
        --> NodeAPIClient (this file -- httpx.AsyncClient)
            --> Node.js / Express HR + Finance REST API  (port 5005)
                --> MongoDB Atlas

Why a separate client instead of reusing this service's own Motor
connection (get_hr_db() / get_finance_db()):
    The Python side already has direct MongoDB access for the
    collections it OWNS and writes through its own workflows (leave /
    salary / incentive / absence approval state machines -- see
    LeaveApprovalWorkflow, SalaryReviewWorkflow, etc. in main.py).
    This client is for the opposite direction: reading data whose
    system of record is the Node.js/Express service, so the AI Agent
    sees exactly what the Node API (and therefore the React frontend)
    sees -- including any computed fields, filtering, or business
    rules that live only in the Node controllers -- without
    duplicating that logic in Python and without the AI needing to
    know Mongoose schema details it doesn't own. If the Node team
    renames a field or migrates a collection, the AI Agent keeps
    working as long as the REST contract is stable.

Production-hardening included:
    - Async (httpx.AsyncClient) -- never blocks the FastAPI event loop
    - One shared, pooled client per process (see get_node_api_client())
    - Per-call timeout + bounded retries w/ exponential backoff for
      timeouts/network errors and 5xx responses (4xx fails immediately
      -- retrying a 400 won't fix it)
    - Circuit breaker (same shape as this codebase's HR Gemini quota
      guard / _GeminiQuotaGuard) -- after N consecutive failures, fail
      fast for a cooldown window instead of stacking up latency against
      a dead Node API
    - Short-TTL in-memory cache for read endpoints (mirrors the
      _DASHBOARD_MEM_CACHE pattern already used in main.py)
    - Defensive response unwrapping -- every Node controller responds
      with the same envelope: {"status": "success"|"failed", "data": ...,
      "message": "..."}. _unwrap_envelope() strips that first, then
      _unwrap_list()/_unwrap_one() dig into the inner shape (some list
      endpoints return a bare array, others return {"invoices": [...],
      "total": N} — see the confirmed shapes below, taken directly from
      finance.controller.js / hr.controller.js).
    - v6.6: SELF-RENEWING AUTHENTICATION. The Node service's
      `Verify` middleware issues short-lived JWTs (this codebase's
      auth.controller.js currently issues 20-minute tokens). A static
      NODE_API_SERVICE_TOKEN pasted into .env therefore goes stale
      ~20 minutes after whoever generated it logged in, and every
      call after that silently 401s until someone manually mints and
      pastes a new one — not viable for a long-running background
      service. This client now:
        1. Decodes the JWT's `exp` claim itself (no extra dependency
           -- just base64 + json on the middle segment) and tracks
           when the *current* token expires, regardless of whether it
           came from NODE_API_SERVICE_TOKEN or from login().
        2. Proactively re-authenticates a configurable safety margin
           before that expiry (NODE_API_TOKEN_REFRESH_MARGIN_SEC)
           instead of waiting to be rejected.
        3. Falls back to a REACTIVE re-auth-and-retry: if a request
           still comes back 401 (token revoked/blacklisted server-side,
           clock skew, first boot before any proactive refresh ran),
           it invalidates the current token, logs in again, and
           retries the SAME request once before giving up.
      Both paths require NODE_API_SERVICE_EMAIL/NODE_API_SERVICE_PASSWORD
      to be set. If only a static NODE_API_SERVICE_TOKEN is provided
      (no email/password), the client still decodes its exp for
      diagnostics/logging but cannot renew it automatically — this is
      logged clearly as a startup warning rather than failing silently
      at minute 20.

Confirmed response shapes (finance.controller.js, read 2026-07):
    GET /finance/customers            -> data = {customers: [...], total}
    GET /finance/customers/:id        -> data = {...customer, invoice_summary}
    GET /finance/invoices             -> data = {invoices: [...], total}
    GET /finance/invoices/pending     -> data = [...]                (bare array)
    GET /finance/invoices/overdue     -> data = [...]                (bare array)
    GET /finance/invoices/:id         -> data = {...invoice, customer_*}
    GET /finance/legal-cases          -> data = [...]                (bare array)
    GET /finance/legal-cases/:id      -> data = {...case}
    GET /finance/collections/log      -> data = [...]                (bare array)
    GET /finance/collections/stats    -> data = {breakdown, summary}
    GET /finance/audit/:domain/:id    -> data = [...]                (bare array)
    GET /finance/decisions/:entity_id -> data = [...]                (bare array,
                                          accepts ?entity= query param, defaults
                                          to "finance_invoices" server-side)
    GET /finance/decisions/history    -> data = [...] (shape TBC server-side)
    GET /finance/escalations/active   -> data = [...]                (bare array)
    GET /finance/escalations/:inv_id  -> data = {invoice, current_tier, ...}
    GET /finance/dashboard            -> data = {invoices, risk, decisions_30d, actions_7d}
    GET /finance/forecast             -> data = {due_7_days, due_30_days, ...}

Required env vars (.env):
    NODE_API_BASE_URL          default: http://localhost:5005/v1

    Authentication — pick ONE strategy:
      RECOMMENDED for a long-running service:
        NODE_API_SERVICE_EMAIL     account this service logs in as
        NODE_API_SERVICE_PASSWORD  its password
        -> the client calls POST /auth/login itself at startup and
           BEFORE every proactive-refresh window, so it never runs on
           a stale token. Any account the Node `Verify` middleware
           accepts works — Verify only checks that the JWT is valid
           and the user exists, it does not check `role` on the
           finance/HR routes wired through this client. Using a
           dedicated low-privilege account is still good practice,
           but is a Node.js-side authorization decision, not something
           this client requires.

      LEGACY / short-lived testing only:
        NODE_API_SERVICE_TOKEN     a JWT copy-pasted from a manual login
        -> works until that token's own `exp` (commonly ~20 minutes in
           this codebase's auth.controller.js) and then every call
           401s until the token is manually replaced. Avoid for
           anything that needs to run unattended past that window.

Optional tuning (sane defaults if unset):
    NODE_API_TIMEOUT_SEC, NODE_API_MAX_RETRIES,
    NODE_API_RETRY_BACKOFF_BASE_SEC, NODE_API_CACHE_TTL_SEC,
    NODE_API_CB_FAILURE_THRESHOLD, NODE_API_CB_COOLDOWN_SEC,
    NODE_API_TOKEN_REFRESH_MARGIN_SEC (default 120s — re-auth this many
        seconds before the current token's exp)
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

import httpx

# ─────────────────────────────────────────────────────────────────────────
# .env loading — DO THIS FIRST, before any os.getenv() calls below.
# ─────────────────────────────────────────────────────────────────────────
# Root cause of a real bug seen in this codebase: main.py imports this
# module (`from core.node_api_client import ...`) BEFORE its own
# `load_dotenv()` call runs. Since the NODE_API_* constants below are
# read at *import time* (module-level `os.getenv(...)`), they were
# always resolving to "" — NODE_API_SERVICE_EMAIL/PASSWORD looked unset
# even when .env had real values in it, no matter what main.py's own
# import order was. A module that reads env vars at import time cannot
# rely on some OTHER module loading .env first; it has to guarantee its
# own env is loaded, deterministically, regardless of who imports it or
# in what order. `load_dotenv()` is idempotent and safe to call more
# than once (a later call in main.py, or in any other module, is a
# harmless no-op for keys already in os.environ), so doing it here has
# no downside and removes an entire class of "works depending on import
# order" bugs.
try:
    from dotenv import load_dotenv as _load_dotenv_for_node_api_client
    _load_dotenv_for_node_api_client()
except ImportError:
    # python-dotenv not installed — fall back to whatever's already in
    # os.environ (e.g. real system/container env vars). Don't crash a
    # module import over a missing dev-convenience dependency.
    pass

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────

NODE_API_BASE_URL = os.getenv("NODE_API_BASE_URL", "http://localhost:5005/v1").rstrip("/")
NODE_API_SERVICE_TOKEN = os.getenv("NODE_API_SERVICE_TOKEN", "")
NODE_API_SERVICE_EMAIL = os.getenv("NODE_API_SERVICE_EMAIL", "")
NODE_API_SERVICE_PASSWORD = os.getenv("NODE_API_SERVICE_PASSWORD", "")
NODE_API_TIMEOUT_SEC = float(os.getenv("NODE_API_TIMEOUT_SEC", "10.0"))
NODE_API_MAX_RETRIES = int(os.getenv("NODE_API_MAX_RETRIES", "2"))
NODE_API_RETRY_BACKOFF_BASE_SEC = float(os.getenv("NODE_API_RETRY_BACKOFF_BASE_SEC", "0.4"))
NODE_API_CACHE_TTL_SEC = float(os.getenv("NODE_API_CACHE_TTL_SEC", "20"))
NODE_API_CB_FAILURE_THRESHOLD = int(os.getenv("NODE_API_CB_FAILURE_THRESHOLD", "5"))
NODE_API_CB_COOLDOWN_SEC = float(os.getenv("NODE_API_CB_COOLDOWN_SEC", "30"))
# How long before the current token's own `exp` claim we proactively
# re-authenticate. Keep this comfortably larger than one request's
# worst-case latency (timeout * (retries+1)) so we never race the
# actual expiry mid-flight.
NODE_API_TOKEN_REFRESH_MARGIN_SEC = float(os.getenv("NODE_API_TOKEN_REFRESH_MARGIN_SEC", "120"))

_HAS_EMAIL_PASSWORD = bool(NODE_API_SERVICE_EMAIL and NODE_API_SERVICE_PASSWORD)

if not NODE_API_SERVICE_TOKEN and not _HAS_EMAIL_PASSWORD:
    logger.warning(
        "⚠️ Neither NODE_API_SERVICE_TOKEN nor NODE_API_SERVICE_EMAIL/"
        "NODE_API_SERVICE_PASSWORD are set — calls to Verify-protected "
        "Node.js HR/Finance routes will get 401 Unauthorized. Set "
        "NODE_API_SERVICE_EMAIL + NODE_API_SERVICE_PASSWORD (recommended — "
        "the client will log in and auto-renew the token itself), or set "
        "NODE_API_SERVICE_TOKEN as a short-lived fallback."
    )
elif NODE_API_SERVICE_TOKEN and not _HAS_EMAIL_PASSWORD:
    logger.warning(
        "⚠️ NODE_API_SERVICE_TOKEN is set but NODE_API_SERVICE_EMAIL/"
        "NODE_API_SERVICE_PASSWORD are NOT — this client can use the "
        "static token but CANNOT renew it when it expires (this "
        "codebase's Node tokens commonly expire in ~20 minutes). Every "
        "call will start failing with 401 once that happens. Set "
        "NODE_API_SERVICE_EMAIL/PASSWORD too so the client can "
        "auto-refresh instead of silently going stale."
    )


class NodeAPIError(Exception):
    """Raised when a Node.js API call fails after retries, or the circuit is open."""

    def __init__(self, message: str, status_code: Optional[int] = None, endpoint: str = ""):
        self.status_code = status_code
        self.endpoint = endpoint
        suffix = f" (status={status_code})" if status_code else ""
        super().__init__(f"[NodeAPI:{endpoint}] {message}{suffix}")


# ─────────────────────────────────────────────────────────────────────────
# JWT helpers — decode-only, no signature verification (we're the client,
# not the verifier; we only need the `exp` claim to know when to renew).
# ─────────────────────────────────────────────────────────────────────────

def _decode_jwt_payload(token: str) -> Optional[dict]:
    """Best-effort decode of a JWT's middle (payload) segment. Returns
    None on any malformed/non-JWT input instead of raising — this is
    only used for proactive-refresh scheduling, never for trust
    decisions, so failing soft here is correct."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload_b64 = parts[1]
        # base64url, re-pad to a multiple of 4
        padding = "=" * (-len(payload_b64) % 4)
        raw = base64.urlsafe_b64decode(payload_b64 + padding)
        return json.loads(raw)
    except Exception:
        return None


def _jwt_expiry_epoch(token: str) -> Optional[float]:
    payload = _decode_jwt_payload(token)
    if not payload or "exp" not in payload:
        return None
    try:
        return float(payload["exp"])
    except (TypeError, ValueError):
        return None


# ─────────────────────────────────────────────────────────────────────────
# Circuit breaker — same shape as the HR agent's Gemini quota guard
# ─────────────────────────────────────────────────────────────────────────

class _NodeAPICircuitBreaker:
    def __init__(self, failure_threshold: int, cooldown_sec: float):
        self._threshold = failure_threshold
        self._cooldown = cooldown_sec
        self._consecutive_failures = 0
        self._opened_at: Optional[float] = None
        self._lock = asyncio.Lock()

    async def before_call(self) -> None:
        async with self._lock:
            if self._opened_at is None:
                return
            elapsed = time.monotonic() - self._opened_at
            if elapsed < self._cooldown:
                raise NodeAPIError(
                    f"circuit open — Node API has been failing, retry in "
                    f"{self._cooldown - elapsed:.0f}s",
                    endpoint="circuit_breaker",
                )
            logger.info("🔌 [NodeAPI circuit] cooldown elapsed — half-open, trying again")

    async def record_success(self) -> None:
        async with self._lock:
            self._consecutive_failures = 0
            self._opened_at = None

    async def record_failure(self) -> None:
        async with self._lock:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._threshold and self._opened_at is None:
                self._opened_at = time.monotonic()
                logger.error(
                    "🔴 [NodeAPI circuit] OPEN after %d consecutive failures — "
                    "failing fast for %.0fs",
                    self._consecutive_failures, self._cooldown,
                )

    @property
    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        return (time.monotonic() - self._opened_at) < self._cooldown

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures


# ─────────────────────────────────────────────────────────────────────────
# Tiny in-memory TTL cache — same pattern as main.py's _mem_cache_get/set
# ─────────────────────────────────────────────────────────────────────────

_NODE_API_CACHE: Dict[str, Dict[str, Any]] = {}


def _cache_get(key: str):
    entry = _NODE_API_CACHE.get(key)
    if entry and time.monotonic() < entry["expires_at"]:
        return entry["data"]
    _NODE_API_CACHE.pop(key, None)
    return None


def _cache_set(key: str, data: Any, ttl_sec: float) -> None:
    _NODE_API_CACHE[key] = {"data": data, "expires_at": time.monotonic() + ttl_sec}


def _cache_key(path: str, params: Optional[dict]) -> str:
    if not params:
        return path
    return f"{path}?{json.dumps(params, sort_keys=True, default=str)}"


def clear_node_api_cache() -> int:
    """Manual cache bust — call after a write elsewhere that should
    invalidate these reads."""
    n = len(_NODE_API_CACHE)
    _NODE_API_CACHE.clear()
    return n


def _unwrap_list(payload: Any, *possible_keys: str) -> Any:
    """For list-returning endpoints. Several Node controllers respond as a
    bare list (e.g. pending/overdue invoices, legal-cases, collections/log,
    audit trails, decisions) while others wrap in {key: [...]} (customers,
    invoices). Try known shapes before falling back to the raw payload."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in (*possible_keys, "data"):
            val = payload.get(key)
            if isinstance(val, list):
                return val
        return payload
    return payload


def _unwrap_one(payload: Any, *possible_keys: str) -> Any:
    """For single-record endpoints (get-by-id). Node controllers respond
    as a bare object ({"_id": ..., ...}) for every confirmed single-record
    finance/HR endpoint — there is no {"invoice": {...}}-style wrapper in
    the actual controllers. Kept defensive: if a wrapper key is present
    (e.g. a future controller change), unwrap it; otherwise return the
    payload itself, since that's what today's controllers actually send."""
    if not isinstance(payload, dict):
        return payload
    for key in (*possible_keys, "data"):
        val = payload.get(key)
        if isinstance(val, dict):
            return val
    return payload


def _find_login_token(raw: Any) -> Optional[str]:
    """Find the JWT in a POST /auth/login response, whatever shape it
    comes back in. Confirmed shape for this codebase's
    auth.controller.js (2026-07):
        {
          "status": "success", "success": true,
          "data": [ { "token": "...", "user": {...} } ],
          "message": "You are now logged in!",
          "token": "...",
          "user": {...}
        }
    i.e. the token is duplicated at the response root AND nested one
    level down inside "data", where "data" is a single-element LIST
    (not a bare object like every other envelope in this API). Checked
    in order of how directly trustworthy each location is; also covers
    plainer shapes ({"data": {...}} or a bare {"token": ...}) in case
    the controller output ever gets normalized later."""
    if not isinstance(raw, dict):
        return None

    def _from_obj(obj: Any) -> Optional[str]:
        if isinstance(obj, dict):
            return obj.get("token") or obj.get("access_token") or obj.get("jwt")
        return None

    # 1) Root level — confirmed present today ("token" duplicated outside "data").
    token = _from_obj(raw)
    if token:
        return token

    # 2) Inside "data", where "data" may be a dict OR a single-element list.
    data = raw.get("data")
    if isinstance(data, list) and data:
        token = _from_obj(data[0])
        if token:
            return token
    elif isinstance(data, dict):
        token = _from_obj(data)
        if token:
            return token

    # 3) Nested one level further under data.user / data[0].user — belt and
    #    braces only, not expected to be needed given the shape above.
    if isinstance(data, list) and data and isinstance(data[0], dict):
        token = _from_obj(data[0].get("user"))
        if token:
            return token
    elif isinstance(data, dict):
        token = _from_obj(data.get("user"))
        if token:
            return token

    return None


def _unwrap_envelope(raw: Any, endpoint: str = "") -> Any:
    """Every Node controller in this codebase responds with the same
    envelope (see sendSuccess()/sendError() in finance.controller.js /
    hr.controller.js):
        { "status": "success" | "failed", "data": <القيمة الفعلية>, "message": "..." }

    This strips that envelope and returns .data, so _unwrap_list()/
    _unwrap_one() operate on the inner shape as documented above.

    If the response isn't shaped like that envelope (no "status" key),
    it's returned as-is — defensive fallback, outside known cases.
    """
    if not isinstance(raw, dict) or "status" not in raw:
        return raw

    if raw.get("status") == "failed":
        raise NodeAPIError(
            raw.get("message", "request failed"),
            endpoint=endpoint,
        )

    return raw.get("data", raw)


# ─────────────────────────────────────────────────────────────────────────
# Client
# ─────────────────────────────────────────────────────────────────────────

class NodeAPIClient:
    """Resilient async client over the Node.js HR + Finance REST API."""

    def __init__(
        self,
        base_url: str = NODE_API_BASE_URL,
        token: str = NODE_API_SERVICE_TOKEN,
        timeout_sec: float = NODE_API_TIMEOUT_SEC,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        headers = {
            "Accept": "application/json",
        }

        if token:
            headers["Authorization"] = f"Bearer {token}"

        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(timeout_sec),
            headers=headers,
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
            ),
            transport=transport,
        )

        self._cb = _NodeAPICircuitBreaker(
            failure_threshold=NODE_API_CB_FAILURE_THRESHOLD,
            cooldown_sec=NODE_API_CB_COOLDOWN_SEC,
        )

        self._token = token
        self._token_expires_at: Optional[float] = _jwt_expiry_epoch(token) if token else None
        self._login_lock = asyncio.Lock()
        self._can_self_renew = _HAS_EMAIL_PASSWORD

        if token and self._token_expires_at:
            remaining = self._token_expires_at - time.time()
            logger.info(
                "🔑 NodeAPIClient starting with a token expiring in %.0fs%s",
                remaining,
                "" if self._can_self_renew else " (no email/password set — cannot auto-renew)",
            )

    async def aclose(self) -> None:
        await self._client.aclose()

    @property
    def circuit_status(self) -> dict:
        return {"open": self._cb.is_open, "consecutive_failures": self._cb.consecutive_failures}

    @property
    def auth_status(self) -> dict:
        """Diagnostic snapshot — surfaced via /health/node-api."""
        remaining = None
        if self._token_expires_at:
            remaining = round(self._token_expires_at - time.time(), 1)
        return {
            "has_token": bool(self._token),
            "token_expires_in_sec": remaining,
            "can_self_renew": self._can_self_renew,
        }

    async def ping(self, timeout_sec: float = 3.0) -> dict:
        """Lightweight reachability probe for /health/detailed — any HTTP
        response (even 404) means the Node.js process is up and routing.
        Bypasses retries/circuit breaker on purpose: this check IS the
        signal, not a call we want to mask with retry logic."""
        t0 = time.monotonic()
        try:
            resp = await self._client.get("/", timeout=timeout_sec)
            return {
                "reachable": True,
                "status_code": resp.status_code,
                "latency_ms": int((time.monotonic() - t0) * 1000),
            }
        except Exception as e:
            return {
                "reachable": False,
                "error": str(e)[:120],
                "latency_ms": int((time.monotonic() - t0) * 1000),
            }

    # ── Auth: POST /auth/login ───────────────────────────────────────────

    async def login(self, email: Optional[str] = None, password: Optional[str] = None) -> str:
        """POST /v1/auth/login — logs in a service account and stores the
        returned JWT (plus its decoded expiry) for subsequent
        Authorization headers on this client instance. Raises
        NodeAPIError on failure (bad creds, Node API down, unexpected
        response shape).

        Confirmed actual auth.controller.js response shape (2026-07):
            {
              "status": "success", "success": true,
              "data": [ { "token": "...", "user": {...} } ],
              "message": "You are now logged in!",
              "token": "...",
              "user": {...}
            }
        Note "data" is a LIST containing one object here, not a bare
        object, and the token is ALSO duplicated at the response root.
        _find_login_token() below checks every shape this controller is
        known to use so a future controller tweak to any one of them
        doesn't silently break auth again."""
        email = email or NODE_API_SERVICE_EMAIL
        password = password or NODE_API_SERVICE_PASSWORD
        if not email or not password:
            raise NodeAPIError(
                "login() called without credentials — set NODE_API_SERVICE_EMAIL "
                "and NODE_API_SERVICE_PASSWORD, or pass email/password directly",
                endpoint="/auth/login",
            )

        resp = await self._client.post("/auth/login", json={"email": email, "password": password})
        if resp.status_code >= 400:
            raise NodeAPIError(f"login failed: {resp.text[:200]}", status_code=resp.status_code, endpoint="/auth/login")

        try:
            raw = resp.json()
        except ValueError as e:
            raise NodeAPIError(f"non-JSON login response: {e}", endpoint="/auth/login") from e

        token = _find_login_token(raw)
        if not token:
            raise NodeAPIError(
                "login succeeded (2xx) but no token found in response — check "
                "the actual field name/shape in auth.controller.js and adjust "
                "_find_login_token()",
                endpoint="/auth/login",
            )

        self._set_token(token)
        expires_in = (self._token_expires_at - time.time()) if self._token_expires_at else None
        logger.info(
            "✅ NodeAPIClient logged in as %s%s",
            email,
            f" — token valid for {expires_in:.0f}s" if expires_in else "",
        )
        return token

    def _set_token(self, token: str) -> None:
        self._token = token
        self._token_expires_at = _jwt_expiry_epoch(token)
        self._client.headers["Authorization"] = f"Bearer {token}"

    def _token_needs_refresh(self) -> bool:
        """True if we have no token, or the current one is within the
        safety margin of (or past) its own exp claim. Tokens without a
        decodable exp are treated as never needing proactive refresh
        (nothing to schedule against) — they'll still be caught by the
        reactive 401 path if they turn out to be invalid."""
        if not self._token:
            return True
        if self._token_expires_at is None:
            return False
        return (self._token_expires_at - time.time()) <= NODE_API_TOKEN_REFRESH_MARGIN_SEC

    async def ensure_authenticated(self, force: bool = False) -> None:
        """Called before every request. No-op if the current token is
        still comfortably valid. Otherwise logs in (or re-logs in) to
        obtain a fresh token — this is what makes the client survive
        past this codebase's ~20-minute Node JWT lifetime unattended.

        If no email/password is configured, this is a no-op even when
        the static token is stale — there's nothing to renew with, and
        that limitation is already surfaced loudly at import time and
        via `auth_status`."""
        if not self._can_self_renew:
            return
        if not force and not self._token_needs_refresh():
            return
        async with self._login_lock:
            # Re-check inside the lock: another concurrent call may have
            # already refreshed while we were waiting.
            if not force and not self._token_needs_refresh():
                return
            logger.info(
                "🔄 [NodeAPI auth] %s — refreshing token",
                "forced re-auth after 401" if force else "proactive refresh (approaching expiry)",
            )
            await self.login()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        json_body: Optional[dict] = None,
        use_cache: bool = False,
        cache_ttl: Optional[float] = None,
        _is_retry_after_reauth: bool = False,
    ) -> Any:
        clean_params = {k: v for k, v in (params or {}).items() if v is not None}
        cache_key = _cache_key(path, clean_params) if use_cache else None
        if cache_key:
            hit = _cache_get(cache_key)
            if hit is not None:
                return hit

        # Proactive refresh — keeps us from ever running on a token that's
        # about to (or already did) expire.
        await self.ensure_authenticated()

        await self._cb.before_call()

        last_exc: Optional[BaseException] = None
        for attempt in range(NODE_API_MAX_RETRIES + 1):
            is_last_attempt = attempt == NODE_API_MAX_RETRIES
            try:
                resp = await self._client.request(method, path, params=clean_params or None, json=json_body)
            except (httpx.TimeoutException, httpx.TransportError) as e:
                last_exc = e
                await self._cb.record_failure()
                if is_last_attempt:
                    raise NodeAPIError(f"network error after {attempt + 1} attempt(s): {e}", endpoint=path) from e
                await asyncio.sleep(NODE_API_RETRY_BACKOFF_BASE_SEC * (2 ** attempt))
                continue

            if resp.status_code == 401:
                await self._cb.record_failure()
                # Reactive path: the proactive refresh above either didn't
                # run (no email/password) or wasn't enough (server-side
                # revocation, clock skew, blacklisted token). If we CAN
                # self-renew and haven't already retried once for this
                # exact call, force a re-login and retry the request a
                # single time before giving up — avoids surfacing a
                # spurious 401 to the caller for what's really just a
                # stale-token race.
                if self._can_self_renew and not _is_retry_after_reauth:
                    logger.warning(
                        "⚠️ [NodeAPI] 401 on %s — forcing re-auth and retrying once", path
                    )
                    try:
                        await self.ensure_authenticated(force=True)
                    except NodeAPIError as login_err:
                        raise NodeAPIError(
                            f"401 Unauthorized, and re-auth also failed: {login_err}",
                            status_code=401, endpoint=path,
                        ) from login_err
                    return await self._request(
                        method, path,
                        params=params, json_body=json_body,
                        use_cache=use_cache, cache_ttl=cache_ttl,
                        _is_retry_after_reauth=True,
                    )
                raise NodeAPIError(
                    "401 Unauthorized — check NODE_API_SERVICE_TOKEN (or "
                    "NODE_API_SERVICE_EMAIL/PASSWORD for login()) against "
                    "the Node service's Verify middleware",
                    status_code=401, endpoint=path,
                )
            if resp.status_code == 404:
                await self._cb.record_failure()
                raise NodeAPIError("404 Not Found", status_code=404, endpoint=path)
            if 400 <= resp.status_code < 500:
                await self._cb.record_failure()
                raise NodeAPIError(f"client error: {resp.text[:200]}", status_code=resp.status_code, endpoint=path)
            if resp.status_code >= 500:
                last_exc = NodeAPIError(f"server error {resp.status_code}", status_code=resp.status_code, endpoint=path)
                await self._cb.record_failure()
                if is_last_attempt:
                    raise last_exc
                await asyncio.sleep(NODE_API_RETRY_BACKOFF_BASE_SEC * (2 ** attempt))
                continue

            # 2xx/3xx success
            await self._cb.record_success()
            try:
                raw = resp.json()
            except ValueError as e:
                raise NodeAPIError(f"non-JSON response body: {e}", status_code=resp.status_code, endpoint=path) from e

            data = _unwrap_envelope(raw, path)

            if cache_key:
                _cache_set(cache_key, data, cache_ttl or NODE_API_CACHE_TTL_SEC)
            return data

        raise NodeAPIError(f"failed after {NODE_API_MAX_RETRIES + 1} attempt(s): {last_exc}", endpoint=path)

    async def create_resource(self, path: str, payload: dict) -> dict:
        """Generic POST for creating resources via the Node API."""
        clear_node_api_cache()
        return await self._request("POST", path, json_body=payload)

    async def update_resource(self, path: str, payload: dict, method: str = "PATCH") -> dict:
        """Generic PATCH/PUT for updating resources via the Node API."""
        clear_node_api_cache()
        return await self._request(method, path, json_body=payload)

    async def delete_resource(self, path: str) -> dict:
        """Generic DELETE for removing resources via the Node API."""
        clear_node_api_cache()
        return await self._request("DELETE", path)

    # ── Finance: Dashboard / Forecast ───────────────────────────────────────
    async def get_finance_dashboard(self) -> dict:
        return await self._request("GET", "/finance/dashboard", use_cache=True, cache_ttl=15)

    async def get_cashflow_forecast(self) -> dict:
        return await self._request("GET", "/finance/forecast", use_cache=True, cache_ttl=60)

    # ── Finance: Invoices ────────────────────────────────────────────────────
    async def create_invoice(self, payload: dict) -> dict:
        """POST /finance/invoices — requires customer_id in payload."""
        return await self.create_resource("/finance/invoices", payload)

    async def get_invoices(self, status: Optional[str] = None, customer_id: Optional[str] = None,
                            limit: int = 100, skip: int = 0) -> List[dict]:
        """GET /finance/invoices — controller returns {invoices: [...], total}."""
        data = await self._request(
            "GET", "/finance/invoices",
            params={"status": status, "customer_id": customer_id, "limit": limit, "skip": skip},
            use_cache=True,
        )
        return _unwrap_list(data, "invoices")

    async def get_invoices_with_total(self, status: Optional[str] = None, customer_id: Optional[str] = None,
                                       limit: int = 100, skip: int = 0) -> dict:
        """Same as get_invoices() but preserves the {invoices, total} shape
        for callers that need the total count (e.g. pagination)."""
        return await self._request(
            "GET", "/finance/invoices",
            params={"status": status, "customer_id": customer_id, "limit": limit, "skip": skip},
            use_cache=True,
        )

    async def get_pending_invoices(self) -> List[dict]:
        """GET /finance/invoices/pending — controller returns a bare array."""
        data = await self._request("GET", "/finance/invoices/pending", use_cache=True)
        return _unwrap_list(data, "invoices")

    async def get_overdue_invoices(self, min_days: Optional[int] = None, limit: Optional[int] = None) -> List[dict]:
        """GET /finance/invoices/overdue — controller returns a bare array.
        Supports optional ?min_days=&limit= query params."""
        data = await self._request(
            "GET", "/finance/invoices/overdue",
            params={"min_days": min_days, "limit": limit}, use_cache=True,
        )
        return _unwrap_list(data, "invoices")

    async def get_invoice(self, invoice_id: str) -> dict:
        data = await self._request("GET", f"/finance/invoices/{invoice_id}", use_cache=True)
        return _unwrap_one(data, "invoice")

    async def update_invoice_status(self, invoice_id: str, status: str, **kwargs) -> dict:
        """PATCH /finance/invoices/:id/status — kwargs may include
        ai_decision, risk_score, decision_reason, action_plan, request_id."""
        payload = {"status": status, **kwargs}
        return await self.update_resource(f"/finance/invoices/{invoice_id}/status", payload)

    async def update_invoice_collection_strategy(self, invoice_id: str, **kwargs) -> dict:
        """PATCH /finance/invoices/:id/strategy — kwargs may include
        risk_score, collection_strategy, first_reminder_days, request_id."""
        return await self.update_resource(f"/finance/invoices/{invoice_id}/strategy", kwargs)

    async def delete_invoice(self, invoice_id: str) -> dict:
        return await self.delete_resource(f"/finance/invoices/{invoice_id}")

    # ── Finance: Customers ───────────────────────────────────────────────────
    async def create_customer(self, payload: dict) -> dict:
        return await self.create_resource("/finance/customers", payload)

    async def get_customers(self, service_status: Optional[str] = None, is_blacklisted: Optional[bool] = None,
                             limit: int = 50, skip: int = 0) -> List[dict]:
        """GET /finance/customers — controller returns {customers: [...], total}."""
        data = await self._request(
            "GET", "/finance/customers",
            params={"service_status": service_status, "is_blacklisted": is_blacklisted,
                    "limit": limit, "skip": skip},
            use_cache=True,
        )
        return _unwrap_list(data, "customers")

    async def get_customers_with_total(self, service_status: Optional[str] = None,
                                        is_blacklisted: Optional[bool] = None,
                                        limit: int = 50, skip: int = 0) -> dict:
        return await self._request(
            "GET", "/finance/customers",
            params={"service_status": service_status, "is_blacklisted": is_blacklisted,
                    "limit": limit, "skip": skip},
            use_cache=True,
        )

    async def get_customer(self, customer_id: str) -> dict:
        """GET /finance/customers/:id — returns {...customer, invoice_summary}."""
        data = await self._request("GET", f"/finance/customers/{customer_id}", use_cache=True)
        return _unwrap_one(data, "customer")

    async def update_customer(self, customer_id: str, payload: dict) -> dict:
        return await self.update_resource(f"/finance/customers/{customer_id}", payload)

    async def delete_customer(self, customer_id: str) -> dict:
        return await self.delete_resource(f"/finance/customers/{customer_id}")

    # ── Finance: Legal Cases ──────────────────────────────────────────────────
    async def create_legal_case(self, payload: dict) -> dict:
        """POST /finance/legal-cases — requires invoice_id in payload."""
        return await self.create_resource("/finance/legal-cases", payload)

    async def get_legal_cases(self, status: Optional[str] = None, customer_id: Optional[str] = None,
                               limit: int = 50) -> List[dict]:
        """GET /finance/legal-cases — controller returns a bare array."""
        data = await self._request(
            "GET", "/finance/legal-cases",
            params={"status": status, "customer_id": customer_id, "limit": limit}, use_cache=True,
        )
        return _unwrap_list(data, "cases", "legal_cases")

    async def get_legal_case(self, case_id: str) -> dict:
        data = await self._request("GET", f"/finance/legal-cases/{case_id}", use_cache=True)
        return _unwrap_one(data, "case")

    async def update_legal_case_status(self, case_id: str, status: str, **kwargs) -> dict:
        """PATCH /finance/legal-cases/:id/status — kwargs may include note, resolution."""
        payload = {"status": status, **kwargs}
        return await self.update_resource(f"/finance/legal-cases/{case_id}/status", payload)

    # ── Finance: Escalations ──────────────────────────────────────────────────
    async def get_active_escalations(self) -> List[dict]:
        data = await self._request("GET", "/finance/escalations/active", use_cache=True)
        return _unwrap_list(data, "escalations")

    async def get_escalation_status(self, invoice_id: str) -> dict:
        return await self._request("GET", f"/finance/escalations/{invoice_id}", use_cache=True)

    # ── Finance: Collections ──────────────────────────────────────────────────
    async def log_collection_action(self, payload: dict) -> dict:
        """POST /finance/collections/log."""
        return await self.create_resource("/finance/collections/log", payload)

    async def get_collection_log(self, invoice_id: Optional[str] = None, customer_id: Optional[str] = None,
                                  action_type: Optional[str] = None, limit: int = 50) -> List[dict]:
        """GET /finance/collections/log — controller returns a bare array."""
        data = await self._request(
            "GET", "/finance/collections/log",
            params={"invoice_id": invoice_id, "customer_id": customer_id,
                    "action_type": action_type, "limit": limit},
            use_cache=True,
        )
        return _unwrap_list(data, "logs", "log")

    async def get_collection_stats(self, days: int = 7) -> dict:
        return await self._request("GET", "/finance/collections/stats", params={"days": days}, use_cache=True)

    # ── Finance: Audit ────────────────────────────────────────────────────────
    async def write_finance_audit(self, **kwargs) -> dict:
        """POST /finance/audit — kwargs must include entity_id, domain, etc."""
        return await self.create_resource("/finance/audit", kwargs)

    async def get_finance_audit(self, entity_id: str, domain: str = "invoice") -> List[dict]:
        """GET /finance/audit/:domain/:entity_id — controller returns a bare array."""
        data = await self._request("GET", f"/finance/audit/{domain}/{entity_id}", use_cache=True)
        return _unwrap_list(data, "audit", "audit_trail")

    # ── Finance: Decisions ────────────────────────────────────────────────────
    async def save_finance_decision(self, **kwargs) -> dict:
        """POST /finance/decisions — kwargs must include entity_id (and
        typically entity, decision, etc.)."""
        return await self.create_resource("/finance/decisions", kwargs)

    async def get_finance_decisions(self, entity_id: str, entity: Optional[str] = None) -> List[dict]:
        """GET /finance/decisions/:entity_id — controller returns a bare array.
        Optional ?entity= query param (defaults server-side to
        "finance_invoices" when omitted)."""
        data = await self._request(
            "GET", f"/finance/decisions/{entity_id}",
            params={"entity": entity}, use_cache=True,
        )
        return _unwrap_list(data, "decisions")

    async def get_finance_decisions_history(self, **params) -> List[dict]:
        """GET /finance/decisions/history — must be requested before the
        /:entity_id route on the Node side (already ordered correctly in
        finance.routes.js). Pass through any supported query params
        (e.g. limit, skip, decision) via kwargs."""
        data = await self._request("GET", "/finance/decisions/history", params=params, use_cache=True)
        return _unwrap_list(data, "decisions")

    # ── HR: Leaves ────────────────────────────────────────────────────────────
    async def create_leave(self, payload: dict) -> dict:
        return await self.create_resource("/hr/leaves", payload)

    async def get_leaves(self, status: Optional[str] = None, limit: int = 50) -> List[dict]:
        data = await self._request("GET", "/hr/leaves", params={"status": status, "limit": limit}, use_cache=True)
        return _unwrap_list(data, "leaves")

    async def get_pending_leaves(self) -> List[dict]:
        data = await self._request("GET", "/hr/leaves/pending", use_cache=True)
        return _unwrap_list(data, "leaves")

    async def get_leave(self, leave_id: str) -> dict:
        data = await self._request("GET", f"/hr/leaves/{leave_id}", use_cache=True)
        return _unwrap_one(data, "leave")

    async def get_leave_decision(self, leave_id: str) -> dict:
        """GET /hr/leaves/:id/decision — the AI decision/explainability
        record for a specific leave request."""
        return await self._request("GET", f"/hr/leaves/{leave_id}/decision", use_cache=True)

    async def update_leave_status(self, leave_id: str, status: str, **kwargs) -> dict:
        payload = {"status": status, **kwargs}
        return await self.update_resource(f"/hr/leaves/{leave_id}/status", payload)

    async def delete_leave(self, leave_id: str) -> dict:
        return await self.delete_resource(f"/hr/leaves/{leave_id}")

    # ── HR: Salary Reviews ────────────────────────────────────────────────────
    async def create_salary_review(self, payload: dict) -> dict:
        return await self.create_resource("/hr/salary-reviews", payload)

    async def get_salary_reviews(self, status: Optional[str] = None, limit: int = 50) -> List[dict]:
        data = await self._request("GET", "/hr/salary-reviews", params={"status": status, "limit": limit}, use_cache=True)
        return _unwrap_list(data, "reviews", "salary_reviews")

    async def get_pending_salary_reviews(self) -> List[dict]:
        data = await self._request("GET", "/hr/salary-reviews/pending", use_cache=True)
        return _unwrap_list(data, "reviews", "salary_reviews")

    async def get_salary_review(self, review_id: str) -> dict:
        data = await self._request("GET", f"/hr/salary-reviews/{review_id}", use_cache=True)
        return _unwrap_one(data, "review", "salary_review")

    async def update_salary_review_status(self, review_id: str, status: str, **kwargs) -> dict:
        payload = {"status": status, **kwargs}
        return await self.update_resource(f"/hr/salary-reviews/{review_id}/status", payload)

    async def delete_salary_review(self, review_id: str) -> dict:
        return await self.delete_resource(f"/hr/salary-reviews/{review_id}")

    # ── HR: Absence Events ────────────────────────────────────────────────────
    async def create_absence_event(self, payload: dict) -> dict:
        return await self.create_resource("/hr/absence-events", payload)

    async def get_absence_events(self, status: Optional[str] = None, limit: int = 50) -> List[dict]:
        data = await self._request("GET", "/hr/absence-events", params={"status": status, "limit": limit}, use_cache=True)
        return _unwrap_list(data, "absences", "absence_events")

    async def get_pending_absence_events(self) -> List[dict]:
        data = await self._request("GET", "/hr/absence-events/pending", use_cache=True)
        return _unwrap_list(data, "absences", "absence_events")

    async def get_absence_event(self, absence_id: str) -> dict:
        data = await self._request("GET", f"/hr/absence-events/{absence_id}", use_cache=True)
        return _unwrap_one(data, "absence", "absence_event")

    async def get_employee_absences(self, employee_id: str, limit: int = 50) -> dict:
        """GET /hr/absence-events/employee/:employee_id — expected shape
        { absences: [...], unexcused_count_90d: N } (object, not a bare list)."""
        return await self._request(
            "GET", f"/hr/absence-events/employee/{employee_id}",
            params={"limit": limit}, use_cache=True,
        )

    async def update_absence_event_status(self, absence_id: str, status: str, **kwargs) -> dict:
        payload = {"status": status, **kwargs}
        return await self.update_resource(f"/hr/absence-events/{absence_id}/status", payload)

    async def delete_absence_event(self, absence_id: str) -> dict:
        return await self.delete_resource(f"/hr/absence-events/{absence_id}")

    # ── HR: Incentive Requests ────────────────────────────────────────────────
    async def create_incentive_request(self, payload: dict) -> dict:
        return await self.create_resource("/hr/incentive-requests", payload)

    async def get_incentive_requests(self, status: Optional[str] = None, limit: int = 50) -> List[dict]:
        data = await self._request("GET", "/hr/incentive-requests", params={"status": status, "limit": limit}, use_cache=True)
        return _unwrap_list(data, "incentives", "incentive_requests")

    async def get_pending_incentive_requests(self) -> List[dict]:
        data = await self._request("GET", "/hr/incentive-requests/pending", use_cache=True)
        return _unwrap_list(data, "incentives", "incentive_requests")

    async def get_incentive_request(self, incentive_id: str) -> dict:
        data = await self._request("GET", f"/hr/incentive-requests/{incentive_id}", use_cache=True)
        return _unwrap_one(data, "incentive", "incentive_request")

    async def update_incentive_status(self, incentive_id: str, status: str, **kwargs) -> dict:
        payload = {"status": status, **kwargs}
        return await self.update_resource(f"/hr/incentive-requests/{incentive_id}/status", payload)

    async def delete_incentive_request(self, incentive_id: str) -> dict:
        return await self.delete_resource(f"/hr/incentive-requests/{incentive_id}")

    # ── HR: Balance Audit ─────────────────────────────────────────────────────
    async def write_balance_audit(self, **kwargs) -> dict:
        return await self.create_resource("/hr/balance-audit", kwargs)

    async def get_balance_audit_history(self, employee_id: str) -> List[dict]:
        """GET /hr/balance-audit/:employee_id — there is no bare list-all
        endpoint, so this always needs an id."""
        data = await self._request("GET", f"/hr/balance-audit/{employee_id}", use_cache=True)
        return _unwrap_list(data, "history", "balance_audit_log")

    # ── HR: Audit ─────────────────────────────────────────────────────────────
    async def write_hr_audit(self, **kwargs) -> dict:
        """POST /hr/audit."""
        return await self.create_resource("/hr/audit", kwargs)

    async def get_hr_audit(self, entity_id: str, domain: str) -> List[dict]:
        """GET /hr/audit/:domain/:entity_id — domain must be one of:
        leave | salary | absence | incentive."""
        data = await self._request("GET", f"/hr/audit/{domain}/{entity_id}", use_cache=True)
        return _unwrap_list(data, "audit", "audit_trail")

    # ── HR: Dashboard ─────────────────────────────────────────────────────────
    async def get_hr_dashboard(self) -> dict:
        return await self._request("GET", "/hr/dashboard", use_cache=True, cache_ttl=15)


# ─────────────────────────────────────────────────────────────────────────
# Process-wide singleton — mirrors get_hr_db()/get_finance_db()
# ─────────────────────────────────────────────────────────────────────────

_node_api_client: Optional[NodeAPIClient] = None


def init_node_api_client() -> NodeAPIClient:
    """Call once from lifespan() startup. Idempotent — safe to call again."""
    global _node_api_client
    if _node_api_client is None:
        _node_api_client = NodeAPIClient()
        logger.info("✅ NodeAPIClient initialized — base_url=%s", NODE_API_BASE_URL)
    return _node_api_client


async def init_node_api_client_async() -> NodeAPIClient:
    """Preferred startup call from lifespan(): does everything
    init_node_api_client() does, and additionally performs an eager
    login (when NODE_API_SERVICE_EMAIL/PASSWORD are configured) so the
    service starts with a guaranteed-fresh token instead of waiting for
    the first real request to discover the static token is missing or
    stale. Falls back gracefully (logs a warning, does not raise) if
    login fails at startup — Node might just still be booting; the
    reactive 401-retry path and the periodic background KPI/leave scans
    will keep retrying afterward."""
    client = init_node_api_client()
    if client._can_self_renew:
        try:
            await client.login()
        except NodeAPIError as e:
            logger.warning(
                "⚠️ Eager login at startup failed (non-fatal, will retry "
                "on first request / proactive refresh): %s", e,
            )
    return client


def get_node_api_client() -> NodeAPIClient:
    """Sync accessor used everywhere else (same calling convention as
    get_hr_db()/get_finance_db()). Lazily initializes if lifespan hasn't
    run yet — constructing httpx.AsyncClient doesn't need a running
    event loop, only .request() calls do."""
    if _node_api_client is None:
        return init_node_api_client()
    return _node_api_client


async def close_node_api_client() -> None:
    global _node_api_client
    if _node_api_client is not None:
        await _node_api_client.aclose()
        _node_api_client = None
        logger.info("🔴 NodeAPIClient closed")