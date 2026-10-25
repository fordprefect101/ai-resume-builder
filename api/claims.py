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


def point_id(
    section: str,
    item_id: str,
    content: str,
    occurrence: int = 0,
    project_id: str | None = None,
) -> str:
    """
    Stable id for a point, so re-normalizing yields the same record. The project is
    part of the fingerprint only when set, so job-level points keep the ids they
    had before projects existed.
    """
    key = f"{section}|{item_id}|{occurrence}|{content}"
    if project_id:
        key += f"|project:{project_id}"
    return f"pt_{hashlib.sha1(key.encode()).hexdigest()[:10]}"


def with_point_defaults(point: dict) -> dict:
    """Fill v5 labels on an older point; values already set are kept."""
    defaults = {"status": "unchecked", "issues": [], "origin": "legacy", "projectId": None}
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
    project_id: str | None = None,
) -> dict:
    """
    A point is a claim tied to one inventory item (a resume bullet). `project_id`
    is empty for a job-level point, or names a project inside that job.
    """
    if status not in POINT_STATUSES:
        raise ValueError(f"unknown point status: {status}")
    if origin not in POINT_ORIGINS:
        raise ValueError(f"unknown point origin: {origin}")
    return {
        "id": point_id(section, item_id, content, occurrence, project_id),
        "content": content,
        "supportedBy": [],
        "section": section,
        "itemId": item_id,
        "projectId": project_id or None,
        "order": order,
        "status": status,
        "issues": [],
        "origin": origin,
    }


def is_point(claim: dict) -> bool:
    return bool(claim.get("itemId"))


def section_has_points(section: str) -> bool:
    return bool(get_section_profile(section).get("polishBullets"))


def section_holds_projects(section: str) -> bool:
    return bool(get_section_profile(section).get("holdsProjects"))


def points_for_item(
    payload: dict, section: str, item_id: str, project_id: str | None = None
) -> list[dict]:
    """Points at one level: the job's own (project_id empty) or one project's."""
    points = [
        c
        for c in (payload.get("claims") or [])
        if c.get("section") == section
        and c.get("itemId") == item_id
        and (c.get("projectId") or None) == (project_id or None)
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
    project_id: str | None = None,
) -> list[dict]:
    """
    Points for one level of one item in the order of `texts`. A point whose text is
    unchanged keeps its id and labels; new text gets a new point.
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
                    project_id=project_id,
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
            key = (claim.get("section"), claim.get("itemId"), claim.get("projectId") or None)
            grouped.setdefault(key, []).append(claim)

    def texts_for(section: str, item_id: str, project_id: str | None) -> list:
        points = sorted(
            grouped.get((section, item_id, project_id), []),
            key=lambda c: c.get("order", 0),
        )
        return [p.get("content") for p in points]

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
                item = {**item, "bullets": texts_for(section, item["id"], None)}
                if section_holds_projects(section) and isinstance(item.get("projects"), list):
                    item["projects"] = [
                        {**project, "bullets": texts_for(section, item["id"], project.get("id"))}
                        if isinstance(project, dict) and project.get("id")
                        else project
                        for project in item["projects"]
                    ]
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
    project_id: str | None = None,
) -> dict:
    """
    The one way to change points: the job's own (project_id empty) or one project's.
    Also refreshes the bullets copies of that item.
    """
    if not section_has_points(section):
        raise ValueError(f"section does not carry points: {section}")
    if project_id:
        item = next(
            (
                i
                for i in ((payload.get("inventory") or {}).get("sections") or {})
                .get(section, {})
                .get("items", [])
                if isinstance(i, dict) and i.get("id") == item_id
            ),
            None,
        )
        known = {
            pr.get("id")
            for pr in (item or {}).get("projects") or []
            if isinstance(pr, dict)
        }
        if item is None or project_id not in known:
            raise KeyError(f"project not found in {section}/{item_id}: {project_id}")
    mine: list[dict] = []
    others: list[dict] = []
    for claim in payload.get("claims") or []:
        if (
            claim.get("section") == section
            and claim.get("itemId") == item_id
            and (claim.get("projectId") or None) == (project_id or None)
        ):
            mine.append(claim)
        else:
            others.append(claim)
    points = reconcile_points(
        mine, section, item_id, texts, origin=origin, project_id=project_id
    )
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
