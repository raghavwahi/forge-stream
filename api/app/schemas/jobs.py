"""Job-type definitions for the async worker queue."""

from __future__ import annotations

from enum import Enum


class JobType(str, Enum):
    """Supported background-worker job types."""

    GENERATE_WORK_ITEMS = "generate_work_items"
    ENHANCE_PROMPT = "enhance_prompt"
    ENHANCE_WORK_ITEM = "enhance_work_item"
    CREATE_GITHUB_ISSUES = "create_github_issues"
