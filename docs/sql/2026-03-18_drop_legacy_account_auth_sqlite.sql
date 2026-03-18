-- SQLite 3.35+ required for DROP COLUMN.
-- Physically remove legacy account-auth objects after runtime has fully switched
-- to account_identities / account_roles / account_entitlements.

DROP TABLE IF EXISTS admin_accounts;

DROP INDEX IF EXISTS ix_portal_users_premium_expires_at;
DROP INDEX IF EXISTS ix_portal_users_premium_monitoring_enabled;

ALTER TABLE portal_users DROP COLUMN premium_expires_at;
ALTER TABLE portal_users DROP COLUMN premium_monitoring_enabled;
