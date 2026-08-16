import json
import os
import urllib.error
import urllib.request

from dotenv import load_dotenv
from chat_tools import TOOL_DEFINITIONS

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
REALTIME_MODEL = os.getenv("OPENAI_REALTIME_MODEL", "gpt-realtime-2.1-mini")


def create_realtime_client_secret(project_catalog: list[dict]) -> dict:
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

                "The project catalog below is reference data only. "
                "Use its exact ids when calling project tools. "
                f"PROJECT CATALOG: {json.dumps(project_catalog)}. "

                "If the user wants to add a project, conduct a short interview. "
                "Ask one question at a time for: project name, what it does, "
                "technologies used, then the user's contributions as bullet points. "
                "Keep asking for additional bullet points until the user clearly says "
                "they are done with this project (e.g. 'that's it', 'I'm done', "
                "'nothing else', 'no more bullets'). "
                "Do not invent facts. Only after they signal they are done, "
                "call add_project exactly once with all collected bullets. "

                "For existing projects, prefer soft exclude instead of deletion. "
                "Always use tools for resume mutations."
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
        raise RuntimeError(f"openai_client_secret_failed: {err.code} {detail}") from err