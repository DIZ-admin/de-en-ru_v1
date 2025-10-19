"""
Simple JWT authentication - OpenAI-First approach.
Minimal code, maximum security.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from time import time
from typing import Iterable, List, Tuple

import jwt
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from prometheus_client import Counter
from redis.exceptions import RedisError

from .config import get_settings
from .redis_utils import get_redis_client

settings = get_settings()
security = HTTPBearer()
logger = logging.getLogger(__name__)

rate_limit_block_counter = Counter(
    "rate_limit_blocked_total",
    "Number of requests blocked due to rate limiting",
)


def _normalize_pem(value: str) -> str:
    return value.replace("\\n", "\n").strip()


def _load_data_from_path(path: str | None) -> str | None:
    if not path:
        return None
    try:
        data = Path(path).read_text(encoding="utf-8")
        return data.strip()
    except FileNotFoundError:
        logger.error("JWT key file not found: %s", path)
        raise


def _load_combined_key(path: str | None, inline: str | None) -> str | None:
    if inline and inline.strip():
        return _normalize_pem(inline)
    if path:
        data = _load_data_from_path(path)
        if data:
            return _normalize_pem(data)
    return None


@lru_cache()
def _get_private_key() -> str | None:
    return _load_combined_key(settings.jwt_private_key_path, settings.jwt_private_key)


@lru_cache()
def _get_public_key() -> str | None:
    key = _load_combined_key(settings.jwt_public_key_path, settings.jwt_public_key)
    if key:
        return key
    # Fallback to private key if public not provided
    return _get_private_key()


@lru_cache()
def _get_additional_public_keys() -> Tuple[str, ...]:
    keys: List[str] = []
    for path in settings.jwt_additional_public_keys_paths:
        data = _load_data_from_path(path)
        if data:
            keys.append(_normalize_pem(data))
    for key in settings.jwt_additional_public_keys:
        if key:
            keys.append(_normalize_pem(key))
    return tuple(keys)


def _iter_verification_keys(token_kid: str | None) -> Iterable[str]:
    primary = _get_public_key()
    additional = list(_get_additional_public_keys())

    if token_kid and settings.jwt_kid and token_kid == settings.jwt_kid:
        if primary:
            yield primary
        for key in additional:
            yield key
        return

    if primary:
        yield primary
    for key in additional:
        yield key


def _clear_key_caches() -> None:
    _get_private_key.cache_clear()
    _get_public_key.cache_clear()
    _get_additional_public_keys.cache_clear()


def create_access_token(user_id: str) -> dict[str, str | int]:
    """
    Create JWT access token.

    Args:
        user_id: User identifier

    Returns:
        Dictionary with token and expiry time
    """
    expire = datetime.now(UTC) + timedelta(
        minutes=settings.jwt_access_token_expire_minutes
    )

    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.now(UTC),
    }

    algorithm = settings.jwt_algorithm.upper()

    if algorithm.startswith("RS"):
        private_key = _get_private_key()
        if not private_key:
            raise RuntimeError(
                "RS256 signing requires JWT_PRIVATE_KEY or JWT_PRIVATE_KEY_PATH"
            )

        headers = {"kid": settings.jwt_kid} if settings.jwt_kid else None
        token = jwt.encode(
            payload,
            private_key,
            algorithm=algorithm,
            headers=headers,
        )
    else:
        token = jwt.encode(
            payload,
            settings.jwt_secret_key,
            algorithm=algorithm,
        )

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.jwt_access_token_expire_minutes * 60,
    }


def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
    """
    Verify JWT token and return user_id.

    Args:
        credentials: HTTP Bearer credentials

    Returns:
        User ID from token

    Raises:
        HTTPException: If token is invalid or expired
    """
    token = credentials.credentials
    algorithm = settings.jwt_algorithm.upper()

    header = jwt.get_unverified_header(token)
    token_kid = header.get("kid") if isinstance(header, dict) else None

    if algorithm.startswith("RS"):
        keys = list(_iter_verification_keys(token_kid))
        if not keys:
            logger.error("No public keys configured for RS256 verification")
            raise HTTPException(status_code=401, detail="Invalid token")
    else:
        keys = [settings.jwt_secret_key]

    for key in keys:
        try:
            payload = jwt.decode(
                token,
                key,
                algorithms=[algorithm],
            )
            user_id: str | None = payload.get("sub")
            if user_id is None:
                raise HTTPException(status_code=401, detail="Invalid token")
            return user_id
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidSignatureError:
            continue
        except jwt.InvalidTokenError:
            continue

    raise HTTPException(status_code=401, detail="Invalid token")


# In-memory fallback for rate limiting
_rate_limits: dict[str, list[float]] = defaultdict(list)


async def check_rate_limit(user_id: str) -> None:
    """
    Check if user exceeded rate limit.

    Args:
        user_id: User identifier

    Raises:
        HTTPException: If rate limit exceeded
    """
    redis_client = get_redis_client()
    window = settings.rate_limit_window_seconds
    limit = settings.rate_limit_max_calls

    if redis_client:
        key = f"rate_limit:{user_id}"
        now = time()
        window_start = now - window

        try:
            await redis_client.zremrangebyscore(key, "-inf", window_start)
            current = await redis_client.zcard(key)

            if current >= limit:
                rate_limit_block_counter.inc()
                raise HTTPException(
                    status_code=429, detail="Rate limit exceeded. Try again later."
                )

            await redis_client.zadd(key, {str(now): now})
            await redis_client.expire(key, window)
            return
        except RedisError as exc:
            logger.warning(
                "Redis rate limiting failed, falling back to memory: %s", exc
            )

    now = time()
    window_start = now - window

    # Remove old entries
    _rate_limits[user_id] = [t for t in _rate_limits[user_id] if t > window_start]

    # Check limit
    if len(_rate_limits[user_id]) >= limit:
        rate_limit_block_counter.inc()
        raise HTTPException(
            status_code=429, detail="Rate limit exceeded. Try again later."
        )

    # Add current request
    _rate_limits[user_id].append(now)
