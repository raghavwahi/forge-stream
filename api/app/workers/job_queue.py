"""Redis-backed FIFO job queue using LPUSH / BRPOP."""
from __future__ import annotations

import logging
import uuid

from app.providers.base import BaseCacheProvider
from app.schemas.jobs import Job, JobStatus

logger = logging.getLogger(__name__)

_QUEUE_KEY = "forge:jobs:pending"
_JOB_PREFIX = "forge:job:"

# Default TTL of 7 days to prevent jobs from expiring while still pending.
_DEFAULT_TTL = 7 * 86_400


class JobQueue:
    """FIFO job queue backed by a Redis list (LPUSH/BRPOP) plus per-job string keys."""

    def __init__(self, redis: BaseCacheProvider, ttl: int = _DEFAULT_TTL) -> None:
        self._redis = redis
        self._ttl = ttl

    # ── helpers ─────────────────────────────────────────────────────────────

    async def _save(self, job: Job) -> None:
        await self._redis.set(
            f"{_JOB_PREFIX}{job.id}", job.model_dump_json(), expire_seconds=self._ttl
        )

    # ── public API ───────────────────────────────────────────────────────────

    async def enqueue(self, job: Job) -> uuid.UUID:
        """Persist job data and push its ID onto the queue. Returns job ID."""
        await self._redis.set_with_lpush(
            f"{_JOB_PREFIX}{job.id}",
            job.model_dump_json(),
            _QUEUE_KEY,
            str(job.id),
            self._ttl,
        )
        logger.info("Enqueued job id=%s type=%s", job.id, job.type)
        return job.id

    async def dequeue(self, timeout: int = 5) -> Job | None:
        """Block-pop one job from the queue; returns None on timeout."""
        result = await self._redis.brpop([_QUEUE_KEY], timeout=timeout)
        if result is None:
            return None
        _, job_id = result
        raw = await self._redis.get(f"{_JOB_PREFIX}{job_id}")
        if raw is None:
            logger.error(
                "Dequeued job id=%s but payload key is missing; possible data "
                "corruption in Redis",
                job_id,
            )
            return None
        job = Job.model_validate_json(raw)
        job.status = JobStatus.RUNNING
        await self._save(job)
        return job

    async def mark_done(self, job: Job, result: dict | None = None) -> None:
        """Mark a running job as successfully completed."""
        job.status = JobStatus.DONE
        job.result = result
        await self._save(job)
        logger.info("Job done id=%s", job.id)

    async def mark_failed(self, job: Job, error: str) -> None:
        """Mark a running job as failed with an error message."""
        job.status = JobStatus.FAILED
        job.error = error
        await self._save(job)
        logger.warning("Job failed id=%s error=%s", job.id, error)

    async def get_status(self, job_id: uuid.UUID | str) -> Job | None:
        """Return the current state of a job by ID, or None if not found."""
        raw = await self._redis.get(f"{_JOB_PREFIX}{job_id}")
        if raw is None:
            return None
        return Job.model_validate_json(raw)
