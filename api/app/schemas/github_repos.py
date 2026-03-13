"""Pydantic schemas for GitHub repository listing."""
from __future__ import annotations

from pydantic import BaseModel, Field


class GitHubRepo(BaseModel):
    id: int = Field(description="GitHub repository ID")
    name: str = Field(description="Repository name (short, without owner)")
    full_name: str = Field(description="owner/repo")
    private: bool = False
    description: str | None = None
    html_url: str
    default_branch: str = "main"
    installation_id: int = Field(description="GitHub App installation that owns this repo")


class ListReposResponse(BaseModel):
    repos: list[GitHubRepo]
    total: int
