# 格物简录 Development Plan

This document is the execution plan for the current MVP repository.
It converts the existing specs into concrete, trackable work.

## Current Baseline (2026-03-15)

- Frontend miniapp pages are present: `home`, `announcements`, `adjustments`, `detail`, `status`.
- Backend FastAPI routers are present and wired under `/api/v1`.
- CI workflow exists for backend tests (`pytest -q`).
- Deployment and workflow docs exist, but no explicit plan file existed before this document.

## Phase 0: Configuration Hardening

Goal: make local/dev/prod configuration explicit and safe.

- [x] Replace miniapp hardcoded API base URL with environment-aware config.
- [x] Replace `touristappid` with real WeChat appid in non-local environments.
- [x] Define and document `USE_MOCK_WECHAT` policy per environment.
- [x] Restrict CORS for non-dev environments.
- [x] Standardize app naming across backend env defaults and docs (格物简录 / 格物简).

Done when:
- Miniapp can switch API base URL without code edits.
- Backend starts with `.env` and no placeholder secrets in runtime config.

## Phase 1: Product Loop Completion (MVP)

Goal: guarantee end-to-end user flow from open app to viewing content.

- [ ] Validate silent login fallback path (wx.login success/failure both usable).
- [ ] Confirm announcements and adjustments search filters work as expected.
- [ ] Ensure detail page schema handles missing fields safely.
- [ ] Normalize user-facing error messages on status page.

Done when:
- A user can complete search -> list -> detail flow without blockers.
- Failure paths route to status page with stable, readable messages.

## Phase 2: Data Pipeline and Operations

Goal: stabilize data ingestion and admin operation lifecycle.

- [ ] Implement or wire crawler refresh job flow against `crawl_jobs`.
- [ ] Validate dedup strategy based on `source_url`.
- [ ] Keep raw snapshots and parse-error records for post-mortem.
- [ ] Verify manual entry and offline flow from admin endpoint.

Done when:
- New content can be ingested and queried in a repeatable way.
- Parse failures are observable without breaking ingestion.

## Phase 3: Quality Gate and Release Readiness

Goal: make daily iteration and release low-risk.

- [ ] Ensure local backend test command works in project bootstrap docs.
- [ ] Add miniapp smoke checklist for page routes and API interactions.
- [ ] Add release checklist for env, migration, backup, rollback validation.

Done when:
- Team can run a reproducible pre-release checklist in under 20 minutes.
- Rollback path is documented and tested.

## Immediate Next Sprint (Suggested)

1. Finish Phase 0 configuration hardening.
2. Run one full miniapp + backend link test pass.
3. Lock a v0.1.0 MVP release checklist.
