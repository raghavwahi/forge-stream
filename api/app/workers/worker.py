"""Async job worker that polls the queue and dispatches to handlers."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.schemas.jobs import JobType
from app.workers.job_queue import JobQueue

logger = logging.getLogger(__name__)

Handler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class Worker:
    """Polls :class:`~app.workers.job_queue.JobQueue` and calls registered handlers."""

    def __init__(self, queue: JobQueue) -> None:
        self._queue = queue
        self._handlers: dict[str, Handler] = {}
        self._running = False

    def register(self, job_type: JobType | str, handler: Handler) -> None:
        """Register *handler* for *job_type*.

        Accepts :class:`~app.schemas.jobs.JobType` enum members or plain strings.
        """
        key = job_type.value if hasattr(job_type, "value") else str(job_type)
        self._handlers[key] = handler

    def stop(self) -> None:
        """Signal the worker loop to exit after the current poll."""
        self._running = False

    async def run(self) -> None:
        """Run the worker loop until :meth:`stop` is called."""
        self._running = True
        logger.info("Worker started")
        while self._running:
            item = await self._queue.dequeue()
            if item is None:
                continue
            job_type, payload = item
            handler = self._handlers.get(job_type)
            if handler is None:
                logger.warning("No handler for job type %r — skipping", job_type)
                continue
            try:
                await handler(payload)
            except Exception:
                logger.exception("Error handling job type %r", job_type)
        logger.info("Worker stopped")
