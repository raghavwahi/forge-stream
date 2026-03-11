"""Redis-backed async job queue.

Extends :class:`~app.providers.redis.RedisProvider` with list-based
push/pop semantics so that enqueueing and dequeueing operations keep all
Redis client access within the provider hierarchy.
"""

from __future__ import annotations

import json
from typing import Any

from app.providers.redis import RedisProvider

_QUEUE_KEY = "forge:worker:jobs"


class JobQueue(RedisProvider):
    """Redis list queue used by the background worker."""

    async def enqueue(self, job_type: str, payload: dict[str, Any]) -> None:
        """Serialise *payload* and push it onto the tail of the queue."""
        if self._client is None:
            raise RuntimeError(
                "JobQueue not connected. Call connect() before enqueueing jobs."
            )
        message = json.dumps({"type": job_type, "payload": payload})
        await self._client.rpush(_QUEUE_KEY, message)

    async def dequeue(
        self, timeout: int = 2
    ) -> tuple[str, dict[str, Any]] | None:
        """Block for *timeout* seconds waiting for a job.

        Returns ``(job_type, payload)`` or ``None`` on timeout.
        """
        if self._client is None:
            raise RuntimeError(
                "JobQueue not connected. Call connect() before dequeueing jobs."
            )
        result = await self._client.blpop(_QUEUE_KEY, timeout=timeout)
        if result is None:
            return None
        _, raw = result
        data = json.loads(raw)
        return data["type"], data["payload"]
