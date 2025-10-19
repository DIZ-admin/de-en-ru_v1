"""
FastAPI application - OpenAI-First approach.
Минимальный backend, максимум делегируется OpenAI SDK.
"""

from collections.abc import AsyncIterator
import logging
import mimetypes
import os
from pathlib import Path
import tempfile
import time
from contextlib import asynccontextmanager
from typing import cast

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from prometheus_client import Counter, Histogram, make_asgi_app
from redis.exceptions import RedisError

from .auth import check_rate_limit, create_access_token, verify_token
from .config import get_settings
from .redis_utils import get_redis_client
from .security import SecurityHeadersMiddleware
from .translate import (
    OpenAIRetryExceeded,
    TranslationRequest,
    TranslationResponse,
    Language,
    translate_text_stream,
    translate_with_cache,
    transcribe_audio_file,
    translate_voice_text,
    VoiceTranslationMetadata,
    VoiceTranslationResponsePayload,
)


settings = get_settings()
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

# Register additional audio mimetypes that are commonly reported by browsers
_CUSTOM_AUDIO_MIMETYPES: dict[str, str] = {
    "audio/mp4": ".m4a",
    "audio/mp4a-latm": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/x-wav": ".wav",
    "audio/flac": ".flac",
    "audio/x-flac": ".flac",
    "audio/oga": ".ogg",
    "video/webm": ".webm",
    "video/mp4": ".mp4",
    "video/mpeg": ".mpeg",
}

for _mime, _ext in _CUSTOM_AUDIO_MIMETYPES.items():
    mimetypes.add_type(_mime, _ext, strict=False)

_ALLOWED_AUDIO_MIME_TYPES = {mime.lower() for mime in settings.voice_allowed_mime_types}


# Prometheus metrics
translation_counter = Counter(
    "translations_total",
    "Total translation requests",
    ["target_lang", "status"],
)
latency_histogram = Histogram(
    "translation_latency_seconds",
    "Translation latency",
)

voice_request_counter = Counter(
    "voice_requests_total",
    "Total voice translation requests",
    ["status"],
)
voice_detected_counter = Counter(
    "voice_detected_language_total",
    "Detected languages for voice input",
    ["lang"],
)
voice_transcription_latency = Histogram(
    "voice_transcription_latency_seconds",
    "Voice transcription latency",
)
voice_translation_latency = Histogram(
    "voice_translation_latency_seconds",
    "Voice translation latency",
)


def _resolve_audio_suffix(upload_file: UploadFile) -> str:
    """Determine a safe file suffix for temporary audio files."""
    content_type = (upload_file.content_type or "").lower()
    suffix = None
    if content_type:
        suffix = mimetypes.guess_extension(content_type)
        if not suffix and content_type in _CUSTOM_AUDIO_MIMETYPES:
            suffix = _CUSTOM_AUDIO_MIMETYPES[content_type]

    if not suffix and upload_file.filename:
        suffix = Path(upload_file.filename).suffix.lower()

    if suffix and suffix.startswith("."):
        return suffix

    raise HTTPException(status_code=415, detail="Unsupported audio content type")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan events."""
    logger.info("Starting application...")
    yield
    logger.info("Shutting down application...")


app = FastAPI(
    title="Trilingual Translator - OpenAI First",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(SecurityHeadersMiddleware)


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if settings.app_env == "production" and any(
    origin == "*" for origin in settings.allowed_origins
):
    logger.warning(
        "Wildcard CORS detected in production environment. Set ALLOWED_ORIGINS to explicit domains."
    )


# ============= Authentication =============


@app.post("/auth/token")
async def get_token(user_id: str = "demo-user") -> dict[str, str | int]:
    """
    Get JWT access token.

    Args:
        user_id: User identifier (demo для MVP)

    Returns:
        JWT token and expiry
    """
    return create_access_token(user_id)


# ============= Translation =============


@app.post("/translate", response_model=TranslationResponse)
async def translate(
    request: TranslationRequest,
    user_id: str = Depends(verify_token),
) -> TranslationResponse:
    """
    Synchronous translation endpoint.

    Args:
        request: Translation request
        user_id: Authenticated user ID

    Returns:
        Translation response
    """
    # Rate limiting
    await check_rate_limit(user_id)

    # Metrics
    translation_counter.labels(
        target_lang=request.target_lang,
        status="requested",
    ).inc()

    try:
        with latency_histogram.time():
            response = await translate_with_cache(request)

        translation_counter.labels(
            target_lang=request.target_lang,
            status="success",
        ).inc()

        return response

    except OpenAIRetryExceeded as exc:
        logger.error(
            "OpenAI retries exhausted",
            extra={"reason": exc.reason, "target_lang": request.target_lang},
        )
        if exc.reason == "rate_limit":
            translation_counter.labels(
                target_lang=request.target_lang, status="rate_limited"
            ).inc()
            raise HTTPException(
                status_code=429, detail="Translation service rate limit exceeded"
            )

        translation_counter.labels(
            target_lang=request.target_lang, status="api_error"
        ).inc()
        raise HTTPException(
            status_code=502, detail="Translation service temporarily unavailable"
        ) from exc

    except HTTPException:
        # Re-raise HTTP exceptions (rate limit, auth errors)
        raise
    except Exception as exc:
        logger.critical(
            "Unexpected translation error", exc_info=True, extra={"error": str(exc)}
        )
        translation_counter.labels(
            target_lang=request.target_lang, status="error"
        ).inc()
        raise HTTPException(status_code=500, detail="Translation failed") from exc


@app.post("/translate/stream")
async def translate_stream(
    request: TranslationRequest,
    user_id: str = Depends(verify_token),
) -> StreamingResponse:
    """
    Streaming translation endpoint (SSE).

    Args:
        request: Translation request
        user_id: Authenticated user ID

    Returns:
        Server-Sent Events stream
    """
    # Rate limiting
    await check_rate_limit(user_id)

    translation_counter.labels(
        target_lang=request.target_lang,
        status="requested",
    ).inc()

    async def event_generator() -> AsyncIterator[bytes]:
        """Generate SSE events."""
        try:
            yield b"event: translation_start\ndata: {}\n\n"

            async for chunk in translate_text_stream(request):
                yield f"data: {chunk}\n\n".encode()

            yield b"event: translation_complete\ndata: {}\n\n"

            translation_counter.labels(
                target_lang=request.target_lang,
                status="success",
            ).inc()

        except OpenAIRetryExceeded as exc:
            logger.error(
                "OpenAI retries exhausted (stream)",
                extra={"reason": exc.reason, "target_lang": request.target_lang},
            )
            status = "rate_limited" if exc.reason == "rate_limit" else "api_error"
            translation_counter.labels(
                target_lang=request.target_lang, status=status
            ).inc()
            message = (
                "Rate limit exceeded"
                if exc.reason == "rate_limit"
                else "Service temporarily unavailable"
            )
            yield f'event: error\ndata: {{"error": "{message}"}}\n\n'.encode()
        except Exception as exc:
            logger.critical(
                "Unexpected streaming error", exc_info=True, extra={"error": str(exc)}
            )
            translation_counter.labels(
                target_lang=request.target_lang, status="error"
            ).inc()
            yield b'event: error\ndata: {"error": "Translation failed"}\n\n'

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


# ============= Voice Translation =============


@app.post("/voice-translate", response_model=VoiceTranslationResponsePayload)
async def voice_translate(
    file: UploadFile = File(...),
    target_langs: str | None = Form(None),
    user_id: str = Depends(verify_token),
) -> VoiceTranslationResponsePayload:
    if not settings.voice_enabled:
        raise HTTPException(status_code=503, detail="Voice translation disabled")

    await check_rate_limit(user_id, weight=settings.voice_rate_limit_weight)
    voice_request_counter.labels(status="requested").inc()

    content_type = (file.content_type or "").lower()
    if content_type not in _ALLOWED_AUDIO_MIME_TYPES:
        voice_request_counter.labels(status="unsupported_media").inc()
        raise HTTPException(status_code=415, detail="Unsupported audio content type")

    data = await file.read()
    if not data:
        voice_request_counter.labels(status="error").inc()
        raise HTTPException(status_code=400, detail="Audio payload is empty")

    max_bytes = settings.voice_max_file_size_mb * 1024 * 1024
    if len(data) > max_bytes:
        voice_request_counter.labels(status="too_large").inc()
        raise HTTPException(status_code=413, detail="Audio payload too large")

    suffix = _resolve_audio_suffix(file)
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        temp_file.write(data)
        temp_file.flush()
        temp_file.close()

        transcription_start = time.perf_counter()
        try:
            transcription = await transcribe_audio_file(temp_file.name)
        except OpenAIRetryExceeded as exc:
            error_status = "api_error"
            if exc.reason == "rate_limit":
                voice_request_counter.labels(status="rate_limited").inc()
                raise HTTPException(
                    status_code=429, detail="Transcription rate limit exceeded"
                ) from exc

            original = getattr(exc, "original", None)
            status_code = getattr(original, "status_code", None)
            detail = getattr(original, "message", None)
            if not detail and hasattr(original, "body"):
                # OpenAI errors often embed message in body.error.message
                detail = (
                    getattr(getattr(original.body, "error", None), "message", None)
                    if hasattr(original.body, "error")
                    else None
                )
                if not detail and isinstance(original.body, dict):
                    detail = original.body.get("error", {}).get("message")

            if isinstance(status_code, int) and 400 <= status_code < 500:
                voice_request_counter.labels(status=error_status).inc()
                raise HTTPException(
                    status_code=status_code,
                    detail=detail or "Transcription request failed",
                ) from exc

            voice_request_counter.labels(status=error_status).inc()
            raise HTTPException(
                status_code=502, detail="Transcription service temporarily unavailable"
            ) from exc
        except Exception as exc:
            voice_request_counter.labels(status="error").inc()
            logger.exception("Voice transcription failed: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to transcribe audio") from exc

        transcription_latency_ms = (time.perf_counter() - transcription_start) * 1000
        voice_transcription_latency.observe(transcription_latency_ms / 1000)

        desired_targets = (
            [lang.strip().lower() for lang in target_langs.split(",") if lang.strip()]
            if target_langs
            else settings.voice_default_target_langs
        )

        validated_targets: list[Language] = []
        for lang in desired_targets:
            if lang not in {"ru", "en", "de"}:
                voice_request_counter.labels(status="error").inc()
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported target language '{lang}'",
                )
            validated_targets.append(cast(Language, lang))

        translation_start = time.perf_counter()
        try:
            translations, reported_lang, applied_source = await translate_voice_text(
                transcription.text,
                transcription.language,
                transcription.confidence,
                validated_targets,
            )
        except OpenAIRetryExceeded as exc:
            voice_request_counter.labels(status="api_error").inc()
            raise HTTPException(
                status_code=502,
                detail="Translation service temporarily unavailable",
            ) from exc
        except HTTPException:
            voice_request_counter.labels(status="error").inc()
            raise
        except Exception as exc:
            voice_request_counter.labels(status="error").inc()
            logger.exception("Voice translation failed: %s", exc)
            raise HTTPException(status_code=500, detail="Voice translation failed") from exc

        translation_latency_ms = (time.perf_counter() - translation_start) * 1000
        voice_translation_latency.observe(translation_latency_ms / 1000)

        voice_detected_counter.labels(lang=reported_lang).inc()
        voice_request_counter.labels(status="success").inc()

        metadata = VoiceTranslationMetadata(
            audio_duration_s=transcription.duration_s,
            transcription_latency_ms=transcription_latency_ms,
            translation_latency_ms=translation_latency_ms,
        )

        return VoiceTranslationResponsePayload(
            transcription=transcription.text,
            detected_lang=reported_lang if reported_lang != "unknown" else None,
            confidence=transcription.confidence,
            translations=translations,
            metadata=metadata,
        )
    finally:
        try:
            os.unlink(temp_file.name)
        except FileNotFoundError:
            pass
# ============= Realtime API (для голоса) =============


@app.post("/realtime/token")
async def get_realtime_token(user_id: str = Depends(verify_token)) -> dict[str, str]:
    """
    Get ephemeral token for OpenAI Realtime API.

    Args:
        user_id: Authenticated user ID

    Returns:
        Ephemeral token for WebRTC connection
    """
    # TODO: Implement when Realtime API is available
    # from openai import OpenAI
    # client = OpenAI(api_key=settings.openai_api_key)
    # session = client.realtime.sessions.create(
    #     model="gpt-realtime-preview",
    #     voice="alloy"
    # )
    # return {"client_secret": session.client_secret.value}

    raise HTTPException(
        status_code=501,
        detail="Realtime API not implemented yet",
    )


# ============= Monitoring =============


@app.get("/healthz")
async def health_check() -> dict[str, str]:
    """
    Health check endpoint.

    Returns:
        Service health status
    """
    redis_status = "disabled"
    redis_client = get_redis_client()
    if redis_client:
        try:
            await redis_client.ping()
            redis_status = "ok"
        except RedisError as exc:
            logger.warning("Redis health check failed: %s", exc)
            redis_status = "unhealthy"

    return {
        "status": "healthy",
        "version": "1.0.0",
        "model": settings.default_model,
        "redis": redis_status,
    }


# Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


# ============= Root =============


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint with API info."""
    return {
        "name": "Trilingual Translator - OpenAI First",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/healthz",
        "metrics": "/metrics",
    }
