"""
The short result handed to the live voice assistant after each action.

Everything the assistant is sent stays in its call for the rest of the call, so this
result must stay small however large the resume is. The screen still receives the
full record; only the assistant gets this. The shape is a contract the assistant's
instructions rely on (see docs/SPEED.md).

Fields (always present unless noted):
    ok         true if the action worked
    tool       the action's name
    message    one plain sentence, at most MESSAGE_CAP characters
    section    the section touched (when there is one)
    itemId     the entry touched or created (when there is one)
    progress   {"setupComplete", "detailsConfirmed", "skills", "sections": {key: count}}
    candidates (search only) at most CANDIDATE_CAP short entries
    ambiguous  (search only) true when several candidates match about equally
    error      (failures only) what went wrong
"""

from __future__ import annotations

MESSAGE_CAP = 200
FIELD_CAP = 80
CANDIDATE_CAP = 6

LABEL_FIELDS = ("company", "title", "name", "institution", "degree")


def _cut(value, cap: int = FIELD_CAP) -> str:
    text = str(value or "").strip()
    return text if len(text) <= cap else text[: cap - 1] + "…"


def progress(payload: dict) -> dict:
    """Counts only, never lists of ids: grows with the number of sections, not entries."""
    intake = payload.get("intake") or {}
    inventory = payload.get("inventory") or {}
    sections = inventory.get("sections") or {}
    return {
        "setupComplete": intake.get("status") == "complete",
        "detailsConfirmed": bool(
            intake.get("basicsVerified") or intake.get("basicsConfirmed")
        ),
        "skills": len(inventory.get("skills") or []),
        "sections": {
            key: len((bag or {}).get("items") or []) for key, bag in sections.items()
        },
    }


def build(
    tool: str,
    payload: dict,
    *,
    message: str,
    section: str | None = None,
    item_id: str | None = None,
) -> dict:
    result: dict = {
        "ok": True,
        "tool": tool,
        "message": _cut(message, MESSAGE_CAP),
        "progress": progress(payload),
    }
    if section:
        result["section"] = _cut(section)
    if item_id:
        result["itemId"] = _cut(item_id)
    return result


def failure(tool: str, error: str) -> dict:
    return {"ok": False, "tool": tool, "error": _cut(error, MESSAGE_CAP)}


def from_search(payload: dict, context: dict) -> dict:
    """Short candidates for a search: enough to pick an entry, not the entries."""
    candidates = []
    for candidate in (context.get("candidates") or [])[:CANDIDATE_CAP]:
        short = {
            "section": _cut(candidate.get("section")),
            "itemId": _cut(candidate.get("id")),
            "onResume": bool(candidate.get("onResume")),
        }
        for field in LABEL_FIELDS:
            if candidate.get(field):
                short[field] = _cut(candidate[field])
        candidates.append(short)
    found = len(candidates)
    result = build(
        "search_resume_context",
        payload,
        message=f"Found {found} possible match{'es' if found != 1 else ''}."
        if found
        else "Nothing matched.",
    )
    result["candidates"] = candidates
    result["ambiguous"] = bool(context.get("ambiguous"))
    return result
