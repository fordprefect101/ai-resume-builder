
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
            if "categories" in enrichment:
                updated["categories"] = enrichment.get("categories") or []
            if "skills" in enrichment:
                updated["skills"] = enrichment.get("skills") or []
            if "bullets" in enrichment:
                updated["bullets"] = enrichment.get("bullets") or updated.get("bullets") or []
            projects.append(updated)
        else:
            projects.append(project)
    inventory["projects"] = projects
    return {**payload, "inventory": inventory}

def exclude_experience_from_resume(payload: dict, experience_id: str) -> dict:
    """Soft-remove: drop experience_id from resume view; keep inventory intact."""
    inventory = payload.get("inventory") or {}
    experience = inventory.get("experience") or []

    if not any(e.get("id") == experience_id for e in experience):
        raise KeyError(f"experience not found: {experience_id}")

    resume = dict(payload.get("resume") or {})
    included = list(resume.get("includedExperienceIds") or [])
    resume["includedExperienceIds"] = [eid for eid in included if eid != experience_id]

    return {**payload, "resume": resume}


def include_experience_on_resume(payload: dict, experience_id: str) -> dict:
    """Soft-include: add experience_id to resume view if it exists in inventory."""
    inventory = payload.get("inventory") or {}
    experience = inventory.get("experience") or []

    if not any(e.get("id") == experience_id for e in experience):
        raise KeyError(f"experience not found: {experience_id}")

    resume = dict(payload.get("resume") or {})
    included = list(resume.get("includedExperienceIds") or [])
    if experience_id not in included:
        included.append(experience_id)
    resume["includedExperienceIds"] = included

    return {**payload, "resume": resume}


def add_experience(
    payload: dict,
    *,
    company: str,
    title: str,
    location: str = "",
    start_date: str = "",
    end_date: str = "",
    bullets: list[str] | None = None,
    experience_id: str | None = None,
) -> tuple[dict, str]:
    """Add to inventory and include on the current resume view. No field updates later."""
    inventory = dict(payload.get("inventory") or {})
    experience = list(inventory.get("experience") or [])
    new_id = experience_id or f"exp_{uuid.uuid4().hex[:8]}"
    if any(e.get("id") == new_id for e in experience):
        raise ValueError(f"experience id already exists: {new_id}")

    item = {
        "id": new_id,
        "company": company,
        "title": title,
        "location": location,
        "startDate": start_date,
        "endDate": end_date,
        "bullets": bullets or [],
        "categories": [],
        "skills": [],
        "status": "active",
    }
    experience.append(item)
    inventory["experience"] = experience

    resume = dict(payload.get("resume") or {})
    included = list(resume.get("includedExperienceIds") or [])
    if new_id not in included:
        included.append(new_id)
    resume["includedExperienceIds"] = included

    return {**payload, "inventory": inventory, "resume": resume}, new_id


def apply_experience_enrichment(
    payload: dict, experience_id: str, enrichment: dict
) -> dict:
    inventory = dict(payload.get("inventory") or {})
    items = []
    for item in inventory.get("experience") or []:
        if item.get("id") == experience_id:
            updated = dict(item)
            if "categories" in enrichment:
                updated["categories"] = enrichment.get("categories") or []
            if "skills" in enrichment:
                updated["skills"] = enrichment.get("skills") or []
            if "bullets" in enrichment:
                updated["bullets"] = enrichment.get("bullets") or updated.get("bullets") or []
            items.append(updated)
        else:
            items.append(item)
    inventory["experience"] = items
    return {**payload, "inventory": inventory}