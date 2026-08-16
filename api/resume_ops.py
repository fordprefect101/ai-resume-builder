
import uuid
def exclude_project_from_resume(payload: dict, project_id: str) -> dict:
    """Soft-remove: drop project_id from resume view; keep inventory intact."""
    inventory = payload.get("inventory") or {}
    projects = inventory.get("projects") or []

    if not any(p.get("id") == project_id for p in projects):
        raise KeyError(f"project not found: {project_id}")

    resume = dict(payload.get("resume") or {})
    included = list(resume.get("includedProjectIds") or [])
    resume["includedProjectIds"] = [pid for pid in included if pid != project_id]

    return {
        **payload,
        "resume": resume,
    }

def include_project_on_resume(payload: dict, project_id: str) -> dict:
    """Soft-include: add project_id to resume view if it exists in inventory."""
    inventory = payload.get("inventory") or {}
    projects = inventory.get("projects") or []

    if not any(p.get("id") == project_id for p in projects):
        raise KeyError(f"project not found: {project_id}")

    resume = dict(payload.get("resume") or {})
    included = list(resume.get("includedProjectIds") or [])
    if project_id not in included:
        included.append(project_id)
    resume["includedProjectIds"] = included

    return {
        **payload,
        "resume": resume,
    }

def add_project(
    payload: dict,
    *,
    name: str,
    description: str = "",
    technologies: list[str] | None = None,
    bullets: list[str] | None = None,
    url: str = "",
    project_id: str | None = None,
) -> dict:
    """Add to inventory and include on the current resume view."""
    inventory = dict(payload.get("inventory") or {})
    projects = list(inventory.get("projects") or [])
    new_id = project_id or f"proj_{uuid.uuid4().hex[:8]}"
    if any(p.get("id") == new_id for p in projects):
        raise ValueError(f"project id already exists: {new_id}")
    project = {
        "id": new_id,
        "name": name,
        "description": description,
        "technologies": technologies or [],
        "bullets": bullets or [],
        "url": url,
        "categories": [],
        "skills": [],
        "status": "active",
    }
    projects.append(project)
    inventory["projects"] = projects
    resume = dict(payload.get("resume") or {})
    included = list(resume.get("includedProjectIds") or [])
    if new_id not in included:
        included.append(new_id)
    resume["includedProjectIds"] = included
    return {
        **payload,
        "inventory": inventory,
        "resume": resume,
    }, new_id

def apply_project_enrichment(payload: dict, project_id: str, enrichment: dict) -> dict:
    inventory = dict(payload.get("inventory") or {})
    projects = []
    for project in inventory.get("projects") or []:
        if project.get("id") == project_id:
            updated = dict(project)
            updated["categories"] = enrichment.get("categories") or []
            updated["skills"] = enrichment.get("skills") or []
            projects.append(updated)
        else:
            projects.append(project)
    inventory["projects"] = projects
    return {**payload, "inventory": inventory}

