"""AI request observability traces."""

from __future__ import annotations

import json

import psycopg


def log_trace(
    cur,
    session_id: str,
    request_type: str,
    input_text: str | None,
    trace: dict,
) -> int:
    cur.execute(
        """
        INSERT INTO ai_traces (session_id, request_type, input_text, trace)
        VALUES (%s, %s, %s, %s::jsonb)
        RETURNING id
        """,
        (session_id, request_type, input_text, json.dumps(trace)),
    )
    row = cur.fetchone()
    return row[0] if row else 0


def get_trace(cur, trace_id: int) -> dict | None:
    cur.execute(
        """
        SELECT session_id, request_type, input_text, trace, created_at
        FROM ai_traces WHERE id = %s
        """,
        (trace_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    return {
        "id": trace_id,
        "sessionId": row[0],
        "requestType": row[1],
        "inputText": row[2],
        "trace": row[3],
        "createdAt": row[4].isoformat() if row[4] else None,
    }
