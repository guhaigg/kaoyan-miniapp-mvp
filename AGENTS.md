# Repository Execution Rules

These rules are mandatory for any assistant or developer working in this repository.

## 1) Required Reading Order

1. `docs/development_protocol.md`
2. `docs/git_workflow.md`
3. `docs/deployment.md`
4. `docs/plan.md`

If any conflict appears, follow the stricter rule.

## 2) Branch and Merge Policy

- Do not develop directly on `main` for normal work.
- Start from `dev` and use:
  - `feat/*` for features
  - `fix/*` for fixes
- Merge flow: `feat/fix -> dev -> main`.

## 3) Commit Rules

- Commit messages must follow conventional types:
  `feat|fix|docs|style|refactor|perf|test|chore|revert`.
- Keep each commit scoped to one concern.
- Push before leaving work; use `WIP` if needed.

## 4) Validation Rules

- Backend changes: run `npm run test:backend` before commit.
- Miniapp changes: run at least one basic smoke pass in WeChat DevTools.
- Infra/deploy changes: verify service status and health endpoints.
- If any validation is skipped, explicitly report it in the delivery summary.

## 5) Skill Usage Rules

- If a task matches an available skill, use the skill first.
- Read the skill's `SKILL.md` before execution.
- Install missing but necessary skills via `skill-installer`.
- If a skill fails, continue with a safe fallback and report the fallback.

## 6) Security Rules

- Never commit real secrets (`.env`, PAT, AppSecret, DB passwords).
- Use environment or secret manager for credentials.
- Rotate any secret exposed in logs or chat immediately.
- Production must not use wildcard CORS.

## 7) Delivery Rules

A task is complete only when all are true:

1. Implementation is done.
2. Required validation is done or clearly declared as pending.
3. Docs are updated when behavior/config/process changed.
4. Summary includes what changed, how it was verified, and next steps.
