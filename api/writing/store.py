"""Putting the writing team's result onto a stored entry.

Pure functions over the resume record: they return new data and save nothing. The save
itself goes through the single save door in api/main.py.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from claims import section_has_points, set_item_points
from facts import replace_ai_facts
from writing import rules


def find_level(
    payload: dict, section: str, item_id: str, project_id: str | None = None
) -> tuple[dict, dict]:
    """(item, level): the entry, and the part that holds the story (the entry itself, or
    one of its projects). Raises KeyError when either is missing."""
    bag = ((payload.get("inventory") or {}).get("sections") or {}).get(section)
    if not isinstance(bag, dict):
        raise KeyError(f"section not found: {section}")
    if not section_has_points(section):
        raise ValueError(f"section does not carry points: {section}")
    item = next(
        (i for i in bag.get("items") or [] if isinstance(i, dict) and i.get("id") == item_id),
        None,
    )
    if item is None:
        raise KeyError(f"item not found in {section}: {item_id}")
    if not project_id:
        return item, item
    project = next(
        (p for p in item.get("projects") or [] if isinstance(p, dict) and p.get("id") == project_id),
        None,
    )
    if project is None:
        raise KeyError(f"project not found in {section}/{item_id}: {project_id}")
    return item, project


def level_story(level: dict) -> list[dict]:
    return [c for c in level.get("story") or [] if isinstance(c, dict)]


def story_fingerprint(story: list[dict]) -> str:
    """A short code for the exact words of a story, so an unchanged story is not re-run."""
    text = "\n".join(rules.normalize(c.get("text")) for c in story)
    return hashlib.sha1(text.encode()).hexdigest()[:16]


def entry_for(item: dict, level: dict, section: str) -> dict:
    """What the writing team is told about the entry: its section and its names."""
    names = {"section": section}
    for key in ("title", "company"):
        if item.get(key):
            names[key] = str(item[key])
    if level is not item and level.get("name"):
        names["name"] = str(level["name"])
    elif item.get("name"):
        names["name"] = str(item["name"])
    return names


def _points_at(payload: dict, section: str, item_id: str, project_id: str | None) -> list[dict]:
    return [
        c for c in payload.get("claims") or []
        if c.get("section") == section and c.get("itemId") == item_id
        and (c.get("projectId") or None) == (project_id or None)
    ]


def user_edited_points(payload: dict, section: str, item_id: str, project_id: str | None = None) -> list[dict]:
    """Points the person wrote or changed. A rewrite must not silently replace these."""
    return [p for p in _points_at(payload, section, item_id, project_id)
            if p.get("status") == "user_edited" or p.get("origin") == "user"]


def already_written(payload: dict, section: str, item_id: str, level: dict, project_id: str | None = None) -> bool:
    """True when the writing team already wrote this exact story's points."""
    marker = (level.get("writing") or {}).get("storyFingerprint")
    has_ai = any(p.get("origin") == "ai" for p in _points_at(payload, section, item_id, project_id))
    return bool(marker) and marker == story_fingerprint(level_story(level)) and has_ai


def _update_level(payload: dict, section: str, item_id: str, project_id: str | None, change) -> dict:
    inventory = dict(payload["inventory"])
    sections = dict(inventory["sections"])
    bag = dict(sections[section])
    items = []
    for item in bag["items"]:
        if isinstance(item, dict) and item.get("id") == item_id:
            if project_id:
                item = {**item, "projects": [
                    change(p) if isinstance(p, dict) and p.get("id") == project_id else p
                    for p in item.get("projects") or []
                ]}
            else:
                item = change(item)
        items.append(item)
    sections[section] = {**bag, "items": items}
    inventory["sections"] = sections
    return {**payload, "inventory": inventory}


def apply_result(
    payload: dict,
    section: str,
    item_id: str,
    result,
    *,
    project_id: str | None = None,
    now: datetime | None = None,
) -> dict:
    """Store a PipelineResult on the entry: its facts, its checked points, its writing
    marker. The entry's points at that level are replaced; running it twice with the same
    result gives the same record. Does nothing for a result that wrote no points."""
    _item, level = find_level(payload, section, item_id, project_id)
    if not result.ok or not result.points:
        return payload
    fingerprint = story_fingerprint(level_story(level))
    payload = replace_ai_facts(payload, section, item_id, result.facts, project_id=project_id)
    payload = set_item_points(
        payload, section, item_id,
        [p["content"] for p in result.points],
        origin="ai",
        project_id=project_id,
        details=[
            {"supportedBy": p["supportedBy"], "status": p["status"], "issues": p["issues"]}
            for p in result.points
        ],
    )
    all_supported = all(p["status"] == "supported" for p in result.points)
    stamp = (now or datetime.now(timezone.utc)).isoformat()

    def mark(target: dict) -> dict:
        writing = dict(target.get("writing") or {})
        writing.update({
            "status": "ready" if all_supported else "needs_review",
            "questions": [
                {"id": "q_" + hashlib.sha1(q.encode()).hexdigest()[:8], "text": q}
                for q in result.missing
            ],
            "storyFingerprint": fingerprint,
            "lastRunAt": stamp,
        })
        return {**target, "writing": writing}

    return _update_level(payload, section, item_id, project_id, mark)
