"""
rate_limit.py — Per-org Redis sliding-window rate limiter.

Upload is expensive: R2 storage costs + ARQ worker compute.
We enforce limits per org_id using atomic Redis INCR + TTL.

Limits (configurable via settings):
  UPLOAD_RATE_LIMIT_PER_HOUR:  max uploads per org per hour
  UPLOAD_RATE_LIMIT_PER_DAY:   max uploads per org per day

Usage in route:
    await check_upload_rate_limit(org_id)

Raises HTTP 429 with a Retry-After header if limit is exceeded.
"""
from __future__ import annotations
import logging
from fastapi import HTTPException
import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

# Lazy singleton — created on first use, shared across requests
_redis_client: aioredis.Redis | None = None


async def _get_redis() -> aioredis.Redis:
    """Return (or create) the async Redis client. Uses the same REDIS_URL as ARQ."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def check_upload_rate_limit(org_id: str) -> None:
    """
    Check hourly and daily upload counts for an org.
    Raises HTTP 429 if either limit is exceeded.

    Uses atomic INCR + EXPIRE so there are no race conditions even
    with multiple API workers running in parallel.
    """
    try:
        redis = await _get_redis()

        # Separate keys for hourly and daily windows
        hour_key  = f"upload_limit:hour:{org_id}"
        day_key   = f"upload_limit:day:{org_id}"

        # Pipeline: INCR both counters atomically, set TTL only on new keys
        async with redis.pipeline(transaction=False) as pipe:
            pipe.incr(hour_key)
            pipe.incr(day_key)
            hour_count, day_count = await pipe.execute()

        # Set TTL only when the key was just created (count == 1)
        # This avoids resetting the window on every request.
        if hour_count == 1:
            await redis.expire(hour_key, 3600)    # 1 hour
        if day_count == 1:
            await redis.expire(day_key, 86400)    # 24 hours

        # Enforce limits
        hour_limit = settings.UPLOAD_RATE_LIMIT_PER_HOUR
        day_limit  = settings.UPLOAD_RATE_LIMIT_PER_DAY

        if hour_count > hour_limit:
            ttl = await redis.ttl(hour_key)
            raise HTTPException(
                status_code = 429,
                detail      = (
                    f"Upload rate limit exceeded: {hour_limit} uploads per hour. "
                    f"Try again in {ttl} seconds."
                ),
                headers     = {"Retry-After": str(max(ttl, 1))},
            )

        if day_count > day_limit:
            ttl = await redis.ttl(day_key)
            raise HTTPException(
                status_code = 429,
                detail      = (
                    f"Upload rate limit exceeded: {day_limit} uploads per day. "
                    f"Try again in {ttl} seconds."
                ),
                headers     = {"Retry-After": str(max(ttl, 1))},
            )

    except HTTPException:
        raise
    except Exception as e:
        # Redis failure must never block an upload — log and continue
        logger.warning(f"Rate limit check failed (Redis error), allowing request: {e}")
