"""Repository layer for GitHub repository management."""

from __future__ import annotations

from uuid import UUID

from app.repositories.base import BaseRepository
from app.schemas.repositories import (
    IssueRunResponse,
    RepositoryCreate,
    RepositoryResponse,
)


class RepositoryRepository(BaseRepository):
    """Handles all database operations for github_repositories and
    repository_issue_runs tables."""

    async def create(
        self, user_id: UUID, data: RepositoryCreate
    ) -> RepositoryResponse:
        """Insert a new repository record and return it."""
        row = await self._db.fetch_one(
            """
            INSERT INTO github_repositories (
                user_id, github_repo_id, owner, name, full_name,
                description, is_private, default_branch, html_url
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (user_id, github_repo_id)
            DO UPDATE SET
                owner          = EXCLUDED.owner,
                name           = EXCLUDED.name,
                full_name      = EXCLUDED.full_name,
                description    = EXCLUDED.description,
                is_private     = EXCLUDED.is_private,
                default_branch = EXCLUDED.default_branch,
                html_url       = EXCLUDED.html_url,
                is_connected   = true,
                updated_at     = NOW()
            RETURNING
                id, user_id, github_repo_id, owner, name, full_name,
                description, is_private, default_branch, html_url,
                is_connected, connected_at, last_synced_at,
                created_at, updated_at
            """,
            user_id,
            data.github_repo_id,
            data.owner,
            data.name,
            data.full_name,
            data.description,
            data.is_private,
            data.default_branch,
            data.html_url,
        )
        return RepositoryResponse(**row)

    async def find_by_id(self, repo_id: UUID) -> RepositoryResponse | None:
        """Fetch a single repository by its primary key."""
        row = await self._db.fetch_one(
            """
            SELECT
                id, user_id, github_repo_id, owner, name, full_name,
                description, is_private, default_branch, html_url,
                is_connected, connected_at, last_synced_at,
                created_at, updated_at
            FROM github_repositories
            WHERE id = $1
            """,
            repo_id,
        )
        return RepositoryResponse(**row) if row else None

    async def find_by_user_id(
        self, user_id: UUID, include_disconnected: bool = False
    ) -> list[RepositoryResponse]:
        """Return all repositories belonging to a user.

        By default only connected repositories are returned.
        Pass ``include_disconnected=True`` to include disconnected ones.
        """
        if include_disconnected:
            rows = await self._db.fetch_all(
                """
                SELECT
                    id, user_id, github_repo_id, owner, name, full_name,
                    description, is_private, default_branch, html_url,
                    is_connected, connected_at, last_synced_at,
                    created_at, updated_at
                FROM github_repositories
                WHERE user_id = $1
                ORDER BY created_at DESC
                """,
                user_id,
            )
        else:
            rows = await self._db.fetch_all(
                """
                SELECT
                    id, user_id, github_repo_id, owner, name, full_name,
                    description, is_private, default_branch, html_url,
                    is_connected, connected_at, last_synced_at,
                    created_at, updated_at
                FROM github_repositories
                WHERE user_id = $1
                  AND is_connected = true
                ORDER BY created_at DESC
                """,
                user_id,
            )
        return [RepositoryResponse(**r) for r in rows]

    async def find_by_github_id(
        self, user_id: UUID, github_repo_id: int
    ) -> RepositoryResponse | None:
        """Find a repository by its GitHub numeric ID scoped to a user."""
        row = await self._db.fetch_one(
            """
            SELECT
                id, user_id, github_repo_id, owner, name, full_name,
                description, is_private, default_branch, html_url,
                is_connected, connected_at, last_synced_at,
                created_at, updated_at
            FROM github_repositories
            WHERE user_id = $1
              AND github_repo_id = $2
            """,
            user_id,
            github_repo_id,
        )
        return RepositoryResponse(**row) if row else None

    async def update_connected(
        self, repo_id: UUID, is_connected: bool
    ) -> RepositoryResponse | None:
        """Flip the is_connected flag on a repository."""
        row = await self._db.fetch_one(
            """
            UPDATE github_repositories
            SET is_connected = $2, updated_at = NOW()
            WHERE id = $1
            RETURNING
                id, user_id, github_repo_id, owner, name, full_name,
                description, is_private, default_branch, html_url,
                is_connected, connected_at, last_synced_at,
                created_at, updated_at
            """,
            repo_id,
            is_connected,
        )
        return RepositoryResponse(**row) if row else None

    async def update_last_synced(self, repo_id: UUID) -> None:
        """Stamp last_synced_at with the current timestamp."""
        await self._db.execute(
            """
            UPDATE github_repositories
            SET last_synced_at = NOW(), updated_at = NOW()
            WHERE id = $1
            """,
            repo_id,
        )

    async def delete(self, repo_id: UUID, user_id: UUID) -> bool:
        """Hard-delete a repository row owned by the given user.

        Returns True if a row was actually removed.
        """
        result = await self._db.execute(
            """
            DELETE FROM github_repositories
            WHERE id = $1 AND user_id = $2
            """,
            repo_id,
            user_id,
        )
        # asyncpg returns 'DELETE N' where N is row count
        deleted_count = int(result.split()[-1])
        return deleted_count > 0

    # ------------------------------------------------------------------
    # Issue run operations
    # ------------------------------------------------------------------

    async def create_issue_run(self, data: dict) -> IssueRunResponse:
        """Insert a new issue run record."""
        row = await self._db.fetch_one(
            """
            INSERT INTO repository_issue_runs (
                repository_id, user_id, prompt, model, status
            )
            VALUES ($1, $2, $3, $4, $5)
            RETURNING
                id, repository_id, user_id, prompt, model,
                status, total_issues, created_issues, error_message,
                started_at, completed_at, created_at
            """,
            data["repository_id"],
            data["user_id"],
            data["prompt"],
            data.get("model"),
            data.get("status", "pending"),
        )
        return IssueRunResponse(**row)

    async def update_issue_run_status(
        self, run_id: UUID, status: str, **kwargs
    ) -> None:
        """Update the status of an issue run, plus any extra fields.

        Supported kwargs: total_issues, created_issues, error_message,
        started_at, completed_at, work_item_snapshot.
        """
        # Build the SET clause dynamically from allowed fields
        allowed_fields = {
            "total_issues",
            "created_issues",
            "error_message",
            "started_at",
            "completed_at",
            "work_item_snapshot",
        }
        extra = {k: v for k, v in kwargs.items() if k in allowed_fields}

        set_parts = ["status = $2"]
        values: list = [run_id, status]
        for field, value in extra.items():
            set_parts.append(f"{field} = ${len(values) + 1}")
            values.append(value)

        await self._db.execute(
            f"UPDATE repository_issue_runs SET {', '.join(set_parts)} WHERE id = $1",
            *values,
        )

    async def get_issue_runs(
        self, repository_id: UUID, limit: int = 20
    ) -> list[IssueRunResponse]:
        """Return the most recent issue runs for a repository."""
        rows = await self._db.fetch_all(
            """
            SELECT
                id, repository_id, user_id, prompt, model,
                status, total_issues, created_issues, error_message,
                started_at, completed_at, created_at
            FROM repository_issue_runs
            WHERE repository_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            repository_id,
            limit,
        )
        return [IssueRunResponse(**r) for r in rows]
