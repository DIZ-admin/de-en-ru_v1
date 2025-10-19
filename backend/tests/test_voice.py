from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.auth import verify_token
from app.main import app
from app.translate import TranslationResponse, translate_voice_text


@pytest.fixture(autouse=True)
def reset_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_voice_translate_success(monkeypatch):
    app.dependency_overrides[verify_token] = lambda: "user-1"

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

    monkeypatch.setattr("app.translate.transcribe_audio_file", fake_transcribe)
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
    client = TestClient(app)

    files = {"file": ("sample.txt", b"", "text/plain")}
    response = client.post(
        "/voice-translate",
        files=files,
        headers={"Authorization": "Bearer token"},
    )
    assert response.status_code == 415


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
