"""Caching and Rate Limiting for TrustShop AI using Redis with graceful offline fallback."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import redis

from app.config import settings

logger = logging.getLogger(__name__)

_REDIS_CLIENT: redis.Redis | None = None
_REDIS_CHECKED = False
_IN_MEMORY_CACHE: dict[str, tuple[float, str]] = {}
_IN_MEMORY_RATELIMIT: dict[str, tuple[float, int]] = {}


def get_redis_client() -> redis.Redis | None:
    """Get active Redis client or return None if Redis is unreachable."""
    global _REDIS_CLIENT, _REDIS_CHECKED
    if _REDIS_CLIENT is not None:
        return _REDIS_CLIENT
    if _REDIS_CHECKED:
        return None

    redis_url = settings.get("redis_url", "redis://localhost:6379/0")
    try:
        client = redis.from_url(
            redis_url,
            socket_timeout=0.3,
            socket_connect_timeout=0.3,
            decode_responses=True,
        )
        client.ping()
        _REDIS_CLIENT = client
        return _REDIS_CLIENT
    except (redis.RedisError, OSError):
        if not _REDIS_CHECKED:
            _REDIS_CHECKED = True
            logger.warning("Redis is unavailable at %s. Operating in graceful degraded mode (no Redis).", redis_url)
        return None


def is_redis_available() -> bool:
    """Check if Redis connection is active and responsive."""
    client = get_redis_client()
    if client is None:
        return False
    try:
        return bool(client.ping())
    except (redis.RedisError, OSError):
        return False


def get_cached_rdap(domain: str) -> dict[str, Any] | None:
    """Retrieve cached RDAP response for domain. Falls back to in-memory cache if Redis is down."""
    clean_domain = domain.strip().lower()
    key = f"rdap:{clean_domain}"

    client = get_redis_client()
    if client is not None:
        try:
            val = client.get(key)
            if val:
                return json.loads(val)
        except (redis.RedisError, OSError):
            pass

    # In-memory fallback
    if key in _IN_MEMORY_CACHE:
        expires_at, val_str = _IN_MEMORY_CACHE[key]
        if time.time() < expires_at:
            return json.loads(val_str)
        del _IN_MEMORY_CACHE[key]

    return None


def set_cached_rdap(domain: str, data: dict[str, Any], ttl_s: int | None = None) -> bool:
    """Store RDAP result in cache with TTL (default 24h)."""
    clean_domain = domain.strip().lower()
    key = f"rdap:{clean_domain}"
    ttl = ttl_s or int(settings.get("cache", {}).get("rdap_ttl_s", 86400))
    val_str = json.dumps(data)

    stored = False
    client = get_redis_client()
    if client is not None:
        try:
            client.setex(key, ttl, val_str)
            stored = True
        except (redis.RedisError, OSError):
            pass

    # Always keep in-memory backup
    _IN_MEMORY_CACHE[key] = (time.time() + ttl, val_str)
    return stored


def check_rate_limit(
    identifier: str,
    limit: int | None = None,
    window_s: int = 60,
    force_in_memory: bool = False,
) -> tuple[bool, int, int]:
    """Fixed-window rate limiter per client IP.
    Returns: (is_allowed, current_count, remaining)
    """
    max_requests = limit if limit is not None else int(settings.get("rate_limit", {}).get("per_minute", 30))
    window_bucket = int(time.time() // window_s)
    key = f"ratelimit:{identifier}:{window_bucket}"

    client = get_redis_client() if not force_in_memory else None
    if client is not None:
        try:
            current = client.incr(key)
            if current == 1:
                client.expire(key, window_s + 5)
            is_allowed = current <= max_requests
            remaining = max(0, max_requests - current)
            return is_allowed, current, remaining
        except (redis.RedisError, OSError):
            # Redis failure: fail-open as specified
            pass

    # In-memory rate limiting fallback
    now = time.time()
    if key in _IN_MEMORY_RATELIMIT:
        expires_at, count = _IN_MEMORY_RATELIMIT[key]
        if now < expires_at:
            count += 1
            _IN_MEMORY_RATELIMIT[key] = (expires_at, count)
            is_allowed = count <= max_requests
            return is_allowed, count, max(0, max_requests - count)

    _IN_MEMORY_RATELIMIT[key] = (now + window_s, 1)
    return True, 1, max_requests - 1


def clear_test_caches() -> None:
    """Clear in-memory test caches."""
    _IN_MEMORY_CACHE.clear()
    _IN_MEMORY_RATELIMIT.clear()
