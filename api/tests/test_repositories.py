"""Tests for the repository listing API endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.dependencies import get_current_user, get_github_app_service
from app.main import app
from app.models.user import UserInDB
from app.routers.repositories import _get_repos_service
from app.schemas.github_repos import GitHubRepo
from app.services.github_repos_service import GitHubReposService

# ── Fixtures / helpers ────────────────────────────────────────────────────────

_MOCK_USER = UserInDB(
    id=uuid.uuid4(),
    email="test@example.com",
    name="Test User",
    provider="email",
    is_active=True,
    created_at=datetime(2024, 1, 1),
    updated_at=datetime(2024, 1, 1),
)

_MOCK_REPOS = [
    GitHubRepo(
        id=1,
        name="forge-stream",
        full_name="org/forge-stream",
        private=False,
        description="ForgeStream repo",
        html_url="https://github.com/org/forge-stream",
        default_branch="main",
        installation_id=42,
    ),
    GitHubRepo(
        id=2,
        name="other-repo",
        full_name="org/other-repo",
        private=True,
        description=None,
        html_url="https://github.com/org/other-repo",
        default_branch="main",
        installation_id=42,
    ),
]


def _make_repos_service(repos: list[GitHubRepo]) -> GitHubReposService:
    svc = MagicMock(spec=GitHubReposService)
    svc.list_repos_for_installation = AsyncMock(return_value=repos)
    return svc


# ── GET /api/v1/repositories ─────────────────────────────────────────────────


def test_list_repositories_success():
    mock_svc = _make_repos_service(_MOCK_REPOS)

    app.dependency_overrides[get_current_user] = lambda: _MOCK_USER
    app.dependency_overrides[_get_repos_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        resp = client.get("/api/v1/repositories?installation_id=42")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert data["repos"][0]["name"] == "forge-stream"
    assert data["repos"][1]["name"] == "other-repo"


def test_list_repositories_requires_auth():
    mock_provider = MagicMock()
    mock_provider.is_configured = True
    mock_svc = MagicMock()
    mock_svc.is_configured = True
    mock_svc.provider = mock_provider

    app.dependency_overrides[get_github_app_service] = lambda: mock_svc

    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/repositories?installation_id=42")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 401


def test_list_repositories_503_when_not_configured():
    unconfigured_svc = MagicMock()
    unconfigured_svc.is_configured = False

    app.dependency_overrides[get_current_user] = lambda: _MOCK_USER
    app.dependency_overrides[get_github_app_service] = (
        lambda: unconfigured_svc
    )

    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/repositories?installation_id=42")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 503
    assert "not configured" in resp.json()["detail"]


def test_list_repositories_502_on_github_error():
    failing_svc = MagicMock(spec=GitHubReposService)
    failing_svc.list_repos_for_installation = AsyncMock(
        side_effect=RuntimeError("GitHub API unreachable")
    )

    app.dependency_overrides[get_current_user] = lambda: _MOCK_USER
    app.dependency_overrides[_get_repos_service] = lambda: failing_svc

    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/repositories?installation_id=42")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 502
    assert "Failed to fetch repositories" in resp.json()["detail"]


# ── GET /api/v1/repositories/search ──────────────────────────────────────────


def test_search_repositories_filters_by_name():
    mock_svc = _make_repos_service(_MOCK_REPOS)

    app.dependency_overrides[get_current_user] = lambda: _MOCK_USER
    app.dependency_overrides[_get_repos_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        resp = client.get(
            "/api/v1/repositories/search?installation_id=42&q=forge"
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["repos"][0]["name"] == "forge-stream"


def test_search_repositories_empty_query_returns_all():
    mock_svc = _make_repos_service(_MOCK_REPOS)

    app.dependency_overrides[get_current_user] = lambda: _MOCK_USER
    app.dependency_overrides[_get_repos_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        resp = client.get("/api/v1/repositories/search?installation_id=42")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["total"] == 2


def test_search_repositories_case_insensitive():
    mock_svc = _make_repos_service(_MOCK_REPOS)

    app.dependency_overrides[get_current_user] = lambda: _MOCK_USER
    app.dependency_overrides[_get_repos_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        resp = client.get(
            "/api/v1/repositories/search?installation_id=42&q=FORGE"
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_search_requires_auth():
    mock_provider = MagicMock()
    mock_provider.is_configured = True
    mock_svc = MagicMock()
    mock_svc.is_configured = True
    mock_svc.provider = mock_provider

    app.dependency_overrides[get_github_app_service] = lambda: mock_svc

    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            "/api/v1/repositories/search?installation_id=42&q=forge"
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 401


def test_search_repositories_502_on_github_error():
    failing_svc = MagicMock(spec=GitHubReposService)
    failing_svc.list_repos_for_installation = AsyncMock(
        side_effect=RuntimeError("GitHub API unreachable")
    )

    app.dependency_overrides[get_current_user] = lambda: _MOCK_USER
    app.dependency_overrides[_get_repos_service] = lambda: failing_svc

    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            "/api/v1/repositories/search?installation_id=42&q=forge"
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 502

