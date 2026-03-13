"""Service layer for analytics: event tracking with Redis-cached summaries."""

from __future__ import annotations

import logging
import uuid
from datetime import date, timedelta, timezone
from datetime import datetime as dt

from app.providers.redis import RedisProvider
from app.repositories.analytics import AnalyticsRepository
from app.schemas.analytics import (
    AnalyticsQueryParams,
    AnalyticsSummaryResponse,
    DailyStatResponse,
    UsageEventCreate,
    UsageEventResponse,
)

logger = logging.getLogger(__name__)

_SUMMARY_TTL_SECONDS = 300  # 5 minutes
_CACHE_KEY_PREFIX = "analytics:summary"
_VERSION_KEY_PREFIX = "analytics:version"


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
            # Bump the per-user cache version so all existing cached keys
            # for this user are bypassed on the next read.
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
        )

    async def get_cached_summary(
        self,
        user_id: uuid.UUID,
        params: AnalyticsQueryParams,
    ) -> AnalyticsSummaryResponse:
        """
        Return analytics summary, serving from Redis when available.
        Cache key: analytics:summary:{user_id}:{version}:{start}:{end}:{limit}
        TTL: 5 minutes.  The version component is bumped on every new event
        so any subsequent read fetches fresh data regardless of the date range
        or limit that was previously cached.
        """
        start, end = _resolve_date_range(params)
        version = await self._get_user_cache_version(user_id)
        cache_key = _build_cache_key(user_id, version, start, end, params.limit)

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

    async def get_user_events(
        self,
        user_id: uuid.UUID,
        params: AnalyticsQueryParams,
    ) -> list[UsageEventResponse]:
        """
        Return a filtered, paginated list of usage events for a user.
        Applies both date range and event_type filters when provided.
        """
        start, end = _resolve_date_range(params)
        return await self._repo.get_recent_events(
            user_id=user_id,
            limit=params.limit,
            event_type=params.event_type,
            start_date=start,
            end_date=end,
        )

    async def get_daily_stats_only(
        self,
        user_id: uuid.UUID,
        params: AnalyticsQueryParams,
    ) -> list[DailyStatResponse]:
        """
        Return only per-day aggregated stats without fetching raw events,
        avoiding the unnecessary recent-events query that would be incurred
        by calling get_user_summary().
        """
        start, end = _resolve_date_range(params)
        return await self._repo.get_daily_stats(
            user_id=user_id,
            start_date=start,
            end_date=end,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_user_cache_version(self, user_id: uuid.UUID) -> int:
        """
        Return the current cache version for *user_id*.
        Returns 0 when no version key has been set yet.
        """
        version_key = f"{_VERSION_KEY_PREFIX}:{user_id}"
        try:
            raw = await self._redis.get(version_key)
            return int(raw) if raw is not None else 0
        except Exception:
            return 0

    async def _invalidate_user_cache(self, user_id: uuid.UUID) -> None:
        """
        Increment the per-user cache version, effectively invalidating
        all previously cached summaries for this user regardless of the
        date range, limit, or event_type that was cached.
        """
        version_key = f"{_VERSION_KEY_PREFIX}:{user_id}"
        try:
            await self._redis.incr(version_key)
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
    user_id: uuid.UUID, version: int, start: date, end: date, limit: int
) -> str:
    return (
        f"{_CACHE_KEY_PREFIX}:{user_id}:{version}"
        f":{start.isoformat()}:{end.isoformat()}:{limit}"
    )

