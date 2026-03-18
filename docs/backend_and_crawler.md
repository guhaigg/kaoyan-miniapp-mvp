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
- `POST /api/v1/search/announcements`
- `POST /api/v1/search/adjustments`
- `GET /api/v1/schools/suggest`
- `POST /api/v1/content` (requires `X-Admin-Token`)
- `POST /api/v1/admin/manual-entry`
- `POST /api/v1/crawl-jobs` (requires admin session or `X-Admin-Token`)
- `GET /api/v1/crawl-jobs` (requires admin session or `X-Admin-Token`)
- `GET /api/v1/crawl-jobs/{job_id}` (requires admin session or `X-Admin-Token`)
- `POST /api/v1/site-sections` (requires admin session or `X-Admin-Token`)
- `GET /api/v1/site-sections` (requires admin session or `X-Admin-Token`)
- `POST /api/v1/site-sections/discover` (requires admin session or `X-Admin-Token`)
- `GET /api/v1/site-sections/{id}/links` (requires admin session or `X-Admin-Token`)
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
- `content_files`: lightweight file records (currently PDF placeholder).
- `users`: shadow accounts (`state=shadow`).
- `user_events`: security and audit trail.

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
  - Deduplicate by `source_url` unique key.
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
- Discovery scheduling:
  - `POST /api/v1/site-sections/discover` creates `crawl_jobs` with `job_kind=site_section_discovery`.
- Worker behavior:
  - For `site_section_discovery`, worker fetches section list page and extracts `<a>` links.
  - New HTML links are saved to `site_section_links` and enqueued as child detail crawl jobs.
  - New PDF links are saved to `site_section_links` and recorded to `content_files` as placeholder entries.
- Observability:
  - Section rows keep `last_discovered_at / last_discovery_status / last_error`.
  - Discovery failure still writes `crawl_errors`.
- Current limitations (intentional for MVP):
  - `list_selector_config` is stored but not yet interpreted as strict CSS/XPath extraction rules.
  - No OCR/PDF text extraction yet; `content_files` only keeps file metadata placeholder.
  - Cross-section dedup (same URL across different sections) is not yet globally merged.
