CREATE TABLE IF NOT EXISTS account_payment_orders (
  id TEXT PRIMARY KEY NOT NULL,
  account_id TEXT NOT NULL,
  entitlement_code TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'web_pay',
  status TEXT NOT NULL DEFAULT 'pending',
  duration_days INTEGER NOT NULL DEFAULT 30,
  amount_cents INTEGER NOT NULL DEFAULT 0,
  currency TEXT NOT NULL DEFAULT 'CNY',
  order_ref TEXT NOT NULL,
  provider_name TEXT,
  provider_order_ref TEXT,
  provider_payment_ref TEXT,
  paid_at TEXT,
  canceled_at TEXT,
  meta_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(account_id) REFERENCES portal_users(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_account_payment_orders_order_ref
  ON account_payment_orders(order_ref);
CREATE INDEX IF NOT EXISTS ix_account_payment_orders_account_id
  ON account_payment_orders(account_id);
CREATE INDEX IF NOT EXISTS ix_account_payment_orders_entitlement_code
  ON account_payment_orders(entitlement_code);
CREATE INDEX IF NOT EXISTS ix_account_payment_orders_source
  ON account_payment_orders(source);
CREATE INDEX IF NOT EXISTS ix_account_payment_orders_status
  ON account_payment_orders(status);
CREATE INDEX IF NOT EXISTS ix_account_payment_orders_provider_order_ref
  ON account_payment_orders(provider_order_ref);
CREATE INDEX IF NOT EXISTS ix_account_payment_orders_provider_payment_ref
  ON account_payment_orders(provider_payment_ref);
