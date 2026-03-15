"""Unit tests for the async Worker."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.jobs import Job, JobStatus, JobType
from app.workers.worker import Worker


def _make_queue() -> MagicMock:
    queue = MagicMock()
    queue.dequeue = AsyncMock()
    queue.mark_done = AsyncMock()
    queue.mark_failed = AsyncMock()
    return queue


class TestWorkerRunOnce:
    @pytest.mark.asyncio
    async def test_run_once_returns_false_on_empty_queue(self):
        queue = _make_queue()
        queue.dequeue.return_value = None

        worker = Worker(queue)
        result = await worker.run_once()

        assert result is False

    @pytest.mark.asyncio
    async def test_run_once_returns_true_on_job_processed(self):
        queue = _make_queue()
        job = Job(type=JobType.GENERATE_ITEMS, payload={"prompt": "test"})
        queue.dequeue.return_value = job

        handler = AsyncMock(return_value={"items": []})
        worker = Worker(queue)
        worker.register(JobType.GENERATE_ITEMS, handler)

        result = await worker.run_once()

        assert result is True
        handler.assert_awaited_once_with(job.payload)
        queue.mark_done.assert_awaited_once_with(job, {"items": []})

    @pytest.mark.asyncio
    async def test_run_once_marks_failed_on_handler_exception(self):
        queue = _make_queue()
        job = Job(type=JobType.CREATE_ISSUES, payload={})
        queue.dequeue.return_value = job

        async def _bad_handler(payload):
            raise ValueError("GitHub error")

        worker = Worker(queue)
        worker.register(JobType.CREATE_ISSUES, _bad_handler)

        await worker.run_once()

        queue.mark_failed.assert_awaited_once()
        call_args = queue.mark_failed.call_args
        assert "GitHub error" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_run_once_marks_failed_for_unregistered_job_type(self):
        queue = _make_queue()
        job = Job(type=JobType.ENHANCE_ITEMS, payload={})
        queue.dequeue.return_value = job

        worker = Worker(queue)  # no handlers registered
        await worker.run_once()

        queue.mark_failed.assert_awaited_once()
        call_args = queue.mark_failed.call_args
        assert "No handler" in call_args[0][1]


class TestWorkerRegister:
    def test_register_stores_handler(self):
        queue = _make_queue()
        worker = Worker(queue)

        async def my_handler(payload):
            return {}

        worker.register(JobType.GENERATE_ITEMS, my_handler)
        assert worker._handlers[JobType.GENERATE_ITEMS] is my_handler

    def test_register_overwrites_existing(self):
        queue = _make_queue()
        worker = Worker(queue)

        async def first(payload):
            return {}

        async def second(payload):
            return {}

        worker.register(JobType.GENERATE_ITEMS, first)
        worker.register(JobType.GENERATE_ITEMS, second)
        assert worker._handlers[JobType.GENERATE_ITEMS] is second


class TestWorkerStop:
    @pytest.mark.asyncio
    async def test_stop_exits_run_loop(self):
        queue = _make_queue()
        queue.dequeue.return_value = None

        worker = Worker(queue)

        import asyncio

        async def _stopper():
            await asyncio.sleep(0.01)
            worker.stop()

        await asyncio.gather(worker.run(), _stopper())
        assert not worker._running
