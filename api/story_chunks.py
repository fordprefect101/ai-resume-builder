"""Keeping the person's own words as an entry's story.

Only the person's words are stored, never the assistant's. The browser sends the turns
the person spoke (or typed) while an entry was discussed; they become story chunks
`{ id, text, source, at }` on that entry (or on a project inside a job). The pipeline
refuses stories over 6000 characters, so the newest words are kept under a smaller cap.
Pure functions: they return new data and save nothing.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from claims import section_has_points

MAX_STORY_CHARS = 4000  # well under the pipeline's 6000 limit
MAX_TURN_CHARS = 1500  # one very long turn cannot crowd out the rest
SOURCES = ("voice", "typed", "followup")


def _clean_turns(turns) -> list[str]:
    out = []
    for turn in turns if isinstance(turns, list) else []:
        if isinstance(turn, str) and turn.strip():
            out.append(" ".join(turn.split())[:MAX_TURN_CHARS])
    return out


def _chunk_id(text: str, existing: int, at: str) -> str:
    digest = hashlib.sha1(f"{existing}|{at}|{text}".encode()).hexdigest()
    return f"story_{digest[:10]}"


def add_story_chunks(level: dict, turns, source: str = "voice") -> dict:
    """The entry (or project) with the person's turns added to its story.

    Old `legacy` chunks (copies of the points) are dropped once real words arrive,
    because the person's words are the better record. The newest turns are kept when
    the total would pass the cap.
    """
    if source not in SOURCES:
        raise ValueError(f"unknown story source: {source}")
    texts = _clean_turns(turns)
    if not texts:
        return level
    at = datetime.now(timezone.utc).isoformat()
    kept = [
        c
        for c in level.get("story") or []
        if isinstance(c, dict) and c.get("source") != "legacy"
    ]
    for text in texts:
        kept.append(
            {"id": _chunk_id(text, len(kept), at), "text": text, "source": source, "at": at}
        )
    # Drop the oldest chunks until the story fits; the newest words always stay.
    while len(kept) > 1 and sum(len(c.get("text", "")) for c in kept) > MAX_STORY_CHARS:
        kept.pop(0)
    return {**level, "story": kept}


def with_story(payload: dict, section: str, item_id: str, turns, source: str = "voice",
               project_id: str | None = None) -> dict:
    """The payload with the turns added to one entry's story (or one project's)."""
    if not section_has_points(section) or not _clean_turns(turns):
        return payload
    inventory = dict(payload.get("inventory") or {})
    sections = dict(inventory.get("sections") or {})
    bag = dict(sections.get(section) or {})
    items = []
    for item in bag.get("items") or []:
        if isinstance(item, dict) and item.get("id") == item_id:
            if project_id:
                item = {
                    **item,
                    "projects": [
                        add_story_chunks(p, turns, source) if isinstance(p, dict) and p.get("id") == project_id else p
                        for p in item.get("projects") or []
                    ],
                }
            else:
                item = add_story_chunks(item, turns, source)
        items.append(item)
    bag["items"] = items
    sections[section] = bag
    inventory["sections"] = sections
    return {**payload, "inventory": inventory}
