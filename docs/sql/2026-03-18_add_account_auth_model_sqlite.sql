CREATE TABLE IF NOT EXISTS account_identities (
  id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL REFERENCES portal_users(id),
  identity_type TEXT NOT NULL,
  login_name TEXT NULL,
  password_hash TEXT NULL,
  provider_subject TEXT NULL,
  provider_unionid TEXT NULL,
  provider_app_id TEXT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  verified_at DATETIME NULL,
  last_login_at DATETIME NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  CONSTRAINT uq_account_identities_type_login_name UNIQUE (identity_type, login_name),
  CONSTRAINT uq_account_identities_type_subject_app UNIQUE (identity_type, provider_subject, provider_app_id)
);

CREATE INDEX IF NOT EXISTS ix_account_identities_account_id ON account_identities (account_id);
CREATE INDEX IF NOT EXISTS ix_account_identities_identity_type ON account_identities (identity_type);
CREATE INDEX IF NOT EXISTS ix_account_identities_provider_unionid ON account_identities (provider_unionid);
CREATE INDEX IF NOT EXISTS ix_account_identities_status ON account_identities (status);

CREATE TABLE IF NOT EXISTS account_roles (
  id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL REFERENCES portal_users(id),
  role_code TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  source TEXT NOT NULL DEFAULT 'manual',
  granted_by_account_id TEXT NULL REFERENCES portal_users(id),
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  CONSTRAINT uq_account_roles_account_role_code UNIQUE (account_id, role_code)
);

CREATE INDEX IF NOT EXISTS ix_account_roles_account_id ON account_roles (account_id);
CREATE INDEX IF NOT EXISTS ix_account_roles_role_code ON account_roles (role_code);
CREATE INDEX IF NOT EXISTS ix_account_roles_status ON account_roles (status);
CREATE INDEX IF NOT EXISTS ix_account_roles_granted_by_account_id ON account_roles (granted_by_account_id);

CREATE TABLE IF NOT EXISTS account_entitlements (
  id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL REFERENCES portal_users(id),
  entitlement_code TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  source TEXT NOT NULL DEFAULT 'manual',
  starts_at DATETIME NOT NULL,
  expires_at DATETIME NULL,
  revoked_at DATETIME NULL,
  order_ref TEXT NULL,
  granted_by_account_id TEXT NULL REFERENCES portal_users(id),
  meta_json JSON NOT NULL DEFAULT '{}',
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_account_entitlements_account_id ON account_entitlements (account_id);
CREATE INDEX IF NOT EXISTS ix_account_entitlements_entitlement_code ON account_entitlements (entitlement_code);
CREATE INDEX IF NOT EXISTS ix_account_entitlements_status ON account_entitlements (status);
CREATE INDEX IF NOT EXISTS ix_account_entitlements_expires_at ON account_entitlements (expires_at);
CREATE INDEX IF NOT EXISTS ix_account_entitlements_order_ref ON account_entitlements (order_ref);
CREATE INDEX IF NOT EXISTS ix_account_entitlements_granted_by_account_id ON account_entitlements (granted_by_account_id);
