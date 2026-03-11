"""Integration tests for the GitHub App router."""
from __future__ import annotations

import hashlib
import hmac
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import GitHubAppSettings
from app.dependencies import get_current_user, get_github_app_service
from app.routers.github_app import router as github_app_router
from app.services.github_app_service import GitHubAppService


def _build_app() -> FastAPI:
    """Build a minimal FastAPI app with just the GitHub App router."""
    app = FastAPI()
    app.include_router(github_app_router)
    return app


def _make_service(
    app_id: str | None = None,
    private_key: str | None = None,
    webhook_secret: str | None = None,
) -> GitHubAppService:
    settings = GitHubAppSettings()
    settings.app_id = app_id
    settings.private_key = private_key
    settings.webhook_secret = webhook_secret
    return GitHubAppService(settings)


def _signed_payload(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


# ── GET /api/v1/github-app/status ─────────────────────────────────────────


def test_status_unconfigured():
    app = _build_app()
    svc = _make_service()
    app.dependency_overrides[get_github_app_service] = lambda: svc
    with TestClient(app) as client:
        resp = client.get("/api/v1/github-app/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_configured"] is False
    assert data["app_id"] is None


def test_status_configured():
    app = _build_app()
    svc = _make_service(
        app_id="123",
        private_key=(
            "-----BEGIN RSA PRIVATE KEY-----\n"
            "dummy\n"
            "-----END RSA PRIVATE KEY-----"
        ),
    )
    app.dependency_overrides[get_github_app_service] = lambda: svc
    with TestClient(app) as client:
        resp = client.get("/api/v1/github-app/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_configured"] is True
    assert data["app_id"] == "123"


# ── GET /api/v1/github-app/installations ──────────────────────────────────


def test_installations_requires_auth():
    app = _build_app()
    with TestClient(app) as client:
        resp = client.get("/api/v1/github-app/installations")
    assert resp.status_code == 401


def test_installations_unconfigured():
    app = _build_app()
    app.dependency_overrides[get_github_app_service] = lambda: _make_service()
    app.dependency_overrides[get_current_user] = lambda: MagicMock()
    with TestClient(app) as client:
        resp = client.get("/api/v1/github-app/installations")
    assert resp.status_code == 503


def test_installations_returns_list():
    svc = _make_service(app_id="123", private_key="key")
    svc.list_installations = AsyncMock(
        return_value=[
            {
                "id": 1,
                "account": {"login": "myorg", "type": "Organization"},
                "html_url": "https://github.com/installations/1",
                "app_id": 123,
            }
        ]
    )
    app = _build_app()
    app.dependency_overrides[get_github_app_service] = lambda: svc
    app.dependency_overrides[get_current_user] = lambda: MagicMock()
    with TestClient(app) as client:
        resp = client.get("/api/v1/github-app/installations")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["account_login"] == "myorg"
    assert data[0]["id"] == 1


# ── POST /api/v1/github-app/installations/{id}/token ──────────────────────


def test_get_token_requires_auth():
    app = _build_app()
    with TestClient(app) as client:
        resp = client.post("/api/v1/github-app/installations/42/token")
    assert resp.status_code == 401


def test_get_token_success():
    svc = _make_service(app_id="123", private_key="key")
    svc.get_installation_token = AsyncMock(
        return_value={"token": "ghs_abc", "expires_at": "2099-01-01T00:00:00Z"}
    )
    app = _build_app()
    app.dependency_overrides[get_github_app_service] = lambda: svc
    app.dependency_overrides[get_current_user] = lambda: MagicMock()
    with TestClient(app) as client:
        resp = client.post("/api/v1/github-app/installations/42/token")
    assert resp.status_code == 200
    data = resp.json()
    assert data["token"] == "ghs_abc"
    assert data["expires_at"] == "2099-01-01T00:00:00Z"


def test_get_token_unconfigured():
    app = _build_app()
    app.dependency_overrides[get_github_app_service] = lambda: _make_service()
    app.dependency_overrides[get_current_user] = lambda: MagicMock()
    with TestClient(app) as client:
        resp = client.post("/api/v1/github-app/installations/42/token")
    assert resp.status_code == 503


# ── POST /api/v1/github-app/webhooks ──────────────────────────────────────


def test_webhook_no_secret_configured():
    """Webhook endpoint returns 503 when no secret is configured (fail-closed)."""
    app = _build_app()
    app.dependency_overrides[get_github_app_service] = lambda: _make_service()
    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/github-app/webhooks",
            content=b'{"action":"created"}',
            headers={"X-GitHub-Event": "installation"},
        )
    assert resp.status_code == 503


def test_webhook_invalid_signature():
    """Webhook endpoint returns 401 on invalid signature."""
    app = _build_app()
    app.dependency_overrides[get_github_app_service] = lambda: _make_service(
        webhook_secret="my-secret"
    )
    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/github-app/webhooks",
            content=b'{"action":"created"}',
            headers={
                "X-GitHub-Event": "installation",
                "X-Hub-Signature-256": "sha256=invalidsig",
            },
        )
    assert resp.status_code == 401


def test_webhook_valid_signature():
    """Webhook endpoint returns 200 with ack on valid signature."""
    secret = "my-secret"
    body = b'{"action":"created"}'
    sig = _signed_payload(secret, body)
    app = _build_app()
    app.dependency_overrides[get_github_app_service] = lambda: _make_service(
        webhook_secret=secret
    )
    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/github-app/webhooks",
            content=body,
            headers={
                "X-GitHub-Event": "installation",
                "X-Hub-Signature-256": sig,
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["received"] is True
    assert data["event"] == "installation"

