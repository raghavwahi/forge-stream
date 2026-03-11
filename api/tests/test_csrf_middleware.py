"""Unit tests for CSRFMiddleware."""
from __future__ import annotations

import time

from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Route
from starlette.testclient import TestClient

from app.middleware.csrf import CSRFMiddleware, _generate_token, _is_valid_token

# ── Token helpers ─────────────────────────────────────────────────────────────


class TestGenerateToken:
    def test_returns_string(self):
        assert isinstance(_generate_token(), str)

    def test_contains_dot_separator(self):
        token = _generate_token()
        assert "." in token

    def test_uniqueness(self):
        tokens = {_generate_token() for _ in range(50)}
        assert len(tokens) == 50


class TestIsValidToken:
    def test_fresh_token_is_valid(self):
        token = _generate_token()
        assert _is_valid_token(token) is True

    def test_missing_dot_is_invalid(self):
        assert _is_valid_token("no-dot-here") is False

    def test_non_numeric_timestamp_is_invalid(self):
        assert _is_valid_token("hexdata.notanumber") is False

    def test_expired_token_is_invalid(self):
        past = str(int(time.time()) - 7200)  # 2 hours ago
        token = f"{'a' * 64}.{past}"
        assert _is_valid_token(token) is False


# ── Middleware integration ─────────────────────────────────────────────────────


def _make_app():
    app = Starlette(routes=[Route("/ping", endpoint=lambda r: Response("pong"))])
    app.add_middleware(CSRFMiddleware)
    return app


class TestCSRFMiddlewareIntegration:
    def test_get_sets_csrf_cookie(self):
        app = _make_app()
        c = TestClient(app, raise_server_exceptions=False)
        resp = c.get("/ping")
        assert "csrf_token" in resp.cookies

    def test_post_without_csrf_header_returns_403(self):
        app = _make_app()
        c = TestClient(app, raise_server_exceptions=False)
        # Prime the cookie
        c.get("/ping")
        resp = c.post("/ping")
        assert resp.status_code == 403

    def test_post_with_correct_csrf_header_passes(self):
        app = _make_app()
        c = TestClient(app, raise_server_exceptions=False)
        get_resp = c.get("/ping")
        token = get_resp.cookies.get("csrf_token", "")
        resp = c.post("/ping", headers={"X-CSRF-Token": token})
        # Will be 405 (not POST route) or 200, but NOT 403
        assert resp.status_code != 403

    def test_post_with_wrong_token_returns_403(self):
        app = _make_app()
        c = TestClient(app, raise_server_exceptions=False)
        c.get("/ping")
        resp = c.post("/ping", headers={"X-CSRF-Token": "wrong-token"})
        assert resp.status_code == 403

    def test_health_path_excluded(self):
        app = Starlette(routes=[Route("/health", endpoint=lambda r: Response("ok"))])
        app.add_middleware(CSRFMiddleware)
        c = TestClient(app, raise_server_exceptions=False)
        # POST to /health should not be CSRF-checked
        resp = c.post("/health")
        assert resp.status_code != 403
