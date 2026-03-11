"""Async worker that processes jobs from a queue."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Dict

from app.schemas.jobs import Job, JobType

HandlerCallable = Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]


class Worker:
    """Async worker that dispatches jobs to registered handlers.

    Parameters
    ----------
    queue:
        A job-queue object that exposes async methods:
        ``dequeue()``, ``mark_done(job, result)``, ``mark_failed(job, reason)``.
    """

    def __init__(self, queue: Any) -> None:
        self._queue = queue
        self._handlers: Dict[JobType, HandlerCallable] = {}
        self._running: bool = False

    def register(self, job_type: JobType, handler: HandlerCallable) -> None:
        """Register (or overwrite) the handler for *job_type*."""
        self._handlers[job_type] = handler

    async def run_once(self) -> bool:
        """Process one job from the queue.

        Returns
        -------
        bool
            ``False`` if the queue was empty; ``True`` if a job was processed.
        """
        job: Job | None = await self._queue.dequeue()
        if job is None:
            return False

        handler = self._handlers.get(job.type)
        if handler is None:
            await self._queue.mark_failed(
                job, f"No handler for job type {job.type}"
            )
            return True

        try:
            result = await handler(job.payload)
        except Exception as exc:
            await self._queue.mark_failed(job, str(exc))
            return True

        await self._queue.mark_done(job, result)
        return True

    async def run(self) -> None:
        """Continuously process jobs until :meth:`stop` is called."""
        self._running = True
        while self._running:
            processed = await self.run_once()
            if not processed:
                # Yield to the event loop when the queue is empty so other
                # tasks (e.g. a stopper coroutine) can run.
                await asyncio.sleep(0)

    def stop(self) -> None:
        """Signal the worker to exit its run loop after the current job."""
        self._running = False
