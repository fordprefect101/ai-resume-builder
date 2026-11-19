from resume_ops import (
    add_item,
    apply_item_enrichment,
    complete_intake,
    exclude_from_resume,
    get_item,
    include_on_resume,
    intake_context,
    is_intake_in_progress,
    reorder_items,
    reorder_sections,
    section_catalog,
    set_skills,
    validate_intake_item_fields,
)
from enrichment import enrich_section_item
from facts import sync_facts_from_item
from timing import timed
import work_projects
from story_chunks import with_story
from context_selector import select_resume_context

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
    {
        "type": "function",
        "name": "reorder_items",
        "description": (
            "Reorder items within one section. Pass the full list of item ids "
            "in the desired order."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "section": {"type": "string"},
                "itemIds": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["section", "itemIds"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "search_resume_context",
        "description": (
            "Read-only search for exact resume item ids relevant to a phrase. "
            "Use before mutating when the current candidate slice is missing or ambiguous."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "section": {
                    "type": "string",
                    "description": "Optional section key to restrict the search.",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
]

_JOB_REF = {
    "section": {
        "type": "string",
        "description": "The section holding the job. Almost always experience.",
    },
    "itemId": {
        "type": "string",
        "description": "The id of the JOB the project belongs to (not the project's own id).",
    },
}

ADD_PROJECT_TOOL = {
    "type": "function",
    "name": "add_project",
    "description": (
        "Add a named project that was done inside a job (for example a recommendation "
        "engine built at ChaiShots). Use this for work that belongs to a job; projects "
        "done on your own go in the projects section with add_item. Optional technologies "
        "and first points are saved as the person said them."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            **_JOB_REF,
            "name": {"type": "string", "description": "A short name, at most 120 characters."},
            "technologies": {"type": "array", "items": {"type": "string"}},
            "bullets": {
                "type": "array",
                "items": {"type": "string"},
                "description": "What the person said they did, in their own words.",
            },
        },
        "required": ["itemId", "name"],
        "additionalProperties": False,
    },
}

EDIT_PROJECT_TOOLS = [
    {
        "type": "function",
        "name": "rename_project",
        "description": "Rename a project inside a job. Find its projectId with search_resume_context.",
        "parameters": {
            "type": "object",
            "properties": {
                **_JOB_REF,
                "projectId": {"type": "string"},
                "name": {"type": "string"},
            },
            "required": ["itemId", "projectId", "name"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "archive_project",
        "description": (
            "Hide a project inside a job. Its points are kept, not deleted. "
            "Find its projectId with search_resume_context."
        ),
        "parameters": {
            "type": "object",
            "properties": {**_JOB_REF, "projectId": {"type": "string"}},
            "required": ["itemId", "projectId"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "reorder_projects",
        "description": (
            "Put a job's active projects in a new order. Pass every active project id of that job."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                **_JOB_REF,
                "projectIds": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["itemId", "projectIds"],
            "additionalProperties": False,
        },
    },
]

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
        "Finish intake after skills and all built-in sections were addressed. "
        "Personal details are confirmed in the app, not through this tool."
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

# Voice only: hangs up the call. Typed chat is not offered it (nothing to hang up).
END_VOICE_SESSION_TOOL = {
    "type": "function",
    "name": "end_voice_session",
    "description": (
        "End the voice call. Say a short goodbye first, then call this. Use it when "
        "intake is complete (after complete_intake), the person says they are done, "
        "or an edit request is finished and they have nothing more. Never call it "
        "while another tool call is still running."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

TOOL_DEFINITIONS.extend([ADD_PROJECT_TOOL, *EDIT_PROJECT_TOOLS])

INTAKE_TOOL_DEFINITIONS = [
    SET_SKILLS_TOOL,
    TOOL_DEFINITIONS[2],
    ADD_PROJECT_TOOL,
    COMPLETE_INTAKE_TOOL,
]


def tools_for_payload(payload: dict) -> list[dict]:
    return (
        INTAKE_TOOL_DEFINITIONS
        if is_intake_in_progress(payload)
        else TOOL_DEFINITIONS
    )


def voice_tools_for_payload(payload: dict) -> list[dict]:
    """The tools of the voice call: the chat tools plus the one that ends the call."""
    return [*tools_for_payload(payload), END_VOICE_SESSION_TOOL]


def execute_tool(
    payload: dict, name: str, arguments: dict, typed_words: str | None = None
) -> tuple[dict, dict]:
    if name == "search_resume_context":
        return payload, {
            "ok": True,
            "mutated": False,
            "context": select_resume_context(
                payload,
                arguments.get("query") or "",
                section=arguments.get("section") or None,
            ),
        }

    if name == "set_basics":
        raise ValueError(
            "Personal details are manual-only and cannot be changed by tools"
        )

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
        new_payload = with_story(new_payload, section, new_id, [typed_words], "typed")
        item = get_item(new_payload, section, new_id)
        with timed("tidy_up"):
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

    if name == "reorder_items":
        section = arguments["section"]
        new_payload = reorder_items(payload, section, arguments["itemIds"])
        return new_payload, {
            "ok": True,
            "section": section,
            "itemIds": [
                item.get("id")
                for item in new_payload["inventory"]["sections"][section]["items"]
            ],
        }

    if name == "add_project":
        section = arguments.get("section") or "experience"
        new_payload, project_id = work_projects.add_project(
            payload,
            section,
            arguments["itemId"],
            arguments["name"],
            technologies=arguments.get("technologies"),
            bullets=arguments.get("bullets"),
        )
        new_payload = with_story(
            new_payload, section, arguments["itemId"], [typed_words], "typed", project_id=project_id
        )
        job = get_item(new_payload, section, arguments["itemId"])
        project = work_projects.get_project(new_payload, section, arguments["itemId"], project_id)
        new_payload = sync_facts_from_item(new_payload, section, job, project=project)
        return new_payload, {"ok": True, "section": section, "itemId": arguments["itemId"], "projectId": project_id}

    if name == "rename_project":
        section = arguments.get("section") or "experience"
        new_payload = work_projects.rename_project(
            payload, section, arguments["itemId"], arguments["projectId"], arguments["name"]
        )
        return new_payload, {"ok": True, "section": section, "projectId": arguments["projectId"]}

    if name == "archive_project":
        section = arguments.get("section") or "experience"
        new_payload = work_projects.archive_project(
            payload, section, arguments["itemId"], arguments["projectId"]
        )
        return new_payload, {"ok": True, "section": section, "projectId": arguments["projectId"]}

    if name == "reorder_projects":
        section = arguments.get("section") or "experience"
        new_payload = work_projects.reorder_projects(
            payload, section, arguments["itemId"], arguments["projectIds"]
        )
        return new_payload, {"ok": True, "section": section, "itemId": arguments["itemId"]}

    raise ValueError(f"unknown tool: {name}")
