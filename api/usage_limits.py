"""Daily AI limits per visitor: the one place that counts what costs money.

A visitor is the logged-in user, else the session id (else the network address, for
calls that have neither). Counts live in Postgres, one row per visitor, kind and UTC day,
so the day resets at UTC midnight. Every endpoint that calls a paid model goes through
`charge`; evals check that none skips it.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone

import psycopg
from fastapi import HTTPException, Request

from byok import has_own_key

# kind -> (setting name, default per day). Names are spelled out so .env.example can be checked.
LIMITS: dict[str, tuple[str, int]] = {
    "chat": ("DAILY_LIMIT_CHAT", 30),
    "mutate": ("DAILY_LIMIT_MUTATE", 30),
    "realtime": ("DAILY_LIMIT_REALTIME", 5),
    "rewrite": ("DAILY_LIMIT_REWRITE", 20),
    "analyze_jd": ("DAILY_LIMIT_ANALYZE_JD", 5),
    "pdf_import": ("DAILY_LIMIT_PDF_IMPORT", 3),
    "enrichment": ("DAILY_LIMIT_ENRICHMENT", 30),
}

# Plain names for the message shown to the person.
LABELS = {
    "chat": "chat messages",
    "mutate": "resume edits",
    "realtime": "voice calls",
    "rewrite": "point rewrites",
    "analyze_jd": "job tailoring runs",
    "pdf_import": "PDF imports",
    "enrichment": "automatic tidy-ups",
}

_CHARGE_SQL = (
    "INSERT INTO usage_counts (visitor, kind, day, count) VALUES (%s, %s, %s, %s) "
    "ON CONFLICT (visitor, kind, day) DO UPDATE SET count = usage_counts.count + EXCLUDED.count "
    "WHERE usage_counts.count + EXCLUDED.count <= %s RETURNING count"
)


def limit_for(kind: str) -> int:
    name, default = LIMITS[kind]
    raw = os.getenv(name)
    try:
        value = int(raw) if raw else default
    except ValueError:
        return default
    return max(value, 0)


def today(now: datetime | None = None) -> date:
    return (now or datetime.now(timezone.utc)).date()


def resets_at(now: datetime | None = None) -> datetime:
    start = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return datetime.combine(start.date() + timedelta(days=1), datetime.min.time(), timezone.utc)


def visitor_key(request: Request, user: dict | None, session_id: str | None = None) -> str:
    if user:
        return f"user:{user['id']}"
    if session_id:
        return f"session:{session_id}"
    host = request.client.host if request.client else "unknown"
    return f"ip:{host}"


def over_limit_message(kind: str, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    reset = resets_at(now)
    hours = max(1, round((reset - now).total_seconds() / 3600))
    return (
        f"You have used today's free limit for {LABELS[kind]}. It resets at "
        f"{reset:%H:%M} UTC (in about {hours} {'hour' if hours == 1 else 'hours'}). "
        "You can keep going now by adding your own OpenAI key."
    )


def charge_cursor(cur, visitor: str, kind: str, amount: int = 1, now: datetime | None = None) -> bool:
    """Add `amount` to today's count unless that passes the limit. True when allowed."""
    limit = limit_for(kind)
    if amount > limit:
        return False
    cur.execute(_CHARGE_SQL, (visitor, kind, today(now), amount, limit))
    return cur.fetchone() is not None


def spend(request: Request, user: dict | None, kind: str, session_id: str | None = None) -> bool:
    """Count one use. True when allowed; False when the visitor is over today's limit.

    A request that carries the person's own key costs us nothing, so it is not counted."""
    if has_own_key():
        return True
    visitor = visitor_key(request, user, session_id)
    with psycopg.connect(os.getenv("DATABASE_URL") or "") as conn:
        with conn.cursor() as cur:
            allowed = charge_cursor(cur, visitor, kind)
        conn.commit()
    return allowed


def charge(request: Request, user: dict | None, kind: str, session_id: str | None = None) -> None:
    """Count one use or refuse with a 429 that says when the limit resets."""
    if not spend(request, user, kind, session_id):
        raise HTTPException(
            status_code=429,
            detail=over_limit_message(kind),
            headers={"Retry-After": str(int((resets_at() - datetime.now(timezone.utc)).total_seconds()))},
        )
