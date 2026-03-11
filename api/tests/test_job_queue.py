"""Unit tests for JobQueue (Redis-backed job queue)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.jobs import Job, JobStatus, JobType
from app.workers.job_queue import _QUEUE_KEY, JobQueue


def _make_redis() -> MagicMock:
    """Return a mock RedisProvider whose ._client is also a mock."""
    redis = MagicMock()
    client = AsyncMock()
    redis._client = client
    return redis, client


class TestJobQueueEnqueue:
    @pytest.mark.asyncio
    async def test_enqueue_returns_job_id(self):
        redis, client = _make_redis()
        pipe = AsyncMock()
        client.pipeline.return_value = pipe
        pipe.execute = AsyncMock(return_value=[True, 1])

        queue = JobQueue(redis)
        job = Job(type=JobType.GENERATE_ITEMS, payload={"prompt": "hello"})
        returned_id = await queue.enqueue(job)

        assert returned_id == job.id

    @pytest.mark.asyncio
    async def test_enqueue_stores_and_pushes(self):
        redis, client = _make_redis()
        pipe = AsyncMock()
        client.pipeline.return_value = pipe
        pipe.set = AsyncMock()
        pipe.lpush = AsyncMock()
        pipe.execute = AsyncMock(return_value=[True, 1])

        queue = JobQueue(redis)
        job = Job(type=JobType.CREATE_ISSUES, payload={})
        await queue.enqueue(job)

        pipe.set.assert_awaited_once()
        pipe.lpush.assert_awaited_once_with(_QUEUE_KEY, job.id)

    @pytest.mark.asyncio
    async def test_enqueue_raises_when_not_connected(self):
        redis = MagicMock()
        redis._client = None
        queue = JobQueue(redis)
        with pytest.raises(RuntimeError, match="not connected"):
            await queue.enqueue(Job(type=JobType.ENHANCE_ITEMS, payload={}))


class TestJobQueueDequeue:
    @pytest.mark.asyncio
    async def test_dequeue_returns_none_on_timeout(self):
        redis, client = _make_redis()
        client.brpop = AsyncMock(return_value=None)

        queue = JobQueue(redis)
        result = await queue.dequeue(timeout=1)
        assert result is None

    @pytest.mark.asyncio
    async def test_dequeue_returns_job_and_marks_running(self):
        redis, client = _make_redis()
        job = Job(type=JobType.GENERATE_ITEMS, payload={})
        job_json = job.model_dump_json().encode()

        client.brpop = AsyncMock(return_value=(b"key", job.id.encode()))
        client.get = AsyncMock(return_value=job_json)
        client.set = AsyncMock()

        queue = JobQueue(redis)
        result = await queue.dequeue(timeout=1)

        assert result is not None
        assert result.id == job.id
        assert result.status == JobStatus.RUNNING


class TestJobQueueMarkDone:
    @pytest.mark.asyncio
    async def test_mark_done_sets_status(self):
        redis, client = _make_redis()
        client.set = AsyncMock()

        queue = JobQueue(redis)
        job = Job(type=JobType.CREATE_ISSUES, payload={}, status=JobStatus.RUNNING)
        await queue.mark_done(job, result={"created": 3})

        assert job.status == JobStatus.DONE
        assert job.result == {"created": 3}

    @pytest.mark.asyncio
    async def test_mark_failed_sets_error(self):
        redis, client = _make_redis()
        client.set = AsyncMock()

        queue = JobQueue(redis)
        job = Job(type=JobType.CREATE_ISSUES, payload={}, status=JobStatus.RUNNING)
        await queue.mark_failed(job, error="timeout")

        assert job.status == JobStatus.FAILED
        assert job.error == "timeout"


class TestJobQueueGetStatus:
    @pytest.mark.asyncio
    async def test_get_status_returns_job(self):
        redis, client = _make_redis()
        job = Job(type=JobType.ENHANCE_ITEMS, payload={})
        client.get = AsyncMock(return_value=job.model_dump_json().encode())

        queue = JobQueue(redis)
        result = await queue.get_status(job.id)

        assert result is not None
        assert result.id == job.id

    @pytest.mark.asyncio
    async def test_get_status_returns_none_if_missing(self):
        redis, client = _make_redis()
        client.get = AsyncMock(return_value=None)

        queue = JobQueue(redis)
        result = await queue.get_status("nonexistent-id")
        assert result is None
