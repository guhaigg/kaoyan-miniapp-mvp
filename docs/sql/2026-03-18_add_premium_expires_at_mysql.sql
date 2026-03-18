-- Premium role expiry migration for MySQL.
-- Safe to rerun: each DDL is guarded by information_schema checks.

SET @schema_name = DATABASE();

SET @has_premium_expires_at = (
  SELECT COUNT(*)
  FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = @schema_name
    AND TABLE_NAME = 'portal_users'
    AND COLUMN_NAME = 'premium_expires_at'
);

SET @ddl = IF(
  @has_premium_expires_at = 0,
  'ALTER TABLE portal_users ADD COLUMN premium_expires_at DATETIME NULL AFTER premium_monitoring_enabled',
  'SELECT "skip: portal_users.premium_expires_at already exists"'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_premium_expires_at_index = (
  SELECT COUNT(*)
  FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = @schema_name
    AND TABLE_NAME = 'portal_users'
    AND INDEX_NAME = 'ix_portal_users_premium_expires_at'
);

SET @ddl = IF(
  @has_premium_expires_at_index = 0,
  'CREATE INDEX ix_portal_users_premium_expires_at ON portal_users (premium_expires_at)',
  'SELECT "skip: ix_portal_users_premium_expires_at already exists"'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
