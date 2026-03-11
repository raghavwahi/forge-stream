"""
Retry logic for LLM calls with invalid JSON responses.

Uses exponential backoff and includes validation error context
in retry prompts to help the LLM self-correct.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Type, TypeVar

from pydantic import BaseModel

from app.providers.validation import LLMResponseValidator

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_json_retries: int = 3,
        initial_backoff_seconds: float = 1.0,
        backoff_multiplier: float = 2.0,
        max_backoff_seconds: float = 30.0,
    ):
        self.max_json_retries = max_json_retries
        self.initial_backoff_seconds = initial_backoff_seconds
        self.backoff_multiplier = backoff_multiplier
        self.max_backoff_seconds = max_backoff_seconds


class LLMRetryHandler:
    """
    Handles retry logic for LLM calls that require validated JSON output.

    Retries on:
    - JSON parse errors (after attempting automatic repair)
    - Schema validation errors (with error context in the retry prompt)
    - Includes exponential backoff between retries
    """

    def __init__(self, config: RetryConfig | None = None):
        self.config = config or RetryConfig()

    async def call_with_validation_retry(
        self,
        llm_call: Callable[[str], Awaitable[str]],
        prompt: str,
        schema: Type[T],
        error_instruction: str = (
            "Your previous response had JSON validation errors. "
            "Respond with ONLY valid JSON matching the required schema — "
            "no prose, no markdown fences, no extra keys."
        ),
    ) -> T:
        """
        Call an async LLM function with automatic retry on JSON/schema errors.

        Args:
            llm_call: Async callable taking a prompt string and returning response text.
            prompt: The initial prompt.
            schema: Pydantic model class to validate against.
            error_instruction: Instruction prepended to each retry prompt.

        Returns:
            Validated Pydantic model instance.

        Raises:
            ValueError: If all retries are exhausted.
        """
        last_error: str | None = None
        last_response: str | None = None
        current_prompt = prompt

        for attempt in range(self.config.max_json_retries + 1):
            if attempt > 0:
                wait = min(
                    self.config.initial_backoff_seconds
                    * (self.config.backoff_multiplier ** (attempt - 1)),
                    self.config.max_backoff_seconds,
                )
                logger.warning(
                    "LLM JSON validation failed (attempt %d/%d) – retrying in %.1fs. Error: %s",
                    attempt,
                    self.config.max_json_retries + 1,
                    wait,
                    last_error,
                )
                await asyncio.sleep(wait)

                # Build a retry prompt that includes the error context
                prev_snippet = (str(last_response or "")[:300]).replace("\n", " ")
                current_prompt = (
                    f"{error_instruction}\n\n"
                    f"Error from your last response: {last_error}\n\n"
                    f"Your previous response (truncated): {prev_snippet}\n\n"
                    f"--- Original request ---\n{prompt}"
                )

            try:
                response_text = await llm_call(current_prompt)
                result = LLMResponseValidator.validate_with_repair(response_text, schema)
                if result.success:
                    if attempt > 0:
                        logger.info(
                            "LLM call succeeded on attempt %d/%d after retry",
                            attempt + 1,
                            self.config.max_json_retries + 1,
                        )
                    return result.model  # type: ignore[return-value]
                else:
                    last_error = result.error
                    last_response = response_text
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                last_response = None
                logger.error(
                    "LLM call raised unexpected exception on attempt %d: %s",
                    attempt + 1,
                    type(exc).__name__,
                )

        raise ValueError(
            f"LLM call failed after {self.config.max_json_retries + 1} attempts. "
            f"Last error: {last_error}"
        )
