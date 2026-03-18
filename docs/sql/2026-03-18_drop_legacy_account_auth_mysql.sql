-- Physically remove legacy account-auth objects after runtime has fully switched
-- to account_identities / account_roles / account_entitlements.

SET @db_name = DATABASE();

SET @has_admin_accounts = (
  SELECT COUNT(*)
  FROM information_schema.TABLES
  WHERE TABLE_SCHEMA = @db_name
    AND TABLE_NAME = 'admin_accounts'
);

SET @drop_admin_accounts = IF(
  @has_admin_accounts = 1,
  'DROP TABLE admin_accounts',
  'SELECT "skip: admin_accounts already removed"'
);
PREPARE stmt FROM @drop_admin_accounts;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_premium_expires_at_index = (
  SELECT COUNT(*)
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = @db_name
    AND TABLE_NAME = 'portal_users'
    AND INDEX_NAME = 'ix_portal_users_premium_expires_at'
);

SET @drop_premium_expires_at_index = IF(
  @has_premium_expires_at_index = 1,
  'DROP INDEX ix_portal_users_premium_expires_at ON portal_users',
  'SELECT "skip: ix_portal_users_premium_expires_at already removed"'
);
PREPARE stmt FROM @drop_premium_expires_at_index;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_premium_monitoring_enabled_index = (
  SELECT COUNT(*)
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = @db_name
    AND TABLE_NAME = 'portal_users'
    AND INDEX_NAME = 'ix_portal_users_premium_monitoring_enabled'
);

SET @drop_premium_monitoring_enabled_index = IF(
  @has_premium_monitoring_enabled_index = 1,
  'DROP INDEX ix_portal_users_premium_monitoring_enabled ON portal_users',
  'SELECT "skip: ix_portal_users_premium_monitoring_enabled already removed"'
);
PREPARE stmt FROM @drop_premium_monitoring_enabled_index;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_premium_expires_at = (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db_name
    AND TABLE_NAME = 'portal_users'
    AND COLUMN_NAME = 'premium_expires_at'
);

SET @drop_premium_expires_at = IF(
  @has_premium_expires_at = 1,
  'ALTER TABLE portal_users DROP COLUMN premium_expires_at',
  'SELECT "skip: portal_users.premium_expires_at already removed"'
);
PREPARE stmt FROM @drop_premium_expires_at;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_premium_monitoring_enabled = (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db_name
    AND TABLE_NAME = 'portal_users'
    AND COLUMN_NAME = 'premium_monitoring_enabled'
);

SET @drop_premium_monitoring_enabled = IF(
  @has_premium_monitoring_enabled = 1,
  'ALTER TABLE portal_users DROP COLUMN premium_monitoring_enabled',
  'SELECT "skip: portal_users.premium_monitoring_enabled already removed"'
);
PREPARE stmt FROM @drop_premium_monitoring_enabled;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
