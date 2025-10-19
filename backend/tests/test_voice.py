from types import SimpleNamespace
import tempfile

import pytest
from fastapi.testclient import TestClient

from app.auth import verify_token
from app.main import app, settings
from app.translate import (
    OpenAIRetryExceeded,
    TranslationResponse,
    VoiceTranscriptionResult,
    translate_voice_text,
    transcribe_audio_file,
)


@pytest.fixture(autouse=True)
def reset_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_voice_translate_success(monkeypatch):
    app.dependency_overrides[verify_token] = lambda: "user-1"

    async def fake_check_rate_limit(_: str, weight: int = 1):
        assert weight == settings.voice_rate_limit_weight
        return None

    async def fake_transcribe(_path: str):
        return SimpleNamespace(
            text="Hello world",
            language="en",
            confidence=0.92,
            duration_s=3.5,
        )

    async def fake_translate(request):
        return TranslationResponse(
            translated_text=f"{request.target_lang}-translated",
            detected_lang=request.source_lang if request.source_lang != "auto" else None,
            model="gpt-4.1-nano",
        )

    monkeypatch.setattr("app.main.check_rate_limit", fake_check_rate_limit)
    monkeypatch.setattr("app.main.transcribe_audio_file", fake_transcribe)
    monkeypatch.setattr("app.translate.transcribe_audio_file", fake_transcribe)
    monkeypatch.setattr("app.main.translate_with_cache", fake_translate)
    monkeypatch.setattr("app.translate.translate_with_cache", fake_translate)

    client = TestClient(app)
    files = {"file": ("sample.webm", b"123", "audio/webm")}

    response = client.post(
        "/voice-translate",
        files=files,
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["transcription"] == "Hello world"
    assert payload["detected_lang"] == "en"
    assert payload["translations"]["ru"] == "ru-translated"
    assert payload["metadata"]["transcription_latency_ms"] >= 0


def test_voice_translate_invalid_media(monkeypatch):
    app.dependency_overrides[verify_token] = lambda: "user-1"
    async def noop_check_rate_limit(*_args, **_kwargs):  # noqa: ARG001
        return None

    monkeypatch.setattr("app.main.check_rate_limit", noop_check_rate_limit)
    client = TestClient(app)

    files = {"file": ("sample.txt", b"", "text/plain")}
    response = client.post(
        "/voice-translate",
        files=files,
        headers={"Authorization": "Bearer token"},
    )
    assert response.status_code == 415


def test_voice_translate_accepts_m4a(monkeypatch):
    app.dependency_overrides[verify_token] = lambda: "user-1"

    async def fake_check_rate_limit(*_args, **_kwargs):
        return None

    async def fake_transcribe(path: str):
        assert path.endswith(".m4a")
        return SimpleNamespace(
            text="Hi",
            language="en",
            confidence=0.9,
            duration_s=1.0,
        )

    async def fake_translate(request):
        return TranslationResponse(
            translated_text=f"{request.target_lang}-translated",
            detected_lang=request.source_lang if request.source_lang != "auto" else None,
            model="gpt-4.1-nano",
        )

    suffixes: list[str | None] = []
    real_named_tempfile = tempfile.NamedTemporaryFile

    def fake_named_tempfile(*args, **kwargs):
        suffixes.append(kwargs.get("suffix"))
        return real_named_tempfile(*args, **kwargs)

    monkeypatch.setattr("app.main.check_rate_limit", fake_check_rate_limit)
    monkeypatch.setattr("app.main.transcribe_audio_file", fake_transcribe)
    monkeypatch.setattr("app.translate.transcribe_audio_file", fake_transcribe)
    monkeypatch.setattr("app.main.translate_with_cache", fake_translate)
    monkeypatch.setattr("app.translate.translate_with_cache", fake_translate)
    monkeypatch.setattr("app.main.tempfile.NamedTemporaryFile", fake_named_tempfile)

    client = TestClient(app)
    files = {"file": ("sample.m4a", b"123", "audio/mp4a-latm")}

    response = client.post(
        "/voice-translate",
        files=files,
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    assert suffixes and suffixes[-1] == ".m4a"


def test_voice_translate_transcription_rate_limit(monkeypatch):
    app.dependency_overrides[verify_token] = lambda: "user-1"

    async def fake_check_rate_limit(*_args, **_kwargs):
        return None

    class DummyRateLimitError(Exception):
        status_code = 429
        message = "Too many requests"

    async def fake_transcribe(_path: str):
        raise OpenAIRetryExceeded("rate_limit", DummyRateLimitError())

    monkeypatch.setattr("app.main.check_rate_limit", fake_check_rate_limit)
    monkeypatch.setattr("app.main.transcribe_audio_file", fake_transcribe)
    monkeypatch.setattr("app.translate.transcribe_audio_file", fake_transcribe)

    client = TestClient(app)
    files = {"file": ("sample.webm", b"123", "audio/webm")}

    response = client.post(
        "/voice-translate",
        files=files,
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 429
    assert response.json()["detail"] == "Transcription rate limit exceeded"


def test_voice_translate_transcription_client_error(monkeypatch):
    app.dependency_overrides[verify_token] = lambda: "user-1"

    async def fake_check_rate_limit(*_args, **_kwargs):
        return None

    class DummyClientError(Exception):
        status_code = 400
        message = "Audio format malformed"

    async def fake_transcribe(_path: str):
        raise OpenAIRetryExceeded("api_error", DummyClientError())

    monkeypatch.setattr("app.main.check_rate_limit", fake_check_rate_limit)
    monkeypatch.setattr("app.main.transcribe_audio_file", fake_transcribe)
    monkeypatch.setattr("app.translate.transcribe_audio_file", fake_transcribe)

    client = TestClient(app)
    files = {"file": ("sample.webm", b"123", "audio/webm")}

    response = client.post(
        "/voice-translate",
        files=files,
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Audio format malformed"


@pytest.mark.asyncio
async def test_translate_voice_low_confidence(monkeypatch):
    async def fake_translate(request):
        assert request.source_lang == "auto"
        return TranslationResponse(
            translated_text="auto-translated",
            detected_lang=None,
            model="gpt-4.1-nano",
        )

    monkeypatch.setattr("app.translate.translate_with_cache", fake_translate)

    translations, reported_lang, applied_source = await translate_voice_text(
        "Hello",
        "en",
        0.1,
        ["de"],
    )
    assert translations["de"] == "auto-translated"
    assert reported_lang == "en"
    assert applied_source == "auto"


@pytest.mark.asyncio
async def test_transcribe_audio_file_fallback(monkeypatch, tmp_path):
    primary_model = "gpt-4o-mini-transcribe"
    fallback_model = "whisper-1"

    monkeypatch.setattr("app.translate.settings.voice_transcription_model", primary_model)
    monkeypatch.setattr(
        "app.translate.settings.voice_transcription_fallback_model", fallback_model
    )

    class DummyApiError(Exception):
        status_code = 404
        message = "Model not found"

    calls: list[str] = []

    async def fake_call_with_retry(func, *, operation, context=None):
        model = context.get("model") if context else None
        calls.append(model)
        if len(calls) == 1:
            raise OpenAIRetryExceeded("api_error", DummyApiError())
        return {
            "text": "Hello world",
            "language": "en",
            "language_probability": 0.9,
            "duration": 1.23,
        }

    monkeypatch.setattr("app.translate._call_with_retry", fake_call_with_retry)

    audio_path = tmp_path / "sample.webm"
    audio_path.write_bytes(b"voice-bytes")

    result: VoiceTranscriptionResult = await transcribe_audio_file(str(audio_path))

    assert result.text == "Hello world"
    assert result.language == "en"
    assert calls == [primary_model, fallback_model]
