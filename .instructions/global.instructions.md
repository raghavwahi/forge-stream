Architecture Rules:

- Follow service → repository → provider pattern
- Controllers must never access DB directly
- Providers must implement interfaces
- LLM integrations must be abstracted
- Always async functions

Code Quality:

- DRY principle mandatory
- No duplicate logic
- Strict typing required

Security:

- Never log tokens
- Encrypt credentials
- Validate all input

Infra:

- Must run in Docker
- Must support Kubernetes
