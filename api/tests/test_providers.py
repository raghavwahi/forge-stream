"""Tests for the provider abstraction layer."""

import pytest
from api.app.providers.auto import AutoProvider, estimate_complexity
from api.app.providers.base import BaseProvider, ProviderResponse, UsageRecord
from api.app.providers.budget import BudgetExceededError, BudgetGuard
from api.app.providers.config import ProviderConfig

# ---------------------------------------------------------------------------
# ProviderConfig
# ---------------------------------------------------------------------------


class TestProviderConfig:
    def test_defaults(self):
        cfg = ProviderConfig(
            openai_api_key="",
            anthropic_api_key="",
            gemini_api_key="",
        )
        assert cfg.ollama_base_url == "http://localhost:11434"
        assert cfg.openai_model == "gpt-4o-mini"
        assert cfg.budget_max_tokens == 1_000_000

    def test_custom_values(self):
        cfg = ProviderConfig(
            openai_api_key="sk-test",
            budget_max_tokens=500,
        )
        assert cfg.openai_api_key == "sk-test"
        assert cfg.budget_max_tokens == 500


# ---------------------------------------------------------------------------
# UsageRecord
# ---------------------------------------------------------------------------


class TestUsageRecord:
    def test_record_accumulates(self):
        rec = UsageRecord()
        rec.record(10, 20)
        rec.record(30, 40)
        assert rec.total_tokens == 100  # (10+20) + (30+40)
        assert rec.total_requests == 2
        assert len(rec.history) == 2


# ---------------------------------------------------------------------------
# BaseProvider (abstract – verify interface)
# ---------------------------------------------------------------------------


class TestBaseProvider:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            BaseProvider()

    def test_concrete_subclass(self):
        class Dummy(BaseProvider):
            provider_name = "dummy"

            async def generate(self, prompt, **kw):
                return ProviderResponse(
                    text="ok", model="m", provider="dummy"
                )

        d = Dummy()
        assert d.provider_name == "dummy"
        assert d.get_usage()["total_tokens"] == 0


# ---------------------------------------------------------------------------
# BudgetGuard
# ---------------------------------------------------------------------------


class TestBudgetGuard:
    def test_under_budget_passes(self):
        bg = BudgetGuard(max_tokens=100, max_requests=10)
        bg.check()  # should not raise
        bg.record(50)
        bg.check()  # still fine

    def test_token_limit_exceeded(self):
        bg = BudgetGuard(max_tokens=100, max_requests=10)
        bg.record(100)
        with pytest.raises(BudgetExceededError, match="Token budget"):
            bg.check()

    def test_request_limit_exceeded(self):
        bg = BudgetGuard(max_tokens=1_000_000, max_requests=2)
        bg.record(1)
        bg.record(1)
        with pytest.raises(BudgetExceededError, match="Request budget"):
            bg.check()

    def test_reset(self):
        bg = BudgetGuard(max_tokens=100, max_requests=10)
        bg.record(100)
        bg.reset()
        bg.check()  # should pass after reset

    def test_get_status(self):
        bg = BudgetGuard(max_tokens=1000, max_requests=10)
        bg.record(200)
        status = bg.get_status()
        assert status["total_tokens_used"] == 200
        assert status["tokens_remaining"] == 800
        assert status["total_requests_used"] == 1


# ---------------------------------------------------------------------------
# estimate_complexity
# ---------------------------------------------------------------------------


class TestEstimateComplexity:
    def test_simple_prompt(self):
        score = estimate_complexity("Hello, how are you?")
        assert score == 0

    def test_complex_keywords(self):
        prompt = "Explain the architecture and design patterns for this system"
        score = estimate_complexity(prompt)
        assert score >= 2  # at least 'architect' and 'explain'

    def test_long_prompt_adds_point(self):
        prompt = "Tell me about cats. " * 50  # well over 500 chars
        score = estimate_complexity(prompt)
        assert score >= 1

    def test_code_fence_adds_point(self):
        prompt = "Fix this:\n```python\nprint('hello')\n```"
        score = estimate_complexity(prompt)
        assert score >= 1

    def test_multiple_questions(self):
        prompt = "What is X? How does Y work? Why is Z important?"
        score = estimate_complexity(prompt)
        assert score >= 1

    def test_highly_complex_prompt(self):
        prompt = (
            "Analyze the security vulnerabilities in the following "
            "architecture and explain the optimization trade-offs. "
            "```python\nimport asyncio\n```\n"
            "What are the concurrency issues? How do we debug them?"
        )
        score = estimate_complexity(prompt)
        assert score >= 3  # should route to Anthropic


# ---------------------------------------------------------------------------
# AutoProvider routing (unit-level, no real API calls)
# ---------------------------------------------------------------------------


class TestAutoProviderRouting:
    def test_selects_anthropic_for_complex(self):
        """When Anthropic is configured, complex prompts route there."""
        cfg = ProviderConfig(
            openai_api_key="sk-test",
            anthropic_api_key="sk-ant-test",
            gemini_api_key="gem-test",
        )
        auto = AutoProvider(config=cfg)
        provider, _ = auto._select_provider(
            "Analyze the security vulnerabilities and explain "
            "the architecture trade-offs in this concurrent algorithm"
        )
        assert provider.provider_name == "anthropic"

    def test_selects_openai_for_medium(self):
        cfg = ProviderConfig(
            openai_api_key="sk-test",
            anthropic_api_key="sk-ant-test",
            gemini_api_key="gem-test",
        )
        auto = AutoProvider(config=cfg)
        provider, _ = auto._select_provider(
            "Explain how this function works"
        )
        assert provider.provider_name == "openai"

    def test_selects_gemini_for_simple(self):
        cfg = ProviderConfig(
            openai_api_key="sk-test",
            anthropic_api_key="sk-ant-test",
            gemini_api_key="gem-test",
        )
        auto = AutoProvider(config=cfg)
        provider, _ = auto._select_provider("Hello world")
        assert provider.provider_name == "gemini"

    def test_falls_back_to_ollama(self):
        """When no cloud keys are set, Ollama is the fallback."""
        cfg = ProviderConfig(
            openai_api_key="",
            anthropic_api_key="",
            gemini_api_key="",
        )
        auto = AutoProvider(config=cfg)
        provider, _ = auto._select_provider("Hello world")
        assert provider.provider_name == "ollama"

    def test_budget_guard_blocks(self):
        cfg = ProviderConfig(
            openai_api_key="",
            anthropic_api_key="",
            gemini_api_key="",
        )
        bg = BudgetGuard(max_tokens=0, max_requests=0)
        auto = AutoProvider(config=cfg, budget=bg)
        with pytest.raises(BudgetExceededError):
            import asyncio

            asyncio.get_event_loop().run_until_complete(
                auto.generate("test")
            )


# ---------------------------------------------------------------------------
# FastAPI endpoint tests
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    from api.app.main import app
    from fastapi.testclient import TestClient

    return TestClient(app)


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestBudgetEndpoint:
    def test_budget_status(self, client):
        resp = client.get("/budget")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_tokens_used" in data
        assert "max_tokens" in data
