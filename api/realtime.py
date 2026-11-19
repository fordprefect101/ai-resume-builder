import json
import os
import urllib.error
import urllib.request

from dotenv import load_dotenv

from byok import api_key, redact
from chat_tools import voice_tools_for_payload
from context_selector import resume_context_summary
from story_chunks import open_follow_ups
from resume_ops import intake_context, is_intake_in_progress

load_dotenv()

REALTIME_MODEL = os.getenv("OPENAI_REALTIME_MODEL", "gpt-realtime-2.1-mini")


END_CALL_RULE = (
    "ENDING THE CALL: when intake is complete (right after complete_intake), when the "
    "person says they are done, or when an edit request is finished and they have "
    "nothing more, say a short goodbye and then call end_voice_session. Never call "
    "end_voice_session in the same turn as another tool; wait for that tool's result first."
)

FOLLOWUP_RULE = (
    "FOLLOW-UP QUESTIONS: OPEN FOLLOW-UPS lists questions the writing team needs answered "
    "to write stronger points. Ask them one at a time, in plain words, at most 2 per entry, "
    "and only once the current topic is finished. After the person answers, call "
    "answer_followup with that question's ids; if they say they don't know or want to skip, "
    "call it with skipped true and move on without pushing. Never answer for them."
)


def followup_instructions(payload: dict) -> str:
    """Instruction text naming the open questions; empty when there are none."""
    open_ones = open_follow_ups(payload)
    if not open_ones:
        return ""
    return f"OPEN FOLLOW-UPS: {json.dumps(open_ones)}. {FOLLOWUP_RULE} "


def create_realtime_client_secret(payload: dict) -> dict:
    key = api_key()
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    intake_mode = is_intake_in_progress(payload)
    summary = resume_context_summary(payload)
    context = intake_context(payload)
    if intake_mode:
        instructions = (
            "You are in INTAKE mode, building a first resume through conversation. "
            "Use the persisted INTAKE CONTEXT together with every new user answer. "
            f"INTAKE CONTEXT: {json.dumps(context)}. "
            f"RESUME SUMMARY: {json.dumps(summary)}. "
            "Ask exactly one question at a time. Do not collect or change personal "
            "basics (name, email, phone, location, LinkedIn, GitHub); those are already "
            "confirmed in the app. Start with skills. "
            "Infer the user's background from their answers and ask relevant skills. "
            "Never ask for a password, token, or other credential. "
            "After skills, address experience, projects, education, and "
            "achievements. For each item, gather every intake field one at a time. "
            "Keep gathering bullets until the user says they are done. Confirm every "
            "blank optional field before calling add_item, and call add_item once per item. "
            "When the user describes a distinct piece of work done inside a job, save it "
            "with add_project using that job's itemId (from add_item's result); work done "
            "on their own belongs in the projects section with add_item. "
            "If the user has nothing for an entire section, explicitly confirm the skip. "
            "Call complete_intake only after skills and all four sections were "
            "addressed; pass every confirmed skipped section. Do not invent facts. "
            "Tool outputs contain refreshed persisted intake context; treat them as truth. "
            + followup_instructions(payload)
            + END_CALL_RULE
        )
    else:
        instructions = (
            "You are in EDIT mode for an existing resume. "
            "Start by greeting briefly and asking what the user wants to edit today. "
            f"RESUME SUMMARY: {json.dumps(summary)}. "
            "The summary intentionally omits item details. When the user refers to an "
            "existing item, call search_resume_context using their phrase before any "
            "mutation. Use exact section keys and ids from that result. If candidates "
            "are ambiguous, ask which one they mean instead of guessing. "
            "Use tools for all resume mutations except personal details. "
            "Never edit name, email, phone, location, LinkedIn, or GitHub. "
            "When adding an item, interview one field at a time and do not invent facts. "
            "If reordering sections, call reorder_sections with the full sectionOrder. "
            "If reordering items inside a section, call reorder_items with that "
            "section and the full itemIds list. "
            "Projects done inside a job are changed with add_project, rename_project, "
            "archive_project and reorder_projects, using the job's itemId and the "
            "projectId that search_resume_context returns. reorder_projects needs every "
            "active projectId of that job. Archiving keeps a project's points. "
            "Prefer soft exclude over deletion. "
            + followup_instructions(payload)
            + END_CALL_RULE
        )

    body = {
        "expires_after": {"anchor": "created_at", "seconds": 600},
        "session": {
            "type": "realtime",
            "model": REALTIME_MODEL,
            "instructions": instructions,
            "tools": voice_tools_for_payload(payload),
            "audio": {
                "input": {
                    "transcription": {
                        "model": "gpt-4o-mini-transcribe",
                    },
                },
            },
            "tool_choice": "auto",
        },
    }

    req = urllib.request.Request(
        "https://api.openai.com/v1/realtime/client_secrets",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as res:
            return json.loads(res.read().decode())
    except urllib.error.HTTPError as err:
        detail = err.read().decode()
        raise RuntimeError(
            redact(f"openai_client_secret_failed: {err.code} {detail}")
        ) from err
