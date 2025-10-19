"""
Utility helpers for working with Redis in the OpenAI-First backend.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import cast

from redis.asyncio import Redis

from .config import get_settings

logger = logging.getLogger(__name__)


@lru_cache()
def _create_redis_client() -> Redis | None:
    """Create a Redis client if Redis is enabled."""
    settings = get_settings()
    if not settings.redis_enabled:
        return None

    url = settings.redis_url
    if not url:
        credentials = ""
        if settings.redis_username and settings.redis_password:
            credentials = f"{settings.redis_username}:{settings.redis_password}@"
        url = f"redis://{credentials}{settings.redis_host}:{settings.redis_port}/{settings.redis_db}"

    logger.info("Initializing Redis client for cache and rate limiting")
    client = Redis.from_url(
        url,
        encoding="utf-8",
        decode_responses=True,
        socket_timeout=3,
    )
    return cast(Redis, client)


def get_redis_client() -> Redis | None:
    """Return cached Redis client or None when disabled."""
    return _create_redis_client()
