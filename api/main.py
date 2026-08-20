import json
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any

import psycopg
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

load_dotenv()

from auth import ensure_auth_schema, get_current_user, load_snapshot, user_resume_session
from auth_routes import router as auth_router
from chat import run_chat
from context_selector import select_resume_context
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
    is_basics_verified,
    require_basics_verified,
    reorder_items,
    reorder_sections,
    update_basics,
    set_skills,
    validate_intake_item_fields,
)
from undo import pop_undo, push_undo

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_auth_schema()
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(auth_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def request_validation_error(_request: Request, exc: RequestValidationError):
    missing: list[str] = []
    other: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err.get("loc", []) if part != "body")
        if err.get("type") == "missing":
            missing.append(loc or "body")
        else:
            other.append(f"{loc}: {err.get('msg')}" if loc else str(err.get("msg")))
    parts: list[str] = []
    if missing:
        label = "field" if len(missing) == 1 else "fields"
        parts.append(f"missing required {label}: {', '.join(missing)}")
    parts.extend(other)
    return JSONResponse(
        status_code=422,
        content={"detail": "; ".join(parts) or "invalid request"},
    )


class PutResumeBody(BaseModel):
    payload: Any


class ChatBody(BaseModel):
    sessionId: str
    message: str


class ReorderSectionsBody(BaseModel):
    sectionOrder: list[str]


class ReorderItemsBody(BaseModel):
    section: str
    itemIds: list[str]


class SectionItemBody(BaseModel):
    section: str
    itemId: str


class AddItemBody(BaseModel):
    section: str
    fields: dict
    itemId: str | None = None
    enrich: bool = True
    confirmedEmptyFields: list[str] = []


class UpdateBasicsBody(BaseModel):
    fullName: str
    email: str = ""
    phone: str = ""
    location: str = ""
    github: str = ""
    linkedin: str = ""
    verify: bool = True


class SetSkillsBody(BaseModel):
    skills: list[str]
    confirmedEmpty: bool = False


class CompleteIntakeBody(BaseModel):
    confirmedSkippedSections: list[str] = []


class SearchContextBody(BaseModel):
    query: str
    section: str | None = None


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/intake/start")
def start_intake(request: Request):
    user = get_current_user(request)
    payload = normalize_payload({})
    payload["intake"] = {
        "status": "in_progress",
        "basicsVerified": False,
        "basicsConfirmed": False,
        "skillsConfirmed": False,
        "confirmedSkippedSections": [],
    }

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            if user:
                existing = user_resume_session(cur, user["id"])
                if existing:
                    return {
                        "sessionId": existing[0],
                        "payload": normalize_payload(existing[1]),
                        "version": existing[2],
                        "mode": "edit"
                        if (existing[1] or {}).get("intake", {}).get("status")
                        == "complete"
                        else "intake",
                    }
            session_id = f"intake_{uuid.uuid4().hex[:12]}"
            cur.execute(
                """
                INSERT INTO resume_snapshots (session_id, payload, user_id)
                VALUES (%s, %s::jsonb, %s)
                RETURNING session_id, payload, version
                """,
                (session_id, json.dumps(payload), user["id"] if user else None),
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
def get_resume(session_id: str, request: Request):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            row = load_snapshot(cur, session_id, get_current_user(request))

    return {
        "sessionId": row[0],
        "payload": normalize_payload(row[1]),
        "version": row[2],
    }


@app.put("/resume/{session_id}")
def put_resume(session_id: str, body: PutResumeBody, request: Request):
    payload = normalize_payload(body.payload)
    user = get_current_user(request)
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT session_id, user_id FROM resume_snapshots
                WHERE session_id = %s
                """,
                (session_id,),
            )
            existing = cur.fetchone()
            if existing:
                load_snapshot(cur, session_id, user)
            elif user:
                owned = user_resume_session(cur, user["id"])
                if owned:
                    raise HTTPException(
                        status_code=409,
                        detail="This account already has a resume",
                    )
            cur.execute(
                """
                INSERT INTO resume_snapshots (session_id, payload, user_id)
                VALUES (%s, %s::jsonb, %s)
                ON CONFLICT (session_id) DO UPDATE
                  SET payload = EXCLUDED.payload,
                      version = resume_snapshots.version + 1,
                      updated_at = now()
                RETURNING session_id, payload, version
                """,
                (
                    session_id,
                    json.dumps(payload),
                    existing[1] if existing else (user["id"] if user else None),
                ),
            )
            row = cur.fetchone()
        conn.commit()

    return {
        "sessionId": row[0],
        "payload": row[1],
        "version": row[2],
    }


@app.post("/resume/{session_id}/tools/search_context")
def tool_search_context(session_id: str, body: SearchContextBody, request: Request):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            row = load_snapshot(cur, session_id, get_current_user(request))

    payload = normalize_payload(row[1])
    try:
        context = select_resume_context(
            payload, body.query, section=body.section
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err

    return {
        "sessionId": session_id,
        "version": row[2],
        "appliedTool": "search_resume_context",
        "mutated": False,
        "context": context,
    }


@app.patch("/resume/{session_id}/basics")
def update_resume_basics(session_id: str, body: UpdateBasicsBody, request: Request):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            row = load_snapshot(cur, session_id, get_current_user(request))
            previous = normalize_payload(row[1])
            try:
                new_payload = update_basics(
                    previous,
                    {
                        "fullName": body.fullName,
                        "email": body.email,
                        "phone": body.phone,
                        "location": body.location,
                    },
                    github=body.github,
                    linkedin=body.linkedin,
                    verify=body.verify,
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
        "basicsVerified": is_basics_verified(saved[1]),
    }


@app.post("/resume/{session_id}/tools/set_skills")
def tool_set_skills(session_id: str, body: SetSkillsBody, request: Request):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            row = load_snapshot(cur, session_id, get_current_user(request))
            previous = normalize_payload(row[1])
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
def tool_complete_intake(session_id: str, body: CompleteIntakeBody, request: Request):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            row = load_snapshot(cur, session_id, get_current_user(request))
            previous = normalize_payload(row[1])
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
def tool_exclude_from_resume(session_id: str, body: SectionItemBody, request: Request):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            row = load_snapshot(cur, session_id, get_current_user(request))
            previous = normalize_payload(row[1])
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
def tool_include_on_resume(session_id: str, body: SectionItemBody, request: Request):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            row = load_snapshot(cur, session_id, get_current_user(request))
            previous = normalize_payload(row[1])
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
def tool_add_item(session_id: str, body: AddItemBody, request: Request):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            row = load_snapshot(cur, session_id, get_current_user(request))
            previous = normalize_payload(row[1])
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
def tool_reorder_sections(session_id: str, body: ReorderSectionsBody, request: Request):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            row = load_snapshot(cur, session_id, get_current_user(request))
            previous = normalize_payload(row[1])
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


@app.post("/resume/{session_id}/tools/reorder_items")
def tool_reorder_items(session_id: str, body: ReorderItemsBody, request: Request):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            row = load_snapshot(cur, session_id, get_current_user(request))
            previous = normalize_payload(row[1])
            try:
                new_payload = reorder_items(previous, body.section, body.itemIds)
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
        "appliedTool": "reorder_items",
        "section": body.section,
        "itemIds": [
            item.get("id")
            for item in new_payload["inventory"]["sections"][body.section]["items"]
        ],
    }


@app.post("/resume/{session_id}/tools/undo")
def tool_undo(session_id: str, request: Request):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            load_snapshot(cur, session_id, get_current_user(request))
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
def chat(body: ChatBody, request: Request):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            row = load_snapshot(cur, body.sessionId, get_current_user(request))
            previous_payload = normalize_payload(row[1])
            version = row[2]

            try:
                require_basics_verified(previous_payload)
                result = run_chat(previous_payload, body.message)
            except ValueError as err:
                raise HTTPException(status_code=400, detail=str(err)) from err
            except Exception as err:
                raise HTTPException(status_code=500, detail=str(err)) from err

            mutated = any(
                call.get("result", {}).get("mutated", True)
                for call in result["toolsCalled"]
            )
            if mutated:
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
            else:
                saved = (body.sessionId, previous_payload, version)
        conn.commit()

    return {
        "sessionId": saved[0],
        "payload": saved[1],
        "version": saved[2],
        "assistantMessage": result["assistantMessage"],
        "toolsCalled": result["toolsCalled"],
        "contextUsed": result["contextUsed"],
    }


@app.post("/import-resume-pdf")
async def import_resume_pdf(request: Request, file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="pdf_required")

    file_bytes = await file.read()

    try:
        payload = normalize_payload(import_pdf_bytes(file_bytes))
    except PdfImportError as err:
        raise HTTPException(status_code=err.status_code, detail=err.detail) from err

    user = get_current_user(request)
    session_id = f"import_{uuid.uuid4().hex[:12]}"

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            if user:
                existing = user_resume_session(cur, user["id"])
                if existing:
                    raise HTTPException(
                        status_code=409,
                        detail="This account already has a resume. Open it from the start screen.",
                    )
            cur.execute(
                """
                INSERT INTO resume_snapshots (session_id, payload, user_id)
                VALUES (%s, %s::jsonb, %s)
                RETURNING session_id, payload, version
                """,
                (session_id, json.dumps(payload), user["id"] if user else None),
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
def realtime_token(sessionId: str, request: Request):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            row = load_snapshot(cur, sessionId, get_current_user(request))

    payload = normalize_payload(row[1])
    try:
        require_basics_verified(payload)
        data = create_realtime_client_secret(payload)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
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
