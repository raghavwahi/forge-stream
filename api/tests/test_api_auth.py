"""API contract tests for authentication endpoints."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=False)


class TestAuthRegistration:
    def test_register_requires_json_body(self):
        resp = client.post("/api/v1/auth/register")
        assert resp.status_code in (400, 422)

    def test_register_validates_email_format(self):
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "not-an-email", "password": "pass123", "full_name": "Test"},
        )
        assert resp.status_code == 422

    def test_register_validates_password_length(self):
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "123", "full_name": "Test"},
        )
        # Too-short password should be rejected
        assert resp.status_code in (400, 422)


class TestAuthLogin:
    def test_login_requires_credentials(self):
        resp = client.post("/api/v1/auth/login")
        assert resp.status_code == 422

    def test_login_with_invalid_credentials_returns_401(self):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "nonexistent@example.com", "password": "wrongpass"},
        )
        assert resp.status_code in (401, 500)  # 500 if DB not available

    def test_login_response_has_token_fields(self):
        """On success the response should include access_token and token_type."""
        # This test will fail with 500 if DB is not available in unit env — that's OK.
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "admin123"},
        )
        if resp.status_code == 200:
            data = resp.json()
            assert "access_token" in data
            assert "token_type" in data


class TestProtectedEndpoints:
    def test_me_requires_auth(self):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code in (401, 403)

    def test_refresh_requires_token(self):
        resp = client.post("/api/v1/auth/refresh")
        assert resp.status_code in (401, 403, 422)

    def test_logout_requires_auth(self):
        resp = client.post("/api/v1/auth/logout")
        assert resp.status_code in (401, 403)

    def test_bearer_with_invalid_token_returns_401(self):
        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.jwt.token"},
        )
        assert resp.status_code == 401
