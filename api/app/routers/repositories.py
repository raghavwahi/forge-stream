"""Router for GitHub repository listing."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import get_current_user, get_github_app_service
from app.models.user import UserInDB
from app.schemas.github_repos import GitHubRepo, ListReposResponse
from app.services.github_app_service import GitHubAppService
from app.services.github_repos_service import GitHubReposService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/repositories", tags=["repositories"])


def _get_repos_service(
    app_service: GitHubAppService = Depends(get_github_app_service),
) -> GitHubReposService:
    if not app_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub App is not configured",
        )
    return GitHubReposService(app_service.provider)


async def _fetch_repos(
    installation_id: int,
    service: GitHubReposService,
) -> list[GitHubRepo]:
    """Fetch repos and map upstream errors to HTTP 502."""
    try:
        return await service.list_repos_for_installation(installation_id)
    except Exception as exc:
        logger.error("Failed to fetch repositories: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch repositories from GitHub",
        ) from exc


@router.get("", response_model=ListReposResponse)
async def list_repositories(
    installation_id: int = Query(..., description="GitHub App installation ID"),
    service: GitHubReposService = Depends(_get_repos_service),
    _: UserInDB = Depends(get_current_user),
) -> ListReposResponse:
    """List all repositories accessible by the given GitHub App installation."""
    repos = await _fetch_repos(installation_id, service)
    return ListReposResponse(repos=repos, total=len(repos))


@router.get("/search", response_model=ListReposResponse)
async def search_repositories(
    installation_id: int = Query(..., description="GitHub App installation ID"),
    q: str = Query("", description="Filter repos by name (case-insensitive)"),
    service: GitHubReposService = Depends(_get_repos_service),
    _: UserInDB = Depends(get_current_user),
) -> ListReposResponse:
    """List repositories, optionally filtered by name substring."""
    repos = await _fetch_repos(installation_id, service)
    if q:
        repos = [r for r in repos if q.lower() in r.name.lower()]
    return ListReposResponse(repos=repos, total=len(repos))
