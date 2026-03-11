"""Standalone async worker process entry-point.

Usage (from repo root):
    python -m app.workers.entrypoint

Or via Docker:
    CMD ["python", "-m", "app.workers.entrypoint"]

Environment variables
---------------------
WORKER_CONCURRENCY : int  (default 4)  – number of parallel worker coroutines
REDIS_HOST, REDIS_PORT, REDIS_DB       – Redis connection (see RedisSettings).
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal

from app.config import RedisSettings
from app.schemas.jobs import JobType
from app.workers.job_queue import JobQueue
from app.workers.worker import Worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

_CONCURRENCY = int(os.getenv("WORKER_CONCURRENCY", "4"))


async def main() -> None:
    redis_settings = RedisSettings()
    queue = JobQueue(redis_settings.host, redis_settings.port, redis_settings.db)
    await queue.connect()
    logger.info("Redis connected at %s:%d", redis_settings.host, redis_settings.port)

    worker = Worker(queue)

    # Register default no-op handlers; real handlers are wired elsewhere
    # (e.g. via app.workers.registry once the service layer grows).
    async def _noop(payload: dict) -> dict:
        logger.info(
            "Received job — no handler registered yet (payload has %d field(s))",
            len(payload),
        )
        return {}

    for jt in JobType:
        worker.register(jt, _noop)

    loop = asyncio.get_running_loop()

    def _stop() -> None:
        logger.info("Shutdown signal received — stopping worker")
        worker.stop()

    loop.add_signal_handler(signal.SIGTERM, _stop)
    loop.add_signal_handler(signal.SIGINT, _stop)

    tasks = [asyncio.create_task(worker.run()) for _ in range(_CONCURRENCY)]
    logger.info("Started %d worker coroutine(s)", _CONCURRENCY)
    try:
        await asyncio.gather(*tasks)
    finally:
        await queue.disconnect()
        logger.info("Redis disconnected")


if __name__ == "__main__":
    asyncio.run(main())
