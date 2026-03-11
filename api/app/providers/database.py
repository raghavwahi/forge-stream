from typing import Any

import asyncpg

from app.providers.base import BaseDatabaseProvider


class DatabaseProvider(BaseDatabaseProvider):
    def __init__(self, dsn: str, min_size: int = 5, max_size: int = 20) -> None:
        self._dsn = dsn
        self._min_size = min_size
        self._max_size = max_size
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(
            self._dsn, min_size=self._min_size, max_size=self._max_size
        )

    async def disconnect(self) -> None:
        if self._pool:
            await self._pool.close()

    async def fetch_one(self, query: str, *args: Any) -> dict | None:
        if self._pool is None:
            raise RuntimeError("DatabaseProvider is not connected")
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None

    async def fetch_all(self, query: str, *args: Any) -> list[dict]:
        if self._pool is None:
            raise RuntimeError("DatabaseProvider is not connected")
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(r) for r in rows]

    async def execute(self, query: str, *args: Any) -> str:
        if self._pool is None:
            raise RuntimeError("DatabaseProvider is not connected")
        async with self._pool.acquire() as conn:
            return await conn.execute(query, *args)
