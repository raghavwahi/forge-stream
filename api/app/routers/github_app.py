"""GitHub App authentication and installation management router."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.dependencies import get_current_user, get_github_app_service
from app.models.github_app import (
    GitHubAppStatusResponse,
    InstallationInfo,
    InstallationTokenResponse,
)
from app.models.user import UserInDB
from app.services.github_app_service import GitHubAppService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/github-app", tags=["github-app"])


@router.get("/status", response_model=GitHubAppStatusResponse)
async def get_app_status(
    service: GitHubAppService = Depends(get_github_app_service),
) -> GitHubAppStatusResponse:
    """Return whether the GitHub App is configured (no auth required)."""
    if service.is_configured:
        return GitHubAppStatusResponse(
            is_configured=True,
            app_id=service.settings.app_id,
            message="GitHub App is configured and ready",
        )
    return GitHubAppStatusResponse(
        is_configured=False,
        message="GitHub App is not configured. Set GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY.",
    )


@router.get("/installations", response_model=list[InstallationInfo])
async def list_installations(
    service: GitHubAppService = Depends(get_github_app_service),
    _: UserInDB = Depends(get_current_user),
) -> list[InstallationInfo]:
    """List all GitHub App installations (requires JWT auth)."""
    if not service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub App is not configured",
        )
    try:
        raw = await service.list_installations()
    except Exception as exc:
        logger.error("Failed to list installations: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to retrieve installations from GitHub API",
        ) from exc

    return [
        InstallationInfo(
            id=inst["id"],
            account_login=inst.get("account", {}).get("login", ""),
            account_type=inst.get("account", {}).get("type", "User"),
            html_url=inst.get("html_url", ""),
            app_id=inst.get("app_id", 0),
        )
        for inst in raw
    ]


@router.get(
    "/installations/{installation_id}/token",
    response_model=InstallationTokenResponse,
)
async def get_installation_token(
    installation_id: int,
    service: GitHubAppService = Depends(get_github_app_service),
    _: UserInDB = Depends(get_current_user),
) -> InstallationTokenResponse:
    """Get a fresh installation access token (requires JWT auth)."""
    if not service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub App is not configured",
        )
    try:
        data = await service.get_installation_token(installation_id)
    except Exception as exc:
        logger.error("Failed to get installation token: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to obtain installation token from GitHub API",
        ) from exc
    return InstallationTokenResponse(
        token=data["token"],
        expires_at=data["expires_at"],
    )


@router.post("/webhooks", status_code=status.HTTP_200_OK)
async def handle_webhook(
    request: Request,
    service: GitHubAppService = Depends(get_github_app_service),
) -> dict:
    """Receive GitHub App webhook events. Validates HMAC-SHA256 signature."""
    payload = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if service.settings.webhook_secret:
        if not service.verify_webhook_signature(payload, signature):
            logger.warning("Webhook signature verification failed")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature",
            )

    event = request.headers.get("X-GitHub-Event", "unknown")
    logger.info("Received GitHub webhook event: %s", event)
    return {"received": True, "event": event}
