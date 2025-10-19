from __future__ import annotations

from types import SimpleNamespace
import pytest

from app import redis_utils


@pytest.fixture(autouse=True)
def clear_cache():
    redis_utils._create_redis_client.cache_clear()
    yield
    redis_utils._create_redis_client.cache_clear()


def test_get_redis_client_disabled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        redis_utils, "get_settings", lambda: SimpleNamespace(redis_enabled=False)
    )
    assert redis_utils.get_redis_client() is None


def test_get_redis_client_enabled(monkeypatch: pytest.MonkeyPatch):
    fake_client = object()

    class FakeRedisModule:
        @staticmethod
        def from_url(url: str, **_: object):
            assert url.startswith("redis://")
            return fake_client

    settings = SimpleNamespace(
        redis_enabled=True,
        redis_url=None,
        redis_host="localhost",
        redis_port=6379,
        redis_db=0,
        redis_username=None,
        redis_password=None,
    )

    monkeypatch.setattr(redis_utils, "get_settings", lambda: settings)
    monkeypatch.setattr(redis_utils, "Redis", FakeRedisModule)

    client = redis_utils.get_redis_client()
    assert client is fake_client
