Architecture Rules:

- Follow service → repository → provider pattern
- Controllers must never access DB directly
- Providers must implement interfaces
- LLM integrations must be abstracted
- Prefer async functions for I/O-bound operations (API handlers / DB / network)

Code Quality:

- Enforce DRY: no duplicate logic
- Strict typing required

Security:

- Never log secrets (API keys, auth/session/JWT/refresh tokens, passwords, etc.)
- Encrypt credentials
- Validate all input
- You may record LLM token counts/usage metrics, but must never log prompts, responses, or any credentials

Infra:

- Must run in Docker
- Must support Kubernetes
