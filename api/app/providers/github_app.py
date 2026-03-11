"""Provider for GitHub App installation token and repository API calls."""

from __future__ import annotations

import logging
import time

import httpx
from jose import jwt

logger = logging.getLogger(__name__)

_GITHUB_API_BASE = "https://api.github.com"
# GitHub App JWTs must expire within 10 minutes; 60 s is comfortably short.
_JWT_EXPIRY_SECONDS = 60
_GITHUB_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


class GitHubAppProvider:
    """Handles raw GitHub App API calls: JWT auth, installation tokens,
    and repository listing."""

    def __init__(self, app_id: str, private_key: str) -> None:
        self._app_id = app_id
        self._private_key = private_key

    @property
    def is_configured(self) -> bool:
        return bool(self._app_id and self._private_key)

    def _generate_jwt(self) -> str:
        """Generate a short-lived RS256 JWT for GitHub App authentication."""
        now = int(time.time())
        claims = {
            "iat": now - 60,  # backdate iat to tolerate server clock drift
            "exp": now + _JWT_EXPIRY_SECONDS,
            "iss": self._app_id,
        }
        return jwt.encode(claims, self._private_key, algorithm="RS256")

    async def get_installation_token(self, installation_id: int) -> str:
        """Exchange an installation ID for a short-lived access token."""
        app_jwt = self._generate_jwt()
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{_GITHUB_API_BASE}/app/installations"
                f"/{installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    **_GITHUB_HEADERS,
                },
            )
            resp.raise_for_status()
            return resp.json()["token"]

    async def list_installation_repos(
        self, token: str, page: int, per_page: int
    ) -> dict:
        """Return raw repository page data for the given installation token."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{_GITHUB_API_BASE}/installation/repositories",
                headers={
                    "Authorization": f"Bearer {token}",
                    **_GITHUB_HEADERS,
                },
                params={"per_page": per_page, "page": page},
            )
            resp.raise_for_status()
            return resp.json()
