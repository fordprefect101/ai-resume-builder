"""Derived resume claims with provenance links to career facts."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from facts import fact_by_id


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_claim_id() -> str:
    return f"claim_{uuid.uuid4().hex[:10]}"


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
