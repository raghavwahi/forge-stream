from __future__ import annotations

import logging
import re

from api.app.providers.anthropic_provider import AnthropicProvider
from api.app.providers.base import BaseProvider, ProviderResponse
from api.app.providers.budget import BudgetGuard
from api.app.providers.config import ProviderConfig
from api.app.providers.gemini_provider import GeminiProvider
from api.app.providers.ollama_provider import OllamaProvider
from api.app.providers.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)

# Keywords / patterns that hint at higher complexity
_COMPLEX_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(architect|design pattern|refactor|optimiz)\w*", re.I),
    re.compile(r"\b(explain|analy[sz]|debug|security|vulnerabilit)\w*", re.I),
    re.compile(r"\b(implement|algorithm|concurren|async)\w*", re.I),
    re.compile(r"\b(trade.?off|compare|contrast|pros?\s+and\s+cons?)\b", re.I),
]

# Complexity thresholds
_LONG_PROMPT_CHARS = 500
_HIGH_COMPLEXITY_SCORE = 3


def estimate_complexity(prompt: str) -> int:
    """Return an integer complexity score for *prompt*.

    Scoring heuristic
    -----------------
    * +1 for every complex-keyword match (capped at 4)
    * +1 if prompt length > 500 chars
    * +1 if prompt contains a code fence
    * +1 if prompt contains multiple questions (``?``)
    """
    score = 0
    keyword_hits = sum(
        1 for pat in _COMPLEX_PATTERNS if pat.search(prompt)
    )
    score += min(keyword_hits, 4)

    if len(prompt) > _LONG_PROMPT_CHARS:
        score += 1

    if "```" in prompt:
        score += 1

    if prompt.count("?") >= 2:
        score += 1

    return score


class AutoProvider(BaseProvider):
    """Meta-provider that routes prompts to the best backend based on
    estimated complexity.

    Routing logic
    -------------
    * **High complexity** (score >= 3) → Anthropic Claude 3.5 Sonnet
    * **Medium complexity** (score >= 1) → OpenAI GPT-4o-mini
    * **Low complexity** (score == 0) → Gemini 1.5 Flash

    If a cloud provider is not configured (missing API key), the router
    gracefully falls back to Ollama (local).
    """

    provider_name = "auto"

    def __init__(
        self,
        config: ProviderConfig | None = None,
        budget: BudgetGuard | None = None,
    ) -> None:
        super().__init__()
        self._config = config or ProviderConfig()
        self._budget = budget or BudgetGuard(
            max_tokens=self._config.budget_max_tokens,
            max_requests=self._config.budget_max_requests,
        )

        # Eagerly build provider map so we can check availability
        self._providers: dict[str, BaseProvider] = {}
        if self._config.openai_api_key:
            self._providers["openai"] = OpenAIProvider(self._config)
        if self._config.anthropic_api_key:
            self._providers["anthropic"] = AnthropicProvider(self._config)
        if self._config.gemini_api_key:
            self._providers["gemini"] = GeminiProvider(self._config)
        # Ollama is always available as a local fallback
        self._providers["ollama"] = OllamaProvider(self._config)

    @property
    def budget(self) -> BudgetGuard:
        return self._budget

    def _select_provider(self, prompt: str) -> tuple[BaseProvider, str | None]:
        """Choose a provider and optional model override for *prompt*."""
        score = estimate_complexity(prompt)
        logger.info("Auto routing – complexity score=%d", score)

        if score >= _HIGH_COMPLEXITY_SCORE:
            if "anthropic" in self._providers:
                return self._providers["anthropic"], None
            if "openai" in self._providers:
                return self._providers["openai"], "gpt-4o"
        elif score >= 1:
            if "openai" in self._providers:
                return self._providers["openai"], None
            if "gemini" in self._providers:
                return self._providers["gemini"], None
        else:
            if "gemini" in self._providers:
                return self._providers["gemini"], None
            if "openai" in self._providers:
                return self._providers["openai"], None

        return self._providers["ollama"], None

    async def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> ProviderResponse:
        # Budget check before making any call
        self._budget.check()

        provider, auto_model = self._select_provider(prompt)
        effective_model = model or auto_model

        logger.info(
            "Auto selected provider=%s model=%s",
            provider.provider_name,
            effective_model or "default",
        )

        response = await provider.generate(
            prompt,
            model=effective_model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Record in both the delegate's tracker and the budget guard
        self._budget.record(response.total_tokens)
        self.usage.record(response.prompt_tokens, response.completion_tokens)

        return response
