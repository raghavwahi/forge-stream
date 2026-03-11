"""Service for fetching GitHub repositories via GitHub App installation tokens."""
from __future__ import annotations

import logging

import httpx

from app.schemas.github_repos import GitHubRepo
from app.services.github_app_service import GitHubAppService

logger = logging.getLogger(__name__)

_REPOS_PER_PAGE = 100


class GitHubReposService:
    """Fetches repositories accessible through a GitHub App installation."""

    def __init__(self, app_service: GitHubAppService) -> None:
        self._app = app_service

    async def list_repos_for_installation(
        self, installation_id: int
    ) -> list[GitHubRepo]:
        """Return all repositories accessible by the given installation."""
        token_data = await self._app.get_installation_token(installation_id)
        token = token_data["token"]

        repos: list[GitHubRepo] = []
        page = 1

        async with httpx.AsyncClient(timeout=15) as client:
            while True:
                resp = await client.get(
                    "https://api.github.com/installation/repositories",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    params={"per_page": _REPOS_PER_PAGE, "page": page},
                )
                resp.raise_for_status()
                data = resp.json()

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
