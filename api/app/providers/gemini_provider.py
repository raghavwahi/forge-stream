from __future__ import annotations

import time

import backoff
import google.generativeai as genai
from api.app.providers.base import BaseProvider, ProviderResponse
from api.app.providers.config import ProviderConfig


class GeminiProvider(BaseProvider):
    """Google Gemini API provider."""

    provider_name = "gemini"

    def __init__(self, config: ProviderConfig | None = None) -> None:
        super().__init__()
        self._config = config or ProviderConfig()
        genai.configure(api_key=self._config.gemini_api_key)

    @backoff.on_exception(
        backoff.expo,
        Exception,
        max_tries=5,
        giveup=lambda e: "rate" not in str(e).lower(),
    )
    async def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> ProviderResponse:
        model_name = model or self._config.gemini_model
        start = time.perf_counter()

        gen_model = genai.GenerativeModel(model_name)
        response = await gen_model.generate_content_async(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )

        latency = (time.perf_counter() - start) * 1000

        prompt_tokens = 0
        completion_tokens = 0
        if response.usage_metadata:
            prompt_tokens = response.usage_metadata.prompt_token_count or 0
            completion_tokens = (
                response.usage_metadata.candidates_token_count or 0
            )
        total_tokens = prompt_tokens + completion_tokens

        self.usage.record(prompt_tokens, completion_tokens)

        return ProviderResponse(
            text=response.text or "",
            model=model_name,
            provider=self.provider_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency,
        )
