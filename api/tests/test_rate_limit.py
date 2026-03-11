"""Tests for the rate limiting middleware.

These tests exercise:
- Tier selection (auth routes per-IP, authenticated per-user, unauthenticated
  per-IP) and verify the correct Redis key scope and limit are used.
- ``X-RateLimit-*`` response headers on both allowed and rejected requests.
- HTTP 429 when the Lua script signals that the limit has been exceeded.
- Redis-unavailable pass-through (no headers, no 429).
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from app.middleware.rate_limit import RateLimitMiddleware

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_JWT_SECRET = "test-secret-key"
_JWT_ALGORITHM = "HS256"


def _make_token(sub: str = "user-uuid-1234") -> str:
    """Return a signed JWT with the given ``sub`` claim."""
    return jwt.encode({"sub": sub}, _JWT_SECRET, algorithm=_JWT_ALGORITHM)


def _lua_result(count: int, remaining: int, reset_ts: int | None = None):
    """Build the mock return value matching the Lua script's output format."""
    if reset_ts is None:
        reset_ts = int(time.time()) + 60
    return [count, remaining, reset_ts]


def _make_redis_mock(count: int = 1, remaining: int = 59, reset_ts: int | None = None):
    """Return an AsyncMock Redis client whose ``eval`` simulates the Lua script."""
    client = AsyncMock()
    client.eval = AsyncMock(return_value=_lua_result(count, remaining, reset_ts))
    return client


def _make_provider_mock(redis_client):
    """Return a mock RedisProvider with the given underlying client."""
    provider = MagicMock()
    type(provider).client = property(lambda self: redis_client)
    return provider


# ---------------------------------------------------------------------------
# App fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def app():
    """Minimal FastAPI app with RateLimitMiddleware attached."""
    _app = FastAPI()
    _app.add_middleware(RateLimitMiddleware)

    @_app.get("/health")
    async def health():
        return {"status": "ok"}

    @_app.get("/api/v1/auth/login")
    async def login():
        return {"token": "fake"}

    return _app


@pytest.fixture()
def client(app):
    """TestClient wrapping the minimal app, with JWT_SECRET_KEY set."""
    mock_settings = MagicMock(
        jwt_secret_key=_JWT_SECRET,
        jwt_algorithm=_JWT_ALGORITHM,
        rate_limit=MagicMock(unauthenticated=60, authenticated=200, window_seconds=60),
    )
    with patch("app.middleware.rate_limit.get_settings", return_value=mock_settings):
        with TestClient(app, raise_server_exceptions=True) as tc:
            yield tc


# ---------------------------------------------------------------------------
# Helpers to inject a mock redis_provider into the app state
# ---------------------------------------------------------------------------


def _set_redis(app, redis_client):
    app.state.redis_provider = _make_provider_mock(redis_client)


def _clear_redis(app):
    if hasattr(app.state, "redis_provider"):
        del app.state.redis_provider


# ---------------------------------------------------------------------------
# Tests: unauthenticated tier (per-IP, lower limit)
# ---------------------------------------------------------------------------


class TestUnauthenticatedTier:
    def test_headers_present_on_allowed_request(self, client, app):
        reset_ts = int(time.time()) + 60
        _set_redis(app, _make_redis_mock(count=1, remaining=59, reset_ts=reset_ts))
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.headers["X-RateLimit-Limit"] == "60"
        assert resp.headers["X-RateLimit-Remaining"] == "59"
        assert resp.headers["X-RateLimit-Reset"] == str(reset_ts)

    def test_429_when_limit_exceeded(self, client, app):
        reset_ts = int(time.time()) + 30
        _set_redis(app, _make_redis_mock(count=60, remaining=-1, reset_ts=reset_ts))
        resp = client.get("/health")
        assert resp.status_code == 429
        assert resp.headers["X-RateLimit-Limit"] == "60"
        assert resp.headers["X-RateLimit-Remaining"] == "0"
        assert resp.headers["X-RateLimit-Reset"] == str(reset_ts)
        assert resp.json()["detail"] == "Rate limit exceeded. Try again later."

    def test_lua_eval_called_with_correct_key_scope(self, client, app):
        redis_client = _make_redis_mock()
        _set_redis(app, redis_client)
        client.get("/health")
        call_args = redis_client.eval.call_args
        # KEYS[1] is the first positional arg after the script and numkeys
        key = call_args[0][2]
        assert key.startswith("rl:ip:"), f"Unexpected key scope in: {key}"
        assert key.endswith(":global"), f"Unexpected route prefix in: {key}"


# ---------------------------------------------------------------------------
# Tests: authenticated tier (per-user, higher limit)
# ---------------------------------------------------------------------------


class TestAuthenticatedTier:
    def test_headers_use_authenticated_limit(self, client, app):
        reset_ts = int(time.time()) + 60
        _set_redis(app, _make_redis_mock(count=1, remaining=199, reset_ts=reset_ts))
        token = _make_token(sub="user-uuid-abc")
        resp = client.get("/health", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.headers["X-RateLimit-Limit"] == "200"
        assert resp.headers["X-RateLimit-Remaining"] == "199"

    def test_lua_eval_called_with_user_scope_and_uuid(self, client, app):
        redis_client = _make_redis_mock()
        _set_redis(app, redis_client)
        user_id = "user-uuid-abc"
        token = _make_token(sub=user_id)
        client.get("/health", headers={"Authorization": f"Bearer {token}"})
        call_args = redis_client.eval.call_args
        key = call_args[0][2]
        assert key.startswith("rl:user:"), f"Expected user scope, got: {key}"
        assert user_id in key, f"Expected user UUID in key: {key}"
        assert key.endswith(":global"), f"Expected global route prefix: {key}"

    def test_429_for_authenticated_user(self, client, app):
        reset_ts = int(time.time()) + 10
        _set_redis(app, _make_redis_mock(count=200, remaining=-1, reset_ts=reset_ts))
        token = _make_token(sub="user-uuid-xyz")
        resp = client.get("/health", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 429
        assert resp.headers["X-RateLimit-Limit"] == "200"
        assert resp.headers["X-RateLimit-Remaining"] == "0"


# ---------------------------------------------------------------------------
# Tests: auth route tier (per-IP, route-specific limit)
# ---------------------------------------------------------------------------


class TestAuthRouteTier:
    def test_login_uses_route_specific_limit(self, client, app):
        reset_ts = int(time.time()) + 60
        _set_redis(app, _make_redis_mock(count=1, remaining=9, reset_ts=reset_ts))
        resp = client.get("/api/v1/auth/login")
        assert resp.status_code == 200
        assert resp.headers["X-RateLimit-Limit"] == "10"
        assert resp.headers["X-RateLimit-Remaining"] == "9"

    def test_login_429_at_boundary(self, client, app):
        reset_ts = int(time.time()) + 45
        _set_redis(app, _make_redis_mock(count=10, remaining=-1, reset_ts=reset_ts))
        resp = client.get("/api/v1/auth/login")
        assert resp.status_code == 429
        assert resp.headers["X-RateLimit-Limit"] == "10"

    def test_login_key_uses_ip_scope_and_full_path(self, client, app):
        redis_client = _make_redis_mock()
        _set_redis(app, redis_client)
        client.get("/api/v1/auth/login")
        call_args = redis_client.eval.call_args
        key = call_args[0][2]
        assert key.startswith("rl:ip:"), f"Expected IP scope: {key}"
        assert "/api/v1/auth/login" in key, f"Expected route path in key: {key}"


# ---------------------------------------------------------------------------
# Tests: Redis unavailable pass-through
# ---------------------------------------------------------------------------


class TestRedisUnavailable:
    def test_no_provider_passes_through(self, client, app):
        _clear_redis(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert "X-RateLimit-Limit" not in resp.headers

    def test_disconnected_provider_passes_through(self, client, app):
        def _raise_not_connected(self):
            raise RuntimeError("not connected")

        provider = MagicMock()
        type(provider).client = property(_raise_not_connected)
        app.state.redis_provider = provider
        resp = client.get("/health")
        assert resp.status_code == 200
        assert "X-RateLimit-Limit" not in resp.headers
