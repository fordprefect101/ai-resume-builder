"""Version history — snapshot + operation log per meaningful mutation."""

from __future__ import annotations

import json
from pathlib import Path

import psycopg

DATABASE_URL = None


def _db_url() -> str:
    import os

    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url


def ensure_v2_schema() -> None:
    sql = (Path(__file__).parent / "db" / "v2.sql").read_text()
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    with psycopg.connect(_db_url()) as conn:
        with conn.cursor() as cur:
            for stmt in statements:
                cur.execute(stmt)
        conn.commit()


def record_version(
    cur,
    session_id: str,
    version_num: int,
    payload: dict,
    operations: list[dict],
    summary: str,
) -> None:
    cur.execute(
        """
        INSERT INTO career_versions
          (session_id, version_num, operations, payload_snapshot, summary)
        VALUES (%s, %s, %s::jsonb, %s::jsonb, %s)
        ON CONFLICT (session_id, version_num) DO UPDATE
          SET operations = EXCLUDED.operations,
              payload_snapshot = EXCLUDED.payload_snapshot,
              summary = EXCLUDED.summary
        """,
        (
            session_id,
            version_num,
            json.dumps(operations),
            json.dumps(payload),
            summary,
        ),
    )


def list_versions(cur, session_id: str, limit: int = 50) -> list[dict]:
    cur.execute(
        """
        SELECT version_num, summary, operations, created_at
        FROM career_versions
        WHERE session_id = %s
        ORDER BY version_num DESC
        LIMIT %s
        """,
        (session_id, limit),
    )
    rows = cur.fetchall()
    return [
        {
            "version": row[0],
            "summary": row[1],
            "operations": row[2],
            "createdAt": row[3].isoformat() if row[3] else None,
        }
        for row in rows
    ]


def get_version_snapshot(cur, session_id: str, version_num: int) -> dict | None:
    cur.execute(
        """
        SELECT payload_snapshot
        FROM career_versions
        WHERE session_id = %s AND version_num = %s
        """,
        (session_id, version_num),
    )
    row = cur.fetchone()
    return row[0] if row else None
