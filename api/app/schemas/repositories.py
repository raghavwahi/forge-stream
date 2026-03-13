"""Pydantic schemas for repository management endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RepositoryBase(BaseModel):
    owner: str
    name: str
    full_name: str
    description: str | None = None
    is_private: bool = False
    default_branch: str = "main"
    html_url: str


class RepositoryCreate(RepositoryBase):
    github_repo_id: int


class RepositoryResponse(RepositoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    github_repo_id: int
    is_connected: bool
    connected_at: datetime
    last_synced_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class RepositoryListResponse(BaseModel):
    repositories: list[RepositoryResponse]
    total: int


class IssueRunCreate(BaseModel):
    repository_id: UUID
    prompt: str
    model: str | None = None


class IssueRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    repository_id: UUID
    user_id: UUID
    prompt: str
    model: str | None = None
    status: str
    total_issues: int | None = None
    created_issues: int
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
