-- 2026-03-18
-- Add selector config for site_sections and lease heartbeat for crawl_jobs.
-- Safe to rerun on MySQL 8+.

SET @db_name = DATABASE();

SET @has_detail_selector_config = (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db_name
    AND TABLE_NAME = 'site_sections'
    AND COLUMN_NAME = 'detail_selector_config'
);

SET @sql = IF(
  @has_detail_selector_config = 0,
  'ALTER TABLE site_sections ADD COLUMN detail_selector_config JSON NULL',
  'SELECT "detail_selector_config already exists"'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_crawl_job_updated_at = (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db_name
    AND TABLE_NAME = 'crawl_jobs'
    AND COLUMN_NAME = 'updated_at'
);

SET @sql = IF(
  @has_crawl_job_updated_at = 0,
  'ALTER TABLE crawl_jobs ADD COLUMN updated_at DATETIME NULL',
  'SELECT "crawl_jobs.updated_at already exists"'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

UPDATE site_sections
SET detail_selector_config = JSON_OBJECT()
WHERE detail_selector_config IS NULL;

UPDATE crawl_jobs
SET updated_at = COALESCE(finished_at, started_at, requested_at, UTC_TIMESTAMP())
WHERE updated_at IS NULL;

SET @has_site_sections_updated_at_idx = (
  SELECT COUNT(*)
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = @db_name
    AND TABLE_NAME = 'crawl_jobs'
    AND INDEX_NAME = 'ix_crawl_jobs_updated_at'
);

SET @sql = IF(
  @has_site_sections_updated_at_idx = 0,
  'CREATE INDEX ix_crawl_jobs_updated_at ON crawl_jobs (updated_at)',
  'SELECT "ix_crawl_jobs_updated_at already exists"'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

ALTER TABLE site_sections
  MODIFY COLUMN detail_selector_config JSON NOT NULL;

ALTER TABLE crawl_jobs
  MODIFY COLUMN updated_at DATETIME NOT NULL;
