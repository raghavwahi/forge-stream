import redis.asyncio as aioredis

from app.providers.base import BaseCacheProvider


class RedisProvider(BaseCacheProvider):
    def __init__(self, host: str, port: int, db: int = 0) -> None:
        self._host = host
        self._port = port
        self._db = db
        self._client: aioredis.Redis | None = None

    @property
    def client(self) -> aioredis.Redis:
        """Return the underlying aioredis client for advanced operations."""
        if self._client is None:
            raise RuntimeError("RedisProvider is not connected")
        return self._client

    async def connect(self) -> None:
        self._client = aioredis.Redis(
            host=self._host, port=self._port, db=self._db
        )
        await self._client.ping()

    async def disconnect(self) -> None:
        if self._client:
            await self._client.close()

    async def get(self, key: str) -> str | None:
        if self._client is None:
            raise RuntimeError("RedisProvider is not connected")
        val = await self._client.get(key)
        return val.decode() if val else None

    async def set(
        self, key: str, value: str, expire_seconds: int | None = None
    ) -> None:
        if self._client is None:
            raise RuntimeError("RedisProvider is not connected")
        if expire_seconds:
            await self._client.set(key, value, ex=expire_seconds)
        else:
            await self._client.set(key, value)

    async def incr(self, key: str) -> int:
        if self._client is None:
            raise RuntimeError("RedisProvider is not connected")
        return await self._client.incr(key)

    async def expire(self, key: str, seconds: int) -> None:
        if self._client is None:
            raise RuntimeError("RedisProvider is not connected")
        await self._client.expire(key, seconds)

    async def delete(self, key: str) -> None:
        if self._client is None:
            raise RuntimeError("RedisProvider is not connected")
        await self._client.delete(key)
