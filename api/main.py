import json
import os
import uuid
from typing import Any

import psycopg
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from chat import run_chat
from enrichment import enrich_section_item
from payload_normalize import normalize_payload
from pdf_import import PdfImportError, import_pdf_bytes
from realtime import create_realtime_client_secret
from resume_ops import (
    add_item,
    apply_item_enrichment,
    complete_intake,
    exclude_from_resume,
    get_item,
    include_on_resume,
    intake_context,
    reorder_sections,
    set_basics,
    set_skills,
    validate_intake_item_fields,
)
from undo import pop_undo, push_undo

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


class ChatBody(BaseModel):
    sessionId: str
    message: str


class ReorderSectionsBody(BaseModel):
    sectionOrder: list[str]


class SectionItemBody(BaseModel):
    section: str
    itemId: str


class AddItemBody(BaseModel):
    section: str
    fields: dict
    itemId: str | None = None
    enrich: bool = True
    confirmedEmptyFields: list[str] = []


class SetBasicsBody(BaseModel):
    basics: dict
    githubUsername: str = ""
    confirmedEmptyFields: list[str] = []


class SetSkillsBody(BaseModel):
    skills: list[str]
    confirmedEmpty: bool = False


class CompleteIntakeBody(BaseModel):
    confirmedSkippedSections: list[str] = []


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/intake/start")
def start_intake():
    payload = normalize_payload({})
    payload["intake"] = {
        "status": "in_progress",
        "basicsConfirmed": False,
        "skillsConfirmed": False,
        "confirmedSkippedSections": [],
    }
    session_id = f"intake_{uuid.uuid4().hex[:12]}"

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
        "mode": "intake",
    }


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
        "payload": normalize_payload(row[1]),
        "version": row[2],
    }


@app.put("/resume/{session_id}")
def put_resume(session_id: str, body: PutResumeBody):
    payload = normalize_payload(body.payload)
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
                (session_id, json.dumps(payload)),
            )
            row = cur.fetchone()
        conn.commit()

    return {
        "sessionId": row[0],
        "payload": row[1],
        "version": row[2],
    }


@app.post("/resume/{session_id}/tools/set_basics")
def tool_set_basics(session_id: str, body: SetBasicsBody):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT payload FROM resume_snapshots WHERE session_id = %s",
                (session_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="not_found")

            previous = normalize_payload(row[0])
            try:
                new_payload = set_basics(
                    previous,
                    body.basics,
                    github_username=body.githubUsername,
                    confirmed_empty_fields=body.confirmedEmptyFields,
                )
            except ValueError as err:
                raise HTTPException(status_code=400, detail=str(err)) from err

            push_undo(cur, session_id, previous)
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
        "appliedTool": "set_basics",
        "intakeContext": intake_context(saved[1]),
    }


@app.post("/resume/{session_id}/tools/set_skills")
def tool_set_skills(session_id: str, body: SetSkillsBody):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT payload FROM resume_snapshots WHERE session_id = %s",
                (session_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="not_found")

            previous = normalize_payload(row[0])
            try:
                new_payload = set_skills(
                    previous,
                    body.skills,
                    confirmed_empty=body.confirmedEmpty,
                )
            except ValueError as err:
                raise HTTPException(status_code=400, detail=str(err)) from err

            push_undo(cur, session_id, previous)
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
        "appliedTool": "set_skills",
        "intakeContext": intake_context(saved[1]),
    }


@app.post("/resume/{session_id}/tools/complete_intake")
def tool_complete_intake(session_id: str, body: CompleteIntakeBody):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT payload FROM resume_snapshots WHERE session_id = %s",
                (session_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="not_found")

            previous = normalize_payload(row[0])
            try:
                new_payload = complete_intake(
                    previous, body.confirmedSkippedSections
                )
            except ValueError as err:
                raise HTTPException(status_code=400, detail=str(err)) from err

            push_undo(cur, session_id, previous)
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
        "appliedTool": "complete_intake",
        "mode": "edit",
        "intakeContext": intake_context(saved[1]),
    }


@app.post("/resume/{session_id}/tools/exclude_from_resume")
def tool_exclude_from_resume(session_id: str, body: SectionItemBody):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT payload FROM resume_snapshots WHERE session_id = %s",
                (session_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="not_found")

            previous = normalize_payload(row[0])
            try:
                new_payload = exclude_from_resume(
                    previous, body.section, body.itemId
                )
            except KeyError as err:
                raise HTTPException(status_code=404, detail=str(err)) from err
            except ValueError as err:
                raise HTTPException(status_code=400, detail=str(err)) from err

            push_undo(cur, session_id, previous)
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
        "appliedTool": "exclude_from_resume",
        "section": body.section,
        "itemId": body.itemId,
    }


@app.post("/resume/{session_id}/tools/include_on_resume")
def tool_include_on_resume(session_id: str, body: SectionItemBody):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT payload FROM resume_snapshots WHERE session_id = %s",
                (session_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="not_found")

            previous = normalize_payload(row[0])
            try:
                new_payload = include_on_resume(
                    previous, body.section, body.itemId
                )
            except KeyError as err:
                raise HTTPException(status_code=404, detail=str(err)) from err
            except ValueError as err:
                raise HTTPException(status_code=400, detail=str(err)) from err

            push_undo(cur, session_id, previous)
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
        "appliedTool": "include_on_resume",
        "section": body.section,
        "itemId": body.itemId,
    }


@app.post("/resume/{session_id}/tools/add_item")
def tool_add_item(session_id: str, body: AddItemBody):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT payload FROM resume_snapshots WHERE session_id = %s",
                (session_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="not_found")

            previous = normalize_payload(row[0])
            try:
                validate_intake_item_fields(
                    previous,
                    body.section,
                    body.fields,
                    body.confirmedEmptyFields,
                )
                new_payload, new_id = add_item(
                    previous,
                    body.section,
                    body.fields,
                    item_id=body.itemId,
                )
                if body.enrich:
                    item = get_item(new_payload, body.section, new_id)
                    enrichment = enrich_section_item(body.section, item)
                    if enrichment:
                        new_payload = apply_item_enrichment(
                            new_payload, body.section, new_id, enrichment
                        )
            except KeyError as err:
                raise HTTPException(status_code=404, detail=str(err)) from err
            except ValueError as err:
                raise HTTPException(status_code=400, detail=str(err)) from err

            push_undo(cur, session_id, previous)
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
        "appliedTool": "add_item",
        "section": body.section,
        "itemId": new_id,
        "intakeContext": intake_context(saved[1]),
    }


@app.post("/resume/{session_id}/tools/reorder_sections")
def tool_reorder_sections(session_id: str, body: ReorderSectionsBody):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT payload FROM resume_snapshots WHERE session_id = %s",
                (session_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="not_found")

            previous = normalize_payload(row[0])
            try:
                new_payload = reorder_sections(previous, body.sectionOrder)
            except KeyError as err:
                raise HTTPException(status_code=400, detail=str(err)) from err
            except ValueError as err:
                raise HTTPException(status_code=400, detail=str(err)) from err

            push_undo(cur, session_id, previous)
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
        "appliedTool": "reorder_sections",
        "sectionOrder": new_payload["resume"]["sectionOrder"],
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


@app.post("/chat")
def chat(body: ChatBody):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT payload FROM resume_snapshots WHERE session_id = %s",
                (body.sessionId,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="not_found")

            previous_payload = normalize_payload(row[0])

            try:
                result = run_chat(previous_payload, body.message)
            except Exception as err:
                raise HTTPException(status_code=500, detail=str(err)) from err

            if result["toolsCalled"]:
                push_undo(cur, body.sessionId, previous_payload)

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


@app.post("/import-resume-pdf")
async def import_resume_pdf(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="pdf_required")

    file_bytes = await file.read()

    try:
        payload = normalize_payload(import_pdf_bytes(file_bytes))
    except PdfImportError as err:
        raise HTTPException(status_code=err.status_code, detail=err.detail) from err
    payload["intake"] = {
        "status": "complete",
        "basicsConfirmed": True,
        "skillsConfirmed": True,
        "confirmedSkippedSections": [],
        "source": "pdf",
    }

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

    payload = normalize_payload(row[0])
    try:
        data = create_realtime_client_secret(payload)
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err)) from err

    return {
        "value": data.get("value"),
        "expiresAt": data.get("expires_at"),
        "mode": "intake"
        if (payload.get("intake") or {}).get("status") == "in_progress"
        else "edit",
        "model": data.get("session", {}).get("model")
        if isinstance(data.get("session"), dict)
        else None,
    }
