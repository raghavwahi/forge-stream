"""Request validation middleware."""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """Middleware that validates incoming requests.

    Currently a no-op pass-through; extend this class to add shared
    request validation logic (e.g., required headers, payload size limits).
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        return await call_next(request)
