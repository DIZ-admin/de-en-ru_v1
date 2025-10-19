from __future__ import annotations

import pytest
from fastapi.security import HTTPAuthorizationCredentials
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from app import auth


def generate_key_pair() -> tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    return private_pem, public_pem


def setup_rs(
    monkeypatch: pytest.MonkeyPatch,
    private: str,
    public: str,
    additional: list[str] | None = None,
    kid: str | None = "active",
) -> None:
    auth._clear_key_caches()
    monkeypatch.setattr(auth.settings, "jwt_algorithm", "RS256")
    monkeypatch.setattr(auth.settings, "jwt_private_key", private)
    monkeypatch.setattr(auth.settings, "jwt_private_key_path", None)
    monkeypatch.setattr(auth.settings, "jwt_public_key", public)
    monkeypatch.setattr(auth.settings, "jwt_public_key_path", None)
    monkeypatch.setattr(auth.settings, "jwt_additional_public_keys", additional or [])
    monkeypatch.setattr(auth.settings, "jwt_additional_public_keys_paths", [])
    monkeypatch.setattr(auth.settings, "jwt_kid", kid)


def test_rs256_token_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    private, public = generate_key_pair()
    setup_rs(monkeypatch, private, public)

    token_payload = auth.create_access_token("user-123")
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials=token_payload["access_token"]
    )

    assert auth.verify_token(credentials) == "user-123"


def test_rs256_rotation_support(monkeypatch: pytest.MonkeyPatch) -> None:
    legacy_private, legacy_public = generate_key_pair()
    new_private, new_public = generate_key_pair()

    setup_rs(monkeypatch, legacy_private, legacy_public, kid="legacy")
    legacy_token = auth.create_access_token("legacy-user")["access_token"]

    setup_rs(
        monkeypatch, new_private, new_public, additional=[legacy_public], kid="current"
    )
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials=legacy_token
    )

    assert auth.verify_token(credentials) == "legacy-user"
