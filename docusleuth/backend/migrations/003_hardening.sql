ALTER TABLE documents ADD COLUMN IF NOT EXISTS content_sha256 text;
CREATE UNIQUE INDEX IF NOT EXISTS documents_workspace_hash_idx ON documents(workspace_id, content_sha256) WHERE content_sha256 IS NOT NULL;

CREATE TABLE IF NOT EXISTS request_rate_limits (
  scope_key text NOT NULL,
  action text NOT NULL,
  window_start timestamptz NOT NULL,
  request_count integer NOT NULL DEFAULT 0,
  PRIMARY KEY (scope_key, action, window_start)
);
CREATE INDEX IF NOT EXISTS request_rate_limits_window_idx ON request_rate_limits(window_start);
