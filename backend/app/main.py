"""
FastAPI application - OpenAI-First approach.
Минимальный backend, максимум делегируется OpenAI SDK.
"""

from collections.abc import AsyncIterator
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
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
    translate_text_stream,
    translate_with_cache,
)


settings = get_settings()
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


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
