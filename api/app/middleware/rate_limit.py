"""Rate limiting middleware using a Redis-backed sliding window algorithm.

Sliding window algorithm
------------------------
For each incoming request a Redis sorted set keyed as
``rl:{scope}:{identifier}:{route_prefix}`` is maintained.  Each element in
the set is a unique request identifier (UUID4) and its score is the current
Unix timestamp in **milliseconds**.

On every request:

1. ``ZREMRANGEBYSCORE key -inf (now_ms - window_ms)``
   — prune entries that fall outside the current window.
2. ``ZCARD key``
   — count how many requests remain inside the window.
3. If *count >= limit* → return HTTP 429 with rate-limit headers; do **not**
   add the request to the set.
4. Otherwise ``ZADD key {uuid4: now_ms}`` — record the request.
5. ``EXPIRE key window_seconds`` — reset the TTL so Redis can reclaim idle
   keys automatically.

This provides a true sliding window (no boundary spikes) at O(log N) per
request, where N is the number of requests in the current window.

Rate-limit tiers
----------------
* **Auth routes** (signup, login, refresh, password-reset): fixed per-route
  limits applied on a *per-IP* basis regardless of authentication status.
* **Authenticated callers** (valid ``Authorization: Bearer <token>`` header):
  ``RATE_LIMIT_AUTHENTICATED`` requests per window, keyed on user UUID.
* **Unauthenticated callers**: ``RATE_LIMIT_UNAUTHENTICATED`` requests per
  window, keyed on client IP.

Key format: ``rl:{scope}:{identifier}:{route_prefix}``
  - *scope*        – ``user`` or ``ip``
  - *identifier*   – user UUID or client IP address
  - *route_prefix* – full path for auth routes, ``global`` otherwise
"""

import logging
import time
import uuid
from typing import Callable

from fastapi import Request, status
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from app.config import get_settings
from app.providers.redis import RedisProvider

logger = logging.getLogger(__name__)

# Route-specific limits: path -> (max_requests, window_seconds)
# These apply per-IP regardless of auth status.
ROUTE_LIMITS: dict[str, tuple[int, int]] = {
    "/api/v1/auth/signup": (5, 60),
    "/api/v1/auth/login": (10, 60),
    "/api/v1/auth/password-reset/request": (3, 300),
    "/api/v1/auth/refresh": (30, 60),
}


def _extract_user_id(
    request: Request, jwt_secret: str, jwt_algorithm: str
) -> str | None:
    """Extract the user UUID from an ``Authorization: Bearer <token>`` header.

    Returns the ``sub`` claim string if the token is present and valid,
    ``None`` in all other cases.  The raw token is never logged.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[len("Bearer "):]
    try:
        data = jwt.decode(token, jwt_secret, algorithms=[jwt_algorithm])
        return data.get("sub")
    except JWTError:
        return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window Redis rate limiter with per-user and per-IP tiers."""

    def __init__(self, app, **kwargs) -> None:
        super().__init__(app, **kwargs)
        # Cache settings at startup to avoid constructing Settings on every
        # request (get_settings() is not cached by default).
        settings = get_settings()
        self._jwt_secret: str = settings.jwt_secret_key
        self._jwt_algorithm: str = settings.jwt_algorithm
        self._rl_unauthenticated: int = settings.rate_limit.unauthenticated
        self._rl_authenticated: int = settings.rate_limit.authenticated
        self._rl_window_seconds: int = settings.rate_limit.window_seconds

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        redis_provider: RedisProvider | None = getattr(
            request.app.state, "redis_provider", None
        )

        # If Redis is unavailable, allow the request through rather than
        # blocking all traffic.
        if redis_provider is None or redis_provider.client is None:
            return await call_next(request)

        client = redis_provider.client
        path = request.url.path

        # ------------------------------------------------------------------
        # Determine rate-limit parameters for this request
        # ------------------------------------------------------------------
        if path in ROUTE_LIMITS:
            # Auth endpoints: fixed limits, always keyed by IP.
            max_requests, window_seconds = ROUTE_LIMITS[path]
            scope = "ip"
            identifier = (
                request.client.host if request.client else "unknown"
            )
            route_prefix = path
        else:
            window_seconds = self._rl_window_seconds
            user_id = _extract_user_id(
                request, self._jwt_secret, self._jwt_algorithm
            )
            if user_id:
                scope = "user"
                identifier = user_id
                max_requests = self._rl_authenticated
            else:
                scope = "ip"
                identifier = (
                    request.client.host if request.client else "unknown"
                )
                max_requests = self._rl_unauthenticated
            route_prefix = "global"

        key = f"rl:{scope}:{identifier}:{route_prefix}"

        now_ms = int(time.time() * 1000)
        window_ms = window_seconds * 1000
        window_start_ms = now_ms - window_ms
        # Unix timestamp when the window will have fully elapsed from now.
        reset_ts = int(time.time()) + window_seconds

        # ------------------------------------------------------------------
        # Sliding window via Redis sorted set
        # ------------------------------------------------------------------

        # Step 1: Remove entries that have fallen outside the window.
        await client.zremrangebyscore(key, "-inf", window_start_ms)

        # Step 2: Count remaining (in-window) entries.
        current_count: int = await client.zcard(key)

        if current_count >= max_requests:
            logger.warning(
                "Rate limit exceeded: scope=%s route_prefix=%s",
                scope,
                route_prefix,
            )
            response = JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded. Try again later."},
            )
            response.headers["X-RateLimit-Limit"] = str(max_requests)
            response.headers["X-RateLimit-Remaining"] = "0"
            response.headers["X-RateLimit-Reset"] = str(reset_ts)
            return response

        # Step 3: Record this request in the sorted set.
        request_id = str(uuid.uuid4())
        await client.zadd(key, {request_id: now_ms})

        # Step 4: Refresh TTL so idle keys are reclaimed by Redis.
        await client.expire(key, window_seconds)

        # remaining reflects the slot consumed by this request.
        remaining = max(0, max_requests - current_count - 1)

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_ts)
        return response
