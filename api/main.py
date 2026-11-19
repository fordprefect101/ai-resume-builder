import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any, Literal

import psycopg
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

load_dotenv()

import assistant_result
from auth import ensure_auth_schema, get_current_user, load_snapshot, user_resume_session
from auth_routes import router as auth_router
from chat import run_chat
from claims import claim_provenance
from context_selector import select_resume_context
from enrichment import enrich_section_item
from facts import sync_facts_from_item
from jd_analyze import analyze_job_description, create_job_variant
from mutation_pipeline import run_mutation
from payload_normalize import normalize_payload
from story_chunks import with_story
from pdf_import import PdfImportError, import_pdf_bytes
from realtime import create_realtime_client_secret
from retrieval import retrieve_evidence
from contact import lookups as contact_lookups
from contact import project_links
from contact import status as contact_status
from traces import get_trace, log_trace
from writing import pipeline as writing_pipeline
from writing import records as writing_records
from writing import store as writing_store
from versions import (
    ensure_base_schema,
    ensure_v2_schema,
    get_version_snapshot,
    list_versions,
    record_version,
)
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
from timing import TimingMiddleware, timed
from undo import pop_undo, push_undo
import work_projects

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Order matters: auth.sql alters resume_snapshots, so the base tables come first.
    ensure_base_schema()
    ensure_auth_schema()
    ensure_v2_schema()
    yield


logger = logging.getLogger("contact")

app = FastAPI(lifespan=lifespan)
app.include_router(auth_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Added last so it wraps everything, CORS included: the time is the whole request.
app.add_middleware(TimingMiddleware)


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


class AddProjectBody(BaseModel):
    section: str = "experience"
    itemId: str
    name: str
    technologies: list[str] = []
    bullets: list[str] = []
    storyTurns: list[str] = []  # what the person said about this project, their own words
    storySource: Literal["voice", "typed"] = "voice"


class RenameProjectBody(BaseModel):
    section: str = "experience"
    itemId: str
    projectId: str
    name: str


class ProjectRefBody(BaseModel):
    section: str = "experience"
    itemId: str
    projectId: str


class ReorderProjectsBody(BaseModel):
    section: str = "experience"
    itemId: str
    projectIds: list[str]


class AddItemBody(BaseModel):
    section: str
    fields: dict
    itemId: str | None = None
    enrich: bool = True
    confirmedEmptyFields: list[str] = []
    storyTurns: list[str] = []  # what the person said about this entry, their own words
    storySource: Literal["voice", "typed"] = "voice"


class RewriteBody(BaseModel):
    section: str
    itemId: str
    projectId: str | None = None
    force: bool = False  # run again even though the story is unchanged
    replaceEdited: bool = False  # allow replacing points the person wrote or edited


class UpdateBasicsBody(BaseModel):
    fullName: str
    email: str = ""
    phone: str = ""
    location: str = ""
    github: str = ""
    linkedin: str = ""
    portfolio: str | None = None
    verify: bool = True


class SetLinkPrivateBody(BaseModel):
    itemId: str
    private: bool = True


class SetSkillsBody(BaseModel):
    skills: list[str]
    confirmedEmpty: bool = False


class CompleteIntakeBody(BaseModel):
    confirmedSkippedSections: list[str] = []


class SearchContextBody(BaseModel):
    query: str
    section: str | None = None


class MutateBody(BaseModel):
    message: str


class AnalyzeJdBody(BaseModel):
    jobDescription: str
    createVariant: bool = True
    variantName: str | None = None


class RetrieveBody(BaseModel):
    query: str
    section: str | None = None


def _save_payload(
    cur,
    session_id: str,
    previous: dict | None,
    new_payload: dict,
    *,
    operations: list,
    summary: str,
    undoable: bool = True,
) -> tuple:
    """
    The single door for changing a stored resume: normalizes the payload, keeps
    an undo copy, bumps the version, and records a history entry.
    """
    new_payload = project_links.refresh_payload(normalize_payload(new_payload))
    if undoable and previous is not None:
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
    if saved:
        record_version(cur, session_id, saved[2], new_payload, operations, summary)
    return saved


def _create_snapshot(
    cur,
    session_id: str,
    payload: dict,
    user_id: str | None,
    *,
    summary: str,
) -> tuple:
    """The single door for creating a stored resume; records its first history entry."""
    payload = normalize_payload(payload)
    cur.execute(
        """
        INSERT INTO resume_snapshots (session_id, payload, user_id)
        VALUES (%s, %s::jsonb, %s)
        RETURNING session_id, payload, version
        """,
        (session_id, json.dumps(payload), user_id),
    )
    saved = cur.fetchone()
    if saved:
        record_version(
            cur, session_id, saved[2], payload, [{"type": "CREATE"}], summary
        )
    return saved


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
            saved = _create_snapshot(
                cur,
                session_id,
                payload,
                user["id"] if user else None,
                summary="Resume created",
            )
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
                current = load_snapshot(cur, session_id, user)
                row = _save_payload(
                    cur,
                    session_id,
                    normalize_payload(current[1]),
                    payload,
                    operations=[{"type": "REPLACE"}],
                    summary="Record replaced",
                )
            else:
                if user:
                    owned = user_resume_session(cur, user["id"])
                    if owned:
                        raise HTTPException(
                            status_code=409,
                            detail="This account already has a resume",
                        )
                row = _create_snapshot(
                    cur,
                    session_id,
                    payload,
                    user["id"] if user else None,
                    summary="Resume created",
                )
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
        "assistantResult": assistant_result.from_search(payload, context),
    }


def _run_background_lookups(session_id: str, lookup, merge, tool: str, summary: str) -> None:
    """Background: run outside lookups on the saved resume, then merge the answers in.

    lookup(payload) does the slow outside calls, with no database connection open.
    merge(latest_payload, results) puts the answers into the latest saved record; it
    keeps only answers whose field still holds the text that was checked. The write
    happens under a row lock, through the single save door.
    """
    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT payload FROM resume_snapshots WHERE session_id = %s",
                    (session_id,),
                )
                row = cur.fetchone()
        if not row:
            return
        results = lookup(normalize_payload(row[0]))
        if not results:
            return

        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT session_id, payload, version FROM resume_snapshots "
                    "WHERE session_id = %s FOR UPDATE",
                    (session_id,),
                )
                row = cur.fetchone()
                if not row:
                    return
                previous = normalize_payload(row[1])
                merged = merge(previous, results)
                if merged != previous:
                    _save_payload(
                        cur,
                        session_id,
                        previous,
                        merged,
                        operations=[{"type": "TOOL", "tool": tool}],
                        summary=summary,
                        undoable=False,
                    )
            conn.commit()
    except Exception:
        # A failed background check must never break anything; "Check again" retries.
        logger.exception("%s failed for %s", tool, session_id)


def _basics_of(payload: dict) -> dict:
    return (payload.get("inventory") or {}).get("basics") or {}


def _run_contact_lookups(session_id: str, force: bool) -> None:
    def merge(latest: dict, results: dict) -> dict:
        inventory = latest.get("inventory") or {}
        merged = contact_lookups.apply_results(_basics_of(latest), results)
        return {**latest, "inventory": {**inventory, "basics": merged}}

    _run_background_lookups(
        session_id,
        lambda payload: contact_lookups.run_lookups(_basics_of(payload), force=force),
        merge,
        "check_contact",
        "Contact details checked",
    )


def _run_link_lookups(session_id: str, force: bool) -> None:
    _run_background_lookups(
        session_id,
        lambda payload: project_links.run_lookups(payload, force=force),
        project_links.apply_results,
        "check_project_links",
        "Project links checked",
    )


@app.patch("/resume/{session_id}/basics")
def update_resume_basics(
    session_id: str,
    body: UpdateBasicsBody,
    request: Request,
    background_tasks: BackgroundTasks,
):
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
                    portfolio=body.portfolio,
                    verify=body.verify,
                )
            except ValueError as err:
                raise HTTPException(status_code=400, detail=str(err)) from err

            saved = _save_payload(
                cur,
                session_id,
                previous,
                new_payload,
                operations=[{"type": "TOOL", "tool": "update_basics"}],
                summary="Contact details updated",
            )
        conn.commit()

    background_tasks.add_task(_run_contact_lookups, session_id, False)
    return {
        "sessionId": saved[0],
        "payload": saved[1],
        "version": saved[2],
        "basicsVerified": is_basics_verified(saved[1]),
        "contactStatus": contact_status.summary(
            (saved[1].get("inventory") or {}).get("basics") or {}
        ),
    }


@app.post("/resume/{session_id}/basics/check")
def recheck_contact_details(
    session_id: str, request: Request, background_tasks: BackgroundTasks
):
    """"Check again": re-run every lookup, ignoring answers already held."""
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            load_snapshot(cur, session_id, get_current_user(request))
    background_tasks.add_task(_run_contact_lookups, session_id, True)
    return {"started": True}


@app.get("/resume/{session_id}/contact-status")
def get_contact_status(session_id: str, request: Request):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            row = load_snapshot(cur, session_id, get_current_user(request))
    payload = normalize_payload(row[1])
    return {
        "sessionId": row[0],
        "version": row[2],
        "contactStatus": contact_status.summary(_basics_of(payload)),
        "projectLinks": project_links.summary(payload),
    }


@app.post("/resume/{session_id}/links/check")
def recheck_project_links(
    session_id: str, request: Request, background_tasks: BackgroundTasks
):
    """"Check again" for every project link."""
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            load_snapshot(cur, session_id, get_current_user(request))
    background_tasks.add_task(_run_link_lookups, session_id, True)
    return {"started": True}


@app.post("/resume/{session_id}/tools/set_link_private")
def tool_set_link_private(
    session_id: str, body: SetLinkPrivateBody, request: Request
):
    """Mark a project's link as private ("can't be checked"), or undo that."""
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            row = load_snapshot(cur, session_id, get_current_user(request))
            previous = normalize_payload(row[1])
            try:
                require_basics_verified(previous)
                new_payload = project_links.set_private(
                    previous, body.itemId, body.private
                )
            except KeyError as err:
                raise HTTPException(status_code=404, detail=str(err)) from err
            except ValueError as err:
                raise HTTPException(status_code=400, detail=str(err)) from err
            saved = _save_payload(
                cur,
                session_id,
                previous,
                new_payload,
                operations=[{
                    "type": "TOOL",
                    "tool": "set_link_private",
                    "section": "projects",
                    "itemId": body.itemId,
                }],
                summary="Project link marked private"
                if body.private
                else "Project link no longer marked private",
            )
        conn.commit()
    return {
        "sessionId": saved[0],
        "payload": saved[1],
        "version": saved[2],
        "projectLinks": project_links.summary(saved[1]),
    }


def _rewrite_summary(result) -> dict:
    return {
        "stage": result.stage,
        "points": [{"content": p["content"], "status": p["status"]} for p in result.points],
        "droppedPoints": result.dropped_points,
        "droppedFacts": len(result.dropped_facts),
        "questions": result.missing,
        "totals": result.totals,
    }


@app.post("/resume/{session_id}/rewrite")
def rewrite_entry(session_id: str, body: RewriteBody, request: Request):
    """Run the writing team on one entry's story and store the checked points.

    Slow (several model calls), so it is never called from the live voice path. No
    database connection is held while the models work.
    """
    user = get_current_user(request)
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            row = load_snapshot(cur, session_id, user)
            payload = normalize_payload(row[1])
            try:
                require_basics_verified(payload)
                item, level = writing_store.find_level(
                    payload, body.section, body.itemId, body.projectId
                )
            except KeyError as err:
                raise HTTPException(status_code=404, detail=str(err)) from err
            except ValueError as err:
                raise HTTPException(status_code=400, detail=str(err)) from err
            story = writing_store.level_story(level)
            fingerprint = writing_store.story_fingerprint(story)
            if (
                writing_store.user_edited_points(payload, body.section, body.itemId, body.projectId)
                and not body.replaceEdited
            ):
                raise HTTPException(
                    status_code=409,
                    detail="This entry has points you wrote or edited. "
                    "Confirm that they may be replaced.",
                )
            if not body.force and writing_store.already_written(
                payload, body.section, body.itemId, level, body.projectId
            ):
                return {"sessionId": session_id, "version": row[2], "skipped": True,
                        "reason": "The story has not changed since the points were written."}
            cur.execute(
                "SELECT count(*) FROM ai_traces WHERE session_id = %s "
                "AND request_type = 'rewrite' AND created_at > now() - interval '1 hour'",
                (session_id,),
            )
            if cur.fetchone()[0] >= writing_pipeline.MAX_REWRITES_PER_HOUR:
                raise HTTPException(
                    status_code=429,
                    detail="Too many rewrites this hour. Try again later.",
                )

    entry = writing_store.entry_for(item, level, body.section)
    result = writing_pipeline.run_pipeline(story, entry)
    if result.stage == "guard":  # refused before any model was called: nothing to record
        raise HTTPException(status_code=400, detail=result.error)

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            trace = {**result.run.as_trace(), "stage": result.stage, "error": result.error[:300],
                     "promptVersions": result.prompt_versions,
                     "droppedFacts": len(result.dropped_facts),
                     "droppedPoints": len(result.dropped_points)}
            trace_id = log_trace(
                cur, session_id, "rewrite",
                writing_records.redact(" ".join(c.get("text", "") for c in story))[:500], trace,
            )
            if not result.ok:
                conn.commit()  # the spend is recorded even though nothing is stored
                raise HTTPException(status_code=502, detail=f"The writing team failed ({result.stage}): {result.error}")
            if not result.points:
                conn.commit()
                return {"sessionId": session_id, "version": row[2], "traceId": trace_id,
                        "rewrite": _rewrite_summary(result)}

            cur.execute(
                "SELECT session_id, payload, version FROM resume_snapshots "
                "WHERE session_id = %s FOR UPDATE",
                (session_id,),
            )
            latest = cur.fetchone()
            previous = normalize_payload(latest[1])
            try:
                _item, now_level = writing_store.find_level(
                    previous, body.section, body.itemId, body.projectId
                )
            except (KeyError, ValueError) as err:
                conn.commit()
                raise HTTPException(status_code=409, detail="The entry changed while it was being written.") from err
            changed = writing_store.story_fingerprint(writing_store.level_story(now_level)) != fingerprint
            edited_meanwhile = (
                writing_store.user_edited_points(previous, body.section, body.itemId, body.projectId)
                and not body.replaceEdited
            )
            if changed or edited_meanwhile:
                conn.commit()
                raise HTTPException(
                    status_code=409,
                    detail="The entry changed while it was being written. Run it again.",
                )
            saved = _save_payload(
                cur,
                session_id,
                previous,
                writing_store.apply_result(
                    previous, body.section, body.itemId, result, project_id=body.projectId
                ),
                operations=[{
                    "type": "TOOL", "tool": "rewrite",
                    "section": body.section, "itemId": body.itemId,
                    "projectId": body.projectId,
                }],
                summary="Entry rewritten by the writing team",
            )
        conn.commit()

    return {
        "sessionId": saved[0],
        "payload": saved[1],
        "version": saved[2],
        "traceId": trace_id,
        "rewrite": _rewrite_summary(result),
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

            saved = _save_payload(
                cur,
                session_id,
                previous,
                new_payload,
                operations=[{"type": "TOOL", "tool": "set_skills"}],
                summary="Skills updated",
            )
        conn.commit()

    return {
        "sessionId": saved[0],
        "payload": saved[1],
        "version": saved[2],
        "appliedTool": "set_skills",
        "intakeContext": intake_context(saved[1]),
        "assistantResult": assistant_result.build(
            "set_skills",
            saved[1],
            message=f"Saved {len(body.skills)} skills.",
        ),
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

            saved = _save_payload(
                cur,
                session_id,
                previous,
                new_payload,
                operations=[{"type": "TOOL", "tool": "complete_intake"}],
                summary="Setup completed",
            )
        conn.commit()

    return {
        "sessionId": saved[0],
        "payload": saved[1],
        "version": saved[2],
        "appliedTool": "complete_intake",
        "mode": "edit",
        "intakeContext": intake_context(saved[1]),
        "assistantResult": assistant_result.build(
            "complete_intake", saved[1], message="Setup is complete."
        ),
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

            saved = _save_payload(
                cur,
                session_id,
                previous,
                new_payload,
                operations=[{
                        "type": "TOOL",
                        "tool": "exclude_from_resume",
                        "section": body.section,
                        "itemId": body.itemId,
                    }],
                summary=f"Hid an entry in {body.section}",
            )
        conn.commit()

    return {
        "sessionId": saved[0],
        "payload": saved[1],
        "version": saved[2],
        "appliedTool": "exclude_from_resume",
        "section": body.section,
        "itemId": body.itemId,
        "assistantResult": assistant_result.build(
            "exclude_from_resume",
            saved[1],
            message="Hid the entry from the resume.",
            section=body.section,
            item_id=body.itemId,
        ),
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

            saved = _save_payload(
                cur,
                session_id,
                previous,
                new_payload,
                operations=[{
                        "type": "TOOL",
                        "tool": "include_on_resume",
                        "section": body.section,
                        "itemId": body.itemId,
                    }],
                summary=f"Showed an entry in {body.section}",
            )
        conn.commit()

    return {
        "sessionId": saved[0],
        "payload": saved[1],
        "version": saved[2],
        "appliedTool": "include_on_resume",
        "section": body.section,
        "itemId": body.itemId,
        "assistantResult": assistant_result.build(
            "include_on_resume",
            saved[1],
            message="Showed the entry on the resume.",
            section=body.section,
            item_id=body.itemId,
        ),
    }


@app.post("/resume/{session_id}/tools/add_item")
def tool_add_item(
    session_id: str,
    body: AddItemBody,
    request: Request,
    background_tasks: BackgroundTasks,
):
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
                    with timed("tidy_up"):
                        enrichment = enrich_section_item(body.section, item)
                    if enrichment:
                        new_payload = apply_item_enrichment(
                            new_payload, body.section, new_id, enrichment
                        )
                new_payload = with_story(
                    new_payload, body.section, new_id, body.storyTurns, body.storySource
                )
                item = get_item(new_payload, body.section, new_id)
                new_payload = sync_facts_from_item(new_payload, body.section, item)
            except KeyError as err:
                raise HTTPException(status_code=404, detail=str(err)) from err
            except ValueError as err:
                raise HTTPException(status_code=400, detail=str(err)) from err

            saved = _save_payload(
                cur,
                session_id,
                previous,
                new_payload,
                operations=[{
                        "type": "TOOL",
                        "tool": "add_item",
                        "section": body.section,
                        "itemId": new_id,
                    }],
                summary=f"Added an entry to {body.section}",
            )
        conn.commit()

    if project_links.pending(saved[1]):
        background_tasks.add_task(_run_link_lookups, session_id, False)
    return {
        "sessionId": saved[0],
        "payload": saved[1],
        "version": saved[2],
        "appliedTool": "add_item",
        "section": body.section,
        "itemId": new_id,
        "intakeContext": intake_context(saved[1]),
        "assistantResult": assistant_result.build(
            "add_item",
            saved[1],
            message=f"Added an entry to {body.section}.",
            section=body.section,
            item_id=new_id,
        ),
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

            saved = _save_payload(
                cur,
                session_id,
                previous,
                new_payload,
                operations=[{"type": "TOOL", "tool": "reorder_sections"}],
                summary="Sections reordered",
            )
        conn.commit()

    return {
        "sessionId": saved[0],
        "payload": saved[1],
        "version": saved[2],
        "appliedTool": "reorder_sections",
        "sectionOrder": new_payload["resume"]["sectionOrder"],
        "assistantResult": assistant_result.build(
            "reorder_sections", saved[1], message="Reordered the sections."
        ),
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

            saved = _save_payload(
                cur,
                session_id,
                previous,
                new_payload,
                operations=[{"type": "TOOL", "tool": "reorder_items", "section": body.section}],
                summary=f"Entries reordered in {body.section}",
            )
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
        "assistantResult": assistant_result.build(
            "reorder_items",
            saved[1],
            message=f"Reordered the entries in {body.section}.",
            section=body.section,
        ),
    }


@app.post("/resume/{session_id}/tools/add_project")
def tool_add_project(session_id: str, body: AddProjectBody, request: Request):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            row = load_snapshot(cur, session_id, get_current_user(request))
            previous = normalize_payload(row[1])
            try:
                new_payload, project_id = work_projects.add_project(
                    previous,
                    body.section,
                    body.itemId,
                    body.name,
                    technologies=body.technologies,
                    bullets=body.bullets,
                )
                new_payload = with_story(
                    new_payload, body.section, body.itemId, body.storyTurns,
                    body.storySource, project_id=project_id,
                )
                job = get_item(new_payload, body.section, body.itemId)
                project = work_projects.get_project(
                    new_payload, body.section, body.itemId, project_id
                )
                new_payload = sync_facts_from_item(
                    new_payload, body.section, job, project=project
                )
            except KeyError as err:
                raise HTTPException(status_code=404, detail=str(err)) from err
            except ValueError as err:
                raise HTTPException(status_code=400, detail=str(err)) from err

            saved = _save_payload(
                cur,
                session_id,
                previous,
                new_payload,
                operations=[
                    {
                        "type": "TOOL",
                        "tool": "add_project",
                        "section": body.section,
                        "itemId": body.itemId,
                        "projectId": project_id,
                    }
                ],
                summary=f"Added a project to {body.section}",
            )
        conn.commit()

    return {
        "sessionId": saved[0],
        "payload": saved[1],
        "version": saved[2],
        "appliedTool": "add_project",
        "section": body.section,
        "itemId": body.itemId,
        "projectId": project_id,
        "assistantResult": assistant_result.build(
            "add_project",
            saved[1],
            message=f"Added the project {body.name.strip()}.",
            section=body.section,
            item_id=body.itemId,
            project_id=project_id,
        ),
    }


@app.post("/resume/{session_id}/tools/rename_project")
def tool_rename_project(session_id: str, body: RenameProjectBody, request: Request):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            row = load_snapshot(cur, session_id, get_current_user(request))
            previous = normalize_payload(row[1])
            try:
                new_payload = work_projects.rename_project(
                    previous, body.section, body.itemId, body.projectId, body.name
                )
            except KeyError as err:
                raise HTTPException(status_code=404, detail=str(err)) from err
            except ValueError as err:
                raise HTTPException(status_code=400, detail=str(err)) from err

            saved = _save_payload(
                cur,
                session_id,
                previous,
                new_payload,
                operations=[
                    {
                        "type": "TOOL",
                        "tool": "rename_project",
                        "section": body.section,
                        "itemId": body.itemId,
                        "projectId": body.projectId,
                    }
                ],
                summary="Renamed a project",
            )
        conn.commit()

    return {
        "sessionId": saved[0],
        "payload": saved[1],
        "version": saved[2],
        "appliedTool": "rename_project",
        "section": body.section,
        "itemId": body.itemId,
        "projectId": body.projectId,
        "assistantResult": assistant_result.build(
            "rename_project",
            saved[1],
            message=f"Renamed the project to {body.name.strip()}.",
            section=body.section,
            item_id=body.itemId,
            project_id=body.projectId,
        ),
    }


@app.post("/resume/{session_id}/tools/archive_project")
def tool_archive_project(session_id: str, body: ProjectRefBody, request: Request):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            row = load_snapshot(cur, session_id, get_current_user(request))
            previous = normalize_payload(row[1])
            try:
                new_payload = work_projects.archive_project(
                    previous, body.section, body.itemId, body.projectId
                )
            except KeyError as err:
                raise HTTPException(status_code=404, detail=str(err)) from err
            except ValueError as err:
                raise HTTPException(status_code=400, detail=str(err)) from err

            saved = _save_payload(
                cur,
                session_id,
                previous,
                new_payload,
                operations=[
                    {
                        "type": "TOOL",
                        "tool": "archive_project",
                        "section": body.section,
                        "itemId": body.itemId,
                        "projectId": body.projectId,
                    }
                ],
                summary="Archived a project",
            )
        conn.commit()

    return {
        "sessionId": saved[0],
        "payload": saved[1],
        "version": saved[2],
        "appliedTool": "archive_project",
        "section": body.section,
        "itemId": body.itemId,
        "projectId": body.projectId,
        "assistantResult": assistant_result.build(
            "archive_project",
            saved[1],
            message="Archived the project; its points are kept.",
            section=body.section,
            item_id=body.itemId,
            project_id=body.projectId,
        ),
    }


@app.post("/resume/{session_id}/tools/reorder_projects")
def tool_reorder_projects(session_id: str, body: ReorderProjectsBody, request: Request):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            row = load_snapshot(cur, session_id, get_current_user(request))
            previous = normalize_payload(row[1])
            try:
                new_payload = work_projects.reorder_projects(
                    previous, body.section, body.itemId, body.projectIds
                )
            except KeyError as err:
                raise HTTPException(status_code=404, detail=str(err)) from err
            except ValueError as err:
                raise HTTPException(status_code=400, detail=str(err)) from err

            saved = _save_payload(
                cur,
                session_id,
                previous,
                new_payload,
                operations=[
                    {
                        "type": "TOOL",
                        "tool": "reorder_projects",
                        "section": body.section,
                        "itemId": body.itemId,
                    }
                ],
                summary="Reordered projects",
            )
        conn.commit()

    return {
        "sessionId": saved[0],
        "payload": saved[1],
        "version": saved[2],
        "appliedTool": "reorder_projects",
        "section": body.section,
        "itemId": body.itemId,
        "assistantResult": assistant_result.build(
            "reorder_projects",
            saved[1],
            message="Reordered the projects.",
            section=body.section,
            item_id=body.itemId,
        ),
    }


@app.post("/resume/{session_id}/tools/undo")
def tool_undo(session_id: str, request: Request):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            load_snapshot(cur, session_id, get_current_user(request))
            previous = pop_undo(cur, session_id)
            if previous is None:
                raise HTTPException(status_code=404, detail="nothing_to_undo")

            saved = _save_payload(
                cur,
                session_id,
                None,
                previous,
                operations=[{"type": "UNDO"}],
                summary="Undid last change",
                undoable=False,
            )
            if not saved:
                raise HTTPException(status_code=404, detail="not_found")
        conn.commit()

    return {
        "sessionId": saved[0],
        "payload": saved[1],
        "version": saved[2],
        "appliedTool": "undo",
    }


@app.post("/resume/{session_id}/mutate")
def mutate_resume(
    session_id: str,
    body: MutateBody,
    request: Request,
    background_tasks: BackgroundTasks,
):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            row = load_snapshot(cur, session_id, get_current_user(request))
            previous = normalize_payload(row[1])
            try:
                require_basics_verified(previous)
                result, trace = run_mutation(previous, body.message)
            except ValueError as err:
                raise HTTPException(status_code=400, detail=str(err)) from err

            trace_id = log_trace(cur, session_id, "mutate", body.message, trace)

            if result.clarification and not result.applied:
                conn.commit()
                return {
                    "sessionId": session_id,
                    "version": row[2],
                    "mutated": False,
                    "clarification": result.clarification,
                    "diff": result.diff,
                    "traceId": trace_id,
                }

            if not result.applied and result.payload == previous:
                conn.commit()
                return {
                    "sessionId": session_id,
                    "version": row[2],
                    "mutated": False,
                    "message": result.clarification or "No changes applied",
                    "traceId": trace_id,
                }

            saved = _save_payload(
                cur,
                session_id,
                previous,
                result.payload,
                operations=result.applied,
                summary="; ".join(result.diff[:3]) if result.diff else "Mutation",
            )
        conn.commit()

    if project_links.pending(saved[1]):
        background_tasks.add_task(_run_link_lookups, session_id, False)
    return {
        "sessionId": saved[0],
        "payload": saved[1],
        "version": saved[2],
        "mutated": True,
        "applied": result.applied,
        "diff": result.diff,
        "clarification": result.clarification,
        "traceId": trace_id,
    }


@app.get("/resume/{session_id}/versions")
def get_versions(session_id: str, request: Request):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            load_snapshot(cur, session_id, get_current_user(request))
            versions = list_versions(cur, session_id)
    return {"sessionId": session_id, "versions": versions}


@app.post("/resume/{session_id}/versions/{version_num}/restore")
def restore_version(session_id: str, version_num: int, request: Request):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            row = load_snapshot(cur, session_id, get_current_user(request))
            previous = normalize_payload(row[1])
            snapshot = get_version_snapshot(cur, session_id, version_num)
            if snapshot is None:
                raise HTTPException(status_code=404, detail="version_not_found")
            restored = normalize_payload(snapshot)
            saved = _save_payload(
                cur,
                session_id,
                previous,
                restored,
                operations=[{"type": "RESTORE", "version": version_num}],
                summary=f"Restored version {version_num}",
            )
        conn.commit()
    return {
        "sessionId": saved[0],
        "payload": saved[1],
        "version": saved[2],
        "restoredFrom": version_num,
    }


@app.post("/resume/{session_id}/retrieve")
def retrieve_career_evidence(session_id: str, body: RetrieveBody, request: Request):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            row = load_snapshot(cur, session_id, get_current_user(request))
    payload = normalize_payload(row[1])
    evidence = retrieve_evidence(payload, body.query, section=body.section)
    return {"sessionId": session_id, **evidence}


@app.post("/resume/{session_id}/analyze-jd")
def analyze_jd(session_id: str, body: AnalyzeJdBody, request: Request):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            row = load_snapshot(cur, session_id, get_current_user(request))
            previous = normalize_payload(row[1])
            try:
                require_basics_verified(previous)
                analysis = analyze_job_description(previous, body.jobDescription)
                new_payload = previous
                variant_id = None
                if body.createVariant:
                    new_payload = create_job_variant(
                        previous,
                        body.jobDescription,
                        name=body.variantName,
                    )
                    variants = new_payload.get("variants") or {}
                    variant_id = next(
                        (vid for vid in variants if vid.startswith("variant_")),
                        None,
                    )
                trace_id = log_trace(
                    cur,
                    session_id,
                    "analyze_jd",
                    body.jobDescription[:500],
                    {"analysis": analysis, "variantId": variant_id},
                )
                if body.createVariant and new_payload != previous:
                    saved = _save_payload(
                        cur,
                        session_id,
                        previous,
                        new_payload,
                        operations=[{"type": "CREATE_VARIANT", "variantId": variant_id}],
                        summary="Job-specific variant created",
                    )
                    out_payload = saved[1]
                    out_version = saved[2]
                else:
                    out_payload = previous
                    out_version = row[2]
            except ValueError as err:
                raise HTTPException(status_code=400, detail=str(err)) from err
        conn.commit()

    return {
        "sessionId": session_id,
        "payload": out_payload,
        "version": out_version,
        "analysis": analysis,
        "variantId": variant_id,
        "traceId": trace_id,
    }


@app.get("/resume/{session_id}/claims/{claim_id}/provenance")
def get_claim_provenance(session_id: str, claim_id: str, request: Request):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            row = load_snapshot(cur, session_id, get_current_user(request))
    payload = normalize_payload(row[1])
    prov = claim_provenance(payload, claim_id)
    if prov is None:
        raise HTTPException(status_code=404, detail="claim_not_found")
    return {"sessionId": session_id, **prov}


@app.get("/traces/{trace_id}")
def read_trace(trace_id: int, request: Request):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            trace = get_trace(cur, trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="trace_not_found")
    return trace


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

            new_payload = normalize_payload(result["payload"])
            mutated = new_payload != previous_payload
            if mutated:
                applied = []
                for call in result.get("toolsCalled") or []:
                    if call.get("name") == "mutate":
                        applied = call.get("result", {}).get("applied") or []
                saved = _save_payload(
                    cur,
                    body.sessionId,
                    previous_payload,
                    new_payload,
                    operations=applied or [{"type": "CHAT"}],
                    summary="; ".join(result.get("diff") or [])[:200] or "Chat update",
                )
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
            saved = _create_snapshot(
                cur,
                session_id,
                payload,
                user["id"] if user else None,
                summary="Imported from PDF",
            )
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
