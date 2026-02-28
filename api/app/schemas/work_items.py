"""Schemas for structured work-item generation."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class WorkItemType(str, Enum):
    """Supported work-item types."""

    EPIC = "epic"
    STORY = "story"
    BUG = "bug"
    TASK = "task"


class WorkItem(BaseModel):
    """A single work item in the hierarchy."""

    type: WorkItemType = Field(description="The type of work item")
    title: str = Field(description="Short title for the work item")
    description: str = Field(
        default="", description="Detailed description or acceptance criteria"
    )
    labels: list[str] = Field(
        default_factory=list, description="GitHub labels to apply"
    )
    children: list[WorkItem] = Field(
        default_factory=list, description="Nested child work items"
    )


class WorkItemHierarchy(BaseModel):
    """Top-level response containing a list of work items."""

    items: list[WorkItem] = Field(description="Root-level work items")


# --------------- Request / Response models ---------------


class GenerateWorkItemsRequest(BaseModel):
    """Request body for generating work items from a prompt."""

    prompt: str = Field(description="User prompt describing the feature or project")
    model: str = Field(
        default="gpt-4o-mini",
        description="LLM model identifier to use",
    )


class GenerateWorkItemsResponse(BaseModel):
    """Response containing the generated work-item hierarchy."""

    items: list[WorkItem]


class EnhancePromptRequest(BaseModel):
    """Request body for enhancing a user prompt."""

    prompt: str = Field(description="Original user prompt to enhance")
    model: str = Field(default="gpt-4o-mini", description="LLM model identifier")


class EnhancePromptResponse(BaseModel):
    """Response with the enhanced prompt."""

    original_prompt: str
    enhanced_prompt: str


class EnhanceWorkItemRequest(BaseModel):
    """Request body for enhancing a single work item."""

    work_item: WorkItem = Field(description="The work item to enhance")
    model: str = Field(default="gpt-4o-mini", description="LLM model identifier")


class EnhanceWorkItemResponse(BaseModel):
    """Response with the enhanced work item."""

    original: WorkItem
    enhanced: WorkItem


# --------------- GitHub creation models ---------------


class GitHubConfig(BaseModel):
    """Configuration for GitHub API access."""

    token: str = Field(description="GitHub personal access token")
    owner: str = Field(description="Repository owner (user or org)")
    repo: str = Field(description="Repository name")


class CreateIssuesRequest(BaseModel):
    """Request to create GitHub issues from work items."""

    github: GitHubConfig
    items: list[WorkItem]


class CreatedIssue(BaseModel):
    """Represents a GitHub issue that was created."""

    number: int
    title: str
    url: str
    item_type: WorkItemType
    children: list[CreatedIssue] = Field(default_factory=list)


class CreateIssuesResponse(BaseModel):
    """Response after creating GitHub issues."""

    created: list[CreatedIssue]
