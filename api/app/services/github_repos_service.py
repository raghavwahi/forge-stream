"""Service for fetching GitHub repositories via GitHub App installation tokens."""
from __future__ import annotations

import logging

from app.providers.github_app import GitHubAppProvider
from app.schemas.github_repos import GitHubRepo

logger = logging.getLogger(__name__)

_REPOS_PER_PAGE = 100


class GitHubReposService:
    """Fetches repositories accessible through a GitHub App installation."""

    def __init__(self, provider: GitHubAppProvider) -> None:
        self._provider = provider

    async def list_repos_for_installation(
        self, installation_id: int
    ) -> list[GitHubRepo]:
        """Return all repositories accessible by the given installation."""
        token = await self._provider.get_installation_token(installation_id)

        repos: list[GitHubRepo] = []
        page = 1

        while True:
            data = await self._provider.list_installation_repos(
                token, page, _REPOS_PER_PAGE
            )

            for r in data.get("repositories", []):
                repos.append(
                    GitHubRepo(
                        id=r["id"],
                        name=r["name"],
                        full_name=r["full_name"],
                        private=r.get("private", False),
                        description=r.get("description"),
                        html_url=r["html_url"],
                        default_branch=r.get("default_branch", "main"),
                        installation_id=installation_id,
                    )
                )

            if len(data.get("repositories", [])) < _REPOS_PER_PAGE:
                break
            page += 1

        logger.info(
            "Fetched %d repos for installation %d", len(repos), installation_id
        )
        return repos
