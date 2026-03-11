"""Tests for the job queue, worker, and job API endpoints."""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.models.user import UserInDB
from app.providers.base import BaseCacheProvider
from app.routers.jobs import _get_queue
from app.routers.jobs import router as jobs_router
from app.schemas.jobs import Job, JobStatus, JobType
from app.workers.job_queue import JobQueue
from app.workers.worker import Worker

# ── In-memory fake cache provider ────────────────────────────────────────────


class FakeCacheProvider(BaseCacheProvider):
    """In-memory BaseCacheProvider for unit tests."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._queues: dict[str, list[str]] = {}

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(
        self, key: str, value: str, expire_seconds: int | None = None
    ) -> None:
        self._store[key] = value

    async def incr(self, key: str) -> int:
        val = int(self._store.get(key, "0")) + 1
        self._store[key] = str(val)
        return val

    async def expire(self, key: str, seconds: int) -> None:
        pass

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def lpush(self, key: str, *values: str) -> int:
        q = self._queues.setdefault(key, [])
        for v in reversed(values):
            q.insert(0, v)
        return len(q)

    async def brpop(
        self, keys: list[str], timeout: int
    ) -> tuple[str, str] | None:
        for key in keys:
            q = self._queues.get(key, [])
            if q:
                return key, q.pop()
        return None

    async def set_with_lpush(
        self,
        data_key: str,
        data_value: str,
        queue_key: str,
        member: str,
        ttl: int,
    ) -> None:
        self._store[data_key] = data_value
        await self.lpush(queue_key, member)


# ── Minimal test app ──────────────────────────────────────────────────────────

_test_app = FastAPI()
_test_app.include_router(jobs_router)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_user(**kwargs: Any) -> UserInDB:
    defaults = dict(
        id=uuid.uuid4(),
        email="alice@example.com",
        name="Alice",
        provider="email",
        is_active=True,
        is_verified=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    return UserInDB(**defaults)


# ── JobQueue unit tests ───────────────────────────────────────────────────────


class TestJobQueue:
    def test_enqueue_stores_job_and_returns_id(self) -> None:
        cache = FakeCacheProvider()
        queue = JobQueue(cache)
        job = Job(type=JobType.GENERATE_ITEMS)

        returned_id = asyncio.run(queue.enqueue(job))

        assert returned_id == job.id
        # Job payload must be persisted
        assert f"forge:job:{job.id}" in cache._store
        # Job ID must appear in the queue list
        assert str(job.id) in cache._queues.get("forge:jobs:pending", [])

    def test_enqueue_dequeue_fifo_order(self) -> None:
        cache = FakeCacheProvider()
        queue = JobQueue(cache)
        job_a = Job(type=JobType.GENERATE_ITEMS)
        job_b = Job(type=JobType.ENHANCE_ITEMS)

        asyncio.run(queue.enqueue(job_a))
        asyncio.run(queue.enqueue(job_b))

        first = asyncio.run(queue.dequeue())
        second = asyncio.run(queue.dequeue())

        assert first is not None and first.id == job_a.id
        assert second is not None and second.id == job_b.id

    def test_dequeue_sets_status_running(self) -> None:
        cache = FakeCacheProvider()
        queue = JobQueue(cache)
        job = Job(type=JobType.CREATE_ISSUES)
        asyncio.run(queue.enqueue(job))

        dequeued = asyncio.run(queue.dequeue())

        assert dequeued is not None
        assert dequeued.status == JobStatus.RUNNING

    def test_dequeue_empty_queue_returns_none(self) -> None:
        cache = FakeCacheProvider()
        queue = JobQueue(cache)

        result = asyncio.run(queue.dequeue(timeout=0))

        assert result is None

    def test_mark_done_updates_status_and_result(self) -> None:
        cache = FakeCacheProvider()
        queue = JobQueue(cache)
        job = Job(type=JobType.GENERATE_ITEMS)
        asyncio.run(queue.enqueue(job))
        dequeued = asyncio.run(queue.dequeue())
        assert dequeued is not None

        asyncio.run(queue.mark_done(dequeued, result={"items": []}))

        stored = asyncio.run(queue.get_status(dequeued.id))
        assert stored is not None
        assert stored.status == JobStatus.DONE
        assert stored.result == {"items": []}

    def test_mark_failed_updates_status_and_error(self) -> None:
        cache = FakeCacheProvider()
        queue = JobQueue(cache)
        job = Job(type=JobType.GENERATE_ITEMS)
        asyncio.run(queue.enqueue(job))
        dequeued = asyncio.run(queue.dequeue())
        assert dequeued is not None

        asyncio.run(queue.mark_failed(dequeued, error="boom"))

        stored = asyncio.run(queue.get_status(dequeued.id))
        assert stored is not None
        assert stored.status == JobStatus.FAILED
        assert stored.error == "boom"

    def test_get_status_nonexistent_returns_none(self) -> None:
        cache = FakeCacheProvider()
        queue = JobQueue(cache)

        result = asyncio.run(queue.get_status(str(uuid.uuid4())))

        assert result is None

    def test_dequeue_missing_payload_logs_and_returns_none(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """If the job ID is popped but the key is already gone, return None."""
        cache = FakeCacheProvider()
        queue = JobQueue(cache)
        phantom_id = str(uuid.uuid4())
        # Push an ID with no corresponding data key
        asyncio.run(cache.lpush("forge:jobs:pending", phantom_id))

        with caplog.at_level(logging.ERROR, logger="app.workers.job_queue"):
            result = asyncio.run(queue.dequeue())

        assert result is None
        assert phantom_id in caplog.text


# ── Worker unit tests ─────────────────────────────────────────────────────────


class TestWorker:
    def _make_queue_mock(self, job: Job | None = None) -> AsyncMock:
        q = AsyncMock(spec=JobQueue)
        q.dequeue.return_value = job
        return q

    def test_run_once_no_job_returns_false(self) -> None:
        mock_queue = self._make_queue_mock(job=None)
        worker = Worker(mock_queue)

        result = asyncio.run(worker.run_once())

        assert result is False
        mock_queue.mark_done.assert_not_called()
        mock_queue.mark_failed.assert_not_called()

    def test_run_once_dispatches_handler_and_marks_done(self) -> None:
        job = Job(type=JobType.GENERATE_ITEMS)
        mock_queue = self._make_queue_mock(job=job)
        worker = Worker(mock_queue)
        handler_result = {"items": ["a"]}

        async def my_handler(payload: dict) -> dict:
            return handler_result

        worker.register(JobType.GENERATE_ITEMS, my_handler)

        result = asyncio.run(worker.run_once())

        assert result is True
        mock_queue.mark_done.assert_awaited_once_with(job, handler_result)
        mock_queue.mark_failed.assert_not_called()

    def test_run_once_handler_exception_marks_failed(self) -> None:
        job = Job(type=JobType.GENERATE_ITEMS)
        mock_queue = self._make_queue_mock(job=job)
        worker = Worker(mock_queue)

        async def bad_handler(payload: dict) -> dict:
            raise ValueError("something went wrong")

        worker.register(JobType.GENERATE_ITEMS, bad_handler)

        result = asyncio.run(worker.run_once())

        assert result is True
        mock_queue.mark_done.assert_not_called()
        mock_queue.mark_failed.assert_awaited_once()
        call_args = mock_queue.mark_failed.call_args[0]
        assert call_args[0] == job
        assert "something went wrong" in call_args[1]

    def test_run_once_no_handler_registered_marks_failed(self) -> None:
        job = Job(type=JobType.GENERATE_ITEMS)
        mock_queue = self._make_queue_mock(job=job)
        worker = Worker(mock_queue)
        # No handler registered for GENERATE_ITEMS

        result = asyncio.run(worker.run_once())

        assert result is True
        mock_queue.mark_failed.assert_awaited_once()
        error_msg = mock_queue.mark_failed.call_args[0][1]
        assert "No handler registered" in error_msg

    def test_dequeue_timeout_is_configurable(self) -> None:
        mock_queue = self._make_queue_mock(job=None)
        worker = Worker(mock_queue, dequeue_timeout=2)

        asyncio.run(worker.run_once())

        mock_queue.dequeue.assert_awaited_once_with(timeout=2)


# ── Job API endpoint tests ─────────────────────────────────────────────────────

_FAKE_USER = _make_user()


def _queue_override(mock_queue: JobQueue):
    def _override() -> JobQueue:
        return mock_queue

    return _override


def _user_override(user: UserInDB = _FAKE_USER):
    def _override() -> UserInDB:
        return user

    return _override


class TestJobEndpoints:
    def setup_method(self) -> None:
        """Install dependency overrides before each test."""
        self._mock_queue = AsyncMock(spec=JobQueue)
        _test_app.dependency_overrides[_get_queue] = _queue_override(
            self._mock_queue
        )
        _test_app.dependency_overrides[get_current_user] = _user_override()
        self._client = TestClient(_test_app, raise_server_exceptions=True)

    def teardown_method(self) -> None:
        """Remove dependency overrides after each test."""
        _test_app.dependency_overrides.clear()

    def test_enqueue_job_returns_202_with_pending_status(self) -> None:
        async def mock_enqueue(job: Job) -> str:
            return str(job.id)

        self._mock_queue.enqueue.side_effect = mock_enqueue

        resp = self._client.post(
            "/api/v1/jobs",
            json={"type": "generate_items", "payload": {"prompt": "hello"}},
        )

        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "pending"
        assert uuid.UUID(data["id"])  # valid UUID
        self._mock_queue.enqueue.assert_called_once()

    def test_enqueue_job_sets_owner_user_id(self) -> None:
        captured: list[Job] = []

        async def capture_enqueue(job: Job) -> str:
            captured.append(job)
            return str(job.id)

        self._mock_queue.enqueue.side_effect = capture_enqueue

        self._client.post(
            "/api/v1/jobs",
            json={"type": "generate_items"},
        )

        assert len(captured) == 1
        assert captured[0].owner_user_id == _FAKE_USER.id

    def test_get_job_status_returns_job(self) -> None:
        job = Job(
            type=JobType.GENERATE_ITEMS,
            status=JobStatus.DONE,
            owner_user_id=_FAKE_USER.id,
            result={"items": []},
        )
        self._mock_queue.get_status.return_value = job

        resp = self._client.get(f"/api/v1/jobs/{job.id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "done"
        assert data["result"] == {"items": []}

    def test_get_job_status_not_found_returns_404(self) -> None:
        self._mock_queue.get_status.return_value = None

        resp = self._client.get(f"/api/v1/jobs/{uuid.uuid4()}")

        assert resp.status_code == 404

    def test_get_job_status_invalid_uuid_returns_422(self) -> None:
        resp = self._client.get("/api/v1/jobs/not-a-uuid")

        assert resp.status_code == 422

    def test_get_job_status_wrong_owner_returns_403(self) -> None:
        other_user_id = uuid.uuid4()
        job = Job(
            type=JobType.GENERATE_ITEMS,
            status=JobStatus.DONE,
            owner_user_id=other_user_id,
        )
        self._mock_queue.get_status.return_value = job

        resp = self._client.get(f"/api/v1/jobs/{job.id}")

        assert resp.status_code == 403

    def test_get_job_status_no_owner_allows_any_user(self) -> None:
        """Jobs without owner_user_id are accessible to any authenticated user."""
        job = Job(
            type=JobType.GENERATE_ITEMS,
            status=JobStatus.RUNNING,
            owner_user_id=None,
        )
        self._mock_queue.get_status.return_value = job

        resp = self._client.get(f"/api/v1/jobs/{job.id}")

        assert resp.status_code == 200

