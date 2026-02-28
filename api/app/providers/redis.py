import redis.asyncio as aioredis

from app.providers.base import BaseCacheProvider


class RedisProvider(BaseCacheProvider):
    def __init__(self, host: str, port: int, db: int = 0) -> None:
        self._host = host
        self._port = port
        self._db = db
        self._client: aioredis.Redis | None = None

    async def connect(self) -> None:
        self._client = aioredis.Redis(
            host=self._host, port=self._port, db=self._db
        )
        await self._client.ping()

    async def disconnect(self) -> None:
        if self._client:
            await self._client.close()

    async def get(self, key: str) -> str | None:
        assert self._client is not None
        val = await self._client.get(key)
        return val.decode() if val else None

    async def set(
        self, key: str, value: str, expire_seconds: int | None = None
    ) -> None:
        assert self._client is not None
        if expire_seconds:
            await self._client.set(key, value, ex=expire_seconds)
        else:
            await self._client.set(key, value)

    async def incr(self, key: str) -> int:
        assert self._client is not None
        return await self._client.incr(key)

    async def expire(self, key: str, seconds: int) -> None:
        assert self._client is not None
        await self._client.expire(key, seconds)

    async def delete(self, key: str) -> None:
        assert self._client is not None
        await self._client.delete(key)
