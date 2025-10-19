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
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, Literal, NamedTuple, TypeVar, cast

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


class VoiceTranscriptionResult(NamedTuple):
    text: str
    language: str | None
    confidence: float | None
    duration_s: float | None


class VoiceTranslationMetadata(BaseModel):
    audio_duration_s: float | None = None
    transcription_latency_ms: float
    translation_latency_ms: float


class VoiceTranslationResponsePayload(BaseModel):
    transcription: str
    detected_lang: str | None = None
    confidence: float | None = None
    translations: Dict[str, str]
    metadata: VoiceTranslationMetadata


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


def _get_attr(data: Any, key: str) -> Any:
    if isinstance(data, dict) and key in data:
        return data[key]
    return getattr(data, key, None)


async def _transcribe_with_model(path: str, model: str) -> Any:
    async def invoke() -> Any:
        with open(path, "rb") as audio_file:
            return await client.audio.transcriptions.create(
                model=model,
                file=audio_file,
                response_format="verbose_json",
            )

    return await _call_with_retry(
        invoke,
        operation="audio.transcriptions.create",
        context={"model": model},
    )


async def transcribe_audio_file(path: str) -> VoiceTranscriptionResult:
    primary_model = settings.voice_transcription_model
    fallback_model = settings.voice_transcription_fallback_model

    models_to_try: list[str] = []
    if primary_model:
        models_to_try.append(primary_model)
    if fallback_model and fallback_model not in models_to_try:
        models_to_try.append(fallback_model)

    last_exception: OpenAIRetryExceeded | None = None

    for index, model_name in enumerate(models_to_try):
        try:
            result = await _transcribe_with_model(path, model_name)
        except OpenAIRetryExceeded as exc:
            last_exception = exc
            original = getattr(exc, "original", None)
            logger.warning(
                "Transcription with model %s failed (reason=%s, status=%s, message=%s)",
                model_name,
                exc.reason,
                getattr(original, "status_code", None),
                getattr(original, "message", str(exc)),
            )
            is_last_model = index == len(models_to_try) - 1
            if is_last_model:
                raise
            continue
        else:
            text = _get_attr(result, "text")
            if not text or not isinstance(text, str):
                raise ValueError("Transcription did not return text")

            language = _get_attr(result, "language")
            if isinstance(language, str):
                language = language.lower()
            else:
                language = None

            confidence = _get_attr(result, "language_probability")
            if isinstance(confidence, (int, float)):
                confidence = float(confidence)
            else:
                confidence = None

            duration = _get_attr(result, "duration")
            if isinstance(duration, (int, float)):
                duration = float(duration)
            else:
                duration = None

            return VoiceTranscriptionResult(
                text=text,
                language=language,
                confidence=confidence,
                duration_s=duration,
            )

    assert last_exception is not None  # For mypy
    raise last_exception


async def translate_voice_text(
    transcription: str,
    detected_lang: str | None,
    confidence: float | None,
    target_langs: list[Language],
) -> tuple[dict[str, str], str, str]:
    normalized_lang = None
    if detected_lang and detected_lang.lower() in {"ru", "en", "de"}:
        normalized_lang = detected_lang.lower()

    use_detected = False
    if normalized_lang:
        if confidence is None:
            use_detected = True
        else:
            use_detected = confidence >= settings.voice_detection_confidence_threshold

    source_lang: Literal["auto"] | Language
    if use_detected:
        source_lang = cast(Language, normalized_lang)
        reported_lang = normalized_lang
    else:
        source_lang = "auto"
        reported_lang = normalized_lang or "unknown"

    translations: dict[str, str] = {}

    async def _translate(lang: Language) -> tuple[Language, str]:
        if use_detected and lang == source_lang:
            return lang, transcription
        response = await translate_with_cache(
            TranslationRequest(
                text=transcription,
                source_lang=source_lang,
                target_lang=lang,
            )
        )
        return lang, response.translated_text

    tasks = [_translate(lang) for lang in target_langs]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, Exception):
            raise result
        lang, translated = result
        translations[lang] = translated

    return translations, reported_lang, source_lang if use_detected else "auto"
