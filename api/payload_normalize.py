"""Normalize older payloads to schemaVersion 3 (sections + includedIds maps)."""

from section_registry import (
    BUILTIN_SECTION_ORDER,
    empty_included_ids,
    empty_sections_bag,
)


def normalize_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return _blank_v3()

    if payload.get("schemaVersion") == 3 and isinstance(
        (payload.get("inventory") or {}).get("sections"), dict
    ):
        return payload

    return _v2_to_v3(payload)


def _blank_v3() -> dict:
    return {
        "schemaVersion": 3,
        "intake": {"status": "not_started"},
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
        "schemaVersion": 3,
        "intake": {"status": "not_started"},
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
    }