"""Derived resume claims with provenance links to career facts."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from facts import fact_by_id


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


def new_point(
    section: str,
    item_id: str,
    content: str,
    order: int,
    *,
    occurrence: int = 0,
) -> dict:
    """A point is a claim tied to one inventory item (a resume bullet)."""
    return {
        "id": point_id(section, item_id, content, occurrence),
        "content": content,
        "supportedBy": [],
        "section": section,
        "itemId": item_id,
        "order": order,
    }


def is_point(claim: dict) -> bool:
    return bool(claim.get("itemId"))


def points_for_item(payload: dict, section: str, item_id: str) -> list[dict]:
    points = [
        c
        for c in (payload.get("claims") or [])
        if c.get("section") == section and c.get("itemId") == item_id
    ]
    return sorted(points, key=lambda c: c.get("order", 0))


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
