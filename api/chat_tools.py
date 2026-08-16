import json
from resume_ops import (
    exclude_project_from_resume,
    include_project_on_resume,
    add_project,
    apply_project_enrichment,
)
from enrichment import enrich_project, polish_project_bullets

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "name": "exclude_project_from_resume",
        "description": (
            "Soft-remove a project from the current resume view. "
            "Keeps it in inventory. Prefer this over deleting."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "projectId": {
                    "type": "string",
                    "description": "Stable project id, e.g. proj_music",
                }
            },
            "required": ["projectId"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "include_project_on_resume",
        "description": "Add an existing inventory project back onto the resume view.",
        "parameters": {
            "type": "object",
            "properties": {
                "projectId": {"type": "string"},
            },
            "required": ["projectId"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "add_project",
        "description": (
            "Create a new project in inventory and include it on the resume. "
            "Enrichment (categories/skills) runs automatically."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "technologies": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "bullets": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "url": {"type": "string"},
            },
            "required": ["name"],
            "additionalProperties": False,
        },
    },
]


def project_catalog(payload: dict) -> list[dict]:
    """Compact list so the model can resolve names → ids."""
    projects = (payload.get("inventory") or {}).get("projects") or []
    included = set((payload.get("resume") or {}).get("includedProjectIds") or [])
    return [
        {
            "id": p.get("id"),
            "name": p.get("name"),
            "onResume": p.get("id") in included,
            "status": p.get("status"),
            "categories": p.get("categories") or [],
        }
        for p in projects
    ]


def execute_tool(payload: dict, name: str, arguments: dict) -> tuple[dict, dict]:
    """
    Apply one tool. Returns (new_payload, result_summary).
    """
    if name == "exclude_project_from_resume":
        project_id = arguments["projectId"]
        new_payload = exclude_project_from_resume(payload, project_id)
        return new_payload, {"ok": True, "projectId": project_id}

    if name == "include_project_on_resume":
        project_id = arguments["projectId"]
        new_payload = include_project_on_resume(payload, project_id)
        return new_payload, {"ok": True, "projectId": project_id}

    if name == "add_project":
        new_payload, new_id = add_project(
            payload,
            name=arguments["name"],
            description=arguments.get("description") or "",
            technologies=arguments.get("technologies") or [],
            bullets=arguments.get("bullets") or [],
            url=arguments.get("url") or "",
        )
        project = next(
            p for p in new_payload["inventory"]["projects"] if p["id"] == new_id
        )
        enrichment = enrich_project(project)
        polished = polish_project_bullets(project)
        enrichment = {**enrichment, **polished}
        new_payload = apply_project_enrichment(new_payload, new_id, enrichment)
        return new_payload, {
            "ok": True,
            "projectId": new_id,
            "enrichment": enrichment,
        }
    raise ValueError(f"unknown tool: {name}")