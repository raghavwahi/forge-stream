from __future__ import annotations

import time

import anthropic
import backoff
from api.app.providers.base import BaseProvider, ProviderResponse
from api.app.providers.config import ProviderConfig


class AnthropicProvider(BaseProvider):
    """Anthropic API provider (Claude 3.5 Sonnet, etc.)."""

    provider_name = "anthropic"

    def __init__(self, config: ProviderConfig | None = None) -> None:
        super().__init__()
        self._config = config or ProviderConfig()
        self._client = anthropic.AsyncAnthropic(
            api_key=self._config.anthropic_api_key,
        )

    @backoff.on_exception(
        backoff.expo,
        (anthropic.RateLimitError, anthropic.APITimeoutError),
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
        model = model or self._config.anthropic_model
        start = time.perf_counter()

        response = await self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )

        latency = (time.perf_counter() - start) * 1000
        prompt_tokens = response.usage.input_tokens
        completion_tokens = response.usage.output_tokens
        total_tokens = prompt_tokens + completion_tokens

        self.usage.record(prompt_tokens, completion_tokens)

        text = ""
        for block in response.content:
            if block.type == "text":
                text += block.text

        return ProviderResponse(
            text=text,
            model=model,
            provider=self.provider_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency,
        )
