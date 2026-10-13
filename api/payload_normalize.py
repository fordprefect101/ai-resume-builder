"""Normalize older payloads to schemaVersion 5 (sections + includedIds maps, story + points)."""

import hashlib

from section_registry import (
    BUILTIN_SECTION_ORDER,
    empty_included_ids,
    empty_sections_bag,
    get_section_profile,
)
from claims import is_point, new_point, point_id, with_point_defaults
from facts import ensure_facts, with_fact_defaults

SCHEMA_VERSION = 5


def normalize_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return _blank_v5()

    if payload.get("schemaVersion") in (3, 4, 5) and isinstance(
        (payload.get("inventory") or {}).get("sections"), dict
    ):
        out = _ensure_intake_flags(payload)
    else:
        out = _ensure_intake_flags(_v2_to_v4(payload))
    return _to_v5(ensure_facts(out))


def _story_id(section: str, item_id: str, text: str, occurrence: int) -> str:
    digest = hashlib.sha1(
        f"{section}|{item_id}|{occurrence}|{text}".encode()
    ).hexdigest()
    return f"story_{digest[:10]}"


def _to_v5(payload: dict) -> dict:
    """
    Give every bullet-bearing item a story, a writing marker, and point records.
    Points mirror item.bullets for now; safe to run repeatedly.
    """
    inventory = dict(payload.get("inventory") or {})
    sections = dict(inventory.get("sections") or {})
    claims = payload.get("claims") or []
    existing_points = {c.get("id"): c for c in claims if is_point(c)}
    points: list[dict] = []

    for section, bag in sections.items():
        if not isinstance(bag, dict):
            continue
        if not get_section_profile(section).get("polishBullets"):
            continue
        items = []
        for item in bag.get("items") or []:
            if not isinstance(item, dict) or not item.get("id"):
                items.append(item)
                continue
            item_id = item["id"]
            bullets = [
                b
                for b in (item.get("bullets") or [])
                if isinstance(b, str) and b.strip()
            ]

            seen: dict[str, int] = {}
            story = []
            for order, bullet in enumerate(bullets):
                occurrence = seen.get(bullet, 0)
                seen[bullet] = occurrence + 1
                kept = existing_points.get(
                    point_id(section, item_id, bullet, occurrence)
                )
                if kept:
                    points.append(with_point_defaults({**kept, "order": order}))
                else:
                    points.append(
                        new_point(
                            section, item_id, bullet, order, occurrence=occurrence
                        )
                    )
                story.append(
                    {
                        "id": _story_id(section, item_id, bullet, occurrence),
                        "text": bullet,
                        "source": "legacy",
                        "at": None,
                    }
                )

            updated = dict(item)
            if not isinstance(updated.get("story"), list):
                updated["story"] = story
            if not isinstance(updated.get("writing"), dict):
                updated["writing"] = {
                    "status": "idle",
                    "questions": [],
                    "followUpsAsked": 0,
                }
            items.append(updated)
        sections[section] = {**bag, "items": items}

    inventory["sections"] = sections
    return {
        **payload,
        "schemaVersion": SCHEMA_VERSION,
        "inventory": inventory,
        "facts": [
            with_fact_defaults(f) if isinstance(f, dict) else f
            for f in (payload.get("facts") or [])
        ],
        "claims": [c for c in claims if not is_point(c)] + points,
    }


def _ensure_intake_flags(payload: dict) -> dict:
    intake = dict(payload.get("intake") or {})
    if "basicsVerified" not in intake:
        intake["basicsVerified"] = bool(intake.get("basicsConfirmed"))
    if "basicsConfirmed" not in intake:
        intake["basicsConfirmed"] = bool(intake.get("basicsVerified"))
    next_payload = dict(payload)
    next_payload["intake"] = intake
    return next_payload


def _blank_v5() -> dict:
    return _to_v5(ensure_facts(_blank_v3()))


def _blank_v3() -> dict:
    return {
        "schemaVersion": 3,
        "intake": {
            "status": "not_started",
            "basicsVerified": False,
            "basicsConfirmed": False,
        },
        "inventory": {
            "basics": {
                "fullName": "",
                "email": "",
                "phone": "",
                "location": "",
                "links": [],
            },
            "skills": [],
            "sections": empty_sections_bag(),
        },
        "resume": {
            "title": "General Resume",
            "summary": "",
            "includedIds": empty_included_ids(),
            "sectionOrder": list(BUILTIN_SECTION_ORDER),
        },
    }


def _v2_to_v3(payload: dict) -> dict:
    inv_in = payload.get("inventory") if isinstance(payload.get("inventory"), dict) else {}
    resume_in = payload.get("resume") if isinstance(payload.get("resume"), dict) else {}

    # Flat v1 fallback: lists at top level
    if not inv_in and any(k in payload for k in ("experience", "projects")):
        inv_in = payload

    sections = empty_sections_bag()
    for key in BUILTIN_SECTION_ORDER:
        items = inv_in.get(key) or []
        if not isinstance(items, list):
            items = []
        sections[key] = {
            "title": sections[key]["title"],
            "items": items,
        }

    basics = inv_in.get("basics") or payload.get("basics") or {}
    skills = inv_in.get("skills") or payload.get("skills") or []
    if not isinstance(skills, list):
        skills = []

    included = empty_included_ids()
    # v2 camelCase lists
    mapping = {
        "experience": "includedExperienceIds",
        "projects": "includedProjectIds",
        "education": "includedEducationIds",
        "achievements": "includedAchievementIds",
    }
    for section, old_key in mapping.items():
        ids = resume_in.get(old_key)
        if ids is None and isinstance(resume_in.get("includedIds"), dict):
            ids = resume_in["includedIds"].get(section)
        if ids is None:
            ids = [i.get("id") for i in sections[section]["items"] if i.get("id")]
        included[section] = [i for i in (ids or []) if i]

    order = resume_in.get("sectionOrder") or list(BUILTIN_SECTION_ORDER)
    order = [s for s in order if s in sections] or list(BUILTIN_SECTION_ORDER)

    return {
        "schemaVersion": 4,
        "intake": {
            "status": "not_started",
            "basicsVerified": False,
            "basicsConfirmed": False,
        },
        "inventory": {
            "basics": {
                "fullName": basics.get("fullName") or "",
                "email": basics.get("email") or "",
                "phone": basics.get("phone") or "",
                "location": basics.get("location") or "",
                "links": basics.get("links") or [],
            },
            "skills": skills,
            "sections": sections,
        },
        "resume": {
            "title": resume_in.get("title") or "General Resume",
            "summary": resume_in.get("summary") or "",
            "includedIds": included,
            "sectionOrder": order,
        },
        "facts": [],
        "claims": [],
        "variants": {},
    }


def _v2_to_v4(payload: dict) -> dict:
    v3 = _v2_to_v3(payload)
    v3["schemaVersion"] = 4
    v3["facts"] = []
    v3["claims"] = []
    v3["variants"] = {}
    return v3