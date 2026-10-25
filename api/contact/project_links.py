"""Checks for the link on each independent project (the `url` field).

The result is kept on the project entry as `linkCheck`, tied to a fingerprint of the
link it checked, like the personal-details checks in status.py. It is information for
the person only: it never touches an entry's points, facts or their statuses, and it is
not printed on the resume. All functions are pure and return new data.
"""

from __future__ import annotations

from datetime import datetime, timezone

from contact import github, reach, shape
from contact.status import fingerprint

SECTION = "projects"
PRIVATE_MESSAGE = "Private, not checked."


def link_of(item: dict) -> str:
    return str(item.get("url") or "").strip()


def _project_items(payload: dict) -> list[dict]:
    bag = ((payload.get("inventory") or {}).get("sections") or {}).get(SECTION) or {}
    return [
        item
        for item in bag.get("items") or []
        if isinstance(item, dict) and item.get("status") != "archived"
    ]


def _current(item: dict) -> dict | None:
    record = item.get("linkCheck")
    if not isinstance(record, dict):
        return None
    if record.get("fingerprint") != fingerprint(link_of(item)):
        return None
    return record


def _with_record(item: dict, record: dict | None) -> dict:
    out = {key: value for key, value in item.items() if key != "linkCheck"}
    if record is not None:
        out["linkCheck"] = record
    return out


def _new_record(item: dict, shape_result: dict, now: datetime | None) -> dict:
    return {
        "fingerprint": fingerprint(link_of(item)),
        "shape": shape_result.get("status"),
        "reach": None,
        "message": shape_result.get("message") or "",
        "checkedAt": (now or datetime.now(timezone.utc)).isoformat(),
        "languages": [],
        "private": False,
    }


def refresh_item(item: dict, *, now: datetime | None = None) -> dict:
    """Drop a stale result, and run the instant shape check if there is no current one."""
    if not link_of(item):
        return _with_record(item, None) if "linkCheck" in item else item
    if _current(item) is not None:
        return item
    result = shape.check_web_url(link_of(item))
    return _with_record(item, _new_record(item, result, now))


def refresh_payload(payload: dict, *, now: datetime | None = None) -> dict:
    """The instant check for every project link; part of every save."""
    sections = (payload.get("inventory") or {}).get("sections") or {}
    bag = sections.get(SECTION)
    if not isinstance(bag, dict) or not isinstance(bag.get("items"), list):
        return payload
    items = [
        refresh_item(item, now=now) if isinstance(item, dict) else item
        for item in bag["items"]
    ]
    if items == bag["items"]:
        return payload
    inventory = {
        **payload["inventory"],
        "sections": {**sections, SECTION: {**bag, "items": items}},
    }
    return {**payload, "inventory": inventory}


def needs_lookup(item: dict, *, force: bool = False) -> bool:
    link = link_of(item)
    if not link or shape.check_web_url(link)["status"] != "ok":
        return False
    record = _current(item)
    if record and record.get("private"):
        return False
    return force or not (record and record.get("reach") in ("exists", "not_found"))


def pending(payload: dict) -> bool:
    return any(needs_lookup(item) for item in _project_items(payload))


def _lookup(link: str) -> dict:
    if github.parse_repo_link(link):
        return github.lookup_repo(link)
    return reach.check_page(link)


def run_lookups(payload: dict, *, force: bool = False) -> dict:
    """{item_id: {"fingerprint", "reach"}} for each project link that needs a lookup."""
    results = {}
    for item in _project_items(payload):
        if item.get("id") and needs_lookup(item, force=force):
            link = link_of(item)
            results[item["id"]] = {
                "fingerprint": fingerprint(link),
                "reach": _lookup(link),
            }
    return results


def apply_results(
    payload: dict, results: dict, *, now: datetime | None = None
) -> dict:
    """Store each answer only if that entry's link is unchanged and not marked private."""
    sections = (payload.get("inventory") or {}).get("sections") or {}
    bag = sections.get(SECTION)
    if not isinstance(bag, dict):
        return payload
    items = []
    for item in bag.get("items") or []:
        result = results.get(item.get("id")) if isinstance(item, dict) else None
        link = link_of(item) if isinstance(item, dict) else ""
        if (
            result
            and link
            and fingerprint(link) == result["fingerprint"]
            and not (_current(item) or {}).get("private")
        ):
            answer = result["reach"]
            record = {
                **_new_record(item, shape.check_web_url(link), now),
                "reach": answer.get("status"),
                "message": answer.get("message") or "",
                "languages": list(answer.get("languages") or []),
            }
            item = _with_record(item, record)
        items.append(item)
    inventory = {
        **payload["inventory"],
        "sections": {**sections, SECTION: {**bag, "items": items}},
    }
    return {**payload, "inventory": inventory}


def set_private(
    payload: dict, item_id: str, private: bool, *, now: datetime | None = None
) -> dict:
    """Mark a project link as private ("can't be checked") or undo that."""
    sections = (payload.get("inventory") or {}).get("sections") or {}
    bag = sections.get(SECTION) or {}
    items = []
    found = False
    for item in bag.get("items") or []:
        if isinstance(item, dict) and item.get("id") == item_id:
            found = True
            if not link_of(item):
                raise ValueError("this project has no link")
            record = _current(item) or _new_record(
                item, shape.check_web_url(link_of(item)), now
            )
            record = {**record, "private": bool(private)}
            if private:
                record = {**record, "reach": None, "message": PRIVATE_MESSAGE, "languages": []}
            else:
                record = {**record, "reach": None, "message": ""}
            item = _with_record(item, record)
        items.append(item)
    if not found:
        raise KeyError(f"item not found in {SECTION}: {item_id}")
    inventory = {
        **payload["inventory"],
        "sections": {**sections, SECTION: {**bag, "items": items}},
    }
    return {**payload, "inventory": inventory}


def view(item: dict) -> dict:
    """What the project's badge says: level is one of
    empty, unchecked, broken, looks_right, exists, warning, private."""
    if not link_of(item):
        return {"level": "empty", "message": "", "languages": []}
    record = _current(item)
    if record is None:
        return {"level": "unchecked", "message": "", "languages": []}
    languages = list(record.get("languages") or [])
    message = record.get("message") or ""
    if record.get("private"):
        return {"level": "private", "message": PRIVATE_MESSAGE, "languages": []}
    if record.get("shape") == "broken":
        return {"level": "broken", "message": message, "languages": []}
    reach_status = record.get("reach")
    if reach_status == "exists":
        return {"level": "exists", "message": message, "languages": languages}
    if reach_status in ("not_found", "unavailable"):
        return {"level": "warning", "message": message, "languages": []}
    return {"level": "looks_right", "message": message, "languages": []}


def summary(payload: dict) -> dict:
    """{item_id: view} for every active project that has a link."""
    return {
        item["id"]: view(item)
        for item in _project_items(payload)
        if item.get("id") and link_of(item)
    }
