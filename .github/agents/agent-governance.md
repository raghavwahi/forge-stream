# Agent Execution Governance

## Task decomposition strategy

- Break work into single-feature tasks with clear module boundaries.
- Prefer creating new feature modules over editing shared/core files.
- Sequence tasks so each task is independently reviewable and mergeable.

## Parallel execution limits

- Run at most **2 parallel agent tasks** against disjoint domains.
- Do not run parallel tasks on overlapping files or directories.
- If overlap is possible, serialize execution.

## Lock file usage

- Before editing, create a lock marker under `.github/architecture/locks/`.
- Lock filename format: `<agent>-<domain>.lock`.
- Only one active lock per domain.
- Remove lock file when task is complete.

## Branch naming conventions

- Branch names must use the format: `feature/<domain>-<short-description>`.
- Examples:
  - `feature/backend-github-route`
  - `feature/frontend-review-page`
  - `feature/devops-ci-hardening`
