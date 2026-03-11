"""Auto-router that selects the best LLM backend based on prompt complexity."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from app.providers.budget import BudgetGuard
from app.providers.config import ProviderConfig

logger = logging.getLogger(__name__)

# Keywords / patterns that hint at higher complexity
_COMPLEX_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(architect|design pattern|refactor|optimiz)\w*", re.I),
    re.compile(r"\b(explain|analy[sz]|debug|security|vulnerabilit)\w*", re.I),
    re.compile(r"\b(implement|algorithm|concurren|async)\w*", re.I),
    re.compile(r"\b(trade.?off|compare|contrast|pros?\s+and\s+cons?)\b", re.I),
]

_LONG_PROMPT_CHARS = 500
_HIGH_COMPLEXITY_SCORE = 3


@dataclass
class ProviderResponse:
    """Response from an LLM provider."""

    text: str
    model: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float


class UsageTracker:
    """Tracks token usage across provider calls."""

    def __init__(self) -> None:
        self._prompt_tokens: int = 0
        self._completion_tokens: int = 0

    def record(self, prompt_tokens: int, completion_tokens: int) -> None:
        self._prompt_tokens += prompt_tokens
        self._completion_tokens += completion_tokens

    @property
    def total_tokens(self) -> int:
        return self._prompt_tokens + self._completion_tokens


def estimate_complexity(prompt: str) -> int:
    """Return an integer complexity score for *prompt*.

    Scoring heuristic
    -----------------
    * +1 for every complex-keyword pattern that matches (capped at 4)
    * +1 if prompt length > 500 chars
    * +1 if prompt contains a code fence
    * +1 if prompt contains multiple questions (``?``)
    """
    score = 0
    keyword_hits = sum(1 for pat in _COMPLEX_PATTERNS if pat.search(prompt))
    score += min(keyword_hits, 4)

    if len(prompt) > _LONG_PROMPT_CHARS:
        score += 1

    if "```" in prompt:
        score += 1

    if prompt.count("?") >= 2:
        score += 1

    return score


class AutoRouter:
    """Meta-provider that routes prompts to the best backend based on
    estimated complexity.

    Routing logic
    -------------
    * **High complexity** (score >= 3) → Anthropic → OpenAI fallback
    * **Medium complexity** (score >= 1) → OpenAI → Gemini fallback
    * **Low complexity** (score == 0) → Gemini → OpenAI fallback
    * **Ultimate fallback** → Ollama (local)

    Provider packages are imported lazily so this module can be imported
    even when cloud-provider SDK packages are not installed.
    """

    provider_name = "auto"

    def __init__(
        self,
        config: ProviderConfig | None = None,
        budget: BudgetGuard | None = None,
    ) -> None:
        self._config = config or ProviderConfig()
        self._budget = budget or BudgetGuard(
            max_tokens=self._config.budget_max_tokens,
            max_requests=self._config.budget_max_requests,
        )
        self.usage = UsageTracker()
        self._providers: dict[str, Any] = {}
        self._build_providers()

    def _build_providers(self) -> None:
        """Populate _providers with available providers (lazily imported)."""
        if self._config.openai_api_key:
            try:
                from app.providers.openai_provider import OpenAIProvider

                self._providers["openai"] = OpenAIProvider(self._config)
            except Exception:
                self._providers["openai"] = None

        if self._config.anthropic_api_key:
            try:
                from app.providers.anthropic_provider import AnthropicProvider

                self._providers["anthropic"] = AnthropicProvider(self._config)
            except Exception:
                self._providers["anthropic"] = None

        if self._config.gemini_api_key:
            try:
                from app.providers.gemini_provider import GeminiProvider

                self._providers["gemini"] = GeminiProvider(self._config)
            except Exception:
                self._providers["gemini"] = None

        # Ollama is always available as a local fallback
        try:
            from app.providers.ollama_provider import OllamaProvider

            self._providers["ollama"] = OllamaProvider(self._config)
        except Exception:
            self._providers["ollama"] = None

    def _select_provider(self, prompt: str) -> Any:
        """Choose a provider for *prompt* based on complexity score."""
        score = estimate_complexity(prompt)
        logger.info("Auto routing – complexity score=%d", score)

        if score >= _HIGH_COMPLEXITY_SCORE:
            if "anthropic" in self._providers:
                return self._providers["anthropic"]
            if "openai" in self._providers:
                return self._providers["openai"]
        elif score >= 1:
            if "openai" in self._providers:
                return self._providers["openai"]
            if "gemini" in self._providers:
                return self._providers["gemini"]
        else:
            if "gemini" in self._providers:
                return self._providers["gemini"]
            if "openai" in self._providers:
                return self._providers["openai"]

        return self._providers.get("ollama")

    async def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> ProviderResponse:
        """Generate a response using the best available provider."""
        self._budget.check()

        provider = self._select_provider(prompt)
        response: ProviderResponse = await provider.generate(
            prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        self._budget.record(response.total_tokens)
        self.usage.record(response.prompt_tokens, response.completion_tokens)

        return response
