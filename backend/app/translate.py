"""
Translation service using OpenAI Responses API directly.
OpenAI-First approach - minimal abstraction.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import time
from typing import Any, AsyncIterator, Awaitable, Callable, Literal, TypeVar, cast

from openai import APIError, AsyncOpenAI, RateLimitError
from openai.types.responses import Response, ResponseInputParam
from pydantic import BaseModel, Field
from prometheus_client import Counter
from redis.exceptions import RedisError

from .config import get_settings
from .redis_utils import get_redis_client


settings = get_settings()
client = AsyncOpenAI(api_key=settings.openai_api_key)
logger = logging.getLogger(__name__)

T = TypeVar("T")

cache_hit_counter = Counter(
    "translation_cache_hits_total",
    "Number of translation cache hits",
)
cache_miss_counter = Counter(
    "translation_cache_misses_total",
    "Number of translation cache misses",
)


# Language types
Language = Literal["ru", "en", "de"]


class TranslationRequest(BaseModel):
    """Translation request model."""

    text: str = Field(..., min_length=1, max_length=4000)
    source_lang: Language | Literal["auto"] = "auto"
    target_lang: Language


class TranslationResponse(BaseModel):
    """Translation response model."""

    translated_text: str
    detected_lang: Language | None = None
    model: str = settings.default_model


class OpenAIRetryExceeded(RuntimeError):
    """Raised when OpenAI retries are exhausted."""

    def __init__(self, reason: str, original: Exception):
        super().__init__(reason)
        self.reason = reason
        self.original = original


def get_system_prompt(target_lang: Language) -> str:
    """
    Get system prompt for translation.

    Args:
        target_lang: Target language code

    Returns:
        System prompt string
    """
    lang_names = {"ru": "Russian", "en": "English", "de": "German"}

    return f"""You are a professional translator. Translate the following text to {lang_names[target_lang]}.
Only return the translation, nothing else. Preserve the tone and meaning."""


def _is_retryable_api_error(error: APIError) -> bool:
    status_code = cast(int | None, getattr(error, "status_code", None))
    if status_code is None:
        return True
    return status_code >= 500


async def _call_with_retry(
    func: Callable[[], Awaitable[T]],
    *,
    operation: str,
    context: dict[str, Any] | None = None,
) -> T:
    attempts = settings.openai_retry_max_attempts
    delay = settings.openai_retry_initial_delay
    for attempt in range(1, attempts + 1):
        try:
            return await func()
        except RateLimitError as exc:
            logger.warning(
                "OpenAI rate limit",
                extra={
                    "operation": operation,
                    "attempt": attempt,
                    "error": str(exc),
                    **(context or {}),
                },
            )
            if attempt == attempts:
                raise OpenAIRetryExceeded("rate_limit", exc) from exc
        except APIError as exc:
            logger.error(
                "OpenAI API error",
                extra={
                    "operation": operation,
                    "attempt": attempt,
                    "status_code": getattr(exc, "status_code", None),
                    "error": str(exc),
                    **(context or {}),
                },
            )
            if attempt == attempts or not _is_retryable_api_error(exc):
                raise OpenAIRetryExceeded("api_error", exc) from exc

        await asyncio.sleep(delay + random.uniform(0, delay))
        delay *= 2

    raise OpenAIRetryExceeded("max_attempts_exceeded", RuntimeError(operation))


async def _stream_translation_with_retry(
    request: TranslationRequest,
) -> AsyncIterator[str]:
    messages: ResponseInputParam = [
        {"role": "system", "content": get_system_prompt(request.target_lang)},
        {"role": "user", "content": request.text},
    ]
    attempts = settings.openai_retry_max_attempts
    delay = settings.openai_retry_initial_delay
    for attempt in range(1, attempts + 1):
        stream = client.responses.stream(
            model=settings.default_model,
            input=messages,
            temperature=0.3,
            max_output_tokens=settings.max_text_length,
        )

        try:
            async with stream as events:
                async for event in events:
                    if event.type == "response.output_text.delta" and event.delta:
                        yield event.delta
            return
        except RateLimitError as exc:
            logger.warning(
                "OpenAI rate limit (stream)",
                extra={"attempt": attempt, "error": str(exc)},
            )
            if attempt == attempts:
                raise OpenAIRetryExceeded("rate_limit", exc) from exc
        except APIError as exc:
            logger.error(
                "OpenAI API error (stream)",
                extra={
                    "attempt": attempt,
                    "status_code": getattr(exc, "status_code", None),
                    "error": str(exc),
                },
            )
            if attempt == attempts or not _is_retryable_api_error(exc):
                raise OpenAIRetryExceeded("api_error", exc) from exc

        await asyncio.sleep(delay + random.uniform(0, delay))
        delay *= 2

    raise OpenAIRetryExceeded("max_attempts_exceeded", RuntimeError("stream"))


async def translate_text(request: TranslationRequest) -> TranslationResponse:
    """
    Translate text using OpenAI Responses API (sync mode).

    Args:
        request: Translation request

    Returns:
        Translation response
    """
    messages: ResponseInputParam = [
        {"role": "system", "content": get_system_prompt(request.target_lang)},
        {"role": "user", "content": request.text},
    ]

    async def invoke() -> Response:
        return await client.responses.create(
            model=settings.default_model,
            input=messages,
            temperature=0.3,
            max_output_tokens=settings.max_text_length,
        )

    response = await _call_with_retry(
        invoke,
        operation="responses.create",
        context={"target_lang": request.target_lang},
    )

    translated_text = response.output_text or ""

    return TranslationResponse(
        translated_text=translated_text,
        detected_lang=request.source_lang if request.source_lang != "auto" else None,
        model=settings.default_model,
    )


async def translate_text_stream(request: TranslationRequest) -> AsyncIterator[str]:
    """
    Translate text using OpenAI Responses API (streaming mode).

    Args:
        request: Translation request

    Yields:
        Text chunks as they arrive
    """
    async for chunk in _stream_translation_with_retry(request):
        yield chunk


# Simple in-memory cache fallback with TTL
_translation_cache: dict[str, tuple[str, float]] = {}


def get_cache_key(text: str, target_lang: Language) -> str:
    """Generate cache key for translation."""
    text_hash = hashlib.md5(text.encode()).hexdigest()
    return f"{target_lang}:{text_hash}"


async def translate_with_cache(request: TranslationRequest) -> TranslationResponse:
    """
    Translate with caching support.

    Args:
        request: Translation request

    Returns:
        Translation response (potentially cached)
    """
    cache_key = get_cache_key(request.text, request.target_lang)

    redis_client = get_redis_client()

    if redis_client:
        try:
            cached_value = await redis_client.get(cache_key)
        except RedisError as exc:
            logger.warning("Redis cache get failed: %s", exc)
            cached_value = None

        if cached_value:
            cache_hit_counter.inc()
            return TranslationResponse(
                translated_text=cached_value,
                detected_lang=(
                    request.source_lang if request.source_lang != "auto" else None
                ),
                model=settings.default_model,
            )
    else:
        cached_entry = _translation_cache.get(cache_key)
        if cached_entry:
            cached_value, expires_at = cached_entry
            if expires_at > time.time():
                cache_hit_counter.inc()
                return TranslationResponse(
                    translated_text=cached_value,
                    detected_lang=(
                        request.source_lang if request.source_lang != "auto" else None
                    ),
                    model=settings.default_model,
                )
            _translation_cache.pop(cache_key, None)

    cache_miss_counter.inc()

    # Translate
    response = await translate_text(request)

    # Cache result
    if redis_client:
        try:
            await redis_client.set(
                cache_key,
                response.translated_text,
                ex=settings.translation_cache_ttl,
            )
        except RedisError as exc:
            logger.warning("Redis cache set failed: %s", exc)
    else:
        expires_at = time.time() + settings.translation_cache_ttl
        _translation_cache[cache_key] = (response.translated_text, expires_at)

    return response
