"""GitHub service for creating issues from structured work items."""

from __future__ import annotations

import asyncio

from github import Github
from github.Repository import Repository as GithubRepo

from app.schemas.work_items import (
    CreatedIssue,
    GitHubConfig,
    WorkItem,
    WorkItemType,
)

_LABEL_MAP: dict[WorkItemType, str] = {
    WorkItemType.EPIC: "epic",
    WorkItemType.STORY: "story",
    WorkItemType.BUG: "bug",
    WorkItemType.TASK: "task",
}


class GitHubService:
    """Create GitHub issues (epics, stories, bugs) with nested task lists."""

    def _get_repo(self, config: GitHubConfig) -> GithubRepo:
        """Authenticate and return the target repository."""
        client = Github(config.token.get_secret_value())
        return client.get_repo(f"{config.owner}/{config.repo}")

    def _ensure_labels(
        self,
        repo: GithubRepo,
        labels: list[str],
        cache: set[str],
    ) -> None:
        """Create missing labels in the repository using a shared cache."""
        for label in labels:
            if label not in cache:
                repo.create_label(name=label, color="ededed")
                cache.add(label)

    def _build_body(self, item: WorkItem) -> str:
        """Build the issue body including a nested task-list for children."""
        parts: list[str] = []
        if item.description:
            parts.append(item.description)

        child_tasks = [
            child for child in item.children if child.type == WorkItemType.TASK
        ]
        if child_tasks:
            parts.append("\n### Tasks\n")
            for task in child_tasks:
                parts.append(f"- [ ] {task.title}")

        return "\n".join(parts)

    def _create_issue_recursive(
        self,
        repo: GithubRepo,
        item: WorkItem,
        label_cache: set[str],
    ) -> CreatedIssue:
        """Recursively create an issue and its non-task children."""
        type_label = _LABEL_MAP.get(item.type, "task")
        all_labels = list({type_label, *item.labels})

        self._ensure_labels(repo, all_labels, label_cache)

        body = self._build_body(item)
        issue = repo.create_issue(
            title=item.title,
            body=body,
            labels=all_labels,
        )

        created_children: list[CreatedIssue] = []
        for child in item.children:
            if child.type != WorkItemType.TASK:
                created_children.append(
                    self._create_issue_recursive(repo, child, label_cache)
                )

        return CreatedIssue(
            number=issue.number,
            title=issue.title,
            url=issue.html_url,
            item_type=item.type,
            children=created_children,
        )

    async def create_issues(
        self, config: GitHubConfig, items: list[WorkItem]
    ) -> list[CreatedIssue]:
        """Create GitHub issues for all root-level work items."""
        return await asyncio.to_thread(self._create_all, config, items)

    def _create_all(
        self, config: GitHubConfig, items: list[WorkItem]
    ) -> list[CreatedIssue]:
        """Synchronous helper executed in a thread pool."""
        repo = self._get_repo(config)
        label_cache = {lbl.name for lbl in repo.get_labels()}
        results: list[CreatedIssue] = []
        for item in items:
            results.append(
                self._create_issue_recursive(repo, item, label_cache)
            )
        return results
