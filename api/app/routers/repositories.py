"""Router for GitHub repository management endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.dependencies import get_current_user, get_repository_service
from app.models.user import UserInDB
from app.schemas.repositories import (
    IssueRunCreate,
    IssueRunResponse,
    RepositoryCreate,
    RepositoryListResponse,
    RepositoryResponse,
)
from app.services.repository_service import RepositoryService

router = APIRouter(prefix="/repositories", tags=["repositories"])


@router.get(
    "/",
    response_model=RepositoryListResponse,
    summary="List connected repositories",
)
async def list_repositories(
    current_user: UserInDB = Depends(get_current_user),
    service: RepositoryService = Depends(get_repository_service),
) -> RepositoryListResponse:
    """Return all GitHub repositories connected by the authenticated user."""
    return await service.list_repositories(current_user.id)


@router.post(
    "/",
    response_model=RepositoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Connect a repository",
)
async def connect_repository(
    data: RepositoryCreate,
    current_user: UserInDB = Depends(get_current_user),
    service: RepositoryService = Depends(get_repository_service),
) -> RepositoryResponse:
    """Connect a GitHub repository to the user's account.

    If the repository was previously connected it will be re-enabled and
    its metadata updated.
    """
    return await service.connect_repository(current_user.id, data)


@router.get(
    "/{repo_id}",
    response_model=RepositoryResponse,
    summary="Get a repository",
)
async def get_repository(
    repo_id: UUID,
    current_user: UserInDB = Depends(get_current_user),
    service: RepositoryService = Depends(get_repository_service),
) -> RepositoryResponse:
    """Return a single repository owned by the authenticated user."""
    return await service.get_repository(current_user.id, repo_id)


@router.delete(
    "/{repo_id}",
    summary="Disconnect a repository",
)
async def disconnect_repository(
    repo_id: UUID,
    current_user: UserInDB = Depends(get_current_user),
    service: RepositoryService = Depends(get_repository_service),
) -> dict[str, str]:
    """Remove a connected repository from the user's account."""
    await service.disconnect_repository(current_user.id, repo_id)
    return {"message": "Repository disconnected"}


@router.get(
    "/{repo_id}/runs",
    response_model=list[IssueRunResponse],
    summary="List issue runs for a repository",
)
async def list_issue_runs(
    repo_id: UUID,
    current_user: UserInDB = Depends(get_current_user),
    service: RepositoryService = Depends(get_repository_service),
) -> list[IssueRunResponse]:
    """Return issue generation runs associated with the given repository."""
    return await service.get_issue_runs(current_user.id, repo_id)


@router.post(
    "/{repo_id}/runs",
    response_model=IssueRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start an issue run",
)
async def start_issue_run(
    repo_id: UUID,
    data: IssueRunCreate,
    current_user: UserInDB = Depends(get_current_user),
    service: RepositoryService = Depends(get_repository_service),
) -> IssueRunResponse:
    """Start a new issue generation run for the given repository.

    The run is created in ``pending`` status; actual issue generation
    is handled asynchronously by a background worker.
    """
    # Ensure the path parameter and body are consistent
    data.repository_id = repo_id
    return await service.start_issue_run(current_user.id, data)
