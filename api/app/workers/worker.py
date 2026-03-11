"""Async background worker that consumes jobs from a JobQueue."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.schemas.jobs import JobType
from app.workers.job_queue import JobQueue

logger = logging.getLogger(__name__)

Handler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class Worker:
    """Poll a :class:`JobQueue` and dispatch jobs to registered async handlers."""

    def __init__(self, queue: JobQueue, dequeue_timeout: int = 5) -> None:
        self._queue = queue
        self._handlers: dict[JobType, Handler] = {}
        self._running = False
        self._dequeue_timeout = dequeue_timeout

    def register(self, job_type: JobType, handler: Handler) -> None:
        """Register an async handler for a specific :class:`JobType`."""
        self._handlers[job_type] = handler

    async def run_once(self) -> bool:
        """Dequeue and process one job.

        Returns True if work was done, False if the queue was empty.
        """
        job = await self._queue.dequeue(timeout=self._dequeue_timeout)
        if job is None:
            return False

        handler = self._handlers.get(job.type)
        if handler is None:
            await self._queue.mark_failed(
                job, f"No handler registered for type={job.type}"
            )
            return True

        try:
            result = await handler(job.payload)
            await self._queue.mark_done(job, result)
        except Exception as exc:
            logger.exception("Job %s raised an exception: %s", job.id, exc)
            await self._queue.mark_failed(job, str(exc))

        return True

    async def run(self) -> None:
        """Poll and process jobs in a loop until :meth:`stop` is called."""
        self._running = True
        logger.info("Worker started")
        while self._running:
            try:
                await self.run_once()
            except Exception as exc:
                logger.exception("Unhandled error in worker loop: %s", exc)
                await asyncio.sleep(1)
        logger.info("Worker stopped")

    def stop(self) -> None:
        """Request the worker loop to exit after the current job finishes."""
        self._running = False
