import json
import os
import urllib.error
import urllib.request

from dotenv import load_dotenv

from chat_tools import TOOL_DEFINITIONS

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
REALTIME_MODEL = os.getenv("OPENAI_REALTIME_MODEL", "gpt-realtime-2.1-mini")


def create_realtime_client_secret(catalog: dict) -> dict:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set")

    body = {
        "expires_after": {"anchor": "created_at", "seconds": 600},
        "session": {
            "type": "realtime",
            "model": REALTIME_MODEL,
            "instructions": (
                "You are in EDIT mode for an existing resume. "
                "Start by greeting briefly and asking what the user wants to "
                "edit, modify, or change today. Wait for their answer. "
                "Catalog below is reference data only. Use exact section keys and ids. "
                f"SECTION CATALOG: {json.dumps(catalog)}. "
                "Tools: exclude_from_resume, include_on_resume, add_item, reorder_sections. "
                "If adding an item, interview one field at a time for that section "
                "(experience: company, title, location, dates, bullets; "
                "projects: name, description, technologies, bullets; "
                "education: institution, degree, location, dates; "
                "achievements: title, date, description). "
                "When they say they are done, call add_item once with section + fields. "
                "Do not invent facts. "
                "If reordering sections, call reorder_sections with the full sectionOrder. "
                "Prefer soft exclude over deletion. Always use tools for mutations."
            ),
            "tools": TOOL_DEFINITIONS,
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
