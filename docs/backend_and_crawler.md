# Backend and Crawler Specification

## 1) API Response Contract

All business APIs should follow a stable JSON envelope:

```json
{
  "code": 0,
  "msg": "success",
  "data": {}
}
```

Current MVP endpoints already return typed payloads. When integrating public clients, keep a compatibility adapter that maps typed payloads to this envelope.

## 2) API List (MVP)

- `POST /api/v1/auth/silent-login`
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`
- `POST /api/v1/search/announcements`
- `POST /api/v1/search/adjustments`
- `GET /api/v1/schools/suggest`
- `POST /api/v1/content` (requires `X-Admin-Token`)
- `POST /api/v1/admin/manual-entry`
- `POST /api/v1/crawl-jobs` (requires portal admin token)
- `GET /api/v1/crawl-jobs` (requires portal admin token)
- `GET /api/v1/crawl-jobs/{job_id}` (requires portal admin token)
- `POST /api/v1/site-sections` (requires portal admin token)
- `GET /api/v1/site-sections` (requires portal admin token)
- `POST /api/v1/site-sections/bootstrap` (requires portal admin token)
- `PATCH /api/v1/site-sections/{id}` (requires portal admin token)
- `POST /api/v1/site-sections/discover` (requires portal admin token)
- `GET /api/v1/site-sections/{id}/links` (requires portal admin token)
- `POST /api/v1/site-sections/{id}/preview-selectors` (requires portal admin token)
- `GET /api/v1/site-sections/content-files` (requires portal admin token)
- `POST /api/v1/site-sections/content-files/{content_file_id}/retry-parse` (requires portal admin token)
- `POST /api/v1/monitoring/targets` (Phase 1 contract: premium user/admin)
- `GET /api/v1/monitoring/targets` (Phase 1 contract: premium user/admin, scoped to current user unless admin)
- `PATCH /api/v1/monitoring/targets/{target_id}` (Phase 1 contract: premium user/admin)
- `POST /api/v1/monitoring/targets/{target_id}/keywords` (Phase 1 contract: premium user/admin)
- `GET /api/v1/monitoring/targets/{target_id}/keywords` (Phase 1 contract: premium user/admin)
- `PATCH /api/v1/monitoring/keywords/{keyword_id}` (Phase 1 contract: premium user/admin)
- `GET /api/v1/monitoring/hits` (Phase 1 contract: premium user/admin, current user scope)
- `GET /api/v1/monitoring/admin/hits` (Phase 1 contract: admin only)
- `GET /api/v1/health`

## 3) Database Naming Rules

- Table names: lowercase snake_case.
- Column names: lowercase snake_case.
- IDs: UUID string (`36 chars`) in MVP.
- Structured data in fixed columns; crawler variable fields in JSON (`extra`, `snapshot_meta`, `query`, `payload`).

## 4) Table Responsibilities

- `schools`: school dictionary and aliases.
- `sources`: source registry and crawling config.
- `contents`: canonical content for announcements/adjustments.
- `content_snapshots`: raw HTML/text snapshots.
- `crawl_jobs`: async refresh jobs.
- `crawl_errors`: crawler/parse failure records.
- `departments`: school departments/graduate schools.
- `site_sections`: maintained section/list-page assets.
- `site_section_links`: discovered detail/pdf links from section pages.
- `content_files`: file records for PDF/attachments, including text extraction status and OCR handoff status.
- `portal_user_monitor_targets`: user-owned monitoring scopes (school/department/section), interval and status.
- `portal_user_monitor_keywords`: per-target custom keywords.
- `portal_user_monitor_hits`: user-target-content match records used by in-app/Bark delivery.
- `users`: shadow accounts (`state=shadow`).
- `user_events`: security and audit trail.
- `account_identities`: login identities (`password`, `wechat_miniapp`).
- `account_roles`: role grants (`admin`).
- `account_entitlements`: runtime entitlements (`premium_monitoring`).
- `account_payment_orders`: billing ledger for premium orders.

## 5) Silent Shadow Account Rules

- Frontend calls `wx.login` silently at app launch.
- Backend exchanges `code -> openid`, then creates/reuses a `shadow` user.
- Backend issues `visitor_token` for rate limit and audit only.
- No explicit profile authorization in MVP.

## 6) Crawler Behavior Guardrails

- User-Agent policy:
  - Use shared UA pool.
  - Rotate by source and retry attempt.
- Retry policy:
  - Network failure: retry up to 3 times with exponential backoff.
  - DOM parse failure: catch and record to `crawl_errors`; do not crash entire task.
- Frequency/concurrency:
  - Per source default max rate: <= 2 requests/sec per IP.
  - Per source concurrency: start with 2, tune after observing anti-bot behavior.
- Data quality:
  - Deduplicate by `content_fingerprint`, with `source_url` as a second guard.
  - Keep raw snapshot for post-mortem.

## 6.1) MVP Crawl Job Worker (Task Pack A Baseline)

- Job lifecycle:
  - `pending -> running -> done|failed`
- Worker behavior (minimal):
  - Consume `pending` rows from `crawl_jobs`.
  - If `query.source_url` exists: fetch URL, parse minimal text, upsert to `contents`.
  - If `query.content` exists: upsert the provided payload directly.
  - If `query.simulate=true`: create a simulated content row for end-to-end validation.
  - If no executable payload exists: mark as `done(noop)` to keep refresh queue observable.
- Snapshot policy:
  - Successful upsert with `raw_html` writes one row to `content_snapshots`.
- Failure policy:
  - Any crawl/parse/upsert exception writes one row to `crawl_errors`.
  - Failed job status is set to `failed` with truncated error message in `crawl_jobs.message`.

## 7) Error Handling Baseline

- Never leak raw stack traces to client.
- Convert predictable failures to 4xx with stable `detail`.
- Log all unexpected 5xx with `request_id`.
- For crawler refresh requests, return accepted/pending state through `crawl_jobs`.

## 8) Site Section Discovery Baseline (Task Pack A-2 / A-3 Lite)

- Asset layer:
  - Admin can maintain `site_sections` with school/department dimensions.
  - Admin can call `POST /api/v1/site-sections/bootstrap` with `school_name + homepage_url` to auto-probe same-host研招/公告栏目并批量落库，再可选直接排 discovery job。
- Discovery scheduling:
  - `POST /api/v1/site-sections/discover` creates `crawl_jobs` with `job_kind=site_section_discovery`.
- Worker behavior:
  - For `site_section_discovery`, worker fetches section list page and extracts `<a>` links.
  - New HTML links are saved to `site_section_links` and enqueued as child detail crawl jobs.
  - New PDF links are saved to `site_section_links`, recorded to `content_files`, and enqueued as `job_kind=file_parse`.
  - Detail page ingestion prefers `detail_selector_config`, falls back to `readability-lxml`, then finally to plain text extraction.
  - PDF file ingestion prefers direct text extraction from text-based PDF; if extracted text is too short, create a placeholder content row and mark the file as `needs_ocr`.
  - Link-only notices generate explanatory placeholder content plus extracted outbound links, rather than exposing raw “click to view” filler text.
  - Extracted content is tagged with domain keywords via `jieba`, and tags are stored in `contents.extra.tags`.
- Observability:
  - Section rows keep `last_discovered_at / last_discovery_status / last_error`.
  - Discovery failure still writes `crawl_errors`.
- Current limitations (intentional for MVP):
  - No OCR yet; scanned/image PDF is marked `needs_ocr` and exposed through original file link placeholder content.
  - Cross-section dedup (same URL across different sections) is not yet globally merged.

## 9) Premium Monitoring Phase 1 Baseline (Implemented + Known Gaps)

- Matching principle:
  - System crawls section/list/detail once.
  - User-level matching runs on shared `contents` results.
  - Do not duplicate crawling per user.
- Access principle:
  - Regular user: cannot create premium monitoring target.
  - Premium user: can create/list/update own targets and keywords.
  - Admin (`portal_users` + `account_roles`): full premium capability + backend hit view.
- Observability principle:
  - Keep hit records and notification delivery records queryable.
  - Keep crawler failure traces in `crawl_errors`.
- Current status note (2026-03-18):
  - `/api/v1/monitoring/*` routes are mounted in `app.main`.
  - `POST /api/v1/content` triggers monitor matching and writes `portal_user_monitor_hits` + `notification_outbox(event_type=monitor.hit)`.
  - Coverage baseline is provided by `backend/tests/test_premium_monitoring_authz.py` and `backend/tests/test_premium_monitoring_targets.py`.
- Known gaps:
  - Monitoring query and hit ranking still rely on rules/tags, not richer structured extraction.
- Intentional Phase 1 limits:
  - No OCR.
  - Text-based PDF extraction is supported, but scanned/image PDF still requires a later OCR stage.
  - NLP is currently limited to domain keyword tagging (`jieba` + custom dictionary), not full ranking/semantic analysis.
  - No per-user dedicated crawler workers.

## 9.1) Announcement Portal Visibility Rules

- Search and premium monitoring only expose announcement rows that are considered visible in the graduate-admissions portal scope, unless the row is explicitly department-scoped.
- `site_section_id / site_section_name` are treated as scope-matching metadata and must be preserved during content upsert/backfill even when portal classification is recomputed.
- Explicitly provided `system_tags` are authoritative and should not be broadened again during upsert.
- Automatically inferred `channel_label` may enrich tags, but should not override the original tag ordering unless the label came from an explicit payload or a maintained `site_section`.
- Negative phrasing such as `不属于研招` / `与研究生招生无关` must not auto-promote ordinary history/news rows into visible graduate-admissions announcements.
- School-level announcement cold start must prefer the maintained canonical admissions portal host when one is configured. Existing school-level sections on sibling hosts or legacy graduate-school entry sites must not be reused ahead of that canonical portal, otherwise announcement crawling will attach to the wrong school-level source.
- When no canonical override exists, school-level announcement cold start may follow bounded same-school portal navigation across sibling subdomains such as `学校首页 -> 研究生院 -> 招生信息网`, but it must keep that discovery bounded and only use it to choose the preferred host. Concrete list-page seeds should still win over inferred host roots when they are the strongest candidate on that host.
- When a non-override school-level announcement cold start successfully resolves candidate portal URLs, the system should persist that verified candidate set for reuse by later cold starts. The reuse order is `canonical override > fresh verified portal cache > existing site sections > live docs/search/navigation discovery`, and cached portal candidates currently expire after 30 days so stale school-level entry points still fall back to live rediscovery.
