"""Analytics API router – usage tracking endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, status

from app.dependencies import get_analytics_service, get_current_user
from app.models.user import UserInDB
from app.schemas.analytics import (
    AnalyticsQueryParams,
    AnalyticsSummaryResponse,
    DailyStatResponse,
    UsageEventCreate,
    UsageEventResponse,
)
from app.services.analytics import AnalyticsService

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get(
    "/summary",
    response_model=AnalyticsSummaryResponse,
    summary="Get analytics summary for the authenticated user",
)
async def get_summary(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    event_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    current_user: UserInDB = Depends(get_current_user),
    service: AnalyticsService = Depends(get_analytics_service),
) -> AnalyticsSummaryResponse:
    """
    Returns total event counts, token usage, per-type breakdowns,
    recent events, and daily stats for the authenticated user.
    Results are served from Redis when available (5-minute TTL).
    """
    params = AnalyticsQueryParams(
        start_date=start_date,
        end_date=end_date,
        event_type=event_type,
        limit=limit,
    )
    return await service.get_cached_summary(current_user.id, params)


@router.get(
    "/events",
    response_model=list[UsageEventResponse],
    summary="List recent usage events for the authenticated user",
)
async def list_events(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    event_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    current_user: UserInDB = Depends(get_current_user),
    service: AnalyticsService = Depends(get_analytics_service),
) -> list[UsageEventResponse]:
    """
    Returns a list of individual usage events ordered by most recent first.
    Filtered by the authenticated user's identity.
    """
    params = AnalyticsQueryParams(
        start_date=start_date,
        end_date=end_date,
        event_type=event_type,
        limit=limit,
    )
    summary = await service.get_user_summary(current_user.id, params)
    return summary.recent_events


@router.get(
    "/daily",
    response_model=list[DailyStatResponse],
    summary="List daily aggregated stats for the authenticated user",
)
async def list_daily_stats(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    current_user: UserInDB = Depends(get_current_user),
    service: AnalyticsService = Depends(get_analytics_service),
) -> list[DailyStatResponse]:
    """
    Returns per-day aggregated event counts and token totals
    for the authenticated user within the requested date range.
    """
    params = AnalyticsQueryParams(
        start_date=start_date,
        end_date=end_date,
    )
    summary = await service.get_user_summary(current_user.id, params)
    return summary.daily_stats


@router.post(
    "/events",
    response_model=UsageEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a usage event (JWT auth required)",
)
async def record_event(
    data: UsageEventCreate,
    current_user: UserInDB = Depends(get_current_user),
    service: AnalyticsService = Depends(get_analytics_service),
) -> UsageEventResponse:
    """
    Persists a single usage event.  The user_id in the payload is
    overridden with the authenticated user's id to prevent spoofing.
    """
    data.user_id = current_user.id
    return await service.track_event(data)
