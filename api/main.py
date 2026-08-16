import json
import os
from typing import Any
import psycopg

# Local imports
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Local functions
from resume_ops import exclude_project_from_resume, include_project_on_resume, add_project

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


class ExcludeProjectBody(BaseModel):
    projectId: str

class AddProjectBody(BaseModel):
    name: str
    description: str = ""
    technologies: list[str] = []
    bullets: list[str] = []
    url: str = ""
    projectId: str | None = None

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

@app.post("/resume/{session_id}/tools/exclude_project")
def tool_exclude_project(session_id: str, body: ExcludeProjectBody):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT payload
                FROM resume_snapshots
                WHERE session_id = %s
                """,
                (session_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="not_found")

            try:
                new_payload = exclude_project_from_resume(row[0], body.projectId)
            except KeyError:
                raise HTTPException(status_code=404, detail="project_not_found")

            cur.execute(
                """
                UPDATE resume_snapshots
                SET payload = %s::jsonb,
                    version = version + 1,
                    updated_at = now()
                WHERE session_id = %s
                RETURNING session_id, payload, version
                """,
                (json.dumps(new_payload), session_id),
            )
            saved = cur.fetchone()
        conn.commit()

    return {
        "sessionId": saved[0],
        "payload": saved[1],
        "version": saved[2],
        "appliedTool": "exclude_project_from_resume",
        "projectId": body.projectId,
    }

@app.post("/resume/{session_id}/tools/include_project")
def tool_include_project(session_id: str, body: ExcludeProjectBody):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT payload
                FROM resume_snapshots
                WHERE session_id = %s
                """,
                (session_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="not_found")

            try:
                new_payload = include_project_on_resume(row[0], body.projectId)
            except KeyError:
                raise HTTPException(status_code=404, detail="project_not_found")

            cur.execute(
                """
                UPDATE resume_snapshots
                SET payload = %s::jsonb,
                    version = version + 1,
                    updated_at = now()
                WHERE session_id = %s
                RETURNING session_id, payload, version
                """,
                (json.dumps(new_payload), session_id),
            )
            saved = cur.fetchone()
        conn.commit()

    return {
        "sessionId": saved[0],
        "payload": saved[1],
        "version": saved[2],
        "appliedTool": "include_project_on_resume",
        "projectId": body.projectId,
    }

@app.post("/resume/{session_id}/tools/add_project")
def tool_add_project(session_id: str, body: AddProjectBody):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT payload
                FROM resume_snapshots
                WHERE session_id = %s
                """,
                (session_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="not_found")

            try:
                new_payload, new_id = add_project(
                    row[0],
                    name=body.name,
                    description=body.description,
                    technologies=body.technologies,
                    bullets=body.bullets,
                    url=body.url,
                    project_id=body.projectId,
                )
            except ValueError as err:
                raise HTTPException(status_code=400, detail=str(err))

            cur.execute(
                """
                UPDATE resume_snapshots
                SET payload = %s::jsonb,
                    version = version + 1,
                    updated_at = now()
                WHERE session_id = %s
                RETURNING session_id, payload, version
                """,
                (json.dumps(new_payload), session_id),
            )
            saved = cur.fetchone()
        conn.commit()

    return {
        "sessionId": saved[0],
        "payload": saved[1],
        "version": saved[2],
        "appliedTool": "add_project",
        "projectId": new_id,
    }