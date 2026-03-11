"""Redis-backed job queue for async work processing."""

from __future__ import annotations

import json
from typing import Any, Optional

from app.schemas.jobs import Job, JobStatus, JobType

_QUEUE_KEY = "jobs:queue"
_JOB_PREFIX = "jobs:"


class JobQueue:
    """Async job queue backed by Redis.

    Parameters
    ----------
    redis:
        A provider object that exposes a ``._client`` attribute pointing to
        an async Redis client (e.g. the ``RedisProvider`` from
        ``app.providers.redis``).
    """

    def __init__(self, redis: Any) -> None:
        self._redis = redis

    @property
    def _client(self) -> Any:
        """Return the underlying Redis client or raise if not connected."""
        client = getattr(self._redis, "_client", None)
        if client is None:
            raise RuntimeError("Redis client is not connected")
        return client

    async def enqueue(self, job: Job) -> str:
        """Persist *job* and push its ID onto the queue.

        Returns the job ID.
        """
        client = self._client
        pipe = await client.pipeline()
        job_key = f"{_JOB_PREFIX}{job.id}"
        await pipe.set(job_key, job.model_dump_json().encode())
        await pipe.lpush(_QUEUE_KEY, job.id)
        await pipe.execute()
        return job.id

    async def dequeue(self, timeout: int = 0) -> Optional[Job]:
        """Pop the next job ID from the queue and mark it as RUNNING.

        Returns ``None`` if the queue is empty (blocking wait timed out).
        """
        client = self._client
        item = await client.brpop(_QUEUE_KEY, timeout=timeout)
        if not item:
            return None

        _key, job_id_bytes = item
        job_id = job_id_bytes.decode()
        job_key = f"{_JOB_PREFIX}{job_id}"
        stored = await client.get(job_key)
        if stored is None:
            return None

        raw = stored.decode() if isinstance(stored, (bytes, bytearray)) else stored
        data = json.loads(raw)
        job = Job(
            id=data.get("id", job_id),
            type=JobType(data["type"]),
            payload=data.get("payload", {}),
            status=JobStatus(data.get("status", JobStatus.PENDING.value)),
            result=data.get("result"),
            error=data.get("error"),
        )
        job.status = JobStatus.RUNNING
        await client.set(job_key, job.model_dump_json().encode())
        return job

    async def mark_done(
        self, job: Job, result: Optional[dict] = None
    ) -> None:
        """Mark *job* as DONE and persist the *result*."""
        job.status = JobStatus.DONE
        job.result = result
        client = self._client
        job_key = f"{_JOB_PREFIX}{job.id}"
        await client.set(job_key, job.model_dump_json().encode())

    async def mark_failed(self, job: Job, error: str) -> None:
        """Mark *job* as FAILED and persist the *error* message."""
        job.status = JobStatus.FAILED
        job.error = error
        client = self._client
        job_key = f"{_JOB_PREFIX}{job.id}"
        await client.set(job_key, job.model_dump_json().encode())

    async def get_status(self, job_id: str) -> Optional[Job]:
        """Return the :class:`Job` for *job_id*, or ``None`` if not found."""
        client = self._client
        job_key = f"{_JOB_PREFIX}{job_id}"
        stored = await client.get(job_key)
        if stored is None:
            return None

        raw = stored.decode() if isinstance(stored, (bytes, bytearray)) else stored
        data = json.loads(raw)
        return Job(
            id=data.get("id", job_id),
            type=JobType(data["type"]),
            payload=data.get("payload", {}),
            status=JobStatus(data.get("status", JobStatus.PENDING.value)),
            result=data.get("result"),
            error=data.get("error"),
        )
