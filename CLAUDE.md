# Claude Project Guide

This file is the fast-start guide for Claude Code when working in this repository.

## Read First

Before making any non-trivial change, read in this order:

1. `AGENTS.md`
2. `docs/development_protocol.md`
3. `docs/git_workflow.md`
4. `docs/deployment.md`
5. `docs/plan.md`

If instructions conflict, follow the stricter rule.

## Project Summary

Ge Wu Jian Lu (`格物简录`) is a multi-surface project with:

- `backend/`: FastAPI API, auth, search, subscriptions, notifications, admin
- `web-ui/`: Next.js web UI for `gewujl.cloud`
- `miniapp/`: WeChat mini program
- `infra/`: nginx, systemd, backup, deployment assets
- `docs/`: process, deployment, architecture, release records

Production currently uses:

- Web: `https://gewujl.cloud`
- API: `https://api.gewujl.cloud`
- External MySQL
- Redis
- Nginx + systemd
- Hong Kong deployment host documented in `docs/deployment.md`

## Working Rules

- Default to Simplified Chinese for user-facing communication, status updates, summaries, and step-by-step progress reports unless the user explicitly asks for another language.
- Multiple subagents may be used for larger tasks, but the main thread must always own final integration, final edits, validation, commit, deploy, and the user-facing summary.
- Do not let multiple subagents modify the same files at the same time.
- When using subagents, define clear ownership boundaries first, then report progress step by step from the main thread.
- Do not redesign the frontend without explicit approval.
- For UI changes, preserve the current visual language and interaction patterns unless the user asks for a redesign.
- For larger frontend changes, prefer targeted edits over broad refactors.
- Never commit secrets, tokens, database passwords, or `.env` files.
- If behavior, deployment, process, or architecture changes, update docs in the same task.

## Git Workflow

Normal policy from repository rules:

- Start from `dev`
- Use `feat/*` for features and `fix/*` for fixes
- Merge `feat/fix -> dev -> main`

Do not assume `main` is the right place for normal development unless the user explicitly asks for direct hotfix-style work.

## Validation Expectations

Run the relevant checks before finishing:

- Backend changes: `npm run test:backend`
- Web UI changes: `cd web-ui && npm run lint && npm run build`
- Deploy/config changes: verify service status and health endpoint
- Miniapp changes: at least one basic WeChat DevTools smoke pass if feasible

If anything is not run, say so explicitly in the delivery summary.

## Common Commands

Repository root:

```bash
npm run test:backend
npm run dev:backend
```

Backend:

```bash
cd backend
../.venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Web UI:

```bash
cd web-ui
npm run dev
npm run lint
npm run build
```

## Frontend Notes

- Stack: Next.js 15, React 19, TypeScript, Framer Motion, TanStack Query, Zustand, Axios
- Data fetching is being standardized around:
  - thin API wrappers in `web-ui/src/api/*`
  - hooks in `web-ui/src/hooks/*`
  - shared cache helpers where needed
- Reuse existing hooks and wrappers before adding new fetch logic directly in pages/components.
- Keep interactions smooth, but do not introduce stylistic changes without user approval.

## Backend Notes

- Stack: FastAPI + SQLAlchemy + MySQL + Redis
- Notifications use outbox/delivery style realtime flow documented in:
  - `docs/notification_realtime_architecture_2026-03-17.md`
- Portal auth and login architecture is documented in:
  - `docs/auth_login_architecture.md`

## Deployment Notes

Authoritative deployment details live in `docs/deployment.md`.

Important current paths:

- Web static root: `/var/www/html`
- Server repo root: `/root/code/kaoyan-miniapp-mvp`

Typical web deploy flow on the Hong Kong host:

```bash
cd /root/code/kaoyan-miniapp-mvp
git pull --ff-only origin main
cd web-ui
npm ci
npm run build
rsync -a --delete out/ /var/www/html/
nginx -t
systemctl reload nginx
```

## Remote Server Permission

Claude may directly use SSH to operate the deployment server for this project when needed for development, debugging, deployment, verification, or log inspection.

Allowed without extra confirmation:

- `ssh`
- `scp`
- `rsync`
- `git pull`
- `git push`
- `systemctl restart/status`
- `journalctl`
- `nginx -t`
- standard build and deploy commands
- health checks, curl-based verification, and service inspection

Preferred behavior:

- Use the minimum necessary remote commands first.
- After each meaningful step, report back what was done before continuing.
- Explain what was changed and what was verified after remote work.
- Prefer targeted fixes over broad server-side refactors.

Must ask before proceeding if the action is high risk:

- deleting files or directories
- dropping, truncating, or overwriting database data
- rotating or replacing credentials
- changing DNS, SSL, firewall, or security policy
- replacing production env files wholesale
- destructive process cleanup beyond normal service restart/reload

## Documentation to Update When Relevant

- Behavior/process rules: `docs/development_protocol.md`
- Deployment/runtime changes: `docs/deployment.md`
- UI architecture or execution baseline: `docs/ui_rebuild_execution_baseline.md`
- API/UI alignment: `docs/web_ui_api_alignment_2026-03-17.md`
- Realtime notifications: `docs/notification_realtime_architecture_2026-03-17.md`

## Delivery Checklist

Before considering a task complete:

1. Code is implemented.
2. Relevant validation is run, or skipped with explicit note.
3. Docs are updated if needed.
4. Summary includes:
   - what changed
   - how it was verified
   - any remaining risk or next step
