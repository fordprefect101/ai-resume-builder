import json
import os
import urllib.error
import urllib.request

from dotenv import load_dotenv

from chat_tools import tools_for_payload
from resume_ops import intake_context, is_intake_in_progress, section_catalog

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
REALTIME_MODEL = os.getenv("OPENAI_REALTIME_MODEL", "gpt-realtime-2.1-mini")


def create_realtime_client_secret(payload: dict) -> dict:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set")

    intake_mode = is_intake_in_progress(payload)
    catalog = section_catalog(payload)
    context = intake_context(payload)
    if intake_mode:
        instructions = (
            "You are in INTAKE mode, building a first resume through conversation. "
            "Use the persisted INTAKE CONTEXT together with every new user answer. "
            f"INTAKE CONTEXT: {json.dumps(context)}. "
            f"SECTION CATALOG: {json.dumps(catalog)}. "
            "Ask exactly one question at a time. Start with basics: full name, email, "
            "phone, location, and links. Never silently leave any field blank: if the "
            "user skips or omits one, ask once whether they intentionally want it blank, "
            "then include that field in confirmedEmptyFields. "
            "Infer the user's background from their answers and ask relevant skills. "
            "If they have worked in technology, ask for their GitHub username only; "
            "never ask for a password, token, or other credential. "
            "After basics and skills, address experience, projects, education, and "
            "achievements. For each item, gather every intake field one at a time. "
            "Keep gathering bullets until the user says they are done. Confirm every "
            "blank optional field before calling add_item, and call add_item once per item. "
            "If the user has nothing for an entire section, explicitly confirm the skip. "
            "Call complete_intake only after basics, skills, and all four sections were "
            "addressed; pass every confirmed skipped section. Do not invent facts. "
            "Tool outputs contain refreshed persisted intake context; treat them as truth."
        )
    else:
        instructions = (
            "You are in EDIT mode for an existing resume. "
            "Start by greeting briefly and asking what the user wants to edit today. "
            f"SECTION CATALOG: {json.dumps(catalog)}. "
            "Use exact section keys and ids. Use tools for all resume mutations. "
            "When adding an item, interview one field at a time and do not invent facts. "
            "If reordering sections, call reorder_sections with the full sectionOrder. "
            "Prefer soft exclude over deletion."
        )

    body = {
        "expires_after": {"anchor": "created_at", "seconds": 600},
        "session": {
            "type": "realtime",
            "model": REALTIME_MODEL,
            "instructions": instructions,
            "tools": tools_for_payload(payload),
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
            "Authorization": f"Bearer {OPENAI_API_KEY}",
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
            f"openai_client_secret_failed: {err.code} {detail}"
        ) from err
