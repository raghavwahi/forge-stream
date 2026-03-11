"""Stateless double-submit CSRF protection middleware."""

from __future__ import annotations

import secrets
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

_TOKEN_TTL: int = 3600  # seconds (1 hour)
_EXCLUDED_PATHS: frozenset[str] = frozenset({"/health"})
_SAFE_METHODS: frozenset[str] = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


def _generate_token() -> str:
    """Return a CSRF token as ``'<random_hex>.<unix_timestamp>'``."""
    rand = secrets.token_hex(32)
    ts = str(int(time.time()))
    return f"{rand}.{ts}"


def _is_valid_token(token: str) -> bool:
    """Return ``True`` if *token* is well-formed and not expired."""
    if "." not in token:
        return False

    parts = token.rsplit(".", 1)
    if len(parts) != 2:
        return False

    try:
        ts = int(parts[1])
    except ValueError:
        return False

    return (time.time() - ts) < _TOKEN_TTL


class CSRFMiddleware(BaseHTTPMiddleware):
    """CSRF protection using the double-submit cookie pattern.

    * GET/HEAD/OPTIONS/TRACE requests receive a fresh ``csrf_token`` cookie.
    * All other methods must supply an ``X-CSRF-Token`` header whose value
      matches the ``csrf_token`` cookie and is not expired.
    * Paths in ``_EXCLUDED_PATHS`` (e.g. ``/health``) bypass CSRF checks.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        if path in _EXCLUDED_PATHS:
            return await call_next(request)

        if request.method in _SAFE_METHODS:
            response = await call_next(request)
            token = _generate_token()
            response.set_cookie(
                "csrf_token", token, httponly=False, samesite="strict"
            )
            return response

        cookie_token = request.cookies.get("csrf_token", "")
        header_token = request.headers.get("X-CSRF-Token", "")

        if not cookie_token or not header_token:
            return JSONResponse(
                {"detail": "CSRF token missing"}, status_code=403
            )

        if cookie_token != header_token or not _is_valid_token(header_token):
            return JSONResponse(
                {"detail": "CSRF token invalid"}, status_code=403
            )

        return await call_next(request)
