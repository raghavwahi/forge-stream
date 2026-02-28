from abc import ABC, abstractmethod
from typing import Any


class BaseDatabaseProvider(ABC):
    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def fetch_one(self, query: str, *args: Any) -> dict | None: ...

    @abstractmethod
    async def fetch_all(self, query: str, *args: Any) -> list[dict]: ...

    @abstractmethod
    async def execute(self, query: str, *args: Any) -> str: ...


class BaseCacheProvider(ABC):
    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def get(self, key: str) -> str | None: ...

    @abstractmethod
    async def set(
        self, key: str, value: str, expire_seconds: int | None = None
    ) -> None: ...

    @abstractmethod
    async def incr(self, key: str) -> int: ...

    @abstractmethod
    async def expire(self, key: str, seconds: int) -> None: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...


class BaseEmailProvider(ABC):
    @abstractmethod
    async def send_email(
        self, to: str, subject: str, html_body: str
    ) -> None: ...


class BaseOAuthProvider(ABC):
    @abstractmethod
    def get_authorization_url(self, state: str) -> str: ...

    @abstractmethod
    async def exchange_code_for_token(self, code: str) -> dict: ...

    @abstractmethod
    async def get_user_info(self, access_token: str) -> dict: ...
