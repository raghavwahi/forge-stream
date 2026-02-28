# Technical Specification

> Living document — updated as the system evolves.

---

## Table of Contents

1. [Database ERD](#database-erd)
2. [API Endpoints](#api-endpoints)
3. [LLM Provider Class Hierarchy](#llm-provider-class-hierarchy)

---

## Database ERD

The database schema below represents the **planned** data model. Tables will be implemented with SQLAlchemy and managed via Alembic migrations.

```
┌──────────────┐       ┌───────────────────┐       ┌──────────────────┐
│    users      │       │   conversations    │       │     messages      │
├──────────────┤       ├───────────────────┤       ├──────────────────┤
│ id       PK  │──┐    │ id            PK  │──┐    │ id           PK  │
│ email        │  │    │ user_id       FK  │  │    │ conversation_id FK│
│ password_hash│  └───>│ title             │  └───>│ role             │
│ created_at   │       │ llm_provider      │       │ content          │
│ updated_at   │       │ created_at        │       │ token_count      │
└──────────────┘       │ updated_at        │       │ created_at       │
                       └───────────────────┘       └──────────────────┘

Relationships
─────────────
users          1 ──< conversations     (one user has many conversations)
conversations  1 ──< messages           (one conversation has many messages)
```

### Key Constraints

| Table | Column | Constraint |
|-------|--------|-----------|
| `users` | `email` | `UNIQUE`, `NOT NULL` |
| `users` | `password_hash` | `NOT NULL` |
| `conversations` | `user_id` | `FOREIGN KEY → users.id ON DELETE CASCADE` |
| `conversations` | `llm_provider` | `NOT NULL`, defaults to `openai` |
| `messages` | `conversation_id` | `FOREIGN KEY → conversations.id ON DELETE CASCADE` |
| `messages` | `role` | `CHECK (role IN ('system', 'user', 'assistant'))` |

---

## API Endpoints

The FastAPI backend auto-generates interactive docs:

| Format | URL |
|--------|-----|
| Swagger UI | `http://localhost:8000/docs` |
| ReDoc | `http://localhost:8000/redoc` |
| OpenAPI JSON | `http://localhost:8000/openapi.json` |

### Current Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/health` | Liveness / readiness probe | None |

### Planned Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `POST` | `/auth/register` | Create a new user account | None |
| `POST` | `/auth/login` | Obtain JWT access + refresh tokens | None |
| `POST` | `/auth/refresh` | Rotate refresh token | Refresh token |
| `GET` | `/conversations` | List conversations for the current user | Bearer |
| `POST` | `/conversations` | Create a new conversation | Bearer |
| `GET` | `/conversations/{id}` | Retrieve a conversation with messages | Bearer |
| `DELETE` | `/conversations/{id}` | Delete a conversation | Bearer |
| `POST` | `/conversations/{id}/messages` | Send a message and stream the LLM reply | Bearer |

---

## LLM Provider Class Hierarchy

All LLM integrations share a common abstract interface so that new providers can be added without modifying consumer code.

```
                ┌─────────────────────┐
                │  BaseLLMProvider     │  (ABC)
                │─────────────────────│
                │ + model: str        │
                │ + temperature: float│
                │─────────────────────│
                │ + complete()        │  → str
                │ + stream()          │  → AsyncIterator[str]
                │ + count_tokens()    │  → int 
                └────────┬────────────┘
                         │
          ┌──────────────┼──────────────┐
          │              │              │
┌─────────▼────┐ ┌──────▼───────┐ ┌────▼──────────┐
│ OpenAIProvider│ │AnthropicProv.│ │OllamaProvider │
│──────────────│ │──────────────│ │───────────────│
│ api_key      │ │ api_key      │ │ base_url      │
│──────────────│ │──────────────│ │───────────────│
│ complete()   │ │ complete()   │ │ complete()    │
│ stream()     │ │ stream()     │ │ stream()      │
│ count_tokens()│ │ count_tokens()│ │ count_tokens()│
└──────────────┘ └──────────────┘ └───────────────┘
```

### Interface Definition (planned)

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator


class BaseLLMProvider(ABC):
    """Abstract base class for LLM provider integrations."""

    def __init__(self, model: str, temperature: float = 0.7):
        self.model = model
        self.temperature = temperature

    @abstractmethod
    async def complete(self, messages: list[dict]) -> str:
        """Return a full completion for the given message history."""
        ...

    @abstractmethod
    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        """Yield completion tokens as they arrive."""
        ...

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Return the token count for the given text."""
        ...
```

### Provider Details

| Provider | SDK | Models | Notes |
|----------|-----|--------|-------|
| **OpenAI** | `openai` | gpt-4o, gpt-4o-mini | Streaming via SSE |
| **Anthropic** | `anthropic` | claude-3.5-sonnet, claude-3-haiku | Streaming via SSE |
| **Ollama** | HTTP (`httpx`) | llama3, mistral, etc. | Self-hosted, no API key required |
