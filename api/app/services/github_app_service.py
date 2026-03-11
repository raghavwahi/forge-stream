"""Service for GitHub App installation token operations."""

from __future__ import annotations

from app.providers.github_app import GitHubAppProvider


class GitHubAppService:
    """Thin service wrapping GitHubAppProvider for installation token ops."""

    def __init__(self, provider: GitHubAppProvider) -> None:
        self.provider = provider

    @property
    def is_configured(self) -> bool:
        return self.provider.is_configured

    async def get_installation_token(self, installation_id: int) -> str:
        """Return a short-lived installation access token (typed str)."""
        return await self.provider.get_installation_token(installation_id)
