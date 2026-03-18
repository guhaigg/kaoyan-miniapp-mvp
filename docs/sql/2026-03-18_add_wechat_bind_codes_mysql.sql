CREATE TABLE IF NOT EXISTS account_bind_codes (
  id VARCHAR(36) NOT NULL PRIMARY KEY,
  account_id VARCHAR(36) NOT NULL,
  code VARCHAR(16) NOT NULL,
  bind_type VARCHAR(32) NOT NULL DEFAULT 'wechat_miniapp',
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  claimed_by_shadow_user_id VARCHAR(36) NULL,
  expires_at DATETIME(6) NOT NULL,
  claimed_at DATETIME(6) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  CONSTRAINT uq_account_bind_codes_code UNIQUE (code),
  CONSTRAINT fk_account_bind_codes_account_id FOREIGN KEY (account_id) REFERENCES portal_users(id),
  CONSTRAINT fk_account_bind_codes_shadow_user_id FOREIGN KEY (claimed_by_shadow_user_id) REFERENCES users(id)
);

CREATE INDEX ix_account_bind_codes_account_id ON account_bind_codes(account_id);
CREATE INDEX ix_account_bind_codes_bind_type ON account_bind_codes(bind_type);
CREATE INDEX ix_account_bind_codes_status ON account_bind_codes(status);
CREATE INDEX ix_account_bind_codes_expires_at ON account_bind_codes(expires_at);
