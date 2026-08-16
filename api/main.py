import json
import os
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PutResumeBody(BaseModel):
    payload: Any


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/resume/{session_id}")
def get_resume(session_id: str):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT session_id, payload, version
                FROM resume_snapshots
                WHERE session_id = %s
                """,
                (session_id,),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="not_found")

    return {
        "sessionId": row[0],
        "payload": row[1],
        "version": row[2],
    }


@app.put("/resume/{session_id}")
def put_resume(session_id: str, body: PutResumeBody):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO resume_snapshots (session_id, payload)
                VALUES (%s, %s::jsonb)
                ON CONFLICT (session_id) DO UPDATE
                  SET payload = EXCLUDED.payload,
                      version = resume_snapshots.version + 1,
                      updated_at = now()
                RETURNING session_id, payload, version
                """,
                (session_id, json.dumps(body.payload)),
            )
            row = cur.fetchone()
        conn.commit()

    return {
        "sessionId": row[0],
        "payload": row[1],
        "version": row[2],
    }