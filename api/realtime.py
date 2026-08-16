import json
import os
import urllib.error
import urllib.request

from dotenv import load_dotenv
from chat_tools import TOOL_DEFINITIONS

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
REALTIME_MODEL = os.getenv("OPENAI_REALTIME_MODEL", "gpt-realtime-2.1-mini")


def create_realtime_client_secret() -> dict:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set")

    body = {
        "expires_after": {"anchor": "created_at", "seconds": 600},
        "session": {
            "type": "realtime",
            "model": REALTIME_MODEL,
            "instructions": (
                "You help edit a resume using tools only. "
                "Prefer soft exclude over deleting. "
                "Use project ids when calling tools. "
                "When the user asks to change the resume, call a tool."
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