"""Tests for CSRF double-submit cookie middleware and token endpoint."""
from __future__ import annotations

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.csrf import (
    _COOKIE_NAME,
    _HEADER_NAME,
    _MAX_TOKEN_AGE_SECONDS,
    CSRFMiddleware,
    _generate_token,
    _is_valid_token,
)
from app.routers.csrf import router as csrf_router

# ── Minimal test apps ─────────────────────────────────────────────


def _build_middleware_app() -> FastAPI:
    """Minimal app that exercises the middleware without the full stack."""
    test_app = FastAPI()
    test_app.add_middleware(CSRFMiddleware)

    @test_app.get("/safe")
    async def safe_endpoint():
        return {"ok": True}

    @test_app.post("/mutating")
    async def mutating_endpoint():
        return {"ok": True}

    @test_app.post("/api/v1/auth/login")
    async def excluded_auth():
        return {"ok": True}

    @test_app.post("/api/v1/github-app/webhooks")
    async def excluded_webhooks():
        return {"ok": True}

    @test_app.get("/health")
    async def excluded_health():
        return {"status": "ok"}

    return test_app


def _build_full_app() -> FastAPI:
    """App that includes both the middleware and the CSRF token endpoint."""
    full_app = FastAPI()
    full_app.add_middleware(CSRFMiddleware)
    full_app.include_router(csrf_router, prefix="/api/v1")
    return full_app


_middleware_app = _build_middleware_app()
_full_app = _build_full_app()


# ── Token utility unit tests ──────────────────────────────────────


class TestIsValidToken:
    def test_freshly_generated_token_is_valid(self):
        token = _generate_token()
        assert _is_valid_token(token) is True

    def test_expired_token_is_rejected(self):
        ts = int(time.time()) - _MAX_TOKEN_AGE_SECONDS - 1
        token = f"abcdef.{ts}"
        assert _is_valid_token(token) is False

    def test_future_timestamp_is_rejected(self):
        ts = int(time.time()) + 3600
        token = f"abcdef.{ts}"
        assert _is_valid_token(token) is False

    def test_malformed_tokens_are_rejected(self):
        assert _is_valid_token("notavalidtoken") is False
        assert _is_valid_token("") is False
        assert _is_valid_token("abc.notanint") is False


# ── Cookie issuance on safe requests ─────────────────────────────


def test_get_sets_csrf_cookie_when_absent():
    client = TestClient(_middleware_app)
    resp = client.get("/safe")
    assert resp.status_code == 200
    assert _COOKIE_NAME in resp.cookies


def test_get_does_not_rotate_cookie_when_valid():
    client = TestClient(_middleware_app)
    resp1 = client.get("/safe")
    token = resp1.cookies.get(_COOKIE_NAME)
    assert token is not None
    # Second safe request — middleware should leave the valid token alone
    resp2 = client.get("/safe")
    # Response should NOT set a new cookie for a still-valid token
    assert _COOKIE_NAME not in resp2.cookies


def test_get_refreshes_cookie_when_expired():
    client = TestClient(_middleware_app)
    expired_token = f"abc123.{int(time.time()) - _MAX_TOKEN_AGE_SECONDS - 1}"
    client.cookies.set(_COOKIE_NAME, expired_token)
    resp = client.get("/safe")
    assert resp.status_code == 200
    new_token = resp.cookies.get(_COOKIE_NAME)
    assert new_token is not None
    assert new_token != expired_token


# ── Mutating request validation ───────────────────────────────────


def test_post_without_csrf_header_returns_403():
    client = TestClient(_middleware_app)
    resp1 = client.get("/safe")
    token = resp1.cookies.get(_COOKIE_NAME)
    # POST without X-CSRF-Token header (cookie is in the session from resp1)
    client.cookies.set(_COOKIE_NAME, token)
    resp = client.post("/mutating")
    assert resp.status_code == 403
    assert resp.json()["detail"] == "CSRF token missing or invalid"


def test_post_with_mismatched_token_returns_403():
    client = TestClient(_middleware_app)
    resp1 = client.get("/safe")
    token = resp1.cookies.get(_COOKIE_NAME)
    client.cookies.set(_COOKIE_NAME, token)
    resp = client.post("/mutating", headers={_HEADER_NAME: "wrong-token"})
    assert resp.status_code == 403
    assert "CSRF" in resp.json()["detail"]


def test_post_with_matching_token_succeeds():
    client = TestClient(_middleware_app)
    resp1 = client.get("/safe")
    token = resp1.cookies.get(_COOKIE_NAME)
    client.cookies.set(_COOKIE_NAME, token)
    resp = client.post("/mutating", headers={_HEADER_NAME: token})
    assert resp.status_code == 200


def test_post_with_expired_token_returns_403():
    client = TestClient(_middleware_app)
    expired_token = f"abc123.{int(time.time()) - _MAX_TOKEN_AGE_SECONDS - 1}"
    client.cookies.set(_COOKIE_NAME, expired_token)
    resp = client.post("/mutating", headers={_HEADER_NAME: expired_token})
    assert resp.status_code == 403


def test_post_with_future_token_returns_403():
    client = TestClient(_middleware_app)
    future_token = f"abc123.{int(time.time()) + 7200}"
    client.cookies.set(_COOKIE_NAME, future_token)
    resp = client.post("/mutating", headers={_HEADER_NAME: future_token})
    assert resp.status_code == 403


# ── Excluded paths ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "method,path",
    [
        ("POST", "/api/v1/auth/login"),
        ("POST", "/api/v1/github-app/webhooks"),
        ("GET", "/health"),
    ],
)
def test_excluded_paths_skip_csrf_check(method, path):
    client = TestClient(_middleware_app)
    resp = client.request(method, path)
    assert resp.status_code == 200
    # Excluded paths must not set a CSRF cookie
    assert _COOKIE_NAME not in resp.cookies


# ── CSRF token endpoint ───────────────────────────────────────────


def test_csrf_token_endpoint_issues_new_token_when_no_cookie():
    client = TestClient(_full_app)
    resp = client.get("/api/v1/csrf/token")
    assert resp.status_code == 200
    data = resp.json()
    assert data["token"] != ""
    # The response body token must match the cookie that was set
    assert resp.cookies.get(_COOKIE_NAME) == data["token"]


def test_csrf_token_endpoint_returns_existing_valid_token():
    client = TestClient(_full_app)
    # Bootstrap a token
    resp1 = client.get("/api/v1/csrf/token")
    token = resp1.json()["token"]
    # Subsequent call with valid cookie should return same token (no new cookie)
    resp2 = client.get("/api/v1/csrf/token")
    assert resp2.json()["token"] == token
    assert _COOKIE_NAME not in resp2.cookies
