"""Tests for the analytics API endpoints."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_analytics_service, get_current_user
from app.models.user import UserInDB
from app.routers.analytics import router as analytics_router
from app.schemas.analytics import (
    AnalyticsSummaryResponse,
    DailyStatResponse,
    UsageEventResponse,
)

# ---------------------------------------------------------------------------
# Minimal test application (avoids importing the full main.py dependency tree)
# ---------------------------------------------------------------------------

_test_app = FastAPI()
_test_app.include_router(analytics_router)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_USER_ID = uuid.uuid4()

_MOCK_USER = UserInDB(
    id=_USER_ID,
    email="test@example.com",
    name="Test User",
    provider="email",
    is_active=True,
    is_verified=True,
    password_hash=None,
    avatar_url=None,
    created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
)

_MOCK_EVENT = UsageEventResponse(
    id=uuid.uuid4(),
    user_id=_USER_ID,
    event_type="completion",
    provider="openai",
    model="gpt-4o-mini",
    tokens_used=100,
    latency_ms=250,
    metadata={},
    created_at=datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc),
)

_MOCK_DAILY = DailyStatResponse(
    date=date(2024, 6, 1),
    total_events=5,
    total_tokens=500,
    events_by_type={"completion": 5},
)

_MOCK_SUMMARY = AnalyticsSummaryResponse(
    total_events=5,
    total_tokens=500,
    events_by_type={"completion": 5},
    recent_events=[_MOCK_EVENT],
    daily_stats=[_MOCK_DAILY],
)


def _make_mock_service(**method_overrides):
    """Return an AsyncMock analytics service with sensible defaults."""
    svc = MagicMock()
    svc.get_cached_summary = AsyncMock(return_value=_MOCK_SUMMARY)
    svc.get_user_events = AsyncMock(return_value=[_MOCK_EVENT])
    svc.get_daily_stats_only = AsyncMock(return_value=[_MOCK_DAILY])
    svc.track_event = AsyncMock(return_value=_MOCK_EVENT)
    for name, value in method_overrides.items():
        setattr(svc, name, value)
    return svc


def _client_with_overrides(service=None):
    """Build a TestClient with both auth and service dependencies overridden."""
    mock_service = service or _make_mock_service()
    _test_app.dependency_overrides[get_current_user] = lambda: _MOCK_USER
    _test_app.dependency_overrides[get_analytics_service] = lambda: mock_service
    client = TestClient(_test_app, raise_server_exceptions=True)
    return client, mock_service


def _teardown():
    _test_app.dependency_overrides.pop(get_current_user, None)
    _test_app.dependency_overrides.pop(get_analytics_service, None)


# ---------------------------------------------------------------------------
# GET /api/v1/analytics/summary
# ---------------------------------------------------------------------------


class TestGetSummary:
    def test_returns_summary(self):
        client, svc = _client_with_overrides()
        try:
            resp = client.get("/api/v1/analytics/summary")
        finally:
            _teardown()

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_events"] == 5
        assert data["total_tokens"] == 500
        assert data["events_by_type"] == {"completion": 5}
        assert len(data["recent_events"]) == 1
        assert len(data["daily_stats"]) == 1

    def test_cache_hit_served_from_cache(self):
        """Second identical call returns the same payload (cache hit simulation)."""
        client, svc = _client_with_overrides()
        try:
            resp1 = client.get("/api/v1/analytics/summary")
            resp2 = client.get("/api/v1/analytics/summary")
        finally:
            _teardown()

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json() == resp2.json()
        # Service was called for both; caching layer is tested at the unit level
        assert svc.get_cached_summary.call_count == 2

    def test_passes_query_params(self):
        client, svc = _client_with_overrides()
        try:
            resp = client.get(
                "/api/v1/analytics/summary",
                params={
                    "start_date": "2024-01-01",
                    "end_date": "2024-06-30",
                    "limit": 10,
                },
            )
        finally:
            _teardown()

        assert resp.status_code == 200
        call_params = svc.get_cached_summary.call_args[0][1]
        assert str(call_params.start_date) == "2024-01-01"
        assert str(call_params.end_date) == "2024-06-30"
        assert call_params.limit == 10

    def test_requires_auth(self):
        resp = TestClient(_test_app).get("/api/v1/analytics/summary")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /api/v1/analytics/events
# ---------------------------------------------------------------------------


class TestListEvents:
    def test_returns_event_list(self):
        client, _ = _client_with_overrides()
        try:
            resp = client.get("/api/v1/analytics/events")
        finally:
            _teardown()

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["event_type"] == "completion"

    def test_date_filter_passed_to_service(self):
        client, svc = _client_with_overrides()
        try:
            resp = client.get(
                "/api/v1/analytics/events",
                params={"start_date": "2024-06-01", "end_date": "2024-06-30"},
            )
        finally:
            _teardown()

        assert resp.status_code == 200
        call_params = svc.get_user_events.call_args[0][1]
        assert str(call_params.start_date) == "2024-06-01"
        assert str(call_params.end_date) == "2024-06-30"

    def test_event_type_filter_passed_to_service(self):
        client, svc = _client_with_overrides()
        try:
            resp = client.get(
                "/api/v1/analytics/events",
                params={"event_type": "completion"},
            )
        finally:
            _teardown()

        assert resp.status_code == 200
        call_params = svc.get_user_events.call_args[0][1]
        assert call_params.event_type == "completion"

    def test_requires_auth(self):
        resp = TestClient(_test_app).get("/api/v1/analytics/events")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /api/v1/analytics/daily
# ---------------------------------------------------------------------------


class TestListDailyStats:
    def test_returns_daily_list(self):
        client, _ = _client_with_overrides()
        try:
            resp = client.get("/api/v1/analytics/daily")
        finally:
            _teardown()

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert data[0]["total_events"] == 5
        assert data[0]["total_tokens"] == 500

    def test_calls_dedicated_daily_method(self):
        """Verifies that /daily uses get_daily_stats_only, not get_user_summary."""
        client, svc = _client_with_overrides()
        try:
            client.get("/api/v1/analytics/daily")
        finally:
            _teardown()

        svc.get_daily_stats_only.assert_called_once()
        if hasattr(svc, "get_user_summary"):
            svc.get_user_summary.assert_not_called()

    def test_requires_auth(self):
        resp = TestClient(_test_app).get("/api/v1/analytics/daily")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# POST /api/v1/analytics/events
# ---------------------------------------------------------------------------


class TestRecordEvent:
    def test_creates_event_returns_201(self):
        client, _ = _client_with_overrides()
        try:
            resp = client.post(
                "/api/v1/analytics/events",
                json={
                    "event_type": "completion",
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                    "tokens_used": 100,
                    "latency_ms": 250,
                    "metadata": {},
                },
            )
        finally:
            _teardown()

        assert resp.status_code == 201
        data = resp.json()
        assert data["event_type"] == "completion"

    def test_user_id_overridden_with_authenticated_user(self):
        """Payload user_id must be replaced by the authenticated user's ID."""
        client, svc = _client_with_overrides()
        try:
            resp = client.post(
                "/api/v1/analytics/events",
                json={
                    "event_type": "completion",
                    "user_id": str(uuid.uuid4()),  # attacker-supplied ID
                    "metadata": {},
                },
            )
        finally:
            _teardown()

        assert resp.status_code == 201
        recorded_data = svc.track_event.call_args[0][0]
        assert recorded_data.user_id == _USER_ID

    def test_requires_auth(self):
        resp = TestClient(_test_app).post(
            "/api/v1/analytics/events",
            json={"event_type": "completion"},
        )
        assert resp.status_code in (401, 403)
