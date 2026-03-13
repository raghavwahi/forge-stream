"""Pydantic schemas for analytics / usage-tracking endpoints."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class UsageEventCreate(BaseModel):
    """Payload used to record a new usage event."""

    model_config = ConfigDict(populate_by_name=True)

    user_id: uuid.UUID | None = None
    event_type: str = Field(..., max_length=100)
    provider: str | None = Field(default=None, max_length=50)
    model: str | None = Field(default=None, max_length=100)
    tokens_used: int | None = None
    latency_ms: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class UsageEventResponse(BaseModel):
    """Full representation of a recorded usage event."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None
    event_type: str
    provider: str | None
    model: str | None
    tokens_used: int | None
    latency_ms: int | None
    metadata: dict[str, Any]
    created_at: datetime


class DailyStatResponse(BaseModel):
    """Aggregated usage statistics for a single calendar day."""

    model_config = ConfigDict(from_attributes=True)

    date: date
    total_events: int
    total_tokens: int
    events_by_type: dict[str, Any]


class AnalyticsSummaryResponse(BaseModel):
    """High-level analytics summary for a user over a date range."""

    model_config = ConfigDict(from_attributes=True)

    total_events: int
    total_tokens: int
    events_by_type: dict[str, Any]
    recent_events: list[UsageEventResponse]
    daily_stats: list[DailyStatResponse]


class AnalyticsQueryParams(BaseModel):
    """Optional filters that apply to analytics query endpoints."""

    model_config = ConfigDict(populate_by_name=True)

    start_date: date | None = None
    end_date: date | None = None
    event_type: str | None = None
    limit: int = Field(default=50, ge=1, le=500)
