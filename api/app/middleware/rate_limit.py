from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.providers.base import BaseCacheProvider

RATE_LIMITS: dict[str, tuple[int, int]] = {
    "/api/v1/auth/signup": (5, 60),
    "/api/v1/auth/login": (10, 60),
    "/api/v1/auth/password-reset/request": (3, 300),
    "/api/v1/auth/refresh": (30, 60),
}
DEFAULT_LIMIT = (60, 60)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: callable
    ) -> Response:
        redis: BaseCacheProvider | None = getattr(
            request.app.state, "redis_provider", None
        )
        if redis is None:
            return await call_next(request)

        # Use request.client.host (the TCP connection source).
        # When deployed behind a reverse proxy, add Starlette's
        # ProxyHeadersMiddleware so this resolves to the real client IP
        # rather than the proxy's address.
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path
        max_requests, window = RATE_LIMITS.get(path, DEFAULT_LIMIT)
        key = f"rate_limit:{path}:{client_ip}"

        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, window)

        if current > max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Try again later.",
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(max_requests)
        response.headers["X-RateLimit-Remaining"] = str(
            max(0, max_requests - current)
        )
        return response
