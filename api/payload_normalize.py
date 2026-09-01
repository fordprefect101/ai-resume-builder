"""Normalize older payloads to schemaVersion 3/4 (sections + includedIds maps)."""

from section_registry import (
    BUILTIN_SECTION_ORDER,
    empty_included_ids,
    empty_sections_bag,
)
from facts import ensure_facts


def normalize_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return _blank_v4()

    if payload.get("schemaVersion") in (3, 4) and isinstance(
        (payload.get("inventory") or {}).get("sections"), dict
    ):
        out = _ensure_intake_flags(payload)
        if out.get("schemaVersion") != 4:
            out = {**out, "schemaVersion": 4}
        return ensure_facts(out)

    return ensure_facts(_ensure_intake_flags(_v2_to_v4(payload)))


def _ensure_intake_flags(payload: dict) -> dict:
    intake = dict(payload.get("intake") or {})
    if "basicsVerified" not in intake:
        intake["basicsVerified"] = bool(intake.get("basicsConfirmed"))
    if "basicsConfirmed" not in intake:
        intake["basicsConfirmed"] = bool(intake.get("basicsVerified"))
    next_payload = dict(payload)
    next_payload["intake"] = intake
    return next_payload


def _blank_v4() -> dict:
    base = _blank_v3()
    base["schemaVersion"] = 4
    return ensure_facts(base)


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