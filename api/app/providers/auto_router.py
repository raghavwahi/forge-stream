"""AutoRouter: complexity-based routing with cascading provider fallback.

Extends AutoProvider by catching provider-level exceptions and trying
the next eligible provider in a deterministic fallback chain before
ultimately reaching the local Ollama instance.
"""
from __future__ import annotations

import asyncio
import logging

from api.app.providers.auto import (
    _HIGH_COMPLEXITY_SCORE,
    AutoProvider,
    estimate_complexity,
)
from api.app.providers.base import BaseProvider, ProviderResponse
from api.app.providers.budget import BudgetGuard
from api.app.providers.config import ProviderConfig

logger = logging.getLogger(__name__)


class AutoRouter(AutoProvider):
    """AutoProvider subclass with cascading fallback on provider errors.

    Routing order (high → low complexity, with fallback on exception):
    - High  (score ≥ 3): anthropic → openai[gpt-4o] → gemini → ollama
    - Mid   (score ≥ 1): openai → gemini → anthropic → ollama
    - Low   (score == 0): gemini → openai → anthropic → ollama
    """

    def __init__(
        self,
        config: ProviderConfig | None = None,
        budget: BudgetGuard | None = None,
    ) -> None:
        super().__init__(config=config, budget=budget)

    def _fallback_chain(self, prompt: str) -> list[tuple[BaseProvider, str | None]]:
        """Return an ordered list of (provider, model_override) pairs to try."""
        score = estimate_complexity(prompt)
        has = self._providers.__contains__

        if score >= _HIGH_COMPLEXITY_SCORE:
            order = ["anthropic", "openai", "gemini", "ollama"]
            model_overrides = {"openai": "gpt-4o"}
        elif score >= 1:
            order = ["openai", "gemini", "anthropic", "ollama"]
            model_overrides = {}
        else:
            order = ["gemini", "openai", "anthropic", "ollama"]
            model_overrides = {}

        return [
            (self._providers[name], model_overrides.get(name))
            for name in order
            if has(name)
        ]

    async def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> ProviderResponse:
        self._budget.check()

        chain = self._fallback_chain(prompt)
        last_exc: Exception | None = None

        for provider, auto_model in chain:
            effective_model = model or auto_model
            logger.info(
                "AutoRouter trying provider=%s model=%s",
                provider.provider_name,
                effective_model or "default",
            )
            try:
                response = await provider.generate(
                    prompt,
                    model=effective_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                self._budget.record(response.total_tokens)
                self.usage.record(response.prompt_tokens, response.completion_tokens)
                return response
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                # Record this failed attempt so it still consumes request budget.
                self._budget.record(0)
                logger.warning(
                    "Provider %s failed (%s), trying next in chain",
                    provider.provider_name,
                    type(exc).__name__,
                )
                last_exc = exc

        raise RuntimeError(
            "All providers in the fallback chain failed"
        ) from last_exc
