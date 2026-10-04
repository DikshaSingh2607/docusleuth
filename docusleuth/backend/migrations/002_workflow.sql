CREATE TABLE IF NOT EXISTS document_summaries (
  document_id uuid PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
  workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','ready','failed')),
  summary text,
  key_entities jsonb,
  error_message text,
  generated_at timestamptz,
  search_vector tsvector GENERATED ALWAYS AS (
    to_tsvector('simple', coalesce(summary,'') || ' ' || coalesce(key_entities::text,''))
  ) STORED
);
CREATE INDEX IF NOT EXISTS document_summaries_search_idx ON document_summaries USING gin(search_vector);

CREATE TABLE IF NOT EXISTS evidence_pins (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  chunk_id uuid REFERENCES chunks(id) ON DELETE SET NULL,
  question text,
  quote text NOT NULL,
  confidence jsonb,
  note text NOT NULL DEFAULT '',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS evidence_pins_workspace_idx ON evidence_pins(workspace_id, created_at DESC);

ALTER TABLE conversations ADD COLUMN IF NOT EXISTS title text;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS citations jsonb;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS confidence jsonb;
