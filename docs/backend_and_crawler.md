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

## 7) Error Handling Baseline

- Never leak raw stack traces to client.
- Convert predictable failures to 4xx with stable `detail`.
- Log all unexpected 5xx with `request_id`.
- For crawler refresh requests, return accepted/pending state through `crawl_jobs`.
