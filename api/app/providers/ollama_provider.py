from __future__ import annotations

import time

import backoff
import httpx
from api.app.providers.base import BaseProvider, ProviderResponse
from api.app.providers.config import ProviderConfig


class OllamaProvider(BaseProvider):
    """Local Ollama provider — calls the Ollama HTTP API."""

    provider_name = "ollama"

    def __init__(self, config: ProviderConfig | None = None) -> None:
        super().__init__()
        self._config = config or ProviderConfig()
        self._base_url = self._config.ollama_base_url.rstrip("/")

    @backoff.on_exception(
        backoff.expo,
        (httpx.ConnectError, httpx.TimeoutException),
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
        model = model or self._config.ollama_model
        start = time.perf_counter()

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self._base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    },
                },
            )
            resp.raise_for_status()
            data = resp.json()

        latency = (time.perf_counter() - start) * 1000

        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)
        total_tokens = prompt_tokens + completion_tokens

        self.usage.record(prompt_tokens, completion_tokens)

        return ProviderResponse(
            text=data.get("response", ""),
            model=model,
            provider=self.provider_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency,
        )
