"""HTTP routes for email + password auth."""

import os
import uuid

import psycopg
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from auth import (
    COOKIE_NAME,
    VERIFY_HOURS,
    RESET_HOURS,
    check_password,
    clear_session_cookie,
    consume_email_token,
    deliver_link,
    get_current_user,
    hash_password,
    issue_email_token,
    issue_session,
    require_verified_user,
    revoke_session,
    set_session_cookie,
    smtp_configured,
    user_resume_session,
    validate_email,
    validate_password,
)


def _db() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url


router = APIRouter()


class EmailPasswordBody(BaseModel):
    email: str
    password: str


class EmailBody(BaseModel):
    email: str


class TokenBody(BaseModel):
    token: str


class ResetBody(BaseModel):
    token: str
    password: str


class ClaimBody(BaseModel):
    sessionId: str


def _public_user(user: dict, session_id: str | None = None) -> dict:
    return {
        "email": user["email"],
        "emailVerified": user["emailVerified"],
        "resumeSessionId": session_id,
    }


@router.post("/auth/signup")
def signup(body: EmailPasswordBody):
    email = validate_email(body.email)
    password = validate_password(body.password)
    user_id = str(uuid.uuid4())

    with psycopg.connect(_db()) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cur.fetchone():
                raise HTTPException(
                    status_code=409,
                    detail="An account with this email already exists",
                )
            cur.execute(
                """
                INSERT INTO users (id, email, password_hash)
                VALUES (%s, %s, %s)
                """,
                (user_id, email, hash_password(password)),
            )
            raw = issue_email_token(cur, user_id, "verify", VERIFY_HOURS)
        conn.commit()

    url = deliver_link("verify", email, raw)
    result = {
        "ok": True,
        "message": "Check your email to verify this account before logging in.",
    }
    if not smtp_configured():
        result["devVerifyUrl"] = url
    return result


@router.post("/auth/login")
def login(body: EmailPasswordBody, response: Response):
    email = validate_email(body.email)
    password = validate_password(body.password)

    with psycopg.connect(_db()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, password_hash, email_verified_at
                FROM users WHERE email = %s
                """,
                (email,),
            )
            row = cur.fetchone()
            if not row or not check_password(password, row[1]):
                raise HTTPException(
                    status_code=401, detail="Invalid email or password"
                )
            user_id = str(row[0])
            if row[2] is None:
                raw = issue_email_token(cur, user_id, "verify", VERIFY_HOURS)
                conn.commit()
                body_out = {"detail": "Verify your email before logging in"}
                if not smtp_configured():
                    body_out["devVerifyUrl"] = deliver_link("verify", email, raw)
                return JSONResponse(status_code=403, content=body_out)
            token = issue_session(cur, user_id)
            resume = user_resume_session(cur, user_id)
        conn.commit()

    set_session_cookie(response, token)
    return {
        "ok": True,
        "user": _public_user(
            {
                "email": email,
                "emailVerified": True,
            },
            resume[0] if resume else None,
        ),
    }


@router.post("/auth/logout")
def logout(request: Request, response: Response):
    raw = request.cookies.get(COOKIE_NAME)
    if raw:
        revoke_session(raw)
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/auth/me")
def me(request: Request):
    user = get_current_user(request)
    if not user:
        return {"user": None}
    with psycopg.connect(_db()) as conn:
        with conn.cursor() as cur:
            resume = user_resume_session(cur, user["id"])
    return {
        "user": _public_user(user, resume[0] if resume else None),
    }


@router.post("/auth/verify")
def verify(body: TokenBody, response: Response):
    with psycopg.connect(_db()) as conn:
        with conn.cursor() as cur:
            user_id = consume_email_token(cur, body.token, "verify")
            cur.execute(
                """
                UPDATE users
                SET email_verified_at = COALESCE(email_verified_at, now())
                WHERE id = %s
                RETURNING email
                """,
                (user_id,),
            )
            email = cur.fetchone()[0]
            token = issue_session(cur, user_id)
            resume = user_resume_session(cur, user_id)
        conn.commit()

    set_session_cookie(response, token)
    return {
        "ok": True,
        "user": _public_user(
            {"email": email, "emailVerified": True},
            resume[0] if resume else None,
        ),
    }


@router.post("/auth/forgot")
def forgot(body: EmailBody):
    email = validate_email(body.email)
    result = {
        "ok": True,
        "message": "If that email exists, a reset link was created.",
    }
    with psycopg.connect(_db()) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            row = cur.fetchone()
            if not row:
                return result
            raw = issue_email_token(cur, str(row[0]), "reset", RESET_HOURS)
        conn.commit()
    url = deliver_link("reset", email, raw)
    if not smtp_configured():
        result["devResetUrl"] = url
    return result


@router.post("/auth/reset")
def reset_password(body: ResetBody):
    password = validate_password(body.password)
    with psycopg.connect(_db()) as conn:
        with conn.cursor() as cur:
            user_id = consume_email_token(cur, body.token, "reset")
            cur.execute(
                "UPDATE users SET password_hash = %s WHERE id = %s",
                (hash_password(password), user_id),
            )
            cur.execute("DELETE FROM auth_sessions WHERE user_id = %s", (user_id,))
        conn.commit()
    return {"ok": True, "message": "Password updated. You can log in now."}


@router.post("/auth/resend-verify")
def resend_verify(body: EmailBody):
    email = validate_email(body.email)
    result = {
        "ok": True,
        "message": "If that email exists and is unverified, a new link was created.",
    }
    with psycopg.connect(_db()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, email_verified_at FROM users WHERE email = %s
                """,
                (email,),
            )
            row = cur.fetchone()
            if not row or row[1] is not None:
                return result
            raw = issue_email_token(cur, str(row[0]), "verify", VERIFY_HOURS)
        conn.commit()
    url = deliver_link("verify", email, raw)
    if not smtp_configured():
        result["devVerifyUrl"] = url
    return result


@router.post("/auth/claim")
def claim_resume(request: Request, body: ClaimBody):
    user = require_verified_user(request)
    session_id = body.sessionId.strip()
    if not session_id:
        raise HTTPException(status_code=400, detail="sessionId is required")

    with psycopg.connect(_db()) as conn:
        with conn.cursor() as cur:
            existing = user_resume_session(cur, user["id"])
            cur.execute(
                """
                SELECT session_id, user_id, payload, version
                FROM resume_snapshots
                WHERE session_id = %s
                """,
                (session_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Resume not found")
            owner = row[1]
            if owner is not None and str(owner) == user["id"]:
                return {
                    "ok": True,
                    "sessionId": row[0],
                    "payload": row[2],
                    "version": row[3],
                    "alreadyOwned": True,
                }
            if owner is not None:
                raise HTTPException(
                    status_code=403,
                    detail="This resume belongs to another account",
                )
            if existing and existing[0] != session_id:
                raise HTTPException(
                    status_code=409,
                    detail="This account already has a resume. Log in from the start to open it.",
                )
            cur.execute(
                "UPDATE resume_snapshots SET user_id = %s WHERE session_id = %s",
                (user["id"], session_id),
            )
            cur.execute(
                """
                SELECT session_id, payload, version
                FROM resume_snapshots WHERE session_id = %s
                """,
                (session_id,),
            )
            saved = cur.fetchone()
        conn.commit()

    return {
        "ok": True,
        "sessionId": saved[0],
        "payload": saved[1],
        "version": saved[2],
    }
