"""Career facts — atomic source-of-truth statements linked to inventory items."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


FACT_KINDS = ("context", "action", "tool", "result", "scale", "unsorted")
FACT_OWNERS = ("me", "team", "unclear")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def with_fact_defaults(fact: dict) -> dict:
    """Fill v5 labels on an older fact without guessing: only tech facts get a kind."""
    field = (fact.get("context") or {}).get("field")
    defaults = {
        "kind": "tool" if field == "technologies" else "unsorted",
        "owner": "unclear",
        "quote": None,
        "storyId": None,
    }
    return {**fact, **{k: v for k, v in defaults.items() if k not in fact}}


def ensure_facts(payload: dict) -> dict:
    if not isinstance(payload.get("facts"), list):
        payload = {**payload, "facts": []}
    if not isinstance(payload.get("claims"), list):
        payload = {**payload, "claims": []}
    if not isinstance(payload.get("variants"), dict):
        payload = {**payload, "variants": {}}
    return payload


def new_fact_id() -> str:
    return f"fact_{uuid.uuid4().hex[:10]}"


def add_fact(
    payload: dict,
    content: str,
    *,
    section: str | None = None,
    item_id: str | None = None,
    field: str | None = None,
    source: str = "user",
    kind: str = "unsorted",
    owner: str = "unclear",
    quote: str | None = None,
    story_id: str | None = None,
) -> dict:
    if kind not in FACT_KINDS:
        raise ValueError(f"unknown fact kind: {kind}")
    if owner not in FACT_OWNERS:
        raise ValueError(f"unknown fact owner: {owner}")
    payload = ensure_facts(payload)
    text = str(content or "").strip()
    if not text:
        return payload
    facts = list(payload.get("facts") or [])
    for existing in facts:
        if (
            existing.get("content") == text
            and existing.get("context", {}).get("itemId") == item_id
        ):
            return payload
    facts.append(
        {
            "id": new_fact_id(),
            "content": text,
            "context": {
                "section": section,
                "itemId": item_id,
                "field": field,
            },
            "source": source,
            "createdAt": _now(),
            "kind": kind,
            "owner": owner,
            "quote": quote,
            "storyId": story_id,
        }
    )
    return {**payload, "facts": facts}


def facts_for_item(payload: dict, section: str, item_id: str) -> list[dict]:
    return [
        f
        for f in (payload.get("facts") or [])
        if f.get("context", {}).get("section") == section
        and f.get("context", {}).get("itemId") == item_id
    ]


def sync_facts_from_item(payload: dict, section: str, item: dict) -> dict:
    """Extract facts from item bullets and technologies."""
    item_id = item.get("id")
    if not item_id:
        return payload
    for bullet in item.get("bullets") or []:
        if isinstance(bullet, str) and bullet.strip():
            payload = add_fact(
                payload,
                bullet.strip(),
                section=section,
                item_id=item_id,
                field="bullets",
                source="user",
            )
    for tech in item.get("technologies") or item.get("skills") or []:
        if isinstance(tech, str) and tech.strip():
            payload = add_fact(
                payload,
                f"Used {tech.strip()}",
                section=section,
                item_id=item_id,
                field="technologies",
                source="user",
                kind="tool",
            )
    return payload


def search_facts(payload: dict, query: str, limit: int = 12) -> list[dict]:
    """Structured keyword search over facts."""
    tokens = [
        t
        for t in query.lower().split()
        if len(t) > 2
    ]
    if not tokens:
        return list(payload.get("facts") or [])[:limit]
    scored: list[tuple[int, dict]] = []
    for fact in payload.get("facts") or []:
        hay = str(fact.get("content") or "").lower()
        score = sum(1 for t in tokens if t in hay)
        if score:
            scored.append((score, fact))
    scored.sort(key=lambda x: -x[0])
    return [f for _, f in scored[:limit]]


def fact_by_id(payload: dict, fact_id: str) -> dict | None:
    for fact in payload.get("facts") or []:
        if fact.get("id") == fact_id:
            return fact
    return None
