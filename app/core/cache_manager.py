"""
🚀 Redis Cache Manager — Production Grade
==========================================
File: app/core/cache_manager.py

Design goals:
    ✅ Lazy singleton connection (نفس فكرة get_hr_db() / get_finance_db())
    ✅ Graceful degradation — لو Redis نزل أو مش متصل، كل method بترجع
       None/False بدل ما تعمل raise، فالـ caller دايمًا يرجع يحسب من DB.
       Redis نزوله مينفعش يكسر الـ API.
    ✅ Log rate-limited (مش هيسبام اللوج لو Redis نزل تمامًا)
    ✅ Pattern-based invalidation — finance:dashboard:* يمسح كل
       الـ variants (days=7, days=30, ...) بنداء واحد.
"""

import json
import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    import redis.asyncio as aioredis
    from redis.exceptions import RedisError
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False
    aioredis = None
    RedisError = Exception


class RedisCacheManager:
    """Lazy singleton async Redis client wrapper."""

    def __init__(self, redis_url: str, enabled: bool = True):
        self._redis_url          = redis_url
        self._enabled            = enabled and _REDIS_AVAILABLE
        self._client             = None
        self._last_error_log     = 0.0
        self._error_log_cooldown = 30.0
        self._healthy            = True

        if enabled and not _REDIS_AVAILABLE:
            logger.warning(
                "⚠️ [CacheManager] 'redis' package غير مثبت — الكاش متعطل، "
                "كل القراءات هتروح على DB مباشرة. شغّل: pip install redis"
            )

    def _get_client(self):
        if not self._enabled:
            return None
        if self._client is None:
            try:
                self._client = aioredis.from_url(
                    self._redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                    retry_on_timeout=False,
                    max_connections=20,
                )
            except Exception as e:
                self._log_error("create client", e)
                return None
        return self._client

    def _log_error(self, op: str, exc: Exception) -> None:
        now = time.monotonic()
        if now - self._last_error_log > self._error_log_cooldown:
            logger.warning(
                "⚠️ [CacheManager] Redis %s failed (%s) — fallback لقراءة مباشرة من DB. "
                "(هذا التحذير محدود لمرة كل %.0fs)",
                op, exc, self._error_log_cooldown,
            )
            self._last_error_log = now
        self._healthy = False

    async def ping(self) -> bool:
        client = self._get_client()
        if client is None:
            return False
        try:
            await client.ping()
            self._healthy = True
            return True
        except Exception as e:
            self._log_error("ping", e)
            return False

    @property
    def healthy(self) -> bool:
        return self._healthy and self._enabled

    # ── get / set / delete — كل واحدة fail-safe ────────────────────────────

    async def get_json(self, key: str) -> Optional[Any]:
        client = self._get_client()
        if client is None:
            return None
        try:
            raw = await client.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("⚠️ [CacheManager] Corrupt cache value at %s: %s", key, e)
            return None
        except Exception as e:
            self._log_error(f"GET {key}", e)
            return None

    async def set_json(self, key: str, value: Any, ttl: int = 300) -> bool:
        client = self._get_client()
        if client is None:
            return False
        try:
            await client.set(key, json.dumps(value, default=str), ex=ttl)
            self._healthy = True
            return True
        except Exception as e:
            self._log_error(f"SET {key}", e)
            return False

    async def delete(self, *keys: str) -> int:
        client = self._get_client()
        if client is None or not keys:
            return 0
        try:
            return await client.delete(*keys)
        except Exception as e:
            self._log_error(f"DEL {keys}", e)
            return 0

    async def delete_pattern(self, pattern: str) -> int:
        """يمسح كل المفاتيح المطابقة لـ pattern، مثلاً 'finance:dashboard:*'."""
        client = self._get_client()
        if client is None:
            return 0
        deleted = 0
        try:
            async for key in client.scan_iter(match=pattern, count=100):
                await client.delete(key)
                deleted += 1
            return deleted
        except Exception as e:
            self._log_error(f"SCAN/DEL {pattern}", e)
            return deleted

    async def close(self) -> None:
        if self._client is not None:
            try:
                await self._client.close()
            except Exception:
                pass


# ════════════════════════════════════════════════════════════════════════════
_cache_manager: Optional[RedisCacheManager] = None


def get_cache_manager() -> RedisCacheManager:
    global _cache_manager
    if _cache_manager is None:
        from config.settings import get_settings
        settings = get_settings()
        _cache_manager = RedisCacheManager(
            redis_url=getattr(settings, "REDIS_URL", "redis://localhost:6379/0"),
            enabled=getattr(settings, "REDIS_ENABLED", True),
        )
    return _cache_manager


class CacheKeys:
    FINANCE_DASHBOARD_PREFIX = "finance:dashboard"

    @staticmethod
    def finance_dashboard(days: int) -> str:
        return f"{CacheKeys.FINANCE_DASHBOARD_PREFIX}:{days}d"

    @staticmethod
    def finance_dashboard_pattern() -> str:
        return f"{CacheKeys.FINANCE_DASHBOARD_PREFIX}:*"


async def invalidate_finance_dashboard_cache() -> None:
    """تُستدعى بعد أي write يأثر على /finance/actions/dashboard-data
    (action_stats, escalations, legal cases, collection log)."""
    try:
        cache   = get_cache_manager()
        deleted = await cache.delete_pattern(CacheKeys.finance_dashboard_pattern())
        if deleted:
            logger.debug("🗑️ [CacheManager] Invalidated %d finance dashboard key(s)", deleted)
    except Exception as e:
        logger.debug("invalidate_finance_dashboard_cache failed (non-critical): %s", e)
