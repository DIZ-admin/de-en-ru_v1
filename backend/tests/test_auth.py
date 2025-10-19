from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from redis.exceptions import RedisError

from app import auth


@pytest.fixture(autouse=True)
def reset_rate_limits(monkeypatch: pytest.MonkeyPatch):
    auth._rate_limits.clear()
    monkeypatch.setattr(auth.settings, "rate_limit_max_calls", 2)
    monkeypatch.setattr(auth.settings, "rate_limit_window_seconds", 60)
    yield


@pytest.fixture()
def rsa_keys() -> tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


@pytest.fixture()
def clear_jwt_caches():
    auth._clear_key_caches()
    yield
    auth._clear_key_caches()


@pytest.mark.asyncio
async def test_check_rate_limit_in_memory(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(auth, "get_redis_client", lambda: None)

    await auth.check_rate_limit("user-1")
    await auth.check_rate_limit("user-1")

    with pytest.raises(HTTPException) as exc:
        await auth.check_rate_limit("user-1")

    assert exc.value.status_code == 429


class _FakeRedisLimiter:
    def __init__(self):
        self.store: dict[str, list[float]] = {}

    async def zremrangebyscore(self, key: str, min_score: str, max_score: float):
        values = self.store.get(key, [])
        self.store[key] = [score for score in values if score > float(max_score)]

    async def zcard(self, key: str) -> int:
        return len(self.store.get(key, []))

    async def zadd(self, key: str, mapping: dict[float, float]):
        values = self.store.setdefault(key, [])
        values.extend(mapping.values())

    async def expire(self, key: str, ttl: int):
        # TTL не моделируем в тестах
        return True


@pytest.mark.asyncio
async def test_check_rate_limit_with_redis(monkeypatch: pytest.MonkeyPatch):
    limiter = _FakeRedisLimiter()
    monkeypatch.setattr(auth, "get_redis_client", lambda: limiter)

    await auth.check_rate_limit("user-redis")
    await auth.check_rate_limit("user-redis")

    with pytest.raises(HTTPException):
        await auth.check_rate_limit("user-redis")


class _FailingRedis:
    async def zremrangebyscore(self, *_args, **_kwargs):
        raise RedisError("boom")

    async def zcard(self, *_args, **_kwargs):
        return 0

    async def zadd(self, *_args, **_kwargs):
        return 1

    async def expire(self, *_args, **_kwargs):
        return True


@pytest.mark.asyncio
async def test_check_rate_limit_fallbacks_when_redis_errors(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(auth, "get_redis_client", lambda: _FailingRedis())

    await auth.check_rate_limit("user-fallback")
    await auth.check_rate_limit("user-fallback")

    with pytest.raises(HTTPException):
        await auth.check_rate_limit("user-fallback")


def test_create_access_token_hs256(
    monkeypatch: pytest.MonkeyPatch, clear_jwt_caches: None
):
    monkeypatch.setattr(auth.settings, "jwt_algorithm", "HS256")
    monkeypatch.setattr(auth.settings, "jwt_secret_key", "top-secret")

    token_info = auth.create_access_token("user-hs")
    token = token_info["access_token"]

    payload = jwt.decode(token, "top-secret", algorithms=["HS256"])
    assert payload["sub"] == "user-hs"


def test_create_access_token_rs256_requires_private_key(
    monkeypatch: pytest.MonkeyPatch, clear_jwt_caches: None
):
    monkeypatch.setattr(auth.settings, "jwt_algorithm", "RS256")
    monkeypatch.setattr(auth.settings, "jwt_private_key", None)
    monkeypatch.setattr(auth.settings, "jwt_private_key_path", None)

    with pytest.raises(RuntimeError):
        auth.create_access_token("user-rs")


def test_create_access_token_rs256_with_inline_key(
    monkeypatch: pytest.MonkeyPatch,
    rsa_keys: tuple[str, str],
    clear_jwt_caches: None,
):
    private_key, public_key = rsa_keys
    monkeypatch.setattr(auth.settings, "jwt_algorithm", "RS256")
    monkeypatch.setattr(auth.settings, "jwt_private_key", private_key)
    monkeypatch.setattr(auth.settings, "jwt_public_key", public_key)
    monkeypatch.setattr(auth.settings, "jwt_kid", "kid-1")

    token_info = auth.create_access_token("user-rs")
    token = token_info["access_token"]

    header = jwt.get_unverified_header(token)
    assert header["kid"] == "kid-1"

    payload = jwt.decode(token, public_key, algorithms=["RS256"])
    assert payload["sub"] == "user-rs"


def test_verify_token_hs256_invalid_signature(
    monkeypatch: pytest.MonkeyPatch, clear_jwt_caches: None
):
    monkeypatch.setattr(auth.settings, "jwt_algorithm", "HS256")
    monkeypatch.setattr(auth.settings, "jwt_secret_key", "actual-secret")

    forged_payload = {
        "sub": "user",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    forged_token = jwt.encode(forged_payload, "wrong", algorithm="HS256")

    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=forged_token)
    with pytest.raises(HTTPException):
        auth.verify_token(credentials)


def test_verify_token_rs256_with_additional_keys(
    monkeypatch: pytest.MonkeyPatch,
    rsa_keys: tuple[str, str],
    clear_jwt_caches: None,
):
    private_key, public_key = rsa_keys
    monkeypatch.setattr(auth.settings, "jwt_algorithm", "RS256")
    monkeypatch.setattr(auth.settings, "jwt_public_key", None)
    monkeypatch.setattr(auth.settings, "jwt_private_key", None)
    monkeypatch.setattr(auth.settings, "jwt_additional_public_keys", [public_key])
    monkeypatch.setattr(auth.settings, "jwt_additional_public_keys_paths", [])
    monkeypatch.setattr(auth.settings, "jwt_kid", "rotated")

    token = jwt.encode(
        {"sub": "rot-user", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        private_key,
        algorithm="RS256",
        headers={"kid": "rotated"},
    )

    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    assert auth.verify_token(credentials) == "rot-user"


def test_verify_token_rs256_without_keys(
    monkeypatch: pytest.MonkeyPatch,
    rsa_keys: tuple[str, str],
    clear_jwt_caches: None,
):
    private_key, _ = rsa_keys
    monkeypatch.setattr(auth.settings, "jwt_algorithm", "RS256")
    monkeypatch.setattr(auth.settings, "jwt_public_key", None)
    monkeypatch.setattr(auth.settings, "jwt_private_key", None)
    monkeypatch.setattr(auth.settings, "jwt_additional_public_keys", [])
    monkeypatch.setattr(auth.settings, "jwt_additional_public_keys_paths", [])

    token = jwt.encode(
        {"sub": "user", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        private_key,
        algorithm="RS256",
    )

    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException):
        auth.verify_token(credentials)


def test_verify_token_fails_when_sub_missing(
    monkeypatch: pytest.MonkeyPatch, clear_jwt_caches: None
):
    monkeypatch.setattr(auth.settings, "jwt_algorithm", "HS256")
    monkeypatch.setattr(auth.settings, "jwt_secret_key", "secret")

    token = jwt.encode(
        {"exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        "secret",
        algorithm="HS256",
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException):
        auth.verify_token(credentials)


def test_verify_token_expired(
    monkeypatch: pytest.MonkeyPatch, clear_jwt_caches: None
):
    monkeypatch.setattr(auth.settings, "jwt_algorithm", "HS256")
    monkeypatch.setattr(auth.settings, "jwt_secret_key", "secret")

    token = jwt.encode(
        {"sub": "user", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        "secret",
        algorithm="HS256",
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as exc:
        auth.verify_token(credentials)
    assert exc.value.detail == "Token expired"


def test_verify_token_invalid_structure(
    monkeypatch: pytest.MonkeyPatch, clear_jwt_caches: None
):
    monkeypatch.setattr(auth.settings, "jwt_algorithm", "HS256")
    monkeypatch.setattr(auth.settings, "jwt_secret_key", "secret")

    base_token = jwt.encode(
        {"sub": "user", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        "secret",
        algorithm="HS256",
    )
    header, payload, _signature = base_token.split(".")
    tampered = ".".join([header, payload, "invalidsig"])
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=tampered)
    with pytest.raises(HTTPException):
        auth.verify_token(credentials)


def test_load_data_from_path_handles_none():
    assert auth._load_data_from_path(None) is None


def test_load_data_from_path_missing(tmp_path: Path):
    missing = tmp_path / "missing.pem"
    with pytest.raises(FileNotFoundError):
        auth._load_data_from_path(str(missing))


def test_load_combined_key_prefers_inline(tmp_path: Path):
    file_key = tmp_path / "key.pem"
    file_key.write_text("FILE", encoding="utf-8")
    result = auth._load_combined_key(str(file_key), "INLINE")
    assert result == "INLINE"


def test_additional_keys_loaded_from_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, clear_jwt_caches: None
):
    key_file = tmp_path / "extra.pem"
    key_file.write_text(
        "-----BEGIN KEY-----\nEXTRA\n-----END KEY-----\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        auth.settings,
        "jwt_additional_public_keys_paths",
        [str(key_file)],
    )
    monkeypatch.setattr(auth.settings, "jwt_additional_public_keys", [])

    keys = auth._get_additional_public_keys()
    assert len(keys) == 1
