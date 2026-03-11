"""Async GitHub issue creation service using httpx (no PyGithub dependency)."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.schemas.work_items import CreatedIssue, GitHubConfig, WorkItem, WorkItemType

logger = logging.getLogger(__name__)

_LABEL_COLOURS: dict[str, str] = {
    "epic": "7B48CC",
    "story": "0075CA",
    "bug": "D73A4A",
    "task": "0E8A16",
}

_LABEL_MAP: dict[WorkItemType, str] = {
    WorkItemType.EPIC: "epic",
    WorkItemType.STORY: "story",
    WorkItemType.BUG: "bug",
    WorkItemType.TASK: "task",
}

_GH_API = "https://api.github.com"
_MAX_RETRIES = 3
_RETRY_STATUSES = {429, 500, 502, 503}


@dataclass
class _Context:
    client: httpx.AsyncClient
    owner: str
    repo: str
    label_cache: set[str] = field(default_factory=set)


class GitHubIssueService:
    """Create GitHub issues from WorkItems using the REST API over httpx.

    Supports:
    - Full recursive issue creation (epics → stories → tasks)
    - Automatic label creation with type-appropriate colours
    - Retry with back-off on transient errors (429 / 5xx)
    - Parallel sibling creation at each level of the hierarchy
    """

    # ── helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _headers(token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def _ensure_label(self, ctx: _Context, label: str) -> None:
        """Create label if not already in cache."""
        if label in ctx.label_cache:
            return
        # Use the type-specific colour for known type labels; neutral for custom ones
        colour = _LABEL_COLOURS.get(label, "ededed")
        try:
            resp = await ctx.client.post(
                f"{_GH_API}/repos/{ctx.owner}/{ctx.repo}/labels",
                json={"name": label, "color": colour},
            )
            if resp.status_code in (201, 422):  # 422 = already exists
                ctx.label_cache.add(label)
            else:
                resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning("Could not create label %s: %s", label, exc)

    async def _request_with_retry(
        self, client: httpx.AsyncClient, method: str, url: str, **kwargs: Any
    ) -> httpx.Response:
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                resp = await client.request(method, url, **kwargs)
            except httpx.RequestError as exc:
                wait = 2**attempt
                logger.warning(
                    "Request error on attempt %d/%d: %s; retrying in %ds",
                    attempt,
                    _MAX_RETRIES,
                    exc,
                    wait,
                )
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(wait)
                else:
                    raise
                continue
            if resp.status_code not in _RETRY_STATUSES:
                resp.raise_for_status()
                return resp
            wait = 2**attempt
            logger.warning(
                "GitHub API returned %d (attempt %d/%d), retrying in %ds",
                resp.status_code,
                attempt,
                _MAX_RETRIES,
                wait,
            )
            await resp.aclose()
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(wait)
        resp.raise_for_status()
        return resp  # unreachable but satisfies type checkers

    def _build_body(self, item: WorkItem) -> str:
        parts: list[str] = []
        if item.description:
            parts.append(item.description)
        tasks = [c for c in item.children if c.type == WorkItemType.TASK]
        if tasks:
            parts.append("\n### Tasks\n")
            parts.extend(f"- [ ] {t.title}" for t in tasks)
        return "\n".join(parts)

    async def _create_issue(self, ctx: _Context, item: WorkItem) -> CreatedIssue:
        type_label = _LABEL_MAP.get(item.type, "task")
        all_labels = list({type_label, *item.labels})

        # Ensure all labels exist
        await asyncio.gather(
            *[self._ensure_label(ctx, lbl) for lbl in all_labels]
        )

        resp = await self._request_with_retry(
            ctx.client,
            "POST",
            f"{_GH_API}/repos/{ctx.owner}/{ctx.repo}/issues",
            json={
                "title": item.title,
                "body": self._build_body(item),
                "labels": all_labels,
            },
        )
        data = resp.json()

        # Create non-task children in parallel
        child_results = await asyncio.gather(
            *[
                self._create_issue(ctx, child)
                for child in item.children
                if child.type != WorkItemType.TASK
            ]
        )

        return CreatedIssue(
            number=data["number"],
            title=data["title"],
            url=data["html_url"],
            item_type=item.type,
            children=list(child_results),
        )

    # ── public API ───────────────────────────────────────────────────────────

    async def create_issues(
        self,
        config: GitHubConfig,
        items: list[WorkItem],
    ) -> list[CreatedIssue]:
        """Create GitHub issues for all root-level WorkItems and their children."""
        token = config.token.get_secret_value()
        async with httpx.AsyncClient(
            headers=self._headers(token), timeout=30
        ) as client:
            ctx = _Context(client=client, owner=config.owner, repo=config.repo)

            # Fetch all existing labels (paginated) to pre-populate the cache
            url: str | None = (
                f"{_GH_API}/repos/{config.owner}/{config.repo}/labels"
            )
            params: dict[str, Any] = {"per_page": 100}
            while url:
                resp = await client.get(url, params=params)
                if not resp.is_success:
                    break
                ctx.label_cache.update(lbl["name"] for lbl in resp.json())
                url = None
                for part in resp.headers.get("Link", "").split(","):
                    if 'rel="next"' in part:
                        url = part.split(";")[0].strip().strip("<>")
                        break
                params = {}

            # Create root-level items in parallel
            results = await asyncio.gather(
                *[self._create_issue(ctx, item) for item in items]
            )

        return list(results)
