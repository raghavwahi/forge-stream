"""
GitHub App authentication and installation management.

GitHub Apps authenticate as installations using JWT tokens, enabling access
to repositories that users have granted the app permission to access.

Auth flow:
1. Generate a short-lived JWT signed with the app's private key
2. Use the JWT to enumerate installations or request installation access tokens
3. Use the installation token (valid 1 hour) to make API calls as that installation
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import re
import time
from typing import Any

import httpx
from jose import jwt as jose_jwt

from app.config import GitHubAppSettings

logger = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com"
_GITHUB_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


class GitHubAppService:
    """Service for GitHub App JWT-based authentication and installation management."""

    def __init__(self, settings: GitHubAppSettings) -> None:
        self.settings = settings

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_private_key(self) -> str:
        """Decode the base64-encoded PEM private key from settings."""
        if not self.settings.private_key:
            raise ValueError("GITHUB_APP_PRIVATE_KEY is not configured")
        raw = self.settings.private_key.strip()
        if raw.startswith("-----BEGIN"):
            # Already a PEM string
            return raw
        try:
            return base64.b64decode(raw).decode("utf-8")
        except Exception as exc:  # pragma: no cover
            raise ValueError(
                "GITHUB_APP_PRIVATE_KEY must be a base64-encoded PEM RSA private key"
            ) from exc

    def _generate_jwt(self) -> str:
        """
        Generate a JWT for authenticating as the GitHub App.
        The JWT is valid for 10 minutes; issued one minute in the past
        to account for clock skew.
        """
        if not self.settings.app_id:
            raise ValueError("GITHUB_APP_ID is not configured")
        now = int(time.time())
        payload = {
            "iat": now - 60,
            "exp": now + (10 * 60),
            "iss": self.settings.app_id,
        }
        private_key = self._get_private_key()
        return jose_jwt.encode(payload, private_key, algorithm="RS256")

    @staticmethod
    def _raise_for_status(response: httpx.Response, context: str) -> None:
        if not response.is_success:
            logger.error(
                "GitHub API error [%s]: %d %s",
                context,
                response.status_code,
                response.text[:200],
            )
            response.raise_for_status()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def list_installations(self) -> list[dict[str, Any]]:
        """List all installations for this GitHub App (paginates automatically)."""
        jwt_token = self._generate_jwt()
        installations: list[dict[str, Any]] = []
        page = 1
        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                response = await client.get(
                    f"{_GITHUB_API}/app/installations",
                    headers={
                        **_GITHUB_HEADERS,
                        "Authorization": f"Bearer {jwt_token}",
                    },
                    params={"per_page": 100, "page": page},
                )
                self._raise_for_status(response, "list_installations")
                page_items: list[dict[str, Any]] = response.json()
                if not page_items:
                    break
                installations.extend(page_items)
                link_header = response.headers.get("Link", "")
                if not re.search(r'rel\s*=\s*"next"', link_header):
                    break
                page += 1
        return installations

    async def get_installation_token(self, installation_id: int) -> dict[str, Any]:
        """
        Exchange an installation ID for an installation access token.

        Returns a dict with 'token' (str) and 'expires_at' (ISO8601 str).
        """
        jwt_token = self._generate_jwt()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{_GITHUB_API}/app/installations/{installation_id}/access_tokens",
                headers={**_GITHUB_HEADERS, "Authorization": f"Bearer {jwt_token}"},
            )
        self._raise_for_status(response, "get_installation_token")
        return response.json()

    async def get_installation_repositories(
        self, installation_token: str
    ) -> list[dict[str, Any]]:
        """List repositories accessible to an installation."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{_GITHUB_API}/installation/repositories",
                headers={
                    **_GITHUB_HEADERS,
                    "Authorization": f"Bearer {installation_token}",
                },
                params={"per_page": 100},
            )
        self._raise_for_status(response, "get_installation_repositories")
        return response.json().get("repositories", [])

    async def get_user_installation(
        self, github_username: str
    ) -> dict[str, Any] | None:
        """Find the installation for a specific GitHub user or organization."""
        installations = await self.list_installations()
        for inst in installations:
            if inst.get("account", {}).get("login") == github_username:
                return inst
        return None

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify a GitHub webhook HMAC-SHA256 signature.

        Args:
            payload: Raw request body bytes.
            signature: Value from the X-Hub-Signature-256 header
                (format: 'sha256=<hex>').
        Returns:
            True if the signature is valid, False otherwise.
        """
        if not self.settings.webhook_secret:
            logger.warning(
                "Webhook signature check skipped: "
                "GITHUB_APP_WEBHOOK_SECRET not set"
            )
            return False
        secret = self.settings.webhook_secret.encode("utf-8")
        expected = "sha256=" + hmac.new(secret, payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    @property
    def is_configured(self) -> bool:
        """Return True if the minimum required settings are present."""
        return bool(self.settings.app_id and self.settings.private_key)
