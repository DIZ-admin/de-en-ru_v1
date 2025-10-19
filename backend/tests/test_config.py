from __future__ import annotations

from pathlib import Path

import pytest

from app import config


def test_allowed_origins_split_string():
    settings = config.Settings(
        openai_api_key="sk-test",
        allowed_origins="http://a.com, http://b.com ",
    )
    assert settings.allowed_origins == ["http://a.com", "http://b.com"]


def test_allowed_origins_invalid_type_raises():
    with pytest.raises(TypeError):
        config.Settings(openai_api_key="sk-test", allowed_origins=123)  # type: ignore[arg-type]


def test_openai_key_cannot_be_blank():
    with pytest.raises(ValueError):
        config.Settings(openai_api_key="   ")


def test_additional_public_keys_from_path_and_inline(tmp_path: Path):
    key_path = tmp_path / "key.pem"
    key_path.write_text("-----BEGIN KEY-----\nA\n-----END KEY-----\n", encoding="utf-8")

    settings = config.Settings(
        openai_api_key="sk-test",
        jwt_additional_public_keys_paths=[str(key_path)],
        jwt_additional_public_keys=["-----BEGIN KEY-----\nB\n-----END KEY-----"],
    )

    assert len(settings.jwt_additional_public_keys_paths) == 1
    assert len(settings.jwt_additional_public_keys) == 1
