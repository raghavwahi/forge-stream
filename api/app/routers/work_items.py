"""API routes for work-item generation and GitHub issue creation."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.work_items import (
    CreateIssuesRequest,
    CreateIssuesResponse,
    EnhancePromptRequest,
    EnhancePromptResponse,
    EnhanceWorkItemRequest,
    EnhanceWorkItemResponse,
    GenerateWorkItemsRequest,
    GenerateWorkItemsResponse,
)
from app.services.github_service import GitHubService
from app.services.work_item_service import WorkItemService

router = APIRouter(prefix="/work-items", tags=["work-items"])

_work_item_service = WorkItemService()
_github_service = GitHubService()


@router.post("/generate", response_model=GenerateWorkItemsResponse)
async def generate_work_items(body: GenerateWorkItemsRequest):
    """Generate a structured work-item hierarchy from a user prompt."""
    items = await _work_item_service.generate(body.prompt, body.model)
    return GenerateWorkItemsResponse(items=items)


@router.post("/enhance-prompt", response_model=EnhancePromptResponse)
async def enhance_prompt(body: EnhancePromptRequest):
    """Enhance a rough prompt into a detailed, technical prompt."""
    enhanced = await _work_item_service.enhance_prompt(body.prompt, body.model)
    return EnhancePromptResponse(
        original_prompt=body.prompt, enhanced_prompt=enhanced
    )


@router.post("/enhance-item", response_model=EnhanceWorkItemResponse)
async def enhance_work_item(body: EnhanceWorkItemRequest):
    """Inject more technical detail into a single work item."""
    enhanced = await _work_item_service.enhance_work_item(
        body.work_item, body.model
    )
    return EnhanceWorkItemResponse(original=body.work_item, enhanced=enhanced)


@router.post("/create-issues", response_model=CreateIssuesResponse)
async def create_github_issues(body: CreateIssuesRequest):
    """Create GitHub issues from a list of structured work items."""
    created = await _github_service.create_issues(body.github, body.items)
    return CreateIssuesResponse(created=created)
