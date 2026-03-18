ALTER TABLE contents ADD COLUMN content_fingerprint TEXT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_contents_content_fingerprint ON contents (content_fingerprint);
