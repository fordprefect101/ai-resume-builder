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


MAX_FOLLOW_UPS = 2  # questions asked per entry, ever
SKIP_WORDS = ("skip", "i don't know", "i dont know", "don't know", "dont know", "no idea", "pass")


def follow_ups_left(level: dict) -> int:
    """How many more questions may still be asked about this entry (or project)."""
    asked = (level.get("writing") or {}).get("followUpsAsked")
    return max(0, MAX_FOLLOW_UPS - (asked if isinstance(asked, int) else 0))


def open_questions(level: dict) -> list[dict]:
    """The writing team's questions still waiting for an answer, within the 2-question limit."""
    questions = [
        q for q in (level.get("writing") or {}).get("questions") or []
        if isinstance(q, dict) and q.get("id") and q.get("text")
    ]
    return questions[: follow_ups_left(level)]


def is_skip(text: str) -> bool:
    """True for "skip" / "I don't know" style answers, which add nothing to the story."""
    plain = " ".join(str(text or "").lower().strip(" .!?").split())
    return not plain or plain in SKIP_WORDS


def answer_follow_up(level: dict, question_id: str, turns, source: str = "voice",
                     skipped: bool = False) -> dict:
    """The entry with one question answered (or skipped). The answer joins the story as
    `followup` chunks; a skip adds nothing. Either way the question is used up: it is
    removed and counts toward the 2-question limit. Raises KeyError for an unknown or
    already-used question, ValueError when the limit is reached."""
    if source not in ("voice", "typed"):
        raise ValueError(f"unknown answer source: {source}")
    if question_id not in {q["id"] for q in open_questions(level)}:
        if follow_ups_left(level) == 0:
            raise ValueError("No more follow-up questions are allowed for this entry.")
        raise KeyError(f"question not found: {question_id}")
    texts = _clean_turns(turns)
    if skipped or not texts or is_skip(" ".join(texts)):
        texts = []
    if texts:
        level = add_story_chunks(level, texts, "followup")
    writing = dict(level.get("writing") or {})
    writing["questions"] = [q for q in writing.get("questions") or [] if q.get("id") != question_id]
    writing["followUpsAsked"] = (writing.get("followUpsAsked") or 0) + 1
    return {**level, "writing": writing}


def with_follow_up_answer(payload: dict, section: str, item_id: str, question_id: str, turns,
                          source: str = "voice", skipped: bool = False,
                          project_id: str | None = None) -> dict:
    """The payload with one follow-up question answered on one entry (or project)."""
    inventory = dict(payload.get("inventory") or {})
    sections = dict(inventory.get("sections") or {})
    bag = dict(sections.get(section) or {})
    if not section_has_points(section) or not bag:
        raise KeyError(f"section not found: {section}")
    items, found = [], False
    for item in bag.get("items") or []:
        if isinstance(item, dict) and item.get("id") == item_id:
            if project_id:
                projects = []
                for p in item.get("projects") or []:
                    if isinstance(p, dict) and p.get("id") == project_id:
                        p, found = answer_follow_up(p, question_id, turns, source, skipped), True
                    projects.append(p)
                item = {**item, "projects": projects}
            else:
                item, found = answer_follow_up(item, question_id, turns, source, skipped), True
        items.append(item)
    if not found:
        raise KeyError(f"entry not found: {section}/{item_id}")
    sections[section] = {**bag, "items": items}
    inventory["sections"] = sections
    return {**payload, "inventory": inventory}


def open_follow_ups(payload: dict) -> list[dict]:
    """Every open question in the resume, with where it belongs, for the voice assistant."""
    out = []
    sections = (payload.get("inventory") or {}).get("sections") or {}
    for section in ("experience", "projects"):
        for item in (sections.get(section) or {}).get("items") or []:
            if not isinstance(item, dict):
                continue
            label = item.get("company") or item.get("title") or item.get("name") or ""
            levels = [(item, None, label)] + [
                (p, p.get("id"), f"{label} / {p.get('name', '')}")
                for p in item.get("projects") or [] if isinstance(p, dict)
            ]
            for level, project_id, name in levels:
                for q in open_questions(level):
                    out.append({"section": section, "itemId": item.get("id"),
                                "projectId": project_id, "entry": name,
                                "questionId": q["id"], "question": q["text"]})
    return out
