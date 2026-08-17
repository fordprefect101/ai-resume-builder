import json
import os
from openai import OpenAI
from dotenv import load_dotenv

from chat_tools import execute_tool, section_catalog, tools_for_payload
from resume_ops import intake_context, is_intake_in_progress

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_CHAT_MODEL", os.getenv("OPENAI_ENRICH_MODEL", "gpt-4.1-mini"))

SYSTEM_PROMPT = """You are a resume editing assistant.
The application owns resume truth. You only change state by calling tools.
Prefer soft exclude over deleting.
Use section + itemId from the catalog when possible.
If the user names a job, project, school, or achievement, match it to an id.
To reorder sections, call reorder_sections with the full sectionOrder.
After tools run, briefly confirm what changed in plain language.
"""

INTAKE_PROMPT = """You are conducting a structured resume intake.
The application owns resume truth. Only mutate state through the listed tools.
Use the persisted INTAKE CONTEXT together with what the user says now.
Ask exactly one question at a time. Never silently leave a field blank: ask the
user to explicitly confirm each blank, then list it in confirmedEmptyFields.
Collect basics first. Adapt skills questions to the user's background. If they
have worked in technology, ask for their GitHub username (never password/token).
Then address experience, projects, education, and achievements. For every item,
keep collecting its fields until the user confirms it is complete; call add_item
once with all fields and confirmed blanks. If a whole section is skipped, confirm
that explicitly. Call complete_intake only after basics, skills, and all sections
have been addressed. Do not invent facts.
"""


def _chat_tools(payload: dict) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"],
            },
        }
        for tool in tools_for_payload(payload)
    ]


def run_chat(payload: dict, message: str) -> dict:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set")

    catalog = section_catalog(payload)
    intake_mode = is_intake_in_progress(payload)
    context = intake_context(payload)
    messages = [
        {"role": "system", "content": INTAKE_PROMPT if intake_mode else SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Current section catalog (JSON):\n"
                f"{json.dumps(catalog)}\n\n"
                "Current intake context (JSON):\n"
                f"{json.dumps(context)}\n\n"
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
            tools=_chat_tools(current),
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