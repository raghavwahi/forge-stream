from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# LLM provider base types
# ---------------------------------------------------------------------------


@dataclass
class ProviderResponse:
    """Structured response returned by every LLM provider."""

    text: str
    model: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0


class UsageRecord:
    """Tracks cumulative token usage across multiple LLM calls."""

    def __init__(self) -> None:
        self._total_tokens: int = 0
        self._total_requests: int = 0
        self.history: list[tuple[int, int]] = []

    def record(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.history.append((prompt_tokens, completion_tokens))
        self._total_tokens += prompt_tokens + completion_tokens
        self._total_requests += 1

    @property
    def total_tokens(self) -> int:
        return self._total_tokens

    @property
    def total_requests(self) -> int:
        return self._total_requests


class BaseProvider(ABC):
    """Abstract base class for all LLM providers."""

    provider_name: str

    def __init__(self) -> None:
        self.usage = UsageRecord()

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> ProviderResponse: ...

    def get_usage(self) -> dict[str, Any]:
        return {
            "total_tokens": self.usage.total_tokens,
            "total_requests": self.usage.total_requests,
        }


# ---------------------------------------------------------------------------
# Infrastructure provider ABCs
# ---------------------------------------------------------------------------


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
