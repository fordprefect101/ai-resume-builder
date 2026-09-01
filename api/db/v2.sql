CREATE TABLE IF NOT EXISTS career_versions (
  id BIGSERIAL PRIMARY KEY,
  session_id TEXT NOT NULL,
  version_num INTEGER NOT NULL,
  operations JSONB NOT NULL DEFAULT '[]'::jsonb,
  payload_snapshot JSONB NOT NULL,
  summary TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (session_id, version_num)
);

CREATE INDEX IF NOT EXISTS career_versions_session_idx
  ON career_versions (session_id, version_num DESC);

CREATE TABLE IF NOT EXISTS ai_traces (
  id BIGSERIAL PRIMARY KEY,
  session_id TEXT NOT NULL,
  request_type TEXT NOT NULL,
  input_text TEXT,
  trace JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ai_traces_session_idx
  ON ai_traces (session_id, created_at DESC);
