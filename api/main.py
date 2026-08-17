import json
import os
import uuid
from typing import Any
import psycopg

# Local imports
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Local functions
from resume_ops import (
    exclude_project_from_resume,
    include_project_on_resume,
    add_project,
    apply_project_enrichment,
    exclude_experience_from_resume,
    include_experience_on_resume,
    add_experience,
    apply_experience_enrichment,
)
from enrichment import (
    enrich_project, polish_project_bullets,
    enrich_experience, polish_experience_bullets,
    )
from chat import run_chat
from undo import push_undo, pop_undo
from pdf_import import import_pdf_bytes, PdfImportError
from realtime import create_realtime_client_secret
from chat_tools import project_catalog

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
    enrich: bool = True

class ChatBody(BaseModel):
    sessionId: str
    message: str

class ExcludeExperienceBody(BaseModel):
    experienceId: str


class AddExperienceBody(BaseModel):
    company: str
    title: str
    location: str = ""
    startDate: str = ""
    endDate: str = ""
    bullets: list[str] = []
    experienceId: str | None = None
    enrich: bool = True

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

            push_undo(cur, session_id, row[0])

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

            push_undo(cur, session_id, row[0])

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
                if body.enrich:
                    project = next(
                        p for p in new_payload["inventory"]["projects"]
                        if p["id"] == new_id
                    )
                    enrichment = enrich_project(project)
                    polished = polish_project_bullets(project)
                    enrichment = {**enrichment, **polished}
                    new_payload = apply_project_enrichment(
                        new_payload, new_id, enrichment
                    )
            except ValueError as err:
                raise HTTPException(status_code=400, detail=str(err))

            push_undo(cur, session_id, row[0])

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

@app.post("/resume/{session_id}/tools/exclude_experience")
def tool_exclude_experience(session_id: str, body: ExcludeExperienceBody):
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
                new_payload = exclude_experience_from_resume(
                    row[0], body.experienceId
                )
            except KeyError:
                raise HTTPException(status_code=404, detail="experience_not_found")

            push_undo(cur, session_id, row[0])

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
        "appliedTool": "exclude_experience_from_resume",
        "experienceId": body.experienceId,
    }


@app.post("/resume/{session_id}/tools/include_experience")
def tool_include_experience(session_id: str, body: ExcludeExperienceBody):
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
                new_payload = include_experience_on_resume(
                    row[0], body.experienceId
                )
            except KeyError:
                raise HTTPException(status_code=404, detail="experience_not_found")

            push_undo(cur, session_id, row[0])

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
        "appliedTool": "include_experience_on_resume",
        "experienceId": body.experienceId,
    }


@app.post("/resume/{session_id}/tools/add_experience")
def tool_add_experience(session_id: str, body: AddExperienceBody):
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
                new_payload, new_id = add_experience(
                    row[0],
                    company=body.company,
                    title=body.title,
                    location=body.location,
                    start_date=body.startDate,
                    end_date=body.endDate,
                    bullets=body.bullets,
                    experience_id=body.experienceId,
                )
                if body.enrich:
                    item = next(
                        e
                        for e in new_payload["inventory"]["experience"]
                        if e["id"] == new_id
                    )
                    enrichment = enrich_experience(item)
                    polished = polish_experience_bullets(item)
                    enrichment = {**enrichment, **polished}
                    new_payload = apply_experience_enrichment(
                        new_payload, new_id, enrichment
                    )
            except ValueError as err:
                raise HTTPException(status_code=400, detail=str(err))

            push_undo(cur, session_id, row[0])

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
        "appliedTool": "add_experience",
        "experienceId": new_id,
    }
@app.post("/chat")
def chat(body: ChatBody):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            try:
                result = run_chat(row[0], body.message)
            except Exception as err:
                raise HTTPException(status_code=500, detail=str(err))
            if result["toolsCalled"]:
                push_undo(cur, body.sessionId, row[0])

            cur.execute(
                """
                SELECT payload
                FROM resume_snapshots
                WHERE session_id = %s
                """,
                (body.sessionId,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="not_found")

            try:
                result = run_chat(row[0], body.message)
            except Exception as err:
                raise HTTPException(status_code=500, detail=str(err))

            cur.execute(
                """
                UPDATE resume_snapshots
                SET payload = %s::jsonb,
                    version = version + 1,
                    updated_at = now()
                WHERE session_id = %s
                RETURNING session_id, payload, version
                """,
                (json.dumps(result["payload"]), body.sessionId),
            )
            saved = cur.fetchone()
        conn.commit()

    return {
        "sessionId": saved[0],
        "payload": saved[1],
        "version": saved[2],
        "assistantMessage": result["assistantMessage"],
        "toolsCalled": result["toolsCalled"],
    }

@app.post("/resume/{session_id}/tools/undo")
def tool_undo(session_id: str):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            previous = pop_undo(cur, session_id)
            if previous is None:
                raise HTTPException(status_code=404, detail="nothing_to_undo")

            cur.execute(
                """
                UPDATE resume_snapshots
                SET payload = %s::jsonb,
                    version = version + 1,
                    updated_at = now()
                WHERE session_id = %s
                RETURNING session_id, payload, version
                """,
                (json.dumps(previous), session_id),
            )
            saved = cur.fetchone()
            if not saved:
                raise HTTPException(status_code=404, detail="not_found")
        conn.commit()

    return {
        "sessionId": saved[0],
        "payload": saved[1],
        "version": saved[2],
        "appliedTool": "undo",
    }

@app.post("/import-resume-pdf")
async def import_resume_pdf(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="pdf_required")

    file_bytes = await file.read()

    try:
        payload = import_pdf_bytes(file_bytes)
    except PdfImportError as err:
        raise HTTPException(status_code=err.status_code, detail=err.detail)

    session_id = f"import_{uuid.uuid4().hex[:12]}"

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO resume_snapshots (session_id, payload)
                VALUES (%s, %s::jsonb)
                RETURNING session_id, payload, version
                """,
                (session_id, json.dumps(payload)),
            )
            saved = cur.fetchone()
        conn.commit()

    return {
        "sessionId": saved[0],
        "payload": saved[1],
        "version": saved[2],
        "extractionMethod": "pdf_upload",
    }

@app.get("/realtime/token")
def realtime_token(sessionId: str):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT payload FROM resume_snapshots WHERE session_id = %s",
                (sessionId,),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="not_found")

    try:
        data = create_realtime_client_secret(project_catalog(row[0]))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))

    return {
        "value": data.get("value"),
        "expiresAt": data.get("expires_at"),
        "model": data.get("session", {}).get("model")
        if isinstance(data.get("session"), dict)
        else None,
    }