"""Shared Python types for ForgeStream API."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, EmailStr


class AuthProvider(str, Enum):
    GITHUB = "github"
    EMAIL = "email"


class LLMProviderName(str, Enum):
    OPENAI = "openai"
    CLAUDE = "claude"
    GEMINI = "gemini"


class User(BaseModel):
    id: str
    email: EmailStr
    name: str
    avatar_url: str | None = None
    provider: AuthProvider
    created_at: datetime
    updated_at: datetime


class LLMRequest(BaseModel):
    provider: LLMProviderName
    model: str
    prompt: str
    max_tokens: int | None = None
    temperature: float | None = None


class TokenUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class LLMResponse(BaseModel):
    provider: LLMProviderName
    model: str
    content: str
    usage: TokenUsage


class ApiError(BaseModel):
    detail: str
    status_code: int
