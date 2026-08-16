import json
import os
from openai import OpenAI
from dotenv import load_dotenv

from chat_tools import TOOL_DEFINITIONS, project_catalog, execute_tool

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_CHAT_MODEL", os.getenv("OPENAI_ENRICH_MODEL", "gpt-4.1-mini"))

# chat.completions expects tools nested under "function"
CHAT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": t["name"],
            "description": t["description"],
            "parameters": t["parameters"],
        },
    }
    for t in TOOL_DEFINITIONS
]

SYSTEM_PROMPT = """You are a resume editing assistant.
The application owns resume truth. You only change state by calling tools.
Prefer soft exclude over deleting. Use project ids from the catalog when possible.
If the user names a project, match it to an id in the catalog.
After tools run, briefly confirm what changed in plain language.
"""


def run_chat(payload: dict, message: str) -> dict:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set")

    catalog = project_catalog(payload)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Current project catalog (JSON):\n"
                f"{json.dumps(catalog)}\n\n"
                f"User request:\n{message}"
            ),
        },
    ]

    tools_called: list[dict] = []
    current = payload

    for _ in range(4):  # max tool rounds
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=CHAT_TOOLS,
            tool_choice="auto",
        )
        choice = response.choices[0].message
        messages.append(choice)

        if not choice.tool_calls:
            return {
                "assistantMessage": choice.content or "",
                "toolsCalled": tools_called,
                "payload": current,
            }

        for call in choice.tool_calls:
            name = call.function.name
            args = json.loads(call.function.arguments or "{}")
            current, summary = execute_tool(current, name, args)
            tools_called.append({"name": name, "arguments": args, "result": summary})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(summary),
                }
            )

    return {
        "assistantMessage": "Stopped after max tool rounds.",
        "toolsCalled": tools_called,
        "payload": current,
    }