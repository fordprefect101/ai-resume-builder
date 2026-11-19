CREATE TABLE IF NOT EXISTS usage_counts (
  visitor TEXT NOT NULL,
  kind TEXT NOT NULL,
  day DATE NOT NULL,
  count INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (visitor, kind, day)
)
