CREATE TABLE IF NOT EXISTS account_bind_codes (
  id TEXT NOT NULL PRIMARY KEY,
  account_id TEXT NOT NULL,
  code TEXT NOT NULL UNIQUE,
  bind_type TEXT NOT NULL DEFAULT 'wechat_miniapp',
  status TEXT NOT NULL DEFAULT 'active',
  claimed_by_shadow_user_id TEXT NULL,
  expires_at DATETIME NOT NULL,
  claimed_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (account_id) REFERENCES portal_users(id),
  FOREIGN KEY (claimed_by_shadow_user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS ix_account_bind_codes_account_id ON account_bind_codes(account_id);
CREATE INDEX IF NOT EXISTS ix_account_bind_codes_bind_type ON account_bind_codes(bind_type);
CREATE INDEX IF NOT EXISTS ix_account_bind_codes_status ON account_bind_codes(status);
CREATE INDEX IF NOT EXISTS ix_account_bind_codes_expires_at ON account_bind_codes(expires_at);
