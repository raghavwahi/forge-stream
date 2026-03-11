"""Unit tests for GitHubIssueService."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.schemas.work_items import GitHubConfig, WorkItem, WorkItemType
from app.services.github_issue_service import _LABEL_COLOURS, GitHubIssueService

_CONFIG = GitHubConfig(token="fake-token", owner="owner", repo="repo")


# ── Mock transport helpers ────────────────────────────────────────────────────


class _MockTransport(httpx.AsyncBaseTransport):
    """Lightweight async transport that delegates to a synchronous handler."""

    def __init__(self, handler):
        self._handler = handler
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self._handler(request)


def _default_handler(
    request: httpx.Request,
    *,
    issue_number: int = 1,
) -> httpx.Response:
    """Return sensible defaults: empty label list, successful label/issue creates."""
    path = request.url.path
    method = request.method
    if method == "GET" and "/labels" in path:
        return httpx.Response(
            200, json=[], headers={"Content-Type": "application/json"}
        )
    if method == "POST" and "/labels" in path:
        body = json.loads(request.content)
        return httpx.Response(201, json={"name": body.get("name", "")})
    if method == "POST" and "/issues" in path:
        body = json.loads(request.content)
        return httpx.Response(
            201,
            json={
                "number": issue_number,
                "title": body.get("title", ""),
                "html_url": f"https://github.com/owner/repo/issues/{issue_number}",
            },
        )
    return httpx.Response(404, json={"message": "not found"})


def _patch_client(transport: _MockTransport):
    """Patcher that injects *transport* into every httpx.AsyncClient created."""
    original = httpx.AsyncClient

    def factory(**kwargs):
        return original(transport=transport, **kwargs)

    return patch("app.services.github_issue_service.httpx.AsyncClient", factory)


# ── Basic issue creation ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_issues_returns_created_issues():
    """Root-level items are created as GitHub issues with correct metadata."""
    transport = _MockTransport(_default_handler)
    with _patch_client(transport):
        svc = GitHubIssueService()
        result = await svc.create_issues(
            _CONFIG,
            [WorkItem(type=WorkItemType.EPIC, title="Test Epic")],
        )
    assert len(result) == 1
    assert result[0].number == 1
    assert result[0].title == "Test Epic"
    assert result[0].url == "https://github.com/owner/repo/issues/1"


# ── TASK vs non-TASK children ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_task_children_appear_in_body_not_as_separate_issues():
    """TASK children are embedded in the parent body, not created as issues."""
    transport = _MockTransport(_default_handler)
    with _patch_client(transport):
        svc = GitHubIssueService()
        await svc.create_issues(
            _CONFIG,
            [
                WorkItem(
                    type=WorkItemType.STORY,
                    title="Story",
                    children=[WorkItem(type=WorkItemType.TASK, title="My task")],
                )
            ],
        )
    issue_posts = [
        r for r in transport.requests if "/issues" in r.url.path and r.method == "POST"
    ]
    assert len(issue_posts) == 1
    body = json.loads(issue_posts[0].content)
    assert "- [ ] My task" in body["body"]


@pytest.mark.asyncio
async def test_non_task_children_created_as_separate_issues():
    """Non-TASK children are recursively created as separate GitHub issues."""
    issue_num = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and "/issues" in request.url.path:
            issue_num["n"] += 1
            body = json.loads(request.content)
            return httpx.Response(
                201,
                json={
                    "number": issue_num["n"],
                    "title": body["title"],
                    "html_url": f"https://github.com/owner/repo/issues/{issue_num['n']}",
                },
            )
        return _default_handler(request)

    transport = _MockTransport(handler)
    with _patch_client(transport):
        svc = GitHubIssueService()
        result = await svc.create_issues(
            _CONFIG,
            [
                WorkItem(
                    type=WorkItemType.EPIC,
                    title="Epic",
                    children=[WorkItem(type=WorkItemType.STORY, title="Story")],
                )
            ],
        )
    assert len(result) == 1
    assert len(result[0].children) == 1
    issue_posts = [
        r for r in transport.requests if "/issues" in r.url.path and r.method == "POST"
    ]
    assert len(issue_posts) == 2  # epic + story


# ── Label colour logic ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_type_labels_use_type_specific_colour():
    """Known type labels (epic/story/bug/task) are created with their own colour."""
    transport = _MockTransport(_default_handler)
    with _patch_client(transport):
        svc = GitHubIssueService()
        await svc.create_issues(
            _CONFIG,
            [WorkItem(type=WorkItemType.BUG, title="Bug title")],
        )
    label_posts = [
        r for r in transport.requests if "/labels" in r.url.path and r.method == "POST"
    ]
    assert label_posts, "Expected at least one label create request"
    bug_create = next(
        (r for r in label_posts if json.loads(r.content)["name"] == "bug"), None
    )
    assert bug_create is not None
    assert json.loads(bug_create.content)["color"] == _LABEL_COLOURS["bug"]


@pytest.mark.asyncio
async def test_custom_labels_use_neutral_default_colour():
    """Custom labels not in the type map are created with neutral colour 'ededed'."""
    transport = _MockTransport(_default_handler)
    with _patch_client(transport):
        svc = GitHubIssueService()
        await svc.create_issues(
            _CONFIG,
            [WorkItem(type=WorkItemType.STORY, title="S", labels=["custom-label"])],
        )
    label_posts = [
        r for r in transport.requests if "/labels" in r.url.path and r.method == "POST"
    ]
    custom = next(
        (
            r
            for r in label_posts
            if json.loads(r.content)["name"] == "custom-label"
        ),
        None,
    )
    assert custom is not None
    assert json.loads(custom.content)["color"] == "ededed"


# ── Label cache ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_existing_labels_preloaded_skip_create():
    """Labels already present in the repo are not re-created."""
    label_posts: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and "/labels" in request.url.path:
            return httpx.Response(200, json=[{"name": "story"}])
        if request.method == "POST" and "/labels" in request.url.path:
            label_posts.append(request)
        return _default_handler(request)

    transport = _MockTransport(handler)
    with _patch_client(transport):
        svc = GitHubIssueService()
        await svc.create_issues(
            _CONFIG,
            [WorkItem(type=WorkItemType.STORY, title="Story")],
        )
    assert not label_posts, "Should not POST to create a label that already exists"


@pytest.mark.asyncio
async def test_label_cache_only_updated_on_success_or_already_exists():
    """Label cache is not updated when the create call fails (e.g. 500)."""
    label_attempt = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and "/labels" in request.url.path:
            label_attempt["n"] += 1
            # First call fails; second call (same label, not cached) succeeds
            if label_attempt["n"] == 1:
                return httpx.Response(500, json={"message": "server error"})
            return httpx.Response(201, json={"name": "story"})
        return _default_handler(request)

    transport = _MockTransport(handler)
    with _patch_client(transport):
        svc = GitHubIssueService()
        # Two items with the same type label; the second should retry the create
        await svc.create_issues(
            _CONFIG,
            [
                WorkItem(type=WorkItemType.STORY, title="Story 1"),
                WorkItem(type=WorkItemType.STORY, title="Story 2"),
            ],
        )
    # "story" label was not cached after the 500 failure, so a second attempt occurs
    assert label_attempt["n"] >= 2


# ── Retry behaviour ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_retry_on_429_succeeds_on_next_attempt():
    """Service retries after a 429 and succeeds on the subsequent attempt."""
    issue_attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and "/issues" in request.url.path:
            issue_attempts["n"] += 1
            if issue_attempts["n"] == 1:
                return httpx.Response(429, json={"message": "rate limited"})
            body = json.loads(request.content)
            return httpx.Response(
                201,
                json={
                    "number": 2,
                    "title": body["title"],
                    "html_url": "https://github.com/owner/repo/issues/2",
                },
            )
        return _default_handler(request)

    transport = _MockTransport(handler)
    with (
        patch("asyncio.sleep", new_callable=AsyncMock),
        _patch_client(transport),
    ):
        svc = GitHubIssueService()
        result = await svc.create_issues(
            _CONFIG,
            [WorkItem(type=WorkItemType.STORY, title="Story")],
        )
    assert result[0].number == 2
    assert issue_attempts["n"] == 2


@pytest.mark.asyncio
async def test_network_error_propagates_after_max_retries():
    """A persistent network error is re-raised after exhausting all retries."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and "/issues" in request.url.path:
            raise httpx.ConnectError("connection refused")
        return _default_handler(request)

    transport = _MockTransport(handler)
    with (
        patch("asyncio.sleep", new_callable=AsyncMock),
        _patch_client(transport),
    ):
        svc = GitHubIssueService()
        with pytest.raises(httpx.ConnectError):
            await svc.create_issues(
                _CONFIG,
                [WorkItem(type=WorkItemType.STORY, title="Story")],
            )
