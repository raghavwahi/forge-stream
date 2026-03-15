"""Standalone async worker process entry-point.

Usage (from repo root):
    python -m app.workers.entrypoint

Or via Docker:
    CMD ["python", "-m", "app.workers.entrypoint"]

Environment variables
---------------------
WORKER_CONCURRENCY : int  (default 4)  – number of parallel worker coroutines
All standard ForgeStream env vars (DB_HOST, REDIS_HOST, …) are required.
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal

from app.config import get_settings
from app.providers.redis import RedisProvider
from app.workers.job_queue import JobQueue
from app.workers.worker import Worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

_CONCURRENCY = int(os.getenv("WORKER_CONCURRENCY", "4"))


async def _build_worker() -> Worker:
    """Initialise providers and return a fully wired Worker."""
    settings = get_settings()
    redis = RedisProvider(
        settings.redis.host, settings.redis.port, settings.redis.db
    )
    await redis.connect()
    logger.info("Redis connected at %s:%d", settings.redis.host, settings.redis.port)

    queue = JobQueue(redis)
    worker = Worker(queue)

    # Register default no-op handlers; real handlers are wired in the API
    # and will be plugged in via app.workers.registry once the service layer grows.
    from app.schemas.jobs import JobType  # noqa: PLC0415

    async def _noop(payload: dict) -> dict:
        logger.info("Received job with payload %s — no handler registered yet", payload)
        return {}

    for jt in JobType:
        worker.register(jt, _noop)

    return worker


async def main() -> None:
    loop = asyncio.get_running_loop()
    worker = await _build_worker()

    # Graceful shutdown on SIGTERM / SIGINT
    def _stop(_sig, _frame):
        logger.info("Shutdown signal received — stopping worker")
        worker.stop()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    tasks = [asyncio.create_task(worker.run()) for _ in range(_CONCURRENCY)]
    logger.info("Started %d worker coroutine(s)", _CONCURRENCY)
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
