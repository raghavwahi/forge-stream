"""Tests for the work-items API endpoints and services."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.work_items import WorkItem, WorkItemType
from app.services.github_service import GitHubService

client = TestClient(app)


# ── Health check ──────────────────────────────────────────────────


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ── POST /work-items/generate ────────────────────────────────────


@patch("app.routers.work_items._work_item_service")
def test_generate_work_items(mock_service):
    mock_service.generate = AsyncMock(
        return_value=[
            WorkItem(
                type=WorkItemType.EPIC,
                title="Auth Epic",
                children=[
                    WorkItem(type=WorkItemType.STORY, title="Login page"),
                ],
            )
        ]
    )
    resp = client.post(
        "/work-items/generate",
        json={"prompt": "Build an auth system", "model": "gpt-4o-mini"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["type"] == "epic"
    assert data["items"][0]["children"][0]["type"] == "story"


# ── POST /work-items/enhance-prompt ──────────────────────────────


@patch("app.routers.work_items._work_item_service")
def test_enhance_prompt(mock_service):
    mock_service.enhance_prompt = AsyncMock(
        return_value="Build a secure OAuth 2.0 authentication system..."
    )
    resp = client.post(
        "/work-items/enhance-prompt",
        json={"prompt": "build auth"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["original_prompt"] == "build auth"
    assert "OAuth" in data["enhanced_prompt"]


# ── POST /work-items/enhance-item ────────────────────────────────


@patch("app.routers.work_items._work_item_service")
def test_enhance_work_item(mock_service):
    enhanced = WorkItem(
        type=WorkItemType.STORY,
        title="Login",
        description="Implement secure login with rate limiting",
        children=[WorkItem(type=WorkItemType.TASK, title="Add rate limiter")],
    )
    mock_service.enhance_work_item = AsyncMock(return_value=enhanced)
    resp = client.post(
        "/work-items/enhance-item",
        json={
            "work_item": {"type": "story", "title": "Login"},
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["original"]["title"] == "Login"
    assert len(data["enhanced"]["children"]) == 1


# ── POST /work-items/create-issues ───────────────────────────────


@patch("app.routers.work_items._github_service")
def test_create_issues(mock_service):
    from app.schemas.work_items import CreatedIssue

    mock_service.create_issues = AsyncMock(
        return_value=[
            CreatedIssue(
                number=1,
                title="Epic",
                url="https://github.com/owner/repo/issues/1",
                item_type=WorkItemType.EPIC,
            )
        ]
    )
    resp = client.post(
        "/work-items/create-issues",
        json={
            "github": {
                "token": "ghp_test",
                "owner": "testowner",
                "repo": "testrepo",
            },
            "items": [{"type": "epic", "title": "Epic"}],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["created"]) == 1
    assert data["created"][0]["number"] == 1


# ── GitHubService._build_body ────────────────────────────────────


class TestGitHubServiceBuildBody:
    def test_body_with_description_only(self):
        svc = GitHubService()
        item = WorkItem(
            type=WorkItemType.STORY,
            title="Story",
            description="Some description",
        )
        body = svc._build_body(item)
        assert "Some description" in body

    def test_body_with_task_list(self):
        svc = GitHubService()
        item = WorkItem(
            type=WorkItemType.EPIC,
            title="Epic",
            children=[
                WorkItem(type=WorkItemType.TASK, title="Task 1"),
                WorkItem(type=WorkItemType.TASK, title="Task 2"),
            ],
        )
        body = svc._build_body(item)
        assert "- [ ] Task 1" in body
        assert "- [ ] Task 2" in body

    def test_body_ignores_non_task_children(self):
        svc = GitHubService()
        item = WorkItem(
            type=WorkItemType.EPIC,
            title="Epic",
            children=[
                WorkItem(type=WorkItemType.STORY, title="Story child"),
            ],
        )
        body = svc._build_body(item)
        assert "Story child" not in body
