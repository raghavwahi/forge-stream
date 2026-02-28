# ForgeStream — Engineering Standards

This document enforces Google/Meta-level engineering standards across the
ForgeStream monorepo. All contributors and AI assistants must follow these rules.

---

## Architecture

- **Service → Repository → Provider pattern** is mandatory for all backend code.
- Controllers/routes must never access the database directly.
- All providers (DB, LLM, auth) must implement interfaces/abstract base classes.
- LLM integrations must be abstracted behind a provider adapter layer.
- All I/O-bound functions must be `async`.

## Strict Typing

- **Python (API):** All request/response models must use Pydantic `BaseModel` with
  explicit field types. No `Any` or untyped `dict`. Use `strict` mode where possible.
- **TypeScript (Web):** Strict mode enabled (`"strict": true` in tsconfig). No `any`.
  All component props must have explicit interfaces. Shared types live in `/shared`.

## Code Quality

- **DRY principle** is mandatory. No duplicate logic across services or layers.
- Extract shared logic into `/shared` (types) or service-level utilities.
- Functions should do one thing. Max function length: ~40 lines.
- Prefer composition over inheritance.

## Database Access

- **Repository pattern** is required for all database operations.
- Repositories must accept a database client via dependency injection.
- Raw SQL or direct ORM calls outside the repository layer are not allowed.
- All queries must be parameterized — no string interpolation.

## Security

- Never log tokens, secrets, or credentials.
- Encrypt all credentials at rest.
- Validate and sanitize all user input at the boundary.
- Use environment variables for all secrets (see `.env.example`).
- Follow OWASP Top 10 guidelines.

## API Design

- All API endpoints must return typed Pydantic response models.
- Use proper HTTP status codes (don't return 200 for errors).
- Error responses should include a human-readable `detail` string.
  - Where supported, include an explicit integer `status_code` in the body.
  - For FastAPI endpoints using `HTTPException` without a global exception
    normalizer, the default `{ "detail": string }` shape is acceptable.

## Infrastructure

- All services must run in Docker (see `/infra/docker`).
- All services must support Kubernetes deployment (see `/infra/k8s`).
- Environment parity: dev, staging, and production must use the same Docker images.

## Testing

- All business logic must have unit tests.
- API endpoints must have integration tests using `httpx` / `TestClient`.
- Frontend components with logic must have tests.
