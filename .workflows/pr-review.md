# PR Review Workflow

Automated AI reviewer for ForgeStream pull requests.

---

## Trigger

Run this review on every pull request targeting `main`.

---

## Review Checklist

### 1. DRY Violations

- [ ] Scan changed files for duplicated logic (functions, constants, config blocks).
- [ ] Flag any code block that appears more than once and suggest extracting it into a shared utility or module.
- [ ] Check for repeated SQL queries, API call patterns, or error-handling boilerplate that should be centralised.

### 2. Security — JWT Handling

- [ ] Verify tokens are validated on every protected endpoint using a dependency (e.g., FastAPI `Depends`).
- [ ] Ensure the signing secret is loaded from environment variables — never hard-coded.
- [ ] Confirm the algorithm is explicitly set (e.g., `HS256`) to prevent algorithm-confusion attacks.
- [ ] Check that token expiry (`exp`) is enforced and lifetime is reasonable (≤ 30 minutes for access tokens).
- [ ] Ensure refresh tokens are rotated on use and stored securely (HTTP-only, Secure, SameSite cookies).
- [ ] Flag any token logged or returned in a response body beyond the initial auth exchange.

### 3. Architectural Alignment

- [ ] API changes stay within `api/app/` and follow the existing FastAPI project layout.
- [ ] Frontend changes stay within `web/src/` and follow the Next.js App Router conventions.
- [ ] Infrastructure changes stay within `infra/` and keep Docker and Kubernetes manifests consistent.
- [ ] New dependencies are added to the correct manifest (`pyproject.toml` for Python, `package.json` for Node).
- [ ] No business logic in route handlers — logic should live in dedicated service or repository modules.
- [ ] LLM provider integrations follow a common abstract base class so new providers can be added without modifying consumers.

---

## Output Format

For each finding, the reviewer should produce:

```
### <Category>  —  <File>:<Line>
**Severity:** Low | Medium | High | Critical
**Description:** <What was found>
**Suggestion:** <Recommended fix>
```

---

## Exit Criteria

| Result | Condition |
|--------|-----------|
| ✅ Approve | Zero High/Critical findings |
| 🔄 Request Changes | One or more High/Critical findings |
