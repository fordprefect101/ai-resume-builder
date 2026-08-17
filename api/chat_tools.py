from resume_ops import (
    exclude_from_resume,
    include_on_resume,
    add_item,
    apply_item_enrichment,
    reorder_sections,
    section_catalog,
    get_item,
)
from enrichment import enrich_section_item

# Re-export for callers that import catalogs from chat_tools
__all__ = [
    "TOOL_DEFINITIONS",
    "execute_tool",
    "section_catalog",
]

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "name": "exclude_from_resume",
        "description": (
            "Soft-remove an item from the current resume view by section. "
            "Keeps it in inventory. Prefer this over deleting."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "section": {
                    "type": "string",
                    "description": "e.g. experience, projects, education, achievements",
                },
                "itemId": {"type": "string"},
            },
            "required": ["section", "itemId"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "include_on_resume",
        "description": "Add an existing inventory item back onto the resume view.",
        "parameters": {
            "type": "object",
            "properties": {
                "section": {"type": "string"},
                "itemId": {"type": "string"},
            },
            "required": ["section", "itemId"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "add_item",
        "description": (
            "Create a new item in a section and include it on the resume. "
            "Pass section-specific fields (e.g. company/title for experience, "
            "name for projects, institution/degree for education, title for achievements)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "section": {"type": "string"},
                "fields": {
                    "type": "object",
                    "description": "Item fields for that section (no id required)",
                },
            },
            "required": ["section", "fields"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "reorder_sections",
        "description": (
            "Reorder resume sections. Pass the full desired order of section keys."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sectionOrder": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["sectionOrder"],
            "additionalProperties": False,
        },
    },
]


def execute_tool(payload: dict, name: str, arguments: dict) -> tuple[dict, dict]:
    if name == "exclude_from_resume":
        section = arguments["section"]
        item_id = arguments["itemId"]
        new_payload = exclude_from_resume(payload, section, item_id)
        return new_payload, {"ok": True, "section": section, "itemId": item_id}

    if name == "include_on_resume":
        section = arguments["section"]
        item_id = arguments["itemId"]
        new_payload = include_on_resume(payload, section, item_id)
        return new_payload, {"ok": True, "section": section, "itemId": item_id}

    if name == "add_item":
        section = arguments["section"]
        fields = arguments.get("fields") or {}
        new_payload, new_id = add_item(payload, section, fields)
        item = get_item(new_payload, section, new_id)
        enrichment = enrich_section_item(section, item)
        if enrichment:
            new_payload = apply_item_enrichment(
                new_payload, section, new_id, enrichment
            )
        return new_payload, {
            "ok": True,
            "section": section,
            "itemId": new_id,
            "enrichment": enrichment,
        }

    if name == "reorder_sections":
        new_payload = reorder_sections(payload, arguments["sectionOrder"])
        return new_payload, {
            "ok": True,
            "sectionOrder": new_payload["resume"]["sectionOrder"],
        }

    raise ValueError(f"unknown tool: {name}")
