-- Account identity / role / entitlement migration for MySQL.
-- Safe to rerun: every table and index is guarded by information_schema checks.

SET @schema_name = DATABASE();

SET @has_account_identities = (
  SELECT COUNT(*)
  FROM INFORMATION_SCHEMA.TABLES
  WHERE TABLE_SCHEMA = @schema_name
    AND TABLE_NAME = 'account_identities'
);
SET @ddl = IF(
  @has_account_identities = 0,
  'CREATE TABLE account_identities (
    id VARCHAR(36) PRIMARY KEY,
    account_id VARCHAR(36) NOT NULL,
    identity_type VARCHAR(32) NOT NULL,
    login_name VARCHAR(64) NULL,
    password_hash VARCHAR(255) NULL,
    provider_subject VARCHAR(255) NULL,
    provider_unionid VARCHAR(255) NULL,
    provider_app_id VARCHAR(128) NULL,
    status VARCHAR(32) NOT NULL DEFAULT ''active'',
    verified_at DATETIME NULL,
    last_login_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    CONSTRAINT fk_account_identities_account FOREIGN KEY (account_id) REFERENCES portal_users(id),
    CONSTRAINT uq_account_identities_type_login_name UNIQUE (identity_type, login_name),
    CONSTRAINT uq_account_identities_type_subject_app UNIQUE (identity_type, provider_subject, provider_app_id)
  )',
  'SELECT "skip: account_identities already exists"'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_ix_account_identities_account_id = (
  SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = @schema_name AND TABLE_NAME = 'account_identities' AND INDEX_NAME = 'ix_account_identities_account_id'
);
SET @ddl = IF(
  @has_ix_account_identities_account_id = 0,
  'CREATE INDEX ix_account_identities_account_id ON account_identities (account_id)',
  'SELECT "skip: ix_account_identities_account_id exists"'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_ix_account_identities_identity_type = (
  SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = @schema_name AND TABLE_NAME = 'account_identities' AND INDEX_NAME = 'ix_account_identities_identity_type'
);
SET @ddl = IF(
  @has_ix_account_identities_identity_type = 0,
  'CREATE INDEX ix_account_identities_identity_type ON account_identities (identity_type)',
  'SELECT "skip: ix_account_identities_identity_type exists"'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_ix_account_identities_provider_unionid = (
  SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = @schema_name AND TABLE_NAME = 'account_identities' AND INDEX_NAME = 'ix_account_identities_provider_unionid'
);
SET @ddl = IF(
  @has_ix_account_identities_provider_unionid = 0,
  'CREATE INDEX ix_account_identities_provider_unionid ON account_identities (provider_unionid)',
  'SELECT "skip: ix_account_identities_provider_unionid exists"'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_ix_account_identities_status = (
  SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = @schema_name AND TABLE_NAME = 'account_identities' AND INDEX_NAME = 'ix_account_identities_status'
);
SET @ddl = IF(
  @has_ix_account_identities_status = 0,
  'CREATE INDEX ix_account_identities_status ON account_identities (status)',
  'SELECT "skip: ix_account_identities_status exists"'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_account_roles = (
  SELECT COUNT(*)
  FROM INFORMATION_SCHEMA.TABLES
  WHERE TABLE_SCHEMA = @schema_name
    AND TABLE_NAME = 'account_roles'
);
SET @ddl = IF(
  @has_account_roles = 0,
  'CREATE TABLE account_roles (
    id VARCHAR(36) PRIMARY KEY,
    account_id VARCHAR(36) NOT NULL,
    role_code VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT ''active'',
    source VARCHAR(32) NOT NULL DEFAULT ''manual'',
    granted_by_account_id VARCHAR(36) NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    CONSTRAINT fk_account_roles_account FOREIGN KEY (account_id) REFERENCES portal_users(id),
    CONSTRAINT fk_account_roles_granted_by FOREIGN KEY (granted_by_account_id) REFERENCES portal_users(id),
    CONSTRAINT uq_account_roles_account_role_code UNIQUE (account_id, role_code)
  )',
  'SELECT "skip: account_roles already exists"'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_ix_account_roles_account_id = (
  SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = @schema_name AND TABLE_NAME = 'account_roles' AND INDEX_NAME = 'ix_account_roles_account_id'
);
SET @ddl = IF(
  @has_ix_account_roles_account_id = 0,
  'CREATE INDEX ix_account_roles_account_id ON account_roles (account_id)',
  'SELECT "skip: ix_account_roles_account_id exists"'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_ix_account_roles_role_code = (
  SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = @schema_name AND TABLE_NAME = 'account_roles' AND INDEX_NAME = 'ix_account_roles_role_code'
);
SET @ddl = IF(
  @has_ix_account_roles_role_code = 0,
  'CREATE INDEX ix_account_roles_role_code ON account_roles (role_code)',
  'SELECT "skip: ix_account_roles_role_code exists"'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_ix_account_roles_status = (
  SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = @schema_name AND TABLE_NAME = 'account_roles' AND INDEX_NAME = 'ix_account_roles_status'
);
SET @ddl = IF(
  @has_ix_account_roles_status = 0,
  'CREATE INDEX ix_account_roles_status ON account_roles (status)',
  'SELECT "skip: ix_account_roles_status exists"'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_ix_account_roles_granted_by = (
  SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = @schema_name AND TABLE_NAME = 'account_roles' AND INDEX_NAME = 'ix_account_roles_granted_by_account_id'
);
SET @ddl = IF(
  @has_ix_account_roles_granted_by = 0,
  'CREATE INDEX ix_account_roles_granted_by_account_id ON account_roles (granted_by_account_id)',
  'SELECT "skip: ix_account_roles_granted_by_account_id exists"'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_account_entitlements = (
  SELECT COUNT(*)
  FROM INFORMATION_SCHEMA.TABLES
  WHERE TABLE_SCHEMA = @schema_name
    AND TABLE_NAME = 'account_entitlements'
);
SET @ddl = IF(
  @has_account_entitlements = 0,
  'CREATE TABLE account_entitlements (
    id VARCHAR(36) PRIMARY KEY,
    account_id VARCHAR(36) NOT NULL,
    entitlement_code VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT ''active'',
    source VARCHAR(32) NOT NULL DEFAULT ''manual'',
    starts_at DATETIME NOT NULL,
    expires_at DATETIME NULL,
    revoked_at DATETIME NULL,
    order_ref VARCHAR(128) NULL,
    granted_by_account_id VARCHAR(36) NULL,
    meta_json JSON NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    CONSTRAINT fk_account_entitlements_account FOREIGN KEY (account_id) REFERENCES portal_users(id),
    CONSTRAINT fk_account_entitlements_granted_by FOREIGN KEY (granted_by_account_id) REFERENCES portal_users(id)
  )',
  'SELECT "skip: account_entitlements already exists"'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_ix_account_entitlements_account_id = (
  SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = @schema_name AND TABLE_NAME = 'account_entitlements' AND INDEX_NAME = 'ix_account_entitlements_account_id'
);
SET @ddl = IF(
  @has_ix_account_entitlements_account_id = 0,
  'CREATE INDEX ix_account_entitlements_account_id ON account_entitlements (account_id)',
  'SELECT "skip: ix_account_entitlements_account_id exists"'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_ix_account_entitlements_entitlement_code = (
  SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = @schema_name AND TABLE_NAME = 'account_entitlements' AND INDEX_NAME = 'ix_account_entitlements_entitlement_code'
);
SET @ddl = IF(
  @has_ix_account_entitlements_entitlement_code = 0,
  'CREATE INDEX ix_account_entitlements_entitlement_code ON account_entitlements (entitlement_code)',
  'SELECT "skip: ix_account_entitlements_entitlement_code exists"'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_ix_account_entitlements_status = (
  SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = @schema_name AND TABLE_NAME = 'account_entitlements' AND INDEX_NAME = 'ix_account_entitlements_status'
);
SET @ddl = IF(
  @has_ix_account_entitlements_status = 0,
  'CREATE INDEX ix_account_entitlements_status ON account_entitlements (status)',
  'SELECT "skip: ix_account_entitlements_status exists"'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_ix_account_entitlements_expires_at = (
  SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = @schema_name AND TABLE_NAME = 'account_entitlements' AND INDEX_NAME = 'ix_account_entitlements_expires_at'
);
SET @ddl = IF(
  @has_ix_account_entitlements_expires_at = 0,
  'CREATE INDEX ix_account_entitlements_expires_at ON account_entitlements (expires_at)',
  'SELECT "skip: ix_account_entitlements_expires_at exists"'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_ix_account_entitlements_order_ref = (
  SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = @schema_name AND TABLE_NAME = 'account_entitlements' AND INDEX_NAME = 'ix_account_entitlements_order_ref'
);
SET @ddl = IF(
  @has_ix_account_entitlements_order_ref = 0,
  'CREATE INDEX ix_account_entitlements_order_ref ON account_entitlements (order_ref)',
  'SELECT "skip: ix_account_entitlements_order_ref exists"'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_ix_account_entitlements_granted_by = (
  SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = @schema_name AND TABLE_NAME = 'account_entitlements' AND INDEX_NAME = 'ix_account_entitlements_granted_by_account_id'
);
SET @ddl = IF(
  @has_ix_account_entitlements_granted_by = 0,
  'CREATE INDEX ix_account_entitlements_granted_by_account_id ON account_entitlements (granted_by_account_id)',
  'SELECT "skip: ix_account_entitlements_granted_by_account_id exists"'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;
