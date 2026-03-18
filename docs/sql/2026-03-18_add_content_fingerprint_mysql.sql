ALTER TABLE contents
  ADD COLUMN content_fingerprint VARCHAR(64) NULL AFTER major;

CREATE UNIQUE INDEX uq_contents_content_fingerprint ON contents (content_fingerprint);

