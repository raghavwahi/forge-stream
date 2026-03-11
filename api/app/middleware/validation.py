"""
Request validation middleware implementing OWASP input validation best practices.

Enforces:
- Maximum request body size to prevent DoS
- Content-Type validation for POST/PUT/PATCH requests
- Security response headers (HSTS, X-Frame-Options, X-Content-Type-Options, etc.)
"""
from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

_DEFAULT_MAX_BODY_SIZE = 10 * 1024 * 1024  # 10 MB

_ALLOWED_CONTENT_TYPES = frozenset(
    [
        "application/json",
        "application/x-www-form-urlencoded",
        "multipart/form-data",
    ]
)

# Security headers added to every outbound response
_SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """
    Validates incoming requests and injects security headers on all responses.

    Checks (in order):
    1. Content-Length if present → 413 if body exceeds max_body_size
    2. Content-Type for body-bearing methods → 415 if unsupported
    3. Adds security headers to every response
    """

    def __init__(self, app: ASGIApp, max_body_size: int = _DEFAULT_MAX_BODY_SIZE) -> None:
        super().__init__(app)
        self.max_body_size = max_body_size

    async def dispatch(self, request: Request, call_next) -> Response:
        # 1. Check declared Content-Length
        content_length_header = request.headers.get("content-length")
        if content_length_header is not None:
            try:
                declared_size = int(content_length_header)
            except ValueError:
                return _security_response(
                    JSONResponse({"detail": "Invalid Content-Length header"}, status_code=400)
                )
            if declared_size > self.max_body_size:
                logger.warning(
                    "Request rejected: Content-Length %d exceeds max %d for %s %s",
                    declared_size,
                    self.max_body_size,
                    request.method,
                    request.url.path,
                )
                return _security_response(
                    JSONResponse({"detail": "Request body too large"}, status_code=413)
                )

        # 2. Content-Type validation for body-bearing methods
        if request.method in ("POST", "PUT", "PATCH"):
            raw_content_type = request.headers.get("content-type", "")
            mime_type = raw_content_type.split(";")[0].strip().lower()
            # Only enforce when a body is actually present
            if mime_type and mime_type not in _ALLOWED_CONTENT_TYPES:
                logger.warning(
                    "Request rejected: unsupported Content-Type '%s' for %s %s",
                    mime_type,
                    request.method,
                    request.url.path,
                )
                return _security_response(
                    JSONResponse(
                        {"detail": f"Unsupported Content-Type: {mime_type}"},
                        status_code=415,
                    )
                )

        # 3. Let the request proceed
        response = await call_next(request)

        # 4. Inject security headers on every response
        return _security_response(response)


def _security_response(response: Response) -> Response:
    """Mutate the response in-place to add security headers."""
    for header, value in _SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    return response
