"""Email + password auth. Verify/reset links are logged until SMTP exists."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt
import psycopg
from fastapi import HTTPException, Request, Response

logger = logging.getLogger("auth")

COOKIE_NAME = "rb_session"
SESSION_DAYS = 30
VERIFY_HOURS = 48
RESET_HOURS = 2
MIN_PASSWORD = 8
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

DATABASE_URL = os.getenv("DATABASE_URL")
PUBLIC_APP_URL = os.getenv("PUBLIC_APP_URL", "http://localhost:5173").rstrip("/")


def _db() -> str:
    url = os.getenv("DATABASE_URL") or DATABASE_URL
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url


def smtp_configured() -> bool:
    return bool(os.getenv("SMTP_HOST") or os.getenv("RESEND_API_KEY"))


def ensure_auth_schema() -> None:
    sql = (Path(__file__).parent / "db" / "auth.sql").read_text()
    statements = [part.strip() for part in sql.split(";") if part.strip()]
    with psycopg.connect(_db()) as conn:
        with conn.cursor() as cur:
            for statement in statements:
                cur.execute(statement)
        conn.commit()


def normalize_email(email: str) -> str:
    return str(email or "").strip().lower()


def validate_email(email: str) -> str:
    value = normalize_email(email)
    if not EMAIL_RE.match(value):
        raise HTTPException(status_code=400, detail="Enter a valid email address")
    return value


def validate_password(password: str) -> str:
    if not isinstance(password, str) or len(password) < MIN_PASSWORD:
        raise HTTPException(
            status_code=400,
            detail=f"Password must be at least {MIN_PASSWORD} characters",
        )
    return password


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def cookie_secure() -> bool:
    return os.getenv("COOKIE_SECURE", "false").lower() == "true"


def set_session_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        raw_token,
        httponly=True,
        samesite="lax",
        secure=cookie_secure(),
        max_age=SESSION_DAYS * 24 * 3600,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


def issue_session(cur, user_id: str) -> str:
    raw = secrets.token_urlsafe(32)
    cur.execute(
        """
        INSERT INTO auth_sessions (id, user_id, token_hash, expires_at)
        VALUES (%s, %s, %s, %s)
        """,
        (
            str(uuid.uuid4()),
            user_id,
            _hash_token(raw),
            _now() + timedelta(days=SESSION_DAYS),
        ),
    )
    return raw


def get_current_user(request: Request) -> dict | None:
    raw = request.cookies.get(COOKIE_NAME)
    if not raw:
        return None
    with psycopg.connect(_db()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.id, u.email, u.email_verified_at
                FROM auth_sessions s
                JOIN users u ON u.id = s.user_id
                WHERE s.token_hash = %s AND s.expires_at > now()
                """,
                (_hash_token(raw),),
            )
            row = cur.fetchone()
    if not row:
        return None
    return {
        "id": str(row[0]),
        "email": row[1],
        "emailVerified": row[2] is not None,
    }


def revoke_session(raw_token: str) -> None:
    with psycopg.connect(_db()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM auth_sessions WHERE token_hash = %s",
                (_hash_token(raw_token),),
            )
        conn.commit()


def require_user(request: Request) -> dict:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Log in to continue")
    return user


def require_verified_user(request: Request) -> dict:
    user = require_user(request)
    if not user["emailVerified"]:
        raise HTTPException(
            status_code=403,
            detail="Verify your email before saving or logging in",
        )
    return user


def user_resume_session(cur, user_id: str) -> tuple | None:
    cur.execute(
        """
        SELECT session_id, payload, version
        FROM resume_snapshots
        WHERE user_id = %s
        """,
        (user_id,),
    )
    return cur.fetchone()


def load_snapshot(cur, session_id: str, user: dict | None) -> tuple:
    cur.execute(
        """
        SELECT session_id, payload, version, user_id
        FROM resume_snapshots
        WHERE session_id = %s
        """,
        (session_id,),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Resume not found")
    owner = row[3]
    if owner is not None and (user is None or user["id"] != str(owner)):
        raise HTTPException(
            status_code=403,
            detail="This resume belongs to another account",
        )
    return row


def issue_email_token(cur, user_id: str, purpose: str, hours: int) -> str:
    cur.execute(
        """
        UPDATE email_tokens
        SET used_at = now()
        WHERE user_id = %s AND purpose = %s AND used_at IS NULL
        """,
        (user_id, purpose),
    )
    raw = secrets.token_urlsafe(32)
    cur.execute(
        """
        INSERT INTO email_tokens (id, user_id, purpose, token_hash, expires_at)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            str(uuid.uuid4()),
            user_id,
            purpose,
            _hash_token(raw),
            _now() + timedelta(hours=hours),
        ),
    )
    return raw


def app_link(kind: str, token: str) -> str:
    return f"{PUBLIC_APP_URL}/?{kind}={token}"


def deliver_link(kind: str, email: str, token: str) -> str:
    url = app_link(kind, token)
    logger.warning("AUTH %s link for %s: %s", kind, email, url)
    print(f"[auth] {kind} link for {email}: {url}", flush=True)
    return url


def consume_email_token(cur, raw_token: str, purpose: str) -> str:
    cur.execute(
        """
        SELECT id, user_id, expires_at, used_at
        FROM email_tokens
        WHERE token_hash = %s AND purpose = %s
        """,
        (_hash_token(raw_token), purpose),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=400, detail="This link is invalid")
    token_id, user_id, expires_at, used_at = row
    if used_at is not None:
        raise HTTPException(status_code=400, detail="This link was already used")
    if expires_at < _now():
        raise HTTPException(status_code=400, detail="This link has expired")
    cur.execute(
        "UPDATE email_tokens SET used_at = now() WHERE id = %s",
        (token_id,),
    )
    return str(user_id)
