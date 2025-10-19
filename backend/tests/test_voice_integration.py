from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.auth import verify_token
from app.main import app, settings


@pytest.fixture(autouse=True)
def reset_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.mark.parametrize(
    "filename, content_type, expected_suffixes",
    [
        ("sample.webm", "audio/webm", (".weba", ".webm")),
        ("sample.m4a", "audio/mp4a-latm", (".m4a",)),
        ("sample.flac", "audio/flac", (".flac",)),
    ],
)
def test_voice_translate_supported_formats(monkeypatch, client, filename, content_type, expected_suffixes):
    app.dependency_overrides[verify_token] = lambda: "user-1"

    async def fake_check_rate_limit(*_args, **_kwargs):
        return None

    async def fake_transcribe(path: str):
        assert any(path.endswith(suffix) for suffix in expected_suffixes)
        return SimpleNamespace(
            text="Hello world",
            language="en",
            confidence=0.9,
            duration_s=1.23,
        )

    async def fake_translate(transcription, detected_lang, confidence, target_langs):
        return {lang: f"{transcription}-{lang}" for lang in target_langs}, detected_lang or "en", detected_lang or "auto"

    monkeypatch.setattr("app.main.check_rate_limit", fake_check_rate_limit)
    monkeypatch.setattr("app.main.transcribe_audio_file", fake_transcribe)
    monkeypatch.setattr("app.translate.transcribe_audio_file", fake_transcribe)
    monkeypatch.setattr("app.main.translate_voice_text", fake_translate)
    monkeypatch.setattr("app.translate.translate_voice_text", fake_translate)

    files = {"file": (filename, b"binary-audio", content_type)}

    response = client.post(
        "/voice-translate",
        files=files,
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["transcription"] == "Hello world"
    assert payload["metadata"]["transcription_latency_ms"] >= 0
    assert payload["metadata"]["translation_latency_ms"] >= 0
    assert payload["translations"]["de"] == "Hello world-de"


def test_voice_translate_rejects_unsupported_type(monkeypatch, client):
    app.dependency_overrides[verify_token] = lambda: "user-1"

    async def fake_check_rate_limit(*_args, **_kwargs):
        return None

    monkeypatch.setattr("app.main.check_rate_limit", fake_check_rate_limit)

    files = {"file": ("note.txt", b"text", "text/plain")}

    response = client.post(
        "/voice-translate",
        files=files,
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 415


def test_voice_translate_rejects_large_file(monkeypatch, client):
    app.dependency_overrides[verify_token] = lambda: "user-1"

    async def fake_check_rate_limit(*_args, **_kwargs):
        return None

    async def fake_transcribe(path: str):  # pragma: no cover
        return SimpleNamespace(
            text="should-not-happen",
            language="en",
            confidence=0.9,
            duration_s=1.0,
        )

    monkeypatch.setattr("app.main.check_rate_limit", fake_check_rate_limit)
    monkeypatch.setattr("app.main.transcribe_audio_file", fake_transcribe)
    monkeypatch.setattr("app.translate.transcribe_audio_file", fake_transcribe)

    too_big = b"x" * (settings.voice_max_file_size_mb * 1024 * 1024 + 1)
    files = {"file": ("huge.webm", too_big, "audio/webm")}

    response = client.post(
        "/voice-translate",
        files=files,
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 413
