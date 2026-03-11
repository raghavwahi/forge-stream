"""Repository for analytics usage events and daily statistics."""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone

from app.repositories.base import BaseRepository
from app.schemas.analytics import (
    AnalyticsSummaryResponse,
    DailyStatResponse,
    UsageEventCreate,
    UsageEventResponse,
)


class AnalyticsRepository(BaseRepository):
    """Provides persistence operations for analytics data."""

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    async def record_event(self, data: UsageEventCreate) -> UsageEventResponse:
        """Insert a new usage event row and return the persisted record."""
        row = await self._db.fetch_one(
            """
            INSERT INTO usage_events
                (user_id, event_type, provider, model,
                 tokens_used, latency_ms, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING
                id, user_id, event_type, provider, model,
                tokens_used, latency_ms, metadata, created_at
            """,
            data.user_id,
            data.event_type,
            data.provider,
            data.model,
            data.tokens_used,
            data.latency_ms,
            json.dumps(data.metadata),
        )
        return _row_to_event(row)

    async def upsert_daily_stats(
        self,
        user_id: uuid.UUID,
        stat_date: date,
        event_type: str,
        tokens: int,
    ) -> None:
        """
        Insert or update the aggregated daily stats row for a user/date pair.
        Increments total_events, total_tokens, and the per-type counter in
        the events_by_type JSONB column atomically.
        """
        await self._db.execute(
            """
            INSERT INTO daily_usage_stats
                (user_id, date, total_events, total_tokens, events_by_type)
            VALUES ($1, $2, 1, $3, jsonb_build_object($4::text, 1))
            ON CONFLICT (user_id, date) DO UPDATE SET
                total_events   = daily_usage_stats.total_events + 1,
                total_tokens   = daily_usage_stats.total_tokens + $3,
                events_by_type = jsonb_set(
                    daily_usage_stats.events_by_type,
                    ARRAY[$4::text],
                    to_jsonb(
                        COALESCE(
                            (daily_usage_stats.events_by_type ->> $4::text)::integer,
                            0
                        ) + 1
                    )
                )
            """,
            user_id,
            stat_date,
            tokens or 0,
            event_type,
        )

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    async def get_recent_events(
        self,
        user_id: uuid.UUID,
        limit: int,
        event_type: str | None,
    ) -> list[UsageEventResponse]:
        """Return the most recent usage events for a user."""
        if event_type:
            rows = await self._db.fetch_all(
                """
                SELECT id, user_id, event_type, provider, model,
                       tokens_used, latency_ms, metadata, created_at
                FROM   usage_events
                WHERE  user_id = $1 AND event_type = $2
                ORDER  BY created_at DESC
                LIMIT  $3
                """,
                user_id,
                event_type,
                limit,
            )
        else:
            rows = await self._db.fetch_all(
                """
                SELECT id, user_id, event_type, provider, model,
                       tokens_used, latency_ms, metadata, created_at
                FROM   usage_events
                WHERE  user_id = $1
                ORDER  BY created_at DESC
                LIMIT  $2
                """,
                user_id,
                limit,
            )
        return [_row_to_event(r) for r in rows]

    async def get_daily_stats(
        self,
        user_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> list[DailyStatResponse]:
        """Return per-day aggregated stats for a user within a date range."""
        rows = await self._db.fetch_all(
            """
            SELECT date, total_events, total_tokens, events_by_type
            FROM   daily_usage_stats
            WHERE  user_id = $1
              AND  date BETWEEN $2 AND $3
            ORDER  BY date ASC
            """,
            user_id,
            start_date,
            end_date,
        )
        return [_row_to_daily_stat(r) for r in rows]

    async def get_user_summary(
        self,
        user_id: uuid.UUID,
        start_date: date,
        end_date: date,
        limit: int,
        event_type: str | None,
    ) -> AnalyticsSummaryResponse:
        """
        Compute a high-level summary combining totals and per-type
        breakdowns from the daily stats table, plus recent raw events.
        """
        # Aggregate totals from daily_usage_stats for the date range
        agg = await self._db.fetch_one(
            """
            SELECT
                COALESCE(SUM(total_events), 0)  AS total_events,
                COALESCE(SUM(total_tokens), 0)  AS total_tokens,
                (
                    SELECT jsonb_object_agg(key, cnt)
                    FROM (
                        SELECT key, SUM(value::bigint) AS cnt
                        FROM   daily_usage_stats,
                               jsonb_each_text(events_by_type)
                        WHERE  user_id = $1
                          AND  date BETWEEN $2 AND $3
                        GROUP  BY key
                    ) sub
                ) AS events_by_type
            FROM daily_usage_stats
            WHERE user_id = $1
              AND date BETWEEN $2 AND $3
            """,
            user_id,
            start_date,
            end_date,
        )

        total_events = int(agg["total_events"]) if agg else 0
        total_tokens = int(agg["total_tokens"]) if agg else 0
        raw_by_type = agg["events_by_type"] if agg else None
        # asyncpg may return the JSONB column as a string or dict
        events_by_type: dict = {}
        if raw_by_type:
            if isinstance(raw_by_type, str):
                events_by_type = json.loads(raw_by_type)
            else:
                events_by_type = dict(raw_by_type)

        recent = await self.get_recent_events(user_id, limit, event_type)
        daily = await self.get_daily_stats(user_id, start_date, end_date)

        return AnalyticsSummaryResponse(
            total_events=total_events,
            total_tokens=total_tokens,
            events_by_type=events_by_type,
            recent_events=recent,
            daily_stats=daily,
        )


# ------------------------------------------------------------------
# Private helpers
# ------------------------------------------------------------------


def _parse_jsonb(value: object) -> dict:
    """Normalise an asyncpg JSONB value to a plain Python dict."""
    if value is None:
        return {}
    if isinstance(value, str):
        return json.loads(value)
    return dict(value)


def _row_to_event(row: dict) -> UsageEventResponse:
    created_at: datetime = row["created_at"]
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return UsageEventResponse(
        id=row["id"],
        user_id=row.get("user_id"),
        event_type=row["event_type"],
        provider=row.get("provider"),
        model=row.get("model"),
        tokens_used=row.get("tokens_used"),
        latency_ms=row.get("latency_ms"),
        metadata=_parse_jsonb(row.get("metadata")),
        created_at=created_at,
    )


def _row_to_daily_stat(row: dict) -> DailyStatResponse:
    return DailyStatResponse(
        date=row["date"],
        total_events=int(row["total_events"]),
        total_tokens=int(row["total_tokens"]),
        events_by_type=_parse_jsonb(row.get("events_by_type")),
    )
