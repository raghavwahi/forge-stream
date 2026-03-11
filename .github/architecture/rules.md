# ForgeStream Architecture Rules

## 1) Module-per-feature

Every new feature must be implemented as its own module and should be isolated to
feature-specific files/folders.

Examples:

- `backend/api/routes/github.py`
- `backend/api/routes/analytics.py`
- `frontend/app/dashboard/page.tsx`
- `frontend/app/review/page.tsx`

Rules:

- Create new feature files before modifying shared files.
- Avoid changing shared files unless a feature cannot be completed otherwise.
- Keep module boundaries explicit and predictable.

## 2) Domain ownership

Agents must only modify files in their owned domains.

### Backend agents

- `backend/app/*`
- `backend/services/*`
- `backend/api/*`

### Frontend agents

- `frontend/app/*`
- `frontend/components/*`
- `frontend/lib/*`

### Security agents

- `backend/security/*`
- `backend/middleware/*`

### DevOps agents

- `docker/*`
- `.github/workflows/*`

### QA agents

- `tests/*`
- `e2e/*`

Cross-domain edits are not allowed unless explicitly approved in task scope.
Approval must come from the PR owner or repository maintainer and be recorded in
the PR description under a `Cross-domain approval` note listing impacted paths.

## 3) Small PR policy

Pull requests must remain small and focused.

Rules:

- Maximum recommended size: **10 files changed**.
- If a change exceeds this size, split it into smaller PRs unless a repository
  maintainer explicitly approves a larger scope in the PR description.
- Each PR should implement **one feature only**.
- Split larger efforts into multiple sequential PRs.
