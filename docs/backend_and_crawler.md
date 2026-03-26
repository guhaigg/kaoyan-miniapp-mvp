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
- `POST /api/v1/site-sections/content-files/{content_file_id}/retry-ocr` (requires portal admin token)
- `POST /api/v1/admin/bootstrap/schools` (requires portal admin login)
- `POST /api/v1/admin/bootstrap/departments` (requires portal admin login)
- `POST /api/v1/admin/rebuilds` (requires portal admin login)
- `POST /api/v1/admin/contents/{content_id}/reclassify` (requires portal admin login)
- `GET /api/v1/admin/contents/{content_id}/explain` (requires portal admin login)
- `GET /api/v1/admin/workflows/{workflow_run_id}` (requires portal admin login)
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
- `portal_nodes`: scoped portal graph nodes built from explicit school/department seeds.
- `portal_edges`: portal graph relationships and navigation evidence.
- `portal_host_decisions`: scoped host decisions with evidence and manual override state.
- `workflow_runs`: typed V2 workflow instances for bootstrap/rebuild/classify operations.
- `workflow_steps`: leased workflow steps consumed by standalone crawler workers.
- `raw_artifacts`: raw fetch artifacts stored per workflow step.
- `parse_artifacts`: parse outputs and warnings stored per workflow step.
- `content_classifications`: persisted scope/visibility/classification verdicts for announcements.
- `governance_actions`: audited admin actions for bootstrap/rebuild/reclassify flows.
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
  - Stored `raw_html` snapshots are truncated to a safe UTF-8 byte budget before insert so oversized detail pages do not fail the entire crawl job; truncation metadata is kept in `snapshot_meta`.
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

## 8.1) Crawler V2 Phase 1 Runtime (2026-03-26)

- Search is now read-only for asset discovery. `POST /api/v1/search/announcements` and `POST /api/v1/search/adjustments` no longer trigger runtime bootstrap, family discovery, or repair jobs.
- School/department asset construction now starts from explicit admin workflows:
  - `POST /api/v1/admin/bootstrap/schools`
  - `POST /api/v1/admin/bootstrap/departments`
  - `POST /api/v1/admin/rebuilds`
- V2 bootstrap only accepts explicit seeds (`homepage_url` plus optional `seed_urls`). Legacy discovery inputs such as `announcement_portal_caches.candidate_urls`, stale detail URLs, historical `content.source_url`, and old `site_section_links` are not used as runtime seeds by the new workflow path.
- School scope and department scope are split at the workflow layer. Each `workflow_run`, `workflow_step`, `portal_node`, `portal_host_decision`, and `content_classification` carries `scope_type + scope_key`.
- `site_sections` now act as the approved/recommended asset layer:
  - search only treats approved school-level sections (`enabled=1`, no `department_id`) as ready assets for school announcement scope
  - V2 bootstrap creates disabled recommended sections first; they must be reviewed or enabled before they become searchable assets
- Bootstrap steps now persist real V2 evidence:
  - `portal_nodes` for homepage / explicit seeds / recommended section candidates
  - `portal_edges` for `explicit_seed` and `section_candidate` relationships
  - `raw_artifacts(bootstrap_input)` and `parse_artifacts(section_candidates)` for replay/debugging
- Scope violations are terminal workflow failures. If a department bootstrap returns school-scoped sections, the worker rolls back partial graph/asset writes and marks the step `failed` instead of retrying.
- Announcement-side legacy `crawl_jobs(job_kind=family_discovery)` now act as a handoff-only compatibility shell. The worker either creates a V2 `scope_rebuild` run from explicit `homepage_url/seed_urls` or a maintained canonical seed entry, or ends the job as `no_candidate` when no governed seed exists.
- Legacy `ensure_announcement_search_bootstrap` is now a read-only compatibility shim. It reports approved assets / active V2 workflows / canonical seed readiness, but it no longer creates `crawl_jobs` or triggers discovery side effects.
- For announcement V2 handoff jobs, `homepage_url + seed_urls` are the only discovery inputs. `candidate_urls` remains in the payload only as a backward-compatible result field and is no longer used to drive discovery.
- Governance now has a minimal read path for workflow-backed assets: `GET /api/v1/admin/workflows/{workflow_run_id}` returns the workflow run, steps, scoped portal graph, host decisions, artifacts, and governance actions in one response. This follows the same practical principle highlighted in the Yanbot notes: origin/channel assets must stay inspectable and governable.
- OCR is now an explicit async step. `retry-parse` only reruns file parsing; `retry-ocr` enqueues a V2 `ocr_enqueue` workflow step.
- API process no longer runs the crawl worker loop. V2 steps are consumed by the standalone worker entrypoint `python -m app.workers.crawler_v2_worker`.
- Announcement visibility is now persisted in `content_classifications` and reused by search and premium monitoring instead of recomputing separate visibility decisions per surface.

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

- As of `2026-03-26`, school-limited announcement search no longer performs online cold start or self-repair. If no approved school asset exists, the response returns `asset_state=not_ready` or `asset_state=rebuilding` and points operators to the admin bootstrap/rebuild flow.
- `announcement_portal_caches` remain historical audit data, but the V2 runtime path does not use cached candidate URLs as discovery seeds.
- Search and monitoring consume `content_classifications` as the canonical announcement verdict. `classification_state` currently includes `school_visible`, `department_visible`, `hidden_scope_conflict`, `hidden_non_admissions`, and `non_announcement`.
- Search and premium monitoring only expose announcement rows that are considered visible in the graduate-admissions portal scope, unless the row is explicitly department-scoped.
- `site_section_id / site_section_name` are treated as scope-matching metadata and must be preserved during content upsert/backfill even when portal classification is recomputed.
- Explicitly provided `system_tags` are authoritative and should not be broadened again during upsert.
- Automatically inferred `channel_label` may enrich tags, but should not override the original tag ordering unless the label came from an explicit payload or a maintained `site_section`.
- Negative phrasing such as `不属于研招` / `与研究生招生无关` must not auto-promote ordinary history/news rows into visible graduate-admissions announcements.
- V2 school bootstrap must prefer the explicit school seed set provided by admins and keep discovery bounded to that scope. The workflow should not infer fresh school seeds from legacy detail pages or stale cache candidates.
- Department bootstrap is independent from school bootstrap. Department hosts, sections, and content verdicts must not be promoted into school-level assets unless an operator explicitly approves a scope change.
- School-level section planning may still follow bounded same-site admissions gateways such as `网站首页 -> 招生学院 -> 硕士招生/通知公告`, but that navigation is evaluated inside the bootstrap workflow and stored as scoped evidence instead of being triggered from a search request.
- For school-level announcement reuse, homepage-like same-host sections such as bare portal roots (`/`, `main.htm`, `index.htm`) count as legacy placeholders unless they already carry structured channel metadata (`portal_entry_url`, `portal_scope`, `channel_label`, `channel_tier`). These placeholder sections must not be reused ahead of family discovery, otherwise canonical portals like `yz.hubu.edu.cn` never advance from the root page to concrete channels such as `zsxy/sszs.htm` and `zsxy/tzgg.htm`.
- School-limited announcement search and school-limited adjustment search intentionally use different school-name semantics. Announcement search is strict: rows that look like `学校名 + 学院/学部/系/研究院/研究所/中心/分校/校区` are treated as conflicting school identities and must not leak into school-level announcement results unless the user explicitly narrows to that department scope. This school-identity check must use both content signals and bound section evidence (`site_section.name`, `section_url`, `probe_heading`, `probe_evidence.stable_text`) so school-level search can still reject polluted学院栏目内容 even when the title/body only says `我院`. Adjustment search is looser: `学校名 + 学院/学部/系` remains part of the parent-school search, but `分校/校区/独立学院` style branch identities must still stay out.
- Polluted announcement cleanup must also detect same-school-prefix collisions, not just wrong hosts. If an announcement is bound to school A but the section evidence, `extra.school_name`, or content text consistently identifies it as `学校A + 学院/学部/...`, the row is treated as polluted school-level announcement data and can be dry-run reviewed, deleted, and then rebuilt through the existing announcement asset rebuild flow. When polluted rows are found for a school, its `announcement_portal_caches` entry must be cleared in the same cleanup so stale sibling-host candidates do not reseed the next cold start.
