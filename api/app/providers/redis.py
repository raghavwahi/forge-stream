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

    def _get_client(self) -> aioredis.Redis:
        if self._client is None:
            raise RuntimeError(
                "RedisProvider client is not initialized. Call connect() before "
                "using cache operations."
            )
        return self._client

    async def get(self, key: str) -> str | None:
        client = self._get_client()
        val = await client.get(key)
        return val.decode() if val else None

    async def set(
        self, key: str, value: str, expire_seconds: int | None = None
    ) -> None:
        client = self._get_client()
        if expire_seconds:
            await client.set(key, value, ex=expire_seconds)
        else:
            await client.set(key, value)

    async def incr(self, key: str) -> int:
        client = self._get_client()
        return await client.incr(key)

    async def expire(self, key: str, seconds: int) -> None:
        client = self._get_client()
        await client.expire(key, seconds)

    async def delete(self, key: str) -> None:
        client = self._get_client()
        await client.delete(key)
