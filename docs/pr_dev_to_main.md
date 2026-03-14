# PR Title (dev -> main)

`feat: release mvp foundation (fastapi + miniapp + async refresh worker)`

# PR Description

## Background
- This PR delivers the first production-ready MVP baseline for the kaoyan miniapp.
- Scope includes backend API foundation, miniapp query pages, docs-as-code, and async refresh worker consumption.

## What Changed
- Backend:
  - Added `/api/v1` core endpoints for silent login, search, content ingest, admin manual entry, schools suggest, health.
  - Added strict shadow-account silent login flow (`code -> openid -> visitor_token`).
  - Added Alembic migration setup and initial schema revision.
  - Added async refresh worker (`crawl_jobs` consumer) and `GET /api/v1/jobs/{job_id}`.
  - Added admin source upsert endpoint for crawler target registration.
- Frontend (miniapp):
  - Added 5 MVP pages: home / announcements / adjustments / detail / status.
  - Added silent login bootstrap and API wrapper.
- Infra:
  - Added Docker Compose services for backend, worker, postgres, redis.
- Quality:
  - Added backend tests and CI workflow.
- Docs:
  - Added full docs set under `docs/`.

## Risk and Rollback
- Risk:
  - Worker logic depends on configured sources; empty sources lead to completed jobs with zero capture.
  - WeChat real mode requires valid credentials.
- Rollback:
  - Revert to previous tag/image and switch gateway back.
  - DB schema rollback via Alembic downgrade if required.

## Verification
- `python -m pytest -q` passed.
- `python -m alembic upgrade head` passed.
- Manual API verification for refresh job creation and status polling completed.

# Checklist

- [x] Code compiles and tests pass.
- [x] New APIs documented.
- [x] Migration files added and executable.
- [x] CI workflow updated.
- [x] Security baseline preserved (rate limit + audit).
- [x] No changes applied to legacy repository code.
- [x] Docs under `docs/` updated.
- [x] Ready for review from `dev` into `main`.

