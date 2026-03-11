"""Tests for the repository management API endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.dependencies import get_current_user, get_repository_service
from app.main import app
from app.models.user import UserInDB
from app.schemas.repositories import (
    IssueRunResponse,
    RepositoryListResponse,
    RepositoryResponse,
)

# ── Fixtures ──────────────────────────────────────────────────────

_USER_ID = uuid.uuid4()
_REPO_ID = uuid.uuid4()
_RUN_ID = uuid.uuid4()
_NOW = datetime.now(timezone.utc)

_MOCK_USER = UserInDB(
    id=_USER_ID,
    email="test@example.com",
    name="Test User",
    provider="email",
    is_active=True,
    is_verified=True,
    created_at=_NOW,
    updated_at=_NOW,
)

_MOCK_REPO = RepositoryResponse(
    id=_REPO_ID,
    user_id=_USER_ID,
    github_repo_id=12345,
    owner="testowner",
    name="testrepo",
    full_name="testowner/testrepo",
    description="A test repository",
    is_private=False,
    default_branch="main",
    html_url="https://github.com/testowner/testrepo",
    is_connected=True,
    connected_at=_NOW,
    last_synced_at=None,
    created_at=_NOW,
    updated_at=_NOW,
)

_MOCK_RUN = IssueRunResponse(
    id=_RUN_ID,
    repository_id=_REPO_ID,
    user_id=_USER_ID,
    prompt="Create auth issues",
    model="gpt-4o-mini",
    status="pending",
    total_issues=None,
    created_issues=0,
    error_message=None,
    started_at=None,
    completed_at=None,
    created_at=_NOW,
)


def _make_client(mock_service) -> TestClient:
    """Return a TestClient with auth and service dependencies overridden."""
    app.dependency_overrides[get_current_user] = lambda: _MOCK_USER
    app.dependency_overrides[get_repository_service] = lambda: mock_service
    return TestClient(app)


def _clear_overrides():
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_repository_service, None)


# ── GET /api/v1/repositories/ ─────────────────────────────────────


def test_list_repositories():
    mock_service = AsyncMock()
    mock_service.list_repositories = AsyncMock(
        return_value=RepositoryListResponse(
            repositories=[_MOCK_REPO], total=1
        )
    )
    client = _make_client(mock_service)
    try:
        resp = client.get("/api/v1/repositories/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["repositories"][0]["full_name"] == "testowner/testrepo"
    finally:
        _clear_overrides()


# ── POST /api/v1/repositories/ ────────────────────────────────────


def test_connect_repository():
    mock_service = AsyncMock()
    mock_service.connect_repository = AsyncMock(return_value=_MOCK_REPO)
    client = _make_client(mock_service)
    try:
        resp = client.post(
            "/api/v1/repositories/",
            json={
                "github_repo_id": 12345,
                "owner": "testowner",
                "name": "testrepo",
                "full_name": "testowner/testrepo",
                "description": "A test repository",
                "is_private": False,
                "default_branch": "main",
                "html_url": "https://github.com/testowner/testrepo",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["github_repo_id"] == 12345
        assert data["full_name"] == "testowner/testrepo"
        assert data["is_connected"] is True
    finally:
        _clear_overrides()


# ── GET /api/v1/repositories/{repo_id} ────────────────────────────


def test_get_repository():
    mock_service = AsyncMock()
    mock_service.get_repository = AsyncMock(return_value=_MOCK_REPO)
    client = _make_client(mock_service)
    try:
        resp = client.get(f"/api/v1/repositories/{_REPO_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(_REPO_ID)
    finally:
        _clear_overrides()


def test_get_repository_not_found():
    from fastapi import HTTPException, status

    mock_service = AsyncMock()
    mock_service.get_repository = AsyncMock(
        side_effect=HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )
    )
    client = _make_client(mock_service)
    try:
        resp = client.get(f"/api/v1/repositories/{uuid.uuid4()}")
        assert resp.status_code == 404
    finally:
        _clear_overrides()


# ── DELETE /api/v1/repositories/{repo_id} ─────────────────────────


def test_disconnect_repository():
    mock_service = AsyncMock()
    mock_service.disconnect_repository = AsyncMock(return_value=True)
    client = _make_client(mock_service)
    try:
        resp = client.delete(f"/api/v1/repositories/{_REPO_ID}")
        assert resp.status_code == 200
        assert resp.json() == {"message": "Repository disconnected"}
    finally:
        _clear_overrides()


def test_disconnect_repository_not_found():
    from fastapi import HTTPException, status

    mock_service = AsyncMock()
    mock_service.disconnect_repository = AsyncMock(
        side_effect=HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )
    )
    client = _make_client(mock_service)
    try:
        # Simulate another user's repo — service returns 404
        resp = client.delete(f"/api/v1/repositories/{uuid.uuid4()}")
        assert resp.status_code == 404
    finally:
        _clear_overrides()


# ── GET /api/v1/repositories/{repo_id}/runs ───────────────────────


def test_list_issue_runs():
    mock_service = AsyncMock()
    mock_service.get_issue_runs = AsyncMock(return_value=[_MOCK_RUN])
    client = _make_client(mock_service)
    try:
        resp = client.get(f"/api/v1/repositories/{_REPO_ID}/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["status"] == "pending"
        assert data[0]["repository_id"] == str(_REPO_ID)
    finally:
        _clear_overrides()


# ── POST /api/v1/repositories/{repo_id}/runs ─────────────────────


def test_start_issue_run():
    mock_service = AsyncMock()
    mock_service.start_issue_run = AsyncMock(return_value=_MOCK_RUN)
    client = _make_client(mock_service)
    try:
        resp = client.post(
            f"/api/v1/repositories/{_REPO_ID}/runs",
            json={"prompt": "Create auth issues", "model": "gpt-4o-mini"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"
        assert data["prompt"] == "Create auth issues"
    finally:
        _clear_overrides()


def test_start_issue_run_no_repository_id_in_body():
    """The request body must NOT require repository_id — it comes from path."""
    mock_service = AsyncMock()
    mock_service.start_issue_run = AsyncMock(return_value=_MOCK_RUN)
    client = _make_client(mock_service)
    try:
        # Omit repository_id entirely — should succeed (no 422)
        resp = client.post(
            f"/api/v1/repositories/{_REPO_ID}/runs",
            json={"prompt": "Create auth issues"},
        )
        assert resp.status_code == 201
    finally:
        _clear_overrides()


def test_start_issue_run_cross_user_returns_404():
    """Attempting to start a run on another user's repo must return 404."""
    from fastapi import HTTPException, status

    mock_service = AsyncMock()
    mock_service.start_issue_run = AsyncMock(
        side_effect=HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )
    )
    client = _make_client(mock_service)
    try:
        resp = client.post(
            f"/api/v1/repositories/{uuid.uuid4()}/runs",
            json={"prompt": "Create auth issues"},
        )
        assert resp.status_code == 404
    finally:
        _clear_overrides()
