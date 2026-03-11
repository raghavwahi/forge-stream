# ForgeStream Architecture Rules

## 1) Module-per-feature

Every new feature must be implemented as its own module and should be isolated to
feature-specific files/folders.

Examples:

- `api/app/routers/github.py`
- `api/app/routers/analytics.py`
- `web/src/app/dashboard/page.tsx`
- `web/src/app/review/page.tsx`

Rules:

- Create new feature files before modifying shared files.
- Avoid changing shared files unless a feature cannot be completed otherwise.
- Keep module boundaries explicit and predictable.

## 2) Domain ownership

Agents must only modify files in their owned domains.

### Backend agents

- `api/app/*`
- `api/db/*`

### Frontend agents

- `web/src/app/*`
- `web/src/components/*`
- `web/src/lib/*`
- `web/src/hooks/*`

### Security agents

- `api/app/security/*`
- `api/app/middleware/*`

### DevOps agents

- `infra/docker/*`
- `infra/k8s/*`
- `.github/workflows/*`

### QA agents

- `api/tests/*`
- `web/src/**/*.test.*`
- `e2e/*`

### Governance agents

- `.github/agents/*`
- `.github/architecture/*`
- `.github/instructions/*`
- `.github/prompts/*`

Cross-domain edits are not allowed unless explicitly approved in task scope.
Approval must come from the PR owner or repository maintainer and be recorded in
the PR description under a `Cross-domain approval` note listing impacted paths.
Teams should enforce this with CI checks that validate approval notes when a PR
touches files across multiple declared domains.

## 3) Small PR policy

Pull requests must remain small and focused.

Rules:

- Maximum size guideline: **10 files changed**.
- If a change exceeds this size, split it into smaller PRs unless a repository
  maintainer explicitly approves a larger scope in the PR description.
- File count includes source, test, docs, and configuration files.
- Each PR should implement **one feature only**.
- Split larger efforts into multiple sequential PRs.
