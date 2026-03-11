"""Redis-backed FIFO job queue using LPUSH / BRPOP."""
from __future__ import annotations

import logging

from app.providers.redis import RedisProvider
from app.schemas.jobs import Job, JobStatus

logger = logging.getLogger(__name__)

_QUEUE_KEY = "forge:jobs:pending"
_JOB_PREFIX = "forge:job:"


class JobQueue:
    """Persistent FIFO job queue backed by Redis sorted-sets + string keys."""

    def __init__(self, redis: RedisProvider) -> None:
        self._redis = redis

    # ── helpers ─────────────────────────────────────────────────────────────

    def _client(self):
        c = self._redis._client
        if c is None:
            raise RuntimeError("RedisProvider is not connected")
        return c

    async def _save(self, job: Job) -> None:
        await self._client().set(
            f"{_JOB_PREFIX}{job.id}", job.model_dump_json(), ex=86_400
        )

    # ── public API ───────────────────────────────────────────────────────────

    async def enqueue(self, job: Job) -> str:
        """Persist job data and push its ID onto the queue. Returns job ID."""
        pipe = self._client().pipeline()
        pipe.set(f"{_JOB_PREFIX}{job.id}", job.model_dump_json(), ex=86_400)
        pipe.lpush(_QUEUE_KEY, job.id)
        await pipe.execute()
        logger.info("Enqueued job id=%s type=%s", job.id, job.type)
        return job.id

    async def dequeue(self, timeout: int = 5) -> Job | None:
        """Block-pop one job from the queue; returns None on timeout."""
        result = await self._client().brpop([_QUEUE_KEY], timeout=timeout)
        if result is None:
            return None
        _, raw_id = result
        raw = await self._client().get(f"{_JOB_PREFIX}{raw_id.decode()}")
        if raw is None:
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

    async def get_status(self, job_id: str) -> Job | None:
        """Return the current state of a job by ID, or None if not found."""
        raw = await self._client().get(f"{_JOB_PREFIX}{job_id}")
        if raw is None:
            return None
        return Job.model_validate_json(raw)
