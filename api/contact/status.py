"""Remembers what each contact check found, and decides if the person can continue.

Results live in basics["contactChecks"], one record per field. A record is tied to a
fingerprint of the exact value it checked, so editing the field makes the record stale
and the field reads as unchecked again. All functions are pure: they return new data.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from contact import shape

FIELDS = ("email", "phone", "github", "linkedin", "portfolio")
LINK_LABELS = {"github": "GitHub", "linkedin": "LinkedIn", "portfolio": "Portfolio"}
SHAPE_CHECKS = {
    "email": shape.check_email,
    "phone": shape.check_phone,
    "github": shape.check_github,
    "linkedin": shape.check_linkedin,
    "portfolio": shape.check_web_url,
}


def fingerprint(value: str) -> str:
    """A short code for the exact text checked. Different text gives a different code."""
    return hashlib.sha256(str(value or "").strip().encode()).hexdigest()[:16]


def field_value(basics: dict, field: str) -> str:
    if field in LINK_LABELS:
        for link in basics.get("links") or []:
            if (
                isinstance(link, dict)
                and str(link.get("label") or "").strip().lower()
                == LINK_LABELS[field].lower()
            ):
                return str(link.get("url") or "").strip()
        return ""
    return str(basics.get(field) or "").strip()


def _records(basics: dict) -> dict:
    raw = basics.get("contactChecks")
    return raw if isinstance(raw, dict) else {}


def _current_record(basics: dict, field: str) -> dict | None:
    record = _records(basics).get(field)
    if not isinstance(record, dict):
        return None
    if record.get("fingerprint") != fingerprint(field_value(basics, field)):
        return None
    return record


def record_check(
    basics: dict,
    field: str,
    shape_result: dict,
    reach_result: dict | None = None,
    *,
    now: datetime | None = None,
) -> dict:
    """Return basics with this field's check stored against its current value."""
    if field not in FIELDS:
        raise ValueError(f"unknown contact field: {field}")
    reach_status = (reach_result or {}).get("status")
    message = (reach_result or {}).get("message") or shape_result.get("message") or ""
    record = {
        "fingerprint": fingerprint(field_value(basics, field)),
        "shape": shape_result.get("status"),
        "reach": reach_status,
        "message": message,
        "checkedAt": (now or datetime.now(timezone.utc)).isoformat(),
    }
    return {**basics, "contactChecks": {**_records(basics), field: record}}


def prune_stale(basics: dict) -> dict:
    """Drop records whose field was edited since the check (or that are malformed)."""
    kept = {
        field: record
        for field, record in _records(basics).items()
        if field in FIELDS and _current_record(basics, field) is not None
    }
    if kept == _records(basics):
        return basics
    return {**basics, "contactChecks": kept}


def has_lookup(basics: dict, field: str) -> bool:
    """True when the field's current value already has a settled "exists" answer."""
    record = _current_record(basics, field)
    return bool(record) and record.get("reach") in ("exists", "not_found")


def refresh_shape(basics: dict, *, now: datetime | None = None) -> dict:
    """Drop stale results, then run the instant "looks right" check on every filled-in
    field that has no current result. Results already held for unchanged fields
    (including "exists" lookups) are kept as they are."""
    out = prune_stale(basics)
    for field in FIELDS:
        value = field_value(out, field)
        if value and _current_record(out, field) is None:
            out = record_check(out, field, SHAPE_CHECKS[field](value), now=now)
    return out


def summary(basics: dict) -> dict:
    """Everything the screen needs: a badge per field and the gate."""
    return {
        "fields": {field: field_view(basics, field) for field in FIELDS},
        "gate": gate(basics),
    }


def field_view(basics: dict, field: str) -> dict:
    """What the badge should say: level is one of
    empty, unchecked, broken, looks_right, exists, warning."""
    value = field_value(basics, field)
    if not value:
        return {"level": "empty", "message": ""}
    record = _current_record(basics, field)
    if record is None:
        return {"level": "unchecked", "message": ""}
    message = record.get("message") or ""
    if record.get("shape") == "broken":
        return {"level": "broken", "message": message}
    reach = record.get("reach")
    if reach == "exists":
        return {"level": "exists", "message": message}
    if reach in ("not_found", "unavailable"):
        return {"level": "warning", "message": message}
    return {"level": "looks_right", "message": message}


def gate(basics: dict) -> dict:
    """Can the person continue? Only a plainly broken filled-in field blocks.

    Judged from the current values every time, never from stored results, so a
    stale or missing record can neither block nor unblock anyone.
    """
    blockers = []
    for field in FIELDS:
        value = field_value(basics, field)
        if not value:
            continue
        result = SHAPE_CHECKS[field](value)
        if result["status"] == "broken":
            blockers.append({"field": field, "message": result["message"]})
    return {"blocked": bool(blockers), "blockers": blockers}
