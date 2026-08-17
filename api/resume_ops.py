"""Generic resume list-section mutations (schemaVersion 3)."""

import uuid

from section_registry import get_section_profile


def _sections(payload: dict) -> dict:
    inventory = payload.get("inventory") or {}
    sections = inventory.get("sections")
    if not isinstance(sections, dict) or not sections:
        raise ValueError("payload has no inventory.sections (normalize to v3 first)")
    return sections


def _ensure_section(payload: dict, section: str) -> tuple[dict, dict, dict]:
    """Return (inventory, sections, section_bag). Raises KeyError if section missing."""
    inventory = dict(payload.get("inventory") or {})
    sections = dict(_sections(payload))
    if section not in sections:
        raise KeyError(f"unknown section: {section}")
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

    for key in required:
        val = fields.get(key)
        if val is None or (isinstance(val, str) and not val.strip()):
            raise ValueError(f"missing required field: {key}")

    unknown = [k for k in fields if k not in allowed]
    if unknown:
        raise ValueError(f"unknown fields for {section}: {unknown}")

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
    sections = _sections(payload)

    if not section_order:
        raise ValueError("sectionOrder must be a non-empty list")

    seen: list[str] = []
    for key in section_order:
        if not isinstance(key, str) or not key:
            raise ValueError("sectionOrder entries must be non-empty strings")
        if key not in sections:
            raise KeyError(f"unknown section: {key}")
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