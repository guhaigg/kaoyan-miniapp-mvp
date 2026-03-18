-- 2026-03-18
-- SQLite fallback migration for site_sections.detail_selector_config and crawl_jobs.updated_at.

ALTER TABLE site_sections ADD COLUMN detail_selector_config TEXT NOT NULL DEFAULT '{}';
ALTER TABLE crawl_jobs ADD COLUMN updated_at DATETIME;

UPDATE crawl_jobs
SET updated_at = COALESCE(finished_at, started_at, requested_at, CURRENT_TIMESTAMP)
WHERE updated_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_crawl_jobs_updated_at ON crawl_jobs (updated_at);
