"""
Operations on the named projects inside a job (for example the "Recommendation
engine" project inside the ChaiShots job).

Every function takes a payload and returns a new one; nothing here saves. Callers
save through the single save door in main.py. Points are changed only through
claims.set_item_points, never directly.
"""

from __future__ import annotations

import uuid

from claims import section_holds_projects, set_item_points
from payload_normalize import blank_writing, legacy_story
from resume_ops import _ensure_section, _find_item, require_basics_verified

NAME_CAP = 120
TECHNOLOGY_CAP = 20
TECHNOLOGY_LENGTH_CAP = 60


def _clean_name(name) -> str:
    text = " ".join(str(name or "").split())
    if not text:
        raise ValueError("a project needs a name")
    if len(text) > NAME_CAP:
        raise ValueError(f"project names are at most {NAME_CAP} characters")
    return text


def _clean_technologies(technologies) -> list[str]:
    cleaned: list[str] = []
    for tech in technologies if isinstance(technologies, list) else []:
        text = " ".join(str(tech or "").split())[:TECHNOLOGY_LENGTH_CAP]
        if text and text.lower() not in {t.lower() for t in cleaned}:
            cleaned.append(text)
    return cleaned[:TECHNOLOGY_CAP]


def _locate(payload: dict, section: str, item_id: str):
    """(inventory, sections, bag, job). Raises if the section or job is unknown."""
    require_basics_verified(payload)
    if not section_holds_projects(section):
        raise ValueError(f"{section} does not hold projects inside its entries")
    inventory, sections, bag = _ensure_section(payload, section)
    job = _find_item(bag["items"], item_id)
    if job is None:
        raise KeyError(f"item not found in {section}: {item_id}")
    return inventory, sections, bag, job


def _write_back(payload: dict, section: str, inventory, sections, bag, job: dict, projects: list):
    bag["items"] = [
        {**job, "projects": projects} if item.get("id") == job["id"] else item
        for item in bag["items"]
    ]
    sections[section] = bag
    inventory["sections"] = sections
    return {**payload, "inventory": inventory}


def _active(projects: list) -> list[dict]:
    return [p for p in projects if isinstance(p, dict) and p.get("status") != "archived"]


def _require_unique(projects: list, name: str, *, ignore: str | None = None) -> None:
    taken = {
        p.get("name", "").lower()
        for p in _active(projects)
        if p.get("id") != ignore
    }
    if name.lower() in taken:
        raise ValueError(f"this job already has a project named {name!r}")


def _find_project(projects: list, project_id: str) -> dict:
    for project in projects:
        if isinstance(project, dict) and project.get("id") == project_id:
            return project
    raise KeyError(f"project not found: {project_id}")


def get_project(payload: dict, section: str, item_id: str, project_id: str) -> dict:
    job = _find_item(
        (((payload.get("inventory") or {}).get("sections") or {}).get(section) or {}).get("items") or [],
        item_id,
    )
    if job is None:
        raise KeyError(f"item not found in {section}: {item_id}")
    return _find_project(job.get("projects") or [], project_id)


def add_project(
    payload: dict,
    section: str,
    item_id: str,
    name: str,
    *,
    technologies=None,
    bullets=None,
    project_id: str | None = None,
) -> tuple[dict, str]:
    """Add a project to a job, optionally with its technologies and first points."""
    inventory, sections, bag, job = _locate(payload, section, item_id)
    name = _clean_name(name)
    projects = [p for p in (job.get("projects") or []) if isinstance(p, dict)]
    _require_unique(projects, name)

    new_id = project_id or f"wp_{uuid.uuid4().hex[:8]}"
    if any(p.get("id") == new_id for p in projects):
        raise ValueError(f"project id already exists in this job: {new_id}")

    texts = [t.strip() for t in (bullets if isinstance(bullets, list) else []) if isinstance(t, str) and t.strip()]
    project = {
        "id": new_id,
        "name": name,
        "technologies": _clean_technologies(technologies),
        "status": "active",
        "story": legacy_story(section, f"{item_id}/{new_id}", texts),
        "writing": blank_writing(),
        "bullets": [],
    }
    new_payload = _write_back(payload, section, inventory, sections, bag, job, projects + [project])
    if texts:
        new_payload = set_item_points(new_payload, section, item_id, texts, project_id=new_id)
    return new_payload, new_id


def rename_project(payload: dict, section: str, item_id: str, project_id: str, name: str) -> dict:
    inventory, sections, bag, job = _locate(payload, section, item_id)
    name = _clean_name(name)
    projects = [p for p in (job.get("projects") or []) if isinstance(p, dict)]
    _find_project(projects, project_id)
    _require_unique(projects, name, ignore=project_id)
    projects = [{**p, "name": name} if p.get("id") == project_id else p for p in projects]
    return _write_back(payload, section, inventory, sections, bag, job, projects)


def archive_project(payload: dict, section: str, item_id: str, project_id: str) -> dict:
    """Hide a project. Its points are kept, not deleted."""
    inventory, sections, bag, job = _locate(payload, section, item_id)
    projects = [p for p in (job.get("projects") or []) if isinstance(p, dict)]
    target = _find_project(projects, project_id)
    if target.get("status") == "archived":
        raise ValueError("this project is already archived")
    projects = [{**p, "status": "archived"} if p.get("id") == project_id else p for p in projects]
    return _write_back(payload, section, inventory, sections, bag, job, projects)


def reorder_projects(payload: dict, section: str, item_id: str, project_ids: list[str]) -> dict:
    """
    Put a job's active projects in the given order. `project_ids` must name every
    active project exactly once; archived projects keep their order after them.
    """
    inventory, sections, bag, job = _locate(payload, section, item_id)
    projects = [p for p in (job.get("projects") or []) if isinstance(p, dict)]
    active = _active(projects)
    archived = [p for p in projects if p.get("status") == "archived"]
    by_id = {p["id"]: p for p in active}

    if not project_ids:
        raise ValueError("projectIds must be a non-empty list")
    seen: list[str] = []
    for project_id in project_ids:
        if not isinstance(project_id, str) or not project_id:
            raise ValueError("projectIds entries must be non-empty strings")
        if project_id not in by_id:
            raise KeyError(f"project not found: {project_id}")
        if project_id not in seen:
            seen.append(project_id)
    missing = [pid for pid in by_id if pid not in seen]
    if missing:
        raise ValueError(f"projectIds must include every active project: missing {missing}")

    return _write_back(payload, section, inventory, sections, bag, job, [by_id[i] for i in seen] + archived)
