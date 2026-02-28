from pydantic_settings import BaseSettings


class ProviderConfig(BaseSettings):
    """Configuration for LLM providers, loaded from environment variables."""

    model_config = {"env_prefix": "LLM_"}

    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"

    # Budget guard defaults
    budget_max_tokens: int = 1_000_000
    budget_max_requests: int = 10_000

    # Default models
    openai_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    gemini_model: str = "gemini-1.5-flash"
    ollama_model: str = "llama3"
