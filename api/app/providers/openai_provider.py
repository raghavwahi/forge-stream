from __future__ import annotations

import time

import backoff
import openai
from api.app.providers.base import BaseProvider, ProviderResponse
from api.app.providers.config import ProviderConfig


class OpenAIProvider(BaseProvider):
    """OpenAI API provider (GPT-4o, GPT-4o-mini, etc.)."""

    provider_name = "openai"

    def __init__(self, config: ProviderConfig | None = None) -> None:
        super().__init__()
        self._config = config or ProviderConfig()
        self._client = openai.AsyncOpenAI(api_key=self._config.openai_api_key)

    @backoff.on_exception(
        backoff.expo,
        (openai.RateLimitError, openai.APITimeoutError),
        max_tries=5,
    )
    async def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> ProviderResponse:
        model = model or self._config.openai_model
        start = time.perf_counter()

        response = await self._client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        latency = (time.perf_counter() - start) * 1000
        usage = response.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        total_tokens = usage.total_tokens if usage else 0

        self.usage.record(prompt_tokens, completion_tokens)

        return ProviderResponse(
            text=response.choices[0].message.content or "",
            model=model,
            provider=self.provider_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency,
        )
