"""
Configuration settings for the application.
OpenAI-First approach - minimal configuration.
"""

from collections.abc import Iterable
from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)
    """Application settings loaded from environment variables."""

    # OpenAI Configuration
    openai_api_key: str = Field(default="")

    # JWT Authentication
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_private_key_path: str | None = None
    jwt_private_key: str | None = None
    jwt_public_key_path: str | None = None
    jwt_public_key: str | None = None
    jwt_additional_public_keys_paths: list[str] = []
    jwt_additional_public_keys: list[str] = []
    jwt_kid: str | None = None
    jwt_access_token_expire_minutes: int = 30

    # Application
    app_env: str = "development"
    log_level: str = "INFO"

    # Rate Limiting (simple in-memory for MVP)
    rate_limit_max_calls: int = 120
    rate_limit_window_seconds: int = 60

    # Translation Settings
    default_model: str = "gpt-4.1-nano"  # Компактная и быстрая модель перевода
    max_text_length: int = 4000
    translation_cache_ttl: int = 600  # 10 минут

    # Voice translation settings
    voice_enabled: bool = True
    voice_allowed_mime_types: list[str] = [
        "audio/webm",
        "audio/ogg",
        "audio/mpeg",
        "audio/wav",
    ]
    voice_max_duration_seconds: int = 60
    voice_max_file_size_mb: int = 5
    voice_transcription_model: str = "gpt-4o-mini-transcribe"
    voice_detection_confidence_threshold: float = 0.7
    voice_default_target_langs: list[str] = ["ru", "en", "de"]
    voice_rate_limit_weight: int = 3
    voice_transcribe_timeout_seconds: int = 20

    # OpenAI retry strategy
    openai_retry_max_attempts: int = 3
    openai_retry_initial_delay: float = 0.5

    # Redis (production cache / rate limiting)
    redis_enabled: bool = False
    redis_url: str | None = None
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_username: str | None = None
    redis_password: str | None = None

    # CORS
    allowed_origins: list[str] = ["http://localhost:3000"]

    # Security headers
    security_hsts_enabled: bool = True
    security_hsts_max_age: int = 31536000
    security_csp: str = "default-src 'self'; frame-ancestors 'none'; object-src 'none';"
    security_frame_options: str = "DENY"
    security_referrer_policy: str = "no-referrer"
    security_permissions_policy: str = "geolocation=(), microphone=(), camera=()"

    @field_validator("openai_api_key")
    @classmethod
    def _validate_openai_key(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("OPENAI_API_KEY must be set.")
        return value

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _split_allowed_origins(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
            return [str(item).strip() for item in value if str(item).strip()]
        raise TypeError("allowed_origins must be a string or iterable of strings")

    @field_validator("jwt_additional_public_keys_paths", mode="before")
    @classmethod
    def _split_key_paths(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
            return [str(item).strip() for item in value if str(item).strip()]
        raise TypeError(
            "jwt_additional_public_keys_paths must be a string or iterable of strings"
        )

    @field_validator("jwt_additional_public_keys", mode="before")
    @classmethod
    def _split_keys(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split("||") if item.strip()]
        if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
            return [str(item).strip() for item in value if str(item).strip()]
        raise TypeError(
            "jwt_additional_public_keys must be a string or iterable of strings"
        )

    @field_validator("voice_allowed_mime_types", mode="before")
    @classmethod
    def _split_voice_mimes(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
            return [str(item).strip() for item in value if str(item).strip()]
        raise TypeError(
            "voice_allowed_mime_types must be a string or iterable of strings"
        )

    @field_validator("voice_default_target_langs", mode="before")
    @classmethod
    def _split_voice_targets(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
            return [str(item).strip() for item in value if str(item).strip()]
        raise TypeError(
            "voice_default_target_langs must be a string or iterable of strings"
        )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
