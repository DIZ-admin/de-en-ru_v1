from __future__ import annotations

from fastapi.testclient import TestClient
from fastapi import HTTPException
import pytest

from app.main import app, verify_token, settings
from app.translate import (
    TranslationResponse,
    TranslationRequest,
    OpenAIRetryExceeded,
)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    async def fake_check_rate_limit(_: str) -> None:
        return None

    async def fake_translate_with_cache(
        request: TranslationRequest,
    ) -> TranslationResponse:
        return TranslationResponse(
            translated_text=f"Translated {request.text}",
            detected_lang="en",
            model="gpt-4.1-nano",
        )

    async def fake_stream(_: TranslationRequest):
        yield "Hello"
        yield " World"

    app.dependency_overrides[verify_token] = lambda: "user"
    monkeypatch.setattr("app.main.check_rate_limit", fake_check_rate_limit)
    monkeypatch.setattr("app.main.translate_with_cache", fake_translate_with_cache)
    monkeypatch.setattr("app.main.translate_text_stream", fake_stream)

    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def auth_header() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}


def test_get_token(client: TestClient):
    response = client.post("/auth/token")
    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert "access_token" in data


def test_translate_success(client: TestClient):
    payload = {"text": "Hallo", "source_lang": "de", "target_lang": "en"}
    response = client.post("/translate", json=payload, headers=auth_header())
    assert response.status_code == 200
    assert response.json()["translated_text"].startswith("Translated")


def test_translate_rate_limited(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    async def raise_limit(_: str) -> None:
        raise HTTPException(status_code=429, detail="Too many requests")

    monkeypatch.setattr("app.main.check_rate_limit", raise_limit)
    payload = {"text": "Hallo", "source_lang": "de", "target_lang": "en"}
    response = client.post("/translate", json=payload, headers=auth_header())
    assert response.status_code == 429


def test_translate_stream_endpoint(client: TestClient):
    payload = {"text": "Hallo", "source_lang": "de", "target_lang": "en"}
    response = client.post("/translate/stream", json=payload, headers=auth_header())
    assert response.status_code == 200
    body = b"".join(response.iter_bytes())
    assert b"data: Hello" in body
    assert b"translation_complete" in body


def test_translate_handles_external_errors(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    class DummyAPIError(Exception): ...

    async def raise_api(_: TranslationRequest) -> TranslationResponse:
        raise OpenAIRetryExceeded("api_error", DummyAPIError("api down"))

    monkeypatch.setattr("app.main.translate_with_cache", raise_api)
    payload = {"text": "Hallo", "source_lang": "de", "target_lang": "en"}
    response = client.post("/translate", json=payload, headers=auth_header())
    assert response.status_code == 502


def test_translate_handles_unexpected_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    async def raise_generic(_: TranslationRequest) -> TranslationResponse:
        raise RuntimeError("boom")

    monkeypatch.setattr("app.main.translate_with_cache", raise_generic)
    payload = {"text": "Hallo", "source_lang": "de", "target_lang": "en"}
    response = client.post("/translate", json=payload, headers=auth_header())
    assert response.status_code == 500


def test_healthz_with_redis(monkeypatch: pytest.MonkeyPatch):
    class FakeRedis:
        async def ping(self) -> None:  # pragma: no cover - trivial
            return None

    monkeypatch.setattr("app.main.get_redis_client", lambda: FakeRedis())
    with TestClient(app) as client:
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json()["redis"] == "ok"


def test_translate_handles_rate_limit_retry_failure(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    class DummyRateLimit(Exception): ...

    async def raise_limit(_: TranslationRequest) -> TranslationResponse:
        raise OpenAIRetryExceeded("rate_limit", DummyRateLimit("slow"))

    monkeypatch.setattr("app.main.translate_with_cache", raise_limit)

    payload = {"text": "Hallo", "source_lang": "de", "target_lang": "en"}
    response = client.post("/translate", json=payload, headers=auth_header())
    assert response.status_code == 429


def test_security_headers_applied(monkeypatch: pytest.MonkeyPatch):
    original_env = settings.app_env
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "security_hsts_enabled", True)
    with TestClient(app) as client:
        response = client.get("/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == settings.security_frame_options
    assert "Strict-Transport-Security" in response.headers
    monkeypatch.setattr(settings, "app_env", original_env)
