import json

MAX_UNDO = 20


def push_undo(cur, session_id: str, payload) -> None:
    """Save current payload before a mutation. Trims old entries."""
    cur.execute(
        """
        INSERT INTO resume_undo (session_id, payload)
        VALUES (%s, %s::jsonb)
        """,
        (session_id, json.dumps(payload)),
    )
    cur.execute(
        """
        DELETE FROM resume_undo
        WHERE id IN (
          SELECT id FROM resume_undo
          WHERE session_id = %s
          ORDER BY created_at DESC, id DESC
          OFFSET %s
        )
        """,
        (session_id, MAX_UNDO),
    )


def pop_undo(cur, session_id: str):
    """
    Return the most recent undo payload, or None.
    Deletes that row so undo is one-shot per entry.
    """
    cur.execute(
        """
        SELECT id, payload
        FROM resume_undo
        WHERE session_id = %s
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (session_id,),
    )
    row = cur.fetchone()
    if not row:
        return None

    undo_id, payload = row
    cur.execute("DELETE FROM resume_undo WHERE id = %s", (undo_id,))
    return payload