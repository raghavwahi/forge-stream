from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)


class BudgetExceededError(Exception):
    """Raised when the token or request budget is exhausted."""


class BudgetGuard:
    """Thread-safe budget tracker that prevents excessive LLM usage.

    Parameters
    ----------
    max_tokens:
        Maximum cumulative tokens allowed across all providers.
    max_requests:
        Maximum cumulative requests allowed across all providers.
    """

    def __init__(
        self,
        max_tokens: int = 1_000_000,
        max_requests: int = 10_000,
    ) -> None:
        self._max_tokens = max_tokens
        self._max_requests = max_requests
        self._total_tokens = 0
        self._total_requests = 0
        self._lock = threading.Lock()

    # -- public API -----------------------------------------------------------

    def check(self) -> None:
        """Raise ``BudgetExceededError`` if budget is exhausted."""
        with self._lock:
            if self._total_tokens >= self._max_tokens:
                raise BudgetExceededError(
                    f"Token budget exhausted: "
                    f"{self._total_tokens}/{self._max_tokens}"
                )
            if self._total_requests >= self._max_requests:
                raise BudgetExceededError(
                    f"Request budget exhausted: "
                    f"{self._total_requests}/{self._max_requests}"
                )

    def record(self, tokens: int) -> None:
        """Record token usage and increment request count."""
        with self._lock:
            self._total_tokens += tokens
            self._total_requests += 1
            remaining_tokens = self._max_tokens - self._total_tokens
            if remaining_tokens < self._max_tokens * 0.1:
                logger.warning(
                    "Budget warning: only %d tokens remaining out of %d",
                    remaining_tokens,
                    self._max_tokens,
                )

    def get_status(self) -> dict:
        """Return current budget status."""
        with self._lock:
            return {
                "total_tokens_used": self._total_tokens,
                "max_tokens": self._max_tokens,
                "total_requests_used": self._total_requests,
                "max_requests": self._max_requests,
                "tokens_remaining": self._max_tokens - self._total_tokens,
                "requests_remaining": self._max_requests - self._total_requests,
            }

    def reset(self) -> None:
        """Reset all counters to zero."""
        with self._lock:
            self._total_tokens = 0
            self._total_requests = 0
