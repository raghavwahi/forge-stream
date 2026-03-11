# Agent Execution Governance

## Task decomposition strategy

- Break work into single-feature tasks with clear module boundaries.
- Prefer creating new feature modules over editing shared/core files.
- Sequence tasks so each task is independently reviewable and mergeable.

## Parallel execution limits

- Run at most **2 parallel agent tasks** against disjoint domains.
- Do not run parallel tasks on overlapping files or directories.
- If overlap is possible, serialize execution.
- This limit is designed to reduce merge-conflict risk and reviewer/CI overload.
  Maintainers may increase the limit when conflict rates and CI capacity allow.

## Lock file usage

- Before editing, create a lock marker under `.github/architecture/locks/`.
- Lock filename format: `<agent>-<domain>.lock`.
- Only one active lock per domain.
- Remove lock file when task is complete.
- Lock acquisition is mandatory and is checked in PR review.
- Stale locks older than 24h can be removed by maintainers after confirmation in
  the PR conversation.

## Branch naming conventions

- Branch names must use the format: `feature/<domain>-<short-description>`.
- Examples:
  - `feature/backend-github-route`
  - `feature/frontend-review-page`
  - `feature/devops-ci-hardening`
- Non-feature work should follow:
  - `bugfix/<domain>-<short-description>`
  - `hotfix/<domain>-<short-description>`
  - `refactor/<domain>-<short-description>`
  - `chore/<domain>-<short-description>`
