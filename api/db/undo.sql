CREATE TABLE IF NOT EXISTS resume_undo (
  id BIGSERIAL PRIMARY KEY,
  session_id TEXT NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS resume_undo_session_created_idx
  ON resume_undo (session_id, created_at DESC);