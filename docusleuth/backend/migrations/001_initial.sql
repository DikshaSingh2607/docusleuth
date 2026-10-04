CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS workspaces (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_hash text NOT NULL UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now(),
  last_seen_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz
);
CREATE TABLE IF NOT EXISTS documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  filename text NOT NULL,
  safe_filename text NOT NULL,
  mime_type text NOT NULL,
  size_bytes integer NOT NULL,
  content bytea NOT NULL,
  storage_key text NOT NULL,
  status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','extracting','OCR','indexing','ready','failed')),
  error_message text,
  document_date_hint text,
  version_hint text,
  section_citation_only boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS documents_workspace_idx ON documents(workspace_id, created_at DESC);
CREATE TABLE IF NOT EXISTS document_pages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  page_number integer,
  section_heading text,
  text_content text NOT NULL,
  ocr_confidence real,
  ocr_boxes jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ingestion_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','extracting','OCR','indexing','ready','failed')),
  attempts integer NOT NULL DEFAULT 0,
  lease_until timestamptz,
  error_message text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ingestion_jobs_ready_idx ON ingestion_jobs(status, lease_until, created_at);
CREATE TABLE IF NOT EXISTS chunks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  page_id uuid REFERENCES document_pages(id) ON DELETE SET NULL,
  workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  text_content text NOT NULL,
  page_number integer,
  section_heading text,
  start_offset integer,
  end_offset integer,
  ocr_confidence real,
  embedding vector(1536),
  search_vector tsvector GENERATED ALWAYS AS (to_tsvector('simple', coalesce(text_content,''))) STORED,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS chunks_workspace_idx ON chunks(workspace_id, document_id);
CREATE INDEX IF NOT EXISTS chunks_search_idx ON chunks USING gin(search_vector);
CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE TABLE IF NOT EXISTS document_entities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  chunk_id uuid REFERENCES chunks(id) ON DELETE SET NULL,
  page_number integer,
  entity_type text NOT NULL,
  subject text NOT NULL,
  normalized_subject text NOT NULL,
  raw_value text NOT NULL,
  normalized_value text NOT NULL,
  confidence real,
  document_date_hint text,
  version_hint text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS entities_compare_idx ON document_entities(workspace_id, normalized_subject, entity_type, normalized_value);
CREATE TABLE IF NOT EXISTS conflict_scans (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','ready','failed')),
  candidate_count integer NOT NULL DEFAULT 0,
  cap_hit boolean NOT NULL DEFAULT false,
  error_message text,
  created_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);
CREATE TABLE IF NOT EXISTS conflicts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  scan_id uuid REFERENCES conflict_scans(id) ON DELETE CASCADE,
  conflict_key text NOT NULL,
  subject text NOT NULL,
  field_type text NOT NULL,
  severity text NOT NULL CHECK (severity IN ('high','medium','low')),
  nli_label text NOT NULL CHECK (nli_label IN ('entailment','contradiction','neutral')),
  subject_match boolean NOT NULL,
  reason text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(workspace_id, conflict_key)
);
CREATE INDEX IF NOT EXISTS conflicts_workspace_idx ON conflicts(workspace_id, severity, created_at DESC);
CREATE TABLE IF NOT EXISTS conflict_claims (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conflict_id uuid NOT NULL REFERENCES conflicts(id) ON DELETE CASCADE,
  document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  chunk_id uuid REFERENCES chunks(id) ON DELETE SET NULL,
  filename text NOT NULL,
  page_number integer,
  section_heading text,
  quote text NOT NULL,
  claim_value text NOT NULL,
  document_date_hint text,
  version_hint text
);
CREATE TABLE IF NOT EXISTS trust_decisions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  conflict_id uuid NOT NULL REFERENCES conflicts(id) ON DELETE CASCADE,
  session_hash text NOT NULL,
  trusted_claim_id uuid NOT NULL REFERENCES conflict_claims(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(workspace_id, conflict_id, session_hash)
);
CREATE TABLE IF NOT EXISTS conversations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  role text NOT NULL CHECK (role IN ('user','assistant')),
  content text NOT NULL,
  citations jsonb,
  confidence jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS rate_limits (
  workspace_id uuid PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
  window_start timestamptz NOT NULL DEFAULT date_trunc('hour', now()),
  question_count integer NOT NULL DEFAULT 0
);
