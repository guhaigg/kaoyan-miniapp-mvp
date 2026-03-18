-- Premium role expiry migration for SQLite.
-- SQLite lacks ADD COLUMN IF NOT EXISTS in many deployed versions,
-- so run only once on an existing DB.

ALTER TABLE portal_users
  ADD COLUMN premium_expires_at DATETIME NULL;

CREATE INDEX IF NOT EXISTS ix_portal_users_premium_expires_at
  ON portal_users (premium_expires_at);
