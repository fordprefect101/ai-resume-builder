from resume_ops import (
    add_item,
    apply_item_enrichment,
    complete_intake,
    exclude_from_resume,
    get_item,
    include_on_resume,
    intake_context,
    is_intake_in_progress,
    reorder_sections,
    section_catalog,
    set_basics,
    set_skills,
    validate_intake_item_fields,
)
from enrichment import enrich_section_item

# Re-export for callers that import catalogs from chat_tools
__all__ = [
    "INTAKE_TOOL_DEFINITIONS",
    "TOOL_DEFINITIONS",
    "execute_tool",
    "section_catalog",
    "tools_for_payload",
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
                "confirmedEmptyFields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Intake only: fields explicitly confirmed as blank."
                    ),
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

SET_BASICS_TOOL = {
    "type": "function",
    "name": "set_basics",
    "description": (
        "Save personal basics during intake only. Ask one field at a time and "
        "explicitly confirm every blank before calling."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "basics": {
                "type": "object",
                "properties": {
                    "fullName": {"type": "string"},
                    "email": {"type": "string"},
                    "phone": {"type": "string"},
                    "location": {"type": "string"},
                    "links": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string"},
                                "url": {"type": "string"},
                            },
                            "required": ["label", "url"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["fullName", "email", "phone", "location", "links"],
                "additionalProperties": False,
            },
            "githubUsername": {
                "type": "string",
                "description": (
                    "GitHub username only, when the user has a technical background."
                ),
            },
            "confirmedEmptyFields": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["basics", "confirmedEmptyFields"],
        "additionalProperties": False,
    },
}

SET_SKILLS_TOOL = {
    "type": "function",
    "name": "set_skills",
    "description": (
        "Save background-appropriate skills during intake. Confirm an empty list first."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "skills": {"type": "array", "items": {"type": "string"}},
            "confirmedEmpty": {"type": "boolean"},
        },
        "required": ["skills", "confirmedEmpty"],
        "additionalProperties": False,
    },
}

COMPLETE_INTAKE_TOOL = {
    "type": "function",
    "name": "complete_intake",
    "description": (
        "Finish intake after basics, skills, and all built-in sections were addressed."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "confirmedSkippedSections": {
                "type": "array",
                "items": {"type": "string"},
            }
        },
        "required": ["confirmedSkippedSections"],
        "additionalProperties": False,
    },
}

INTAKE_TOOL_DEFINITIONS = [
    SET_BASICS_TOOL,
    SET_SKILLS_TOOL,
    TOOL_DEFINITIONS[2],
    COMPLETE_INTAKE_TOOL,
]


def tools_for_payload(payload: dict) -> list[dict]:
    return (
        INTAKE_TOOL_DEFINITIONS
        if is_intake_in_progress(payload)
        else TOOL_DEFINITIONS
    )


def execute_tool(payload: dict, name: str, arguments: dict) -> tuple[dict, dict]:
    if name == "set_basics":
        new_payload = set_basics(
            payload,
            arguments["basics"],
            github_username=arguments.get("githubUsername") or "",
            confirmed_empty_fields=arguments.get("confirmedEmptyFields") or [],
        )
        return new_payload, {
            "ok": True,
            "intakeContext": intake_context(new_payload),
        }

    if name == "set_skills":
        new_payload = set_skills(
            payload,
            arguments.get("skills") or [],
            confirmed_empty=bool(arguments.get("confirmedEmpty")),
        )
        return new_payload, {
            "ok": True,
            "intakeContext": intake_context(new_payload),
        }

    if name == "complete_intake":
        new_payload = complete_intake(
            payload, arguments.get("confirmedSkippedSections") or []
        )
        return new_payload, {
            "ok": True,
            "mode": "edit",
            "intakeContext": intake_context(new_payload),
        }

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
        validate_intake_item_fields(
            payload,
            section,
            fields,
            arguments.get("confirmedEmptyFields") or [],
        )
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
            "intakeContext": intake_context(new_payload)
            if is_intake_in_progress(new_payload)
            else None,
        }

    if name == "reorder_sections":
        new_payload = reorder_sections(payload, arguments["sectionOrder"])
        return new_payload, {
            "ok": True,
            "sectionOrder": new_payload["resume"]["sectionOrder"],
        }

    raise ValueError(f"unknown tool: {name}")
