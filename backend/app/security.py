"""Security middleware and helpers."""

from __future__ import annotations

from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from .config import get_settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach security headers to every response."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self.settings = get_settings()

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        settings = self.settings

        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", settings.security_frame_options)
        response.headers.setdefault(
            "Referrer-Policy", settings.security_referrer_policy
        )
        response.headers.setdefault(
            "Permissions-Policy", settings.security_permissions_policy
        )

        if settings.security_csp:
            response.headers.setdefault(
                "Content-Security-Policy", settings.security_csp
            )

        # Apply HSTS only outside development
        if settings.security_hsts_enabled and settings.app_env != "development":
            response.headers.setdefault(
                "Strict-Transport-Security",
                f"max-age={settings.security_hsts_max_age}; includeSubDomains",
            )

        return response
