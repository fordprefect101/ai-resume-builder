"""Derived resume claims with provenance links to career facts."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from facts import fact_by_id
from section_registry import get_section_profile

POINT_STATUSES = ("unchecked", "supported", "needs_review", "user_edited")
POINT_ORIGINS = ("legacy", "ai", "user", "imported")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_claim_id() -> str:
    return f"claim_{uuid.uuid4().hex[:10]}"


def point_id(section: str, item_id: str, content: str, occurrence: int = 0) -> str:
    """Stable id for an item's point, so re-normalizing yields the same record."""
    digest = hashlib.sha1(
        f"{section}|{item_id}|{occurrence}|{content}".encode()
    ).hexdigest()
    return f"pt_{digest[:10]}"


def with_point_defaults(point: dict) -> dict:
    """Fill v5 labels on an older point; values already set are kept."""
    defaults = {"status": "unchecked", "issues": [], "origin": "legacy"}
    return {**point, **{k: v for k, v in defaults.items() if k not in point}}


def new_point(
    section: str,
    item_id: str,
    content: str,
    order: int,
    *,
    occurrence: int = 0,
    status: str = "unchecked",
    origin: str = "legacy",
) -> dict:
    """A point is a claim tied to one inventory item (a resume bullet)."""
    if status not in POINT_STATUSES:
        raise ValueError(f"unknown point status: {status}")
    if origin not in POINT_ORIGINS:
        raise ValueError(f"unknown point origin: {origin}")
    return {
        "id": point_id(section, item_id, content, occurrence),
        "content": content,
        "supportedBy": [],
        "section": section,
        "itemId": item_id,
        "order": order,
        "status": status,
        "issues": [],
        "origin": origin,
    }


def is_point(claim: dict) -> bool:
    return bool(claim.get("itemId"))


def section_has_points(section: str) -> bool:
    return bool(get_section_profile(section).get("polishBullets"))


def points_for_item(payload: dict, section: str, item_id: str) -> list[dict]:
    points = [
        c
        for c in (payload.get("claims") or [])
        if c.get("section") == section and c.get("itemId") == item_id
    ]
    return sorted(points, key=lambda c: c.get("order", 0))


def clean_point_texts(texts) -> list[str]:
    if isinstance(texts, str):
        texts = [texts]
    return [t for t in (texts or []) if isinstance(t, str) and t.strip()]


def reconcile_points(
    existing: list[dict],
    section: str,
    item_id: str,
    texts,
    *,
    origin: str = "legacy",
) -> list[dict]:
    """
    Points for one item in the order of `texts`. A point whose text is unchanged
    keeps its id and labels; new text gets a new point.
    """
    pool: dict[str, list[dict]] = {}
    for point in sorted(existing, key=lambda c: c.get("order", 0)):
        pool.setdefault(point.get("content"), []).append(point)

    points: list[dict] = []
    seen: dict[str, int] = {}
    for order, text in enumerate(clean_point_texts(texts)):
        occurrence = seen.get(text, 0)
        seen[text] = occurrence + 1
        if pool.get(text):
            points.append(with_point_defaults({**pool[text].pop(0), "order": order}))
        else:
            points.append(
                new_point(
                    section,
                    item_id,
                    text,
                    order,
                    occurrence=occurrence,
                    origin=origin,
                )
            )
    return points


def rebuild_bullets(payload: dict, only: tuple[str, str] | None = None) -> dict:
    """
    The only place item.bullets is written: a display copy of the item's points.
    `only=(section, item_id)` limits it to one item; without it every item is
    rebuilt, so the payload must already be normalized.
    """
    grouped: dict[tuple, list[dict]] = {}
    for claim in payload.get("claims") or []:
        if is_point(claim):
            key = (claim.get("section"), claim.get("itemId"))
            grouped.setdefault(key, []).append(claim)

    inventory = dict(payload.get("inventory") or {})
    sections = dict(inventory.get("sections") or {})
    for section, bag in sections.items():
        if not isinstance(bag, dict) or not section_has_points(section):
            continue
        items = []
        for item in bag.get("items") or []:
            if (
                isinstance(item, dict)
                and item.get("id")
                and (only is None or only == (section, item["id"]))
            ):
                points = sorted(
                    grouped.get((section, item["id"]), []),
                    key=lambda c: c.get("order", 0),
                )
                item = {**item, "bullets": [p.get("content") for p in points]}
            items.append(item)
        sections[section] = {**bag, "items": items}
    inventory["sections"] = sections
    return {**payload, "inventory": inventory}


def set_item_points(
    payload: dict,
    section: str,
    item_id: str,
    texts,
    *,
    origin: str = "legacy",
) -> dict:
    """The one way to change an item's points. Also refreshes its bullets copy."""
    if not section_has_points(section):
        raise ValueError(f"section does not carry points: {section}")
    mine: list[dict] = []
    others: list[dict] = []
    for claim in payload.get("claims") or []:
        if claim.get("section") == section and claim.get("itemId") == item_id:
            mine.append(claim)
        else:
            others.append(claim)
    points = reconcile_points(mine, section, item_id, texts, origin=origin)
    return rebuild_bullets(
        {**payload, "claims": others + points}, only=(section, item_id)
    )


def add_claim(
    payload: dict,
    content: str,
    supported_by: list[str],
    *,
    variant_id: str | None = None,
    status: str = "pending",
) -> dict:
    claims = list(payload.get("claims") or [])
    claims.append(
        {
            "id": new_claim_id(),
            "content": str(content or "").strip(),
            "supportedBy": list(supported_by),
            "variantId": variant_id,
            "status": status,
            "createdAt": _now(),
        }
    )
    return {**payload, "claims": claims}


def claim_provenance(payload: dict, claim_id: str) -> dict | None:
    for claim in payload.get("claims") or []:
        if claim.get("id") != claim_id:
            continue
        facts = [
            fact_by_id(payload, fid)
            for fid in (claim.get("supportedBy") or [])
        ]
        return {
            "claim": claim,
            "facts": [f for f in facts if f],
        }
    return None


def claims_for_variant(payload: dict, variant_id: str | None = None) -> list[dict]:
    return [
        c
        for c in (payload.get("claims") or [])
        if c.get("variantId") == variant_id or (variant_id is None and not c.get("variantId"))
    ]
