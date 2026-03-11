"""Double-submit cookie CSRF protection middleware.

Strategy
--------
1. On every GET/HEAD/OPTIONS request a ``csrf_token`` cookie is set (if absent).
2. Mutating requests (POST, PUT, PATCH, DELETE) must echo the same token
   in the ``X-CSRF-Token`` request header.
3. Mismatch or missing header → HTTP 403.

Paths under ``/api/v1/auth/`` and ``/api/v1/github-app/webhooks`` are
excluded because they either handle their own verification or are called
by external services.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

_COOKIE_NAME = "csrf_token"
_HEADER_NAME = "x-csrf-token"
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
_EXCLUDE_PREFIXES = (
    "/api/v1/auth/",
    "/api/v1/github-app/webhooks",
    "/health",
)
_TOKEN_BYTES = 32
_MAX_TOKEN_AGE_SECONDS = 3600  # 1 hour


def _generate_token() -> str:
    raw = os.urandom(_TOKEN_BYTES)
    ts = str(int(time.time()))
    return f"{raw.hex()}.{ts}"


def _is_valid_token(token: str) -> bool:
    """Return True if token is syntactically correct and not expired."""
    try:
        _, ts_str = token.rsplit(".", 1)
        ts = int(ts_str)
    except (ValueError, AttributeError):
        return False
    return (time.time() - ts) < _MAX_TOKEN_AGE_SECONDS


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # Skip excluded paths
        if any(path.startswith(prefix) for prefix in _EXCLUDE_PREFIXES):
            return await call_next(request)

        cookie_token: str | None = request.cookies.get(_COOKIE_NAME)

        # Validate mutating requests
        if request.method not in _SAFE_METHODS:
            header_token = request.headers.get(_HEADER_NAME)
            if (
                not header_token
                or not cookie_token
                or not hmac.compare_digest(header_token, cookie_token)
                or not _is_valid_token(cookie_token)
            ):
                logger.warning(
                    "CSRF validation failed for %s %s", request.method, path
                )
                return Response(
                    content='{"detail":"CSRF token missing or invalid"}',
                    status_code=403,
                    media_type="application/json",
                )

        response = await call_next(request)

        # Refresh or set the cookie on safe requests
        if request.method in _SAFE_METHODS or not cookie_token:
            new_token = _generate_token()
            response.set_cookie(
                key=_COOKIE_NAME,
                value=new_token,
                httponly=False,   # must be readable by JS
                samesite="strict",
                secure=False,     # set True in production behind TLS
                max_age=_MAX_TOKEN_AGE_SECONDS,
                path="/",
            )

        return response
