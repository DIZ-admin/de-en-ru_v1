from __future__ import annotations

from types import SimpleNamespace
from typing import Any, List
from unittest.mock import AsyncMock

import pytest
import openai
from redis.exceptions import RedisError

from app import translate
from app.translate import OpenAIRetryExceeded


@pytest.fixture(autouse=True)
def reset_cache(monkeypatch: pytest.MonkeyPatch):
    """Reset in-memory cache between tests."""
    monkeypatch.setattr(translate, "_translation_cache", {})
    monkeypatch.setattr(translate.settings, "redis_enabled", False)
    yield
    translate.client.responses.create = translate.client.responses.create  # type: ignore[attr-defined]


class _FakeStreamIterator:
    def __init__(self, events: List[Any]):
        self._events = events

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._events:
            raise StopAsyncIteration
        return self._events.pop(0)


class _FakeStreamContext:
    def __init__(self, events: List[Any]):
        self._events = events

    async def __aenter__(self):
        return _FakeStreamIterator(self._events)

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_translate_text_uses_async_responses(monkeypatch: pytest.MonkeyPatch):
    async def mock_create(*_: Any, **__: Any):
        return SimpleNamespace(output_text="Hallo Welt")

    monkeypatch.setattr(translate.client.responses, "create", mock_create)

    request = translate.TranslationRequest(text="Hello world", target_lang="de")
    response = await translate.translate_text(request)

    assert response.translated_text == "Hallo Welt"
    assert response.model == translate.settings.default_model


@pytest.mark.asyncio
async def test_translate_retries_on_rate_limit(monkeypatch: pytest.MonkeyPatch):
    call_counter = {"count": 0}

    from httpx import Request, Response

    async def flaky_create(*_: Any, **__: Any):
        call_counter["count"] += 1
        if call_counter["count"] == 1:
            dummy_request = Request("POST", "https://api.openai.com/v1/responses")
            dummy_response = Response(429, request=dummy_request)
            raise openai.RateLimitError("slow", response=dummy_response, body=None)
        return SimpleNamespace(output_text="Hallo Welt")

    monkeypatch.setattr(translate.client.responses, "create", flaky_create)

    request = translate.TranslationRequest(text="Hello", target_lang="de")
    response = await translate.translate_text(request)

    assert response.translated_text == "Hallo Welt"
    assert call_counter["count"] == 2


@pytest.mark.asyncio
async def test_translate_raises_on_nonretryable_api_error(
    monkeypatch: pytest.MonkeyPatch,
):
    from httpx import Request

    async def failing_create(*_: Any, **__: Any):
        error = openai.APIError(
            "bad request", request=Request("POST", "https://api.openai.com"), body=None
        )
        error.status_code = 400
        raise error

    monkeypatch.setattr(translate.client.responses, "create", failing_create)

    request = translate.TranslationRequest(text="Hello", target_lang="de")
    with pytest.raises(OpenAIRetryExceeded) as exc:
        await translate.translate_text(request)

    assert exc.value.reason == "api_error"


@pytest.mark.asyncio
async def test_stream_retries_on_rate_limit(monkeypatch: pytest.MonkeyPatch):
    from httpx import Request, Response

    attempts = {"count": 0}

    class FlakyStream:
        async def __aenter__(self):
            attempts["count"] += 1
            if attempts["count"] == 1:
                dummy_request = Request("POST", "https://api.openai.com/v1/responses")
                dummy_response = Response(429, request=dummy_request)
                raise openai.RateLimitError("slow", response=dummy_response, body=None)
            events = [
                SimpleNamespace(type="response.output_text.delta", delta="Hallo"),
                SimpleNamespace(type="response.output_text.delta", delta=" Welt"),
            ]
            return _FakeStreamIterator(events)

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(translate.client.responses, "stream", lambda **_: FlakyStream())

    request = translate.TranslationRequest(text="Hello", target_lang="de")
    chunks = [chunk async for chunk in translate.translate_text_stream(request)]
    assert chunks == ["Hallo", " Welt"]
    assert attempts["count"] == 2


@pytest.mark.asyncio
async def test_stream_raises_on_nonretryable_api_error(monkeypatch: pytest.MonkeyPatch):
    from httpx import Request

    class ErrorStream:
        async def __aenter__(self):
            error = openai.APIError(
                "bad request",
                request=Request("POST", "https://api.openai.com/v1/responses"),
                body=None,
            )
            error.status_code = 400
            raise error

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(translate.client.responses, "stream", lambda **_: ErrorStream())

    request = translate.TranslationRequest(text="oops", target_lang="en")
    with pytest.raises(OpenAIRetryExceeded) as exc:
        async for _ in translate.translate_text_stream(request):
            pass
    assert exc.value.reason == "api_error"


@pytest.mark.asyncio
async def test_translate_with_cache_in_memory(monkeypatch: pytest.MonkeyPatch):
    call_counter = {"count": 0}

    async def fake_translate(
        _: translate.TranslationRequest,
    ) -> translate.TranslationResponse:
        call_counter["count"] += 1
        return translate.TranslationResponse(
            translated_text="Cached value",
            detected_lang="en",
            model=translate.settings.default_model,
        )

    monkeypatch.setattr(translate, "translate_text", fake_translate)
    monkeypatch.setattr(translate.settings, "redis_enabled", False)

    request = translate.TranslationRequest(text="Hello", target_lang="de")
    first = await translate.translate_with_cache(request)
    second = await translate.translate_with_cache(request)

    assert first.translated_text == "Cached value"
    assert second.translated_text == "Cached value"
    assert (
        call_counter["count"] == 1
    ), "translate_text should be called once due to cache"


class _FakeRedisCache:
    def __init__(self):
        self.storage: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.storage.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        self.storage[key] = value


@pytest.mark.asyncio
async def test_translate_with_cache_redis(monkeypatch: pytest.MonkeyPatch):
    fake_redis = _FakeRedisCache()
    cache_key = translate.get_cache_key("Hello", "de")
    fake_redis.storage[cache_key] = "Aus dem Cache"

    monkeypatch.setattr(translate, "get_redis_client", lambda: fake_redis)
    monkeypatch.setattr(translate.settings, "redis_enabled", True)
    monkeypatch.setattr(
        translate.client.responses,
        "create",
        AsyncMock(side_effect=AssertionError("Should not call OpenAI when cache hit")),
    )

    request = translate.TranslationRequest(text="Hello", target_lang="de")
    response = await translate.translate_with_cache(request)

    assert response.translated_text == "Aus dem Cache"


class _RedisGetError:
    async def get(self, _key: str) -> str | None:
        raise RedisError("unavailable")

    async def set(self, *_args, **_kwargs):
        return True


class _RedisSetError:
    def __init__(self):
        self.storage: dict[str, str] = {}

    async def get(self, _key: str) -> str | None:
        return None

    async def set(self, *_args, **_kwargs):
        raise RedisError("write failed")


@pytest.mark.asyncio
async def test_translate_with_cache_handles_redis_get_error(monkeypatch: pytest.MonkeyPatch):
    async def fake_translate(_: translate.TranslationRequest) -> translate.TranslationResponse:
        return translate.TranslationResponse(
            translated_text="fallback",
            detected_lang=None,
            model=translate.settings.default_model,
        )

    monkeypatch.setattr(translate, "get_redis_client", lambda: _RedisGetError())
    monkeypatch.setattr(translate, "translate_text", fake_translate)
    monkeypatch.setattr(translate.settings, "redis_enabled", True)

    request = translate.TranslationRequest(text="Hello", target_lang="de")
    response = await translate.translate_with_cache(request)
    assert response.translated_text == "fallback"


@pytest.mark.asyncio
async def test_translate_with_cache_handles_redis_set_error(monkeypatch: pytest.MonkeyPatch):
    async def fake_translate(_: translate.TranslationRequest) -> translate.TranslationResponse:
        return translate.TranslationResponse(
            translated_text="stored",
            detected_lang=None,
            model=translate.settings.default_model,
        )

    redis_client = _RedisSetError()
    monkeypatch.setattr(translate, "get_redis_client", lambda: redis_client)
    monkeypatch.setattr(translate, "translate_text", fake_translate)
    monkeypatch.setattr(translate.settings, "redis_enabled", True)

    request = translate.TranslationRequest(text="Hello", target_lang="de")
    response = await translate.translate_with_cache(request)
    assert response.translated_text == "stored"


@pytest.mark.asyncio
async def test_translate_stream_emits_deltas(monkeypatch: pytest.MonkeyPatch):
    events = [
        SimpleNamespace(type="response.output_text.delta", delta="Hallo"),
        SimpleNamespace(type="response.output_text.delta", delta=" Welt"),
        SimpleNamespace(type="response.completed"),
    ]

    monkeypatch.setattr(
        translate.client.responses,
        "stream",
        lambda **_: _FakeStreamContext(events[:]),
    )

    request = translate.TranslationRequest(text="Hello", target_lang="de")
    chunks = [chunk async for chunk in translate.translate_text_stream(request)]

    assert chunks == ["Hallo", " Welt"]
