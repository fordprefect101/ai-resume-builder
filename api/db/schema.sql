CREATE TABLE IF NOT EXISTS resume_snapshots (
  session_id TEXT PRIMARY KEY,
  payload JSONB NOT NULL,
  version INTEGER NOT NULL DEFAULT 1,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);