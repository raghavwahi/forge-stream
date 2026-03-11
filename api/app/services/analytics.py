"""Service layer for analytics: event tracking with Redis-cached summaries."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import date, timedelta, timezone
from datetime import datetime as dt

from app.providers.redis import RedisProvider
from app.repositories.analytics import AnalyticsRepository
from app.schemas.analytics import (
    AnalyticsQueryParams,
    AnalyticsSummaryResponse,
    UsageEventCreate,
    UsageEventResponse,
)

logger = logging.getLogger(__name__)

_SUMMARY_TTL_SECONDS = 300  # 5 minutes
_CACHE_KEY_PREFIX = "analytics:summary"


class AnalyticsService:
    """Orchestrates analytics write and read operations."""

    def __init__(
        self,
        analytics_repo: AnalyticsRepository,
        redis: RedisProvider,
    ) -> None:
        self._repo = analytics_repo
        self._redis = redis

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------

    async def track_event(self, data: UsageEventCreate) -> UsageEventResponse:
        """
        Persist a usage event and, when a user_id is present, update the
        daily aggregation table and invalidate the cached summary.
        """
        event = await self._repo.record_event(data)

        if data.user_id is not None:
            event_date = event.created_at.astimezone(timezone.utc).date()
            await self._repo.upsert_daily_stats(
                user_id=data.user_id,
                stat_date=event_date,
                event_type=data.event_type,
                tokens=data.tokens_used or 0,
            )
            # Invalidate any cached summary that covers today so the next
            # read reflects the new event.
            await self._invalidate_user_cache(data.user_id)

        return event

    # ------------------------------------------------------------------
    # Read path
    # ------------------------------------------------------------------

    async def get_user_summary(
        self,
        user_id: uuid.UUID,
        params: AnalyticsQueryParams,
    ) -> AnalyticsSummaryResponse:
        """Return analytics summary, bypassing the cache."""
        start, end = _resolve_date_range(params)
        return await self._repo.get_user_summary(
            user_id=user_id,
            start_date=start,
            end_date=end,
            limit=params.limit,
            event_type=params.event_type,
        )

    async def get_cached_summary(
        self,
        user_id: uuid.UUID,
        params: AnalyticsQueryParams,
    ) -> AnalyticsSummaryResponse:
        """
        Return analytics summary, serving from Redis when available.
        Cache key: analytics:summary:{user_id}:{start_date}:{end_date}
        TTL: 5 minutes.
        """
        start, end = _resolve_date_range(params)
        cache_key = _build_cache_key(user_id, start, end)

        cached = await self._redis.get(cache_key)
        if cached:
            try:
                return AnalyticsSummaryResponse.model_validate_json(cached)
            except Exception:
                # Corrupt cache entry – fall through to DB
                logger.warning(
                    "Failed to deserialise cached summary for user_id=%s",
                    user_id,
                )

        summary = await self._repo.get_user_summary(
            user_id=user_id,
            start_date=start,
            end_date=end,
            limit=params.limit,
            event_type=params.event_type,
        )

        try:
            await self._redis.set(
                cache_key,
                summary.model_dump_json(),
                expire_seconds=_SUMMARY_TTL_SECONDS,
            )
        except Exception:
            logger.warning(
                "Failed to cache summary for user_id=%s", user_id
            )

        return summary

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _invalidate_user_cache(self, user_id: uuid.UUID) -> None:
        """
        Delete the cached summary for the date range that includes today.
        Only the current-day-inclusive range is invalidated; historical
        ranges remain valid until their TTL expires.
        """
        today = dt.now(timezone.utc).date()
        # Invalidate the default 30-day window that covers today
        start = today - timedelta(days=29)
        cache_key = _build_cache_key(user_id, start, today)
        try:
            await self._redis.delete(cache_key)
        except Exception:
            logger.warning(
                "Failed to invalidate cache for user_id=%s", user_id
            )


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


def _resolve_date_range(params: AnalyticsQueryParams) -> tuple[date, date]:
    """Return a (start_date, end_date) pair, defaulting to the last 30 days."""
    today = dt.now(timezone.utc).date()
    end = params.end_date or today
    start = params.start_date or (end - timedelta(days=29))
    return start, end


def _build_cache_key(
    user_id: uuid.UUID, start: date, end: date
) -> str:
    return f"{_CACHE_KEY_PREFIX}:{user_id}:{start.isoformat()}:{end.isoformat()}"
