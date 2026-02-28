from __future__ import annotations

import abc
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProviderResponse:
    """Standard response returned by every provider."""

    text: str
    model: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0


@dataclass
class UsageRecord:
    """Accumulated usage for a single provider instance."""

    total_tokens: int = 0
    total_requests: int = 0
    history: list[dict] = field(default_factory=list)

    def record(self, prompt_tokens: int, completion_tokens: int) -> None:
        total = prompt_tokens + completion_tokens
        self.total_tokens += total
        self.total_requests += 1
        self.history.append(
            {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total,
                "timestamp": time.time(),
            }
        )


class BaseProvider(abc.ABC):
    """Abstract base class that every LLM provider must implement."""

    provider_name: str = "base"

    def __init__(self) -> None:
        self.usage = UsageRecord()

    @abc.abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> ProviderResponse:
        """Generate a completion for the given prompt."""

    def get_usage(self) -> dict:
        """Return accumulated token usage statistics."""
        return {
            "provider": self.provider_name,
            "total_tokens": self.usage.total_tokens,
            "total_requests": self.usage.total_requests,
        }


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
