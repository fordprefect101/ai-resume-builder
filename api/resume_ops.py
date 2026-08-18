"""Generic resume list-section mutations (schemaVersion 3)."""

from datetime import datetime, timezone
import uuid

from section_registry import (
    BUILTIN_SECTION_ORDER,
    format_unknown_section,
    get_section_profile,
)


BASIC_FIELDS = ("fullName", "email", "phone", "location")
BASICS_UNVERIFIED = "Confirm your personal details before continuing."


def is_intake_in_progress(payload: dict) -> bool:
    return (payload.get("intake") or {}).get("status") == "in_progress"


def is_basics_verified(payload: dict) -> bool:
    intake = payload.get("intake") or {}
    return bool(intake.get("basicsVerified") or intake.get("basicsConfirmed"))


def require_basics_verified(payload: dict) -> None:
    if not is_basics_verified(payload):
        raise ValueError(BASICS_UNVERIFIED)


def _require_intake(payload: dict) -> None:
    if not is_intake_in_progress(payload):
        raise ValueError("intake is not in progress")


def _confirmed_empty_fields(
    empty_fields: list[str], confirmed_empty_fields: list[str] | None
) -> None:
    confirmed = set(confirmed_empty_fields or [])
    unconfirmed = [field for field in empty_fields if field not in confirmed]
    if unconfirmed:
        raise ValueError(
            "confirm intentionally empty fields before saving: "
            + ", ".join(unconfirmed)
        )


def _github_url(value: str) -> str:
    username = str(value or "").strip().lstrip("@")
    if "github.com/" in username:
        username = username.split("github.com/", 1)[1].split("/", 1)[0]
    username = username.strip("/")
    if not username:
        return ""
    return f"https://github.com/{username}"


def _linkedin_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if "linkedin.com/" in raw.lower():
        if raw.startswith("http://") or raw.startswith("https://"):
            return raw
        return f"https://{raw.lstrip('/')}"
    handle = raw.lstrip("@").strip("/")
    if handle.lower().startswith("in/"):
        handle = handle[3:]
    if not handle:
        return ""
    return f"https://www.linkedin.com/in/{handle}"


def _upsert_link(links: list[dict], label: str, url: str) -> list[dict]:
    kept = [
        link
        for link in links
        if str(link.get("label") or "").strip().lower() != label.lower()
    ]
    if url:
        kept.append({"label": label, "url": url})
    return kept


def update_basics(
    payload: dict,
    basics: dict,
    *,
    github: str | None = None,
    linkedin: str | None = None,
    verify: bool = False,
) -> dict:
    """
    Manual-only basics update. AI tools must not call this.
    verify=True requires a name and unlocks resume tools.
    Any save with verify=False clears the verification gate.
    """
    if not isinstance(basics, dict):
        raise ValueError("basics must be an object")

    cleaned = {
        field: str(basics.get(field) or "").strip() for field in BASIC_FIELDS
    }
    email = cleaned["email"]
    if email and "@" not in email:
        raise ValueError("email must contain @")

    existing = ((payload.get("inventory") or {}).get("basics") or {}).get("links")
    links: list[dict] = []
    if isinstance(existing, list):
        for link in existing:
            if not isinstance(link, dict):
                continue
            label = str(link.get("label") or "").strip()
            url = str(link.get("url") or "").strip()
            if label and url:
                links.append({"label": label, "url": url})
    incoming = basics.get("links")
    if isinstance(incoming, list):
        links = []
        for link in incoming:
            if not isinstance(link, dict):
                continue
            label = str(link.get("label") or "").strip()
            url = str(link.get("url") or "").strip()
            if label and url:
                links.append({"label": label, "url": url})

    if github is not None:
        links = _upsert_link(links, "GitHub", _github_url(github))
    if linkedin is not None:
        links = _upsert_link(links, "LinkedIn", _linkedin_url(linkedin))

    if verify and not cleaned["fullName"]:
        raise ValueError("fullName is required to verify personal details")

    inventory = dict(payload.get("inventory") or {})
    inventory["basics"] = {**cleaned, "links": links}
    intake = dict(payload.get("intake") or {})
    intake["basicsVerified"] = bool(verify)
    intake["basicsConfirmed"] = bool(verify)
    intake["basicsVerifiedAt"] = (
        datetime.now(timezone.utc).isoformat() if verify else None
    )
    return {**payload, "inventory": inventory, "intake": intake}


def set_skills(
    payload: dict,
    skills: list[str],
    *,
    confirmed_empty: bool = False,
) -> dict:
    """Set the flat skills list during intake only."""
    require_basics_verified(payload)
    _require_intake(payload)
    if not isinstance(skills, list):
        raise ValueError("skills must be an array")

    cleaned: list[str] = []
    for skill in skills:
        value = str(skill).strip()
        if value and value.lower() not in {s.lower() for s in cleaned}:
            cleaned.append(value)
    if not cleaned and not confirmed_empty:
        raise ValueError("confirm an intentionally empty skills list before saving")

    inventory = dict(payload.get("inventory") or {})
    inventory["skills"] = cleaned
    intake = dict(payload.get("intake") or {})
    intake["skillsConfirmed"] = True
    return {**payload, "inventory": inventory, "intake": intake}


def validate_intake_item_fields(
    payload: dict,
    section: str,
    fields: dict,
    confirmed_empty_fields: list[str] | None = None,
) -> None:
    """Require explicit confirmation for omitted optional interview fields."""
    if not is_intake_in_progress(payload):
        return

    profile = get_section_profile(section)
    intake_fields = profile.get("intakeFields") or (
        list(profile.get("requiredFields") or [])
        + [
            field
            for field in (profile.get("optionalFields") or [])
            if field not in {"categories", "skills", "status", "details"}
        ]
    )
    empty = []
    for field in intake_fields:
        value = fields.get(field)
        if value is None or value == "" or value == []:
            empty.append(field)
    _confirmed_empty_fields(empty, confirmed_empty_fields)


def complete_intake(
    payload: dict, confirmed_skipped_sections: list[str] | None = None
) -> dict:
    """Finish intake after basics, skills, and every built-in section are addressed."""
    require_basics_verified(payload)
    _require_intake(payload)
    intake = dict(payload.get("intake") or {})
    if not intake.get("skillsConfirmed"):
        raise ValueError("skills must be confirmed before completing intake")

    skipped = set(confirmed_skipped_sections or [])
    sections = _sections(payload)
    unresolved = [
        section
        for section in BUILTIN_SECTION_ORDER
        if not (sections.get(section) or {}).get("items") and section not in skipped
    ]
    if unresolved:
        raise ValueError(
            "confirm skipped sections before completing intake: "
            + ", ".join(unresolved)
        )

    intake["status"] = "complete"
    intake["confirmedSkippedSections"] = sorted(
        section for section in skipped if section in BUILTIN_SECTION_ORDER
    )
    return {**payload, "intake": intake}


def intake_context(payload: dict) -> dict:
    """Compact persisted state returned to Realtime after each intake tool."""
    inventory = payload.get("inventory") or {}
    sections = inventory.get("sections") or {}
    return {
        "intake": payload.get("intake") or {},
        "basicsVerified": is_basics_verified(payload),
        "basics": inventory.get("basics") or {},
        "skills": inventory.get("skills") or [],
        "sections": {
            key: {
                "title": (bag or {}).get("title") or key,
                "itemCount": len((bag or {}).get("items") or []),
                "itemIds": [
                    item.get("id")
                    for item in (bag or {}).get("items") or []
                    if item.get("id")
                ],
            }
            for key, bag in sections.items()
        },
    }


def _sections(payload: dict) -> dict:
    inventory = payload.get("inventory") or {}
    sections = inventory.get("sections")
    if not isinstance(sections, dict) or not sections:
        raise ValueError("payload has no inventory.sections (normalize to v3 first)")
    return sections


def _ensure_section(payload: dict, section: str) -> tuple[dict, dict, dict]:
    """Return (inventory, sections, section_bag). Raises KeyError if section missing."""
    if not isinstance(section, str) or not section.strip():
        raise ValueError("section is required")
    inventory = dict(payload.get("inventory") or {})
    sections = dict(_sections(payload))
    if section not in sections:
        raise KeyError(format_unknown_section(section, sections))
    bag = dict(sections[section] or {})
    if "items" not in bag or not isinstance(bag.get("items"), list):
        bag["items"] = list(bag.get("items") or [])
    if not bag.get("title"):
        bag["title"] = get_section_profile(section).get("title") or section
    return inventory, sections, bag


def _included_ids(resume: dict) -> dict:
    included = resume.get("includedIds")
    if not isinstance(included, dict):
        return {}
    return dict(included)


def _find_item(items: list, item_id: str) -> dict | None:
    for item in items:
        if item.get("id") == item_id:
            return item
    return None


def exclude_from_resume(payload: dict, section: str, item_id: str) -> dict:
    require_basics_verified(payload)
    profile = get_section_profile(section)
    if not profile.get("allowExclude", True):
        raise ValueError(f"exclude not allowed for section: {section}")

    _inventory, _sections_map, bag = _ensure_section(payload, section)
    if _find_item(bag["items"], item_id) is None:
        raise KeyError(f"item not found in {section}: {item_id}")

    resume = dict(payload.get("resume") or {})
    included = _included_ids(resume)
    ids = list(included.get(section) or [])
    included[section] = [i for i in ids if i != item_id]
    resume["includedIds"] = included
    return {**payload, "resume": resume}


def include_on_resume(payload: dict, section: str, item_id: str) -> dict:
    require_basics_verified(payload)
    _inventory, _sections_map, bag = _ensure_section(payload, section)
    if _find_item(bag["items"], item_id) is None:
        raise KeyError(f"item not found in {section}: {item_id}")

    resume = dict(payload.get("resume") or {})
    included = _included_ids(resume)
    ids = list(included.get(section) or [])
    if item_id not in ids:
        ids.append(item_id)
    included[section] = ids
    resume["includedIds"] = included
    return {**payload, "resume": resume}


def add_item(
    payload: dict,
    section: str,
    fields: dict,
    *,
    item_id: str | None = None,
) -> tuple[dict, str]:
    """
    Append item to inventory.sections[section].items and include on resume.
    Does not run LLM enrichment — caller applies that via apply_item_enrichment.
    """
    require_basics_verified(payload)
    profile = get_section_profile(section)
    if not profile.get("allowAdd", True):
        raise ValueError(f"add not allowed for section: {section}")

    inventory, sections, bag = _ensure_section(payload, section)
    items = list(bag["items"])

    required = profile.get("requiredFields") or []
    optional = profile.get("optionalFields") or []
    allowed = set(required) | set(optional) | {"id"}

    if not isinstance(fields, dict):
        raise ValueError("fields must be an object")

    missing = [
        key
        for key in required
        if fields.get(key) is None
        or (isinstance(fields.get(key), str) and not str(fields.get(key)).strip())
    ]
    if missing:
        required_list = ", ".join(required)
        raise ValueError(
            f"missing required field{'s' if len(missing) != 1 else ''} "
            f"for {section}: {', '.join(missing)}. required: {required_list}"
        )

    unknown = [k for k in fields if k not in allowed]
    if unknown:
        allowed_list = ", ".join(sorted(allowed))
        raise ValueError(
            f"unknown fields for {section}: {', '.join(unknown)}. "
            f"allowed: {allowed_list}"
        )

    new_id = item_id or fields.get("id") or f"{profile['idPrefix']}{uuid.uuid4().hex[:8]}"
    if _find_item(items, new_id) is not None:
        raise ValueError(f"item id already exists in {section}: {new_id}")

    item: dict = {"id": new_id, "status": fields.get("status") or "active"}

    for key in required:
        item[key] = fields[key]

    for key in optional:
        if key == "status":
            continue
        if key not in fields:
            # Sensible defaults for list-ish fields
            if key in ("bullets", "technologies", "categories", "skills", "details"):
                item[key] = []
            elif key in ("description", "url", "location", "startDate", "endDate", "date"):
                item[key] = ""
            continue
        item[key] = fields[key]

    # Enrichment placeholders when those fields exist on the profile
    if "categories" in optional and "categories" not in item:
        item["categories"] = []
    if "skills" in optional and "skills" not in item:
        item["skills"] = []

    items.append(item)
    bag["items"] = items
    sections[section] = bag
    inventory["sections"] = sections

    resume = dict(payload.get("resume") or {})
    included = _included_ids(resume)
    ids = list(included.get(section) or [])
    if new_id not in ids:
        ids.append(new_id)
    included[section] = ids
    resume["includedIds"] = included

    # Ensure section appears in sectionOrder
    order = list(resume.get("sectionOrder") or [])
    if section not in order:
        order.append(section)
    resume["sectionOrder"] = order

    return {**payload, "inventory": inventory, "resume": resume}, new_id


def apply_item_enrichment(
    payload: dict, section: str, item_id: str, enrichment: dict
) -> dict:
    inventory, sections, bag = _ensure_section(payload, section)
    items = []
    found = False
    for item in bag["items"]:
        if item.get("id") == item_id:
            found = True
            updated = dict(item)
            if "categories" in enrichment:
                updated["categories"] = enrichment.get("categories") or []
            if "skills" in enrichment:
                updated["skills"] = enrichment.get("skills") or []
            if "bullets" in enrichment:
                updated["bullets"] = (
                    enrichment.get("bullets") or updated.get("bullets") or []
                )
            items.append(updated)
        else:
            items.append(item)
    if not found:
        raise KeyError(f"item not found in {section}: {item_id}")

    bag["items"] = items
    sections[section] = bag
    inventory["sections"] = sections
    return {**payload, "inventory": inventory}


def reorder_sections(payload: dict, section_order: list[str]) -> dict:
    """Set resume.sectionOrder. Rejects unknown keys; appends omitted sections."""
    require_basics_verified(payload)
    sections = _sections(payload)

    if not section_order:
        raise ValueError("sectionOrder must be a non-empty list")

    seen: list[str] = []
    for key in section_order:
        if not isinstance(key, str) or not key:
            raise ValueError("sectionOrder entries must be non-empty strings")
        if key not in sections:
            raise KeyError(format_unknown_section(key, sections))
        if key not in seen:
            seen.append(key)

    prev = list((payload.get("resume") or {}).get("sectionOrder") or [])
    for key in prev:
        if key in sections and key not in seen:
            seen.append(key)
    for key in sections:
        if key not in seen:
            seen.append(key)

    resume = dict(payload.get("resume") or {})
    resume["sectionOrder"] = seen
    return {**payload, "resume": resume}


def reorder_items(payload: dict, section: str, item_ids: list[str]) -> dict:
    """
    Reorder inventory.sections[section].items.
    itemIds must be a full permutation of existing item ids.
    """
    require_basics_verified(payload)
    inventory, sections, bag = _ensure_section(payload, section)
    items = list(bag.get("items") or [])
    by_id = {item.get("id"): item for item in items if item.get("id")}
    existing = [item.get("id") for item in items if item.get("id")]

    if not item_ids:
        raise ValueError("itemIds must be a non-empty list")

    seen: list[str] = []
    for item_id in item_ids:
        if not isinstance(item_id, str) or not item_id:
            raise ValueError("itemIds entries must be non-empty strings")
        if item_id not in by_id:
            raise KeyError(f"item not found in {section}: {item_id}")
        if item_id not in seen:
            seen.append(item_id)

    missing = [item_id for item_id in existing if item_id not in seen]
    if missing:
        raise ValueError(
            f"itemIds must include every item in {section}: missing {missing}"
        )

    bag["items"] = [by_id[item_id] for item_id in seen]
    sections[section] = bag
    inventory["sections"] = sections

    resume = dict(payload.get("resume") or {})
    included = _included_ids(resume)
    included_set = set(included.get(section) or [])
    included[section] = [item_id for item_id in seen if item_id in included_set]
    resume["includedIds"] = included

    return {**payload, "inventory": inventory, "resume": resume}


def section_catalog(payload: dict) -> dict[str, list[dict]]:
    """
    Compact catalogs per section for the model: id, labels, onResume, status.
    """
    sections = _sections(payload)
    resume = payload.get("resume") or {}
    included_map = _included_ids(resume)
    out: dict[str, list[dict]] = {}

    for section, bag in sections.items():
        profile = get_section_profile(section)
        label_fields = profile.get("labelFields") or []
        included = set(included_map.get(section) or [])
        entries = []
        for item in bag.get("items") or []:
            entry = {
                "id": item.get("id"),
                "onResume": item.get("id") in included,
                "status": item.get("status"),
            }
            for lf in label_fields:
                entry[lf] = item.get(lf)
            entries.append(entry)
        out[section] = entries
    return out


def get_item(payload: dict, section: str, item_id: str) -> dict:
    _inventory, _sections_map, bag = _ensure_section(payload, section)
    item = _find_item(bag["items"], item_id)
    if item is None:
        raise KeyError(f"item not found in {section}: {item_id}")
    return item