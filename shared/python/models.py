"""Shared Python types for ForgeStream API."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, EmailStr


class AuthProvider(str, Enum):
    GITHUB = "github"
    EMAIL = "email"


class LLMProviderName(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    OLLAMA = "ollama"


class User(BaseModel):
    id: str
    email: EmailStr
    name: str
    avatar_url: str | None = None
    provider: AuthProvider
    created_at: datetime
    updated_at: datetime


class LLMRequest(BaseModel):
    prompt: str
    model: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None


class TokenUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class LLMResponse(BaseModel):
    text: str
    model: str
    provider: LLMProviderName
    usage: TokenUsage
    latency_ms: float


class ApiError(BaseModel):
    detail: str
    status_code: int
