"""Job type definitions and Pydantic schemas for the background job queue."""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class JobType(str, Enum):
    CREATE_ISSUES = "create_issues"
    ENHANCE_ITEMS = "enhance_items"
    GENERATE_ITEMS = "generate_items"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class Job(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: JobType
    payload: dict[str, Any] = Field(default_factory=dict)
    status: JobStatus = JobStatus.PENDING
    created_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )
    error: str | None = None
    result: dict[str, Any] | None = None


class EnqueueJobRequest(BaseModel):
    type: JobType
    payload: dict[str, Any] = Field(default_factory=dict)


class JobStatusResponse(BaseModel):
    id: str
    type: JobType
    status: JobStatus
    error: str | None = None
    result: dict[str, Any] | None = None
    created_at: str
