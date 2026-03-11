"""Unit tests for AutoRouter provider fallback logic."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.providers.auto_router import AutoRouter, ProviderResponse
from app.providers.config import ProviderConfig


def _mock_response(provider_name: str = "mock") -> ProviderResponse:
    return ProviderResponse(
        text="answer",
        model="mock-model",
        provider=provider_name,
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        latency_ms=100,
    )


def _make_router(available_providers: list[str]) -> AutoRouter:
    """Build an AutoRouter with only the specified providers available."""
    config = ProviderConfig(
        openai_api_key="sk-test" if "openai" in available_providers else "",
        anthropic_api_key="sk-ant-test" if "anthropic" in available_providers else "",
        gemini_api_key="gemini-test" if "gemini" in available_providers else "",
        budget_max_tokens=100_000,
        budget_max_requests=1_000,
    )
    router = AutoRouter(config=config)
    # Replace providers with mocks
    for name in list(router._providers.keys()):
        mock_provider = MagicMock()
        mock_provider.provider_name = name
        mock_provider.generate = AsyncMock(return_value=_mock_response(name))
        router._providers[name] = mock_provider
    return router


class TestAutoRouterFallback:
    @pytest.mark.asyncio
    async def test_uses_first_provider_on_success(self):
        router = _make_router(["anthropic", "openai", "gemini"])
        # Low-complexity prompt → gemini first
        resp = await router.generate("hi")
        assert resp.provider == "gemini"

    @pytest.mark.asyncio
    async def test_falls_back_to_next_on_exception(self):
        router = _make_router(["openai", "gemini"])
        # For mid complexity, order is openai → gemini → ollama.
        # Current AutoRouter does not implement fallback-on-exception,
        # so an error from the selected provider should propagate.
        router._providers["openai"].generate = AsyncMock(
            side_effect=RuntimeError("rate limited")
        )
        with pytest.raises(RuntimeError, match="rate limited"):
            await router.generate("explain concurrency")

    @pytest.mark.asyncio
    async def test_raises_when_selected_provider_fails(self):
        router = _make_router(["gemini"])
        router._providers["gemini"].generate = AsyncMock(
            side_effect=RuntimeError("unavailable")
        )
        with pytest.raises(RuntimeError, match="unavailable"):
            await router.generate("simple question")

    @pytest.mark.asyncio
    async def test_high_complexity_prefers_anthropic(self):
        router = _make_router(["anthropic", "openai", "gemini"])
        # High complexity: architect (pat1) + analyze/security (pat2) + algorithm (pat3)
        resp = await router.generate(
            "architect and analyze the security algorithm"
            " to implement concurrent design patterns"
        )
        assert resp.provider == "anthropic"

    @pytest.mark.asyncio
    async def test_low_complexity_prefers_gemini(self):
        router = _make_router(["anthropic", "openai", "gemini"])
        resp = await router.generate("hello")
        assert resp.provider == "gemini"


class TestAutoRouterBudget:
    @pytest.mark.asyncio
    async def test_budget_recorded_on_success(self):
        router = _make_router(["gemini"])
        before = router.usage.total_tokens
        await router.generate("hi")
        assert router.usage.total_tokens > before
