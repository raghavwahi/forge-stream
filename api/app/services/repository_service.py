"""Service layer for GitHub repository management."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status

from app.repositories.repository import RepositoryRepository
from app.schemas.repositories import (
    IssueRunCreate,
    IssueRunResponse,
    RepositoryCreate,
    RepositoryListResponse,
    RepositoryResponse,
)


class RepositoryService:
    """Orchestrates repository and issue-run business logic.

    The service validates ownership before any mutation or retrieval,
    ensuring users can only access their own repositories.
    """

    def __init__(self, repo: RepositoryRepository) -> None:
        self._repo = repo

    async def connect_repository(
        self, user_id: UUID, data: RepositoryCreate
    ) -> RepositoryResponse:
        """Connect (or reconnect) a GitHub repository for the user.

        If the repository was previously connected by the same user it
        is updated in-place; otherwise a new record is inserted.
        """
        return await self._repo.create(user_id, data)

    async def disconnect_repository(
        self, user_id: UUID, repo_id: UUID
    ) -> bool:
        """Mark a repository as disconnected (soft-delete via is_connected flag).

        Raises 404 when the repository does not exist or does not belong
        to the requesting user.  Returns True on success.  Run history is
        preserved because the row is not deleted.
        """
        existing = await self._get_owned_repo(user_id, repo_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found",
            )
        updated = await self._repo.update_connected(repo_id, False)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found",
            )
        return True

    async def list_repositories(
        self, user_id: UUID
    ) -> RepositoryListResponse:
        """Return all connected repositories owned by the user."""
        repositories = await self._repo.find_by_user_id(user_id)
        return RepositoryListResponse(
            repositories=repositories, total=len(repositories)
        )

    async def get_repository(
        self, user_id: UUID, repo_id: UUID
    ) -> RepositoryResponse:
        """Return a single repository, verifying user ownership.

        Raises 404 when the repository is not found or belongs to
        a different user.
        """
        repo = await self._get_owned_repo(user_id, repo_id)
        if repo is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found",
            )
        return repo

    async def start_issue_run(
        self, user_id: UUID, data: IssueRunCreate
    ) -> IssueRunResponse:
        """Create a pending issue-run record for the given repository.

        Validates that the repository exists and is owned by the user
        before inserting the run.
        """
        repo = await self._get_owned_repo(user_id, data.repository_id)
        if repo is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found",
            )
        if not repo.is_connected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Repository is not connected",
            )
        run_data = {
            "repository_id": data.repository_id,
            "user_id": user_id,
            "prompt": data.prompt,
            "model": data.model,
            "status": "pending",
        }
        return await self._repo.create_issue_run(run_data)

    async def get_issue_runs(
        self, user_id: UUID, repo_id: UUID
    ) -> list[IssueRunResponse]:
        """Return issue runs for a repository, verifying user ownership."""
        repo = await self._get_owned_repo(user_id, repo_id)
        if repo is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found",
            )
        return await self._repo.get_issue_runs(repo_id)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _get_owned_repo(
        self, user_id: UUID, repo_id: UUID
    ) -> RepositoryResponse | None:
        """Fetch a repository and verify it belongs to the given user.

        Returns None when the repository does not exist or belongs to
        a different user, ensuring no information leakage.
        """
        repo = await self._repo.find_by_id(repo_id)
        if repo is None or repo.user_id != user_id:
            return None
        return repo
